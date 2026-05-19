import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from app.pipelines.steps.reverse_infer._helpers import (
    _hash_dict,
    _clamp_float,
    _build_ui_text,
    _build_fingerprint_text,
    _parse_infer_response,
    _validate_new_project_output,
    _validate_old_project_output,
    _CONFIDENCE_THRESHOLD,
)

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps.reverse_infer_prompts import (
    _SYSTEM_NEW_PROJECT,
    _SYSTEM_OLD_PROJECT,
    _SYSTEM_OLD_PROJECT_NO_UI,
    _USER_NEW_PROJECT,
    _USER_OLD_PROJECT,
    _USER_OLD_PROJECT_NO_UI,
)


class ReverseInfer(PipelineStep):

    name: str = "reverse_infer"
    version: str = "1.0"
    requires: List[str] = ["raw_signals"]
    produces: List[str] = ["inferred_business_summary"]

    def should_run(self, ctx: PipelineContext) -> bool:
        raw_signals = ctx.get_artifact("raw_signals")
        if raw_signals is None:
            return False
        if raw_signals.get("has_ui", False):
            return True
        return raw_signals.get("is_old_project", False)

    def cache_key(self, ctx: PipelineContext) -> str:
        raw_signals = ctx.get_artifact("raw_signals")
        fingerprints = ctx.get_artifact("history_fingerprints")

        if raw_signals is None:
            return ""

        project_id = raw_signals.get("project_id", 0)
        ui_hash = _hash_dict(raw_signals.get("ui_specs", []))
        fp_hash = _hash_dict(fingerprints) if fingerprints else "no_fp"

        raw = f"{self.name}:{self.version}:project={project_id}:ui={ui_hash}:fp={fp_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        raw_signals = ctx.get_artifact("raw_signals")
        if raw_signals is None:
            return StepResult(success=False, error="缺少 raw_signals 产物")

        project_id = raw_signals.get("project_id")
        if not project_id:
            return StepResult(success=False, error="raw_signals 缺少 project_id")

        ui_descriptions = raw_signals.get("ui_descriptions", [])
        ui_specs = raw_signals.get("ui_specs", [])
        fingerprints = ctx.get_artifact("history_fingerprints")
        is_old_project = (
            (fingerprints is not None and fingerprints.get("total_count", 0) > 0)
            or raw_signals.get("is_old_project", False)
        )
        has_ui = bool(ui_descriptions or ui_specs)

        if not has_ui:
            if is_old_project and fingerprints and fingerprints.get("total_count", 0) > 0:
                system_prompt = _SYSTEM_OLD_PROJECT_NO_UI
                fp_text = _build_fingerprint_text(fingerprints)
                user_prompt = _USER_OLD_PROJECT_NO_UI.format(fingerprint_text=fp_text)
                ui_text = fp_text
            else:
                return StepResult(success=False, error="无 UI 信息，无法反推")
        elif is_old_project:
            ui_text = _build_ui_text(ui_descriptions, ui_specs)
            system_prompt = _SYSTEM_OLD_PROJECT
            fp_text = _build_fingerprint_text(fingerprints)
            user_prompt = _USER_OLD_PROJECT.format(ui_text=ui_text, fingerprint_text=fp_text)
        else:
            ui_text = _build_ui_text(ui_descriptions, ui_specs)
            system_prompt = _SYSTEM_NEW_PROJECT
            user_prompt = _USER_NEW_PROJECT.format(ui_text=ui_text)

        try:
            response = ctx.get_ai_client().complete(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.3,
                max_tokens=4096,
                metadata={
                    "step_name": self.name,
                    "run_id": ctx.run.id,
                    "iteration_id": ctx.iteration_id,
                    "mode": "old_project" if is_old_project else "new_project",
                },
            )
        except Exception as e:
            from loguru import logger
            logger.error("ReverseInfer AI 调用失败: {}", e)
            return StepResult(success=False, error=f"AI 调用失败: {e}")

        parsed = _parse_infer_response(response.content)
        if parsed is None:
            return StepResult(success=False, error="AI 返回解析失败，非有效 JSON")

        if is_old_project and has_ui:
            ok, err = _validate_old_project_output(parsed)
        else:
            ok, err = _validate_new_project_output(parsed)

        if not ok:
            return StepResult(success=False, error=err or "输出校验失败")

        overall = parsed.get("overall_confidence", 0.0)
        confidence = _clamp_float(overall, 0.0, 1.0)
        questions = parsed.get("uncertain_questions", [])

        result = StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "project_id": project_id,
                "is_old_project": is_old_project,
                "mode": "old_project" if is_old_project else "new_project",
                "ui_text": ui_text,
                "parsed": parsed,
                "confidence": confidence,
                "uncertain_question_count": len(questions) if isinstance(questions, list) else 0,
            },
            artifact_kind="inferred_business_summary",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "mode": "old_project" if is_old_project else "new_project",
                "model_version": response.model_version,
                "latency_ms": response.latency_ms,
            },
        )

        if confidence < _CONFIDENCE_THRESHOLD:
            result.pause_for_confirmation = True
            result.confirmation_reason = (
                f"反推置信度 ({confidence:.2f}) 低于阈值 ({_CONFIDENCE_THRESHOLD})，"
                f"请确认 AI 推断的{len(questions) if isinstance(questions, list) else 0}个疑问"
            )
            result.confirmation_payload = {
                "questions": questions if isinstance(questions, list) else [],
                "summary": parsed.get("analysis_summary", ""),
                "confidence": confidence,
            }

        return result

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["iteration_id", "project_id", "parsed"]
        if not all(k in payload for k in required):
            return False
        parsed = payload.get("parsed", {})
        if not isinstance(parsed, dict):
            return False
        return "overall_confidence" in parsed

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        from loguru import logger
        logger.error("ReverseInfer fallback: {}", error)
        return StepResult(
            success=False,
            error=f"业务反推失败且无降级方案: {error}",
            degraded=True,
        )
