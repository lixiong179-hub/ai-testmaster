import pytest
from datetime import datetime
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="tr_test_user",
        email="tr_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestResult).filter(TestResult.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(TestTask).filter(TestTask.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="结果测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_case(db, test_project):
    tc = TestCase(
        case_no="TC-TR-001",
        project_id=test_project.id,
        module="模块",
        title="结果测试用例",
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
def test_task(db, test_project, test_user):
    task = TestTask(
        task_name="结果测试任务",
        project_id=test_project.id,
        executor_id=test_user.id,
        case_ids=[]
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task


class TestTestResultModel:
    def test_create_test_result(self, db, test_task, test_project, test_case):
        result = TestResult(
            task_id=test_task.id,
            project_id=test_project.id,
            case_id=test_case.id,
            case_no="TC-TR-001",
            exec_status=1
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        assert result.id is not None
        assert result.task_id == test_task.id
        assert result.project_id == test_project.id
        assert result.case_id == test_case.id
        assert result.case_no == "TC-TR-001"
        assert result.exec_status == 1
        assert result.exec_time is not None
        assert result.create_time is not None
        db.delete(result)
        db.commit()

    def test_test_result_default_values(self, db, test_task, test_project, test_case):
        result = TestResult(
            task_id=test_task.id,
            project_id=test_project.id,
            case_id=test_case.id,
            case_no="TC-TR-DEF"
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        assert result.exec_status == 0
        assert result.exec_log is None
        assert result.error_msg is None
        assert result.screenshot_url is None
        assert result.ai_analysis is None
        assert result.location_method is None
        assert result.video_path is None
        db.delete(result)
        db.commit()

    def test_test_result_exec_status_values(self, db, test_task, test_project, test_case):
        for status in [0, 1, 2, 3]:
            result = TestResult(
                task_id=test_task.id,
                project_id=test_project.id,
                case_id=test_case.id,
                case_no=f"TC-TR-STA-{status}",
                exec_status=status
            )
            db.add(result)
            db.commit()
            db.refresh(result)
            assert result.exec_status == status
            db.delete(result)
            db.commit()

    def test_test_result_with_error(self, db, test_task, test_project, test_case):
        result = TestResult(
            task_id=test_task.id,
            project_id=test_project.id,
            case_id=test_case.id,
            case_no="TC-TR-ERR",
            exec_status=2,
            error_msg="元素未找�?,
            screenshot_url="/screenshots/error.png"
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        assert result.exec_status == 2
        assert result.error_msg == "元素未找�?
        assert result.screenshot_url == "/screenshots/error.png"
        db.delete(result)
        db.commit()

    def test_test_result_with_ai_analysis(self, db, test_task, test_project, test_case):
        result = TestResult(
            task_id=test_task.id,
            project_id=test_project.id,
            case_id=test_case.id,
            case_no="TC-TR-AI",
            exec_status=2,
            ai_analysis="失败原因：定位器过期",
            location_method="css",
            video_path="/videos/test.webm"
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        assert result.ai_analysis == "失败原因：定位器过期"
        assert result.location_method == "css"
        assert result.video_path == "/videos/test.webm"
        db.delete(result)
        db.commit()

    def test_test_result_relationships(self):
        assert hasattr(TestResult, 'project')
        assert hasattr(TestResult, 'test_case')
        assert hasattr(TestResult, 'test_task')
