import json as _json
from typing import Any

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._signal_scoring import (
    _compute_analyzer_score,
    _compute_prior_score,
    _score_to_grade,
)


def _collect_d_grade_cases(
    generated_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    d_entries = []
    for entry in generated_cases:
        if entry.get("status") != "success":
            continue
        tp = entry.get("test_point", {})
        case_data_list = entry.get("case_data", [])
        d_cases = [c for c in case_data_list if c.get("prior_quality_grade") == "D"]
        if d_cases:
            d_score_idxs = [c.get("_d_score_idx") for c in d_cases if c.get("_d_score_idx") is not None]
            good_titles = [c.get("title", "") for c in case_data_list if c.get("prior_quality_grade") != "D"]
            d_entries.append(
                {
                    "test_point": tp,
                    "d_cases": d_cases,
                    "d_score_idxs": d_score_idxs,
                    "good_titles": good_titles,
                    "parent_entry": entry,
                }
            )
    return d_entries


_REGEN_PROMPT_HEADER: tuple[str, ...] = (
    "你是一名资深测试工程师。",
    "",
    "## 任务",
    "以下测试点的部分用例质量不达标（预期结果模糊、步骤不完整等），请重新生成这些用例。",
    "",
    "## 测试点信息：",
)

_REGEN_PROMPT_RULES: tuple[str, ...] = (
    "",
    "## 生成规则",
    "1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏",
    "2. 分支流程需标注触发条件，作为独立场景生成用例",
    "3. 异常流程需标注异常场景和预期错误提示",
    "4. 标题格式：「场景/条件」+「操作」+「验证重点」，15-40字，禁用模糊词",
    '5. 前置条件必须含"账号已登录"和网络环境，禁止依赖特定业务数据',
    "6. 步骤原子化可执行，每步必须有 action 和 expected_result",
    '7. 预期结果可量化判定，禁止"页面正常""功能正常"等模糊描述，必须含量化标记（具体文案、状态变化、数值）',
    "",
    "## 输出格式要求：",
    "严格按以下JSON数组格式输出，不要添加任何其他文字：",
    "",
    "[",
    "  {",
    '    "title": "用例标题（15-40字，要素明确）",',
    '    "module": "所属模块",',
    '    "precondition": "前置条件（含登录状态、网络环境）",',
    '    "steps": [',
    '      {"action": "具体操作步骤", "expected_result": "每步预期结果"}',
    "    ],",
    '    "expected_result": "整体预期结果",',
    '    "case_type": "用例类型（功能测试/边界测试/异常测试）",',
    '    "priority": 数字1-5,',
    '    "case_category": "正向/边界/异常",',
    '    "test_data": {}',
    "  }",
    "]",
)


def _build_regeneration_prompt(d_entry: dict[str, Any]) -> str:
    """拼装 D 级重生成 prompt：头部规则 + 测试点 + 待重生成标题 + 已合格标题 + 规则与格式。"""
    d_titles = [case.get("title", "未知") for case in d_entry["d_cases"]]
    good_titles = d_entry["good_titles"]
    good_titles_text = "、".join(f"「{t}」" for t in good_titles[:10]) if good_titles else "无"

    parts = list(_REGEN_PROMPT_HEADER)
    parts.append(_json.dumps(d_entry["test_point"], ensure_ascii=False))
    parts.append("")
    parts.append("## 需要重新生成的用例标题：")
    parts.extend(f"- {title}" for title in d_titles)
    parts.append("")
    parts.append("## 同测试点已合格用例标题（禁止重复）：")
    parts.append(good_titles_text)
    parts.extend(_REGEN_PROMPT_RULES)
    return "\n".join(parts)


def _replace_d_cases(parent_entry: dict[str, Any], regen_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """用重生成结果替换父条目中的 D 级用例，并清理评分期临时字段。"""
    new_case_data = [c for c in parent_entry.get("case_data", []) if c.get("prior_quality_grade") != "D"]
    new_case_data.extend(regen_cases)
    for case in new_case_data:
        case.pop("_d_score_idx", None)
    parent_entry["case_data"] = new_case_data
    return new_case_data


def _compute_regeneration_adjustment(new_case_data: list[dict[str, Any]], check_coverage: Any) -> float:
    """重生成后按覆盖度缺口均摊调整分（无缺口 +5，缺一条 -8）。"""
    if not new_case_data:
        return 0.0
    coverage_gap = check_coverage(new_case_data)
    coverage_adj = -8.0 * len(coverage_gap) if coverage_gap else 5.0
    return round(coverage_adj / len(new_case_data), 2)


def _score_regenerated_case(
    ctx: PipelineContext,
    regen_case: dict[str, Any],
    tp: dict[str, Any],
    signals: dict[str, Any],
    inferred: dict[str, Any],
    aligned: dict[str, Any],
    analyzer: Any,
    per_case_adj: float,
) -> dict[str, Any]:
    """给单条重生成用例打分并返回评分条目（同步回写用例字典）。"""
    score, grade, breakdown = _resolve_regenerated_score(ctx, regen_case, tp, signals, inferred, aligned, analyzer)

    if per_case_adj != 0.0:
        score = max(0.0, min(100.0, round(score + per_case_adj, 2)))
        breakdown["coverage_adjustment"] = per_case_adj
        grade = _score_to_grade(score)

    regen_case["prior_quality_score"] = score
    regen_case["prior_quality_grade"] = grade
    regen_case["lifecycle_status"] = "pending_review" if grade == "D" else "draft"
    if grade == "D":
        logger.info("R5: 重生成后仍D级，保持 pending_review: {}", regen_case.get("title", "")[:30])
    else:
        logger.info("R5: 重生成成功，{}级: {}", grade, regen_case.get("title", "")[:30])

    return {
        "test_point_id": tp.get("id"),
        "case_title": regen_case.get("title", ""),
        "score": score,
        "grade": grade,
        "breakdown": breakdown,
        "lifecycle_status": regen_case.get("lifecycle_status", "draft"),
        "regenerated": True,
    }


def _resolve_regenerated_score(
    ctx: PipelineContext,
    regen_case: dict[str, Any],
    tp: dict[str, Any],
    signals: dict[str, Any],
    inferred: dict[str, Any],
    aligned: dict[str, Any],
    analyzer: Any,
) -> tuple[float, str, dict[str, Any]]:
    """analyzer 优先，缺失或异常时降级到自研先验评分。"""
    if analyzer is not None:
        try:
            return _compute_analyzer_score(analyzer, regen_case)
        except Exception:
            pass
    return _compute_prior_score(regen_case, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db)


def _drop_stale_scores(scores: list[dict[str, Any]], d_score_idxs: list[Any]) -> None:
    """剔除已被重生成替换的旧评分条目（按 `_score_idx` 标记）。"""
    if not d_score_idxs:
        return
    stale = set(d_score_idxs)
    scores[:] = [s for s in scores if s.get("_score_idx") not in stale]


def _regenerate_single_entry(
    ctx: PipelineContext,
    d_entry: dict[str, Any],
    signals: dict[str, Any],
    inferred: dict[str, Any],
    aligned: dict[str, Any],
    scores: list[dict[str, Any]],
    analyzer: Any,
) -> None:
    """单个测试点的 D 级重生成：请求 → 解析 → 替换用例 → 重新评分。"""
    from app.pipelines.steps.case_generation import (
        _check_type_coverage,
        _enrich_case_data,
        _parse_case_response,
    )

    tp = d_entry["test_point"]
    response = ctx.ai_client.complete(
        prompt=_build_regeneration_prompt(d_entry),
        temperature=0.4,
        max_tokens=3000,
        metadata={
            "step_name": "quality_gate_regen",
            "test_point_id": tp.get("id"),
            "iteration_id": ctx.iteration_id,
            "regen_count": len(d_entry["d_cases"]),
        },
    )
    if not response.content:
        logger.warning("R5: D级用例重生成返回空，tp_id={}", tp.get("id"))
        return

    parsed = _parse_case_response(response.content)
    if not parsed:
        logger.warning("R5: D级用例重生成解析失败，tp_id={}", tp.get("id"))
        return

    regen_cases = _enrich_case_data(parsed, tp, signals.get("has_ui", False))
    new_case_data = _replace_d_cases(d_entry["parent_entry"], regen_cases)
    per_case_adj = _compute_regeneration_adjustment(new_case_data, _check_type_coverage)

    for regen_case in regen_cases:
        scores.append(_score_regenerated_case(ctx, regen_case, tp, signals, inferred, aligned, analyzer, per_case_adj))

    _drop_stale_scores(scores, d_entry["d_score_idxs"])


def _regenerate_d_cases(
    ctx: PipelineContext,
    d_entries: list[dict[str, Any]],
    signals: dict[str, Any],
    inferred: dict[str, Any],
    aligned: dict[str, Any],
    scores: list[dict[str, Any]],
    analyzer: Any = None,
) -> None:
    """对 D 级用例批量重生成；单个测试点异常只记日志，不影响其余测试点。"""
    for d_entry in d_entries:
        try:
            _regenerate_single_entry(ctx, d_entry, signals, inferred, aligned, scores, analyzer)
        except Exception as e:
            logger.warning("R5: D级用例重生成异常，tp_id={}: {}", d_entry.get("test_point", {}).get("id"), e)
