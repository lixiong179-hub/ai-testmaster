"""测试用例版本查询与对比模块

从 case_version_service.py 拆分，包含版本对比、详情查询与快照解析工具。
所有函数均为模块级纯函数，由 CaseVersionService 类方法薄委托调用。
"""
import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.test_case_version import TestCaseVersion


def parse_snapshot_data(data: Any) -> Any:
    """解析 snapshot_data/changed_fields，兼容 JSON 字符串和 dict 类型

    Args:
        data: 原始数据（可能是 dict、str 或 None）。

    Returns:
        解析后的字典或原始值。
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
    return data


def compare_versions(
    db: Session,
    test_case_id: int,
    v1_id: int,
    v2_id: int,
) -> Dict[str, Any]:
    """对比两个版本，返回字段级 diff

    逐字段比较两个版本的 snapshot_data，输出每个字段的旧值和新值。

    Args:
        db: 数据库会话。
        test_case_id: 用例ID。
        v1_id: 旧版本ID。
        v2_id: 新版本ID。

    Returns:
        对比结果字典，包含 v1/v2 信息和字段级 diff。
        格式: {"v1": {...}, "v2": {...}, "diff": {"field": {"old": ..., "new": ...}}}

    Raises:
        ValueError: 版本不存在或不属于指定用例。
    """
    v1 = db.query(TestCaseVersion).filter(
        TestCaseVersion.id == v1_id,
        TestCaseVersion.test_case_id == test_case_id,
    ).first()
    v2 = db.query(TestCaseVersion).filter(
        TestCaseVersion.id == v2_id,
        TestCaseVersion.test_case_id == test_case_id,
    ).first()

    if not v1:
        raise ValueError(f"版本不存在: v1_id={v1_id}, test_case_id={test_case_id}")
    if not v2:
        raise ValueError(f"版本不存在: v2_id={v2_id}, test_case_id={test_case_id}")

    snap1 = parse_snapshot_data(v1.snapshot_data)
    snap2 = parse_snapshot_data(v2.snapshot_data)

    diff: Dict[str, Dict[str, Any]] = {}
    all_fields = set(list(snap1.keys()) + list(snap2.keys()))
    for field in all_fields:
        old_val = snap1.get(field)
        new_val = snap2.get(field)
        if old_val != new_val:
            diff[field] = {"old": old_val, "new": new_val}

    return {
        "v1": {
            "id": v1.id,
            "version_number": v1.version_number,
            "change_type": v1.change_type,
            "created_at": v1.created_at.isoformat() if v1.created_at else None,
        },
        "v2": {
            "id": v2.id,
            "version_number": v2.version_number,
            "change_type": v2.change_type,
            "created_at": v2.created_at.isoformat() if v2.created_at else None,
        },
        "diff": diff,
    }


def get_version(
    db: Session,
    test_case_id: int,
    version_id: int,
) -> Optional[Dict[str, Any]]:
    """获取版本详情

    Args:
        db: 数据库会话。
        test_case_id: 用例ID。
        version_id: 版本ID。

    Returns:
        版本详情字典，版本不存在时返回 None。
    """
    version = db.query(TestCaseVersion).filter(
        TestCaseVersion.id == version_id,
        TestCaseVersion.test_case_id == test_case_id,
    ).first()
    if not version:
        return None

    return {
        "id": version.id,
        "test_case_id": version.test_case_id,
        "version_number": version.version_number,
        "change_type": version.change_type,
        "change_description": version.change_description,
        "changed_fields": parse_snapshot_data(version.changed_fields),
        "snapshot_data": parse_snapshot_data(version.snapshot_data),
        "operator_id": version.operator_id,
        "operator_name": version.operator_name,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }
