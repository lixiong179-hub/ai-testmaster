"""Persist Step 后验评分触发。

根据配置开关触发后验质量评分，评分失败不阻断主流程。
"""
from typing import Any, Dict, Optional

from loguru import logger

from app.pipelines.context import PipelineContext


def _trigger_posterior_scoring(
    ctx: PipelineContext,
    project_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    """触发后验评分，返回 posterior_result 或 None。

    开关来源优先级：
    1. ctx 配置 ENABLE_POSTERIOR_SCORING；
    2. PipelineConfig 表的 enable_posterior_scoring 字段。

    评分失败时仅记录错误日志，返回 None，不阻断持久化主流程。

    Args:
        ctx: Pipeline 上下文，提供 db 会话与配置访问。
        project_id: 项目 ID。

    Returns:
        后验评分结果字典；未启用或失败时返回 None。
    """
    enable_posterior = ctx.get_config("ENABLE_POSTERIOR_SCORING", False)
    if not enable_posterior:
        from app.models.pipeline_config import PipelineConfig
        config_row = ctx.db.query(PipelineConfig).first()
        if config_row and getattr(config_row, "enable_posterior_scoring", False):
            enable_posterior = True

    if not enable_posterior:
        return None

    try:
        from app.services.posterior_quality_service import compute_and_persist_posterior
        posterior_result = compute_and_persist_posterior(ctx.db, project_id)
        logger.info(
            "后验评分已触发: project_id={}, score={}",
            project_id,
            posterior_result.get("posterior_quality_score"),
        )
        return posterior_result
    except Exception as e:
        logger.error("后验评分触发失败: project_id={}, error={}", project_id, e)
        return None
