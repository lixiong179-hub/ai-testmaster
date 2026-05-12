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
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.db.database import get_db
from app.models.user import User
from app.services import audit_service
from app.core.exception import create_response

router = APIRouter(prefix="/audit-log", tags=["审计日志"])


def _get_current_user():
    """延迟导入避免循环依赖。"""
    from app.api.v1.endpoints.auth import get_current_user
    return get_current_user


def _require_admin(db: Session, user_id: int):
    """验证当前用户是否为 Pipeline 管理员"""
    from app.services.pipeline_permission_service import check_pipeline_permission
    if not check_pipeline_permission(db, user_id, "config", "read", "all"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅管理员可访问审计日志"
        )


@router.get("/logs", response_model=dict)
async def get_audit_logs(
    target_kind: Optional[str] = Query(None, description="目标实体类型过滤"),
    target_id: Optional[int] = Query(None, description="目标实体ID过滤"),
    actor_id: Optional[int] = Query(None, description="操作人ID过滤"),
    action: Optional[str] = Query(None, description="操作类型过滤"),
    since: Optional[datetime] = Query(None, description="起始时间（含）"),
    until: Optional[datetime] = Query(None, description="截止时间（含）"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    """查询审计日志（管理员权限）"""
    try:
        _require_admin(db=db, user_id=current_user.id)

        offset = (page - 1) * page_size
        logs = audit_service.query_logs(
            db=db,
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
            db=db,
            target_kind=target_kind,
            target_id=target_id,
            actor_id=actor_id,
            action=action,
            since=since,
            until=until,
        )

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
