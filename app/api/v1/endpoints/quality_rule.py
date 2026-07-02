"""项目质量规则配置 API 端点（已迁移至 AsyncSession）。

端点概览:
    - GET  /api/v1/projects/{project_id}/quality-rules — 获取项目质量规则列表
    - PUT  /api/v1/projects/{project_id}/quality-rules — 更新项目质量规则

迁移说明（任务1 续作 - 异步试点）:
    本模块作为首个 async endpoint 试点，验证 AsyncSession 端到端链路。
    改造要点:
        1. db: Session → db: AsyncSession，依赖 get_db → async_get_db
        2. db.query(Model).filter().first() → (await db.execute(select(...))).scalar_one_or_none()
        3. db.query(Model).filter().all() → (await db.execute(select(...))).scalars().all()
        4. db.flush() → await db.commit() + await db.refresh() 修复持久化 bug
    试点通过后，可参照本文件模式批量迁移其他 endpoint。
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_get_db
from app.models.quality_rule_config import QualityRuleConfig
from app.models.project import Project
from app.schemas.quality_rule import (
    QualityRuleConfigResponse,
    QualityRuleConfigUpdate,
)
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get(
    "/{project_id}/quality-rules",
    response_model=List[QualityRuleConfigResponse],
    summary="获取项目质量规则列表",
)
async def get_quality_rules(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> List[QualityRuleConfig]:
    """获取指定项目的所有质量规则配置。"""
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    rules = (
        await db.execute(
            select(QualityRuleConfig).where(
                QualityRuleConfig.project_id == project_id
            )
        )
    ).scalars().all()
    return rules


@router.put(
    "/{project_id}/quality-rules",
    response_model=QualityRuleConfigResponse,
    summary="更新项目质量规则",
)
async def update_quality_rule(
    project_id: int,
    body: QualityRuleConfigUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> QualityRuleConfig:
    """更新指定项目的质量规则配置，不存在则创建。"""
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    existing = (
        await db.execute(
            select(QualityRuleConfig).where(
                QualityRuleConfig.project_id == project_id,
                QualityRuleConfig.rule_key == body.rule_key,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.rule_value = body.rule_value
        # 修复：原代码仅 flush 不 commit，依赖 get_db 自动提交，
        # 但 get_db 未配置自动 commit，导致更新在连接归还时被回滚。
        # 此处显式 commit 确保持久化。
        await db.commit()
        await db.refresh(existing)
        logger.info(
            f"更新质量规则: project_id={project_id}, key={body.rule_key}"
        )
        return existing

    new_rule = QualityRuleConfig(
        project_id=project_id,
        rule_key=body.rule_key,
        rule_value=body.rule_value,
    )
    db.add(new_rule)
    await db.commit()
    # 刷新以获取 DB 服务器生成的字段（id / created_at / updated_at），
    # 否则 Pydantic 序列化 response 时访问未加载属性会触发 async lazy load 失败。
    await db.refresh(new_rule)
    logger.info(
        f"创建质量规则: project_id={project_id}, key={body.rule_key}"
    )
    return new_rule
