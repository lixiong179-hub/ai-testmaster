import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from loguru import logger

_CONFIDENCE_THRESHOLD: float = 0.7
_MAX_UI_CHARS: int = 4000
_MAX_FINGERPRINT_COUNT: int = 30


def _hash_dict(obj: Any) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception:
        return "error"


def _clamp_float(value: Any, low: float, high: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, v))


def _build_ui_text(
    ui_descriptions: List[Dict[str, Any]],
    ui_specs: List[Dict[str, Any]],
) -> str:
    parts: List[str] = []

    for desc in ui_descriptions[:20]:
        screen_name = desc.get("screen_name", "未知页面")
        description = desc.get("description", "")
        parts.append(f"- 页面: {screen_name}")
        if description:
            parts.append(f"  描述: {description}")

    if ui_specs:
        parts.append("\nUI 控件信息:")
        for spec in ui_specs[:20]:
            screen_name = spec.get("screen_name", "未知页面")
            ui_spec = spec.get("ui_spec", {})
            if isinstance(ui_spec, dict):
                components = ui_spec.get("components", [])
                elements = ui_spec.get("elements", [])
                all_items = list(components) + list(elements)
                if all_items:
                    item_names = [
                        (i.get("name") or i.get("type") or str(i))
                        for i in all_items[:10]
                        if isinstance(i, dict)
                    ]
                    parts.append(f"- [{screen_name}]: {', '.join(item_names[:10])}")
            elif isinstance(ui_spec, list):
                item_names = [
                    (i.get("name") or i.get("type") or str(i))
                    for i in ui_spec[:10]
                    if isinstance(i, dict)
                ]
                parts.append(f"- [{screen_name}]: {', '.join(item_names[:10])}")

    text = "\n".join(parts)
    if len(text) > _MAX_UI_CHARS:
        text = text[:_MAX_UI_CHARS] + "\n...(UI 信息过长已截断)"
    return text


def _build_fingerprint_text(fingerprints: Optional[Dict[str, Any]]) -> str:
    if not fingerprints:
        return "（无历史用例指纹）"

    items = fingerprints.get("fingerprints", [])
    if not isinstance(items, list) or len(items) == 0:
        return "（无历史用例指纹）"

    parts: List[str] = []
    seen_modules: set = set()

    for item in items[:_MAX_FINGERPRINT_COUNT]:
        if not isinstance(item, dict):
            continue
        module = str(item.get("module", ""))
        title = str(item.get("title", ""))
        summary = str(item.get("summary", ""))

        if module and module not in seen_modules:
            seen_modules.add(module)
            parts.append(f"\n### 模块: {module}")

        parts.append(f"- [{title}]: {summary[:120]}")

    text = "\n".join(parts)
    if len(text) > 3000:
        text = text[:3000] + "\n...(指纹信息过长已截断)"
    return text


def _parse_infer_response(content: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"inferred_capabilities": parsed, "overall_confidence": 0.5}
    except (json.JSONDecodeError, TypeError):
        pass

    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            parsed = json.loads(m.group())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _validate_new_project_output(parsed: Dict[str, Any]) -> tuple:
    if "overall_confidence" not in parsed:
        return False, "缺少 overall_confidence 字段"

    caps = parsed.get("inferred_capabilities", [])
    if not isinstance(caps, list):
        return False, "inferred_capabilities 必须是数组"

    for cap in caps:
        if not isinstance(cap, dict):
            return False, "inferred_capabilities 元素必须是对象"
        for field_name in ["name", "key", "description", "confidence"]:
            if field_name not in cap:
                return False, f"capability 缺少 {field_name} 字段"

    questions = parsed.get("uncertain_questions", [])
    if not isinstance(questions, list):
        return False, "uncertain_questions 必须是数组"

    return True, None


def _validate_old_project_output(parsed: Dict[str, Any]) -> tuple:
    if "overall_confidence" not in parsed:
        return False, "缺少 overall_confidence 字段"

    cs = parsed.get("change_summary")
    if cs is None or not isinstance(cs, dict):
        return False, "缺少 change_summary 或格式错误"

    for key in ["new_capabilities", "modified_capabilities", "removed_capabilities"]:
        value = cs.get(key, [])
        if not isinstance(value, list):
            return False, f"change_summary.{key} 必须是数组"

    questions = parsed.get("uncertain_questions", [])
    if not isinstance(questions, list):
        return False, "uncertain_questions 必须是数组"

    return True, None
