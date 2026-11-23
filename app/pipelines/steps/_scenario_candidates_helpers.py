"""S7 ScenarioCandidateExtractor 辅助函数集合。

包含候选场景提取所需的工具方法：
    - 信号提取（PRD/UI/反推摘要/已有模块/已有用例摘要）
    - 候选解析与 JSON 容错提取
    - 候选校验与模块模糊匹配
    - UI 控件数量估算
    - 置信度计算
"""

import json
import re
from typing import Any

from app.pipelines.steps.reverse_infer._helpers import _CONFIDENCE_THRESHOLD


def _extract_prd(raw_signals: dict[str, Any]) -> str:
    prd = raw_signals.get("prd_content", "")
    if prd:
        return prd[:3000]
    return "（无 PRD 文档）"


def _extract_ui(raw_signals: dict[str, Any]) -> str:
    ui_specs = raw_signals.get("ui_specs", [])
    if not ui_specs:
        return "（无 UI 规格）"
    parts = []
    for spec in ui_specs[:5]:
        name = spec.get("screen_name", "未知屏幕")
        ui_spec = spec.get("ui_spec", "")
        if ui_spec:
            try:
                spec_text = json.dumps(ui_spec, ensure_ascii=False, indent=2)[:500]
            except (TypeError, ValueError):
                spec_text = str(ui_spec)[:500]
            parts.append(f"### {name}\n{spec_text}")
    return "\n\n".join(parts) if parts else "（无 UI 规格）"


def _dump_text(value: Any) -> str:
    """优先 JSON 序列化（中文不转义），失败降级为 str。"""
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(value)


def _extract_parsed_inferred(inferred: Any) -> dict[str, Any]:
    """取 inferred.parsed，非 dict 结构统一返回空字典。"""
    if not inferred or not isinstance(inferred, dict):
        return {}
    parsed = inferred.get("parsed") or {}
    return parsed if isinstance(parsed, dict) else {}


def _format_capability(cap: dict[str, Any]) -> str:
    """单条能力行：低置信度加 ⚠️ 与「待确认」标记。"""
    name = cap.get("name") or cap.get("key") or "未知能力"
    confidence = cap.get("confidence")
    is_numeric = isinstance(confidence, (int, float))
    if is_numeric and confidence < _CONFIDENCE_THRESHOLD:
        return f"- ⚠️{name}(置信度{confidence:.1f},待确认)"
    suffix = f"(置信度{confidence:.1f})" if is_numeric else ""
    return f"- {name}{suffix}"


def _render_capabilities(capabilities: Any) -> str:
    """渲染至多 10 条能力清单，非 dict 条目跳过。"""
    lines: list[str] = []
    for cap in capabilities[:10]:
        if isinstance(cap, dict):
            lines.append(_format_capability(cap))
    return "\n".join(lines)


def _render_parsed_inferred(parsed: dict[str, Any]) -> list[str]:
    """把 parsed 反推结果渲染为摘要 / 变更摘要 / 能力三段文本。"""
    parts: list[str] = []

    summary = parsed.get("analysis_summary") or parsed.get("summary")
    if summary:
        parts.append(f"反推摘要: {str(summary)[:1000]}")

    change_summary = parsed.get("change_summary")
    if change_summary:
        parts.append(f"变更摘要: {_dump_text(change_summary)[:1500]}")

    capabilities = parsed.get("inferred_capabilities") or parsed.get("capabilities") or []
    cap_text = _render_capabilities(capabilities)
    if cap_text:
        parts.append("反推能力:\n" + cap_text)

    return parts


def _extract_inferred(inferred: Any, raw_signals: dict[str, Any] | None = None) -> str:
    parts: list[str] = []
    raw_signals = raw_signals or {}

    change_notes = raw_signals.get("change_notes", "")
    if change_notes:
        parts.append(f"变更说明: {str(change_notes)[:1000]}")

    parts.extend(_render_parsed_inferred(_extract_parsed_inferred(inferred)))

    return "\n\n".join(parts) if parts else "（无反推摘要/变更线索）"


def _extract_existing_modules(fingerprints: Any) -> list[str]:
    if fingerprints is None:
        return []
    fps = fingerprints.get("fingerprints", [])
    modules = sorted({fp.get("module", "") for fp in fps if fp.get("module")})
    return modules


def _extract_existing_summaries(fingerprints: Any) -> str:
    if fingerprints is None:
        return "（无已有用例）"
    fps = fingerprints.get("fingerprints", [])
    if not fps:
        return "（无已有用例）"
    parts = []
    for fp in fps[:20]:
        parts.append(f"- [{fp.get('module', '?')}] {fp.get('summary', fp.get('title', '无标题'))}")
    return "\n".join(parts)


def _parse_candidates(content: str) -> list[dict[str, Any]] | None:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        data = _try_extract_json_array(content)
        if data is None:
            return None

    if isinstance(data, dict):
        for key in ("candidates", "scenarios", "items", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return None

    if isinstance(data, list):
        return data

    return None


def _try_extract_json_array(text: str) -> list[dict[str, Any]] | None:
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _validate_candidates(
    candidates: list[dict[str, Any]],
    existing_modules: list[str],
) -> list[dict[str, Any]]:
    validated = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        desc = (c.get("description") or "").strip()
        if not desc or len(desc) > 50:
            continue
        module = (c.get("module") or "").strip()
        if not module:
            continue
        if existing_modules and module not in existing_modules:
            closest = _find_closest_module(module, existing_modules)
            if closest:
                c["module_original"] = module
                c["module"] = closest
            else:
                c["module_original"] = module
        priority = c.get("priority", 3)
        if not isinstance(priority, int) or priority not in (1, 2, 3):
            priority = 3
        c["priority"] = priority
        reason = (c.get("reason") or "").strip()
        if not reason:
            reason = desc
        c["reason"] = reason[:100]
        validated.append(c)
    return validated


def _find_closest_module(target: str, modules: list[str]) -> str | None:
    target_lower = target.lower()
    for m in modules:
        if m.lower() == target_lower:
            return m
    for m in modules:
        if target_lower in m.lower() or m.lower() in target_lower:
            return m
    return None


def _estimate_ui_controls(raw_signals: dict[str, Any]) -> int:
    ui_specs = raw_signals.get("ui_specs", [])
    count = 0
    for spec in ui_specs:
        ui_spec = spec.get("ui_spec")
        if isinstance(ui_spec, dict):
            components = ui_spec.get("components", ui_spec.get("elements", []))
            if isinstance(components, (list, dict)):
                count += len(components)
        elif isinstance(ui_spec, list):
            count += len(ui_spec)
    return max(count, len(ui_specs))


def _compute_confidence(candidates: list[dict[str, Any]], coverage_ok: bool) -> float:
    if not candidates:
        return 0.0
    base = 0.7 if coverage_ok else 0.4
    high_priority = sum(1 for c in candidates if c.get("priority") == 1)
    bonus = min(0.2, high_priority * 0.05)
    return min(1.0, base + bonus)
