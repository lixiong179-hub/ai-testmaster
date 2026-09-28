"""自愈管理端点模块。

提供自愈审计记录查询、回滚与项目级自愈配置管理 API。

路由（由 main.py 以 prefix=/api/v1 挂载）:
    - GET  /self-healing/audits                          分页查询审计记录
    - GET  /self-healing/audits/{audit_id}               审计详情
    - POST /self-healing/audits/{audit_id}/rollback      回滚自愈变更
    - GET  /projects/{project_id}/self-healing-config    查询项目自愈配置
    - PUT  /projects/{project_id}/self-healing-config    更新项目自愈配置

权限: 所有端点需 Bearer 令牌认证；项目配置端点额外校验项目归属。

设计说明:
    service 层（SelfHealingAuditService / SelfHealingConfigService）接受 sync Session
    且内部自管事务（commit/rollback），因此端点采用 async + asyncio.to_thread 模式，
    为每次调用新建独立 sync 会话，避免与 get_current_user 注入的 async 会话混用
    （参考 app/api/v1/endpoints/audit_log.py 的既有模式）。
"""
import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import PrimarySessionLocal, async_get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.self_healing import (
    AuditListResponse,
    AuditResponse,
    RollbackResponse,
    SelfHealingConfigResponse,
    SelfHealingConfigUpdate,
)
from app.services.self_healing.audit_service import SelfHealingAuditService
from app.services.self_healing.config_service import (
    CONFIG_KEY,
    DEFAULT_SELF_HEALING_CONFIG,
    SelfHealingConfigService,
)

router = APIRouter(tags=["自愈管理"])


async def _verify_project_owner(
    db: AsyncSession, project_id: int, user_id: int
) -> None:
    """校验项目归属当前用户，不存在或无权限抛 403。"""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == user_id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )


def _to_audit_response(audit: Any) -> AuditResponse:
    """将 SelfHealingAudit ORM 对象转换为响应模型（Decimal 置信度由 Pydantic 强转 float）。"""
    return AuditResponse.model_validate(audit)


def _run_sync(fn: Callable[[Session], Any]) -> Any:
    """在线程池中执行 sync service 调用，独立 sync 会话，结束即关闭。

    service 内部自管事务，故为每次调用新建独立 sync 会话；HTTPException/ValueError
    等异常原样向上抛出，由端点层统一捕获转译。
    """
    sync_db = PrimarySessionLocal()
    try:
        return fn(sync_db)
    finally:
        sync_db.close()


@router.get(
    "/self-healing/audits",
    response_model=ApiResponse[AuditListResponse],
    summary="分页查询自愈审计记录",
)
async def list_audits(
    project_id: int | None = Query(None, description="项目ID过滤"),
    test_case_id: int | None = Query(None, description="用例ID过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """分页查询自愈审计记录，支持按项目/用例过滤。

    传入 project_id 时校验当前用户对该项目的访问权限；未传 project_id 时
    仅校验登录态（简化策略，与 spec 允许的"登录即可查"一致）。
    """
    try:
        if project_id is not None:
            await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> tuple[list[Any], int]:
            service = SelfHealingAuditService(sync_db)
            return service.list_audits(
                project_id=project_id,
                test_case_id=test_case_id,
                page=page,
                page_size=page_size,
            )

        records, total = await asyncio.to_thread(_run_sync, _do)
        items = [_to_audit_response(r) for r in records]
        data = AuditListResponse(
            items=items, total=total, page=page, page_size=page_size
        )
        return create_response(data=data.model_dump(), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询自愈审计失败: {e}")
        raise HTTPException(status_code=500, detail="查询自愈审计失败")


@router.get(
    "/self-healing/audits/{audit_id}",
    response_model=ApiResponse[AuditResponse],
    summary="自愈审计详情",
)
async def get_audit(
    audit_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取单条自愈审计记录详情，不存在返回 404。"""
    try:
        def _do(sync_db: Session) -> Any:
            service = SelfHealingAuditService(sync_db)
            return service.get_audit(audit_id)

        audit = await asyncio.to_thread(_run_sync, _do)
        if audit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"审计记录 {audit_id} 不存在",
            )
        data = _to_audit_response(audit)
        return create_response(data=data.model_dump(), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取自愈审计详情失败: {e}")
        raise HTTPException(status_code=500, detail="获取自愈审计详情失败")


@router.post(
    "/self-healing/audits/{audit_id}/rollback",
    response_model=ApiResponse[RollbackResponse],
    summary="回滚自愈变更",
)
async def rollback_audit(
    audit_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """回滚指定审计记录的自愈变更，恢复旧选择器并写入回滚审计。

    异常映射:
        - 审计记录不存在: 404（service 抛 HTTPException）
        - old_selector/locator_id 为空: 400（service 抛 ValueError）
        - 定位器版本并发冲突: 409（service 抛 HTTPException）
    """
    try:
        def _do(sync_db: Session) -> Any:
            service = SelfHealingAuditService(sync_db)
            return service.rollback_audit(audit_id)

        new_audit = await asyncio.to_thread(_run_sync, _do)
        data = RollbackResponse(
            audit_id=audit_id,
            restored_selector=new_audit.new_selector or "",
            new_audit_id=new_audit.id,
            message="回滚成功",
        )
        return create_response(data=data.model_dump(), msg="回滚成功")
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"回滚自愈审计失败: {e}")
        raise HTTPException(status_code=500, detail="回滚自愈审计失败")


@router.get(
    "/projects/{project_id}/self-healing-config",
    response_model=ApiResponse[SelfHealingConfigResponse],
    summary="查询项目自愈配置",
)
async def get_self_healing_config(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """查询项目级自愈配置（enabled 已合并全局开关，全局关则必为 False）。"""
    try:
        await _verify_project_owner(db, project_id, current_user.id)

        def _do(sync_db: Session) -> dict:
            service = SelfHealingConfigService(sync_db)
            return service.get_project_config(project_id)

        config = await asyncio.to_thread(_run_sync, _do)
        data = SelfHealingConfigResponse(**config)
        return create_response(data=data.model_dump(), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目自愈配置失败: {e}")
        raise HTTPException(status_code=500, detail="获取项目自愈配置失败")


@router.put(
    "/projects/{project_id}/self-healing-config",
    response_model=ApiResponse[SelfHealingConfigResponse],
    summary="更新项目自愈配置",
)
async def update_self_healing_config(
    project_id: int,
    config_data: SelfHealingConfigUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """更新项目级自愈配置，仅更新传入字段，未传字段保留原值。

    service.set_project_config 会用默认值填充缺失字段并整体覆盖 self_healing_config
    子键，因此这里先读取原始存储配置（未合并全局开关）与默认值合并后再传入，
    避免部分更新时未传字段被重置为默认值。字段合法性由 service 层强校验。
    """
    try:
        await _verify_project_owner(db, project_id, current_user.id)
        update_dict = config_data.model_dump(exclude_unset=True)

        def _do(sync_db: Session) -> dict:
            service = SelfHealingConfigService(sync_db)
            project = (
                sync_db.query(Project)
                .filter(Project.id == project_id)
                .first()
            )
            if project is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"项目不存在: {project_id}",
                )
            raw = project.config if isinstance(project.config, dict) else {}
            stored = raw.get(CONFIG_KEY, {})
            stored = stored if isinstance(stored, dict) else {}
            merged = {**DEFAULT_SELF_HEALING_CONFIG, **stored, **update_dict}
            return service.set_project_config(project_id, merged)

        config = await asyncio.to_thread(_run_sync, _do)
        data = SelfHealingConfigResponse(**config)
        return create_response(data=data.model_dump(), msg="更新成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新项目自愈配置失败: {e}")
        raise HTTPException(status_code=500, detail="更新项目自愈配置失败")
