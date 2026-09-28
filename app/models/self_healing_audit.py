"""
自愈审计日志模型模块

本模块定义 SelfHealingAudit 模型，记录 UI 自动化执行过程中触发"自愈"的
每一次决策痕迹，用于事后回溯、置信度复核与 Token 成本核算。

核心类概览：
    - SelfHealingAudit : 自愈审计日志模型

表关系：
    ElementLocator → SelfHealingAudit（外键关联 element_locators.id，
                                    ondelete=SET NULL 保证定位器被清理时
                                    审计记录仍保留，仅 locator_id 置空）

字段语义：
    - failure_type : 失败原因分类（element_gone/dom_changed/load_delay/env_noise）
    - strategy     : 自愈策略（mcp/vision/stagehand/rollback/retry/skip）
    - confidence   : 自愈决策置信度（0.00-1.00），低于阈值时 low_confidence=True
    - token_cost   : 本次自愈消耗的 LLM Token 数（MCP/Vision/Stagehand 策略才会计）

依赖关系：
    - app.utils.db_time.utcnow : UTC 时间戳生成
    - app.db.database.Base     : SQLAlchemy 声明性基类（ModelBase 已注入到 MRO）

审计设计要点：
    1. 表本身只追加（append-only），不提供更新接口，保证审计痕迹不可篡改；
    2. locator_id 外键 ondelete=SET NULL，定位器被删除时审计记录保留、仅置空引用；
    3. (test_case_id, step_index) 复合索引覆盖按用例步骤维度检索的高频查询。
"""
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    Numeric,
    String,
)

from app.db.database import Base
from app.utils.db_time import utcnow


# 失败原因与自愈策略枚举值常量，集中维护便于校验与文档对齐
FAILURE_TYPE_VALUES = ("element_gone", "dom_changed", "load_delay", "env_noise")
STRATEGY_VALUES = ("mcp", "vision", "stagehand", "rollback", "retry", "skip")


class SelfHealingAudit(Base):
    """
    自愈审计日志模型

    每条记录描述一次自愈事件：哪个用例的哪一步、定位器原始选择器与修复后
    选择器、触发原因、采用策略、置信度与 Token 成本，以及是否落入低置信度
    人工复核通道。

    表关系：
        - 外键关联 → ElementLocator（locator_id，ondelete=SET NULL，
                                    定位器删除时审计记录保留、仅置空引用）

    使用场景：
        - 自愈引擎决策落库，供事后回溯与统计
        - 低置信度记录聚合后供人工复核
        - 按 test_case_id/step_index 检索历史自愈痕迹，辅助回归
    """
    __tablename__ = "self_healing_audits"
    __table_args__ = (
        # 复合索引：覆盖按用例步骤维度检索自愈记录的高频查询
        Index("idx_case_step", "test_case_id", "step_index"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自愈审计记录主键ID")  # 自增主键
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True, comment="触发自愈的测试用例ID")  # 用例ID，外键关联 test_cases，单列索引辅助按用例筛选
    step_index = Column(Integer, nullable=False, comment="触发自愈的步骤序号（0-based）")  # 步骤序号
    locator_id = Column(Integer, ForeignKey("element_locators.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联的元素定位器ID（外键关联，定位器删除时置 NULL 保留审计记录）")  # 元素定位器ID，单列索引辅助按定位器检索

    old_selector = Column(String(512), nullable=True, comment="自愈前选择器（CSS/XPath 等）")  # 自愈前选择器
    new_selector = Column(String(512), nullable=True, comment="自愈后选择器（CSS/XPath 等）")  # 自愈后选择器

    failure_type = Column(String(32), nullable=False, comment="失败原因: element_gone/dom_changed/load_delay/env_noise")  # 失败原因分类
    strategy = Column(String(32), nullable=False, comment="自愈策略: mcp/vision/stagehand/rollback/retry/skip")  # 自愈策略

    confidence = Column(Numeric(5, 2), nullable=True, comment="自愈决策置信度（0.00-1.00），NULL 表示策略无需置信度")  # 置信度
    token_cost = Column(Integer, nullable=False, default=0, comment="本次自愈消耗的LLM Token数（非AI策略为0）")  # Token消耗
    low_confidence = Column(Boolean, nullable=False, default=False, comment="是否低于置信度阈值（人工复核标记）")  # 低置信度标记

    created_at = Column(DateTime, default=utcnow, comment="记录创建时间（UTC）")  # 创建时间

    def __repr__(self) -> str:
        """返回审计记录的字符串表示，便于调试与日志输出。"""
        return (
            f"<SelfHealingAudit(id={self.id}, case_id={self.test_case_id}, "
            f"step={self.step_index}, strategy={self.strategy}, "
            f"confidence={self.confidence})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        将审计记录转换为字典格式，供 API 响应与日志输出使用。

        Returns:
            Dict[str, Any]: 包含审计记录核心字段的字典。
        """
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "step_index": self.step_index,
            "locator_id": self.locator_id,
            "old_selector": self.old_selector,
            "new_selector": self.new_selector,
            "failure_type": self.failure_type,
            "strategy": self.strategy,
            "confidence": float(self.confidence) if self.confidence is not None else None,
            "token_cost": self.token_cost,
            "low_confidence": self.low_confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def validate_failure_type(failure_type: Optional[str]) -> bool:
        """
        校验失败原因是否在允许的枚举值内。

        Args:
            failure_type: 失败原因字符串

        Returns:
            bool: 是否为合法的失败原因
        """
        return failure_type in FAILURE_TYPE_VALUES

    @staticmethod
    def validate_strategy(strategy: Optional[str]) -> bool:
        """
        校验自愈策略是否在允许的枚举值内。

        Args:
            strategy: 自愈策略字符串

        Returns:
            bool: 是否为合法的自愈策略
        """
        return strategy in STRATEGY_VALUES

    @staticmethod
    def validate_confidence(confidence: Optional[float]) -> bool:
        """
        校验置信度取值范围是否合法（0.00-1.00）。

        NULL 视为合法（rollback/retry/skip 等非 AI 策略可能无置信度）。

        Args:
            confidence: 置信度数值

        Returns:
            bool: 是否为合法的置信度取值
        """
        if confidence is None:
            return True
        try:
            value = float(confidence)
        except (TypeError, ValueError):
            return False
        return 0.0 <= value <= 1.0
