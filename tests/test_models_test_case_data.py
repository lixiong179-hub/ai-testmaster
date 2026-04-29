import pytest
from app.models.test_case_data import TestCaseData
from app.models.test_data import TestData
from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="tcd_test_user",
        email="tcd_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestCaseData).filter(TestCaseData.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestData).filter(TestData.step_id.in_(
        db.query(TestStep.id).filter(TestStep.test_case_id.in_(
            db.query(TestCase.id).filter(TestCase.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            ))
        ))
    )).delete(synchronize_session=False)
    db.query(TestStep).filter(TestStep.test_case_id.in_(
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
    project = Project(name="用例数据测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_case(db, test_project):
    tc = TestCase(
        case_no="TC-TCD-001",
        project_id=test_project.id,
        module="模块",
        title="用例数据测试",
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


@pytest.fixture
def test_data_record(db, test_case):
    step = TestStep(
        test_case_id=test_case.id,
        step_number=1,
        action="输入",
        expected_result="显示"
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    td = TestData(
        step_id=step.id,
        field_name="username"
    )
    db.add(td)
    db.commit()
    db.refresh(td)
    yield td


class TestTestCaseDataModel:
    def test_create_test_case_data(self, db, test_case, test_data_record):
        tcd = TestCaseData(
            test_case_id=test_case.id,
            test_data_id=test_data_record.id
        )
        db.add(tcd)
        db.commit()
        db.refresh(tcd)
        assert tcd.id is not None
        assert tcd.test_case_id == test_case.id
        assert tcd.test_data_id == test_data_record.id
        db.delete(tcd)
        db.commit()

    def test_test_case_data_repr(self, db, test_case, test_data_record):
        tcd = TestCaseData(
            test_case_id=test_case.id,
            test_data_id=test_data_record.id
        )
        db.add(tcd)
        db.commit()
        db.refresh(tcd)
        repr_str = repr(tcd)
        assert "TestCaseData" in repr_str
        assert str(test_case.id) in repr_str
        db.delete(tcd)
        db.commit()

    def test_test_case_data_relationships(self):
        assert hasattr(TestCaseData, 'test_case')
        assert hasattr(TestCaseData, 'test_data')
