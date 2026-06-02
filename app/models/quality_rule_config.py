"""质量规则配置模型。

存储项目级别的质量规则覆盖，每条规则以 (project_id, rule_key) 唯一标识。
rule_value 为 JSON 类型，存储规则的具体参数值。

示例:
    rule_key="title_min", rule_value=10
    rule_key="steps_min", rule_value=3
    rule_key="duplication_threshold", rule_value=0.85
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.sql import func

from app.db.database import Base


class QualityRuleConfig(Base):
    """项目级质量规则配置表。"""
    __tablename__ = "quality_rule_configs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联项目ID",
    )
    rule_key = Column(String(80), nullable=False, comment="规则键名")
    rule_value = Column(JSON, nullable=False, comment="规则值（JSON格式）")
    created_at = Column(
        DateTime, nullable=False, default=func.now(), comment="创建时间",
    )
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        Index(
            "ix_quality_rule_project_key",
            "project_id", "rule_key",
            unique=True,
        ),
    )
