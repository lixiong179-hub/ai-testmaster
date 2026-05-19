import pytest
from app.crud.test_task import (
    create_test_task,
    get_test_task_by_id,
    get_test_tasks_by_project,
    get_test_tasks_count,
    update_test_task_status,
    update_test_task_progress,
    delete_test_task,
)


class TestCreateTestTask:
    def test_create_basic(self, db, testProject, testUser):
        task = create_test_task(
            db, "回归测试", testProject.id, [1, 2, 3], testUser.id,
        )
        assert task.id is not None
        assert task.task_name == "回归测试"
        assert task.total_count == 3
        assert task.status == 0
        assert task.progress == 0

    def test_create_empty_cases(self, db, testProject, testUser):
        task = create_test_task(
            db, "空任务", testProject.id, [], testUser.id,
        )
        assert task.total_count == 0


class TestGetTestTaskById:
    def test_found(self, db, testProject, testUser):
        task = create_test_task(
            db, "查询任务", testProject.id, [1], testUser.id,
        )
        found = get_test_task_by_id(db, task.id, testProject.id)
        assert found is not None
        assert found.id == task.id

    def test_wrong_project(self, db, testProject, testUser):
        task = create_test_task(
            db, "隔离任务", testProject.id, [1], testUser.id,
        )
        found = get_test_task_by_id(db, task.id, 99999)
        assert found is None

    def test_nonexistent(self, db):
        found = get_test_task_by_id(db, 99999, 1)
        assert found is None


class TestGetTestTasksByProject:
    def test_returns_tasks(self, db, testProject, testUser):
        create_test_task(db, "任务1", testProject.id, [1], testUser.id)
        create_test_task(db, "任务2", testProject.id, [2], testUser.id)
        tasks = get_test_tasks_by_project(db, testProject.id)
        assert len(tasks) >= 2

    def test_filter_by_status(self, db, testProject, testUser):
        task = create_test_task(db, "状态任务", testProject.id, [1], testUser.id)
        tasks = get_test_tasks_by_project(db, testProject.id, status=0)
        assert all(t.status == 0 for t in tasks)

    def test_empty_project(self, db):
        tasks = get_test_tasks_by_project(db, 99999)
        assert len(tasks) == 0


class TestGetTestTasksCount:
    def test_count(self, db, testProject, testUser):
        create_test_task(db, "计数1", testProject.id, [1], testUser.id)
        create_test_task(db, "计数2", testProject.id, [2], testUser.id)
        count = get_test_tasks_count(db, testProject.id)
        assert count >= 2

    def test_count_by_status(self, db, testProject, testUser):
        create_test_task(db, "状态计数", testProject.id, [1], testUser.id)
        count = get_test_tasks_count(db, testProject.id, status=0)
        assert count >= 1


class TestUpdateTestTaskStatus:
    def test_start_execution(self, db, testProject, testUser):
        task = create_test_task(db, "启动任务", testProject.id, [1], testUser.id)
        updated = update_test_task_status(db, task.id, testProject.id, 1)
        assert updated.status == 1
        assert updated.start_time is not None

    def test_complete_execution(self, db, testProject, testUser):
        task = create_test_task(db, "完成任务", testProject.id, [1], testUser.id)
        updated = update_test_task_status(db, task.id, testProject.id, 2)
        assert updated.status == 2
        assert updated.end_time is not None

    def test_nonexistent_task(self, db):
        result = update_test_task_status(db, 99999, 1, 1)
        assert result is None


class TestUpdateTestTaskProgress:
    def test_update_progress(self, db, testProject, testUser):
        task = create_test_task(db, "进度任务", testProject.id, [1, 2, 3], testUser.id)
        updated = update_test_task_progress(db, task.id, testProject.id, 50, success_count=1, fail_count=0)
        assert updated.progress == 50
        assert updated.success_count == 1

    def test_update_only_progress(self, db, testProject, testUser):
        task = create_test_task(db, "仅进度", testProject.id, [1], testUser.id)
        updated = update_test_task_progress(db, task.id, testProject.id, 30)
        assert updated.progress == 30

    def test_nonexistent_task(self, db):
        result = update_test_task_progress(db, 99999, 1, 50)
        assert result is None


class TestDeleteTestTask:
    def test_delete_existing(self, db, testProject, testUser):
        task = create_test_task(db, "删除任务", testProject.id, [1], testUser.id)
        result = delete_test_task(db, task.id, testProject.id)
        assert result is True
        assert get_test_task_by_id(db, task.id, testProject.id) is None

    def test_delete_nonexistent(self, db):
        result = delete_test_task(db, 99999, 1)
        assert result is False
