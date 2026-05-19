from typing import Any, Dict, List

from loguru import logger

_TITLE_SIMILARITY_THRESHOLD = 0.6


def _jaccard_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    def _to_ngrams(text: str, n: int = 2) -> set:
        return {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}

    set_a = _to_ngrams(a)
    set_b = _to_ngrams(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _dedup_cases_by_title(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(cases) <= 1:
        return cases

    kept: List[Dict[str, Any]] = []
    for case in cases:
        title = case.get("title", "")
        is_dup = False
        for existing in kept:
            existing_title = existing.get("title", "")
            if _jaccard_similarity(title, existing_title) > _TITLE_SIMILARITY_THRESHOLD:
                is_dup = True
                logger.info(
                    "去重：标题相似度过高，丢弃 \"{}\"（与 \"{}\" 相似）",
                    title[:30], existing_title[:30],
                )
                break
        if not is_dup:
            kept.append(case)

    return kept


def _dedup_cases_global(
    generated_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    kept_titles: List[str] = []

    for entry in generated_cases:
        if entry.get("status") != "success":
            kept.append(entry)
            continue

        case_data = entry.get("case_data", [])
        filtered_cases: List[Dict[str, Any]] = []

        for case in case_data:
            title = case.get("title", "")
            is_dup = False
            for existing_title in kept_titles:
                if _jaccard_similarity(title, existing_title) > _TITLE_SIMILARITY_THRESHOLD:
                    is_dup = True
                    source = entry.get("test_point", {}).get("id") or \
                             entry.get("task", {}).get("task_id", "unknown")
                    logger.info(
                        "全局去重：丢弃 \"{}\"（来源: {}，与 \"{}\" 相似）",
                        title[:30], source, existing_title[:30],
                    )
                    break

            if not is_dup:
                filtered_cases.append(case)
                kept_titles.append(title)

        entry_copy = dict(entry)
        entry_copy["case_data"] = filtered_cases
        kept.append(entry_copy)

    return kept
