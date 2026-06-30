import hashlib
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


def _compute_step_hash(case: Dict[str, Any]) -> str:
    """计算用例步骤序列的哈希值。

    业务原因：标题不同但步骤完全相同的用例是冗余的，
    通过 action+expected_result 拼接后 SHA256 计算哈希，识别步骤级重复。
    步骤序号不参与哈希计算，序号不同但内容相同视为重复。

    哈希输入使用长度前缀编码（``{len(action)}:{action}|{len(expected)}:{expected}``），
    避免 action/expected 文本内含 ``|`` 或 ``\\n`` 时的拼接歧义导致碰撞。
    """
    steps = case.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return ""

    step_parts: List[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action", "")).strip()
        expected = str(step.get("expected_result", "")).strip()
        # 长度前缀编码：消除分隔符在内容内出现时的歧义
        step_parts.append(f"{len(action)}:{action}|{len(expected)}:{expected}")

    if not step_parts:
        return ""

    raw = "\n".join(step_parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dedup_cases_global(
    generated_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    kept: List[Dict[str, Any]] = []
    kept_titles: List[str] = []
    seen_step_hashes: set = set()

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

            if is_dup:
                continue

            # 标题去重通过后，追加步骤哈希去重
            step_hash = _compute_step_hash(case)
            if step_hash and step_hash in seen_step_hashes:
                source = entry.get("test_point", {}).get("id") or \
                         entry.get("task", {}).get("task_id", "unknown")
                logger.info(
                    "全局步骤去重：丢弃 \"{}\"（来源: {}，步骤序列重复）",
                    title[:30], source,
                )
                continue

            filtered_cases.append(case)
            kept_titles.append(title)
            if step_hash:
                seen_step_hashes.add(step_hash)

        entry_copy = dict(entry)
        entry_copy["case_data"] = filtered_cases
        kept.append(entry_copy)

    return kept
