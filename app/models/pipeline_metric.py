"""
Pipeline 监控指标模型模块

本模块定义 pipeline_metrics 表，记录 FMEA 失败模式检测指标。
对应 plan §8 FMEA 表中 F1/F2/F3/F5/F9/F11/F12/F13/F14/F15 各项。

核心类概览：
    - PipelineMetric : 监控指标记录，按 (metric_name, run_id, step_name) 聚合

指标枚举（FMEA_ID → metric_name）：
    F1  low_confidence_pause       — artifact.confidence < 0.7 + Pipeline 暂停
    F2  json_validation_failure    — AI 返回 JSON 校验失败
    F3  conflict_detected          — 双向扫描红色冲突
    F5  confirmed_zero_edit        — 用户零编辑确认（敷衍确认）
    F9  pipeline_recovery          — Pipeline 中断恢复
    F11 token_budget_exceeded      — Token 预算超限
    F12 fallback_model_used        — Fallback 模型调用
    F13 review_undo                — 评审撤销
    F14 pipeline_version_rerun     — Pipeline 版本升级触发强制重跑
    F15 audit_log_write_failure    — 审计日志写入失败

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳
    - app.db.database.Base     : SQLAlchemy 声明性基类
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, Index, text
from app.utils.db_time import utcnow
from app.db.database import Base


FMEA_METRICS = {
    "low_confidence_pause": {"fmea_id": "F1", "description": "低置信度暂停（confidence < 0.7）"},
    "json_validation_failure": {"fmea_id": "F2", "description": "AI 返回 JSON 校验失败"},
    "conflict_detected": {"fmea_id": "F3", "description": "双向扫描红色冲突"},
    "confirmed_zero_edit": {"fmea_id": "F5", "description": "用户零编辑确认"},
    "pipeline_recovery": {"fmea_id": "F9", "description": "Pipeline 中断恢复"},
    "token_budget_exceeded": {"fmea_id": "F11", "description": "Token 预算超限"},
    "fallback_model_used": {"fmea_id": "F12", "description": "Fallback 模型调用"},
    "review_undo": {"fmea_id": "F13", "description": "评审撤销"},
    "pipeline_version_rerun": {"fmea_id": "F14", "description": "Pipeline 版本升级强制重跑"},
    "audit_log_write_failure": {"fmea_id": "F15", "description": "审计日志写入失败"},
    "posterior_quality_score": {"fmea_id": "F16", "description": "后验质量分（review+execution+modification 加权）"},
    "review_rejection_rate_high": {"fmea_id": "F17", "description": "评审拒绝率超过阈值（>30%）"},
}

VALID_METRIC_NAMES = set(FMEA_METRICS.keys())


class PipelineMetric(Base):
    """Pipeline 监控指标模型

    记录 FMEA 失败模式检测指标，支持按指标名、项目、迭代、运行等维度聚合查询。

    表关系：
        - 逻辑关联 PipelineRun（run_id，非 FK，避免级联删除丢失指标）
        - 逻辑关联 Iteration（iteration_id，非 FK）
    """
    __tablename__ = "pipeline_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(
        String(64), nullable=False, index=True,
        comment="指标名（FMEA 枚举值）",
    )
    value = Column(Float, nullable=False, default=1.0, server_default=text("1.0"), comment="指标值（通常为计数 1.0）")
    project_id = Column(Integer, nullable=True, index=True, comment="项目 ID")
    iteration_id = Column(Integer, nullable=True, comment="迭代 ID")
    run_id = Column(Integer, nullable=True, comment="PipelineRun ID")
    step_name = Column(String(64), nullable=True, comment="Step 名称")
    detail = Column(JSON, nullable=True, comment="附加详情（如 confidence 值、错误信息）")
    created_at = Column(
        DateTime, nullable=False, default=utcnow,
        server_default=text("UTC_TIMESTAMP"), comment="记录时间",
    )

    __table_args__ = (
        Index("ix_pipeline_metrics_name_project", "metric_name", "project_id"),
        Index("ix_pipeline_metrics_created_at", "created_at"),
    )
