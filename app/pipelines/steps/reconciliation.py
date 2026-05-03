"""S7 Reconciliation — 双向扫描合并矩阵 Step

将 backward_verdicts 与 forward_verdicts 按 plan §6 合并矩阵合并，
输出每个用例的最终动作（KEEP / NEEDS_MODIFY / DEPRECATE / ADD_NEW / CONFLICT 等）。

核心流程：
    1. 获取 backward_verdicts + forward_verdicts 产物
    2. 按 case_id 建立 backward index
    3. 对每个 forward verdict：
       - NEW → ADD_NEW
       - EXISTING/MODIFY → 查 backward，应用合并矩阵
    4. 对仅有 backward 的用例（forward 未匹配到）→ 按矩阵 (无前向) 列处理
    5. 标记冲突（DEPRECATED × EXISTING/MODIFY）
    6. 输出 merged_verdicts 产物

合并矩阵为纯函数，零 AI 调用，100% 可测试。
"""
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Final, List, Literal, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


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


class Reconciliation(PipelineStep):
    name: ClassVar[str] = "reconciliation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["backward_verdicts", "forward_verdicts"]
    produces: ClassVar[List[str]] = ["merged_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")
        return backward is not None or forward is not None

    def cache_key(self, ctx: PipelineContext) -> str:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")

        bw_count = 0
        if backward:
            bw_count = backward.get("total_count", 0)

        fw_count = 0
        if forward:
            fw_count = forward.get("total_count", 0)

        raw = f"{self.name}:{self.version}:bw={bw_count}:fw={fw_count}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")

        backward_verdicts = backward.get("verdicts", []) if backward else []
        forward_verdicts = forward.get("verdicts", []) if forward else []

        project_id = 0
        if backward:
            project_id = backward.get("project_id", 0)
        elif forward:
            project_id = forward.get("project_id", 0)

        merged = merge(backward_verdicts, forward_verdicts)

        payload = {
            "project_id": project_id,
            "verdicts": [_verdict_to_dict(v) for v in merged],
            "total_count": len(merged),
            "stats": _compute_reconciliation_stats(merged),
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="merged_verdicts",
            artifact_confidence=_compute_avg_confidence(merged),
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_count": len(merged),
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required) and payload["total_count"] == len(payload["verdicts"])

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        backward = ctx.get_artifact("backward_verdicts")
        forward = ctx.get_artifact("forward_verdicts")

        project_id = 0
        if backward:
            project_id = backward.get("project_id", 0)
        elif forward:
            project_id = forward.get("project_id", 0)

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "verdicts": [],
                "total_count": 0,
                "stats": {"keep": 0, "needs_modify": 0, "locator_broken": 0,
                          "locator_and_modify": 0, "deprecate": 0, "add_new": 0,
                          "conflict": 0, "pending_review": 0},
            },
            artifact_kind="merged_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )


def merge(
    backward_verdicts: List[Dict[str, Any]],
    forward_verdicts: List[Dict[str, Any]],
) -> List[MergedVerdict]:
    """执行合并矩阵，返回 MergedVerdict 列表。

    Args:
        backward_verdicts: 反向扫描结果列表 [{case_id, verdict, confidence, hint}]。
        forward_verdicts: 正向扫描结果列表 [{candidate_index, label, matched_case_id, confidence, reason}]。

    Returns:
        MergedVerdict 列表。
    """
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
                    source="forward_only",
                    case_id=None,
                    candidate_index=fv.get("candidate_index"),
                    action=MergedAction.ADD_NEW,
                    backward_verdict=None,
                    forward_label=fw_label,
                    confidence=fv.get("confidence", 0.8),
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
                    source="forward_only",
                    case_id=matched_cid,
                    candidate_index=fv.get("candidate_index"),
                    action=MergedAction.ADD_NEW,
                    backward_verdict=None,
                    forward_label=fw_label,
                    confidence=fv.get("confidence", 0.8),
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
                source="merged",
                case_id=matched_cid,
                candidate_index=fv.get("candidate_index"),
                action=action,
                backward_verdict=bw_verdict,
                forward_label=fw_label,
                confidence=confidence,
                reason=reason,
                conflict_marker=conflict,
            )
        )

    for cid, bw in bw_index.items():
        if cid in forward_case_ids:
            continue
        bw_verdict = bw.get("verdict", "UNCERTAIN")
        action, conflict = _lookup_matrix(bw_verdict, None)
        merged.append(
            MergedVerdict(
                source="backward_only",
                case_id=cid,
                candidate_index=None,
                action=action,
                backward_verdict=bw_verdict,
                forward_label=None,
                confidence=bw.get("confidence", 0.7),
                reason=f"反向裁决: {bw.get('hint', '')}"[:100],
                conflict_marker=conflict,
            )
        )

    return merged


def _lookup_matrix(
    bw_verdict: str,
    fw_label: Optional[str],
) -> tuple:
    """查合并矩阵，返回 (MergedAction, is_conflict)。

    Args:
        bw_verdict: 反向裁决字符串。
        fw_label: 正向标签字符串或 None。

    Returns:
        (action, conflict_marker) 元组。
    """
    if bw_verdict not in MERGE_MATRIX:
        return MergedAction.PENDING_REVIEW, False

    row = MERGE_MATRIX[bw_verdict]
    key = fw_label if fw_label in row else None
    action = row.get(key, MergedAction.PENDING_REVIEW)
    conflict = (bw_verdict, fw_label) in CONFLICT_PAIRS
    return action, conflict


def _build_merge_reason(
    action: MergedAction,
    conflict: bool,
    bw: Dict[str, Any],
    fv: Dict[str, Any],
) -> str:
    """构建合并结果的理由说明。

    Args:
        action: 合并后的动作。
        conflict: 是否冲突。
        bw: 反向裁决 dict。
        fv: 正向裁决 dict。

    Returns:
        不超过 100 字的原因描述。
    """
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
        "source": v.source,
        "case_id": v.case_id,
        "candidate_index": v.candidate_index,
        "action": v.action.value,
        "backward_verdict": v.backward_verdict,
        "forward_label": v.forward_label,
        "confidence": v.confidence,
        "reason": v.reason,
        "conflict_marker": v.conflict_marker,
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
