"""
A/B测试指标服务

提供A/B实验指标的记录、汇总统计和实验列表查询能力。
汇总统计按变体分组计算均值、标准差和样本数，用于对比实验效果。
"""
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.ab_test_metric import ABTestMetric

# 合法的指标名称白名单，防止任意字段写入
VALID_METRIC_NAMES: set[str] = {
    "step_executable_rate",
    "requirement_alignment_rate",
    "irrelevant_element_rate",
    "context_token_count",
    "manual_revision_rate",
    "evidence_refs_accuracy",
    "history_filter_accuracy",
    "completeness_score_effectiveness",
    "completeness_score",
}


class ABTestService:
    """A/B测试指标服务，封装指标记录与统计查询逻辑"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_metric(
        self,
        experiment_id: str,
        variant: str,
        metric_name: str,
        metric_value: float,
        project_id: Optional[int] = None,
        test_point_id: Optional[int] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> ABTestMetric:
        """记录一条A/B测试指标数据

        Args:
            experiment_id: 实验标识
            variant: 变体标识（control/treatment）
            metric_name: 指标名称，必须在VALID_METRIC_NAMES白名单内
            metric_value: 指标值
            project_id: 项目ID（可选）
            test_point_id: 测试点ID（可选）
            detail: 指标详情JSON（可选）

        Returns:
            ABTestMetric: 已持久化的指标记录

        Raises:
            ValueError: metric_name不在合法白名单内
        """
        if metric_name not in VALID_METRIC_NAMES:
            raise ValueError(
                f"非法指标名称: {metric_name}，合法值为: {sorted(VALID_METRIC_NAMES)}"
            )
        row = ABTestMetric(
            experiment_id=experiment_id,
            variant=variant,
            project_id=project_id,
            test_point_id=test_point_id,
            metric_name=metric_name,
            metric_value=metric_value,
            detail=detail,
        )
        self.db.add(row)
        self.db.flush()
        self.db.refresh(row)
        return row

    def get_experiment_summary(
        self,
        experiment_id: str,
        project_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """获取实验汇总统计，按变体分组计算均值、标准差和样本数

        Args:
            experiment_id: 实验标识
            project_ids: 允许查看的项目ID列表，None表示不过滤

        Returns:
            包含experiment_id和variants统计字典的结果，
            variants的key为变体标识，value为各指标的统计信息
        """
        query = self.db.query(ABTestMetric).filter(
            ABTestMetric.experiment_id == experiment_id,
        )
        if project_ids is not None:
            query = query.filter(ABTestMetric.project_id.in_(project_ids))
        rows: List[ABTestMetric] = query.all()
        if not rows:
            return {"experiment_id": experiment_id, "variants": {}}

        # 按变体分组收集指标值
        grouped: Dict[str, Dict[str, List[float]]] = {}
        for row in rows:
            variant_key = row.variant
            if variant_key not in grouped:
                grouped[variant_key] = {}
            if row.metric_name not in grouped[variant_key]:
                grouped[variant_key][row.metric_name] = []
            grouped[variant_key][row.metric_name].append(row.metric_value)

        # 计算每个变体下每个指标的统计量
        variants: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for variant_key, metrics in grouped.items():
            variant_stats: Dict[str, Dict[str, Any]] = {}
            for name, values in metrics.items():
                count = len(values)
                mean_val = sum(values) / count if count > 0 else 0.0
                variance = (
                    sum((v - mean_val) ** 2 for v in values) / count
                    if count > 0
                    else 0.0
                )
                std_dev = math.sqrt(variance)
                variant_stats[name] = {
                    "mean": round(mean_val, 6),
                    "std_dev": round(std_dev, 6),
                    "sample_count": count,
                }
            variants[variant_key] = variant_stats

        return {"experiment_id": experiment_id, "variants": variants}

    def list_experiments(
        self,
        project_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """列出所有实验ID及其样本数

        Args:
            project_ids: 允许查看的项目ID列表，None表示不过滤

        Returns:
            实验列表，每个元素包含experiment_id和sample_count
        """
        query = self.db.query(
            ABTestMetric.experiment_id,
            func.count(ABTestMetric.id).label("sample_count"),
        )
        if project_ids is not None:
            query = query.filter(ABTestMetric.project_id.in_(project_ids))
        results = query.group_by(ABTestMetric.experiment_id).order_by(ABTestMetric.experiment_id).all()
        return [
            {"experiment_id": row.experiment_id, "sample_count": row.sample_count}
            for row in results
        ]
