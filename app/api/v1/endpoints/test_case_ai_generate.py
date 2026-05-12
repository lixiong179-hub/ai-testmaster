"""测试用例AI生成 - 生成端点模块

本模块定义AI生成测试用例的全部非流式生成端点，包含基础生成、增强生成、
上下文获取、单条生成、批量生成以及前置条件相关端点。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /ai-generate                  - AI基础生成测试用例
    - POST /ai-enhanced-generate         - AI增强模式生成
    - POST /generate-context             - 获取AI生成上下文
    - POST /generate-single              - 基于单个测试点生成
    - POST /ai-batch-generate            - AI批量生成（占位）
    - GET  /{case_id}/precondition-steps - 获取前置条件步骤
    - PUT  /{case_id}/precondition-steps - 批量保存前置条件步骤
    - POST /{case_id}/parse-precondition - AI解析前置条件

所有端点均需要Bearer令牌认证。
"""
import asyncio
import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
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
from app.core.constants import normalize_priority
from app.core.exception import create_response
from app.db.database import get_db
from app.models.project import Project
from app.models.test_case import TestCase, TestCasePreconditionStep, TestStep
from app.models.user import User
from app.schemas.test_case import (
    PreconditionStepBatchSave,
    PreconditionStepResponse,
)
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
    for exc_type, (http_code, detail) in _AI_ERROR_MAP.items():
        if isinstance(e, exc_type):
            raise HTTPException(status_code=http_code, detail=detail) from e
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AI生成失败"
    )


# ── AI基础生成端点 ────────────────────────────────────────


@router.post("/ai-generate")
async def ai_generate_test_case(
    request_data: AIGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI基础生成测试用例（写入数据库）。"""
    project_id = request_data.project_id
    description = request_data.description
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
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
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            steps_json=generated_case.get("steps", []),
            case_no=f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            generate_status=1,
            test_category=generated_case.get("test_category", None),
        )
        db.add(new_test_case)
        db.flush()
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
        db.commit()
        db.refresh(new_test_case)
        return create_response(data=build_test_case_response(new_test_case))
    except Exception as e:
        db.rollback()
        logger.error(f"AI生成测试用例失败: {e}")
        _raise_ai_error(e)


@router.post("/ai-enhanced-generate")
async def ai_enhanced_generate(
    request: AIGenerateEnhancedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI增强模式生成测试用例（不写入数据库）。

    支持 linear / graph 两种模式，对 AI 各类异常做细粒度分类返回不同 HTTP 状态码。
    """
    project_id = request.project_id
    description = request.description
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == current_user.id
    ).first()
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
        context = request.context or {}
        logger.info(
            f"AI生成增强模式 - 接收到的context: "
            f"{json.dumps(context, ensure_ascii=False, default=str)[:500]}"
        )
        if request.mode == "graph":
            prompt_data = _build_graph_prompt_data(
                flow_sort_data=request.flow_sort_data,
                context=context, description=description,
                priority=request.priority,
            )
            generated_case = await asyncio.to_thread(generate_test_case_enhanced, prompt_data)
        elif request.enhanced_mode:
            prompt_data = _build_linear_prompt_data(
                context=context, description=description,
                priority=request.priority, case_type=request.case_type or "manual",
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
                case_type=request.case_type or "manual",
            )
            for case_item in cases_list
        ]
        return create_response(data=response_data)
    except Exception as e:
        logger.error(f"AI增强模式生成测试用例失败: {e}")
        _raise_ai_error(e)


# ── 上下文与单条生成端点 ─────────────────────────────────


@router.post("/generate-context", response_model=dict)
async def get_generation_context(
    request: GenerateContextRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取AI生成测试用例的上下文信息。"""
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation_service import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=request.test_point_ids,
        force_refresh=request.force_refresh,
        test_point_page=request.test_point_page,
        test_point_page_size=request.test_point_page_size,
    )
    test_points_count = len(context.get("test_points", []))
    if test_points_count == 0:
        logger.warning(f"项目 {request.project_id} 没有找到测试点")

    # 查询历史参考用例（仅限本项目、非删除、active状态）
    # None = 前端未指定，自动查全部；[] = 前端明确不选任何用例；有值 = 按指定查询
    history_cases = []
    if request.history_case_ids is None:
        # 自动查全部 active 用例
        cases = db.query(TestCase).filter(
            TestCase.project_id == request.project_id,
            TestCase.is_deleted == False,
            TestCase.lifecycle_status == 'active',
        ).order_by(TestCase.id).all()
    elif len(request.history_case_ids) > 0:
        cases = db.query(TestCase).filter(
            TestCase.id.in_(request.history_case_ids),
            TestCase.project_id == request.project_id,
            TestCase.is_deleted == False,
            TestCase.lifecycle_status == 'active',
        ).all()
    else:
        # [] = 明确不选，不查任何用例
        cases = []

    # 统一摘要格式：每条用例给 title + summary + steps概要，控制单条长度
    for c in cases:
        steps = c.steps_json or []
        steps_summary = ""
        if isinstance(steps, list) and steps:
            # 只取前3步的 action，拼接为一句话
            actions = [s.get("action", s.get("description", "")) for s in steps[:3]]
            steps_summary = " → ".join(a for a in actions if a)
        history_cases.append({
            "id": c.id,
            "case_no": c.case_no,
            "module": c.module or "",
            "title": c.title,
            "summary": (c.summary or steps_summary or "")[:150],
            "expected_result": (c.expected_result or "")[:100],
        })

    project_config = {
        "project_name": project.name,
        "project_type": project.project_type or "web",
    }
    return create_response(data={
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
        "history_cases": history_cases,
        "message": f"获取成功：{test_points_count}个测试点",
    })


@router.post("/generate-single")
async def generate_single_test_case(
    request: SingleGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """基于单个测试点AI生成测试用例。"""
    project = db.query(Project).filter(
        Project.id == request.project_id, Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此项目"
        )
    from app.services.test_case_generation_service import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    context = await service.get_context_for_generation(
        project_id=request.project_id, user_id=current_user.id,
        requirement_file_ids=request.requirement_file_ids,
        ui_file_ids=request.ui_file_ids,
        ui_screen_ids=request.ui_screen_ids,
        test_point_ids=[request.test_point_id],
    )
    test_points = context.get("test_points", [])
    if not test_points:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"没有找到ID为{request.test_point_id}的测试点",
        )
    test_point = test_points[0]
    try:
        generated_case = await service.generate_test_case_for_point(
            context=context, test_point=test_point,
            project_id=request.project_id, case_type=request.case_type,
        )
        saved_case = await service._save_test_case(
            project_id=request.project_id,
            generated_case=generated_case, test_point=test_point,
        )
        steps_data = [
            {
                "step": step.get("step", "步骤"),
                "action": step.get("action", "执行"),
                "param": step.get("param", ""),
            }
            for step in generated_case.get("steps", [])
        ]
        return create_response(data={
            "id": saved_case.id, "project_id": saved_case.project_id,
            "case_no": saved_case.case_no, "module": saved_case.module,
            "title": saved_case.title, "precondition": saved_case.precondition,
            "test_data": generated_case.get("test_data", {}),
            "steps": steps_data, "expected_result": saved_case.expected_result,
            "priority": saved_case.priority, "case_type": saved_case.case_type,
            "generate_status": saved_case.generate_status,
            "test_point_id": test_point.get("id"),
            "message": "测试用例生成成功",
        })
    except Exception as e:
        db.rollback()
        logger.error(f"生成测试用例失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="生成失败"
        )


# ── 批量生成端点（占位） ─────────────────────────────────


@router.post("/ai-batch-generate")
async def ai_batch_generate_test_cases(
    request: BatchGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI批量生成测试用例 — 即将上线。
    
    请使用流式端点 /batch-generate/stream 或逐条调用 /generate-single。
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="批量生成功能即将上线，请使用 /batch-generate/stream 流式端点或 /generate-single 逐条生成",
    )


# ── 前置条件端点 ──────────────────────────────────────────


@router.get("/{case_id}/precondition-steps")
async def get_precondition_steps(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取前置条件步骤列表。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
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
    """批量保存前置条件步骤（覆盖式保存）。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
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
    """AI解析前置条件为可执行步骤。"""
    test_case = db.query(TestCase).join(Project).filter(
        TestCase.id == case_id, Project.user_id == current_user.id
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
