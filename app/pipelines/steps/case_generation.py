"""S11 CaseGeneration — 用例生成 Step

调用 AI 为每个测试点生成测试用例。
复用现有 TestCaseGenerationService 的 prompt 构建和解析逻辑，
但通过 Pipeline AIClient 抽象层调用模型。
"""
import hashlib
from typing import Any, ClassVar, Dict, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps._dedup import _dedup_cases_global
from app.pipelines.steps._execution import _execute_task_based, _execute_legacy

from app.pipelines.steps._prompt import (
    _build_full_prompt,
    _filter_prd_by_testpoint,
    _filter_ui_specs_by_testpoint,
)
from app.pipelines.steps._parsing import (
    _parse_case_response,
    _validate_test_data,
    _enrich_case_data,
    _enrich_case_data_with_task,
)
from app.pipelines.steps._dedup import (
    _jaccard_similarity,
    _dedup_cases_by_title,
)
from app.pipelines.steps._case_coverage import (
    _classify_case_type,
    _check_type_coverage,
    _generate_supplemental,
)
from app.pipelines.steps._task_generators import (
    _generate_create_case,
    _generate_modify_case,
    _generate_locator_fix,
)


class CaseGeneration(PipelineStep):
    """用例生成 Step — 为每个测试点调用 AI 生成测试用例。"""

    name: ClassVar[str] = "case_generation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["generation_tasks"]
    produces: ClassVar[List[str]] = ["generated_cases"]

    def should_run(self, ctx: PipelineContext) -> bool:
        tasks_artifact = ctx.get_artifact("generation_tasks")
        if tasks_artifact:
            tasks = tasks_artifact.get("generation_tasks", [])
            return len(tasks) > 0
        aligned = ctx.get_artifact("aligned_testpoints")
        if aligned:
            return aligned.get("total_testpoints", 0) > 0
        signals = ctx.get_artifact("raw_signals")
        if signals:
            return signals.get("has_testpoints", False)
        return False

    def cache_key(self, ctx: PipelineContext) -> str:
        tasks = ctx.get_artifact("generation_tasks")
        aligned = ctx.get_artifact("aligned_testpoints")
        signals = ctx.get_artifact("raw_signals")

        task_ids = []
        if tasks:
            task_ids = sorted(
                t.get("task_id", "") for t in tasks.get("generation_tasks", [])
            )

        tp_ids = []
        if aligned:
            tp_ids = sorted(
                a["test_point"].get("id", 0)
                for a in aligned.get("aligned_testpoints", [])
            )
        elif signals:
            tp_ids = sorted(
                tp.get("id", 0)
                for tp in signals.get("test_points", [])
                if tp is not None
            )

        raw = f"{self.name}:{self.version}:tasks={task_ids}:tp={tp_ids}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        signals = ctx.get_artifact("raw_signals")
        prd_content = signals.get("prd_content", "") if signals else ""
        ui_specs = signals.get("ui_specs", []) if signals else []
        ui_descriptions = signals.get("ui_descriptions", []) if signals else []
        has_ui = signals.get("has_ui", False) if signals else False

        tasks_artifact = ctx.get_artifact("generation_tasks")
        aligned = ctx.get_artifact("aligned_testpoints")

        ui_description = ""
        if ui_descriptions:
            ui_description = "\n".join(
                d.get("description", d.get("summary", ""))
                for d in ui_descriptions
                if d.get("description") or d.get("summary")
            )

        if tasks_artifact:
            generation_tasks = tasks_artifact.get("generation_tasks", [])
            deprecation_suggestions = tasks_artifact.get("deprecation_suggestions", [])
            actionable_tasks = [
                t for t in generation_tasks
                if t.get("task_type") in ("create", "modify", "locator_fix")
            ]
        else:
            generation_tasks = []
            deprecation_suggestions = []
            actionable_tasks = []

        history_cases: List[Dict[str, Any]] = []
        if actionable_tasks:
            hf_artifact = ctx.get_artifact("history_fingerprints")
            if hf_artifact:
                for fp in hf_artifact.get("fingerprints", [])[:50]:
                    history_cases.append({
                        "title": fp.get("title", fp.get("case_title", "")),
                        "module": fp.get("module", ""),
                        "summary": fp.get("summary", ""),
                        "priority": fp.get("priority", 3),
                    })

        if actionable_tasks:
            generated_cases, failed_count = _execute_task_based(
                ctx, actionable_tasks, prd_content, ui_description,
                ui_specs, has_ui, history_cases,
            )
        else:
            if not aligned and not signals:
                return StepResult(
                    success=False,
                    error="缺少 generation_tasks、aligned_testpoints 和 raw_signals 产物",
                )
            generated_cases, failed_count = _execute_legacy(
                ctx, aligned, signals, prd_content, ui_description,
                ui_specs, has_ui,
            )

        generated_cases = _dedup_cases_global(generated_cases)

        success_count = len([c for c in generated_cases if c["status"] == "success"])
        total = len(generated_cases)
        confidence = success_count / total if total > 0 else 0.0

        project_id = None
        if aligned:
            project_id = aligned.get("project_id")
        elif signals:
            project_id = signals.get("project_id")

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "generated_cases": generated_cases,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "has_ui": has_ui,
            "deprecation_suggestions": deprecation_suggestions,
        }

        return StepResult(
            success=success_count > 0,
            artifact_payload=payload,
            artifact_kind="generated_cases",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "success_rate": f"{success_count}/{total}",
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "generated_cases" in payload and "total" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"用例生成降级: {error}",
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "generated_cases": [],
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "has_ui": False,
            },
            artifact_kind="generated_cases",
            artifact_confidence=0.0,
            degraded=True,
        )
