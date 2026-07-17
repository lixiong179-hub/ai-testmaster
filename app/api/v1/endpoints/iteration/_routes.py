from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from app.db.database import async_get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.common import ApiResponse
from app.schemas.iteration import IterationCreate, IterationUpdate, IterationInputCreate
from app.api.v1.endpoints.pipeline import PipelineRunRequest
from app.services import iteration_service
from app.core.exception import create_response
from app.api.v1.endpoints.iteration._helpers import (
    _verify_project_ownership_async,
    _iteration_to_dict,
    _cleanup_iteration_resources_async,
)

router = APIRouter(prefix="/iteration", tags=["迭代管理"])

ALLOWED_UPDATE_FIELDS = {"name", "version", "description", "start_date", "end_date"}


@router.post("/", response_model=ApiResponse)
async def create_iteration(
    iteration_data: IterationCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        await _verify_project_ownership_async(
            db=db, project_id=iteration_data.project_id, current_user=current_user
        )
        service = iteration_service.IterationService(db)
        iteration = await service.create_iteration_async(
            project_id=iteration_data.project_id, name=iteration_data.name,
            version=iteration_data.version, description=iteration_data.description,
            base_iteration_id=iteration_data.base_iteration_id, created_by=current_user.id,
            start_date=iteration_data.start_date, end_date=iteration_data.end_date,
        )
        await db.commit()
        return create_response(data=_iteration_to_dict(iteration), msg="创建成功")
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.BaseIterationValidationError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("创建迭代失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="创建迭代失败")


@router.get("/list/{project_id}", response_model=ApiResponse)
async def get_iterations(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        await _verify_project_ownership_async(
            db=db, project_id=project_id, current_user=current_user
        )
        skip = (page - 1) * page_size
        service = iteration_service.IterationService(db)
        iterations = await service.list_iterations_async(
            project_id=project_id, skip=skip, limit=page_size
        )
        total = await service.get_iterations_count_by_project_async(project_id=project_id)
        items = [_iteration_to_dict(it) for it in iterations]
        return create_response(
            data={"items": items, "total": total, "page": page, "page_size": page_size},
            msg="获取成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取迭代列表失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="获取迭代列表失败")


@router.get("/{iteration_id}", response_model=ApiResponse)
async def get_iteration(
    iteration_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = iteration_service.IterationService(db)
        iteration = await service.get_iteration_async(iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        await _verify_project_ownership_async(
            db=db, project_id=iteration.project_id, current_user=current_user
        )
        return create_response(data=_iteration_to_dict(iteration), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取迭代详情失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="获取迭代详情失败")


@router.put("/{iteration_id}", response_model=ApiResponse)
async def update_iteration(
    iteration_id: int,
    update_data: IterationUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = iteration_service.IterationService(db)
        iteration = await service.get_iteration_async(iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        await _verify_project_ownership_async(
            db=db, project_id=iteration.project_id, current_user=current_user
        )
        update_kwargs = {}
        for field in ALLOWED_UPDATE_FIELDS:
            value = getattr(update_data, field, None)
            if value is not None:
                if hasattr(value, 'value'):
                    value = value.value
                update_kwargs[field] = value
        updated = await service.update_iteration_async(
            iteration_id=iteration_id, **update_kwargs
        )
        if not updated:
            raise HTTPException(status_code=404, detail="迭代不存在")
        return create_response(data=_iteration_to_dict(updated), msg="更新成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("更新迭代失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="更新迭代失败")


@router.delete("/{iteration_id}", response_model=ApiResponse)
async def delete_iteration(
    iteration_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = iteration_service.IterationService(db)
        iteration = await service.get_iteration_async(iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        await _verify_project_ownership_async(
            db=db, project_id=iteration.project_id, current_user=current_user
        )
        await _cleanup_iteration_resources_async(db=db, iteration_id=iteration_id)
        await service.delete_iteration_async(iteration_id=iteration_id)
        return create_response(data={}, msg="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("删除迭代失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="删除迭代失败")


@router.post("/{iteration_id}/finalize", response_model=ApiResponse)
async def finalize_iteration(
    iteration_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = iteration_service.IterationService(db)
        iteration = await service.get_iteration_async(iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        await _verify_project_ownership_async(
            db=db, project_id=iteration.project_id, current_user=current_user
        )
        finalized = await service.finalize_iteration_async(iteration_id=iteration_id)
        await db.commit()
        return create_response(data=_iteration_to_dict(finalized), msg="定稿成功")
    except iteration_service.IterationStatusTransitionError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("定稿迭代失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="定稿迭代失败")


@router.post("/{iteration_id}/inputs", response_model=ApiResponse)
async def add_iteration_input(
    iteration_id: int,
    input_data: IterationInputCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        service = iteration_service.IterationService(db)
        iteration = await service.get_iteration_async(iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        await _verify_project_ownership_async(
            db=db, project_id=iteration.project_id, current_user=current_user
        )
        inp = await service.add_input_async(
            iteration_id=iteration_id, kind=input_data.kind.value,
            file_id=input_data.file_id, payload=input_data.payload, hash_value=input_data.hash,
        )
        await db.commit()
        return create_response(data={
            "id": inp.id, "iteration_id": inp.iteration_id, "kind": inp.kind,
            "file_id": inp.file_id, "payload": inp.payload,
            "content_hash": inp.content_hash, "uploaded_at": inp.uploaded_at,
        }, msg="添加输入成功")
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.DuplicateInputHashError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except iteration_service.IterationInputValidationError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error("添加迭代输入失败: {}", e, exc_info=True)
        raise HTTPException(status_code=500, detail="添加迭代输入失败")


@router.post("/{iteration_id}/pipeline/run", response_model=ApiResponse)
async def run_iteration_pipeline(
    iteration_id: int,
    body: PipelineRunRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    from app.api.v1.endpoints.pipeline import run_pipeline
    return await run_pipeline(iteration_id=iteration_id, body=body, db=db, current_user=current_user)
