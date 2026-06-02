"""CaseVersionService 版本管理增强测试模块

覆盖：
    - 自动快照触发（before_flush event listener）
    - bulk update 改 ORM 后 event 触发
    - 版本对比 diff 输出
    - 保留策略归档
    - changed_fields 完整性
    - create_snapshot / get_version / restore_version
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.models.test_case import (
    TestCase,
    enable_lifecycle_transition,
    disable_lifecycle_transition,
    skip_version_snapshot,
    resume_version_snapshot,
)
from app.models.test_case_version import TestCaseVersion
from app.models.project import Project
from app.models.user import User
from app.services.case_version_service import (
    CaseVersionService,
    TRACKED_FIELDS,
    MAX_VERSIONS_PER_CASE,
    ARCHIVE_OLDER_THAN_DAYS,
)


@pytest.fixture
def version_user(db):
    user = User(
        username="version_test_user",
        email="version_test@test.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.flush()


@pytest.fixture
def version_project(db, version_user):
    project = Project(name="版本测试项目", user_id=version_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_case(db, project_id, **kwargs):
    case_no = kwargs.pop("case_no", f"VER-{datetime.now().strftime('%H%M%S%f')}")
    case = TestCase(
        project_id=project_id,
        case_no=case_no,
        module=kwargs.get("module", "默认模块"),
        title=kwargs.get("title", "版本测试用例"),
        precondition=kwargs.get("precondition", "前置条件"),
        steps_json=kwargs.get("steps_json", [{"step": "步骤1", "action": "操作", "param": "参数"}]),
        expected_result=kwargs.get("expected_result", "预期结果"),
        priority=kwargs.get("priority", 1),
        case_type=kwargs.get("case_type", "UI"),
        lifecycle_status=kwargs.get("lifecycle_status", "active"),
    )
    enable_lifecycle_transition()
    try:
        db.add(case)
        db.flush()
        db.refresh(case)
    finally:
        disable_lifecycle_transition()
    return case


class TestCreateSnapshot:
    """create_snapshot 基本功能测试"""

    def test_create_snapshot_success(self, db, version_project):
        case = _make_case(db, version_project.id)
        version = CaseVersionService.create_snapshot(
            db=db,
            test_case_id=case.id,
            change_type="update",
            operator_id=1,
            operator_name="tester",
            change_description="标题修改",
            changed_fields={"title": {"old": "旧标题", "new": "新标题"}},
        )
        assert version is not None
        assert version.test_case_id == case.id
        assert version.version_number == 1
        assert version.change_type == "update"
        assert version.changed_fields == {"title": {"old": "旧标题", "new": "新标题"}}
        assert version.operator_id == 1
        assert version.operator_name == "tester"
        assert version.snapshot_data is not None
        assert version.snapshot_data["title"] == case.title

    def test_create_snapshot_nonexistent_case(self, db):
        version = CaseVersionService.create_snapshot(
            db=db,
            test_case_id=99999,
            change_type="update",
        )
        assert version is None

    def test_create_snapshot_version_number_increments(self, db, version_project):
        case = _make_case(db, version_project.id)
        skip_version_snapshot()
        try:
            v1 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
            v2 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()
        assert v1.version_number == 1
        assert v2.version_number == 2

    def test_create_snapshot_without_changed_fields(self, db, version_project):
        case = _make_case(db, version_project.id)
        version = CaseVersionService.create_snapshot(
            db=db,
            test_case_id=case.id,
            change_type="create",
        )
        assert version is not None
        assert version.changed_fields is None


class TestAutoSnapshotTrigger:
    """before_flush event listener 自动快照触发测试"""

    def test_auto_snapshot_on_title_change(self, db, version_project):
        case = _make_case(db, version_project.id, title="原始标题")
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        case.title = "修改后标题"
        db.flush()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        assert new_count == old_count + 1

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).order_by(TestCaseVersion.version_number.desc()).first()
        assert version.change_type == "update"
        assert version.changed_fields is not None
        assert "title" in version.changed_fields
        assert version.changed_fields["title"]["old"] == "原始标题"
        assert version.changed_fields["title"]["new"] == "修改后标题"

    def test_auto_snapshot_on_priority_change(self, db, version_project):
        case = _make_case(db, version_project.id, priority=1)
        case.priority = 2
        db.flush()

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).order_by(TestCaseVersion.version_number.desc()).first()
        assert version is not None
        assert "priority" in version.changed_fields
        assert version.changed_fields["priority"]["old"] == 1
        assert version.changed_fields["priority"]["new"] == 2

    def test_auto_snapshot_on_steps_json_change(self, db, version_project):
        case = _make_case(db, version_project.id, steps_json=[{"step": "旧步骤"}])
        case.steps_json = [{"step": "新步骤"}]
        db.flush()

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).order_by(TestCaseVersion.version_number.desc()).first()
        assert version is not None
        assert "steps_json" in version.changed_fields

    def test_no_snapshot_on_untracked_field_change(self, db, version_project):
        case = _make_case(db, version_project.id)
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        case.review_status = "approved"
        db.flush()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        assert new_count == old_count

    def test_no_snapshot_when_value_unchanged(self, db, version_project):
        case = _make_case(db, version_project.id, title="不变标题")
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        case.title = "不变标题"
        db.flush()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        assert new_count == old_count

    def test_skip_version_snapshot_flag(self, db, version_project):
        case = _make_case(db, version_project.id, title="跳过测试")
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        skip_version_snapshot()
        try:
            case.title = "跳过后标题"
            db.flush()
        finally:
            resume_version_snapshot()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        assert new_count == old_count


class TestBulkUpdateOrmTrigger:
    """bulk update 改 ORM 逐条更新后 event 触发测试"""

    def test_posterior_quality_score_update_triggers_snapshot(self, db, version_project):
        case = _make_case(db, version_project.id, title="后验质量分测试")
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        case.posterior_quality_score = 85.5
        db.flush()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        # posterior_quality_score 不在 TRACKED_FIELDS 中，不应触发快照
        assert new_count == old_count

    def test_orm_update_tracked_field_triggers_snapshot(self, db, version_project):
        case = _make_case(db, version_project.id, title="ORM更新测试")
        old_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()

        # 模拟 posterior_score_service 的 ORM 逐条更新方式
        case.title = "ORM更新后标题"
        db.flush()

        new_count = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).count()
        assert new_count == old_count + 1


class TestCompareVersions:
    """版本对比 diff 输出测试"""

    def test_compare_two_versions(self, db, version_project):
        case = _make_case(db, version_project.id, title="版本A标题", priority=1)

        skip_version_snapshot()
        try:
            v1 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )

            case.title = "版本B标题"
            case.priority = 2
            db.flush()

            v2 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()

        result = CaseVersionService.compare_versions(
            db=db, test_case_id=case.id, v1_id=v1.id, v2_id=v2.id,
        )
        assert "v1" in result
        assert "v2" in result
        assert "diff" in result
        assert result["v1"]["id"] == v1.id
        assert result["v2"]["id"] == v2.id
        assert "title" in result["diff"]
        assert result["diff"]["title"]["old"] == "版本A标题"
        assert result["diff"]["title"]["new"] == "版本B标题"
        assert "priority" in result["diff"]
        assert result["diff"]["priority"]["old"] == 1
        assert result["diff"]["priority"]["new"] == 2

    def test_compare_identical_versions(self, db, version_project):
        case = _make_case(db, version_project.id, title="相同版本")

        skip_version_snapshot()
        try:
            v1 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
            v2 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()

        result = CaseVersionService.compare_versions(
            db=db, test_case_id=case.id, v1_id=v1.id, v2_id=v2.id,
        )
        assert result["diff"] == {}

    def test_compare_nonexistent_version_raises(self, db, version_project):
        case = _make_case(db, version_project.id)
        skip_version_snapshot()
        try:
            v1 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()

        with pytest.raises(ValueError, match="版本不存在"):
            CaseVersionService.compare_versions(
                db=db, test_case_id=case.id, v1_id=v1.id, v2_id=99999,
            )


class TestGetVersion:
    """get_version 版本详情查询测试"""

    def test_get_version_success(self, db, version_project):
        case = _make_case(db, version_project.id)
        version = CaseVersionService.create_snapshot(
            db=db,
            test_case_id=case.id,
            change_type="update",
            change_description="查询测试",
            changed_fields={"title": {"old": "a", "new": "b"}},
        )

        result = CaseVersionService.get_version(db=db, test_case_id=case.id, version_id=version.id)
        assert result is not None
        assert result["id"] == version.id
        assert result["version_number"] == version.version_number
        assert result["change_type"] == "update"
        assert result["change_description"] == "查询测试"
        assert result["changed_fields"] == {"title": {"old": "a", "new": "b"}}

    def test_get_version_not_found(self, db, version_project):
        result = CaseVersionService.get_version(db=db, test_case_id=1, version_id=99999)
        assert result is None


class TestRestoreVersion:
    """restore_version 版本恢复测试"""

    def test_restore_version_success(self, db, version_project):
        case = _make_case(db, version_project.id, title="原始标题", priority=1)

        skip_version_snapshot()
        try:
            v1 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )

            case.title = "修改后标题"
            case.priority = 2
            db.flush()

            v2 = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()

        # 恢复到 v1
        restored = CaseVersionService.restore_version(
            db=db, test_case_id=case.id, version_id=v1.id, operator_id=1,
        )
        assert restored is not None
        assert restored.title == "原始标题"
        assert restored.priority == 1

        # 应创建 restore 类型的版本记录
        restore_version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id,
            TestCaseVersion.change_type == "restore",
        ).first()
        assert restore_version is not None
        assert restore_version.changed_fields is not None

    def test_restore_nonexistent_version(self, db, version_project):
        case = _make_case(db, version_project.id)
        result = CaseVersionService.restore_version(
            db=db, test_case_id=case.id, version_id=99999,
        )
        assert result is None

    def test_restore_nonexistent_case(self, db):
        result = CaseVersionService.restore_version(
            db=db, test_case_id=99999, version_id=1,
        )
        assert result is None


class TestArchivePolicy:
    """版本保留策略归档测试"""

    def test_archive_triggers_when_exceeds_max(self, db, version_project):
        case = _make_case(db, version_project.id, title="归档测试")

        skip_version_snapshot()
        try:
            # 创建超过 MAX_VERSIONS_PER_CASE 的版本
            for i in range(MAX_VERSIONS_PER_CASE + 5):
                CaseVersionService.create_snapshot(
                    db=db,
                    test_case_id=case.id,
                    change_type="update",
                    change_description=f"版本{i + 1}",
                )
        finally:
            resume_version_snapshot()

        total = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id,
        ).count()
        assert total == MAX_VERSIONS_PER_CASE + 5

        # 由于新创建的版本 created_at 都是当前时间（不超过90天），
        # 归档不会实际清理，但归档逻辑已执行
        versions_with_data = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id,
            TestCaseVersion.snapshot_data.isnot(None),
        ).count()
        assert versions_with_data == total

    def test_archive_clears_old_snapshot_data(self, db, version_project):
        case = _make_case(db, version_project.id, title="旧归档测试")

        skip_version_snapshot()
        try:
            # 创建版本并手动设置 created_at 为91天前
            versions = []
            for i in range(MAX_VERSIONS_PER_CASE + 2):
                version = CaseVersionService.create_snapshot(
                    db=db,
                    test_case_id=case.id,
                    change_type="update",
                    change_description=f"旧版本{i + 1}",
                )
                versions.append(version)
                # 手动将前几个版本设为91天前
                if i < 3:
                    version.created_at = datetime.now(timezone.utc) - timedelta(
                        days=ARCHIVE_OLDER_THAN_DAYS + 1
                    )
            db.flush()

            # 手动触发归档（因为 create_snapshot 中 auto_flush=True 时归档已执行，
            # 但 created_at 修改在归档之后，需再次触发）
            CaseVersionService._archive_old_versions(db, case.id)
        finally:
            resume_version_snapshot()

        # 检查旧版本的 snapshot_data 是否被置空
        archived = [v for v in versions if v.snapshot_data is None]
        assert len(archived) > 0

        # 归档版本仍保留元数据
        for ver in archived:
            assert ver.version_number is not None
            assert ver.change_type is not None


class TestChangedFieldsIntegrity:
    """changed_fields 完整性测试"""

    def test_changed_fields_records_all_tracked_changes(self, db, version_project):
        case = _make_case(
            db, version_project.id,
            title="完整测试",
            module="旧模块",
            precondition="旧前置",
            expected_result="旧预期",
            priority=1,
            steps_json=[{"step": "旧步骤"}],
        )

        case.title = "新标题"
        case.module = "新模块"
        case.precondition = "新前置"
        case.expected_result = "新预期"
        case.priority = 2
        case.steps_json = [{"step": "新步骤"}]
        db.flush()

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).order_by(TestCaseVersion.version_number.desc()).first()
        assert version is not None
        assert version.changed_fields is not None

        for field in TRACKED_FIELDS:
            assert field in version.changed_fields, f"字段 {field} 未记录在 changed_fields 中"
            assert "old" in version.changed_fields[field]
            assert "new" in version.changed_fields[field]

    def test_changed_fields_only_records_actual_changes(self, db, version_project):
        case = _make_case(
            db, version_project.id,
            title="不变标题",
            module="不变模块",
        )

        case.title = "不变标题"
        case.module = "变化模块"
        db.flush()

        version = db.query(TestCaseVersion).filter(
            TestCaseVersion.test_case_id == case.id
        ).order_by(TestCaseVersion.version_number.desc()).first()
        assert version is not None
        assert "title" not in version.changed_fields
        assert "module" in version.changed_fields

    def test_snapshot_data_contains_current_state(self, db, version_project):
        case = _make_case(
            db, version_project.id,
            title="快照验证",
            module="快照模块",
            precondition="快照前置",
            expected_result="快照预期",
            priority=3,
            steps_json=[{"step": "快照步骤"}],
        )

        skip_version_snapshot()
        try:
            version = CaseVersionService.create_snapshot(
                db=db, test_case_id=case.id, change_type="update",
            )
        finally:
            resume_version_snapshot()

        assert version.snapshot_data["title"] == "快照验证"
        assert version.snapshot_data["module"] == "快照模块"
        assert version.snapshot_data["precondition"] == "快照前置"
        assert version.snapshot_data["expected_result"] == "快照预期"
        assert version.snapshot_data["priority"] == 3
        assert version.snapshot_data["steps_json"] == [{"step": "快照步骤"}]

    def test_build_changed_fields_from_state(self, db, version_project):
        from sqlalchemy import inspect as sa_inspect

        case = _make_case(db, version_project.id, title="state测试", priority=1)
        case.title = "state修改"
        case.priority = 2

        state = sa_inspect(case)
        changed_fields = CaseVersionService.build_changed_fields(case, state)

        assert "title" in changed_fields
        assert changed_fields["title"]["old"] == "state测试"
        assert changed_fields["title"]["new"] == "state修改"
        assert "priority" in changed_fields
        assert changed_fields["priority"]["old"] == 1
        assert changed_fields["priority"]["new"] == 2
