"""
测试用例AI前置条件端点模块

本模块定义测试用例前置条件相关的API端点，包括查询、保存和AI解析前置条件步骤。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - GET  /{case_id}/precondition-steps  - 获取前置条件步骤
    - PUT  /{case_id}/precondition-steps  - 批量保存前置条件步骤
    - POST /{case_id}/parse-precondition  - AI解析前置条件为步骤

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 前置条件步骤独立于主测试步骤管理
    - AI解析调用DeepSeek API，需配置DEEPSEEK_API_KEY
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase, TestCasePreconditionStep
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import get_current_user
from app.utils.ai_client import parse_precondition_to_steps
from app.schemas.test_case import PreconditionStepBatchSave, PreconditionStepResponse
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取前置条件步骤列表"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    steps = db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).order_by(TestCasePreconditionStep.step_number).all()

    return create_response(data=[PreconditionStepResponse.model_validate(s) for s in steps])


@router.put("/{case_id}/precondition-steps")
async def batch_save_precondition_steps(
    case_id: int,
    request: PreconditionStepBatchSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量保存前置条件步骤（覆盖式保存）"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).delete()

    for i, step_data in enumerate(request.steps):
        step = TestCasePreconditionStep(
            test_case_id=case_id,
            step_number=step_data.step_number or (i + 1),
            action=step_data.action,
            expected_result=step_data.expected_result or "",
            action_type=step_data.action_type,
            input_value=step_data.input_value,
            target_element=step_data.target_element,
            has_locator=0,
            locator_status="pending"
        )
        db.add(step)

    db.commit()

    steps = db.query(TestCasePreconditionStep).filter(
        TestCasePreconditionStep.test_case_id == case_id
    ).order_by(TestCasePreconditionStep.step_number).all()

    return create_response(data=[PreconditionStepResponse.model_validate(s) for s in steps])


@router.post("/{case_id}/parse-precondition")
async def parse_precondition(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """AI解析前置条件为可执行步骤"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id,
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    if not test_case.precondition:
        return create_response(data=[], msg="前置条件为空，无需解析")

    project_url = ""
    if test_case.project_id:
        project = db.query(Project).filter(Project.id == test_case.project_id).first()
        if project:
            project_url = getattr(project, 'test_object_url', '') or ''

    try:
        steps = await parse_precondition_to_steps(
            precondition_text=test_case.precondition,
            project_url=project_url
        )

        if steps:
            db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).delete()

            for i, step_data in enumerate(steps):
                pc_step = TestCasePreconditionStep(
                    test_case_id=case_id,
                    step_number=step_data.get('step_number', i + 1),
                    action=step_data.get('action', ''),
                    expected_result=step_data.get('expected_result', ''),
                    action_type=step_data.get('action_type', ''),
                    input_value=step_data.get('input_value', ''),
                    target_element=step_data.get('target_element', ''),
                    has_locator=0,
                    locator_status="pending"
                )
                db.add(pc_step)

            db.commit()

            saved_steps = db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).order_by(TestCasePreconditionStep.step_number).all()

            return create_response(
                data=[PreconditionStepResponse.model_validate(s) for s in saved_steps],
                msg=f"解析成功，生成 {len(steps)} 个步骤"
            )

        return create_response(data=[], msg="解析成功，但未生成步骤")
    except Exception as e:
        logger.error(f"AI解析前置条件失败: {e}")
        raise HTTPException(status_code=500, detail="AI解析前置条件失败")
