"""
审计日志端点模块

本模块定义审计日志查询的API端点，仅管理员可访问。

路由前缀: /audit-log
标签: 审计日志

端点概览:
    - GET /logs - 查询审计日志（支持多维度过滤+分页）

权限要求: Bearer令牌认证 + Pipeline admin 角色
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any
from datetime import datetime

from app.db.database import async_get_db
from app.models.user import User
from app.services import audit_service
from app.core.exception import create_response
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/audit-log", tags=["审计日志"])


def _get_current_user():
    """延迟导入避免循环依赖。"""
    from app.api.v1.endpoints.auth import get_current_user
    return get_current_user


def _require_admin(db: AsyncSession, user_id: int) -> None:
    """验证当前用户是否为 Pipeline 管理员（在 run_sync 上下文内调用）。"""
    from app.services.pipeline_permission_service import check_pipeline_permission
    if not check_pipeline_permission(db, user_id, "config", "read", "all"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问审计日志"
        )


@router.get("/logs", response_model=ApiResponse)
async def get_audit_logs(
    target_kind: Optional[str] = Query(None, description="目标实体类型过滤"),
    target_id: Optional[int] = Query(None, description="目标实体ID过滤"),
    actor_id: Optional[int] = Query(None, description="操作人ID过滤"),
    action: Optional[str] = Query(None, description="操作类型过滤"),
    since: Optional[datetime] = Query(None, description="起始时间（含）"),
    until: Optional[datetime] = Query(None, description="截止时间（含）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(_get_current_user()),
) -> dict[str, Any]:
    """查询审计日志（管理员权限）"""
    try:
        offset = (page - 1) * page_size

        def _query(sync_db):
            _require_admin(db=sync_db, user_id=current_user.id)
            logs = audit_service.query_logs(
                db=sync_db,
                target_kind=target_kind,
                target_id=target_id,
                actor_id=actor_id,
                action=action,
                since=since,
                until=until,
                limit=page_size,
                offset=offset,
            )
            total = audit_service.count_logs(
                db=sync_db,
                target_kind=target_kind,
                target_id=target_id,
                actor_id=actor_id,
                action=action,
                since=since,
                until=until,
            )
            return logs, total

        logs, total = await db.run_sync(_query)

        items = [
            {
                "id": log.id,
                "action": log.action,
                "actor_id": log.actor_id,
                "target_kind": log.target_kind,
                "target_id": log.target_id,
                "detail": log.detail,
                "run_id": log.run_id,
                "iteration_id": log.iteration_id,
                "created_at": log.created_at,
            }
            for log in logs
        ]

        return create_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            },
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="查询审计日志失败")
