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
from typing import Any, Dict, List, Optional

from app.pipelines.steps.reverse_infer._helpers import _CONFIDENCE_THRESHOLD


def _extract_prd(raw_signals: Dict[str, Any]) -> str:
    prd = raw_signals.get("prd_content", "")
    if prd:
        return prd[:3000]
    return "（无 PRD 文档）"


def _extract_ui(raw_signals: Dict[str, Any]) -> str:
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


def _extract_inferred(inferred: Any, raw_signals: Optional[Dict[str, Any]] = None) -> str:
    parts = []
    raw_signals = raw_signals or {}

    change_notes = raw_signals.get("change_notes", "")
    if change_notes:
        parts.append(f"变更说明: {str(change_notes)[:1000]}")

    if inferred and isinstance(inferred, dict):
        parsed = inferred.get("parsed") or {}
        if isinstance(parsed, dict):
            summary = parsed.get("analysis_summary") or parsed.get("summary")
            if summary:
                parts.append(f"反推摘要: {str(summary)[:1000]}")

            change_summary = parsed.get("change_summary")
            if change_summary:
                try:
                    text = json.dumps(change_summary, ensure_ascii=False, indent=2)
                except (TypeError, ValueError):
                    text = str(change_summary)
                parts.append(f"变更摘要: {text[:1500]}")

            capabilities = parsed.get("inferred_capabilities") or parsed.get("capabilities") or []
            if capabilities:
                cap_lines = []
                for cap in capabilities[:10]:
                    if not isinstance(cap, dict):
                        continue
                    name = cap.get("name") or cap.get("key") or "未知能力"
                    conf = cap.get("confidence")
                    if isinstance(conf, (int, float)) and conf < _CONFIDENCE_THRESHOLD:
                        cap_lines.append(f"- ⚠️{name}(置信度{conf:.1f},待确认)")
                    else:
                        conf_str = f"(置信度{conf:.1f})" if isinstance(conf, (int, float)) else ""
                        cap_lines.append(f"- {name}{conf_str}")
                if cap_lines:
                    parts.append("反推能力:\n" + "\n".join(cap_lines))

    return "\n\n".join(parts) if parts else "（无反推摘要/变更线索）"


def _extract_existing_modules(fingerprints: Any) -> List[str]:
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


def _parse_candidates(content: str) -> Optional[List[Dict[str, Any]]]:
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


def _try_extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _validate_candidates(
    candidates: List[Dict[str, Any]],
    existing_modules: List[str],
) -> List[Dict[str, Any]]:
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


def _find_closest_module(target: str, modules: List[str]) -> Optional[str]:
    target_lower = target.lower()
    for m in modules:
        if m.lower() == target_lower:
            return m
    for m in modules:
        if target_lower in m.lower() or m.lower() in target_lower:
            return m
    return None


def _estimate_ui_controls(raw_signals: Dict[str, Any]) -> int:
    ui_specs = raw_signals.get("ui_specs", [])
    count = 0
    for spec in ui_specs:
        ui_spec = spec.get("ui_spec")
        if isinstance(ui_spec, dict):
            components = ui_spec.get("components", ui_spec.get("elements", []))
            if isinstance(components, list):
                count += len(components)
            elif isinstance(components, dict):
                count += len(components)
        elif isinstance(ui_spec, list):
            count += len(ui_spec)
    return max(count, len(ui_specs))


def _compute_confidence(candidates: List[Dict[str, Any]], coverage_ok: bool) -> float:
    if not candidates:
        return 0.0
    base = 0.7 if coverage_ok else 0.4
    high_priority = sum(1 for c in candidates if c.get("priority") == 1)
    bonus = min(0.2, high_priority * 0.05)
    return min(1.0, base + bonus)
