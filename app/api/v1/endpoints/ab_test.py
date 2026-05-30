"""
A/B测试指标端点模块

提供A/B实验指标的记录、汇总查询和实验列表接口。
所有接口均需登录鉴权，写入指标时校验项目归属。

路由前缀: （由main.py统一添加 /api/v1/ab-test）
标签: A/B测试

端点概览:
    - POST /experiments/{experiment_id}/metrics — 记录一条指标
    - GET  /experiments/{experiment_id}/summary  — 获取实验汇总
    - GET  /experiments                          — 列出所有实验
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import get_db
from app.models.project import Project
from app.models.user import User
from app.services.ab_test_service import ABTestService, VALID_METRIC_NAMES

router = APIRouter(tags=["A/B测试"])


class MetricCreateRequest(BaseModel):
    variant: str = Field(..., max_length=32, description="变体标识: control/treatment")
    metric_name: str = Field(..., max_length=64, description="指标名称")
    metric_value: float = Field(..., description="指标值")
    project_id: Optional[int] = Field(None, description="项目ID")
    test_point_id: Optional[int] = Field(None, description="测试点ID")
    detail: Optional[Dict[str, Any]] = Field(None, description="指标详情JSON")


def _verify_project_ownership(project_id: int, current_user: User, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
    return project


@router.post("/experiments/{experiment_id}/metrics", response_model=dict)
async def record_metric(
    experiment_id: str,
    body: MetricCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    if body.project_id is not None:
        _verify_project_ownership(body.project_id, current_user, db)
    try:
        service = ABTestService(db)
        row = service.record_metric(
            experiment_id=experiment_id,
            variant=body.variant,
            metric_name=body.metric_name,
            metric_value=body.metric_value,
            project_id=body.project_id,
            test_point_id=body.test_point_id,
            detail=body.detail,
        )
        db.commit()
        return create_response(
            data={
                "id": row.id,
                "experiment_id": row.experiment_id,
                "variant": row.variant,
                "metric_name": row.metric_name,
                "metric_value": row.metric_value,
                "created_at": row.created_at,
            },
            msg="指标记录成功",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"记录指标失败: {exc}",
        )


@router.get("/experiments/{experiment_id}/summary", response_model=dict)
async def get_experiment_summary(
    experiment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        user_project_ids = [
            row[0] for row in db.query(Project.id).filter(
                Project.user_id == current_user.id,
            ).all() if row[0] is not None
        ]
        service = ABTestService(db)
        summary = service.get_experiment_summary(experiment_id, project_ids=user_project_ids)
        return create_response(data=summary, msg="获取实验汇总成功")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取实验汇总失败: {exc}",
        )


@router.get("/experiments", response_model=dict)
async def list_experiments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    try:
        user_project_ids = [
            row[0] for row in db.query(Project.id).filter(
                Project.user_id == current_user.id,
            ).all() if row[0] is not None
        ]
        service = ABTestService(db)
        experiments: List[Dict[str, Any]] = service.list_experiments(project_ids=user_project_ids)
        return create_response(data=experiments, msg="获取实验列表成功")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取实验列表失败: {exc}",
        )
