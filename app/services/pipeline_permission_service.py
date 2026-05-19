"""
Pipeline 权限服务模块

本模块提供 Pipeline 专用权限体系的校验和初始化功能，
与通用 RBAC 并行，管理流水线相关权限。

核心函数概览：
    - check_pipeline_permission : 校验 Pipeline 权限（含 scope 维度）
    - require_permission : FastAPI Depends 装饰器
    - init_pipeline_roles : 初始化预定义角色和权限（幂等）
    - assign_pipeline_role : 分配 Pipeline 角色
    - revoke_pipeline_role : 撤销 Pipeline 角色

角色定义：
    - admin : 全部权限
    - qa_lead : 迭代负责人权限
    - qa_engineer : 评审者权限
    - viewer : 只读权限

依赖关系：
    - app.models.pipeline_permission : PipelineRole, PipelinePermission, pipeline_user_role
    - app.services.audit_service : 审计日志
"""
import logging
from typing import Optional, Callable, Any

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline_permission import PipelineRole, PipelinePermission, pipeline_user_role

logger = logging.getLogger(__name__)


def _get_current_user():
    """延迟导入 get_current_user 避免循环依赖。"""
    from app.api.v1.endpoints.auth import get_current_user
    return get_current_user

ROLE_DEFINITIONS = {
    "admin": {
        "description": "Pipeline 管理员，拥有全部权限",
        "permissions": [
            {"resource": "iteration", "action": "create", "scope": "all"},
            {"resource": "iteration", "action": "read", "scope": "all"},
            {"resource": "iteration", "action": "update", "scope": "all"},
            {"resource": "iteration", "action": "delete", "scope": "all"},
            {"resource": "pipeline", "action": "start", "scope": "all"},
            {"resource": "pipeline", "action": "read", "scope": "all"},
            {"resource": "pipeline", "action": "cancel", "scope": "all"},
            {"resource": "review", "action": "approve", "scope": "all"},
            {"resource": "review", "action": "reject", "scope": "all"},
            {"resource": "review", "action": "finalize", "scope": "all"},
            {"resource": "test_case", "action": "create", "scope": "all"},
            {"resource": "test_case", "action": "read", "scope": "all"},
            {"resource": "test_case", "action": "update", "scope": "all"},
            {"resource": "test_case", "action": "delete", "scope": "all"},
            {"resource": "report", "action": "read", "scope": "all"},
            {"resource": "config", "action": "read", "scope": "all"},
            {"resource": "config", "action": "update", "scope": "all"},
        ],
    },
    "qa_lead": {
        "description": "迭代负责人，可创建迭代、启动流水线、定稿评审",
        "permissions": [
            {"resource": "iteration", "action": "create", "scope": "project"},
            {"resource": "iteration", "action": "read", "scope": "project"},
            {"resource": "iteration", "action": "update", "scope": "own"},
            {"resource": "pipeline", "action": "start", "scope": "project"},
            {"resource": "pipeline", "action": "read", "scope": "project"},
            {"resource": "pipeline", "action": "cancel", "scope": "own"},
            {"resource": "review", "action": "approve", "scope": "project"},
            {"resource": "review", "action": "reject", "scope": "project"},
            {"resource": "review", "action": "finalize", "scope": "project"},
            {"resource": "test_case", "action": "create", "scope": "project"},
            {"resource": "test_case", "action": "read", "scope": "project"},
            {"resource": "test_case", "action": "update", "scope": "project"},
            {"resource": "report", "action": "read", "scope": "project"},
            {"resource": "config", "action": "read", "scope": "project"},
        ],
    },
    "qa_engineer": {
        "description": "评审者，可评审用例、查看报告",
        "permissions": [
            {"resource": "iteration", "action": "read", "scope": "project"},
            {"resource": "pipeline", "action": "read", "scope": "project"},
            {"resource": "review", "action": "approve", "scope": "own"},
            {"resource": "review", "action": "reject", "scope": "own"},
            {"resource": "test_case", "action": "read", "scope": "project"},
            {"resource": "test_case", "action": "update", "scope": "own"},
            {"resource": "report", "action": "read", "scope": "project"},
        ],
    },
    "viewer": {
        "description": "只读用户，可查看用例和报告",
        "permissions": [
            {"resource": "iteration", "action": "read", "scope": "project"},
            {"resource": "pipeline", "action": "read", "scope": "project"},
            {"resource": "test_case", "action": "read", "scope": "project"},
            {"resource": "report", "action": "read", "scope": "project"},
        ],
    },
}

SCOPE_HIERARCHY = {"own": 1, "project": 2, "all": 3}


def check_pipeline_permission(
    db: Session,
    user_id: int,
    resource: str,
    action: str,
    scope: str = "project",
    project_id: Optional[int] = None,
) -> bool:
    """校验用户是否拥有指定 Pipeline 权限。

    Args:
        db: 数据库会话。
        user_id: 用户 ID。
        resource: 资源类型（iteration/pipeline/review/test_case/report/config）。
        action: 操作类型（create/read/update/delete/start/approve/reject/finalize/cancel）。
        scope: 所需范围（own/project/all）。
        project_id: 项目 ID（scope 为 own/project 时用于过滤）。

    Returns:
        有权限返回 True，无权限返回 False。
    """
    rows = (
        db.query(PipelinePermission)
        .join(PipelineRole)
        .join(pipeline_user_role, pipeline_user_role.c.role_id == PipelineRole.id)
        .filter(
            pipeline_user_role.c.user_id == user_id,
            PipelinePermission.resource == resource,
            PipelinePermission.action == action,
        )
    )

    if project_id is not None:
        rows = rows.filter(pipeline_user_role.c.project_id == project_id)

    for perm in rows.all():
        perm_scope_level = SCOPE_HIERARCHY.get(perm.scope, 0)
        required_scope_level = SCOPE_HIERARCHY.get(scope, 0)
        if perm_scope_level >= required_scope_level:
            if perm.scope == "own" and project_id is None:
                continue
            return True

    return False


def require_permission(resource: str, action: str, scope: str = "project") -> Callable[..., Any]:
    """FastAPI Depends 工厂：校验 Pipeline 权限。

    用法：
        @router.post("/pipeline/start")
        async def start_pipeline(
            ...,
            _: None = Depends(require_permission("pipeline", "start", "project")),
        ):

    Args:
        resource: 资源类型。
        action: 操作类型。
        scope: 所需范围。

    Returns:
        FastAPI 依赖函数。
    """
    async def _check(
        db: Session = Depends(get_db),
        current_user: User = Depends(_get_current_user),
    ):
        if not check_pipeline_permission(db, current_user.id, resource, action, scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {resource}:{action} (scope={scope})",
            )
    return _check


def init_pipeline_roles(db: Session) -> None:
    """初始化预定义角色和权限（幂等：已存在则跳过）。

    Args:
        db: 数据库会话。
    """
    for role_name, role_def in ROLE_DEFINITIONS.items():
        role = db.query(PipelineRole).filter(PipelineRole.name == role_name).first()
        if role is None:
            role = PipelineRole(
                name=role_name,
                description=role_def["description"],
            )
            db.add(role)
            db.flush()

        for perm_def in role_def["permissions"]:
            existing = (
                db.query(PipelinePermission)
                .filter(
                    PipelinePermission.role_id == role.id,
                    PipelinePermission.resource == perm_def["resource"],
                    PipelinePermission.action == perm_def["action"],
                    PipelinePermission.scope == perm_def["scope"],
                )
                .first()
            )
            if existing is None:
                perm = PipelinePermission(
                    role_id=role.id,
                    resource=perm_def["resource"],
                    action=perm_def["action"],
                    scope=perm_def["scope"],
                )
                db.add(perm)

    db.flush()


def assign_pipeline_role(
    db: Session,
    user_id: int,
    role_name: str,
    project_id: int,
    actor_id: Optional[int] = None,
) -> None:
    """分配 Pipeline 角色。

    Args:
        db: 数据库会话。
        user_id: 用户 ID。
        role_name: 角色名。
        project_id: 项目 ID。
        actor_id: 操作人 ID。

    Raises:
        ValueError: 角色不存在或已分配。
    """
    role = db.query(PipelineRole).filter(PipelineRole.name == role_name).first()
    if role is None:
        raise ValueError(f"Pipeline role '{role_name}' not found")

    existing = (
        db.query(pipeline_user_role)
        .filter(
            pipeline_user_role.c.user_id == user_id,
            pipeline_user_role.c.role_id == role.id,
            pipeline_user_role.c.project_id == project_id,
        )
        .first()
    )
    if existing is not None:
        return

    db.execute(
        pipeline_user_role.insert().values(
            user_id=user_id, role_id=role.id, project_id=project_id,
        )
    )
    db.flush()

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action="permission_change",
            actor_id=actor_id,
            target_kind="user",
            target_id=user_id,
            detail={"role": role_name, "project_id": project_id, "op": "assign"},
        )
    except Exception as e:
        logger.error("Failed to write audit log for permission_change: %s", e)


def revoke_pipeline_role(
    db: Session,
    user_id: int,
    role_name: str,
    project_id: int,
    actor_id: Optional[int] = None,
) -> None:
    """撤销 Pipeline 角色。

    Args:
        db: 数据库会话。
        user_id: 用户 ID。
        role_name: 角色名。
        project_id: 项目 ID。
        actor_id: 操作人 ID。

    Raises:
        ValueError: 角色不存在。
    """
    role = db.query(PipelineRole).filter(PipelineRole.name == role_name).first()
    if role is None:
        raise ValueError(f"Pipeline role '{role_name}' not found")

    db.execute(
        pipeline_user_role.delete().where(
            pipeline_user_role.c.user_id == user_id,
            pipeline_user_role.c.role_id == role.id,
            pipeline_user_role.c.project_id == project_id,
        )
    )
    db.flush()

    try:
        from app.services.audit_service import log_action
        log_action(
            db=db,
            action="permission_change",
            actor_id=actor_id,
            target_kind="user",
            target_id=user_id,
            detail={"role": role_name, "project_id": project_id, "op": "revoke"},
        )
    except Exception as e:
        logger.error("Failed to write audit log for permission_change: %s", e)
