"""测试用例 CRUD 创建与查询路由处理函数。

路由处理函数以普通 async 函数形式定义，由 test_case_crud.py 通过
router.add_api_route 注册，保持 router 定义在原文件中。

本文件包含:
    - POST /                - 创建测试用例（含步骤和测试数据）
    - GET  /                - 查询测试用例列表（分页、按项目/需求文件筛选）
    - GET  /{test_case_id}  - 获取用例详情
"""
from typing import Optional

from fastapi import Depends, HTTPException, status, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_get_db
from app.schemas.test_case import (
    TestCaseCreate, TestCaseListResponse,
)
from app.models.test_case import TestCase
from app.models.enums import TestCaseLifecycleStatus
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.services.case_number_service import CaseNumberService
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger

from app.api.v1.endpoints._test_case_crud_helpers import (
    merge_test_data_to_steps,
    create_steps_and_test_data,
)


async def create_test_case(
    test_case: TestCaseCreate,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """创建测试用例（含步骤和测试数据，编号自动生成）"""
    try:
        project_result = await db.execute(
            select(Project).where(
                Project.id == test_case.project_id,
                Project.user_id == current_user.id,
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        case_no = test_case.case_no
        if not case_no:
            case_no = await CaseNumberService.generate_async(test_case.project_id, db)

        new_test_case = TestCase(
            project_id=test_case.project_id,
            case_no=case_no,
            module=test_case.module,
            title=test_case.title,
            precondition=test_case.precondition,
            steps_json=merge_test_data_to_steps(test_case),
            expected_result=test_case.expected_result,
            priority=test_case.priority,
            case_type=test_case.case_type,
            exec_script=test_case.exec_script,
            generate_status=test_case.generate_status,
            lifecycle_status=test_case.lifecycle_status,
            test_point_id=test_case.test_point_id,
            summary=test_case.summary,
            summary_model_version=test_case.summary_model_version,
            parent_case_id=test_case.parent_case_id,
            ai_change_type=test_case.ai_change_type,
            test_category=test_case.test_category if test_case.test_category else None,
        )

        db.add(new_test_case)
        await db.flush()

        await create_steps_and_test_data(test_case, new_test_case.id, db)

        await db.commit()
        await db.refresh(new_test_case)

        return create_response(data=build_test_case_response(new_test_case))
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"创建测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建测试用例失败"
        )


async def get_test_cases(
    project_id: Optional[int] = Query(default=None, description="项目ID"),
    requirement_file_id: Optional[int] = Query(default=None, description="需求文件ID"),
    lifecycle_status: Optional[str] = Query(default=None, description="生命周期状态（逗号分隔多值）"),
    keyword: Optional[str] = Query(default=None, description="关键词"),
    module: Optional[str] = Query(default=None, description="模块"),
    priority: Optional[int] = Query(default=None, ge=1, le=3, description="优先级"),
    case_type: Optional[str] = Query(default=None, description="用例类型"),
    target_device: Optional[str] = Query(default=None, description="按目标设备类型筛选"),
    status_filter: Optional[str] = Query(default=None, alias="status", description="生命周期状态别名"),
    sort_by: Optional[str] = Query(default="create_time", description="排序字段"),
    sort_order: Optional[str] = Query(default="desc", pattern="^(asc|desc)$", description="排序方向"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=500, description="每页数量"),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """查询测试用例列表（分页，按项目/需求文件筛选，排除已删除，只返回用户有权访问的项目的用例）"""
    effective_lifecycle_status = lifecycle_status or status_filter
    try:
        authorized_subquery = select(Project.id).where(
            Project.user_id == current_user.id
        )

        conditions = [
            TestCase.is_deleted.is_(False),
            TestCase.project_id.in_(authorized_subquery),
        ]

        if project_id:
            project_access_result = await db.execute(
                select(Project.id).where(
                    Project.id == project_id,
                    Project.user_id == current_user.id,
                )
            )
            if not project_access_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="无权限访问此项目"
                )
            conditions.append(TestCase.project_id == project_id)
        if requirement_file_id:
            conditions.append(TestCase.requirement_file_id == requirement_file_id)
        if module:
            conditions.append(TestCase.module == module)
        if priority is not None:
            conditions.append(TestCase.priority == priority)
        if case_type:
            conditions.append(TestCase.case_type == case_type)
        if target_device:
            if target_device == "general":
                conditions.append(TestCase.target_device.is_(None))
            else:
                conditions.append(TestCase.target_device == target_device)
        if keyword:
            keyword_like = f"%{keyword.strip()}%"
            conditions.append(
                or_(
                    TestCase.title.like(keyword_like),
                    TestCase.case_no.like(keyword_like),
                    TestCase.module.like(keyword_like),
                )
            )
        if effective_lifecycle_status:
            valid_statuses = {s.value for s in TestCaseLifecycleStatus}
            statuses = [s.strip() for s in effective_lifecycle_status.split(",") if s.strip()]
            invalid = [s for s in statuses if s not in valid_statuses]
            if invalid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的生命周期状态: {', '.join(invalid)}",
                )
            if len(statuses) == 1:
                conditions.append(TestCase.lifecycle_status == statuses[0])
            elif statuses:
                conditions.append(TestCase.lifecycle_status.in_(statuses))

        offset = (page - 1) * page_size

        total = (await db.execute(
            select(func.count()).select_from(TestCase).where(*conditions)
        )).scalar() or 0

        automated_conditions = conditions + [
            TestCase.case_type.in_(["ui_automation", "api_automation"])
        ]
        automated = (await db.execute(
            select(func.count()).select_from(TestCase).where(*automated_conditions)
        )).scalar() or 0

        manual_conditions = conditions + [TestCase.case_type == "manual"]
        manual = (await db.execute(
            select(func.count()).select_from(TestCase).where(*manual_conditions)
        )).scalar() or 0

        high_priority_conditions = conditions + [TestCase.priority == 1]
        high_priority = (await db.execute(
            select(func.count()).select_from(TestCase).where(*high_priority_conditions)
        )).scalar() or 0

        sort_columns = {
            "create_time": TestCase.create_time,
            "update_time": TestCase.update_time,
            "priority": TestCase.priority,
            "title": TestCase.title,
        }
        sort_column = sort_columns.get(sort_by or "create_time", TestCase.create_time)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        result = await db.execute(
            select(TestCase).where(*conditions).order_by(order_clause).offset(offset).limit(page_size)
        )
        test_cases = result.scalars().all()
        items = [build_test_case_response(tc) for tc in test_cases]

        data = TestCaseListResponse(
            total=total,
            items=items,
            page=page,
            page_size=page_size,
            stats={
                "total": total,
                "automated": automated,
                "manual": manual,
                "high_priority": high_priority,
            }
        ).model_dump()

        return create_response(data=data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询测试用例列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="查询测试用例列表失败"
        )


async def get_test_case(
    test_case_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试用例详情（含步骤和测试数据，只允许访问用户有权访问的项目的用例）"""
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

        return create_response(data=build_test_case_response(test_case))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试用例详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取测试用例详情失败"
        )
