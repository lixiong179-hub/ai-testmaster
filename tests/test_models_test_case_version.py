import pytest
from datetime import datetime
from app.models.test_case_version import TestCaseVersion
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="tcv_test_user",
        email="tcv_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestCaseVersion).filter(TestCaseVersion.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="版本测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_case(db, test_project):
    tc = TestCase(
        case_no="TC-TCV-001",
        project_id=test_project.id,
        module="模块",
        title="版本测试用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI"
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    yield tc


class TestTestCaseVersionModel:
    def test_create_version(self, db, test_case):
        version = TestCaseVersion(
            test_case_id=test_case.id,
            version_number=1,
            change_type="create",
            snapshot_data={"title": "版本测试用例", "priority": 1}
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        assert version.id is not None
        assert version.test_case_id == test_case.id
        assert version.version_number == 1
        assert version.change_type == "create"
        assert version.snapshot_data == {"title": "版本测试用例", "priority": 1}
        assert version.created_at is not None
        db.delete(version)
        db.commit()

    def test_version_default_values(self, db, test_case):
        version = TestCaseVersion(
            test_case_id=test_case.id,
            version_number=2,
            snapshot_data={}
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        assert version.change_type is None
        assert version.change_description is None
        assert version.changed_fields is None
        assert version.operator_id is None
        assert version.operator_name is None
        db.delete(version)
        db.commit()

    def test_version_change_type_values(self, db, test_case):
        for ct in ["create", "update", "delete", "restore", "correction"]:
            version = TestCaseVersion(
                test_case_id=test_case.id,
                version_number=1,
                change_type=ct,
                snapshot_data={}
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            assert version.change_type == ct
            db.delete(version)
            db.commit()

    def test_version_with_change_description(self, db, test_case):
        version = TestCaseVersion(
            test_case_id=test_case.id,
            version_number=1,
            change_type="update",
            change_description="修改了用例标�?,
            changed_fields={"title": {"old": "旧标�?, "new": "新标�?}},
            snapshot_data={"title": "新标�?}
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        assert version.change_description == "修改了用例标�?
        assert version.changed_fields == {"title": {"old": "旧标�?, "new": "新标�?}}
        db.delete(version)
        db.commit()

    def test_version_with_operator(self, db, test_case):
        version = TestCaseVersion(
            test_case_id=test_case.id,
            version_number=1,
            snapshot_data={},
            operator_id=1,
            operator_name="管理�?
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        assert version.operator_id == 1
        assert version.operator_name == "管理�?
        db.delete(version)
        db.commit()

    def test_version_increment(self, db, test_case):
        for vn in [1, 2, 3]:
            version = TestCaseVersion(
                test_case_id=test_case.id,
                version_number=vn,
                change_type="update",
                snapshot_data={"version": vn}
            )
            db.add(version)
            db.commit()
            db.refresh(version)
            assert version.version_number == vn
            db.delete(version)
            db.commit()

    def test_version_relationship(self):
        assert hasattr(TestCaseVersion, 'test_case')
