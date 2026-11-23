import re
from typing import Any

_PRD_MAX_CHARS = 6000


def _build_full_prompt(
    tp: dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: list[dict[str, Any]],
    task_type: str | None = None,
    task_context: dict[str, Any] | None = None,
    history_cases: list[dict[str, Any]] | None = None,
    is_self_test: bool = False,
) -> str:
    filtered_prd = _filter_prd_by_testpoint(prd_content, tp)
    filtered_ui_specs = _filter_ui_specs_by_testpoint(ui_specs, tp)

    extra_context: dict[str, Any] = {}
    if task_type:
        extra_context["task_type"] = task_type
    if task_context:
        extra_context["task_context"] = task_context
    if history_cases and task_type == "create":
        extra_context["history_cases"] = history_cases[:20]

    if is_self_test:
        from app.services.prompt_builder.self_test_prompt import build_self_test_prompt

        return build_self_test_prompt(
            requirement_content=filtered_prd,
            ui_description=ui_description,
            module=tp.get("module", "未知模块"),
            function=tp.get("function", "未知功能"),
            point=tp.get("point", ""),
            priority=tp.get("priority", 3),
            ui_specs=filtered_ui_specs,
            history_cases=history_cases,
            extra_context=extra_context,
        )

    from app.services.prompt_builder import PromptBuilder

    return PromptBuilder.build_linear_prompt(
        requirement_content=filtered_prd,
        ui_description=ui_description,
        module=tp.get("module", "未知模块"),
        function=tp.get("function", "未知功能"),
        point=tp.get("point", ""),
        priority=tp.get("priority", 3),
        ui_specs=filtered_ui_specs,
        extra_context=extra_context,
    )


def _extract_tp_keywords(tp: dict[str, Any], fields: tuple[str, ...]) -> set[str]:
    """从测试点字段提取关键词（按分隔符切分，丢弃长度 < 2 的碎片）。"""
    keywords: set[str] = set()
    for field in fields:
        value = tp.get(field, "")
        if not value:
            continue
        for part in re.split(r"[/、，,\s]+", value):
            if len(part) >= 2:
                keywords.add(part.lower())
    return keywords


def _score_prd_paragraphs(prd_content: str, keywords: set[str]) -> list[tuple[int, int, str]]:
    """按关键词命中数给段落打分，命中多者优先、同分保持原文顺序。"""
    scored_paragraphs = []
    for idx, para in enumerate(re.split(r"\n{2,}", prd_content)):
        para_lower = para.lower()
        match_count = sum(1 for kw in keywords if kw in para_lower)
        scored_paragraphs.append((match_count, idx, para))
    scored_paragraphs.sort(key=lambda x: (-x[0], x[1]))
    return scored_paragraphs


def _select_paragraphs_by_budget(
    scored_paragraphs: list[tuple[int, int, str]], max_chars: int
) -> list[tuple[int, str]]:
    """按字符预算贪心取段落；末段剩余预算 > 100 时截断保留。"""
    selected: list[tuple[int, str]] = []
    total_chars = 0
    for _match_count, idx, para in scored_paragraphs:
        if total_chars + len(para) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 100:
                selected.append((idx, para[:remaining]))
            break
        selected.append((idx, para))
        total_chars += len(para)
        if total_chars >= max_chars:
            break
    return selected


def _filter_prd_by_testpoint(prd_content: str, tp: dict[str, Any]) -> str:
    if not prd_content or not prd_content.strip():
        return prd_content

    if len(prd_content) <= _PRD_MAX_CHARS:
        return prd_content

    keywords = _extract_tp_keywords(tp, ("module", "function", "point"))
    if not keywords:
        return prd_content[:_PRD_MAX_CHARS]

    selected = _select_paragraphs_by_budget(_score_prd_paragraphs(prd_content, keywords), _PRD_MAX_CHARS)
    if not selected:
        return prd_content[:_PRD_MAX_CHARS]

    selected.sort(key=lambda x: x[0])
    return "\n\n".join(text for _, text in selected)


def _spec_search_text(spec: dict[str, Any]) -> str:
    """拼装规格检索文本：screen_name + purpose + regions 键名。"""
    spec_text = spec.get("screen_name", "").lower()
    ui_spec = spec.get("ui_spec", {})
    if not isinstance(ui_spec, dict):
        return spec_text
    spec_text += " " + (ui_spec.get("purpose", "") or "").lower()
    regions = ui_spec.get("regions", {})
    if isinstance(regions, dict):
        spec_text += " " + " ".join(k.lower() for k in regions if k)
    return spec_text


def _split_specs_by_keywords(
    ui_specs: list[dict[str, Any]], keywords: set[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按关键词命中与否分成 (命中, 未命中) 两组，组内保持原序。"""
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for spec in ui_specs:
        spec_text = _spec_search_text(spec)
        if any(kw in spec_text for kw in keywords):
            matched.append(spec)
        else:
            unmatched.append(spec)
    return matched, unmatched


def _filter_ui_specs_by_testpoint(ui_specs: list[dict[str, Any]], tp: dict[str, Any]) -> list[dict[str, Any]]:
    if not ui_specs or len(ui_specs) <= 10:
        return ui_specs

    keywords = _extract_tp_keywords(tp, ("module", "function"))
    if not keywords:
        return ui_specs[:10]

    matched, unmatched = _split_specs_by_keywords(ui_specs, keywords)
    result = matched[:10]
    if len(result) < 10:
        result.extend(unmatched[: 10 - len(result)])
    return result
