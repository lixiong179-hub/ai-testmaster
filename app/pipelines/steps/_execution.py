from typing import Any, Dict, List, Optional, Tuple

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
    actionable_tasks: List[Dict[str, Any]],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
    history_cases: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], int]:
    generated_cases: List[Dict[str, Any]] = []
    failed_count = 0

    for task in actionable_tasks:
        task_type = task.get("task_type")
        try:
            if task_type == "create":
                cases = _generate_create_case(
                    ctx, task, prd_content, ui_description, ui_specs, has_ui,
                    history_cases=history_cases,
                )
            elif task_type == "modify":
                cases = _generate_modify_case(
                    ctx, task, prd_content, ui_description, ui_specs, has_ui,
                )
            elif task_type == "locator_fix":
                cases = _generate_locator_fix(
                    ctx, task, prd_content, ui_description, ui_specs, has_ui,
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
                        ctx=ctx, tp=tp_info, prd_content=prd_content,
                        ui_description=ui_description, ui_specs=ui_specs,
                        missing_types=coverage_gap,
                        existing_titles=[c.get("title", "") for c in enriched],
                        has_ui=has_ui,
                    )
                    if supplemental:
                        supplemental = _enrich_case_data_with_task(
                            supplemental, task, has_ui,
                        )
                        supplemental = _dedup_cases_by_title(
                            enriched + supplemental,
                        )[len(enriched):]
                        enriched.extend(supplemental)
                        coverage_gap = _check_type_coverage(enriched)

                generated_cases.append({
                    "task": task,
                    "status": "success",
                    "case_data": enriched,
                    "coverage_gap": coverage_gap,
                })
            else:
                failed_count += 1
                generated_cases.append({
                    "task": task,
                    "status": "failed",
                    "error": "生成结果为空",
                })
        except Exception as e:
            failed_count += 1
            logger.error(
                "用例生成失败 task_id={}: {}",
                task.get("task_id"), e,
            )
            generated_cases.append({
                "task": task,
                "status": "failed",
                "error": str(e),
            })

    return generated_cases, failed_count


def _execute_legacy(
    ctx: PipelineContext,
    aligned: Optional[Dict[str, Any]],
    signals: Optional[Dict[str, Any]],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> Tuple[List[Dict[str, Any]], int]:
    from app.pipelines.steps._parsing import _parse_case_response

    generated_cases: List[Dict[str, Any]] = []
    failed_count = 0

    if aligned:
        aligned_tps = aligned.get("aligned_testpoints", [])
    else:
        raw_tps = signals.get("test_points", []) if signals else []
        aligned_tps = [
            {
                "test_point": tp,
                "ui_match": None,
                "alignment_status": "no_ui_input",
            }
            for tp in raw_tps if tp is not None
        ]

    for entry in aligned_tps:
        tp = entry.get("test_point", {})
        try:
            prompt = _build_full_prompt(
                tp=tp,
                prd_content=prd_content,
                ui_description=ui_description,
                ui_specs=ui_specs,
            )

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
                        logger.warning(
                            "AI 返回空内容，tp_id={}，重试中",
                            tp.get("id"),
                        )
                        continue
                    break

                parsed = _parse_case_response(response.content)
                if parsed:
                    break

                last_error = "AI 响应解析失败"
                if attempt == 0:
                    logger.warning(
                        "AI 响应解析失败，tp_id={}，重试中",
                        tp.get("id"),
                    )

            if not parsed:
                failed_count += 1
                generated_cases.append({
                    "test_point": tp,
                    "status": "failed",
                    "error": (
                        f"{last_error}（重试后仍失败）"
                        if last_error else "生成失败"
                    ),
                })
                continue

            case_data = _enrich_case_data(parsed, tp, has_ui)
            case_data = _dedup_cases_by_title(case_data)
            coverage_gap = _check_type_coverage(case_data)
            if coverage_gap:
                logger.info(
                    "测试点 tp_id={} 缺少覆盖类型: {}，追加生成中",
                    tp.get("id"), coverage_gap,
                )
                supplemental = _generate_supplemental(
                    ctx=ctx, tp=tp, prd_content=prd_content,
                    ui_description=ui_description, ui_specs=ui_specs,
                    missing_types=coverage_gap,
                    existing_titles=[c.get("title", "") for c in case_data],
                    has_ui=has_ui,
                )
                if supplemental:
                    supplemental = _enrich_case_data(supplemental, tp, has_ui)
                    supplemental = _dedup_cases_by_title(
                        case_data + supplemental,
                    )[len(case_data):]
                    case_data.extend(supplemental)
                    coverage_gap = _check_type_coverage(case_data)

            generated_cases.append({
                "test_point": tp,
                "status": "success",
                "case_data": case_data,
                "degraded": degraded,
                "coverage_gap": coverage_gap,
            })
        except Exception as e:
            failed_count += 1
            logger.error(
                "用例生成失败 tp_id={}: {}",
                tp.get("id") if tp else "N/A", e,
            )
            generated_cases.append({
                "test_point": tp,
                "status": "failed",
                "error": str(e),
            })

    return generated_cases, failed_count
