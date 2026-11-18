"""项目质量规则配置 API 端点（R2-1：同步 Session + 线程池执行）。

端点概览:
    - GET  /api/v1/projects/{project_id}/quality-rules — 获取项目质量规则列表
    - PUT  /api/v1/projects/{project_id}/quality-rules — 更新项目质量规则

实现说明（R2-1 阶段三 W2-5；本模块原为 async 试点，已随范式收敛回退）:
    1. 依赖 `Depends(get_db)`（同步 Session），`db.query` / `db.commit` 语义不变；
    2. 查询经模块级 `_execute(db, stmt)`（内部 `asyncio.to_thread`）在线程池执行；
    3. 写路径保持 `commit` 后 `refresh`，修复历史持久化 bug。
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.quality_rule_config import QualityRuleConfig
from app.models.project import Project
from app.schemas.quality_rule import (
    QualityRuleConfigResponse,
    QualityRuleConfigUpdate,
)
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User


# [B-08 校正 2026-11-12] 前端**已接线**：`src/api/qualityRule.ts` → 项目详情页 `QualityRuleTab.vue`。
# 原 R4-6「命中 0」结论系双重误判：① 脚本按资源段匹配，前端旧 URL `/api/v1/quality-rule/project/{id}`
# 与后端实际路径不符；② 该错误 URL 已在本轮修正为 `/api/v1/projects/{project_id}/quality-rules`。
async def _execute(db: Session, stmt):
    """同步 Session 的查询在线程池执行，避免阻塞事件循环（R2-1）。"""
    return await asyncio.to_thread(db.execute, stmt)


router = APIRouter(tags=["质量规则"])


@router.get(
    "/{project_id}/quality-rules",
    response_model=list[QualityRuleConfigResponse],
    summary="获取项目质量规则列表",
)
async def get_quality_rules(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QualityRuleConfig]:
    """获取指定项目的所有质量规则配置。"""
    # 安全收紧：联合校验项目归属，避免越权访问他人项目数据
    # 不区分 404/403，统一返回 403 避免泄露项目存在性
    project = (
        await _execute(
            db,
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id,
            ),
        )
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此项目")
    rules = (
        (await _execute(db, select(QualityRuleConfig).where(QualityRuleConfig.project_id == project_id)))
        .scalars()
        .all()
    )
    return rules


@router.put(
    "/{project_id}/quality-rules",
    response_model=QualityRuleConfigResponse,
    summary="更新项目质量规则",
)
async def update_quality_rule(
    project_id: int,
    body: QualityRuleConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityRuleConfig:
    """更新指定项目的质量规则配置，不存在则创建。"""
    # 安全收紧：联合校验项目归属
    project = (
        await _execute(
            db,
            select(Project).where(
                Project.id == project_id,
                Project.user_id == current_user.id,
            ),
        )
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=403, detail="无权限操作此项目")

    existing = (
        await _execute(
            db,
            select(QualityRuleConfig).where(
                QualityRuleConfig.project_id == project_id,
                QualityRuleConfig.rule_key == body.rule_key,
            ),
        )
    ).scalar_one_or_none()

    if existing:
        existing.rule_value = body.rule_value
        # 修复：原代码仅 flush 不 commit，依赖 get_db 自动提交，
        # 但 get_db 未配置自动 commit，导致更新在连接归还时被回滚。
        # 此处显式 commit 确保持久化。
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, existing)
        logger.info(f"更新质量规则: project_id={project_id}, key={body.rule_key}")
        return existing

    new_rule = QualityRuleConfig(
        project_id=project_id,
        rule_key=body.rule_key,
        rule_value=body.rule_value,
    )
    db.add(new_rule)
    await asyncio.to_thread(db.commit)
    # 刷新以获取 DB 服务器生成的字段（id / created_at / updated_at），
    # 否则 Pydantic 序列化 response 时访问未加载属性会触发 async lazy load 失败。
    await asyncio.to_thread(db.refresh, new_rule)
    logger.info(f"创建质量规则: project_id={project_id}, key={body.rule_key}")
    return new_rule
