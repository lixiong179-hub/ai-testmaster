"""S3 ReverseInfer — 业务摘要反推 Step

从 UI 原型反推业务摘要，支持两种模式：
    - 新项目（场景 3）：仅 UI → 反推 inferred_capabilities + uncertain_questions
    - 旧项目（场景 5）：UI + 历史指纹 → 反推 change_summary + uncertain_questions

核心流程：
    1. 获取 raw_signals 产物（必须含 UI）
    2. 检测是否有历史指纹（决定新/旧项目模式）
    3. 构建 prompt 调 AI 推断
    4. 置信度 < 阈值 → 标记 pause_for_confirmation
    5. 输出 inferred_business_summary 产物
"""
import hashlib
import json
import re
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

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

_CONFIDENCE_THRESHOLD: float = 0.7
_MAX_UI_CHARS: int = 4000
_MAX_FINGERPRINT_COUNT: int = 30


class ReverseInfer(PipelineStep):
    """业务摘要反推 Step — 从 UI 反推业务能力或变更摘要。"""

    name: ClassVar[str] = "reverse_infer"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["raw_signals"]
    produces: ClassVar[List[str]] = ["inferred_business_summary"]

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
                ui_text = fp_text  # no-UI 分支：payload 字段名保持 ui_text 兼容性，实际为指纹文本
                logger.info("ReverseInfer: 旧项目无 UI 模式，从 {} 条指纹反推",
                            fingerprints.get("total_count", 0))
            else:
                return StepResult(success=False, error="无 UI 信息，无法反推")
        elif is_old_project:
            ui_text = _build_ui_text(ui_descriptions, ui_specs)
            system_prompt = _SYSTEM_OLD_PROJECT
            fp_text = _build_fingerprint_text(fingerprints)
            user_prompt = _USER_OLD_PROJECT.format(
                ui_text=ui_text,
                fingerprint_text=fp_text,
            )
            logger.info("ReverseInfer: 旧项目模式，含 {} 条历史指纹", fingerprints.get("total_count", 0))
        else:
            ui_text = _build_ui_text(ui_descriptions, ui_specs)
            system_prompt = _SYSTEM_NEW_PROJECT
            user_prompt = _USER_NEW_PROJECT.format(ui_text=ui_text)
            logger.info("ReverseInfer: 新项目模式，无历史指纹")

        try:
            response = ctx.ai_client.complete(
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
            logger.warning("ReverseInfer 置信度低于阈值，暂停等待确认: {:.2f}", confidence)

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
        logger.error("ReverseInfer fallback: {}", error)
        return StepResult(
            success=False,
            error=f"业务反推失败且无降级方案: {error}",
            degraded=True,
        )


def _hash_dict(obj: Any) -> str:
    """计算对象的 sha256 摘要前 16 位。"""
    try:
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception:
        return "error"


def _clamp_float(value: Any, low: float, high: float) -> float:
    """将值限制在 [low, high] 范围内。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, v))


def _build_ui_text(
    ui_descriptions: List[Dict[str, Any]],
    ui_specs: List[Dict[str, Any]],
) -> str:
    """构建 UI 文本描述供 prompt 使用。"""
    parts: List[str] = []

    for desc in ui_descriptions[:20]:
        screen_name = desc.get("screen_name", "未知页面")
        description = desc.get("description", "")
        parts.append(f"- 页面: {screen_name}")
        if description:
            parts.append(f"  描述: {description}")

    if ui_specs:
        parts.append("\nUI 控件信息:")
        for spec in ui_specs[:20]:
            screen_name = spec.get("screen_name", "未知页面")
            ui_spec = spec.get("ui_spec", {})
            if isinstance(ui_spec, dict):
                components = ui_spec.get("components", [])
                elements = ui_spec.get("elements", [])
                all_items = list(components) + list(elements)
                if all_items:
                    item_names = [
                        (i.get("name") or i.get("type") or str(i))
                        for i in all_items[:10]
                        if isinstance(i, dict)
                    ]
                    parts.append(f"- [{screen_name}]: {', '.join(item_names[:10])}")
            elif isinstance(ui_spec, list):
                item_names = [
                    (i.get("name") or i.get("type") or str(i))
                    for i in ui_spec[:10]
                    if isinstance(i, dict)
                ]
                parts.append(f"- [{screen_name}]: {', '.join(item_names[:10])}")

    text = "\n".join(parts)
    if len(text) > _MAX_UI_CHARS:
        text = text[:_MAX_UI_CHARS] + "\n...(UI 信息过长已截断)"
    return text


def _build_fingerprint_text(fingerprints: Optional[Dict[str, Any]]) -> str:
    """构建历史指纹文本描述供 prompt 使用。"""
    if not fingerprints:
        return "（无历史用例指纹）"

    items = fingerprints.get("fingerprints", [])
    if not isinstance(items, list) or len(items) == 0:
        return "（无历史用例指纹）"

    parts: List[str] = []
    seen_modules: set[str] = set()

    for item in items[:_MAX_FINGERPRINT_COUNT]:
        if not isinstance(item, dict):
            continue
        module = str(item.get("module", ""))
        title = str(item.get("title", ""))
        summary = str(item.get("summary", ""))

        if module and module not in seen_modules:
            seen_modules.add(module)
            parts.append(f"\n### 模块: {module}")

        parts.append(f"- [{title}]: {summary[:120]}")

    text = "\n".join(parts)
    if len(text) > 3000:
        text = text[:3000] + "\n...(指纹信息过长已截断)"
    return text


def _parse_infer_response(content: str) -> Optional[Dict[str, Any]]:
    """解析 AI 响应 JSON，支持多种格式。"""
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"inferred_capabilities": parsed, "overall_confidence": 0.5}
    except (json.JSONDecodeError, TypeError):
        pass

    # 尝试从文本中提取 JSON 块
    m = re.search(r'\{[\s\S]*\}', content)
    if m:
        try:
            parsed = json.loads(m.group())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _validate_new_project_output(parsed: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """校验新项目模式输出。"""
    if "overall_confidence" not in parsed:
        return False, "缺少 overall_confidence 字段"

    caps = parsed.get("inferred_capabilities", [])
    if not isinstance(caps, list):
        return False, "inferred_capabilities 必须是数组"

    for cap in caps:
        if not isinstance(cap, dict):
            return False, "inferred_capabilities 元素必须是对象"
        for field in ["name", "key", "description", "confidence"]:
            if field not in cap:
                return False, f"capability 缺少 {field} 字段"

    questions = parsed.get("uncertain_questions", [])
    if not isinstance(questions, list):
        return False, "uncertain_questions 必须是数组"

    return True, None


def _validate_old_project_output(parsed: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """校验旧项目模式输出。"""
    if "overall_confidence" not in parsed:
        return False, "缺少 overall_confidence 字段"

    cs = parsed.get("change_summary")
    if cs is None or not isinstance(cs, dict):
        return False, "缺少 change_summary 或格式错误"

    for key in ["new_capabilities", "modified_capabilities", "removed_capabilities"]:
        value = cs.get(key, [])
        if not isinstance(value, list):
            return False, f"change_summary.{key} 必须是数组"

    questions = parsed.get("uncertain_questions", [])
    if not isinstance(questions, list):
        return False, "uncertain_questions 必须是数组"

    return True, None
