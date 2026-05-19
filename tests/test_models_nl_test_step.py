import pytest
from datetime import datetime
from app.models.nl_test_step import NLTestStep
from app.models.test_task import TestTask
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="nl_test_user",
        email="nl_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(NLTestStep).filter(NLTestStep.task_id.in_(
        db.query(TestTask.id).filter(TestTask.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestTask).filter(TestTask.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="NL步骤测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_task(db, test_project, test_user):
    task = TestTask(
        task_name="NL步骤测试任务",
        project_id=test_project.id,
        executor_id=test_user.id,
        case_ids=[]
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task


class TestNLTestStepModel:
    def test_create_nl_test_step(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="click",
            target_desc="点击登录按钮"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.id is not None
        assert step.task_id == test_task.id
        assert step.step_index == 1
        assert step.action == "click"
        assert step.target_desc == "点击登录按钮"
        db.delete(step)
        db.commit()

    def test_nl_test_step_default_values(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="input",
            target_desc="输入用户名"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.param is None
        assert step.expected is None
        assert step.screenshot_path is None
        assert step.error_message is None
        assert step.ai_analysis is None
        assert step.start_time is None
        assert step.end_time is None
        db.delete(step)
        db.commit()

    def test_nl_test_step_action_values(self, db, test_task):
        for action in ["click", "input", "wait", "assert", "navigate"]:
            step = NLTestStep(
                task_id=test_task.id,
                step_index=1,
                action=action,
                target_desc=f"操作{action}"
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            assert step.action == action
            db.delete(step)
            db.commit()

    def test_nl_test_step_with_param(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="input",
            target_desc="用户名输入框",
            param="testuser",
            expected="输入框显示testuser"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.param == "testuser"
        assert step.expected == "输入框显示testuser"
        db.delete(step)
        db.commit()

    def test_nl_test_step_with_error(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="click",
            target_desc="登录按钮",
            error_message="元素未找到",
            screenshot_path="/screenshots/error.png"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.error_message == "元素未找到"
        assert step.screenshot_path == "/screenshots/error.png"
        db.delete(step)
        db.commit()

    def test_nl_test_step_with_ai_analysis(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="click",
            target_desc="按钮",
            ai_analysis="定位器可能已过期，建议更新CSS选择器"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.ai_analysis == "定位器可能已过期，建议更新CSS选择器"
        db.delete(step)
        db.commit()

    def test_nl_test_step_with_timestamps(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="click",
            target_desc="按钮",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 0, 5)
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.start_time == datetime(2024, 1, 1, 10, 0, 0)
        assert step.end_time == datetime(2024, 1, 1, 10, 0, 5)
        db.delete(step)
        db.commit()

    def test_nl_test_step_repr(self, db, test_task):
        step = NLTestStep(
            task_id=test_task.id,
            step_index=1,
            action="click",
            target_desc="按钮"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        repr_str = repr(step)
        assert "NLTestStep" in repr_str
        db.delete(step)
        db.commit()

    def test_nl_test_step_relationship(self):
        assert hasattr(NLTestStep, 'test_task')
