"""S13 Persist — 用例持久化 Step

将生成的测试用例写入数据库，
设置 lifecycle_status、关联测试点、生成用例编号。

实现拆分为以下子模块（均为内部 API）：
    - _persist_utils: JSON/日期解析、评分映射、步骤持久化
    - _persist_writer: 主持久化循环（生命周期锁、用例构建）
    - _persist_consistency: 持久化数量一致性校验
    - _persist_posterior: 后验评分触发
"""
import threading
from typing import Any, ClassVar, Dict, List, Optional

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.steps._persist_consistency import _run_consistency_check
from app.pipelines.steps._persist_posterior import _trigger_posterior_scoring
from app.pipelines.steps._persist_utils import _build_score_map
from app.pipelines.steps._persist_writer import _persist_generated_cases

# 保留私有 API 导出，供 tests/pipelines/test_persist_helpers.py 等使用
__all__ = ["Persist", "_build_score_map"]


class Persist(PipelineStep):
    """用例持久化 Step — 将生成的用例落库。"""

    name: ClassVar[str] = "persist"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases", "quality_scores"]
    produces: ClassVar[List[str]] = ["persisted_case_ids"]
    # 类级初始化避免懒初始化的 TOCTOU 竞态：
    # 若在方法内 `if not hasattr(...): Lock()` 判断与赋值之间可能两个线程同时进入，
    # 创建两个不同的 Lock 实例导致锁失效。
    _lifecycle_lock: ClassVar[threading.Lock] = threading.Lock()

    def should_run(self, ctx: PipelineContext) -> bool:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        # 持久化步骤不应缓存，每次都需实际写入数据库
        return ""

    def execute(self, ctx: PipelineContext) -> StepResult:
        cases_artifact = ctx.get_artifact("generated_cases")
        scores_artifact = ctx.get_artifact("quality_scores")

        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        generated_cases = cases_artifact.get("generated_cases", [])
        project_id = cases_artifact.get("project_id")
        score_map = _build_score_map(scores_artifact)

        persisted_ids, failed_persist = _persist_generated_cases(
            ctx,
            generated_cases,
            project_id,
            score_map,
            cases_artifact.get("has_ui", False),
            Persist._lifecycle_lock,
        )

        if not persisted_ids:
            return StepResult(
                success=False,
                error="所有用例持久化失败",
            )

        # --- 一致性校验 ---
        consistency_check, artifact_confidence_val = _run_consistency_check(
            ctx, persisted_ids,
        )

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "persisted_case_ids": persisted_ids,
            "total_persisted": len(persisted_ids),
            "failed_persist": failed_persist,
            "consistency_check": consistency_check,
        }

        posterior_result = _trigger_posterior_scoring(ctx, project_id)
        if posterior_result is not None:
            payload["posterior_scoring"] = posterior_result

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="persisted_case_ids",
            artifact_confidence=artifact_confidence_val,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "persisted_count": len(persisted_ids),
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "persisted_case_ids" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"用例持久化降级: {error}",
            degraded=True,
        )
