"""测试用例 AI 生成端点包。

路由处理函数已内联在本模块（原 `_generate.py` / `_context.py` /
`_precondition.py` 已合并）；历史用例检索与信任度评估等纯逻辑下沉至
`app.services.test_case_generation.history_context`。

`generate_test_case` / `generate_test_case_enhanced` / `parse_precondition_to_steps`
等符号在本模块命名空间可见，保持既有 patch 与 import 路径可用。
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_ai_helpers import (
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.api.v1.endpoints.test_case_ai_schemas import (
    AIGenerateEnhancedRequest,
    AIGenerateRequest,
    BatchGenerateRequest,
    GenerateContextRequest,
    SingleGenerateRequest,
)
from app.core.constants import normalize_priority, DEFAULT_AI_FALLBACK_CASE_TYPE
from app.core.exception import create_response
from app.db.database import PrimarySessionLocal, get_db
from app.models.project import Project
from app.models.test_case import TestCase, TestCasePreconditionStep, TestStep
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.test_case import (
    PreconditionStepBatchSave,
    PreconditionStepResponse,
)
from app.services.test_case_generation.history_context import DEFAULT_HISTORY_CASE_LIMIT
from app.utils.ai_client import (
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIResponseParseError,
    AIResponseFormatError,
    AIServiceError,
    generate_test_case,
    generate_test_case_enhanced,
    parse_precondition_to_steps,
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
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败")


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request_data.project_id
    description = request_data.description

    project_result = await asyncio.to_thread(
        db.execute,
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id),
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    try:
        generated_case = generate_test_case(description)
        priority_value = normalize_priority(generated_case.get("priority", "medium"))

        new_test_case = TestCase(
            project_id=project_id,
            title=generated_case.get("title") or "(无标题)",
            precondition=generated_case.get("precondition", ""),
            expected_result=generated_case.get("expected_result", ""),
            priority=priority_value,
            module="AI生成",
            case_type=generated_case.get("case_type")
            or generated_case.get("test_category")
            or DEFAULT_AI_FALLBACK_CASE_TYPE,
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None),
        )
        db.add(new_test_case)
        await asyncio.to_thread(db.flush)
        for i, step in enumerate(generated_case.get("steps", [])):
            action = step.get("action") or step.get("step") or f"步骤{i + 1}"
            expected_result = step.get("expected_result") or step.get("param") or "预期结果正常"
            test_step = TestStep(
                test_case_id=new_test_case.id,
                step_number=i + 1,
                action=action,
                expected_result=expected_result,
                action_type=step.get("action_type", ""),
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1,
                is_technical_view=1,
            )
            db.add(test_step)
        await asyncio.to_thread(db.commit)
        await asyncio.to_thread(db.refresh, new_test_case)
        data = build_test_case_response(new_test_case)
        return create_response(data=data)
    except Exception as e:
        await asyncio.to_thread(db.rollback)
        logger.error(f"AI生成测试用例失败: {e}")
        _raise_ai_error(e)


@router.post("/ai-enhanced-generate")
async def ai_enhanced_generate(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project_id = request.project_id
    description = request.description

    project_result = await asyncio.to_thread(
        db.execute,
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id),
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not description or len(description.strip()) < 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空且至少需要5个字符")
    if request.mode == "graph" and not request.flow_sort_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Graph模式下flow_sort_data不能为空")
    try:
        context = dict(request.context or {})
        if request.extra_requirements:
            context["extra_requirements"] = request.extra_requirements
        logger.info(f"AI生成增强模式 - 接收到的context: {json.dumps(context, ensure_ascii=False, default=str)[:500]}")

        has_requirement = bool(context.get("requirement_content", "").strip())
        has_ui = bool(context.get("ui_specs"))
        has_ui_reference = has_ui or bool(context.get("ui_descriptions"))
        has_flow = request.mode == "graph" and request.flow_sort_data and len(request.flow_sort_data.nodes) > 0
        if not has_requirement and not has_ui_reference and not has_flow:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="生成上下文为空：请上传需求文档、UI原型图或配置流程节点，确保AI有足够的输入信息",
            )

        if request.mode == "graph":
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request.flow_sort_data,
                context=context,
                description=description,
                priority=request.priority,
                case_type=request.case_type or None,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context,
                description=description,
                priority=request.priority,
                case_type=request.case_type or None,
                exec_mode=request.exec_mode,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        else:
            generated_case = await asyncio.to_thread(generate_test_case, description)
        cases_list = generated_case if isinstance(generated_case, list) else [generated_case]
        response_data = [
            _format_case_response(
                generated_case=case_item,
                project_id=project_id,
                description=description,
                priority=request.priority,
                case_type=request.case_type or DEFAULT_AI_FALLBACK_CASE_TYPE,
            )
            for case_item in cases_list
        ]
        return create_response(data=response_data)
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        _raise_ai_error(e)


@router.post("/generate-context", response_model=ApiResponse)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project_result = await asyncio.to_thread(
        db.execute,
        select(Project).where(Project.id == request.project_id, Project.user_id == current_user.id),
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import run_async_coro_in_thread

    # TestCaseGenerationService 内部使用 sync Session API，需独立 sync 会话
    # 性能优化：将整个 async service 调用放到独立线程，避免 sync_db.query() 阻塞主事件循环
    sync_db = PrimarySessionLocal()
    try:
        service = TestCaseGenerationService(sync_db)
        context = await run_async_coro_in_thread(
            service.get_context_for_generation(
                project_id=request.project_id,
                user_id=current_user.id,
                requirement_file_ids=request.requirement_file_ids,
                ui_file_ids=request.ui_file_ids,
                ui_screen_ids=request.ui_screen_ids,
                test_point_ids=request.test_point_ids,
                force_refresh=request.force_refresh,
                test_point_page=request.test_point_page,
                test_point_page_size=request.test_point_page_size,
            )
        )
        test_points_count = len(context.get("test_points", []))
        if test_points_count == 0:
            logger.warning(f"项目 {request.project_id} 没有找到测试点")

        service.enrich_context_with_trust_and_scoring(
            context,
            request.project_id,
            history_case_ids=request.history_case_ids,
            history_limit=DEFAULT_HISTORY_CASE_LIMIT,
        )

        project_config = {
            "project_name": project.name,
            "project_type": project.project_type or "web",
        }

        has_explicit_history = request.history_case_ids is not None and len(request.history_case_ids) > 0
        has_explicit_test_points = request.test_point_ids and len(request.test_point_ids) > 0
        if has_explicit_history and not has_explicit_test_points:
            context["test_points"] = []
            test_points_count = 0
            logger.info(f"项目 {request.project_id}: 历史用例查漏补缺模式，跳过测试点自动加载")

        return create_response(
            data={
                "requirement_content": context.get("requirement_content", ""),
                "requirement_length": len(context.get("requirement_content", "")),
                "ui_descriptions": context.get("ui_descriptions", []),
                "ui_specs": context.get("ui_specs", []),
                "ui_count": len(context.get("ui_descriptions", [])),
                "test_points": context.get("test_points", []),
                "test_point_count": test_points_count,
                "files_used": context.get("files_used", []),
                "warnings": context.get("warnings", []),
                "pagination": context.get("pagination", None),
                "project_config": project_config,
                "history_cases": context.get("history_cases", []),
                "context_stats": context.get("context_stats", {}),
                "evidence_refs": context.get("evidence_refs", {}),
                "message": f"获取成功：{test_points_count}个测试点",
            }
        )
    finally:
        sync_db.close()


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    project_result = await asyncio.to_thread(
        db.execute,
        select(Project).where(Project.id == request.project_id, Project.user_id == current_user.id),
    )
    project = project_result.scalars().first()
    if not project:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目")
    from app.services.test_case_generation import TestCaseGenerationService
    from app.utils.async_sync_bridge import run_async_coro_in_thread

    sync_db = PrimarySessionLocal()
    try:
        service = TestCaseGenerationService(sync_db)
        # 性能优化：将 service 调用放到独立线程，避免 sync_db.query() 阻塞事件循环
        context = await run_async_coro_in_thread(
            service.get_context_for_generation(
                project_id=request.project_id,
                user_id=current_user.id,
                requirement_file_ids=request.requirement_file_ids,
                ui_file_ids=request.ui_file_ids,
                ui_screen_ids=request.ui_screen_ids,
                test_point_ids=[request.test_point_id],
            )
        )
        service.enrich_context_with_trust_and_scoring(context, request.project_id)
        test_points = context.get("test_points", [])
        if not test_points:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"没有找到ID为{request.test_point_id}的测试点",
            )
        test_point = test_points[0]
        try:
            from app.utils.ai_concurrency import ai_generation_slot

            # AI 生成调用受模块级信号量保护，限制跨请求总并发（P-2 修复）
            async with ai_generation_slot():
                generated_case = await run_async_coro_in_thread(
                    service.generate_test_case_for_point(
                        context=context,
                        test_point=test_point,
                        project_id=request.project_id,
                        case_type=request.case_type,
                    )
                )
            saved_case = await run_async_coro_in_thread(
                service._save_test_case(
                    project_id=request.project_id,
                    generated_case=generated_case,
                    test_point=test_point,
                )
            )
            steps_data = [
                {
                    "step": step.get("step", "步骤"),
                    "action": step.get("action", "执行"),
                    "param": step.get("param", ""),
                }
                for step in generated_case.get("steps", [])
            ]
            return create_response(
                data={
                    "id": saved_case.id,
                    "project_id": saved_case.project_id,
                    "case_no": saved_case.case_no,
                    "module": saved_case.module,
                    "title": saved_case.title,
                    "precondition": saved_case.precondition,
                    "test_data": generated_case.get("test_data", {}),
                    "steps": steps_data,
                    "expected_result": saved_case.expected_result,
                    "priority": saved_case.priority,
                    "case_type": saved_case.case_type,
                    "generate_status": saved_case.generate_status,
                    "test_point_id": test_point.get("id"),
                    "context_stats": context.get("context_stats", {}),
                    "evidence_refs": context.get("evidence_refs", {}),
                    "warnings": context.get("warnings", []),
                    "message": "测试用例生成成功",
                }
            )
        except Exception as e:
            sync_db.rollback()
            logger.error(f"生成测试用例失败: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成失败")
    finally:
        sync_db.close()


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="批量生成功能即将上线，请使用 /batch-generate/stream 流式端点或 /generate-single 逐条生成",
    )


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test_case_result = await asyncio.to_thread(
        db.execute,
        select(TestCase)
        .join(Project)
        .where(TestCase.id == case_id, TestCase.is_deleted.is_(False), Project.user_id == current_user.id),
    )
    test_case = test_case_result.scalars().first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    steps_result = await asyncio.to_thread(
        db.execute,
        select(TestCasePreconditionStep)
        .where(TestCasePreconditionStep.test_case_id == case_id)
        .order_by(TestCasePreconditionStep.step_number),
    )
    steps = steps_result.scalars().all()
    data = [PreconditionStepResponse.model_validate(s) for s in steps]
    return create_response(data=data)


@router.put("/{case_id}/precondition-steps")
async def batch_save_precondition_steps(
    case_id: int,
    request: PreconditionStepBatchSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test_case_result = await asyncio.to_thread(
        db.execute,
        select(TestCase)
        .join(Project)
        .where(TestCase.id == case_id, TestCase.is_deleted.is_(False), Project.user_id == current_user.id),
    )
    test_case = test_case_result.scalars().first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    await asyncio.to_thread(
        db.execute,
        delete(TestCasePreconditionStep).where(TestCasePreconditionStep.test_case_id == case_id),
    )
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
            locator_status="pending",
        )
        db.add(step)
    await asyncio.to_thread(db.commit)
    steps_result = await asyncio.to_thread(
        db.execute,
        select(TestCasePreconditionStep)
        .where(TestCasePreconditionStep.test_case_id == case_id)
        .order_by(TestCasePreconditionStep.step_number),
    )
    steps = steps_result.scalars().all()
    data = [PreconditionStepResponse.model_validate(s) for s in steps]
    return create_response(data=data)


@router.post("/{case_id}/parse-precondition")
async def parse_precondition(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test_case_result = await asyncio.to_thread(
        db.execute,
        select(TestCase)
        .join(Project)
        .where(TestCase.id == case_id, TestCase.is_deleted.is_(False), Project.user_id == current_user.id),
    )
    test_case = test_case_result.scalars().first()
    if not test_case:
        raise HTTPException(status_code=404, detail="测试用例不存在")
    precondition = test_case.precondition
    if not precondition:
        return create_response(data=[], msg="前置条件为空，无需解析")
    try:
        steps = parse_precondition_to_steps(
            precondition=precondition,
        )
        if steps:
            await asyncio.to_thread(
                db.execute,
                delete(TestCasePreconditionStep).where(TestCasePreconditionStep.test_case_id == case_id),
            )
            for i, step_data in enumerate(steps):
                pc_step = TestCasePreconditionStep(
                    test_case_id=case_id,
                    step_number=step_data.get("step_number", i + 1),
                    action=step_data.get("action", ""),
                    expected_result=step_data.get("expected_result", ""),
                    action_type=step_data.get("action_type", ""),
                    input_value=step_data.get("input_value", ""),
                    target_element=step_data.get("target_element", ""),
                    has_locator=0,
                    locator_status="pending",
                )
                db.add(pc_step)
            await asyncio.to_thread(db.commit)
            saved_result = await asyncio.to_thread(
                db.execute,
                select(TestCasePreconditionStep)
                .where(TestCasePreconditionStep.test_case_id == case_id)
                .order_by(TestCasePreconditionStep.step_number),
            )
            saved_steps = saved_result.scalars().all()
            saved = [PreconditionStepResponse.model_validate(s) for s in saved_steps]
            return create_response(
                data=saved,
                msg=f"解析成功，生成 {len(steps)} 个步骤",
            )
        return create_response(data=[], msg="解析成功，但未生成步骤")
    except Exception as e:
        logger.error(f"AI解析前置条件失败: {e}")
        raise HTTPException(status_code=500, detail="AI解析前置条件失败")


__all__ = [
    "router",
    "ai_generate_test_case",
    "ai_enhanced_generate",
    "get_generation_context",
    "generate_single_test_case",
    "ai_batch_generate_test_cases",
    "get_precondition_steps",
    "batch_save_precondition_steps",
    "parse_precondition",
]
