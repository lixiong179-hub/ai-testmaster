import pytest
from datetime import datetime
from app.models.test_task import TestTask, TaskStatus
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="tt_test_user",
        email="tt_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestTask).filter(TestTask.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="任务测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestTestTaskModel:
    def test_create_test_task(self, db, test_project, test_user):
        task = TestTask(
            task_name="回归测试",
            project_id=test_project.id,
            executor_id=test_user.id,
            case_ids=[1, 2, 3]
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.id is not None
        assert task.task_name == "回归测试"
        assert task.project_id == test_project.id
        assert task.executor_id == test_user.id
        assert task.case_ids == [1, 2, 3]
        assert task.status == 0
        assert task.create_time is not None
        db.delete(task)
        db.commit()

    def test_test_task_default_values(self, db, test_project, test_user):
        task = TestTask(
            task_name="默认任务",
            project_id=test_project.id,
            executor_id=test_user.id,
            case_ids=[]
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.status == 0
        assert task.success_count == 0
        assert task.fail_count == 0
        assert task.total_count == 0
        assert task.progress == 0
        assert task.start_time is None
        assert task.end_time is None
        db.delete(task)
        db.commit()

    def test_test_task_status_values(self, db, test_project, test_user):
        for status in [0, 1, 2, 3, 4]:
            task = TestTask(
                task_name=f"状态任务{status}",
                project_id=test_project.id,
                executor_id=test_user.id,
                case_ids=[],
                status=status
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            assert task.status == status
            db.delete(task)
            db.commit()

    def test_test_task_with_progress(self, db, test_project, test_user):
        task = TestTask(
            task_name="进度任务",
            project_id=test_project.id,
            executor_id=test_user.id,
            case_ids=[1, 2, 3],
            total_count=3,
            success_count=2,
            fail_count=1,
            progress=100
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.total_count == 3
        assert task.success_count == 2
        assert task.fail_count == 1
        assert task.progress == 100
        db.delete(task)
        db.commit()

    def test_test_task_with_timestamps(self, db, test_project, test_user):
        task = TestTask(
            task_name="时间任务",
            project_id=test_project.id,
            executor_id=test_user.id,
            case_ids=[],
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 11, 0, 0)
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.start_time == datetime(2024, 1, 1, 10, 0, 0)
        assert task.end_time == datetime(2024, 1, 1, 11, 0, 0)
        db.delete(task)
        db.commit()

    def test_test_task_case_ids_json(self, db, test_project, test_user):
        case_ids = [1, 2, 3, 4, 5]
        task = TestTask(
            task_name="JSON任务",
            project_id=test_project.id,
            executor_id=test_user.id,
            case_ids=case_ids
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        assert task.case_ids == case_ids
        db.delete(task)
        db.commit()

    def test_test_task_relationships(self):
        assert hasattr(TestTask, 'project')
        assert hasattr(TestTask, 'executor')
        assert hasattr(TestTask, 'test_results')
        assert hasattr(TestTask, 'video_records')


class TestTaskStatusConstants:
    def test_all_status_values(self):
        assert TaskStatus.PENDING == 0
        assert TaskStatus.RUNNING == 1
        assert TaskStatus.COMPLETED == 2
        assert TaskStatus.FAILED == 3
        assert TaskStatus.STOPPED == 4

    def test_labels_mapping(self):
        assert TaskStatus.LABELS[TaskStatus.PENDING] == "等待执行"
        assert TaskStatus.LABELS[TaskStatus.RUNNING] == "执行中"
        assert TaskStatus.LABELS[TaskStatus.COMPLETED] == "执行完成"
        assert TaskStatus.LABELS[TaskStatus.FAILED] == "执行失败"
        assert TaskStatus.LABELS[TaskStatus.STOPPED] == "已停止"
