import os
"""
迭代管理端点模块

本模块定义迭代（Sprint）管理的API端点，支持迭代的创建、查询、更新、删除和输入管理。

路由前缀: /iteration
标签: 迭代管理

端点概览:
    - POST   /                        - 创建迭代
    - GET    /list/{project_id}       - 获取迭代列表
    - GET    /{iteration_id}          - 获取迭代详情（含 inputs）
    - PUT    /{iteration_id}          - 更新迭代
    - DELETE /{iteration_id}          - 删除迭代
    - POST   /{iteration_id}/inputs   - 添加迭代输入

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 迭代关联项目，包含起止时间和状态
    - 迭代状态由系统自动驱动: draft → in_pipeline → in_review → finalized → archived
    - status 不允许用户手动修改
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.database import get_db
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeProject, UIPrototypeScreen, UIScreenTestCaseLink
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.iteration import IterationCreate, IterationUpdate, IterationInputCreate
from app.crud import iteration as iteration_crud
from app.services import iteration_service
from app.core.exception import create_response
from loguru import logger

router = APIRouter(prefix="/iteration", tags=["迭代管理"])

ALLOWED_UPDATE_FIELDS = {"name", "version", "description", "start_date", "end_date"}


def _verify_project_ownership(db: Session, project_id: int, current_user: User) -> Project:
    """验证项目归属权"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


def _iteration_to_dict(iteration):
    """将迭代对象转换为字典格式（含流水线上下文字段和 inputs）"""
    result = {
        "id": iteration.id,
        "project_id": iteration.project_id,
        "name": iteration.name,
        "version": iteration.version,
        "description": iteration.description,
        "status": iteration.status,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "base_iteration_id": iteration.base_iteration_id,
        "created_by": iteration.created_by,
        "finalized_at": iteration.finalized_at,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
    }
    # 包含 inputs（如果已加载）
    inputs = getattr(iteration, 'inputs', None)
    if inputs is not None:
        result["inputs"] = [
            {
                "id": inp.id,
                "iteration_id": inp.iteration_id,
                "kind": inp.kind,
                "file_id": inp.file_id,
                "payload": inp.payload,
                "content_hash": inp.content_hash,
                "uploaded_at": inp.uploaded_at,
            }
            for inp in inputs
        ]
    return result


def _cleanup_iteration_resources(db: Session, iteration_id: int):
    """清理迭代关联的资源（必须在事务内调用）"""
    project_files = db.query(ProjectFile).filter(
        ProjectFile.iteration_id == iteration_id
    ).all()
    for pf in project_files:
        pf.is_active = False

    ui_prototype_projects = db.query(UIPrototypeProject).filter(
        UIPrototypeProject.iteration_id == iteration_id
    ).all()
    for proto_project in ui_prototype_projects:
        screens = db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.prototype_project_id == proto_project.id
        ).all()
        for screen in screens:
            if screen.original_file_path and os.path.exists(screen.original_file_path):
                try:
                    os.remove(screen.original_file_path)
                except OSError as e:
                    logger.warning(f"删除UI原型文件失败: {screen.original_file_path}, 错误: {e}")
            db.query(UIScreenTestCaseLink).filter(
                UIScreenTestCaseLink.screen_id == screen.id
            ).delete()
            db.delete(screen)
        db.delete(proto_project)


@router.post("/", response_model=dict)
async def create_iteration(
    iteration_data: IterationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        _verify_project_ownership(db=db, project_id=iteration_data.project_id, current_user=current_user)

        iteration = iteration_service.create_iteration(
            db=db,
            project_id=iteration_data.project_id,
            name=iteration_data.name,
            version=iteration_data.version,
            description=iteration_data.description,
            base_iteration_id=iteration_data.base_iteration_id,
            created_by=current_user.id,
            start_date=iteration_data.start_date,
            end_date=iteration_data.end_date,
        )
        db.commit()

        return create_response(
            data=_iteration_to_dict(iteration),
            msg="创建成功"
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.BaseIterationValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except iteration_service.IterationInputValidationError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
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
        iterations = iteration_service.list_iterations(
            db=db,
            project_id=project_id,
            skip=skip,
            limit=page_size,
        )
        total = iteration_crud.get_iterations_count_by_project(db=db, project_id=project_id)

        items = [_iteration_to_dict(it) for it in iterations]

        return create_response(
            data={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size
            },
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception as e:
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

        return create_response(
            data=_iteration_to_dict(iteration),
            msg="获取成功"
        )
    except HTTPException:
        raise
    except Exception as e:
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

        return create_response(
            data=_iteration_to_dict(updated),
            msg="更新成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
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
        raise HTTPException(status_code=500, detail=f"删除迭代失败: {str(e)}")


@router.post("/{iteration_id}/inputs", response_model=dict)
async def add_iteration_input(
    iteration_id: int,
    input_data: IterationInputCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """添加迭代输入"""
    try:
        iteration = iteration_service.get_iteration(db=db, iteration_id=iteration_id)
        if not iteration:
            raise HTTPException(status_code=404, detail="迭代不存在")

        _verify_project_ownership(db=db, project_id=iteration.project_id, current_user=current_user)

        inp = iteration_service.add_input(
            db=db,
            iteration_id=iteration_id,
            kind=input_data.kind.value,
            file_id=input_data.file_id,
            payload=input_data.payload,
            hash_value=input_data.hash,
        )
        db.commit()

        return create_response(
            data={
                "id": inp.id,
                "iteration_id": inp.iteration_id,
                "kind": inp.kind,
                "file_id": inp.file_id,
                "payload": inp.payload,
                "content_hash": inp.content_hash,
                "uploaded_at": inp.uploaded_at,
            },
            msg="添加输入成功"
        )
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
        raise HTTPException(status_code=500, detail=f"添加迭代输入失败: {str(e)}")
