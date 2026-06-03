"""Prompt 模板版本管理端点

路由前缀: （由 main.py 统一添加 /api/v1/prompt-templates）
标签: Prompt模板

端点概览:
    - GET  /                       — 列表（支持按 prompt_key 筛选）
    - POST /                       — 注册新版本
    - POST /{key}/set-default      — 设为默认版本
    - POST /{key}/rollback         — 回滚到指定版本
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateListResponse,
    SetDefaultRequest,
    RollbackRequest,
)
from app.services.prompt_registry import PromptRegistry


async def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not any(r.name == "admin" for r in current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user

router = APIRouter(tags=["Prompt模板"])


@router.get("/", response_model=PromptTemplateListResponse)
def list_prompt_templates(
    prompt_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PromptTemplateListResponse:
    """获取 Prompt 模板列表，支持按 prompt_key 筛选。"""
    query = db.query(PromptTemplate)
    if prompt_key:
        query = query.filter(PromptTemplate.prompt_key == prompt_key)
    items = query.order_by(PromptTemplate.prompt_key, PromptTemplate.prompt_version.asc()).all()
    return PromptTemplateListResponse(items=items, total=len(items))


@router.post("/", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
def register_prompt_template(
    data: PromptTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
) -> PromptTemplateResponse:
    """注册 Prompt 新版本"""
    registry = PromptRegistry(db)
    try:
        template = registry.register_prompt(
            key=data.prompt_key,
            content=data.content,
            description=data.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return template


@router.post("/{key}/set-default", response_model=PromptTemplateResponse)
def set_default_prompt(
    key: str,
    data: SetDefaultRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
) -> PromptTemplateResponse:
    """将指定版本设为默认版本"""
    registry = PromptRegistry(db)
    try:
        template = registry.set_default(key=key, version=data.version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return template


@router.post("/{key}/rollback", response_model=PromptTemplateResponse)
def rollback_prompt(
    key: str,
    data: RollbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
) -> PromptTemplateResponse:
    """回滚到指定版本"""
    registry = PromptRegistry(db)
    try:
        template = registry.rollback(key=key, target_version=data.target_version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    return template
