"""
按需解析需求链接正文（缓存优先，与 fetch-content 接口逻辑一致）
"""
from datetime import datetime, timedelta
from app.utils.db_time import utcnow
import json
from sqlalchemy.orm import Session

from app.models.requirement_link import RequirementLink
from app.crud import requirement_link as requirement_link_crud
from app.services.link_fetcher_service import link_fetcher_service


async def load_requirement_link_content(
    db: Session,
    link: RequirementLink,
    *,
    force_refresh: bool = False,
) -> tuple[bool, str]:
    """
    Returns:
        (success, content_on_success_or_error_message_on_failure)
    """
    if (
        not force_refresh
        and link.cached_content
        and link.last_fetch_time
    ):
        expire_time = link.last_fetch_time + timedelta(minutes=link.cache_expire_minutes)
        if utcnow() < expire_time:
            return True, link.cached_content

    if link.link_type == "ui_mockup":
        success, result, message = link_fetcher_service.fetch_and_parse_ui_mockup(
            url=link.link_url,
            auth_type=link.auth_type,
            auth_config=link.auth_config,
        )
        if success:
            content = json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else str(result)
            requirement_link_crud.update_link_cache(db, link.id, content, "success")
            return True, content
        requirement_link_crud.update_link_cache(db, link.id, "", "failed")
        return False, message or "获取链接内容失败"

    success, content, message = link_fetcher_service.fetch_content(
        url=link.link_url,
        auth_type=link.auth_type,
        auth_config=link.auth_config,
    )
    if success:
        requirement_link_crud.update_link_cache(db, link.id, content or "", "success")
        return True, content or ""
    requirement_link_crud.update_link_cache(db, link.id, "", "failed")
    return False, message or "获取链接内容失败"
