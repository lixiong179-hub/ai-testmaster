from typing import Any, Dict, List, Optional

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._prompt import _build_full_prompt
from app.pipelines.steps._parsing import _parse_case_response


def _generate_create_case(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
    history_cases: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[Dict[str, Any]]]:
    tp = {
        "module": task.get("candidate_module", task.get("module", "")),
        "function": task.get("candidate_description", ""),
        "point": task.get("candidate_description", ""),
        "priority": task.get("candidate_priority", 3),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="create",
        task_context={
            "candidate_description": task.get("candidate_description", ""),
            "candidate_reason": task.get("candidate_reason", ""),
        },
        history_cases=history_cases,
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=5000,
            metadata={
                "step_name": "case_generation_create",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed


def _generate_modify_case(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    original = task.get("original_case", {})
    tp = {
        "module": original.get("module", task.get("module", "")),
        "function": task.get("modification_hint", ""),
        "point": original.get("title", task.get("candidate_description", "")),
        "priority": task.get("candidate_priority", original.get("priority", 3)),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="modify",
        task_context={
            "original_case": original,
            "modification_hint": task.get("modification_hint", ""),
            "need_locator_fix": task.get("need_locator_fix", False),
        },
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=5000,
            metadata={
                "step_name": "case_generation_modify",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed


def _generate_locator_fix(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    original = task.get("original_case", {})
    tp = {
        "module": original.get("module", task.get("module", "")),
        "function": "定位器修复",
        "point": original.get("title", ""),
        "priority": original.get("priority", 3),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="locator_fix",
        task_context={
            "original_case": original,
            "locator_hint": task.get(
                "locator_hint",
                "UI元素定位器已变更，请使用新UI描述中的元素名称",
            ),
        },
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.2,
            max_tokens=4000,
            metadata={
                "step_name": "case_generation_locator",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed
