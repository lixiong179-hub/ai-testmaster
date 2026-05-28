from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from loguru import logger
from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.iteration import IterationCreate, IterationUpdate, IterationInputCreate
from app.api.v1.endpoints.pipeline import PipelineRunRequest
from app.crud import iteration as iteration_crud
from app.services import iteration_service
from app.core.exception import create_response
from app.api.v1.endpoints.iteration._helpers import (
    _verify_project_ownership,
    _iteration_to_dict,
    _cleanup_iteration_resources,
)

router = APIRouter(prefix="/iteration", tags=["迭代管理"])

ALLOWED_UPDATE_FIELDS = {"name", "version", "description", "start_date", "end_date"}


@router.post("/", response_model=dict)
async def create_iteration(
    iteration_data: IterationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        _verify_project_ownership(db=db, project_id=iteration_data.project_id, current_user=current_user)
        iteration = iteration_service.create_iteration(
            db=db, project_id=iteration_data.project_id, name=iteration_data.name,
            version=iteration_data.version, description=iteration_data.description,
            base_iteration_id=iteration_data.base_iteration_id, created_by=current_user.id,
            start_date=iteration_data.start_date, end_date=iteration_data.end_date,
        )
        db.commit()
        return create_response(data=_iteration_to_dict(iteration), msg="创建成功")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.BaseIterationValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建迭代失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建迭代失败")


@router.get("/list/{project_id}", response_model=dict)
async def get_iterations(
    project_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        _verify_project_ownership(db=db, project_id=project_id, current_user=current_user)
        skip = (page - 1) * page_size
        iterations = iteration_service.list_iterations(db=db, project_id=project_id, skip=skip, limit=page_size)
        total = iteration_crud.get_iterations_count_by_project(db=db, project_id=project_id)
        items = [_iteration_to_dict(it) for it in iterations]
        return create_response(data={"items": items, "total": total, "page": page, "page_size": page_size}, msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取迭代列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取迭代列表失败")


@router.get("/{iteration_id}", response_model=dict)
async def get_iteration(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        iteration = iteration_service.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)
        return create_response(data=_iteration_to_dict(iteration), msg="获取成功")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取迭代详情失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取迭代详情失败")


@router.put("/{iteration_id}", response_model=dict)
async def update_iteration(
    iteration_id: int,
    update_data: IterationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        iteration = iteration_crud.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)
        update_kwargs = {}
        for field in ALLOWED_UPDATE_FIELDS:
            value = getattr(update_data, field, None)
            if value is not None:
                if hasattr(value, 'value'):
                    value = value.value
                update_kwargs[field] = value
        updated = iteration_crud.update_iteration(db=db, iteration_id=iteration_id, **update_kwargs)
        if not updated:
            raise HTTPException(status_code=404, detail="迭代不存在")
        return create_response(data=_iteration_to_dict(updated), msg="更新成功")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新迭代失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="更新迭代失败")


@router.delete("/{iteration_id}", response_model=dict)
async def delete_iteration(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        iteration = iteration_crud.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)
        with db.begin_nested():
            _cleanup_iteration_resources(db=db, iteration_id=iteration_id)
            iteration_crud.delete_iteration(db=db, iteration_id=iteration_id)
        return create_response(data={}, msg="删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除迭代失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="删除迭代失败")


@router.post("/{iteration_id}/finalize", response_model=dict)
async def finalize_iteration(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        iteration = iteration_service.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)
        finalized = iteration_service.finalize_iteration(db=db, iteration_id=iteration_id)
        db.commit()
        return create_response(data=_iteration_to_dict(finalized), msg="定稿成功")
    except iteration_service.IterationStatusTransitionError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"定稿迭代失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="定稿迭代失败")


@router.post("/{iteration_id}/inputs", response_model=dict)
async def add_iteration_input(
    iteration_id: int,
    input_data: IterationInputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        iteration = iteration_service.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")
        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)
        inp = iteration_service.add_input(
            db=db, iteration_id=iteration_id, kind=input_data.kind.value,
            file_id=input_data.file_id, payload=input_data.payload, hash_value=input_data.hash,
        )
        db.commit()
        return create_response(data={
            "id": inp.id, "iteration_id": inp.iteration_id, "kind": inp.kind,
            "file_id": inp.file_id, "payload": inp.payload,
            "content_hash": inp.content_hash, "uploaded_at": inp.uploaded_at,
        }, msg="添加输入成功")
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.DuplicateInputHashError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except iteration_service.IterationInputValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"添加迭代输入失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="添加迭代输入失败")


@router.post("/{iteration_id}/pipeline/run", response_model=dict)
async def run_iteration_pipeline(
    iteration_id: int,
    body: PipelineRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.api.v1.endpoints.pipeline import run_pipeline
    return await run_pipeline(iteration_id=iteration_id, body=body, db=db, current_user=current_user)
