import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.backward_scan._service import BackwardScanService
from app.pipelines.schemas.backward_verdict import (
    BackwardCaseVerdict,
    BackwardVerdict,
)
from app.pipelines.steps.backward_scan._helpers import (
    _extract_change_signals,
    _compute_scan_confidence,
)

BATCH_SIZE = 50


class BackwardScan(PipelineStep):

    name: ClassVar[str] = "backward_scan"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["history_fingerprints", "raw_signals"]
    produces: ClassVar[List[str]] = ["backward_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        fingerprints = ctx.get_artifact("history_fingerprints")
        if fingerprints is None:
            return False
        return fingerprints.get("total_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        fingerprints = ctx.get_artifact("history_fingerprints")
        raw_signals = ctx.get_artifact("raw_signals")
        fp_count = 0
        if fingerprints:
            fp_count = fingerprints.get("total_count", 0)
        sig_hash = ""
        if raw_signals:
            sig_hash = hashlib.sha256(
                json.dumps(raw_signals, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]
        raw = f"{self.name}:{self.version}:fp={fp_count}:sig={sig_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        fingerprints = ctx.get_artifact("history_fingerprints")
        raw_signals = ctx.get_artifact("raw_signals")

        if fingerprints is None or raw_signals is None:
            return StepResult(
                success=False,
                error="缺少 history_fingerprints 或 raw_signals 产物",
            )

        change_signals = _extract_change_signals(raw_signals)
        all_fps = fingerprints.get("fingerprints", [])

        service = BackwardScanService(
            ai_client=ctx.get_ai_client(),
            batch_size=BATCH_SIZE,
        )

        verdicts, stats = service.scan(
            change_signals=change_signals,
            fingerprints=all_fps,
            check_budget=ctx.check_budget,
        )

        payload = {
            "project_id": fingerprints.get("project_id", 0),
            "verdicts": [v.dict() for v in verdicts],
            "total_count": len(verdicts),
            "stats": stats,
        }

        confidence = _compute_scan_confidence(verdicts)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="backward_verdicts",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_count": len(verdicts),
                "stats": stats,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        fingerprints = ctx.get_artifact("history_fingerprints")
        project_id = 0
        if fingerprints:
            project_id = fingerprints.get("project_id", 0)
            fps = fingerprints.get("fingerprints", [])
            verdicts = [
                BackwardCaseVerdict(
                    case_id=fp["case_id"],
                    verdict=BackwardVerdict.UNCERTAIN,
                    confidence=0.0,
                    hint=f"降级：{str(error)[:100]}",
                )
                for fp in fps
            ]
        else:
            verdicts = []

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "verdicts": [v.dict() for v in verdicts],
                "total_count": len(verdicts),
                "stats": {
                    "batches": 0,
                    "retries": 0,
                    "degraded": len(verdicts),
                    "auto_corrected": 0,
                },
            },
            artifact_kind="backward_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )
