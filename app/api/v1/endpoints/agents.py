"""Agent API 端点模块。

提供 Agent 会话管理与 HITL 审计审批/回滚的 REST 接口。

路由（由 main.py 以 prefix=/api/v1 挂载，本路由器自带 prefix=/agents）:
    - POST /agents/sessions                              创建并启动 Agent 会话
    - GET  /agents/sessions                              分页查询会话列表
    - GET  /agents/sessions/{session_id}                 查询单个会话
    - GET  /agents/sessions/{session_id}/messages        查询会话消息流
    - POST /agents/sessions/{session_id}/cancel          取消会话
    - POST /agents/audits/{audit_id}/approve             审批审计动作
    - POST /agents/audits/{audit_id}/rollback            回滚审计动作

设计说明:
    - SessionService / AgentAuditService 接收 AsyncSession 且仅 flush 不 commit，
      端点在变更操作后显式 await db.commit() 落库。
    - 创建会话仅落库 running 记录，不调用 AgentRuntime.run，避免阻塞 HTTP 请求；
      真正的 Runtime 调用由后台任务或后续专门端点触发。
    - 异常映射: AgentError→400, NotImplementedError→501, HTTPException 透传, 其他→500。
    - 复用 execution_core._helpers.verify_project_permission_async 校验项目归属，避免重复。
"""
from typing import Any, List, NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.execution_core._helpers import (
    verify_project_permission_async,
)
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.agent_audit import AgentAudit
from app.models.agent_session import AgentSession
from app.models.user import User
from app.schemas.agent import (
    ApprovalRequest,
    AuditResponse,
    MessageResponse,
    RollbackRequest,
    RollbackResponse,
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
)
from app.schemas.common import ApiResponse
# 仅轻量导入 Artifact 基类（pydantic 模型）用于类型注解；
# ArtifactRegistry / 具体 artifact 类 / AgentRuntime 均在函数内延迟导入 ——
# 它们会连带加载 _tool_executor 等重依赖，顶层导入会在 HTTP 请求中触发
# 跨事件循环问题（实测 POST /agents/sessions 返回 500）。
from app.services.agent.artifacts.base import Artifact
from app.services.agent.audit_service import AgentAuditService
from app.services.agent.exceptions import AgentError
from app.services.agent.metrics import get_metrics
from app.services.agent.session_service import SessionService

router = APIRouter(prefix="/agents", tags=["agents"])

# 服务单例：无内部状态，可安全复用
_session_service = SessionService()
_audit_service = AgentAuditService()
_metrics = get_metrics()

def _build_artifact_registry():
    """构造并注册全部内置 artifact 类的注册表（延迟导入重依赖）。"""
    from app.services.agent.artifact_registry import ArtifactRegistry
    from app.services.agent.artifacts import (
        ApplicationStateArtifact,
        ExecutionStateArtifact,
        FailureHistoryArtifact,
        ProjectContextArtifact,
        TestCaseArtifact,
        UserIntentArtifact,
    )

    registry = ArtifactRegistry()
    for artifact_class in (
        TestCaseArtifact,
        ExecutionStateArtifact,
        ApplicationStateArtifact,
        ProjectContextArtifact,
        FailureHistoryArtifact,
        UserIntentArtifact,
    ):
        registry.register(artifact_class)
    return registry


def _parse_initial_artifacts(raw: List[dict]) -> List[Artifact]:
    """把请求体中的 artifact dict 校验为 Artifact 实例。

    约定格式：{"artifact_type": "<已注册类型>", "data": {...}}
    未注册类型或数据不合 schema 时抛 AgentError（由 _raise_for_agent 映射为 400）。
    """
    from pydantic import ValidationError

    if not raw:
        return []
    registry = _build_artifact_registry()
    artifacts: List[Artifact] = []
    for item in raw:
        artifact_type = item.get("artifact_type")
        if not artifact_type:
            raise AgentError("initial_artifacts 元素缺少 artifact_type 字段")
        data = item.get("data") or {}
        try:
            artifacts.append(registry.validate(artifact_type, data))
        except KeyError as e:
            raise AgentError(f"未注册的 artifact 类型: {artifact_type}") from e
        except ValidationError as e:
            raise AgentError(f"artifact 数据校验失败({artifact_type}): {e}") from e
    return artifacts


def _build_runtime(db: AsyncSession):
    """构造 AgentRuntime —— 测试替换点（mock Runtime 时 patch 本函数）。

    延迟导入：AgentRuntime 会连带加载 _tool_executor 等重依赖，
    顶层导入会在 HTTP 请求中触发跨事件循环问题。
    """
    from app.services.agent.runtime import AgentRuntime

    return AgentRuntime(db=db)


def _raise_for_agent(e: Exception, action: str) -> NoReturn:
    """统一异常转译：HTTPException 透传，NotImplementedError→501，AgentError→400，其他→500。"""
    if isinstance(e, HTTPException):
        raise e
    if isinstance(e, NotImplementedError):
        raise HTTPException(
            status_code=http_status.HTTP_501_NOT_IMPLEMENTED, detail=str(e)
        )
    if isinstance(e, AgentError):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    logger.error(f"{action}失败: {e}")
    raise HTTPException(
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{action}失败",
    )


async def _check_session_ownership(
    db: AsyncSession, session_id: int, current_user: User,
) -> Optional[AgentSession]:
    """校验当前用户是否为指定会话的所有者，超级管理员绕过。

    会话不存在返回 None（由调用方按现有契约决定 404/400/空列表）；
    存在但 created_by 非本人且非超管抛 403，防止 IDOR 越权访问他人会话。
    """
    session = await _session_service.get_session(db, session_id)
    if session is None:
        return None
    if session.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="无权限操作此会话",
        )
    return session


async def _check_audit_session_ownership(
    db: AsyncSession, audit_id: int, current_user: User,
) -> None:
    """按 audit_id 查询审计记录，校验其关联会话的归属。

    审计记录不存在时不抛错（由后续 service 调用抛 AgentError→400，保持契约）；
    存在则校验 session 归属，越权抛 403。AgentAudit.session_id ondelete=CASCADE，
    审计存在即意味着会话存在，无需单独处理会话缺失。
    """
    audit = (
        await db.execute(select(AgentAudit).where(AgentAudit.id == audit_id))
    ).scalar_one_or_none()
    if audit is None:
        return
    await _check_session_ownership(db, audit.session_id, current_user)


@router.post(
    "/sessions",
    response_model=ApiResponse[SessionResponse],
    summary="创建并启动 Agent 会话",
    description=(
        "校验 agent_type 合法性与项目访问权限后，落库 running 状态会话。"
        "不立即调用 AgentRuntime.run（避免阻塞 HTTP），Runtime 由后续端点触发。"
    ),
)
async def create_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """创建 Agent 会话。

    agent_type 合法性由 SessionService.create_session 校验，非法值返回 400。
    initial_artifacts 由后续 Runtime 触发端点消费，本端点不处理。
    """
    try:
        await verify_project_permission_async(db, req.project_id, current_user.id)
        session = await _session_service.create_session(
            db,
            agent_type=req.agent_type,
            project_id=req.project_id,
            created_by=current_user.id,
        )
        await db.commit()
        data = SessionResponse.model_validate(session)
        return create_response(data=data.model_dump(), msg="会话创建成功")
    except Exception as e:
        _raise_for_agent(e, "创建Agent会话")


@router.get(
    "/sessions",
    response_model=ApiResponse[SessionListResponse],
    summary="分页查询 Agent 会话列表",
    description="支持按 project_id/agent_type/status 过滤，按 id 倒序分页返回。",
)
async def list_sessions(
    project_id: int | None = Query(None, description="项目ID过滤"),
    agent_type: str | None = Query(None, description="Agent类型过滤"),
    status: str | None = Query(None, description="会话状态过滤"),
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分页查询会话列表。非法 agent_type/status 由 service 校验返回 400。"""
    try:
        sessions, total = await _session_service.list_sessions(
            db,
            project_id=project_id,
            agent_type=agent_type,
            status=status,
            offset=offset,
            limit=limit,
        )
        items = [SessionResponse.model_validate(s) for s in sessions]
        data = SessionListResponse(items=items, total=total)
        return create_response(data=data.model_dump(), msg="获取成功")
    except Exception as e:
        _raise_for_agent(e, "查询会话列表")


@router.get(
    "/sessions/{session_id}",
    response_model=ApiResponse[SessionResponse],
    summary="查询单个 Agent 会话",
    description="按 ID 查询会话详情，不存在返回 404。",
)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按 ID 查询会话，不存在返回 404，非本人会话返回 403。"""
    try:
        session = await _check_session_ownership(db, session_id, current_user)
        if session is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在: {session_id}",
            )
        data = SessionResponse.model_validate(session)
        return create_response(data=data.model_dump(), msg="获取成功")
    except Exception as e:
        _raise_for_agent(e, "查询Agent会话")


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ApiResponse[List[MessageResponse]],
    summary="查询会话消息流",
    description="按时间升序返回会话消息流，最多 limit 条。",
)
async def list_messages(
    session_id: int,
    limit: int = Query(50, ge=1, le=500, description="返回消息条数上限"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """按时间升序返回会话消息流。非本人会话返回 403。"""
    try:
        await _check_session_ownership(db, session_id, current_user)
        messages = await _session_service.get_history(db, session_id, limit=limit)
        data = [MessageResponse.model_validate(m).model_dump() for m in messages]
        return create_response(data=data, msg="获取成功")
    except Exception as e:
        _raise_for_agent(e, "查询会话消息")


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=ApiResponse[SessionResponse],
    summary="取消 Agent 会话",
    description="将指定会话置为 cancelled 状态，会话不存在返回 400。",
)
async def cancel_session(
    session_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """取消会话（status=cancelled）。非本人会话返回 403。"""
    try:
        await _check_session_ownership(db, session_id, current_user)
        session = await _session_service.cancel_session(db, session_id)
        await db.commit()
        data = SessionResponse.model_validate(session)
        return create_response(data=data.model_dump(), msg="会话已取消")
    except Exception as e:
        _raise_for_agent(e, "取消Agent会话")


@router.get(
    "/sessions/{session_id}/audits",
    response_model=ApiResponse[List[AuditResponse]],
    summary="查询会话审计（工具调用）记录",
    description=(
        "R1-3：按 id 升序返回该会话的完整审计链。"
        "复用 _check_session_ownership 防越权（非本人会话 403、超管绕过）。"
    ),
)
async def list_session_audits(
    session_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询指定会话的审计记录；会话不存在时返回空列表（与 messages 端点契约一致）。"""
    try:
        await _check_session_ownership(db, session_id, current_user)
        audits = await _audit_service.get_session_audit(db, session_id)
        data = [AuditResponse.model_validate(a).model_dump() for a in audits]
        return create_response(data=data, msg="获取成功")
    except Exception as e:
        _raise_for_agent(e, "查询会话审计")


@router.post(
    "/sessions/run",
    response_model=ApiResponse[SessionResponse],
    summary="创建并驱动 Agent 会话运行",
    description=(
        "R1-2：校验项目归属后调用 AgentRuntime.run 真实执行并落库。"
        "与 POST /sessions 的区别 —— 后者仅落库 running 记录不驱动 Runtime，"
        "本端点会驱动 Runtime 直到会话终态（completed / failed）。"
    ),
)
async def run_session(
    req: SessionCreateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """创建并驱动 Agent 会话运行。

    Runtime 自身不提交事务（仅 flush），本端点在 run 返回后显式 commit。
    """
    try:
        await verify_project_permission_async(db, req.project_id, current_user.id)
        runtime = _build_runtime(db)
        session = await runtime.run(
            agent_type=req.agent_type,
            project_id=req.project_id,
            initial_artifacts=_parse_initial_artifacts(req.initial_artifacts),
            created_by=current_user.id,
        )
        await db.commit()
        return create_response(
            data=SessionResponse.model_validate(session).model_dump(),
            msg="Agent 会话执行完成",
        )
    except Exception as e:
        _raise_for_agent(e, "执行Agent会话")


@router.post(
    "/audits/{audit_id}/approve",
    response_model=ApiResponse[AuditResponse],
    summary="审批 Agent 审计动作",
    description="标记审计记录审批结果（批准/拒绝），并记录 HITL 审批指标。",
)
async def approve_audit(
    audit_id: int,
    req: ApprovalRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """HITL 审批：approved=True 批准，False 拒绝。审计记录不存在返回 400，非本人会话返回 403。"""
    try:
        await _check_audit_session_ownership(db, audit_id, current_user)
        audit = await _audit_service.approve_action(
            db,
            audit_id=audit_id,
            approved_by=current_user.id,
            approved=req.approved,
        )
        await db.commit()
        _metrics.record_approval("approve" if req.approved else "reject")
        data = AuditResponse.model_validate(audit)
        return create_response(data=data.model_dump(), msg="审批成功")
    except Exception as e:
        _raise_for_agent(e, "审批Agent动作")


@router.post(
    "/audits/{audit_id}/rollback",
    response_model=ApiResponse[RollbackResponse],
    summary="回滚 Agent 审计动作",
    description=(
        "回滚已记录的 Agent 动作，写入补偿审计记录。"
        "未注册回滚处理器的 action_type 返回 501，审计记录不存在返回 400。"
    ),
)
async def rollback_audit(
    audit_id: int,
    req: RollbackRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """回滚审计动作。original_action_type 由回滚审计 action_type 去前缀推导。非本人会话返回 403。"""
    try:
        await _check_audit_session_ownership(db, audit_id, current_user)
        new_audit = await _audit_service.rollback_action(
            db,
            audit_id=audit_id,
            rolled_by=current_user.id,
            reason=req.reason,
        )
        await db.commit()
        original_action_type = new_audit.action_type.removeprefix("rollback_")
        data = RollbackResponse(
            audit_id=audit_id,
            original_action_type=original_action_type,
            rolled_back=True,
            new_audit_id=new_audit.id,
        )
        return create_response(data=data.model_dump(), msg="回滚成功")
    except Exception as e:
        _raise_for_agent(e, "回滚Agent动作")
