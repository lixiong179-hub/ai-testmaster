"""
A/B测试指标模型

用于记录A/B实验中各变体的指标数据，支持实验效果对比分析。
支持指标名称包括：步骤可执行率、需求对齐率、无关元素引入率、
上下文token数、人工二次修改率、evidence_refs准确率、
历史低可信过滤准确率、上下文完整性评分有效性等。
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, JSON
from app.utils.db_time import utcnow
from app.db.database import Base


class ABTestMetric(Base):
    """A/B测试指标记录模型，每条记录对应一次实验中某变体的一个指标采样"""
    __tablename__ = "ab_test_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    experiment_id = Column(String(64), nullable=False, index=True, comment="实验ID")
    variant = Column(String(32), nullable=False, comment="变体标识: control/treatment")
    project_id = Column(Integer, nullable=True, index=True)
    test_point_id = Column(Integer, nullable=True)
    metric_name = Column(String(64), nullable=False, comment="指标名称")
    metric_value = Column(Float, nullable=False, comment="指标值")
    detail = Column(JSON, nullable=True, comment="指标详情JSON")
    created_at = Column(DateTime, default=utcnow, nullable=False)
