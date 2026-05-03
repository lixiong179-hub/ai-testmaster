"""S7 ScenarioCandidateExtractor — 新场景候选提取 Step

从 PRD/UI 规格中提取候选测试场景列表（短描述 + 模块归属），
供后续 ForwardScan Step 消费。

核心流程：
    1. 获取 raw_signals + history_fingerprints 产物
    2. 提取已有模块列表（从 history_fingerprints）
    3. 调 AI 生成候选场景
    4. 校验输出 schema + 启发式数量检查
    5. 输出 scenario_candidates 产物
"""
import hashlib
import json
import re
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


_SYSTEM_PROMPT = (
    "你是一个专业的测试场景分析专家。你的任务是根据需求文档和UI规格，"
    "提取出需要新增测试的场景候选列表。\n\n"
    "对于每个候选场景，输出以下 JSON 结构：\n"
    "- description: 场景描述（不超过50字）\n"
    "- module: 所属模块名称\n"
    "- priority: 优先级（1高/2中/3低）\n"
    "- reason: 为什么需要新增此场景（不超过50字）\n\n"
    "提取规则：\n"
    "1. 只提取【新增】或【变更】的场景，不要重复已有用例覆盖的场景\n"
    "2. 模块名称必须从已有模块列表中选择\n"
    "3. 每个场景应独立可测试，不与其他场景耦合\n"
    "4. 优先覆盖核心业务流程和边界条件\n\n"
    "请以 JSON 数组格式返回。"
)

_USER_TEMPLATE = (
    "## 需求文档\n\n{prd_text}\n\n"
    "## UI 规格信息\n\n{ui_text}\n\n"
    "## 已有模块列表\n\n{modules_text}\n\n"
    "## 已有用例摘要\n\n{existing_text}\n\n"
    "请根据以上信息，提取需要新增测试的场景候选列表。"
)


class ScenarioCandidateExtractor(PipelineStep):
    """新场景候选提取 Step — 从 PRD/UI 提取候选测试场景。"""

    name: ClassVar[str] = "scenario_candidate_extractor"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["raw_signals", "history_fingerprints"]
    produces: ClassVar[List[str]] = ["scenario_candidates"]

    def should_run(self, ctx: PipelineContext) -> bool:
        raw_signals = ctx.get_artifact("raw_signals")
        if raw_signals is None:
            return False
        return bool(raw_signals.get("project_id"))

    def cache_key(self, ctx: PipelineContext) -> str:
        raw_signals = ctx.get_artifact("raw_signals")
        if raw_signals is None:
            return ""
        project_id = raw_signals.get("project_id", 0)
        sig_hash = hashlib.sha256(
            json.dumps(raw_signals, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        raw = f"{self.name}:{self.version}:project={project_id}:sig={sig_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        raw_signals = ctx.get_artifact("raw_signals")
        fingerprints = ctx.get_artifact("history_fingerprints")

        if raw_signals is None:
            return StepResult(success=False, error="缺少 raw_signals 产物")

        project_id = raw_signals.get("project_id")
        if not project_id:
            return StepResult(success=False, error="raw_signals 缺少 project_id")

        prd_text = _extract_prd(raw_signals)
        ui_text = _extract_ui(raw_signals)
        modules = _extract_existing_modules(fingerprints)
        existing_text = _extract_existing_summaries(fingerprints)

        modules_text = ", ".join(modules) if modules else "（无已有模块，请根据需求自行归纳）"

        prompt = _USER_TEMPLATE.format(
            prd_text=prd_text,
            ui_text=ui_text,
            modules_text=modules_text,
            existing_text=existing_text,
        )

        try:
            response = ctx.ai_client.complete(
                prompt=prompt,
                system=_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=4000,
                metadata={"step_name": "scenario_candidate_extractor"},
            )
        except Exception as e:
            return StepResult(
                success=False,
                error=f"AI 调用失败: {e}",
            )

        candidates = _parse_candidates(response.content)
        if candidates is None:
            return StepResult(
                success=False,
                error="AI 返回解析失败",
            )

        validated = _validate_candidates(candidates, modules)

        ui_control_count = _estimate_ui_controls(raw_signals)
        min_expected = max(1, int(ui_control_count * 0.3))
        coverage_ok = len(validated) >= min_expected

        payload = {
            "project_id": project_id,
            "candidates": validated,
            "total_count": len(validated),
            "existing_modules": modules,
            "coverage_check": {
                "ui_control_count": ui_control_count,
                "min_expected": min_expected,
                "actual_count": len(validated),
                "passed": coverage_ok,
            },
        }

        confidence = _compute_confidence(validated, coverage_ok)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="scenario_candidates",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "project_id": project_id,
                "total_count": len(validated),
                "coverage_passed": coverage_ok,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "candidates", "total_count", "existing_modules", "coverage_check"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        raw_signals = ctx.get_artifact("raw_signals")
        project_id = 0
        if raw_signals:
            project_id = raw_signals.get("project_id", 0)

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "candidates": [],
                "total_count": 0,
                "existing_modules": [],
                "coverage_check": {
                    "ui_control_count": 0,
                    "min_expected": 0,
                    "actual_count": 0,
                    "passed": False,
                },
            },
            artifact_kind="scenario_candidates",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )


def _extract_prd(raw_signals: Dict[str, Any]) -> str:
    prd = raw_signals.get("prd_content", "")
    if prd:
        return prd[:3000]
    return "（无 PRD 文档）"


def _extract_ui(raw_signals: Dict[str, Any]) -> str:
    ui_specs = raw_signals.get("ui_specs", [])
    if not ui_specs:
        return "（无 UI 规格）"
    parts = []
    for spec in ui_specs[:5]:
        name = spec.get("screen_name", "未知屏幕")
        ui_spec = spec.get("ui_spec", "")
        if ui_spec:
            try:
                spec_text = json.dumps(ui_spec, ensure_ascii=False, indent=2)[:500]
            except (TypeError, ValueError):
                spec_text = str(ui_spec)[:500]
            parts.append(f"### {name}\n{spec_text}")
    return "\n\n".join(parts) if parts else "（无 UI 规格）"


def _extract_existing_modules(fingerprints: Any) -> List[str]:
    if fingerprints is None:
        return []
    fps = fingerprints.get("fingerprints", [])
    modules = sorted({fp.get("module", "") for fp in fps if fp.get("module")})
    return modules


def _extract_existing_summaries(fingerprints: Any) -> str:
    if fingerprints is None:
        return "（无已有用例）"
    fps = fingerprints.get("fingerprints", [])
    if not fps:
        return "（无已有用例）"
    parts = []
    for fp in fps[:20]:
        parts.append(f"- [{fp.get('module', '?')}] {fp.get('summary', fp.get('title', '无标题'))}")
    return "\n".join(parts)


def _parse_candidates(content: str) -> Optional[List[Dict[str, Any]]]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        data = _try_extract_json_array(content)
        if data is None:
            return None

    if isinstance(data, dict):
        for key in ("candidates", "scenarios", "items", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return None

    if isinstance(data, list):
        return data

    return None


def _try_extract_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            return json.loads(match.group())
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _validate_candidates(
    candidates: List[Dict[str, Any]],
    existing_modules: List[str],
) -> List[Dict[str, Any]]:
    validated = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        desc = c.get("description", "").strip()
        if not desc or len(desc) > 50:
            continue
        module = c.get("module", "").strip()
        if not module:
            continue
        if existing_modules and module not in existing_modules:
            closest = _find_closest_module(module, existing_modules)
            if closest:
                c["module_original"] = module
                c["module"] = closest
            else:
                continue
        priority = c.get("priority", 3)
        if not isinstance(priority, int) or priority not in (1, 2, 3):
            priority = 3
        c["priority"] = priority
        reason = c.get("reason", "").strip()
        if not reason:
            reason = desc
        c["reason"] = reason[:100]
        validated.append(c)
    return validated


def _find_closest_module(target: str, modules: List[str]) -> Optional[str]:
    target_lower = target.lower()
    for m in modules:
        if m.lower() == target_lower:
            return m
    for m in modules:
        if target_lower in m.lower() or m.lower() in target_lower:
            return m
    return None


def _estimate_ui_controls(raw_signals: Dict[str, Any]) -> int:
    ui_specs = raw_signals.get("ui_specs", [])
    count = 0
    for spec in ui_specs:
        ui_spec = spec.get("ui_spec")
        if isinstance(ui_spec, dict):
            components = ui_spec.get("components", ui_spec.get("elements", []))
            if isinstance(components, list):
                count += len(components)
            elif isinstance(components, dict):
                count += len(components)
        elif isinstance(ui_spec, list):
            count += len(ui_spec)
    return max(count, len(ui_specs))


def _compute_confidence(candidates: List[Dict[str, Any]], coverage_ok: bool) -> float:
    if not candidates:
        return 0.0
    base = 0.7 if coverage_ok else 0.4
    high_priority = sum(1 for c in candidates if c.get("priority") == 1)
    bonus = min(0.2, high_priority * 0.05)
    return min(1.0, base + bonus)
