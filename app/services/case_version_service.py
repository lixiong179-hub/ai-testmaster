"""测试用例版本管理服务

本模块提供测试用例版本快照的创建、对比、查询、恢复和归档功能。
所有版本操作统一通过 CaseVersionService 执行，确保 changed_fields 完整性
和版本保留策略的一致性。

核心类概览：
    - CaseVersionService : 版本管理服务，封装快照创建/对比/恢复/归档

依赖关系：
    - app.models.test_case : TestCase
    - app.models.test_case_version : TestCaseVersion

拆分说明：
    - 查询与对比（compare_versions/get_version）+ 快照解析（_parse_snapshot）
      拆分至 _case_version_query
    - 归档与变更字段构建（_archive_old_versions/build_changed_fields）
      + TRACKED_FIELDS/MAX_VERSIONS_PER_CASE/ARCHIVE_OLDER_THAN_DAYS 常量
      拆分至 _case_version_archive；本模块 re-export 常量保持导入兼容
"""
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.models.test_case_version import TestCaseVersion

from app.services._case_version_archive import (
    TRACKED_FIELDS,
    MAX_VERSIONS_PER_CASE,
    ARCHIVE_OLDER_THAN_DAYS,
    archive_old_versions,
    build_changed_fields_from_state,
)
from app.services._case_version_query import (
    compare_versions as _compare_versions_impl,
    get_version as _get_version_impl,
    parse_snapshot_data,
)


class CaseVersionService:
    """测试用例版本管理服务

    统一封装版本快照的创建、对比、查询、恢复和归档逻辑，
    确保所有版本操作的一致性和完整性。

    使用场景：
        - before_flush event listener 自动触发快照
        - API 端点手动创建/对比/恢复版本
        - 其他服务委托版本创建
    """

    @staticmethod
    def create_snapshot(
        db: Session,
        test_case_id: int,
        change_type: str,
        operator_id: Optional[int] = None,
        operator_name: Optional[str] = None,
        change_description: Optional[str] = None,
        changed_fields: Optional[Dict[str, Dict[str, Any]]] = None,
        auto_flush: bool = True,
    ) -> Optional[TestCaseVersion]:
        """创建版本快照

        记录用例变更后的完整数据快照和变更字段对比信息。
        超过 MAX_VERSIONS_PER_CASE 时触发归档策略。

        Args:
            db: 数据库会话。
            test_case_id: 用例ID。
            change_type: 变更类型（create/update/restore/correction/human_edit/refresh_apply）。
            operator_id: 操作人ID。
            operator_name: 操作人姓名。
            change_description: 变更说明。
            changed_fields: 变更字段对比，格式 {"field_name": {"old": old_val, "new": new_val}}。
            auto_flush: 是否自动 flush，before_flush event 中调用时需设为 False。

        Returns:
            创建的 TestCaseVersion 实例，用例不存在时返回 None。
        """
        case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not case:
            logger.warning(f"版本快照创建失败：用例不存在 id={test_case_id}")
            return None

        latest_version = (
            db.query(TestCaseVersion)
            .filter(TestCaseVersion.test_case_id == test_case_id)
            .order_by(TestCaseVersion.version_number.desc())
            .first()
        )
        next_version = (latest_version.version_number + 1) if latest_version else 1

        snapshot_data = {
            "title": case.title,
            "module": case.module,
            "precondition": case.precondition,
            "steps_json": case.steps_json,
            "expected_result": case.expected_result,
            "priority": case.priority,
        }

        version = TestCaseVersion(
            test_case_id=test_case_id,
            version_number=next_version,
            change_type=change_type,
            change_description=change_description,
            changed_fields=changed_fields,
            snapshot_data=snapshot_data,
            operator_id=operator_id,
            operator_name=operator_name,
        )
        db.add(version)
        if auto_flush:
            db.flush()

        logger.info(
            f"版本快照已创建: case_id={test_case_id}, "
            f"version={next_version}, type={change_type}"
        )

        if auto_flush:
            archive_old_versions(db, test_case_id)

        return version

    @staticmethod
    def compare_versions(
        db: Session,
        test_case_id: int,
        v1_id: int,
        v2_id: int,
    ) -> Dict[str, Any]:
        """对比两个版本，返回字段级 diff

        详见 _case_version_query.compare_versions。
        """
        return _compare_versions_impl(db, test_case_id, v1_id, v2_id)

    @staticmethod
    def get_version(
        db: Session,
        test_case_id: int,
        version_id: int,
    ) -> Optional[Dict[str, Any]]:
        """获取版本详情

        详见 _case_version_query.get_version。
        """
        return _get_version_impl(db, test_case_id, version_id)

    @staticmethod
    def restore_version(
        db: Session,
        test_case_id: int,
        version_id: int,
        operator_id: Optional[int] = None,
    ) -> Optional[TestCase]:
        """恢复到指定版本

        将用例的追踪字段恢复到目标版本的快照值，并自动创建恢复版本记录。

        Args:
            db: 数据库会话。
            test_case_id: 用例ID。
            version_id: 目标版本ID。
            operator_id: 操作人ID。

        Returns:
            恢复后的 TestCase 实例，版本或用例不存在时返回 None。

        Raises:
            ValueError: 版本快照数据为空，无法恢复。
        """
        case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
        if not case:
            return None

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.id == version_id,
            TestCaseVersion.test_case_id == test_case_id,
        ).first()
        if not version:
            return None

        snapshot = parse_snapshot_data(version.snapshot_data)
        if not snapshot:
            raise ValueError(f"版本V{version.version_number}无快照数据，无法恢复")

        changed_fields: Dict[str, Dict[str, Any]] = {}
        restorable_fields = ["title", "module", "precondition", "steps_json",
                             "expected_result", "priority", "case_type"]
        for field in restorable_fields:
            if field in snapshot:
                old_value = getattr(case, field, None)
                new_value = snapshot[field]
                if old_value != new_value:
                    changed_fields[field] = {"old": old_value, "new": new_value}
                setattr(case, field, new_value)

        # 跳过自动版本快照，恢复操作由下方手动创建
        from app.models.test_case import skip_version_snapshot, resume_version_snapshot
        skip_version_snapshot()
        try:
            db.flush()
        finally:
            resume_version_snapshot()

        CaseVersionService.create_snapshot(
            db=db,
            test_case_id=test_case_id,
            change_type="restore",
            operator_id=operator_id,
            change_description=f"恢复到版本V{version.version_number}",
            changed_fields=changed_fields if changed_fields else None,
        )

        logger.info(
            f"版本恢复完成: case_id={test_case_id}, "
            f"restored_to=V{version.version_number}, operator_id={operator_id}"
        )
        return case

    @staticmethod
    def build_changed_fields(
        case: TestCase,
        state: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """根据 SQLAlchemy instance state 构建 changed_fields

        详见 _case_version_archive.build_changed_fields_from_state。
        """
        return build_changed_fields_from_state(case, state)

    @staticmethod
    def _archive_old_versions(db: Session, test_case_id: int) -> None:
        """归档超过保留策略的旧版本

        详见 _case_version_archive.archive_old_versions。
        """
        archive_old_versions(db, test_case_id)

    @staticmethod
    def _parse_snapshot(data: Any) -> Any:
        """解析 snapshot_data/changed_fields，兼容 JSON 字符串和 dict 类型

        详见 _case_version_query.parse_snapshot_data。
        """
        return parse_snapshot_data(data)
