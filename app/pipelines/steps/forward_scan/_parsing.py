import json
import re
from typing import Any, Dict, List, Optional

from app.pipelines.steps.forward_scan._types import (
    ForwardVerdict,
    CoarseMatch,
)


def _parse_forward_response(
    raw: str,
    candidate: Dict[str, Any],
    top_matches: List[CoarseMatch],
) -> ForwardVerdict:
    data = _try_parse_json(raw)
    if data is None:
        return ForwardVerdict(
            candidate_index=-1,
            candidate_description=candidate.get("description", ""),
            label="NEW",
            matched_case_id=None,
            matched_title="",
            matched_similarity=top_matches[0].similarity if top_matches else 0.0,
            confidence=0.0,
            reason="LLM 响应 JSON 解析失败，降级为 NEW",
        )

    label = data.get("label", "NEW")
    if label not in ("EXISTING", "MODIFY", "NEW"):
        label = "NEW"

    matched_case_id = data.get("matched_case_id")
    matched_title = data.get("matched_title", "")

    if label in ("EXISTING", "MODIFY"):
        if not isinstance(matched_case_id, int) or isinstance(matched_case_id, bool) or not matched_title:
            label = "NEW"
            matched_case_id = None
            matched_title = ""
        elif not _is_valid_match(matched_case_id, top_matches):
            label = "NEW"
            matched_case_id = None
            matched_title = ""

    if label == "NEW":
        matched_case_id = None
        matched_title = ""

    confidence = data.get("confidence", 0.7)
    if not isinstance(confidence, (int, float)):
        confidence = 0.7
    confidence = max(0.0, min(1.0, float(confidence)))

    reason = data.get("reason", "")
    if not isinstance(reason, str) or not reason.strip():
        reason = candidate.get("description", "无理由")
    reason = reason[:100]

    return ForwardVerdict(
        candidate_index=-1,
        candidate_description=candidate.get("description", ""),
        label=label,
        matched_case_id=matched_case_id,
        matched_title=matched_title,
        matched_similarity=top_matches[0].similarity if top_matches else 0.0,
        confidence=confidence,
        reason=reason,
    )


def _try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _is_valid_match(case_id: int, top_matches: List[CoarseMatch]) -> bool:
    valid_ids = {m.case_id for m in top_matches}
    return case_id in valid_ids


def _verdict_to_dict(v: ForwardVerdict) -> Dict[str, Any]:
    return {
        "candidate_index": v.candidate_index,
        "candidate_description": v.candidate_description,
        "label": v.label,
        "matched_case_id": v.matched_case_id,
        "matched_title": v.matched_title,
        "matched_similarity": v.matched_similarity,
        "confidence": v.confidence,
        "reason": v.reason,
    }


def _compute_stats(verdicts: List[ForwardVerdict]) -> Dict[str, int]:
    existing = sum(1 for v in verdicts if v.label == "EXISTING")
    modify = sum(1 for v in verdicts if v.label == "MODIFY")
    new = sum(1 for v in verdicts if v.label == "NEW")
    return {"existing": existing, "modify": modify, "new": new}


def _compute_forward_confidence(verdicts: List[ForwardVerdict]) -> float:
    if not verdicts:
        return 0.0
    return sum(v.confidence for v in verdicts) / len(verdicts)
