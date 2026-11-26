"""历史用例分类算法（R2-3：从 `endpoints/_history_asset_classification.py` 下沉）。

职责：把历史用例与系统用例做标题相似度匹配，输出「新增 / 更新 / 保留」分类结果。
无 DB 访问、无 HTTP 依赖，纯函数（相似度 = 0.4 × Jaccard + 0.6 × 公共前缀比）。
"""

from typing import Any

from app.schemas.history_asset import HistoryClassificationItem


def _title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_lower, b_lower = a.strip().lower(), b.strip().lower()
    if a_lower == b_lower:
        return 1.0
    a_set = set(a_lower)
    b_set = set(b_lower)
    if not a_set or not b_set:
        return 0.0
    jaccard = len(a_set & b_set) / len(a_set | b_set)
    max_len = max(len(a_lower), len(b_lower))
    if max_len == 0:
        return 0.0
    common_prefix = 0
    for i in range(min(len(a_lower), len(b_lower))):
        if a_lower[i] == b_lower[i]:
            common_prefix += 1
        else:
            break
    prefix_ratio = common_prefix / max_len
    return 0.4 * jaccard + 0.6 * prefix_ratio


def _pick_best_match(h_title: str, system_cases: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    """在系统用例中找标题最相似的一条。"""
    best_match: dict[str, Any] | None = None
    best_score = 0.0
    for s_case in system_cases:
        score = _title_similarity(h_title, s_case.get("title", ""))
        if score > best_score:
            best_score = score
            best_match = s_case
    return best_match, best_score


def _steps_differ(h_steps: list, s_steps: list) -> bool:
    if len(h_steps) != len(s_steps):
        return True
    return any(
        str(h_step.get("action", "")) != str(s_step.get("action", "")) for h_step, s_step in zip(h_steps, s_steps)
    )


def _build_content_diff_item(
    idx: int,
    h_case: dict[str, Any],
    best_match: dict[str, Any],
    best_score: float,
) -> HistoryClassificationItem:
    """标题高度匹配：内容一致则复用，否则给出字段级差异。"""
    h_steps = h_case.get("steps", [])
    s_steps = best_match.get("steps", [])
    h_er = h_case.get("expected_result", "")
    s_er = best_match.get("expected_result", "")
    steps_differ = _steps_differ(h_steps, s_steps)
    er_differ = h_er.strip() != s_er.strip()

    if not steps_differ and not er_differ:
        return HistoryClassificationItem(
            client_id=f"ha_case_{idx}",
            classification="REUSE_CASE",
            confidence=best_score,
            history_case=h_case,
            suggested_case=None,
            diff_fields=None,
            reason=f"与系统用例「{best_match.get('title', '')}」完全匹配，可复用",
            matched_system_case_id=best_match.get("case_id"),
        )

    diff_fields: dict[str, Any] = {}
    if steps_differ:
        diff_fields["steps"] = {"old": s_steps, "new": h_steps}
    if er_differ:
        diff_fields["expected_result"] = {"old": s_er, "new": h_er}
    return HistoryClassificationItem(
        client_id=f"ha_case_{idx}",
        classification="UPDATE_CASE",
        confidence=best_score,
        history_case=h_case,
        suggested_case=h_case,
        diff_fields=diff_fields,
        reason=f"与系统用例「{best_match.get('title', '')}」标题高度匹配但内容有差异",
        matched_system_case_id=best_match.get("case_id"),
    )


def _build_partial_match_item(
    idx: int,
    h_case: dict[str, Any],
    best_match: dict[str, Any],
    best_score: float,
) -> HistoryClassificationItem:
    """标题部分匹配：建议更新标题。"""
    return HistoryClassificationItem(
        client_id=f"ha_case_{idx}",
        classification="UPDATE_CASE",
        confidence=best_score,
        history_case=h_case,
        suggested_case=h_case,
        diff_fields={"title": {"old": best_match.get("title", ""), "new": h_case.get("title", "")}},
        reason=f"与系统用例「{best_match.get('title', '')}」标题部分匹配，建议更新",
        matched_system_case_id=best_match.get("case_id"),
    )


def _build_no_match_item(
    idx: int,
    h_case: dict[str, Any],
    requirement_keywords: list[str],
) -> HistoryClassificationItem:
    """无匹配系统用例：按需求关键词决定「建议新增」或「需人工确认」。"""
    h_title = h_case.get("title", "")
    matched_keywords = (
        [kw for kw in requirement_keywords if kw.lower() in h_title.lower()] if requirement_keywords else []
    )
    if not requirement_keywords:
        return HistoryClassificationItem(
            client_id=f"ha_case_{idx}",
            classification="NEW_CASE",
            confidence=0.6,
            history_case=h_case,
            suggested_case=h_case,
            diff_fields=None,
            reason="无匹配系统用例，建议新增",
        )
    if matched_keywords:
        return HistoryClassificationItem(
            client_id=f"ha_case_{idx}",
            classification="NEW_CASE",
            confidence=0.7,
            history_case=h_case,
            suggested_case=h_case,
            diff_fields=None,
            reason=f"无匹配系统用例，但标题包含需求关键词「{'、'.join(matched_keywords[:3])}」，建议新增",
        )
    return HistoryClassificationItem(
        client_id=f"ha_case_{idx}",
        classification="CONFIRM_REQUIRED",
        confidence=0.4,
        history_case=h_case,
        suggested_case=None,
        diff_fields=None,
        reason="无匹配系统用例且标题不含需求关键词，需人工确认是否新增",
    )


def _append_deprecated_system_cases(
    results: list[HistoryClassificationItem],
    system_cases: list[dict[str, Any]],
) -> None:
    """未被任何历史用例命中的系统用例标记为可能废弃。"""
    matched_system_ids = {item.matched_system_case_id for item in results if item.matched_system_case_id}
    for s_case in system_cases:
        s_id = s_case.get("case_id")
        if not s_id or s_id in matched_system_ids:
            continue
        results.append(
            HistoryClassificationItem(
                client_id=f"sys_case_{s_id}",
                classification="DEPRECATED_CASE",
                confidence=0.6,
                history_case=None,
                suggested_case=None,
                diff_fields=None,
                reason=f"系统用例「{s_case.get('title', '')}」在新资料中无匹配，可能废弃",
                matched_system_case_id=s_id,
            )
        )


def _classify_history_cases(
    history_cases: list[dict[str, Any]],
    system_cases: list[dict[str, Any]],
    requirement_keywords: list[str],
) -> list[HistoryClassificationItem]:
    results: list[HistoryClassificationItem] = []
    for idx, h_case in enumerate(history_cases):
        best_match, best_score = _pick_best_match(h_case.get("title", ""), system_cases)
        if best_score >= 0.9 and best_match:
            results.append(_build_content_diff_item(idx, h_case, best_match, best_score))
        elif best_score >= 0.5 and best_match:
            results.append(_build_partial_match_item(idx, h_case, best_match, best_score))
        else:
            results.append(_build_no_match_item(idx, h_case, requirement_keywords))

    _append_deprecated_system_cases(results, system_cases)
    return results
