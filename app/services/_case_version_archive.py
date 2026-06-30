"""测试用例版本归档与变更字段构建模块

从 case_version_service.py 拆分，包含版本保留策略归档、changed_fields 构建
与相关常量。所有函数均为模块级纯函数，由 CaseVersionService 类方法薄委托调用。
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_case_version import TestCaseVersion

# 需要追踪变更的核心字段
TRACKED_FIELDS: List[str] = [
    "title", "module", "precondition", "steps_json",
    "expected_result", "priority",
]

# 版本保留策略阈值
MAX_VERSIONS_PER_CASE: int = 50
ARCHIVE_OLDER_THAN_DAYS: int = 90


def archive_old_versions(db: Session, test_case_id: int) -> None:
    """归档超过保留策略的旧版本

    当同一用例的版本数超过 MAX_VERSIONS_PER_CASE 时，
    将 ARCHIVE_OLDER_THAN_DAYS 天前的旧快照的 snapshot_data 置空，
    保留元数据供审计追溯。

    Args:
        db: 数据库会话。
        test_case_id: 用例ID。
    """
    total = db.query(TestCaseVersion).filter(
        TestCaseVersion.test_case_id == test_case_id,
    ).count()

    if total <= MAX_VERSIONS_PER_CASE:
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_OLDER_THAN_DAYS)
    old_versions = (
        db.query(TestCaseVersion)
        .filter(
            TestCaseVersion.test_case_id == test_case_id,
            TestCaseVersion.created_at < cutoff,
            TestCaseVersion.snapshot_data.isnot(None),
        )
        .order_by(TestCaseVersion.version_number.asc())
        .all()
    )

    archived_count = 0
    for ver in old_versions:
        if total - archived_count <= MAX_VERSIONS_PER_CASE:
            break
        ver.snapshot_data = None
        archived_count += 1

    if archived_count > 0:
        db.flush()
        logger.info(
            f"版本归档完成: case_id={test_case_id}, "
            f"archived={archived_count}, remaining={total - archived_count}"
        )


def build_changed_fields_from_state(
    case: TestCase,
    state: Any,
) -> Dict[str, Dict[str, Any]]:
    """根据 SQLAlchemy instance state 构建 changed_fields

    对比追踪字段的新旧值，只记录真正变更的字段。

    Args:
        case: TestCase 实例（保留参数以兼容调用契约，函数体内不使用）。
        state: SQLAlchemy inspect 返回的 instance state。

    Returns:
        变更字段字典，格式 {"field_name": {"old": old_val, "new": new_val}}。
    """
    changed_fields: Dict[str, Dict[str, Any]] = {}
    for field in TRACKED_FIELDS:
        hist = getattr(state.attrs, field, None)
        if hist is None:
            continue
        history = hist.history
        if history.deleted or history.added:
            old_val = history.deleted[0] if history.deleted else None
            new_val = history.added[0] if history.added else None
            if old_val != new_val:
                changed_fields[field] = {"old": old_val, "new": new_val}
    return changed_fields
