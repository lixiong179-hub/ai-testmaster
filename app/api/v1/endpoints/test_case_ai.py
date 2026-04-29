from typing import Optional, List
from datetime import datetime
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.user import User
from app.models.project import Project
from app.api.v1.endpoints.auth import oauth2_scheme, get_current_user
from app.utils.ai_client import (
    generate_test_case,
    generate_test_case_enhanced,
    parse_precondition_to_steps,
    AIServiceError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError
)
from app.utils.test_case_helpers import convert_steps_to_response
from app.schemas.test_case import PreconditionStepBatchSave, PreconditionStepResponse
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class AIGenerateRequest(BaseModel):
    project_id: int
    description: str

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('描述不能为空且至少需要10个字符')
        if len(v) > 10000:
            raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')
        return v.strip()


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    project_id = request_data.project_id
    description = request_data.description

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    if not description or len(description.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="描述不能为空且至少需要10个字符"
        )

    try:
        generated_case = generate_test_case(description)

        priority_map = {"high": 1, "medium": 2, "low": 3}
        priority_value = priority_map.get(generated_case["priority"], 2)

        new_test_case = TestCase(
            project_id=project_id,
            title=generated_case["title"],
            precondition=generated_case.get("precondition", ""),
            expected_result=generated_case.get("expected_result", ""),
            priority=priority_value,
            module="AI生成",
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None)
        )

        db.add(new_test_case)
        db.flush()

        for i, step in enumerate(generated_case.get("steps", [])):
            if "action" in step:
                action = step["action"]
            elif "step" in step:
                action = step["step"]
            else:
                action = f"步骤{i + 1}"

            if "expected_result" in step:
                expected_result = step["expected_result"]
            elif "param" in step:
                expected_result = step["param"]
            else:
                expected_result = "预期结果正常"

            test_step = TestStep(
                test_case_id=new_test_case.id,
                step_number=i + 1,
                action=action,
                expected_result=expected_result,
                action_type=step.get("action_type", ""),
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1,
                is_technical_view=1
            )
            db.add(test_step)

        db.commit()
        db.refresh(new_test_case)

        from app.utils.test_case_helpers import build_test_case_response
        return create_response(data=build_test_case_response(new_test_case))
    except AIAuthenticationError as e:
        db.rollback()
        logger.error(f"AI认证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI服务认证失败: {e.message}。请检查 .env 文件中的 DEEPSEEK_API_KEY 是否正确。"
        )
    except AIRateLimitError as e:
        db.rollback()
        logger.error(f"AI请求频率限制: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI服务请求频率过高: {e.message}。请稍后重试。"
        )
    except AITimeoutError as e:
        db.rollback()
        logger.error(f"AI请求超时: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"AI服务请求超时: {e.message}。请稍后重试。"
        )
    except AIResponseFormatError as e:
        db.rollback()
        logger.error(f"AI响应格式错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI响应格式错误: {e.message}。请稍后重试或联系管理员。"
        )
    except AIResponseParseError as e:
        db.rollback()
        logger.error(f"AI响应解析失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI响应解析失败: {e.message}。请稍后重试或联系管理员。"
        )
    except AIServiceError as e:
        db.rollback()
        logger.error(f"AI服务错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"AI服务错误: {e.message}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"AI生成测试用例失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成失败: {str(e)}"
        )


class AIGenerateEnhancedRequest(BaseModel):
    project_id: int
    description: str
    case_type: Optional[str] = None
    exec_mode: str = "all"
    priority: int = 2
    enhanced_mode: bool = True
    context: Optional[dict] = None
    ui_screen_ids: Optional[List[int]] = None

    @field_validator('case_type')
    @classmethod
    def validate_case_type(cls, v):
        if v is None:
            return None
        valid_types = ('ui_automation', 'manual', 'api_automation', 'performance', 'security',
                       'functional', 'api_auto', 'UI', 'API')
        if v not in valid_types:
            raise ValueError(f'不支持的用例类型: {v}')
        from app.core.constants import TestCaseType
        return TestCaseType.from_legacy(v).value

    @field_validator('exec_mode')
    @classmethod
    def validate_exec_mode(cls, v):
        valid_modes = ('all', 'ui_auto', 'manual')
        if v not in valid_modes:
            raise ValueError(f'不支持的执行模式: {v}')
        return v

    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if len(v.strip()) < 5:
            raise ValueError('描述不能为空且至少需要5个字符')
        if len(v) > 10000:
            raise ValueError(f'描述过长({len(v)}字符)，最大允许10000字符')
        return v.strip()


@router.post("/ai-generate-enhanced")
async def ai_generate_test_case_enhanced(
    request_data: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
):
    project_id = request_data.project_id
    description = request_data.description

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="项目不存在"
        )

    if not description or len(description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="描述不能为空且至少需要5个字符"
        )

    try:
        context = request_data.context or {}
        logger.info(f"AI生成增强模式 - 接收到的context: {json.dumps(context, ensure_ascii=False, default=str)[:500]}")

        if request_data.enhanced_mode:
            test_points = context.get('test_points', [])
            test_point = context.get('test_point', {}) or context.get('current_test_point', {})
            logger.info(f"AI生成增强模式 - 解析后的test_point: {test_point}")
            if not test_point and test_points:
                test_point = test_points[0]
            if not test_point:
                test_point = {
                    'module': 'AI生成',
                    'function': '测试场景',
                    'point': description,
                    'priority': request_data.priority
                }

            raw_ui_desc = context.get('ui_description', '')
            ui_specs = context.get('ui_specs', [])

            generated_case = await asyncio.to_thread(generate_test_case_enhanced, {
                'requirement_content': context.get('requirement_content', ''),
                'ui_description': raw_ui_desc,
                'ui_spec': ui_specs[0].get('ui_spec', {}) if ui_specs else {},
                'ui_specs': ui_specs,
                'test_point': test_point,
                'case_type': request_data.case_type,
                'exec_mode': request_data.exec_mode,
                'project_config': context.get('project_config')
            })
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)

        priority_value = request_data.priority

        steps_data = convert_steps_to_response(generated_case.get("steps", []))

        return create_response(data={
            "id": 0,
            "project_id": project_id,
            "case_no": f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "module": generated_case.get("module", "AI生成"),
            "title": generated_case.get("title", description[:50]),
            "precondition": generated_case.get("precondition", ""),
            "test_data": generated_case.get("test_data", {}),
            "steps": steps_data,
            "expected_result": generated_case.get("expected_result", ""),
            "priority": priority_value,
            "case_type": generated_case.get("case_type", request_data.case_type),
            "generate_status": 1,
            "create_time": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI生成失败: {str(e)}"
        )


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
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
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
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
    test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
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
        raise HTTPException(status_code=500, detail=f"AI解析前置条件失败: {str(e)}")
