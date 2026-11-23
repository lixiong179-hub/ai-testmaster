from typing import Any

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._parsing import _enrich_case_data, _enrich_case_data_with_task
from app.pipelines.steps._dedup import _dedup_cases_by_title
from app.pipelines.steps._case_coverage import _check_type_coverage, _generate_supplemental
from app.pipelines.steps._prompt import _build_full_prompt
from app.pipelines.steps._task_generators import (
    _generate_create_case,
    _generate_modify_case,
    _generate_locator_fix,
)


def _execute_task_based(
    ctx: PipelineContext,
    actionable_tasks: list[dict[str, Any]],
    prd_content: str,
    ui_description: str,
    ui_specs: list[dict[str, Any]],
    has_ui: bool,
    history_cases: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    generated_cases: list[dict[str, Any]] = []
    failed_count = 0

    for task in actionable_tasks:
        task_type = task.get("task_type")
        try:
            if task_type == "create":
                cases = _generate_create_case(
                    ctx,
                    task,
                    prd_content,
                    ui_description,
                    ui_specs,
                    has_ui,
                    history_cases=history_cases,
                )
            elif task_type == "modify":
                cases = _generate_modify_case(
                    ctx,
                    task,
                    prd_content,
                    ui_description,
                    ui_specs,
                    has_ui,
                )
            elif task_type == "locator_fix":
                cases = _generate_locator_fix(
                    ctx,
                    task,
                    prd_content,
                    ui_description,
                    ui_specs,
                    has_ui,
                )
            else:
                continue

            if cases:
                enriched = _enrich_case_data_with_task(cases, task, has_ui)
                enriched = _dedup_cases_by_title(enriched)
                coverage_gap = _check_type_coverage(enriched)
                if coverage_gap:
                    tp_info = {
                        "id": task.get("task_id"),
                        "module": task.get("module", ""),
                        "function": task.get("function", ""),
                        "point": task.get("candidate_description", ""),
                        "priority": task.get("candidate_priority", 3),
                    }
                    supplemental = _generate_supplemental(
                        ctx=ctx,
                        tp=tp_info,
                        prd_content=prd_content,
                        ui_description=ui_description,
                        ui_specs=ui_specs,
                        missing_types=coverage_gap,
                        existing_titles=[c.get("title", "") for c in enriched],
                        has_ui=has_ui,
                    )
                    if supplemental:
                        supplemental = _enrich_case_data_with_task(
                            supplemental,
                            task,
                            has_ui,
                        )
                        supplemental = _dedup_cases_by_title(
                            enriched + supplemental,
                        )[len(enriched) :]
                        enriched.extend(supplemental)
                        coverage_gap = _check_type_coverage(enriched)

                generated_cases.append(
                    {
                        "task": task,
                        "status": "success",
                        "case_data": enriched,
                        "coverage_gap": coverage_gap,
                    }
                )
            else:
                failed_count += 1
                generated_cases.append(
                    {
                        "task": task,
                        "status": "failed",
                        "error": "生成结果为空",
                    }
                )
        except Exception as e:
            failed_count += 1
            logger.error(
                "用例生成失败 task_id={}: {}",
                task.get("task_id"),
                e,
            )
            generated_cases.append(
                {
                    "task": task,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return generated_cases, failed_count


def _resolve_aligned_testpoints(aligned: dict[str, Any] | None, signals: dict[str, Any] | None) -> list[dict[str, Any]]:
    """优先用对齐产物；缺失时把原始测试点包装成「无 UI 输入」的对齐结构。"""
    if aligned:
        return aligned.get("aligned_testpoints", [])

    raw_tps = signals.get("test_points", []) if signals else []
    return [{"test_point": tp, "ui_match": None, "alignment_status": "no_ui_input"} for tp in raw_tps if tp is not None]


def _request_case_response(
    ctx: PipelineContext, tp: dict[str, Any], prompt: str, parse_response: Any
) -> tuple[list[dict[str, Any]] | None, bool, str]:
    """请求 AI 并解析用例（最多 2 轮）；返回 (解析结果, 是否降级, 最后一次错误)。"""
    parsed = None
    degraded = False
    last_error = ""

    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=5000,
            metadata={
                "step_name": "case_generation",
                "test_point_id": tp.get("id"),
                "iteration_id": ctx.iteration_id,
                "attempt": attempt + 1,
            },
        )
        degraded = degraded or response.degraded

        if not response.content:
            last_error = "AI 返回空内容"
            if attempt == 0:
                logger.warning("AI 返回空内容，tp_id={}，重试中", tp.get("id"))
                continue
            break

        parsed = parse_response(response.content)
        if parsed:
            break

        last_error = "AI 响应解析失败"
        if attempt == 0:
            logger.warning("AI 响应解析失败，tp_id={}，重试中", tp.get("id"))

    return parsed, degraded, last_error


def _fill_coverage_gap(
    ctx: PipelineContext,
    tp: dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: list[dict[str, Any]],
    has_ui: bool,
    case_data: list[dict[str, Any]],
) -> list[str]:
    """覆盖率缺口补生成；返回补生成后的最新缺口列表。"""
    coverage_gap = _check_type_coverage(case_data)
    if not coverage_gap:
        return coverage_gap

    logger.info("测试点 tp_id={} 缺少覆盖类型: {}，追加生成中", tp.get("id"), coverage_gap)
    supplemental = _generate_supplemental(
        ctx=ctx,
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        missing_types=coverage_gap,
        existing_titles=[c.get("title", "") for c in case_data],
        has_ui=has_ui,
    )
    if not supplemental:
        return coverage_gap

    supplemental = _enrich_case_data(supplemental, tp, has_ui)
    supplemental = _dedup_cases_by_title(case_data + supplemental)[len(case_data) :]
    case_data.extend(supplemental)
    return _check_type_coverage(case_data)


def _generate_case_entry(
    ctx: PipelineContext,
    tp: dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: list[dict[str, Any]],
    has_ui: bool,
    parse_response: Any,
) -> dict[str, Any]:
    """单测试点生成入口：构造 prompt → 请求解析 → 补覆盖 → 组装结果条目。"""
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
    )
    parsed, degraded, last_error = _request_case_response(ctx, tp, prompt, parse_response)
    if not parsed:
        error = f"{last_error}（重试后仍失败）" if last_error else "生成失败"
        return {"test_point": tp, "status": "failed", "error": error}

    case_data = _dedup_cases_by_title(_enrich_case_data(parsed, tp, has_ui))
    coverage_gap = _fill_coverage_gap(ctx, tp, prd_content, ui_description, ui_specs, has_ui, case_data)
    return {
        "test_point": tp,
        "status": "success",
        "case_data": case_data,
        "degraded": degraded,
        "coverage_gap": coverage_gap,
    }


def _execute_legacy(
    ctx: PipelineContext,
    aligned: dict[str, Any] | None,
    signals: dict[str, Any] | None,
    prd_content: str,
    ui_description: str,
    ui_specs: list[dict[str, Any]],
    has_ui: bool,
) -> tuple[list[dict[str, Any]], int]:
    from app.pipelines.steps._parsing import _parse_case_response

    generated_cases: list[dict[str, Any]] = []
    failed_count = 0

    for entry in _resolve_aligned_testpoints(aligned, signals):
        tp = entry.get("test_point", {})
        try:
            case_entry = _generate_case_entry(
                ctx, tp, prd_content, ui_description, ui_specs, has_ui, _parse_case_response
            )
        except Exception as e:
            logger.error("用例生成失败 tp_id={}: {}", tp.get("id") if tp else "N/A", e)
            case_entry = {"test_point": tp, "status": "failed", "error": str(e)}

        if case_entry["status"] == "failed":
            failed_count += 1
        generated_cases.append(case_entry)

    return generated_cases, failed_count
