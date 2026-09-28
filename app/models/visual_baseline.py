"""视觉基线模型 - VisualBaseline。

业务用途：
    VisualBaseline 是 Visual AI 引擎的核心数据载体，持久化每个页面/视口的
    基线截图与配置。测试执行时，当前截图与基线对比生成 VisualDiff，实现
    视觉回归测试。

表关系：
    - Project → VisualBaseline（一对多，project_id 关联）
    - TestCase → VisualBaseline（一对多，test_case_id 可空，支持非用例绑定）
    - User → VisualBaseline（一对多，created_by 关联）
    - VisualBaseline → VisualDiff（一对多，baseline_id 关联）
    - VisualBaseline → BaselineApproval（一对多，baseline_id 关联）

字段语义：
    - image_key       : 基线截图在 StorageBackend 中的对象 key
    - dom_snapshot_key: DOM 快照存储 key，用于 Layout Match Level
    - match_level     : 对比模式（strict/layout/ignore_colors）
    - status          : 基线状态（active/archived/superseded）
    - version         : 基线版本号，每次更新基线递增
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
    Float,
)

from app.db.database import Base
from app.utils.db_time import utcnow


# 基线状态枚举值，集中维护便于校验
BASELINE_STATUS_VALUES = ("active", "archived", "superseded")
# Match Level 枚举值，三层对比模式
MATCH_LEVEL_VALUES = ("strict", "layout", "ignore_colors")


class VisualBaseline(Base):
    """视觉基线模型。

    每条记录描述一个页面+视口的基线截图与对比配置，是视觉回归测试的
    参照基准。基线可随 UI 演进更新，旧版本自动归档。

    使用场景：
        - 测试执行时按 page_url + viewport 查询当前基线
        - 基线更新时旧版本 status → superseded，新版本 status = active
        - Diff 协作工作流中审批人决定是否更新基线
    """

    __tablename__ = "visual_baselines"
    __table_args__ = (
        # 复合索引：按项目+页面+视口检索当前基线（测试执行主查询路径）
        Index("idx_baseline_project_page", "project_id", "page_url", "viewport_width", "viewport_height"),
        # 复合索引：按项目+状态检索活跃基线（基线管理页面）
        Index("idx_baseline_project_status", "project_id", "status"),
        # 复合索引：按用例维度检索基线
        Index("idx_baseline_test_case", "test_case_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="基线主键ID")
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="项目ID")
    test_case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联测试用例ID（可空，支持页面级基线）")

    name = Column(String(256), nullable=False, comment="基线名称，如 登录页-桌面端-1280x800")
    page_url = Column(String(1024), nullable=False, comment="被测页面URL")
    viewport_width = Column(Integer, nullable=False, comment="视口宽度（像素）")
    viewport_height = Column(Integer, nullable=False, comment="视口高度（像素）")

    image_key = Column(String(512), nullable=False, comment="基线截图在StorageBackend中的对象key")
    image_width = Column(Integer, nullable=False, default=0, comment="截图宽度（像素）")
    image_height = Column(Integer, nullable=False, default=0, comment="截图高度（像素）")

    match_level = Column(String(32), nullable=False, default="strict", comment="对比模式: strict/layout/ignore_colors")
    dom_snapshot_key = Column(String(512), nullable=True, comment="DOM快照存储key，用于Layout Match Level")

    status = Column(String(32), nullable=False, default="active", comment="基线状态: active/archived/superseded")
    version = Column(Integer, nullable=False, default=1, comment="基线版本号，每次更新递增")

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="创建者用户ID")
    created_at = Column(DateTime, default=utcnow, nullable=False, comment="创建时间（UTC）")
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False, comment="更新时间（UTC）")

    def __repr__(self) -> str:
        return (
            f"<VisualBaseline(id={self.id}, project_id={self.project_id}, "
            f"name={self.name}, version={self.version}, status={self.status})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回基线核心字段字典，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "test_case_id": self.test_case_id,
            "name": self.name,
            "page_url": self.page_url,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "image_key": self.image_key,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "match_level": self.match_level,
            "dom_snapshot_key": self.dom_snapshot_key,
            "status": self.status,
            "version": self.version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def validate_match_level(match_level: str) -> bool:
        """校验 Match Level 是否在允许枚举值内。"""
        return match_level in MATCH_LEVEL_VALUES

    @staticmethod
    def validate_status(status: str) -> bool:
        """校验基线状态是否在允许枚举值内。"""
        return status in BASELINE_STATUS_VALUES


__all__ = ["VisualBaseline", "BASELINE_STATUS_VALUES", "MATCH_LEVEL_VALUES"]
