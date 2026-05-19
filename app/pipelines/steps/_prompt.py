import re
from typing import Any, Dict, List, Optional

_PRD_MAX_CHARS = 6000


def _build_full_prompt(
    tp: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    task_type: Optional[str] = None,
    task_context: Optional[Dict[str, Any]] = None,
    history_cases: Optional[List[Dict[str, Any]]] = None,
) -> str:
    from app.services.prompt_builder import PromptBuilder

    filtered_prd = _filter_prd_by_testpoint(prd_content, tp)
    filtered_ui_specs = _filter_ui_specs_by_testpoint(ui_specs, tp)

    extra_context: Dict[str, Any] = {}
    if task_type:
        extra_context["task_type"] = task_type
    if task_context:
        extra_context["task_context"] = task_context
    if history_cases and task_type == "create":
        extra_context["history_cases"] = history_cases[:20]

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


def _filter_prd_by_testpoint(prd_content: str, tp: Dict[str, Any]) -> str:
    if not prd_content or not prd_content.strip():
        return prd_content

    if len(prd_content) <= _PRD_MAX_CHARS:
        return prd_content

    keywords = set()
    for field in ["module", "function", "point"]:
        val = tp.get(field, "")
        if val:
            for part in re.split(r'[/、，,\s]+', val):
                if len(part) >= 2:
                    keywords.add(part.lower())

    if not keywords:
        return prd_content[:_PRD_MAX_CHARS]

    paragraphs = re.split(r'\n{2,}', prd_content)

    scored_paragraphs = []
    for i, para in enumerate(paragraphs):
        para_lower = para.lower()
        match_count = sum(1 for kw in keywords if kw in para_lower)
        scored_paragraphs.append((match_count, i, para))

    scored_paragraphs.sort(key=lambda x: (-x[0], x[1]))

    selected = []
    total_chars = 0

    for match_count, idx, para in scored_paragraphs:
        if total_chars + len(para) > _PRD_MAX_CHARS:
            remaining = _PRD_MAX_CHARS - total_chars
            if remaining > 100:
                selected.append((idx, para[:remaining]))
                total_chars = _PRD_MAX_CHARS
            break

        selected.append((idx, para))
        total_chars += len(para)

        if total_chars >= _PRD_MAX_CHARS:
            break

    if not selected:
        return prd_content[:_PRD_MAX_CHARS]

    selected.sort(key=lambda x: x[0])
    ordered = [text for _, text in selected]

    return "\n\n".join(ordered)


def _filter_ui_specs_by_testpoint(
    ui_specs: List[Dict[str, Any]], tp: Dict[str, Any]
) -> List[Dict[str, Any]]:
    if not ui_specs or len(ui_specs) <= 10:
        return ui_specs

    keywords = set()
    for field in ["module", "function"]:
        val = tp.get(field, "")
        if val:
            for part in re.split(r'[/、，,\s]+', val):
                if len(part) >= 2:
                    keywords.add(part.lower())

    if not keywords:
        return ui_specs[:10]

    matched = []
    unmatched = []

    for spec in ui_specs:
        screen_name = spec.get("screen_name", "").lower()
        ui_spec = spec.get("ui_spec", {})
        spec_text = screen_name
        if isinstance(ui_spec, dict):
            spec_text += " " + (ui_spec.get("purpose", "") or "").lower()
            regions = ui_spec.get("regions", {})
            if isinstance(regions, dict):
                spec_text += " " + " ".join(k.lower() for k in regions.keys() if k)

        if any(kw in spec_text for kw in keywords):
            matched.append(spec)
        else:
            unmatched.append(spec)

    result = matched[:10]
    if len(result) < 10:
        result.extend(unmatched[:10 - len(result)])

    return result
