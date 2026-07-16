"""generation_batch 端点 CRUD 路由处理函数。

路由处理函数以普通 async 函数形式定义，由 generation_batch.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints._generation_batch_helpers import (
    _batch_to_response,
    _generate_batch_no,
    _validate_status_transition,
)
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.generation_batch import GenerationBatch
from app.models.project import Project
from app.models.user import User
from app.schemas.generation_batch import (
    GenerationBatchCreate,
    GenerationBatchUpdate,
)
from app.utils.db_time import utcnow


async def create_generation_batch(
    body: GenerationBatchCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """创建生成批次。"""
    project_result = await db.execute(
        select(Project).where(
            Project.id == body.project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限"
        )

    batch = GenerationBatch(
        batch_no=_generate_batch_no(body.project_id),
        project_id=body.project_id,
        user_id=current_user.id,
        entry_type=body.entry_type,
        scenario_type=body.scenario_type,
        generation_strategy=body.generation_strategy,
        status="created",
        requirement_file_ids_json=body.requirement_file_ids,
        test_point_ids_json=body.test_point_ids,
        ui_screen_ids_json=body.ui_screen_ids,
        history_asset_ids_json=body.history_asset_ids,
        client_request_id=body.client_request_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return create_response(data=_batch_to_response(batch))


async def get_generation_batch(
    batch_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """获取生成批次详情。"""
    batch_result = await db.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在"
        )
    if batch.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此批次"
        )
    return create_response(data=_batch_to_response(batch))


async def update_generation_batch(
    batch_id: int,
    body: GenerationBatchUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    """更新生成批次状态与上下文统计。"""
    batch_result = await db.execute(
        select(GenerationBatch).where(GenerationBatch.id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在"
        )
    if batch.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此批次"
        )

    if body.status is not None:
        _validate_status_transition(batch.status, body.status)
        batch.status = body.status

    if body.context_stats is not None:
        batch.context_stats_json = body.context_stats
    if body.warnings is not None:
        batch.warnings_json = body.warnings
    if body.evidence_refs is not None:
        batch.evidence_refs_json = body.evidence_refs
    if body.quality_summary is not None:
        batch.quality_summary_json = body.quality_summary

    batch.updated_at = utcnow()
    await db.commit()
    await db.refresh(batch)
    return create_response(data=_batch_to_response(batch))
