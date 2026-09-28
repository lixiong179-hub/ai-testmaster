"""视觉校验编排 mixin（Task 9 拆分）。

将一站式视觉校验流程（run_visual_check）与 Token 预算预检从 sdk.py 抽出，
保持 sdk.py 主类聚焦门面编排与基础 CRUD，控制单文件行数。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.services.visual_ai._sdk_helpers import (
    build_diff_record,
    build_dom_diff_report,
    load_baseline_dom,
    persist_diff_image,
)
from app.services.visual_ai.comparison_engine import (
    ComparisonEngine,
    LLMAnalysisResult,
)
from app.services.visual_ai.token_estimator import VisualTokenBudgetGuard


@dataclass
class VisualCheckResult:
    """一站式视觉校验结果。

    Attributes:
        baseline_id       : 对比的基线 ID（无基线时为 None）
        diff_id           : 创建的 Diff 记录 ID
        diff_percentage   : 像素差异百分比
        diff_pixel_count  : 差异像素数
        match_level       : 使用的对比模式
        status            : Diff 状态（auto_approved/pending）
        llm_analysis      : LLM 语义分析结果（未执行时为 None）
        token_cost        : 实际 Token 消耗
        token_estimated   : 预估 Token 消耗
        llm_skipped       : LLM 是否被跳过（预算超限或未启用）
        skip_reason       : LLM 跳过原因
        diff_report       : Markdown Diff 报告
    """

    baseline_id: Optional[int]
    diff_id: Optional[int]
    diff_percentage: float
    diff_pixel_count: int
    match_level: str
    status: str
    llm_analysis: Optional[LLMAnalysisResult] = None
    token_cost: int = 0
    token_estimated: int = 0
    llm_skipped: bool = False
    skip_reason: str = ""
    diff_report: str = ""


class VisualCheckMixin:
    """一站式视觉校验编排 mixin。

    依赖宿主类提供的属性：
        _db / _storage / _ai_client / _redis_client / _baseline_service / _estimator
    以及方法：get_baseline。
    """

    async def run_visual_check(
        self,
        project_id: int,
        page_url: str,
        viewport_width: int,
        viewport_height: int,
        current_image_bytes: bytes,
        match_level: Optional[str] = None,
        test_case_id: Optional[int] = None,
        test_result_id: Optional[int] = None,
        current_dom_html: Optional[str] = None,
        created_by: Optional[int] = None,
    ) -> VisualCheckResult:
        """一站式视觉校验：对比 + 自动审批 + LLM 分析 + 预算守卫。

        流程：
            1. 查询活跃基线（无基线返回 skip）
            2. 预估 LLM Token 消耗，预算超限则跳过 LLM
            3. 执行像素对比 + 可选 LLM 语义分析
            4. 差异低于阈值自动审批，否则进入 pending 队列
            5. 生成 Markdown Diff 报告（含 DOM 对比）
            6. 持久化 Diff 记录与 Diff 图片
        """
        # 1. 查询活跃基线
        baseline = await self.get_baseline(
            project_id=project_id,
            page_url=page_url,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        if baseline is None:
            return VisualCheckResult(
                baseline_id=None,
                diff_id=None,
                diff_percentage=0.0,
                diff_pixel_count=0,
                match_level=match_level or "strict",
                status="skipped",
                skip_reason="no_baseline",
            )

        baseline_image = await self._baseline_service.load_baseline_image(baseline.id)
        effective_match_level = match_level or baseline.match_level

        # 2. Token 预检：预算超限则跳过 LLM
        llm_skipped, skip_reason, token_estimated = self._check_token_budget(
            project_id=project_id,
            baseline_image=baseline_image,
            current_image_bytes=current_image_bytes,
            effective_match_level=effective_match_level,
        )

        # 3. 执行对比
        engine = ComparisonEngine(
            ai_client=self._ai_client,
            llm_analysis_threshold=settings.VISUAL_AI_LLM_ANALYSIS_THRESHOLD,
            llm_token_limit=settings.VISUAL_AI_LLM_TOKEN_LIMIT,
        )
        result = await engine.compare(
            baseline_bytes=baseline_image,
            current_bytes=current_image_bytes,
            match_level=effective_match_level,
            enable_llm_analysis=not llm_skipped,
        )

        # 4. 自动审批
        diff_status = (
            "auto_approved"
            if result.diff_percentage < settings.VISUAL_AI_AUTO_APPROVE_THRESHOLD
            else "pending"
        )

        # 5. DOM 对比报告（可选）
        dom_diff = await load_baseline_dom(
            storage=self._storage,
            baseline=baseline,
            current_dom_html=current_dom_html or "",
        )
        llm_desc = result.llm_analysis.description if result.llm_analysis else ""
        diff_report = build_dom_diff_report(
            pixel_diff_percentage=result.diff_percentage,
            dom_diff=dom_diff,
            llm_description=llm_desc,
        )

        # 6. 持久化 Diff 记录
        diff_record = build_diff_record(
            project_id=project_id,
            baseline=baseline,
            result=result,
            test_case_id=test_case_id,
            test_result_id=test_result_id,
            diff_status=diff_status,
        )
        self._db.add(diff_record)
        await self._db.commit()
        await self._db.refresh(diff_record)

        # 保存 Diff 图片（如有）
        if result.diff_image:
            await persist_diff_image(
                storage=self._storage,
                db=self._db,
                diff_record=diff_record,
                diff_image=result.diff_image,
                project_id=project_id,
                page_url=page_url,
                baseline_id=baseline.id,
                diff_pixel_count=result.diff_pixel_count,
            )

        return VisualCheckResult(
            baseline_id=baseline.id,
            diff_id=diff_record.id,
            diff_percentage=result.diff_percentage,
            diff_pixel_count=result.diff_pixel_count,
            match_level=result.match_level,
            status=diff_status,
            llm_analysis=result.llm_analysis,
            token_cost=result.total_token_cost,
            token_estimated=token_estimated,
            llm_skipped=llm_skipped,
            skip_reason=skip_reason,
            diff_report=diff_report,
        )

    def _check_token_budget(
        self,
        *,
        project_id: int,
        baseline_image: bytes,
        current_image_bytes: bytes,
        effective_match_level: str,
    ) -> tuple[bool, str, int]:
        """Token 预检：判断是否应跳过 LLM 分析。

        Returns:
            tuple[llm_skipped, skip_reason, token_estimated]
        """
        if self._ai_client is None or not settings.VISUAL_AI_ENABLED:
            return True, "ai_client_unavailable", 0

        estimate = self._estimator.estimate_comparison(
            baseline_bytes=baseline_image,
            current_bytes=current_image_bytes,
            match_level=effective_match_level,
            enable_llm_analysis=True,
        )
        token_estimated = estimate.total_tokens
        guard = VisualTokenBudgetGuard(
            redis_client=self._redis_client,
            project_id=project_id,
        )
        if guard.check_single_call(token_estimated):
            return True, "single_call_token_exceeded", token_estimated
        if guard.is_daily_budget_exhausted():
            return True, "daily_budget_exhausted", token_estimated
        return False, "", token_estimated


__all__ = ["VisualCheckResult", "VisualCheckMixin"]
