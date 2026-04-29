"""
测试点变更端点模块

本模块定义测试点的增删改操作API端点，包括创建、更新、删除和AI生成测试点。

路由前缀: /testPoint（由父模块test_point.py注册）
标签: 测试点管理

端点概览:
    - POST   /                          - 创建测试点
    - PUT    /{test_point_id}           - 更新测试点
    - DELETE /{test_point_id}           - 删除测试点
    - POST   /ai-generate               - AI生成测试点
    - POST   /ai-generate/stream        - AI生成测试点（SSE流式）
    - POST   /batch-generate-by-req     - 按需求文件批量生成测试点

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - AI生成调用DeepSeek API，需配置DEEPSEEK_API_KEY
    - 流式生成通过SSE实时推送进度
    - 批量生成基于需求文件内容
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_point import TestPointUpdate, TestPointResponse
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_point import batch_create_test_points
from loguru import logger
from app.models.project import Project

router = APIRouter()


def check_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


@router.post("/batch-save")
async def batch_save_test_points(
    project_id: int = Query(..., description="项目ID"),
    test_points: List[Dict[str, Any]] = Body(..., description="测试点列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    MAX_BATCH_SIZE = 200
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    try:
        if not test_points or not isinstance(test_points, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="测试点列表不能为空"
            )
        if len(test_points) > MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次保存数量不能超过{MAX_BATCH_SIZE}个"
            )
        valid_points = []
        for i, item in enumerate(test_points):
            if not isinstance(item, dict):
                logger.warning(f"跳过无效数据项[{i}]: 非字典类型")
                continue
            module = str(item.get('module', '')).strip()
            point = str(item.get('point', '')).strip()
            if not module or not point:
                logger.warning(f"跳过数据项[{i}]: 缺少必填字段(module/point)")
                continue
            if len(module) > 100 or len(point) > 500:
                logger.warning(f"跳过数据项[{i}]: 字段超长")
                continue
            try:
                priority = int(item.get('priority', 2))
                if priority < 1 or priority > 3:
                    priority = 2
            except (ValueError, TypeError):
                priority = 2
            valid_points.append({
                'module': module,
                'point': point,
                'priority': priority,
                'ai_prompt': item.get('ai_prompt')
            })
        if not valid_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点数据可保存"
            )
        saved_test_points = batch_create_test_points(
            db=db,
            project_id=project_id,
            test_points_data=valid_points,
            created_by=current_user.username,
        )
        logger.info(f"批量保存测试点成功: {len(saved_test_points)}/{len(valid_points)} 个 (用户: {current_user.username})")
        return {
            "code": 200,
            "message": f"成功保存 {len(saved_test_points)} 个测试点",
            "data": {
                "saved_count": len(saved_test_points),
                "total_submitted": len(valid_points),
                "items": [
                    {
                        "id": tp.id,
                        "module": tp.module,
                        "point": tp.point,
                        "priority": tp.priority
                    }
                    for tp in saved_test_points
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存测试点失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存失败"
        )


@router.put("/{test_point_id}")
async def update_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    update_data: TestPointUpdate = Body(..., description="更新数据"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        project = check_project_permission(db, project_id, current_user.id)
        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试点不存在"
            )
        if update_data.module is not None:
            test_point.module = update_data.module
        if update_data.point is not None:
            test_point.point = update_data.point
        if update_data.priority is not None:
            test_point.priority = update_data.priority
        if update_data.ai_prompt is not None:
            test_point.ai_prompt = update_data.ai_prompt
        if update_data.status is not None:
            test_point.status = update_data.status
        # 任意字段变更时递增版本号
        test_point.version = (test_point.version or 1) + 1
        db.commit()
        db.refresh(test_point)
        logger.info(f"用户 {current_user.username} 更新了测试点 {test_point_id}")
        return {
            "code": 200,
            "message": "更新成功",
            "data": TestPointResponse(
                id=test_point.id,
                project_id=test_point.project_id,
                requirement_id=test_point.requirement_id,
                module=test_point.module,
                point=test_point.point,
                priority=test_point.priority,
                ai_prompt=test_point.ai_prompt,
                capability_id=test_point.capability_id, version=test_point.version, status=test_point.status,
                create_time=test_point.create_time,
                created_by=test_point.created_by,
                test_case_count=0,
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.delete("/batch")
async def batch_delete_test_points(
    project_id: int = Query(..., description="项目ID"),
    ids: List[int] = Body(..., description="要删除的测试点ID列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    MAX_BATCH_DELETE = 100
    try:
        project = check_project_permission(db, project_id, current_user.id)
        if not ids or not isinstance(ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供有效的ID列表"
            )
        unique_ids = list(set(filter(lambda x: isinstance(x, int) and x > 0, ids)))
        if len(unique_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点ID"
            )
        if len(unique_ids) > MAX_BATCH_DELETE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次删除数量不能超过{MAX_BATCH_DELETE}个（当前{len(unique_ids)}个）"
            )
        from app.models.test_point import TestPoint as TestPointModel
        deleted_count = db.query(TestPointModel).filter(
            TestPointModel.id.in_(unique_ids),
            TestPointModel.project_id == project_id
        ).delete(synchronize_session=False)
        db.commit()
        logger.info(f"用户 {current_user.username} 批量删除了 {deleted_count} 个测试点")
        return {
            "code": 200,
            "message": f"成功删除 {deleted_count} 个测试点",
            "data": {
                "deleted_count": deleted_count,
                "requested_count": len(unique_ids)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.delete("/{test_point_id}")
async def delete_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        project = check_project_permission(db, project_id, current_user.id)
        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        if not test_point:
            return {
                "code": 200,
                "message": "删除成功",
                "data": {"id": test_point_id}
            }
        db.delete(test_point)
        db.commit()
        logger.info(f"用户 {current_user.username} 删除了测试点 {test_point_id}")
        return {
            "code": 200,
            "message": "删除成功",
            "data": {"id": test_point_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )
