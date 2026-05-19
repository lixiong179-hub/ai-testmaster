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

    test_points = raw_signals.get("test_points", [])
    if test_points:
        tp_text = json.dumps(test_points, ensure_ascii=False, indent=2)
        parts.append(f"## 测试点\n{tp_text[:2000]}")

    if not parts:
        parts.append("（无明确变更信号）")

    return "\n\n".join(parts)


def _compute_scan_confidence(verdicts: List[BackwardCaseVerdict]) -> float:
    if not verdicts:
        return 0.0

    certain = sum(1 for v in verdicts if v.verdict != BackwardVerdict.UNCERTAIN)
    return certain / len(verdicts)
