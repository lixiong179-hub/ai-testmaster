import pytest
from decimal import Decimal
from app.models.api_cost_log import ApiCostLog
from app.models.test_task import TestTask
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="acl_test_user",
        email="acl_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(ApiCostLog).filter(ApiCostLog.task_id.in_(
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
    project = Project(name="API成本测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_task(db, test_project, test_user):
    task = TestTask(
        task_name="API成本测试任务",
        project_id=test_project.id,
        executor_id=test_user.id,
        case_ids=[]
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    yield task


class TestApiCostLogModel:
    def test_create_api_cost_log(self, db, test_task):
        log = ApiCostLog(
            task_id=test_task.id,
            model="deepseek-v4-flash",
            api_type="test_generation",
            output_tokens=500,
            cost=Decimal("0.015000"),
            status="success"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.id is not None
        assert log.task_id == test_task.id
        assert log.model == "deepseek-v4-flash"
        assert log.api_type == "test_generation"
        assert log.output_tokens == 500
        db.delete(log)
        db.commit()

    def test_api_cost_log_default_values(self, db):
        log = ApiCostLog(
            model="qwen",
            api_type="analysis"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.task_id is None
        assert log.output_tokens is None
        assert log.cost is None
        assert log.status is None
        assert log.error_message is None
        db.delete(log)
        db.commit()

    def test_api_cost_log_model_values(self, db):
        for model in ["deepseek-v4-flash", "qwen", "kimi"]:
            log = ApiCostLog(
                model=model,
                api_type="test_generation"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            assert log.model == model
            db.delete(log)
            db.commit()

    def test_api_cost_log_api_type_values(self, db):
        for api_type in ["test_generation", "analysis", "vision"]:
            log = ApiCostLog(
                model="deepseek-v4-flash",
                api_type=api_type
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            assert log.api_type == api_type
            db.delete(log)
            db.commit()

    def test_api_cost_log_status_values(self, db):
        for status in ["success", "failed", "timeout"]:
            log = ApiCostLog(
                model="deepseek-v4-flash",
                api_type="test_generation",
                status=status
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            assert log.status == status
            db.delete(log)
            db.commit()

    def test_api_cost_log_with_error(self, db):
        log = ApiCostLog(
            model="deepseek-v4-flash",
            api_type="test_generation",
            status="failed",
            error_message="API调用超时"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.status == "failed"
        assert log.error_message == "API调用超时"
        db.delete(log)
        db.commit()

    def test_api_cost_log_cost_precision(self, db):
        log = ApiCostLog(
            model="deepseek-v4-flash",
            api_type="test_generation",
            cost=Decimal("0.000001")
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.cost == Decimal("0.000001")
        db.delete(log)
        db.commit()

    def test_api_cost_log_repr(self, db):
        log = ApiCostLog(
            model="deepseek-v4-flash",
            api_type="test_generation",
            cost=Decimal("0.010000")
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        repr_str = repr(log)
        assert "ApiCostLog" in repr_str
        assert "deepseek-v4-flash" in repr_str
        db.delete(log)
        db.commit()
