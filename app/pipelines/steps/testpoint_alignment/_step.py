import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.testpoint_alignment._helpers import (
    _extract_inferred_capabilities,
    _extract_scenario_candidates,
    _find_matching_screens,
    _find_matching_capability,
    _find_matching_scenario,
    _build_no_match_note,
    _align_from_inferred_only,
    _compute_coverage,
    _compute_alignment_confidence,
)


class TestPointAlignment(PipelineStep):

    __test__ = False
    name: ClassVar[str] = "testpoint_alignment"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["raw_signals"]
    produces: ClassVar[List[str]] = ["aligned_testpoints"]

    def should_run(self, ctx: PipelineContext) -> bool:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return False
        inferred = ctx.get_artifact("inferred_business_summary")
        return bool(signals.get("test_points") or (inferred is not None))

    def cache_key(self, ctx: PipelineContext) -> str:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return ""
        tp_ids = sorted(p.get("id", 0) for p in signals.get("test_points", []))
        ui_count = len(signals.get("ui_specs", []))

        inferred = ctx.get_artifact("inferred_business_summary")
        inferred_hash = ""
        if inferred:
            try:
                caps = (inferred.get("parsed") or {}).get("inferred_capabilities", [])
                inferred_hash = hashlib.sha256(
                    json.dumps(caps, sort_keys=True, ensure_ascii=False, default=str).encode()
                ).hexdigest()[:16]
            except Exception:
                inferred_hash = "error"

        candidates = ctx.get_artifact("scenario_candidates")
        candidate_hash = ""
        if candidates:
            try:
                cands = candidates.get("candidates", [])
                candidate_hash = hashlib.sha256(
                    json.dumps(cands, sort_keys=True, ensure_ascii=False, default=str).encode()
                ).hexdigest()[:16]
            except Exception:
                candidate_hash = "error"

        raw = f"{self.name}:{self.version}:tp={tp_ids}:ui={ui_count}:inf={inferred_hash}:cand={candidate_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        signals = ctx.get_artifact("raw_signals")
        if not signals:
            return StepResult(success=False, error="缺少 raw_signals 产物")

        test_points = signals.get("test_points", [])
        ui_specs = signals.get("ui_specs", [])
        has_ui = signals.get("has_ui", False)

        inferred = ctx.get_artifact("inferred_business_summary")
        inferred_caps = _extract_inferred_capabilities(inferred)

        candidates = ctx.get_artifact("scenario_candidates")
        scenario_cands = _extract_scenario_candidates(candidates)

        aligned = []
        conflicts = []

        sources = {
            "ui": has_ui and len(ui_specs) > 0,
            "inferred": len(inferred_caps) > 0,
            "scenario": len(scenario_cands) > 0,
        }
        active_sources = [k for k, v in sources.items() if v]

        for tp in test_points:
            entry = {
                "test_point": tp,
                "ui_match": None,
                "capability_match": None,
                "scenario_match": None,
                "alignment_status": "aligned",
                "notes": "",
            }

            any_source_match = False

            if sources["ui"]:
                matched_screens = _find_matching_screens(tp, ui_specs)
                if matched_screens:
                    entry["ui_match"] = matched_screens[0]
                    any_source_match = True

            if sources["inferred"]:
                matched_cap = _find_matching_capability(tp, inferred_caps)
                if matched_cap:
                    entry["capability_match"] = matched_cap
                    any_source_match = True

            if sources["scenario"]:
                matched_scenario = _find_matching_scenario(tp, scenario_cands)
                if matched_scenario:
                    entry["scenario_match"] = matched_scenario
                    any_source_match = True

            if not any_source_match:
                if has_ui or sources["inferred"] or sources["scenario"]:
                    entry["alignment_status"] = "no_ui_match"
                    entry["notes"] = _build_no_match_note(tp, active_sources)
                    conflicts.append(entry)
                else:
                    entry["alignment_status"] = "no_sources"
                    entry["notes"] = "无可对齐的源（无 UI / 反推能力 / 场景候选）"

            aligned.append(entry)

        if not test_points and inferred_caps:
            aligned, conflicts = _align_from_inferred_only(inferred_caps)

        coverage = _compute_coverage(aligned, conflicts, inferred_caps)

        confidence = _compute_alignment_confidence(aligned, conflicts)
        should_pause = len(conflicts) > 0 and confidence < 0.7

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": signals.get("project_id"),
            "aligned_testpoints": aligned,
            "conflicts": conflicts,
            "total_testpoints": len(test_points) or len(inferred_caps),
            "aligned_count": len([a for a in aligned if a["alignment_status"] == "aligned"]),
            "conflict_count": len(conflicts),
            "has_ui": has_ui,
            "active_sources": active_sources,
            "sources": sources,
            "coverage": coverage,
        }

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="aligned_testpoints",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "conflict_count": len(conflicts),
                "active_sources": active_sources,
            },
            pause_for_confirmation=should_pause,
            confirmation_reason=f"发现 {len(conflicts)} 个测试点未对齐，请确认是否继续",
            confirmation_payload={"conflicts": conflicts[:10], "active_sources": active_sources},
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "aligned_testpoints" in payload and "sources" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        signals = ctx.get_artifact("raw_signals")
        test_points = signals.get("test_points", []) if signals else []
        aligned = [
            {
                "test_point": tp,
                "ui_match": None,
                "capability_match": None,
                "scenario_match": None,
                "alignment_status": "fallback",
                "notes": f"对齐降级: {error}",
            }
            for tp in test_points
        ]
        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "aligned_testpoints": aligned,
                "conflicts": [],
                "total_testpoints": len(test_points),
                "aligned_count": 0,
                "conflict_count": 0,
                "has_ui": False,
                "active_sources": [],
                "sources": {"ui": False, "inferred": False, "scenario": False},
                "coverage": None,
            },
            artifact_kind="aligned_testpoints",
            artifact_confidence=0.3,
            degraded=True,
        )
