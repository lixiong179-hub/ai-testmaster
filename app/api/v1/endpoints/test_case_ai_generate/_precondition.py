from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
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
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get(sync_db):
        test_case = sync_db.query(TestCase).join(Project).filter(
            TestCase.id == case_id,
            TestCase.is_deleted.is_(False),
            Project.user_id == current_user.id
        ).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")
        steps = sync_db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.test_case_id == case_id
        ).order_by(TestCasePreconditionStep.step_number).all()
        return [PreconditionStepResponse.model_validate(s) for s in steps]
    data = await db.run_sync(_get)
    return create_response(data=data)


@router.put("/{case_id}/precondition-steps")
async def batch_save_precondition_steps(
    case_id: int,
    request: PreconditionStepBatchSave,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _save(sync_db):
        test_case = sync_db.query(TestCase).join(Project).filter(
            TestCase.id == case_id, TestCase.is_deleted.is_(False),
            Project.user_id == current_user.id
        ).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")
        sync_db.query(TestCasePreconditionStep).filter(
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
            sync_db.add(step)
        sync_db.commit()
        steps = sync_db.query(TestCasePreconditionStep).filter(
            TestCasePreconditionStep.test_case_id == case_id
        ).order_by(TestCasePreconditionStep.step_number).all()
        return [PreconditionStepResponse.model_validate(s) for s in steps]
    data = await db.run_sync(_save)
    return create_response(data=data)


@router.post("/{case_id}/parse-precondition")
async def parse_precondition(
    case_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get_precondition(sync_db):
        test_case = sync_db.query(TestCase).join(Project).filter(
            TestCase.id == case_id, TestCase.is_deleted.is_(False),
            Project.user_id == current_user.id
        ).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="测试用例不存在")
        return test_case.precondition
    precondition = await db.run_sync(_get_precondition)
    if not precondition:
        return create_response(data=[], msg="前置条件为空，无需解析")
    try:
        steps = parse_precondition_to_steps(
            precondition=precondition,
        )
        if steps:
            def _save_steps(sync_db):
                sync_db.query(TestCasePreconditionStep).filter(
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
                    sync_db.add(pc_step)
                sync_db.commit()
                saved_steps = sync_db.query(TestCasePreconditionStep).filter(
                    TestCasePreconditionStep.test_case_id == case_id
                ).order_by(TestCasePreconditionStep.step_number).all()
                return [PreconditionStepResponse.model_validate(s) for s in saved_steps]
            saved = await db.run_sync(_save_steps)
            return create_response(
                data=saved,
                msg=f"解析成功，生成 {len(steps)} 个步骤",
            )
        return create_response(data=[], msg="解析成功，但未生成步骤")
    except Exception as e:
        logger.error(f"AI解析前置条件失败: {e}")
        raise HTTPException(status_code=500, detail="AI解析前置条件失败")
