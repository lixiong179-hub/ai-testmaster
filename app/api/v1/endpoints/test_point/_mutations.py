from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_point._helpers import check_project_permission
from app.crud.test_point import get_test_point_by_id
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.test_point import TestPointResponse, TestPointUpdate

router = APIRouter()


@router.post("/batch-save")
async def batch_save_test_points(
    project_id: int = Query(..., description="项目ID"),
    test_points: List[Dict[str, Any]] = Body(..., description="测试点列表"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    max_batch_size = 200
    try:
        if not test_points or not isinstance(test_points, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="测试点列表不能为空"
            )
        if len(test_points) > max_batch_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次保存数量不能超过{max_batch_size}个",
            )
        valid_points = []
        for i, item in enumerate(test_points):
            if not isinstance(item, dict):
                logger.warning(f"跳过无效数据项[{i}]: 非字典类型")
                continue
            module = str(item.get("module", "")).strip()
            point = str(item.get("point", "")).strip()
            if not module or not point:
                logger.warning(f"跳过数据项[{i}]: 缺少必填字段(module/point)")
                continue
            if len(module) > 100 or len(point) > 500:
                logger.warning(f"跳过数据项[{i}]: 字段超长")
                continue
            try:
                priority = int(item.get("priority", 2))
                if priority < 1 or priority > 3:
                    priority = 2
            except (ValueError, TypeError):
                priority = 2
            valid_points.append({
                "module": module,
                "point": point,
                "priority": priority, "ai_prompt": item.get("ai_prompt"),
            })
        if not valid_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点数据可保存",
            )
        from app.crud.test_point import batch_create_test_points

        def _save(sync_db):
            check_project_permission(sync_db, project_id, current_user.id)
            saved = batch_create_test_points(
                db=sync_db, project_id=project_id,
                test_points_data=valid_points, created_by=current_user.username,
            )
            return {
                "saved_count": len(saved), "total_submitted": len(valid_points),
                "items": [
                    {"id": tp.id, "module": tp.module,
                     "point": tp.point, "priority": tp.priority}
                    for tp in saved
                ],
            }

        data = await db.run_sync(_save)
        logger.info(
            f"批量保存测试点成功: {data['saved_count']}/{data['total_submitted']} 个 "
            f"(用户: {current_user.username})"
        )
        return {
            "code": 200,
            "message": f"成功保存 {data['saved_count']} 个测试点",
            "data": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存测试点失败: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存失败"
        )


@router.put("/{test_point_id}")
async def update_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    update_data: TestPointUpdate = Body(..., description="更新数据"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _update(sync_db) -> TestPointResponse:
            check_project_permission(sync_db, project_id, current_user.id)
            test_point = get_test_point_by_id(sync_db, test_point_id, project_id)
            if not test_point:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="测试点不存在"
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
            test_point.version = (test_point.version or 1) + 1
            sync_db.commit()
            sync_db.refresh(test_point)
            return TestPointResponse(
                id=test_point.id, project_id=test_point.project_id,
                requirement_id=test_point.requirement_id, module=test_point.module,
                point=test_point.point,
                priority=test_point.priority, ai_prompt=test_point.ai_prompt,
                capability_id=test_point.capability_id, version=test_point.version, status=test_point.status,
                create_time=test_point.create_time, created_by=test_point.created_by,
                test_case_count=0,
            )

        data = await db.run_sync(_update)
        logger.info(f"用户 {current_user.username} 更新了测试点 {test_point_id}")
        return {"code": 200, "message": "更新成功", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新测试点失败: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.delete("/batch")
async def batch_delete_test_points(
    project_id: int = Query(..., description="项目ID"),
    ids: List[int] = Body(..., description="要删除的测试点ID列表"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    max_batch_delete = 100
    try:
        if not ids or not isinstance(ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="请提供有效的ID列表"
            )
        unique_ids = list(set(filter(lambda x: isinstance(x, int) and x > 0, ids)))
        if len(unique_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="没有有效的测试点ID"
            )
        if len(unique_ids) > max_batch_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次删除数量不能超过{max_batch_delete}个（当前{len(unique_ids)}个）",
            )
        from app.models.test_point import TestPoint as TestPointModel

        def _batch_delete(sync_db) -> int:
            check_project_permission(sync_db, project_id, current_user.id)
            deleted_count = sync_db.query(TestPointModel).filter(
                TestPointModel.id.in_(unique_ids),
                TestPointModel.project_id == project_id,
            ).delete(synchronize_session=False)
            sync_db.commit()
            return deleted_count

        deleted_count = await db.run_sync(_batch_delete)
        logger.info(f"用户 {current_user.username} 批量删除了 {deleted_count} 个测试点")
        return {
            "code": 200, "message": f"成功删除 {deleted_count} 个测试点",
            "data": {"deleted_count": deleted_count, "requested_count": len(unique_ids)},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除测试点失败: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )


@router.delete("/{test_point_id}")
async def delete_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        def _delete(sync_db) -> dict:
            check_project_permission(sync_db, project_id, current_user.id)
            test_point = get_test_point_by_id(sync_db, test_point_id, project_id)
            if not test_point:
                return {"id": test_point_id}
            sync_db.delete(test_point)
            sync_db.commit()
            return {"id": test_point_id}

        data = await db.run_sync(_delete)
        logger.info(f"用户 {current_user.username} 删除了测试点 {test_point_id}")
        return {"code": 200, "message": "删除成功", "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除测试点失败: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
        )
