import json
from typing import Any, Dict, List

from app.pipelines.schemas.backward_verdict import (
    BackwardCaseVerdict,
    BackwardVerdict,
)


def _extract_change_signals(raw_signals: Dict[str, Any]) -> str:
    parts = []
    prd = raw_signals.get("prd_content", "")
    if prd:
        parts.append(f"## PRD 变更\n{prd[:3000]}")

    change_notes = raw_signals.get("change_notes", "")
    if change_notes:
        parts.append(f"## 变更说明\n{str(change_notes)[:2000]}")

    ui_text = _extract_ui_change_text(raw_signals)
    if ui_text:
        parts.append(f"## UI 原型/页面信号\n{ui_text[:2000]}")

    test_points = raw_signals.get("test_points", [])
    if test_points:
        tp_text = json.dumps(test_points, ensure_ascii=False, indent=2)
        parts.append(f"## 测试点\n{tp_text[:2000]}")

    if not parts:
        parts.append("（无明确变更信号）")

    return "\n\n".join(parts)


def _extract_ui_change_text(raw_signals: Dict[str, Any]) -> str:
    ui_descriptions = raw_signals.get("ui_descriptions", []) or []
    ui_specs = raw_signals.get("ui_specs", []) or []
    parts = []

    for item in ui_descriptions[:5]:
        if not isinstance(item, dict):
            continue
        name = item.get("screen_name", "unknown")
        desc = item.get("description") or item.get("summary") or ""
        if desc:
            parts.append(f"- {name}: {desc}")

    for item in ui_specs[:3]:
        if not isinstance(item, dict):
            continue
        name = item.get("screen_name", "unknown")
        spec = item.get("ui_spec", "")
        if not spec:
            continue
        try:
            spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            spec_text = str(spec)
        parts.append(f"- {name} spec: {spec_text[:500]}")

    return "\n".join(parts)


def _compute_scan_confidence(verdicts: List[BackwardCaseVerdict]) -> float:
    if not verdicts:
        return 0.0

    certain = sum(1 for v in verdicts if v.verdict != BackwardVerdict.UNCERTAIN)
    return certain / len(verdicts)
