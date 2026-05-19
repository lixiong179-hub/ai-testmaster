from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Literal, Optional


class MergedAction(str, Enum):
    KEEP = "keep"
    NEEDS_MODIFY = "needs_modify"
    LOCATOR_BROKEN = "locator_broken"
    LOCATOR_AND_MODIFY = "locator_and_modify"
    DEPRECATE = "deprecate"
    ADD_NEW = "add_new"
    CONFLICT = "conflict"
    PENDING_REVIEW = "pending_review"


BackwardVerdict = Literal["VALID", "LOCATOR_ONLY", "NEEDS_MODIFY", "DEPRECATED", "UNCERTAIN"]
ForwardLabel = Optional[Literal["EXISTING", "MODIFY"]]

MERGE_MATRIX: Final[Dict[BackwardVerdict, Dict[ForwardLabel, MergedAction]]] = {
    "VALID": {
        "EXISTING": MergedAction.KEEP,
        "MODIFY": MergedAction.NEEDS_MODIFY,
        None: MergedAction.KEEP,
    },
    "LOCATOR_ONLY": {
        "EXISTING": MergedAction.LOCATOR_BROKEN,
        "MODIFY": MergedAction.LOCATOR_AND_MODIFY,
        None: MergedAction.LOCATOR_BROKEN,
    },
    "NEEDS_MODIFY": {
        "EXISTING": MergedAction.NEEDS_MODIFY,
        "MODIFY": MergedAction.NEEDS_MODIFY,
        None: MergedAction.NEEDS_MODIFY,
    },
    "DEPRECATED": {
        "EXISTING": MergedAction.CONFLICT,
        "MODIFY": MergedAction.CONFLICT,
        None: MergedAction.DEPRECATE,
    },
    "UNCERTAIN": {
        "EXISTING": MergedAction.PENDING_REVIEW,
        "MODIFY": MergedAction.PENDING_REVIEW,
        None: MergedAction.PENDING_REVIEW,
    },
}

CONFLICT_PAIRS = [
    ("DEPRECATED", "EXISTING"),
    ("DEPRECATED", "MODIFY"),
]


@dataclass
class MergedVerdict:
    source: str
    case_id: Optional[int]
    candidate_index: Optional[int]
    action: MergedAction
    backward_verdict: Optional[str]
    forward_label: Optional[str]
    confidence: float
    reason: str
    conflict_marker: bool


def merge(
    backward_verdicts: List[Dict[str, Any]],
    forward_verdicts: List[Dict[str, Any]],
) -> List[MergedVerdict]:
    bw_index: Dict[int, Dict[str, Any]] = {}
    for v in backward_verdicts:
        cid = v.get("case_id")
        if cid is not None:
            bw_index[cid] = v

    forward_case_ids: set = set()
    merged: List[MergedVerdict] = []

    for fv in forward_verdicts:
        fw_label = fv.get("label", "NEW")
        matched_cid = fv.get("matched_case_id")

        if fw_label == "NEW" or matched_cid is None:
            merged.append(
                MergedVerdict(
                    source="forward_only", case_id=None,
                    candidate_index=fv.get("candidate_index"),
                    action=MergedAction.ADD_NEW, backward_verdict=None,
                    forward_label=fw_label, confidence=fv.get("confidence", 0.8),
                    reason=f"新增场景: {fv.get('reason', '无理由')}",
                    conflict_marker=False,
                )
            )
            continue

        forward_case_ids.add(matched_cid)

        bw = bw_index.get(matched_cid)
        if bw is None:
            merged.append(
                MergedVerdict(
                    source="forward_only", case_id=matched_cid,
                    candidate_index=fv.get("candidate_index"),
                    action=MergedAction.ADD_NEW, backward_verdict=None,
                    forward_label=fw_label, confidence=fv.get("confidence", 0.8),
                    reason=f"未找到反向裁决(case_id={matched_cid})，作为新增",
                    conflict_marker=False,
                )
            )
            continue

        bw_verdict = bw.get("verdict", "UNCERTAIN")
        action, conflict = _lookup_matrix(bw_verdict, fw_label)

        confidence = min(fv.get("confidence", 0.7), bw.get("confidence", 0.7))
        reason = _build_merge_reason(action, conflict, bw, fv)

        merged.append(
            MergedVerdict(
                source="merged", case_id=matched_cid,
                candidate_index=fv.get("candidate_index"),
                action=action, backward_verdict=bw_verdict,
                forward_label=fw_label, confidence=confidence,
                reason=reason, conflict_marker=conflict,
            )
        )

    for cid, bw in bw_index.items():
        if cid in forward_case_ids:
            continue
        bw_verdict = bw.get("verdict", "UNCERTAIN")
        action, conflict = _lookup_matrix(bw_verdict, None)
        merged.append(
            MergedVerdict(
                source="backward_only", case_id=cid,
                candidate_index=None, action=action,
                backward_verdict=bw_verdict, forward_label=None,
                confidence=bw.get("confidence", 0.7),
                reason=f"反向裁决: {bw.get('hint', '')}"[:100],
                conflict_marker=conflict,
            )
        )

    return merged


def _lookup_matrix(bw_verdict: str, fw_label: Optional[str]) -> tuple:
    if bw_verdict not in MERGE_MATRIX:
        return MergedAction.PENDING_REVIEW, False
    row = MERGE_MATRIX[bw_verdict]
    key = fw_label if fw_label in row else None
    action = row.get(key, MergedAction.PENDING_REVIEW)
    conflict = (bw_verdict, fw_label) in CONFLICT_PAIRS
    return action, conflict


def _build_merge_reason(
    action: MergedAction, conflict: bool,
    bw: Dict[str, Any], fv: Dict[str, Any],
) -> str:
    if conflict:
        return f"冲突: 反向={bw.get('verdict')}, 前向={fv.get('label')}，需人工决策"
    hints = []
    bw_hint = bw.get("hint", "")
    fw_reason = fv.get("reason", "")
    if bw_hint:
        hints.append(f"反向: {bw_hint[:40]}")
    if fw_reason:
        hints.append(f"前向: {fw_reason[:40]}")
    base = "; ".join(hints) if hints else "合并结果"
    return base[:100]


def _verdict_to_dict(v: MergedVerdict) -> Dict[str, Any]:
    return {
        "source": v.source, "case_id": v.case_id,
        "candidate_index": v.candidate_index,
        "action": v.action.value, "backward_verdict": v.backward_verdict,
        "forward_label": v.forward_label, "confidence": v.confidence,
        "reason": v.reason, "conflict_marker": v.conflict_marker,
    }


def _compute_reconciliation_stats(verdicts: List[MergedVerdict]) -> Dict[str, int]:
    stats: Dict[str, int] = {a.value: 0 for a in MergedAction}
    for v in verdicts:
        stats[v.action.value] += 1
    return stats


def _compute_avg_confidence(verdicts: List[MergedVerdict]) -> float:
    if not verdicts:
        return 0.0
    return sum(v.confidence for v in verdicts) / len(verdicts)


def _record_conflict_metric(
    db, project_id: int = 0, detail: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from app.services.metrics_service import record_metric
        record_metric("conflict_detected", project_id=project_id if project_id else None, detail=detail)
    except Exception:
        pass
