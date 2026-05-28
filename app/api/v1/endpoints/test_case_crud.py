"""
测试用例CRUD端点模块

本模块定义测试用例的基础增删改查API端点，包括单条操作。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST   /                    - 创建测试用例（含步骤和测试数据）
    - GET    /                    - 查询测试用例列表（分页、按项目/需求文件筛选）
    - GET    /{test_case_id}      - 获取用例详情
    - PUT    /{test_case_id}      - 更新用例（含步骤重建）
    - DELETE /{test_case_id}      - 软删除单个用例

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 创建用例时同步创建步骤和测试数据记录
    - 更新用例时若步骤变更，先删除旧步骤再重建
    - 删除为软删除（is_deleted标记），支持批量恢复
    - 用例编号自动生成，格式: CASE{project_id}-{时间戳}
"""
from datetime import datetime
from typing import Optional
from app.utils.db_time import utcnow
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_case import (
    TestCaseCreate, TestCaseUpdate, TestCaseListResponse,
)
from app.models.test_case import TestCase, TestStep
from app.models.enums import TestCaseLifecycleStatus
from app.models.test_data import TestData, DataType, GenerationRule
from app.models.project import Project
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


def merge_test_data_to_steps(test_case: TestCaseCreate) -> list:
    steps_list = [step.model_dump() for step in test_case.steps]
    top_level_test_data = getattr(test_case, 'test_data', None)
    if top_level_test_data and isinstance(top_level_test_data, dict) and steps_list:
        steps_list[0]['test_data'] = top_level_test_data
    return steps_list


def create_steps_and_test_data(test_case: TestCaseCreate, new_test_case_id: int, db: Session) -> None:
    for i, step_data in enumerate(test_case.steps or []):
        step = TestStep(
            test_case_id=new_test_case_id,
            step_number=i + 1,
            action=step_data.action,
            expected_result=step_data.expected_result if step_data.expected_result else "",
            action_type=step_data.action_type if hasattr(step_data, 'action_type') and step_data.action_type else None,
            input_value=step_data.input_value if hasattr(step_data, 'input_value') and step_data.input_value else None,
            target_element=step_data.target_element if hasattr(step_data, 'target_element') and step_data.target_element else None,
            is_business_view=1,
            is_technical_view=1
        )
        db.add(step)
        db.flush()

        step_test_data = step_data.test_data if hasattr(step_data, 'test_data') and step_data.test_data else None
        if step_test_data and isinstance(step_test_data, list):
            for j, td in enumerate(step_test_data):
                if not isinstance(td, dict):
                    continue
                field_type_str = td.get('field_type', 'text')
                try:
                    field_type = DataType(field_type_str)
                except ValueError:
                    field_type = DataType.TEXT

                gen_rule_str = td.get('generation_rule', 'custom')
                try:
                    gen_rule = GenerationRule(gen_rule_str)
                except ValueError:
                    gen_rule = GenerationRule.CUSTOM

                enum_values = td.get('enum_values')
                enum_values_str = json.dumps(enum_values, ensure_ascii=False) if enum_values else None

                test_data_record = TestData(
                    step_id=step.id,
                    field_name=td.get('field_name', ''),
                    field_type=field_type,
                    data_value=td.get('data_value', ''),
                    generation_rule=gen_rule,
                    enum_values=enum_values_str,
                    description=td.get('description', ''),
                    is_required=True,
                    sort_order=j
                )
                db.add(test_data_record)


@router.post("/")
async def create_test_case(
    test_case: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建测试用例（含步骤和测试数据，编号自动生成）"""
    # 验证用户对项目的访问权限
    project = db.query(Project).filter(
        Project.id == test_case.project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    new_test_case = TestCase(
        project_id=test_case.project_id,
        case_no=test_case.case_no if test_case.case_no else f"CASE{test_case.project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
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
        test_category=test_case.test_category if test_case.test_category else None
    )

    db.add(new_test_case)
    db.flush()

    create_steps_and_test_data(test_case, new_test_case.id, db)

    db.commit()
    db.refresh(new_test_case)

    return create_response(data=build_test_case_response(new_test_case))


@router.get("/")
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """查询测试用例列表（分页，按项目/需求文件筛选，排除已删除，只返回用户有权访问的项目的用例）"""
    authorized_project_ids_query = db.query(Project.id).filter(
        Project.user_id == current_user.id
    )

    query = db.query(TestCase).filter(TestCase.is_deleted.is_(False))

    # 限制只查询用户有权访问的项目
    query = query.filter(TestCase.project_id.in_(authorized_project_ids_query))

    if project_id:
        # 额外验证项目ID是否属于当前用户
        project_access = db.query(Project.id).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        if not project_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限访问此项目"
            )
        query = query.filter(TestCase.project_id == project_id)
    if requirement_file_id:
        query = query.filter(TestCase.requirement_file_id == requirement_file_id)
    if module:
        query = query.filter(TestCase.module == module)
    if priority is not None:
        query = query.filter(TestCase.priority == priority)
    if case_type:
        query = query.filter(TestCase.case_type == case_type)
    if target_device:
        if target_device == "general":
            query = query.filter(TestCase.target_device.is_(None))
        else:
            query = query.filter(TestCase.target_device == target_device)
    if keyword:
        keyword_like = f"%{keyword.strip()}%"
        query = query.filter(or_(TestCase.title.like(keyword_like), TestCase.case_no.like(keyword_like), TestCase.module.like(keyword_like)))
    if status_filter and not lifecycle_status:
        lifecycle_status = status_filter
    if lifecycle_status:
        valid_statuses = {s.value for s in TestCaseLifecycleStatus}
        statuses = [s.strip() for s in lifecycle_status.split(",") if s.strip()]
        invalid = [s for s in statuses if s not in valid_statuses]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的生命周期状态: {', '.join(invalid)}",
            )
        if len(statuses) == 1:
            query = query.filter(TestCase.lifecycle_status == statuses[0])
        elif statuses:
            query = query.filter(TestCase.lifecycle_status.in_(statuses))

    offset = (page - 1) * page_size

    total = query.count()
    automated = query.filter(TestCase.case_type.in_(["ui_automation", "api_automation"])).count()
    manual = query.filter(TestCase.case_type == "manual").count()
    high_priority = query.filter(TestCase.priority == 1).count()

    sort_columns = {
        "create_time": TestCase.create_time,
        "update_time": TestCase.update_time,
        "priority": TestCase.priority,
        "title": TestCase.title,
    }
    sort_column = sort_columns.get(sort_by or "create_time", TestCase.create_time)
    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    test_cases = query.offset(offset).limit(page_size).all()

    items = [build_test_case_response(tc) for tc in test_cases]

    return create_response(
        data=TestCaseListResponse(
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
        )
    )


@router.get("/{test_case_id}")
async def get_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试用例详情（含步骤和测试数据，只允许访问用户有权访问的项目的用例）"""
    # 先验证用例所属项目是否属于当前用户
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    return create_response(data=build_test_case_response(test_case))


@router.put("/{test_case_id}")
async def update_test_case(
    test_case_id: int,
    test_case_update: TestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新测试用例（部分更新，步骤变更时重建，只允许操作用户有权访问的项目的用例）"""
    # 先验证用例所属项目是否属于当前用户
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    try:
        update_data = test_case_update.model_dump(exclude_unset=True)

        steps_data = None
        if 'steps' in update_data and update_data['steps'] is not None:
            steps_data = update_data['steps']
            test_case.steps_json = steps_data
            del update_data['steps']

        for field, value in update_data.items():
            setattr(test_case, field, value)

        db.flush()

        if steps_data is not None:
            db.query(TestStep).filter(TestStep.test_case_id == test_case_id).delete()

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

        db.commit()
        db.refresh(test_case)

        return create_response(data=build_test_case_response(test_case))
    except Exception as e:
        db.rollback()
        logger.error(f"更新测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新测试用例失败"
        )


@router.delete("/{test_case_id}")
async def delete_test_case(
    test_case_id: int,
    project_id: Optional[int] = Query(default=None, description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """软删除测试用例（is_deleted标记，可批量恢复）"""
    query = db.query(TestCase).join(Project).filter(
        TestCase.id == test_case_id,
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    )
    if project_id:
        query = query.filter(TestCase.project_id == project_id)

    test_case = query.first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    test_case.is_deleted = True
    test_case.deleted_at = utcnow()
    db.commit()

    logger.info(f"[删除用例] 用户ID={current_user.id}, 用户名={current_user.username}, 用例ID={test_case_id}")

    return {"message": "测试用例已删除"}
