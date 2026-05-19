from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase, TestCasePreconditionStep
from app.models.user import User
from app.schemas.test_case import (
    PreconditionStepBatchSave,
    PreconditionStepResponse,
)
from app.utils.ai_client import parse_precondition_to_steps

router = APIRouter()


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id,
        TestCase.is_deleted.is_(False),
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
    current_user: User = Depends(get_current_user),
):
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, TestCase.is_deleted.is_(False),
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
            has_locator=0, locator_status="pending",
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
    current_user: User = Depends(get_current_user),
):
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    if not test_case.precondition:
        return create_response(data=[], msg="前置条件为空，无需解析")
    project_url = ""
    if test_case.project_id:
        proj = db.query(Project).filter(Project.id == test_case.project_id).first()
        if proj:
            project_url = getattr(proj, "test_object_url", "") or ""
    try:
        steps = await parse_precondition_to_steps(
            precondition_text=test_case.precondition, project_url=project_url,
        )
        if steps:
            db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).delete()
            for i, step_data in enumerate(steps):
                pc_step = TestCasePreconditionStep(
                    test_case_id=case_id,
                    step_number=step_data.get("step_number", i + 1),
                    action=step_data.get("action", ""),
                    expected_result=step_data.get("expected_result", ""),
                    action_type=step_data.get("action_type", ""),
                    input_value=step_data.get("input_value", ""),
                    target_element=step_data.get("target_element", ""),
                    has_locator=0, locator_status="pending",
                )
                db.add(pc_step)
            db.commit()
            saved_steps = db.query(TestCasePreconditionStep).filter(
                TestCasePreconditionStep.test_case_id == case_id
            ).order_by(TestCasePreconditionStep.step_number).all()
            return create_response(
                data=[PreconditionStepResponse.model_validate(s) for s in saved_steps],
                msg=f"解析成功，生成 {len(steps)} 个步骤",
            )
        return create_response(data=[], msg="解析成功，但未生成步骤")
    except Exception as e:
        logger.error(f"AI解析前置条件失败: {e}")
        raise HTTPException(status_code=500, detail="AI解析前置条件失败")
