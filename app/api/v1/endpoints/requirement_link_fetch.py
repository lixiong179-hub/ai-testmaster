import json
"""
需求链接获取端点模块

本模块定义从外部系统获取需求链接的API端点，支持从Jira等外部工具拉取需求。

路由前缀: /requirement-link（由父模块requirement_link.py注册）
标签: 需求链接

端点概览:
    - POST /fetch          - 从外部系统拉取需求
    - GET  /sync-status    - 获取同步状态

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 外部系统集成需配置API密钥和地址
    - 同步为增量同步，避免重复拉取
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from app.utils.db_time import utcnow
from app.db.database import async_get_db
from app.schemas.requirement_link import FetchContentRequest, FetchContentResponse
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.crud import requirement_link as requirement_link_crud
from app.services.link_fetcher_service import link_fetcher_service
from loguru import logger

router = APIRouter()


@router.post("/fetch-content", response_model=FetchContentResponse)
async def fetch_link_content(
    request: FetchContentRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    def _fetch(sync_db: Session):
        link = requirement_link_crud.get_requirement_link_by_id(sync_db, request.link_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="需求链接不存在"
            )
        project = sync_db.query(Project).filter(
            Project.id == link.project_id,
            Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        if not request.force_refresh and link.cached_content and link.last_fetch_time:
            expire_time = link.last_fetch_time + timedelta(minutes=link.cache_expire_minutes)
            if utcnow() < expire_time:
                return FetchContentResponse(
                    success=True,
                    content=link.cached_content,
                    content_type="cached",
                    message="从缓存获取成功",
                    cached=True
                )
        if link.link_type == "ui_mockup":
            success, result, message = link_fetcher_service.fetch_and_parse_ui_mockup(
                url=link.link_url,
                auth_type=link.auth_type,
                auth_config=link.auth_config
            )
            if success:
                content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
                requirement_link_crud.update_link_cache(sync_db, link.id, content, "success")
                return FetchContentResponse(
                    success=True,
                    content=content,
                    content_type="json",
                    message="获取成功",
                    cached=False
                )
            else:
                requirement_link_crud.update_link_cache(sync_db, link.id, "", "failed")
                return FetchContentResponse(
                    success=False,
                    content=None,
                    content_type=None,
                    message=message,
                    cached=False
                )
        else:
            success, content, message = link_fetcher_service.fetch_content(
                url=link.link_url,
                auth_type=link.auth_type,
                auth_config=link.auth_config
            )
            if success:
                requirement_link_crud.update_link_cache(sync_db, link.id, content, "success")
                return FetchContentResponse(
                    success=True,
                    content=content,
                    content_type=message,
                    message="获取成功",
                    cached=False
                )
            else:
                requirement_link_crud.update_link_cache(sync_db, link.id, "", "failed")
                return FetchContentResponse(
                    success=False,
                    content=None,
                    content_type=None,
                    message=message,
                    cached=False
                )

    try:
        return await db.run_sync(_fetch)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取链接内容失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取链接内容失败"
        )


@router.post("/validate")
async def validate_link_access(
    link_url: str,
    auth_type: str = Query("none", description="认证类型"),
    username: Optional[str] = Query(None, description="用户名"),
    password: Optional[str] = Query(None, description="密码"),
    token: Optional[str] = Query(None, description="Token"),
    api_key: Optional[str] = Query(None, description="API Key"),
    api_key_header: Optional[str] = Query(None, description="API Key Header"),
    cookie: Optional[str] = Query(None, description="Cookie"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        auth_config = None
        if auth_type != "none":
            auth_config = {}
            if auth_type == "basic":
                auth_config = {"username": username, "password": password}
            elif auth_type == "bearer":
                auth_config = {"token": token}
            elif auth_type == "api_key":
                auth_config = {"api_key": api_key, "api_key_header": api_key_header or "X-API-Key"}
            elif auth_type == "cookie":
                auth_config = {"cookie": cookie}
        success, message = link_fetcher_service.validate_link_access(
            url=link_url,
            auth_type=auth_type,
            auth_config=auth_config
        )
        return {
            "success": success,
            "message": message,
            "link_url": link_url,
            "auth_type": auth_type
        }
    except Exception as e:
        logger.error(f"验证链接失败: {e}")
        return {
            "success": False,
            "message": f"验证失败: {str(e)}",
            "link_url": link_url,
            "auth_type": auth_type
        }
