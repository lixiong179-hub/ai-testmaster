"""测试覆盖率映射模型（Phase 1 Task 4：Test Impact Analysis）

业务用途：持久化"测试用例 ↔ 代码文件行范围"映射，供 TIA 增量分析查询。
设计原则：
1. 单条记录描述一个测试用例对单个代码文件的覆盖区间；
2. (test_case_id, file_path) 复合索引覆盖按用例/文件双向检索高频查询；
3. project_id 冗余存储，避免 JOIN test_cases 表，加速按项目过滤；
4. test_name 仅用于调试与日志，不参与业务逻辑判定。

表关系：
    - 外键 → projects（ondelete=CASCADE，项目删除时映射级联清理）
    - 外键 → test_cases（ondelete=CASCADE，用例删除时映射级联清理）
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
)

from app.db.database import Base
from app.utils.db_time import utcnow


class TestCoverageMap(Base):
    """测试覆盖率映射模型：单条记录 = 单个用例对单个代码文件的覆盖区间。

    使用场景：
        - TIA 启动时按 project_id 批量加载，构造 CoverageEntry 列表传入 ImpactScheduler；
        - 测试执行完成后由集成服务写入新映射或更新已有行（upsert by test_case_id+file_path）；
        - 管理员 API 查询覆盖率映射状态、统计覆盖率覆盖度。
    """

    __tablename__ = "test_coverage_maps"
    __table_args__ = (
        # 复合索引：覆盖按用例维度检索其覆盖的所有文件
        Index("idx_coverage_case", "test_case_id"),
        # 复合索引：覆盖按文件维度检索所有覆盖该文件的用例（TIA 主查询路径）
        Index("idx_coverage_file", "file_path"),
        # 复合索引：覆盖按项目维度批量加载（TIA 冷启动主路径）
        Index("idx_coverage_project_file", "project_id", "file_path"),
        # 唯一约束：同一用例对同一文件仅保留一条映射（upsert 唯一键）
        Index("uq_case_file", "test_case_id", "file_path", unique=True),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="覆盖率映射主键ID")
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="项目ID（冗余存储，加速按项目过滤避免 JOIN）",
    )
    test_case_id = Column(
        Integer,
        ForeignKey("test_cases.id", ondelete="CASCADE"),
        nullable=False,
        comment="测试用例ID",
    )
    file_path = Column(
        String(512),
        nullable=False,
        comment="相对项目根目录的代码文件路径，如 app/services/foo.py",
    )
    line_start = Column(Integer, nullable=False, comment="覆盖起始行号（1-based，包含）")
    line_end = Column(Integer, nullable=False, comment="覆盖结束行号（1-based，包含）")
    test_name = Column(
        String(256),
        nullable=False,
        default="",
        comment="测试函数名，仅用于调试与日志，不参与业务逻辑",
    )
    created_at = Column(DateTime, default=utcnow, nullable=False, comment="记录创建时间（UTC）")
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
        comment="记录更新时间（UTC）",
    )

    def __repr__(self) -> str:
        return (
            f"<TestCoverageMap(id={self.id}, case_id={self.test_case_id}, "
            f"file={self.file_path}, lines={self.line_start}-{self.line_end})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """返回映射核心字段字典，供 API 响应与日志输出使用。"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "test_case_id": self.test_case_id,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "test_name": self.test_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["TestCoverageMap"]
