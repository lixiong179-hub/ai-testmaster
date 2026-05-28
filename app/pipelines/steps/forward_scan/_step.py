import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.forward_scan._types import ForwardVerdict
from app.pipelines.steps.forward_scan._service import ForwardScanService
from app.pipelines.steps.forward_scan._parsing import (
    _verdict_to_dict,
    _compute_stats,
    _compute_forward_confidence,
)


class ForwardScan(PipelineStep):
    name: ClassVar[str] = "forward_scan"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["scenario_candidates", "history_fingerprints"]
    produces: ClassVar[List[str]] = ["forward_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        candidates = ctx.get_artifact("scenario_candidates")
        if candidates is None:
            return False
        return candidates.get("total_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        candidates = ctx.get_artifact("scenario_candidates")
        fingerprints = ctx.get_artifact("history_fingerprints")

        cand_count = 0
        cand_desc_hash = ""
        if candidates:
            cand_count = candidates.get("total_count", 0)
            cand_desc_hash = hashlib.sha256(
                json.dumps(candidates.get("candidates", []), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]

        fp_count = 0
        fp_id_hash = ""
        if fingerprints:
            fp_count = fingerprints.get("total_count", 0)
            fp_id_hash = hashlib.sha256(
                json.dumps(fingerprints.get("fingerprints", []), sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]

        raw = f"{self.name}:{self.version}:c={cand_count}:{cand_desc_hash}:fp={fp_count}:{fp_id_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        candidates = ctx.get_artifact("scenario_candidates")
        fingerprints = ctx.get_artifact("history_fingerprints")

        if candidates is None:
            return StepResult(
                success=False,
                error="缺少 scenario_candidates 产物",
            )

        candidate_list = candidates.get("candidates", [])
        if not candidate_list:
            return StepResult(
                success=False,
                error="候选场景列表为空",
            )

        all_fps = []
        if fingerprints:
            all_fps = fingerprints.get("fingerprints", [])

        service = ForwardScanService(ai_client=ctx.get_ai_client())

        verdicts = service.scan(
            candidates=candidate_list,
            fingerprints=all_fps,
        )

        payload = {
            "project_id": candidates.get("project_id", 0),
            "verdicts": [_verdict_to_dict(v) for v in verdicts],
            "total_count": len(verdicts),
            "stats": _compute_stats(verdicts),
        }

        confidence = _compute_forward_confidence(verdicts)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="forward_verdicts",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_count": len(verdicts),
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required) and payload["total_count"] == len(payload["verdicts"])

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        candidates = ctx.get_artifact("scenario_candidates")
        project_id = 0
        if candidates:
            project_id = candidates.get("project_id", 0)
            candidate_list = candidates.get("candidates", [])
            verdicts = [
                ForwardVerdict(
                    candidate_index=i,
                    candidate_description=c.get("description", ""),
                    label="NEW",
                    matched_case_id=None,
                    matched_title="",
                    matched_similarity=0.0,
                    confidence=0.0,
                    reason=f"降级：{str(error)[:100]}",
                )
                for i, c in enumerate(candidate_list)
            ]
        else:
            verdicts = []

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "verdicts": [_verdict_to_dict(v) for v in verdicts],
                "total_count": len(verdicts),
                "stats": _compute_stats(verdicts),
            },
            artifact_kind="forward_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )
