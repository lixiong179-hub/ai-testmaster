"""测试用例 CRUD 更新与删除路由处理函数。

路由处理函数以普通 async 函数形式定义，由 test_case_crud.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。

本文件包含:
    - PUT    /{test_case_id} - 更新用例（含步骤重建）
    - DELETE /{test_case_id} - 软删除单个用例
"""
from typing import Optional

from app.utils.db_time import utcnow
from fastapi import Depends, HTTPException, status, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.schemas.test_case import TestCaseUpdate
from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger


async def update_test_case(
    test_case_id: int,
    test_case_update: TestCaseUpdate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """更新测试用例（部分更新，步骤变更时重建，只允许操作用户有权访问的项目的用例）"""
    try:
        result = await db.execute(
            select(TestCase).join(Project).where(
                TestCase.id == test_case_id,
                TestCase.is_deleted.is_(False),
                Project.user_id == current_user.id,
            )
        )
        test_case = result.scalar_one_or_none()

        if not test_case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试用例不存在"
            )

        update_data = test_case_update.model_dump(exclude_unset=True)

        steps_data = None
        if 'steps' in update_data and update_data['steps'] is not None:
            steps_data = update_data['steps']
            test_case.steps_json = steps_data
            del update_data['steps']

        for field, value in update_data.items():
            setattr(test_case, field, value)

        await db.flush()

        if steps_data is not None:
            await db.execute(
                delete(TestStep).where(TestStep.test_case_id == test_case_id)
            )

            for i, step_data in enumerate(steps_data):
                step = TestStep(
                    test_case_id=test_case_id,
                    step_number=i + 1,
                    action=step_data.get('action', ''),
                    expected_result=step_data.get('expected_result', ''),
                    action_type=step_data.get('action_type', ''),
                    input_value=step_data.get('input_value', ''),
                    target_element=step_data.get('target_element', ''),
                    is_business_view=1,
                    is_technical_view=1
                )
                db.add(step)

        await db.commit()
        await db.refresh(test_case)

        return create_response(data=build_test_case_response(test_case))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新测试用例失败"
        )


async def delete_test_case(
    test_case_id: int,
    project_id: Optional[int] = Query(default=None, description="项目ID"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """软删除测试用例（is_deleted标记，可批量恢复）"""
    try:
        query = (
            select(TestCase)
            .join(Project)
            .where(
                TestCase.id == test_case_id,
                TestCase.is_deleted.is_(False),
                Project.user_id == current_user.id,
            )
        )
        if project_id:
            query = query.where(TestCase.project_id == project_id)

        result = await db.execute(query)
        test_case = result.scalar_one_or_none()
        if not test_case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试用例不存在"
            )

        test_case.is_deleted = True
        test_case.deleted_at = utcnow()
        await db.commit()

        logger.info(f"[删除用例] 用户ID={current_user.id}, 用户名={current_user.username}, 用例ID={test_case_id}")

        return {"message": "测试用例已删除"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"删除测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除测试用例失败"
        )
