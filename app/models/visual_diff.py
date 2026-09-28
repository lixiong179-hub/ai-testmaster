"""视觉差异模型 - VisualDiff。

业务用途：
    VisualDiff 记录每次视觉对比的结果，包括当前截图、差异图、差异指标
    与 LLM 语义分析结果。Diff 可被审批（approve/reject/update_baseline），
    审批通过后可更新基线。

表关系：
    - Project → VisualDiff（一对多，project_id 关联）
    - VisualBaseline → VisualDiff（一对多，baseline_id 关联）
    - TestCase → VisualDiff（一对多，test_case_id 可空）
    - TestResult → VisualDiff（一对多，test_result_id 可空）
    - VisualDiff → BaselineApproval（一对多，diff_id 关联）

字段语义：
    - diff_percentage : 差异百分比（0.0-100.0），像素对比结果
    - diff_pixel_count: 差异像素数
    - match_level     : 使用的 Match Level
    - status          : 审批状态（pending/approved/rejected/auto_approved）
    - llm_analysis    : LLM 语义分析结果（JSON 字符串，含分类/置信度/建议）
    - llm_token_cost  : LLM Token 消耗
"""
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from app.db.database import Base
from app.utils.db_time import utcnow


# Diff 审批状态枚举值
DIFF_STATUS_VALUES = ("pending", "approved", "rejected", "auto_approved")


class VisualDiff(Base):
    """视觉差异模型。

    每条记录描述一次视觉对比的结果，包括像素级差异指标与可选的 LLM 语义
    分析结果。Diff 进入 pending 状态后进入审批队列，审批人决定后续动作。

    使用场景：
        - 测试执行后自动创建 Diff 记录
        - diff_percentage < 阈值时自动审批为 auto_approved
        - 审批人查看 Diff 详情后决定 approve/reject/update_baseline
    """

    __tablename__ = "visual_diffs"
    __table_args__ = (
        # 复合索引：按项目+状态检索待审批 Diff（审批队列主查询）
        Index("idx_diff_project_status", "project_id", "status"),
        # 复合索引：按基线维度检索 Diff 历史
        Index("idx_diff_baseline", "baseline_id"),
        # 复合索引：按用例+测试结果维度检索 Diff
        Index("idx_diff_case_result", "test_case_id", "test_result_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="Diff主键ID")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    baseline_id = Column(BigInteger, ForeignKey("visual_baselines.id", ondelete="CASCADE"), nullable=False, comment="对比的基线ID")
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联测试用例ID")
    test_result_id = Column(Integer, ForeignKey("test_results.id", ondelete="SET NULL"), nullable=True, comment="关联测试结果ID")

    current_image_key = Column(String(512), nullable=False, comment="当前截图在StorageBackend中的对象key")
    diff_image_key = Column(String(512), nullable=True, comment="差异图存储key（高亮差异区域的叠加图）")

    diff_percentage = Column(Float, nullable=False, default=0.0, comment="差异百分比（0.0-100.0）")
    diff_pixel_count = Column(Integer, nullable=False, default=0, comment="差异像素数")
    total_pixel_count = Column(Integer, nullable=False, default=0, comment="总像素数（用于计算百分比）")

    match_level = Column(String(32), nullable=False, default="strict", comment="使用的对比模式: strict/layout/ignore_colors")

    status = Column(String(32), nullable=False, default="pending", comment="审批状态: pending/approved/rejected/auto_approved")

    llm_analysis = Column(Text, nullable=True, comment="LLM语义分析结果（JSON字符串，含分类/置信度/建议）")
    llm_token_cost = Column(Integer, nullable=False, default=0, comment="LLM Token消耗")

    created_at = Column(DateTime, default=utcnow, nullable=False, comment="创建时间（UTC）")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False, comment="更新时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<VisualDiff(id={self.id}, baseline_id={self.baseline_id}, "
            f"diff_percentage={self.diff_percentage}, status={self.status})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回 Diff 核心字段字典，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "baseline_id": self.baseline_id,
            "test_case_id": self.test_case_id,
            "test_result_id": self.test_result_id,
            "current_image_key": self.current_image_key,
            "diff_image_key": self.diff_image_key,
            "diff_percentage": self.diff_percentage,
            "diff_pixel_count": self.diff_pixel_count,
            "total_pixel_count": self.total_pixel_count,
            "match_level": self.match_level,
            "status": self.status,
            "llm_analysis": self.llm_analysis,
            "llm_token_cost": self.llm_token_cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def validate_status(status: str) -> bool:
        """校验审批状态是否在允许枚举值内。"""
        return status in DIFF_STATUS_VALUES


__all__ = ["VisualDiff", "DIFF_STATUS_VALUES"]
