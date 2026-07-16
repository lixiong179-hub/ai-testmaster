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


def _classify_history_cases(
    history_cases: list[dict[str, Any]],
    system_cases: list[dict[str, Any]],
    requirement_keywords: list[str],
) -> list[HistoryClassificationItem]:
    results: list[HistoryClassificationItem] = []

    for idx, h_case in enumerate(history_cases):
        h_title = h_case.get("title", "")
        best_match: dict[str, Any] | None = None
        best_score = 0.0

        for s_case in system_cases:
            s_title = s_case.get("title", "")
            score = _title_similarity(h_title, s_title)
            if score > best_score:
                best_score = score
                best_match = s_case

        if best_score >= 0.9 and best_match:
            h_steps = h_case.get("steps", [])
            s_steps = best_match.get("steps", [])
            h_er = h_case.get("expected_result", "")
            s_er = best_match.get("expected_result", "")
            steps_differ = (
                len(h_steps) != len(s_steps)
                or any(
                    str(hs.get("action", "")) != str(ss.get("action", ""))
                    for hs, ss in zip(h_steps, s_steps)
                )
            )
            er_differ = h_er.strip() != s_er.strip()

            if steps_differ or er_differ:
                diff_fields: dict[str, Any] = {}
                if steps_differ:
                    diff_fields["steps"] = {"old": s_steps, "new": h_steps}
                if er_differ:
                    diff_fields["expected_result"] = {"old": s_er, "new": h_er}
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="UPDATE_CASE",
                    confidence=best_score,
                    history_case=h_case,
                    suggested_case=h_case,
                    diff_fields=diff_fields,
                    reason=f"与系统用例「{best_match.get('title', '')}」标题高度匹配但内容有差异",
                    matched_system_case_id=best_match.get("case_id"),
                ))
            else:
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="REUSE_CASE",
                    confidence=best_score,
                    history_case=h_case,
                    suggested_case=None,
                    diff_fields=None,
                    reason=f"与系统用例「{best_match.get('title', '')}」完全匹配，可复用",
                    matched_system_case_id=best_match.get("case_id"),
                ))
        elif best_score >= 0.5 and best_match:
            results.append(HistoryClassificationItem(
                client_id=f"ha_case_{idx}",
                classification="UPDATE_CASE",
                confidence=best_score,
                history_case=h_case,
                suggested_case=h_case,
                diff_fields={"title": {"old": best_match.get("title", ""), "new": h_title}},
                reason=f"与系统用例「{best_match.get('title', '')}」标题部分匹配，建议更新",
                matched_system_case_id=best_match.get("case_id"),
            ))
        else:
            if requirement_keywords:
                title_lower = h_title.lower()
                matched_kw = [kw for kw in requirement_keywords if kw.lower() in title_lower]
                if matched_kw:
                    results.append(HistoryClassificationItem(
                        client_id=f"ha_case_{idx}",
                        classification="NEW_CASE",
                        confidence=0.7,
                        history_case=h_case,
                        suggested_case=h_case,
                        diff_fields=None,
                        reason=f"无匹配系统用例，但标题包含需求关键词「{'、'.join(matched_kw[:3])}」，建议新增",
                    ))
                else:
                    results.append(HistoryClassificationItem(
                        client_id=f"ha_case_{idx}",
                        classification="CONFIRM_REQUIRED",
                        confidence=0.4,
                        history_case=h_case,
                        suggested_case=None,
                        diff_fields=None,
                        reason="无匹配系统用例且标题不含需求关键词，需人工确认是否新增",
                    ))
            else:
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="NEW_CASE",
                    confidence=0.6,
                    history_case=h_case,
                    suggested_case=h_case,
                    diff_fields=None,
                    reason="无匹配系统用例，建议新增",
                ))

    matched_system_ids: set[int] = set()
    for item in results:
        if item.matched_system_case_id:
            matched_system_ids.add(item.matched_system_case_id)

    for s_case in system_cases:
        s_id = s_case.get("case_id")
        if s_id and s_id not in matched_system_ids:
            results.append(HistoryClassificationItem(
                client_id=f"sys_case_{s_id}",
                classification="DEPRECATED_CASE",
                confidence=0.6,
                history_case=None,
                suggested_case=None,
                diff_fields=None,
                reason=f"系统用例「{s_case.get('title', '')}」在新资料中无匹配，可能废弃",
                matched_system_case_id=s_id,
            ))

    return results
