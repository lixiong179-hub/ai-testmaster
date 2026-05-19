import json as _json
from typing import Any, Dict, List

from loguru import logger

from app.pipelines.context import PipelineContext
from app.pipelines.steps._signal_scoring import (
    _compute_analyzer_score,
    _compute_prior_score,
    _score_to_grade,
)


def _collect_d_grade_cases(
    generated_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    d_entries = []
    for entry in generated_cases:
        if entry.get("status") != "success":
            continue
        tp = entry.get("test_point", {})
        case_data_list = entry.get("case_data", [])
        d_cases = [c for c in case_data_list if c.get("prior_quality_grade") == "D"]
        if d_cases:
            d_score_idxs = [c.get("_d_score_idx") for c in d_cases if c.get("_d_score_idx") is not None]
            good_titles = [
                c.get("title", "") for c in case_data_list
                if c.get("prior_quality_grade") != "D"
            ]
            d_entries.append({
                "test_point": tp,
                "d_cases": d_cases,
                "d_score_idxs": d_score_idxs,
                "good_titles": good_titles,
                "parent_entry": entry,
            })
    return d_entries


def _regenerate_d_cases(
    ctx: PipelineContext,
    d_entries: List[Dict[str, Any]],
    signals: Dict[str, Any],
    inferred: Dict[str, Any],
    aligned: Dict[str, Any],
    scores: List[Dict[str, Any]],
    analyzer: Any = None,
) -> None:
    from app.pipelines.steps.case_generation import (
        _parse_case_response, _enrich_case_data, _check_type_coverage,
    )

    for d_entry in d_entries:
        tp = d_entry["test_point"]
        d_cases = d_entry["d_cases"]
        d_score_idxs = set(d_entry["d_score_idxs"])
        good_titles = d_entry["good_titles"]
        parent_entry = d_entry["parent_entry"]

        good_titles_text = "、".join(f"「{t}」" for t in good_titles[:10]) if good_titles else "无"
        d_titles = [c.get("title", "未知") for c in d_cases]

        regen_parts: List[str] = []
        regen_parts.append("你是一名资深测试工程师。")
        regen_parts.append("")
        regen_parts.append("## 任务")
        regen_parts.append("以下测试点的部分用例质量不达标（预期结果模糊、步骤不完整等），请重新生成这些用例。")
        regen_parts.append("")
        regen_parts.append("## 测试点信息：")
        regen_parts.append(_json.dumps(tp, ensure_ascii=False))
        regen_parts.append("")
        regen_parts.append("## 需要重新生成的用例标题：")
        for t in d_titles:
            regen_parts.append(f"- {t}")
        regen_parts.append("")
        regen_parts.append("## 同测试点已合格用例标题（禁止重复）：")
        regen_parts.append(good_titles_text)
        regen_parts.append("")
        regen_parts.append("## 生成规则")
        regen_parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        regen_parts.append("2. 分支流程需标注触发条件，作为独立场景生成用例")
        regen_parts.append("3. 异常流程需标注异常场景和预期错误提示")
        regen_parts.append("4. 标题格式：「场景/条件」+「操作」+「验证重点」，15-40字，禁用模糊词")
        regen_parts.append("5. 前置条件必须含\"账号已登录\"和网络环境，禁止依赖特定业务数据")
        regen_parts.append("6. 步骤原子化可执行，每步必须有 action 和 expected_result")
        regen_parts.append("7. 预期结果可量化判定，禁止\"页面正常\"\"功能正常\"等模糊描述，必须含量化标记（具体文案、状态变化、数值）")
        regen_parts.append("")
        regen_parts.append("## 输出格式要求：")
        regen_parts.append("严格按以下JSON数组格式输出，不要添加任何其他文字：")
        regen_parts.append("")
        regen_parts.append("[")
        regen_parts.append("  {")
        regen_parts.append('    "title": "用例标题（15-40字，要素明确）",')
        regen_parts.append('    "module": "所属模块",')
        regen_parts.append('    "precondition": "前置条件（含登录状态、网络环境）",')
        regen_parts.append('    "steps": [')
        regen_parts.append('      {"action": "具体操作步骤", "expected_result": "每步预期结果"}')
        regen_parts.append('    ],')
        regen_parts.append('    "expected_result": "整体预期结果",')
        regen_parts.append('    "case_type": "用例类型（功能测试/边界测试/异常测试）",')
        regen_parts.append('    "priority": 数字1-5,')
        regen_parts.append('    "case_category": "正向/边界/异常",')
        regen_parts.append('    "test_data": {}')
        regen_parts.append('  }')
        regen_parts.append(']')

        regen_prompt = "\n".join(regen_parts)

        try:
            response = ctx.ai_client.complete(
                prompt=regen_prompt,
                temperature=0.4,
                max_tokens=3000,
                metadata={
                    "step_name": "quality_gate_regen",
                    "test_point_id": tp.get("id"),
                    "iteration_id": ctx.iteration_id,
                    "regen_count": len(d_cases),
                },
            )
            if not response.content:
                logger.warning("R5: D级用例重生成返回空，tp_id={}", tp.get("id"))
                continue

            has_ui = signals.get("has_ui", False)
            parsed = _parse_case_response(response.content)
            if not parsed:
                logger.warning("R5: D级用例重生成解析失败，tp_id={}", tp.get("id"))
                continue

            regen_cases = _enrich_case_data(parsed, tp, has_ui)

            old_case_data = parent_entry.get("case_data", [])
            new_case_data = [c for c in old_case_data if c.get("prior_quality_grade") != "D"]
            new_case_data.extend(regen_cases)
            for c in new_case_data:
                c.pop("_d_score_idx", None)
            parent_entry["case_data"] = new_case_data

            regen_coverage_gap = _check_type_coverage(new_case_data)
            if regen_coverage_gap:
                regen_coverage_adj = -8.0 * len(regen_coverage_gap)
            else:
                regen_coverage_adj = 5.0
            per_regen_case_adj = round(regen_coverage_adj / len(new_case_data), 2) if new_case_data else 0.0

            for regen_case in regen_cases:
                if analyzer is not None:
                    try:
                        score, grade, breakdown = _compute_analyzer_score(analyzer, regen_case)
                    except Exception:
                        score, grade, breakdown = _compute_prior_score(
                            regen_case, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                        )
                else:
                    score, grade, breakdown = _compute_prior_score(
                        regen_case, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                    )

                if per_regen_case_adj != 0.0:
                    score = max(0.0, min(100.0, round(score + per_regen_case_adj, 2)))
                    breakdown["coverage_adjustment"] = per_regen_case_adj
                    grade = _score_to_grade(score)

                regen_case["prior_quality_score"] = score
                regen_case["prior_quality_grade"] = grade
                regen_case["lifecycle_status"] = "draft"
                if grade == "D":
                    regen_case["lifecycle_status"] = "pending_review"
                    logger.info("R5: 重生成后仍D级，保持 pending_review: {}", regen_case.get("title", "")[:30])
                else:
                    logger.info("R5: 重生成成功，{}级: {}", grade, regen_case.get("title", "")[:30])

                scores.append({
                    "test_point_id": tp.get("id"),
                    "case_title": regen_case.get("title", ""),
                    "score": score,
                    "grade": grade,
                    "breakdown": breakdown,
                    "lifecycle_status": regen_case.get("lifecycle_status", "draft"),
                    "regenerated": True,
                })

            if d_score_idxs:
                scores[:] = [
                    s for s in scores
                    if s.get("_score_idx") not in d_score_idxs
                ]

        except Exception as e:
            logger.warning("R5: D级用例重生成异常，tp_id={}: {}", tp.get("id"), e)
