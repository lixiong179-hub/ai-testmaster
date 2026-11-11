"""测试用例CRUD端点模块（async 版本）。

本模块为测试用例基础增删改查API端点的聚合入口，路由处理函数直接内联在本文件中，
共享工具函数下沉至 app/services/test_case_crud_helpers.py。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST   /                    - 创建测试用例（含步骤和测试数据）
    - GET    /                    - 查询测试用例列表（分页、按项目/需求文件筛选）
    - GET    /{test_case_id}      - 获取用例详情
    - PUT    /{test_case_id}      - 更新用例（含步骤重建）
    - DELETE /{test_case_id}      - 软删除单个用例

权限要求: 所有端点需要Bearer令牌认证

迁移说明（P0 服务 async 化）:
    消除所有 db.run_sync() 包裹，内联 DB 操作改为 select() + await db.execute()。
    create_steps_and_test_data 改为 async，供本模块与 test_case_crud_batch 共享。

公开符号通过本文件 re-export，保持 import 路径不变
（from app.api.v1.endpoints.test_case_crud import xxx）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.enums import TestCaseLifecycleStatus
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.schemas.test_case import (
    TestCaseCreate,
    TestCaseListResponse,
    TestCaseUpdate,
)
from app.services.case_number_service import CaseNumberService
from app.services.test_case_crud_helpers import (
    merge_test_data_to_steps,
    create_steps_and_test_data,
)
from app.utils.db_time import utcnow
from app.utils.test_case_helpers import build_test_case_response


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


router = APIRouter()

router.add_api_route("/", create_test_case, methods=["POST"])
router.add_api_route("/", get_test_cases, methods=["GET"])
router.add_api_route("/{test_case_id}", get_test_case, methods=["GET"])
router.add_api_route("/{test_case_id}", update_test_case, methods=["PUT"])
router.add_api_route("/{test_case_id}", delete_test_case, methods=["DELETE"])

__all__ = [
    "router",
    "merge_test_data_to_steps",
    "create_steps_and_test_data",
    "create_test_case",
    "get_test_cases",
    "get_test_case",
    "update_test_case",
    "delete_test_case",
]
