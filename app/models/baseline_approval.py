"""基线审批模型 - BaselineApproval。

业务用途：
    BaselineApproval 记录 Diff 审批历史，包括审批动作（approve/reject/
    update_baseline）、审批意见与审批人。审批通过后可触发基线更新流程，
    旧基线版本归档，新版本激活。

表关系：
    - Project → BaselineApproval（一对多，project_id 关联）
    - VisualDiff → BaselineApproval（一对多，diff_id 关联）
    - VisualBaseline → BaselineApproval（一对多，baseline_id 关联）
    - User → BaselineApproval（一对多，reviewer_id 关联）

字段语义：
    - action      : 审批动作（approve/reject/update_baseline）
    - comment     : 审批意见（可空）
    - reviewer_id : 审批人用户 ID
    - reviewed_at : 审批时间
"""
from typing import Any, Dict

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from app.db.database import Base
from app.utils.db_time import utcnow


# 审批动作枚举值
APPROVAL_ACTION_VALUES = ("approve", "reject", "update_baseline")


class BaselineApproval(Base):
    """基线审批模型。

    每条记录描述一次 Diff 审批操作，包括审批人、动作与意见。审批通过后
    可触发基线更新流程（action=update_baseline），旧基线版本归档。

    使用场景：
        - 审批人在 Diff 协作工作流中审批 Diff
        - 审批历史审计追溯
        - 基线更新决策记录
    """

    __tablename__ = "baseline_approvals"
    __table_args__ = (
        # 复合索引：按项目+时间检索审批历史
        Index("idx_approval_project_time", "project_id", "reviewed_at"),
        # 复合索引：按 Diff 维度检索审批记录
        Index("idx_approval_diff", "diff_id"),
        # 复合索引：按基线维度检索审批历史
        Index("idx_approval_baseline", "baseline_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="审批主键ID")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    diff_id = Column(BigInteger, ForeignKey("visual_diffs.id", ondelete="CASCADE"), nullable=False, comment="关联的Diff ID")
    baseline_id = Column(BigInteger, ForeignKey("visual_baselines.id", ondelete="CASCADE"), nullable=False, comment="关联的基线ID")

    action = Column(String(32), nullable=False, comment="审批动作: approve/reject/update_baseline")
    comment = Column(Text, nullable=True, comment="审批意见")

    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="审批人用户ID")
    reviewed_at = Column(DateTime, default=utcnow, nullable=False, comment="审批时间（UTC）")
    created_at = Column(DateTime, default=utcnow, nullable=False, comment="创建时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<BaselineApproval(id={self.id}, diff_id={self.diff_id}, "
            f"action={self.action}, reviewer_id={self.reviewer_id})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回审批核心字段字典，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "diff_id": self.diff_id,
            "baseline_id": self.baseline_id,
            "action": self.action,
            "comment": self.comment,
            "reviewer_id": self.reviewer_id,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def validate_action(action: str) -> bool:
        """校验审批动作是否在允许枚举值内。"""
        return action in APPROVAL_ACTION_VALUES


__all__ = ["BaselineApproval", "APPROVAL_ACTION_VALUES"]
