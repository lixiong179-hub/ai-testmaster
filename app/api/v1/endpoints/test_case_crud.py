"""
测试用例CRUD端点模块

本模块定义测试用例的基础增删改查API端点，包括单条和批量操作。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST   /                    - 创建测试用例（含步骤和测试数据）
    - GET    /                    - 查询测试用例列表（分页、按项目/需求文件筛选）
    - POST   /batch-restore       - 批量恢复已删除的用例
    - POST   /batch-delete        - 批量软删除用例
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
from typing import Optional
from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_case import (
    TestCaseCreate, TestCaseUpdate, TestCaseListResponse,
)
from app.models.test_case import TestCase, TestStep
from app.models.test_data import TestData, DataType, GenerationRule
from app.models.user import User
from app.api.v1.endpoints.auth import oauth2_scheme, get_current_user
from app.utils.test_case_helpers import build_test_case_response
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.post("/")
async def create_test_case(
    test_case: TestCaseCreate,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    创建测试用例

    创建新的测试用例，同时创建关联的测试步骤和测试数据记录。
    用例编号自动生成，格式为 CASE{project_id}-{时间戳}。

    请求参数(TestCaseCreate):
        - project_id: 所属项目ID（必填）
        - title: 用例标题（必填）
        - module: 所属模块
        - precondition: 前置条件
        - steps: 测试步骤列表（含测试数据）
        - expected_result: 预期结果
        - priority: 优先级（1-高/2-中/3-低）
        - case_type: 用例类型

    权限要求: 需要Bearer令牌认证
    """
    new_test_case = TestCase(
        project_id=test_case.project_id,
        case_no=test_case.case_no if test_case.case_no else f"CASE{test_case.project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        module=test_case.module,
        title=test_case.title,
        precondition=test_case.precondition,
        steps_json=[step.model_dump() for step in test_case.steps],
        expected_result=test_case.expected_result,
        priority=test_case.priority,
        case_type=test_case.case_type,
        exec_script=test_case.exec_script,
        generate_status=test_case.generate_status,
        test_category=test_case.test_category if test_case.test_category else None
    )

    db.add(new_test_case)
    db.flush()

    for i, step_data in enumerate(test_case.steps):
        step = TestStep(
            test_case_id=new_test_case.id,
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

    db.commit()
    db.refresh(new_test_case)

    return create_response(data=build_test_case_response(new_test_case))


@router.get("/")
async def get_test_cases(
    project_id: Optional[int] = Query(default=None, description="项目ID"),
    requirement_file_id: Optional[int] = Query(default=None, description="需求文件ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    查询测试用例列表

    分页查询测试用例，支持按项目ID和需求文件ID筛选。
    默认排除已软删除的用例。

    请求参数:
        - project_id: 项目ID（可选，筛选指定项目的用例）
        - requirement_file_id: 需求文件ID（可选）
        - page: 页码（默认1）
        - page_size: 每页数量（默认10，最大100）

    权限要求: 需要Bearer令牌认证
    """
    query = db.query(TestCase).filter(TestCase.is_deleted == False)
    if project_id:
        query = query.filter(TestCase.project_id == project_id)
    if requirement_file_id:
        query = query.filter(TestCase.requirement_file_id == requirement_file_id)

    offset = (page - 1) * page_size

    test_cases = query.offset(offset).limit(page_size).all()
    total = query.count()

    items = [build_test_case_response(tc) for tc in test_cases]

    return create_response(
        data=TestCaseListResponse(
            total=total,
            items=items,
            page=page,
            page_size=page_size
        )
    )


class BatchRestoreRequest(BaseModel):
    """批量恢复请求模型，限制单次最多恢复500个用例"""
    caseIds: list[int]

    @field_validator('caseIds')
    @classmethod
    def validate_case_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError('用例ID列表不能为空')
        if len(v) > 500:
            raise ValueError(f'一次最多恢复500个用例，当前: {len(v)}')
        return v


@router.post("/batch-restore")
async def batch_restore_test_cases(
    request: BatchRestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量恢复已删除的测试用例

    将已软删除的用例恢复为正常状态，清除删除时间标记。
    单次最多恢复500个用例。

    请求参数(BatchRestoreRequest):
        - caseIds: 用例ID列表（最多500个）

    响应格式:
        - successCount: 成功恢复数量
        - failCount: 失败数量
        - notFoundIds: 未找到的用例ID列表

    权限要求: 需要Bearer令牌认证
    """
    case_ids = request.caseIds
    success_count = 0
    fail_count = 0
    not_found_ids = []

    deleted_cases = db.query(TestCase).filter(
        TestCase.id.in_(case_ids),
        TestCase.is_deleted == True
    ).all()

    existing_ids = {case.id for case in deleted_cases}
    not_found_ids = [id for id in case_ids if id not in existing_ids]

    restored_case_ids = []
    for test_case in deleted_cases:
        try:
            test_case.is_deleted = False
            test_case.deleted_at = None
            success_count += 1
            restored_case_ids.append(test_case.id)
        except Exception as e:
            logger.error(f"恢复用例 {test_case.id} 失败: {e}")
            fail_count += 1

    db.commit()

    logger.info(
        f"[批量恢复] 用户ID={current_user.id}, 用户名={current_user.username}, "
        f"恢复用例IDs={restored_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"
    )

    return create_response(data={
        "successCount": success_count,
        "failCount": fail_count,
        "notFoundCount": len(not_found_ids),
        "notFoundIds": not_found_ids,
        "restoredIds": restored_case_ids,
        "total": len(case_ids),
        "message": f"恢复完成：成功 {success_count} 个，失败 {fail_count} 个，未找到 {len(not_found_ids)} 个"
    })


class BatchDeleteRequest(BaseModel):
    """批量删除请求模型，限制单次最多删除500个用例"""
    caseIds: list[int]

    @field_validator('caseIds')
    @classmethod
    def validate_case_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError('用例ID列表不能为空')
        if len(v) > 500:
            raise ValueError(f'一次最多删除500个用例，当前: {len(v)}')
        return v


@router.post("/batch-delete")
async def batch_delete_test_cases(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量软删除测试用例

    将指定用例标记为已删除（is_deleted=True），记录删除时间。
    单次最多删除500个用例。已删除的用例可通过批量恢复接口恢复。

    请求参数(BatchDeleteRequest):
        - caseIds: 用例ID列表（最多500个）

    响应格式:
        - successCount: 成功删除数量
        - failCount: 失败数量
        - notFoundIds: 未找到的用例ID列表

    权限要求: 需要Bearer令牌认证
    """
    from datetime import datetime as dt

    case_ids = request.caseIds
    success_count = 0
    fail_count = 0
    not_found_ids = []

    existing_cases = db.query(TestCase).filter(
        TestCase.id.in_(case_ids),
        TestCase.is_deleted == False
    ).all()

    existing_ids = {case.id for case in existing_cases}
    not_found_ids = [id for id in case_ids if id not in existing_ids]

    deleted_case_ids = []
    for test_case in existing_cases:
        try:
            test_case.is_deleted = True
            test_case.deleted_at = dt.utcnow()
            success_count += 1
            deleted_case_ids.append(test_case.id)
        except Exception as e:
            logger.error(f"删除用例 {test_case.id} 失败: {e}")
            fail_count += 1

    db.commit()

    logger.info(
        f"[批量删除] 用户ID={current_user.id}, 用户名={current_user.username}, "
        f"删除用例IDs={deleted_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"
    )

    return create_response(data={
        "successCount": success_count,
        "failCount": fail_count,
        "notFoundCount": len(not_found_ids),
        "notFoundIds": not_found_ids,
        "deletedIds": deleted_case_ids,
        "total": len(case_ids),
        "message": f"删除完成：成功 {success_count} 个，失败 {fail_count} 个，未找到 {len(not_found_ids)} 个"
    })


@router.get("/{test_case_id}")
async def get_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    """
    获取测试用例详情

    根据ID查询单个测试用例的完整信息，包括步骤和测试数据。

    路径参数:
        - test_case_id: 测试用例ID

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
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
    token: str = Depends(oauth2_scheme)
):
    """
    更新测试用例

    更新指定测试用例的信息。若步骤数据发生变更，先删除旧步骤再重建。
    仅更新请求体中明确提供的字段（部分更新）。

    路径参数:
        - test_case_id: 测试用例ID

    请求参数(TestCaseUpdate): 支持部分更新，仅传入需修改的字段

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 404: 测试用例不存在
        HTTPException 500: 更新失败
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.is_deleted == False).first()
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
            detail=f"更新测试用例失败: {str(e)}"
        )


@router.delete("/{test_case_id}")
async def delete_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    软删除测试用例

    将指定测试用例标记为已删除（is_deleted=True），记录删除时间。
    已删除的用例可通过批量恢复接口恢复。

    路径参数:
        - test_case_id: 测试用例ID

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    from datetime import datetime as dt
    test_case.is_deleted = True
    test_case.deleted_at = dt.utcnow()
    db.commit()

    logger.info(f"[删除用例] 用户ID={current_user.id}, 用户名={current_user.username}, 用例ID={test_case_id}")

    return {"message": "测试用例已删除"}
