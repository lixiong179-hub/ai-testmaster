"""S2 HistoryFingerprint — 历史指纹采集 Step

从项目已有用例中采集 summary 指纹，构建后续 BackwardScan/ForwardScan
所需的统一上下文产物。按需增量更新过期 summary。

核心逻辑：
    1. 查询项目下所有非 archived 用例的 summary
    2. 检测 model_version 不匹配的过期 summary，触发增量重算
    3. 输出 history_fingerprints 产物，供后续 Step 消费
"""
import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class HistoryFingerprint(PipelineStep):
    """历史指纹采集 Step — 加载已有用例 summary 并按需增量更新。"""

    name: ClassVar[str] = "history_fingerprint"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["raw_signals"]
    produces: ClassVar[List[str]] = ["history_fingerprints"]

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
        raw = f"{self.name}:{self.version}:project={project_id}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        raw_signals = ctx.get_artifact("raw_signals")
        if raw_signals is None:
            return StepResult(
                success=False,
                error="缺少 raw_signals 产物",
            )

        project_id = raw_signals.get("project_id")
        if not project_id:
            return StepResult(
                success=False,
                error="raw_signals 缺少 project_id",
            )

        stale_count = _detect_stale_summaries(ctx, project_id)
        backfilled_count = 0
        if stale_count > 0:
            logger.info(
                "检测到 {} 条过期 summary，触发增量重算 (project_id={})",
                stale_count, project_id,
            )
            backfilled_count = _incremental_backfill(ctx, project_id)

        fingerprints = _load_fingerprints(ctx, project_id)

        payload = {
            "project_id": project_id,
            "fingerprints": fingerprints,
            "total_count": len(fingerprints),
            "stale_backfilled_count": backfilled_count,
        }

        confidence = _compute_fingerprint_confidence(fingerprints)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="history_fingerprints",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "project_id": project_id,
                "total_count": len(fingerprints),
                "stale_backfilled_count": backfilled_count,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "fingerprints", "total_count", "stale_backfilled_count"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        project_id = 0
        if ctx is not None:
            raw_signals = ctx.get_artifact("raw_signals")
            if raw_signals:
                project_id = raw_signals.get("project_id", 0)

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "fingerprints": [],
                "total_count": 0,
                "stale_backfilled_count": 0,
            },
            artifact_kind="history_fingerprints",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )


def _load_fingerprints(
    ctx: PipelineContext,
    project_id: int,
    module: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """加载项目下所有非 archived 用例的指纹数据。

    Args:
        ctx: Pipeline 运行时上下文。
        project_id: 项目 ID。
        module: 可选模块过滤。
        limit: 分页大小，默认 1000。
        offset: 分页偏移，默认 0。
    """
    from app.models.test_case import TestCase

    query = ctx.db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.lifecycle_status != "archived",
        TestCase.is_deleted.is_(False),
    )

    if module is not None:
        query = query.filter(TestCase.module == module)

    cases = query.order_by(TestCase.id).offset(offset).limit(limit).all()

    fingerprints = []
    for case in cases:
        fp = {
            "case_id": case.id,
            "title": case.title or "",
            "module": case.module or "",
            "summary": case.summary or "",
            "summary_version": case.summary_version or 0,
            "summary_model_version": case.summary_model_version or "",
            "lifecycle_status": case.lifecycle_status or "draft",
            "priority": case.priority or 3,
        }
        fingerprints.append(fp)

    return fingerprints


def _detect_stale_summaries(ctx: PipelineContext, project_id: int) -> int:
    """检测 model_version 不匹配的过期 summary 数量。"""
    from app.models.test_case import TestCase
    from sqlalchemy import func

    current_model_version = _get_current_model_version(ctx)

    count = (
        ctx.db.query(func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.lifecycle_status != "archived",
            TestCase.is_deleted.is_(False),
            TestCase.summary.isnot(None),
            TestCase.summary != "",
            TestCase.summary_model_version != current_model_version,
        )
        .scalar()
    )

    return count or 0


def _incremental_backfill(ctx: PipelineContext, project_id: int) -> int:
    """增量重算过期 summary，返回重算数量。"""
    from app.models.test_case import TestCase

    current_model_version = _get_current_model_version(ctx)

    stale_cases = (
        ctx.db.query(TestCase)
        .filter(
            TestCase.project_id == project_id,
            TestCase.lifecycle_status != "archived",
            TestCase.is_deleted.is_(False),
            TestCase.summary.isnot(None),
            TestCase.summary != "",
            TestCase.summary_model_version != current_model_version,
        )
        .all()
    )

    backfilled = 0
    for case in stale_cases:
        if not ctx.check_budget():
            logger.warning(
                "预算不足，增量回填在 {} 条后停止 (project_id={})",
                backfilled, project_id,
            )
            break
        try:
            prompt = _build_summary_prompt(case)
            response = ctx.ai_client.complete(
                prompt=prompt,
                system="你是一个测试用例摘要生成助手。",
                temperature=0.3,
                max_tokens=300,
                metadata={
                    "step_name": "history_fingerprint_backfill",
                    "case_id": case.id,
                    "run_id": ctx.run.id,
                },
            )
            summary = response.content.strip()
            if summary:
                case.summary = summary
                case.summary_version = (case.summary_version or 0) + 1
                case.summary_model_version = current_model_version
                backfilled += 1
        except Exception as e:
            logger.warning(
                "增量回填用例 #{} summary 失败: {}", case.id, e,
            )

    if backfilled > 0:
        ctx.db.flush()

    return backfilled


def _build_summary_prompt(case: Any) -> str:
    """构建 summary 生成 prompt。"""
    steps_text = "无"
    if case.steps_json:
        try:
            steps_text = json.dumps(case.steps_json, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            steps_text = str(case.steps_json)

    parts = [
        f"用例标题: {case.title or '无标题'}",
        f"前置条件: {case.precondition or '无'}",
        f"测试步骤: {steps_text}",
        f"预期结果: {case.expected_result or '无'}",
    ]
    return (
        "请为以下测试用例生成一段简洁的中文摘要（不超过200字），"
        "概括用例的测试目的和关键验证点：\n\n"
        + "\n".join(parts)
    )


def _get_current_model_version(ctx: PipelineContext) -> str:
    """获取当前 AI 模型版本标识。"""
    for attr in ("model_name", "model", "_model"):
        val = getattr(ctx.ai_client, attr, None)
        if val is not None:
            return str(val)
    return "unknown"


def _compute_fingerprint_confidence(fingerprints: List[Dict[str, Any]]) -> float:
    """计算指纹产物的置信度。

    规则：
        - 0 条指纹 → 0.0（新项目，无历史）
        - 有指纹但 summary 覆盖率 < 50% → 0.5
        - summary 覆盖率 ≥ 50% → 0.8
        - summary 覆盖率 100% → 1.0
    """
    if not fingerprints:
        return 0.0

    with_summary = sum(1 for fp in fingerprints if fp.get("summary"))
    coverage = with_summary / len(fingerprints)

    if coverage >= 1.0:
        return 1.0
    if coverage >= 0.5:
        return 0.8
    return 0.5
