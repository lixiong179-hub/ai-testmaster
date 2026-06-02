"""项目质量规则配置 API 端点。

端点概览:
    - GET  /api/v1/projects/{project_id}/quality-rules — 获取项目质量规则列表
    - PUT  /api/v1/projects/{project_id}/quality-rules — 更新项目质量规则
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
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

router = APIRouter()


@router.get(
    "/{project_id}/quality-rules",
    response_model=List[QualityRuleConfigResponse],
    summary="获取项目质量规则列表",
)
def get_quality_rules(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[QualityRuleConfig]:
    """获取指定项目的所有质量规则配置。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    rules = db.query(QualityRuleConfig).filter(
        QualityRuleConfig.project_id == project_id,
    ).all()
    return rules


@router.put(
    "/{project_id}/quality-rules",
    response_model=QualityRuleConfigResponse,
    summary="更新项目质量规则",
)
def update_quality_rule(
    project_id: int,
    body: QualityRuleConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityRuleConfig:
    """更新指定项目的质量规则配置，不存在则创建。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    existing = db.query(QualityRuleConfig).filter(
        QualityRuleConfig.project_id == project_id,
        QualityRuleConfig.rule_key == body.rule_key,
    ).first()

    if existing:
        existing.rule_value = body.rule_value
        db.flush()
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
    db.flush()
    logger.info(
        f"创建质量规则: project_id={project_id}, key={body.rule_key}"
    )
    return new_rule
