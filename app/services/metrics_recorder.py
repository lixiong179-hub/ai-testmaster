"""Pipeline 指标写入（fire-and-forget，sync）。

从 `metrics_service.py` 拆出（单文件 400 行上限）：只负责落库，不做查询。
设计要点与拆分前一致：

- `record_metric` / `record_metrics` 保持 **sync**：它们被 9+ 个 sync 调用点
  （pipelines/runner、ai/fallback_client、services/audit_service、endpoints/review_inbox
  等）以 fire-and-forget 方式调用，强行 async 化会导致调用链级联改造；
- 内部使用独立 Session（`get_db_context`）提交，不随主事务回滚而丢失。

指标查询（聚合 / 时序 / 仪表盘摘要）仍在 `app.services.metrics_service`。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.models.pipeline_metric import PipelineMetric, VALID_METRIC_NAMES


def record_metric(
    metric_name: str,
    *,
    value: float = 1.0,
    project_id: int | None = None,
    iteration_id: int | None = None,
    run_id: int | None = None,
    step_name: str | None = None,
    detail: dict[str, Any] | None = None,
) -> PipelineMetric | None:
    """记录单条监控指标（使用独立 Session 提交，不随主事务回滚丢失）。

    Args:
        metric_name: 指标名（必须为 VALID_METRIC_NAMES 中的值）。
        value: 指标值（默认 1.0，用于计数）。
        project_id: 项目 ID。
        iteration_id: 迭代 ID。
        run_id: PipelineRun ID。
        step_name: Step 名称。
        detail: 附加详情。

    Returns:
        创建后的 PipelineMetric 实例，失败返回 None。

    Raises:
        ValueError: metric_name 不在合法枚举中。
    """
    if metric_name not in VALID_METRIC_NAMES:
        raise ValueError(f"Invalid metric name: '{metric_name}'. Valid names: {sorted(VALID_METRIC_NAMES)}")

    record = PipelineMetric(
        metric_name=metric_name,
        value=value,
        project_id=project_id,
        iteration_id=iteration_id,
        run_id=run_id,
        step_name=step_name,
        detail=detail,
    )
    try:
        from app.db.database import get_db_context

        with get_db_context() as db:
            db.add(record)
            db.flush()
            db.expunge(record)
        return record
    except Exception as e:
        logger.debug(f"指标记录失败: {e}")
        return None


def record_metrics(
    metrics: list[dict[str, Any]],
) -> list[PipelineMetric]:
    """批量记录监控指标（使用独立 Session 提交）。

    Args:
        metrics: 指标字典列表，每个字典含 metric_name 及可选字段。

    Returns:
        创建后的 PipelineMetric 实例列表。
    """
    results = []
    for m in metrics:
        name = m.get("metric_name", "")
        if name not in VALID_METRIC_NAMES:
            continue
        result = record_metric(
            name,
            value=m.get("value", 1.0),
            project_id=m.get("project_id"),
            iteration_id=m.get("iteration_id"),
            run_id=m.get("run_id"),
            step_name=m.get("step_name"),
            detail=m.get("detail"),
        )
        if result is not None:
            results.append(result)
    return results


__all__ = ["record_metric", "record_metrics"]
