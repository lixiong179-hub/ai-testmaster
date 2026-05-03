"""S11 CaseGeneration — 用例生成 Step

调用 AI 为每个测试点生成测试用例。
复用现有 TestCaseGenerationService 的 prompt 构建和解析逻辑，
但通过 Pipeline AIClient 抽象层调用模型。
"""
import hashlib
import json
import re
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class CaseGeneration(PipelineStep):
    """用例生成 Step — 为每个测试点调用 AI 生成测试用例。"""

    name: ClassVar[str] = "case_generation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["generated_cases"]

    def should_run(self, ctx: PipelineContext) -> bool:
        aligned = ctx.get_artifact("aligned_testpoints")
        if aligned:
            return aligned.get("total_testpoints", 0) > 0
        signals = ctx.get_artifact("raw_signals")
        if signals:
            return signals.get("has_testpoints", False)
        return False

    def cache_key(self, ctx: PipelineContext) -> str:
        aligned = ctx.get_artifact("aligned_testpoints")
        signals = ctx.get_artifact("raw_signals")

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

        raw = f"{self.name}:{self.version}:tp={tp_ids}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        aligned = ctx.get_artifact("aligned_testpoints")
        signals = ctx.get_artifact("raw_signals")

        if not aligned and not signals:
            return StepResult(success=False, error="缺少 aligned_testpoints 和 raw_signals 产物")

        prd_content = signals.get("prd_content", "") if signals else ""
        ui_specs = signals.get("ui_specs", []) if signals else []
        has_ui = signals.get("has_ui", False) if signals else False

        if aligned:
            aligned_tps = aligned.get("aligned_testpoints", [])
        else:
            raw_tps = signals.get("test_points", []) if signals else []
            aligned_tps = [
                {"test_point": tp, "ui_match": None, "alignment_status": "no_ui_input"}
                for tp in raw_tps
                if tp is not None
            ]

        generated_cases = []
        failed_count = 0

        for entry in aligned_tps:
            tp = entry.get("test_point", {})
            try:
                prompt = _build_case_prompt(tp, prd_content, ui_specs, has_ui)
                response = ctx.ai_client.complete(
                    prompt=prompt,
                    system=_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=2000,
                    metadata={
                        "step_name": self.name,
                        "test_point_id": tp.get("id"),
                        "iteration_id": ctx.iteration_id,
                    },
                )

                if not response.content:
                    failed_count += 1
                    generated_cases.append({
                        "test_point": tp,
                        "status": "failed",
                        "error": "AI 返回空内容",
                    })
                    continue

                parsed = _parse_case_response(response.content)
                if not parsed:
                    failed_count += 1
                    generated_cases.append({
                        "test_point": tp,
                        "status": "failed",
                        "error": "AI 响应解析失败",
                    })
                    continue

                case_data = _enrich_case_data(parsed, tp, has_ui)
                generated_cases.append({
                    "test_point": tp,
                    "status": "success",
                    "case_data": case_data,
                    "degraded": response.degraded,
                })

            except Exception as e:
                failed_count += 1
                logger.error("用例生成失败 tp_id={}: {}", tp.get("id") if tp else "N/A", e)
                generated_cases.append({
                    "test_point": tp,
                    "status": "failed",
                    "error": str(e),
                })

        success_count = len([c for c in generated_cases if c["status"] == "success"])
        total = len(generated_cases)
        confidence = success_count / total if total > 0 else 0.0

        project_id = (
            aligned.get("project_id")
            if aligned
            else (signals.get("project_id") if signals else None)
        )

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "generated_cases": generated_cases,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "has_ui": has_ui,
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


_SYSTEM_PROMPT = (
    "你是一个专业的测试用例生成专家。根据提供的需求文档、测试点和UI规格，"
    "生成详细的测试用例。每个用例必须包含以下字段：\n"
    "1. title: 用例标题\n"
    "2. module: 所属模块\n"
    "3. precondition: 前置条件\n"
    "4. steps: 测试步骤列表，每步包含 action 和 expected\n"
    "5. expected_result: 预期结果\n"
    "6. priority: 优先级(1-4)\n"
    "7. case_type: 用例类型(functional/performance/security/etc)\n\n"
    "请以 JSON 数组格式返回，每个元素代表一个测试用例。"
)


def _build_case_prompt(
    tp: Dict[str, Any],
    prd_content: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> str:
    parts = [
        f"## 测试点信息",
        f"- 模块: {tp.get('module', '未知')}",
        f"- 功能: {tp.get('function', '')}",
        f"- 测试点: {tp.get('point', '未知')}",
        f"- 优先级: {tp.get('priority', 3)}",
    ]

    if prd_content:
        parts.append(f"\n## 需求文档摘要\n{prd_content[:3000]}")

    if has_ui and ui_specs:
        ui_text = _format_ui_specs_for_prompt(ui_specs[:5])
        if ui_text:
            parts.append(f"\n## UI 规格信息\n{ui_text}")

    parts.append("\n请为上述测试点生成测试用例（JSON 数组格式）。")

    return "\n".join(parts)


def _format_ui_specs_for_prompt(ui_specs: List[Dict[str, Any]]) -> str:
    parts = []
    for spec in ui_specs:
        screen_name = spec.get("screen_name", "未知页面")
        ui_spec = spec.get("ui_spec", {})
        if isinstance(ui_spec, dict):
            elements = ui_spec.get("elements", [])
            elem_texts = []
            for elem in elements[:20]:
                elem_type = elem.get("type", "")
                elem_text = elem.get("text", "")
                if elem_text:
                    elem_texts.append(f"  [{elem_type}] {elem_text}")
            if elem_texts:
                parts.append(f"### {screen_name}\n" + "\n".join(elem_texts))
    return "\n\n".join(parts)


def _parse_case_response(content: str) -> Optional[List[Dict[str, Any]]]:
    from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string

    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            cases = result.get("cases") or result.get("test_cases") or []
            if isinstance(cases, list):
                return cases
    except json.JSONDecodeError:
        pass

    fixed = fix_common_json_issues(content)
    if fixed:
        try:
            result = json.loads(fixed)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                cases = result.get("cases") or result.get("test_cases") or []
                if isinstance(cases, list):
                    return cases
        except json.JSONDecodeError:
            pass

    cleaned = clean_json_string(content)
    if cleaned:
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\[[\s\S]*\]', content)
    if json_match:
        array_content = json_match.group()
        fixed_array = clean_json_string(array_content)
        if fixed_array:
            try:
                return json.loads(fixed_array)
            except json.JSONDecodeError:
                pass

    return None


def _enrich_case_data(
    parsed: List[Dict[str, Any]], tp: Dict[str, Any], has_ui: bool
) -> List[Dict[str, Any]]:
    tp_module = tp.get("module", "")
    tp_point = tp.get("point", "")
    tp_id = tp.get("id")

    for case in parsed:
        if not case.get("module"):
            case["module"] = tp_module
        if not case.get("title"):
            case["title"] = f"{tp_point} - 测试用例"
        case["test_point_id"] = tp_id
        case["lifecycle_status"] = "draft"
        if not has_ui:
            case["case_type"] = "API"

    return parsed
