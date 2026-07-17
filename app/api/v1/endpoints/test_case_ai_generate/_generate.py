import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai_helpers import (
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.api.v1.endpoints.test_case_ai_schemas import (
    AIGenerateEnhancedRequest,
    AIGenerateRequest,
)
from app.core.constants import normalize_priority, DEFAULT_AI_FALLBACK_CASE_TYPE
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.user import User
from app.utils.ai_client import (
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError,
    AIServiceError,
    generate_test_case,
    generate_test_case_enhanced,
)
from app.utils.test_case_helpers import build_test_case_response

router = APIRouter()

_AI_ERROR_MAP: dict[type[Exception], tuple[int, str]] = {
    AIAuthenticationError: (status.HTTP_503_SERVICE_UNAVAILABLE, "AI服务认证失败，请检查API密钥"),
    AIRateLimitError: (status.HTTP_429_TOO_MANY_REQUESTS, "AI服务请求频率过高，请稍后重试"),
    AITimeoutError: (status.HTTP_504_GATEWAY_TIMEOUT, "AI服务请求超时，请稍后重试"),
    AIResponseFormatError: (status.HTTP_502_BAD_GATEWAY, "AI响应格式错误，请稍后重试"),
    AIResponseParseError: (status.HTTP_502_BAD_GATEWAY, "AI响应格式错误，请稍后重试"),
    AIServiceError: (status.HTTP_503_SERVICE_UNAVAILABLE, "AI服务暂时不可用"),
}


def _raise_ai_error(e: Exception) -> None:
    if isinstance(e, HTTPException):
        raise e
    for exc_type, (http_code, detail) in _AI_ERROR_MAP.items():
        if isinstance(e, exc_type):
            raise HTTPException(status_code=http_code, detail=detail) from e
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败"
    )


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request_data.project_id
    description = request_data.description

    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    try:
        generated_case = generate_test_case(description)
        priority_value = normalize_priority(generated_case.get("priority", "medium"))

        new_test_case = TestCase(
            project_id=project_id, title=generated_case.get("title") or "(无标题)",
            precondition=generated_case.get("precondition", ""),
            expected_result=generated_case.get("expected_result", ""),
            priority=priority_value, module="AI生成",
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or DEFAULT_AI_FALLBACK_CASE_TYPE,
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None),
        )
        db.add(new_test_case)
        await db.flush()
        for i, step in enumerate(generated_case.get("steps", [])):
            action = step.get("action") or step.get("step") or f"步骤{i + 1}"
            expected_result = (
                step.get("expected_result") or step.get("param") or "预期结果正常"
            )
            test_step = TestStep(
                test_case_id=new_test_case.id, step_number=i + 1,
                action=action, expected_result=expected_result,
                action_type=step.get("action_type", ""),
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1, is_technical_view=1,
            )
            db.add(test_step)
        await db.commit()
        await db.refresh(new_test_case)
        data = build_test_case_response(new_test_case)
        return create_response(data=data)
    except Exception as e:
        await db.rollback()
        logger.error(f"AI生成测试用例失败: {e}")
        _raise_ai_error(e)


@router.post("/ai-enhanced-generate")
async def ai_enhanced_generate(
    request: AIGenerateEnhancedRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id
    description = request.description

    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.user_id == current_user.id
        )
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not description or len(description.strip()) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符"
        )
    if request.mode == "graph" and not request.flow_sort_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Graph模式下flow_sort_data不能为空"
        )
    try:
        context = dict(request.context or {})
        if request.extra_requirements:
            context["extra_requirements"] = request.extra_requirements
        logger.info(
            f"AI生成增强模式 - 接收到的context: "
            f"{json.dumps(context, ensure_ascii=False, default=str)[:500]}"
        )

        has_requirement = bool(context.get("requirement_content", "").strip())
        has_ui = bool(context.get("ui_specs"))
        has_ui_reference = has_ui or bool(context.get("ui_descriptions"))
        has_flow = request.mode == "graph" and request.flow_sort_data and len(request.flow_sort_data.nodes) > 0
        if not has_requirement and not has_ui_reference and not has_flow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="生成上下文为空：请上传需求文档、UI原型图或配置流程节点，确保AI有足够的输入信息"
            )

        if request.mode == "graph":
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request.flow_sort_data,
                context=context, description=description,
                priority=request.priority,
                case_type=request.case_type or None,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context, description=description,
                priority=request.priority, case_type=request.case_type or None,
                exec_mode=request.exec_mode,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)
        cases_list = generated_case if isinstance(generated_case, list) else [generated_case]
        response_data = [
            _format_case_response(
                generated_case=case_item, project_id=project_id,
                description=description, priority=request.priority,
                case_type=request.case_type or DEFAULT_AI_FALLBACK_CASE_TYPE,
            )
            for case_item in cases_list
        ]
        return create_response(data=response_data)
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        _raise_ai_error(e)
