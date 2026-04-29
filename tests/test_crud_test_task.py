import uuid
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
from tests.helpers import createTestProject, createTestUser


class TestCreateTestTask:
    def test_create_test_task_normal(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1, 2, 3],
            executor_id=testUser.id,
        )
        assert task is not None
        assert task.id is not None
        assert task.project_id == testProject.id
        assert task.executor_id == testUser.id
        assert task.total_count == 3
        assert task.status == 0
        assert task.progress == 0
        assert task.success_count == 0
        assert task.fail_count == 0

    def test_create_test_task_empty_case_ids(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_empty_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[],
            executor_id=testUser.id,
        )
        assert task.total_count == 0

    def test_create_test_task_single_case(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_single_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[100],
            executor_id=testUser.id,
        )
        assert task.total_count == 1


class TestGetTestTaskById:
    def test_get_test_task_by_id_normal(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_get_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        found = get_test_task_by_id(db=db, task_id=task.id, project_id=testProject.id)
        assert found is not None
        assert found.id == task.id

    def test_get_test_task_by_id_nonexistent(self, db, testProject):
        found = get_test_task_by_id(db=db, task_id=99999, project_id=testProject.id)
        assert found is None

    def test_get_test_task_by_id_wrong_project(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_wp_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        found = get_test_task_by_id(db=db, task_id=task.id, project_id=99999)
        assert found is None


class TestGetTestTasksByProject:
    def test_get_test_tasks_by_project_normal(self, db, testProject, testUser):
        for i in range(3):
            create_test_task(
                db=db,
                task_name=f"task_list_{i}_{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                case_ids=[1],
                executor_id=testUser.id,
            )
        tasks = get_test_tasks_by_project(db=db, project_id=testProject.id)
        assert len(tasks) >= 3

    def test_get_test_tasks_by_project_with_status_filter(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_status_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=2)
        tasks = get_test_tasks_by_project(db=db, project_id=testProject.id, status=2)
        assert all(t.status == 2 for t in tasks)

    def test_get_test_tasks_by_project_pagination(self, db, testProject, testUser):
        for i in range(5):
            create_test_task(
                db=db,
                task_name=f"task_page_{i}_{uuid.uuid4().hex[:8]}",
                project_id=testProject.id,
                case_ids=[1],
                executor_id=testUser.id,
            )
        first = get_test_tasks_by_project(db=db, project_id=testProject.id, skip=0, limit=2)
        assert len(first) <= 2

    def test_get_test_tasks_by_project_empty(self, db):
        tasks = get_test_tasks_by_project(db=db, project_id=99999)
        assert tasks == []


class TestGetTestTasksCount:
    def test_get_test_tasks_count_normal(self, db, testProject, testUser):
        create_test_task(
            db=db,
            task_name=f"task_cnt_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        count = get_test_tasks_count(db=db, project_id=testProject.id)
        assert count >= 1

    def test_get_test_tasks_count_with_status_filter(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_cnts_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=1)
        count = get_test_tasks_count(db=db, project_id=testProject.id, status=1)
        assert count >= 1

    def test_get_test_tasks_count_empty(self, db):
        count = get_test_tasks_count(db=db, project_id=99999)
        assert count == 0


class TestUpdateTestTaskStatus:
    def test_update_status_to_running(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_run_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=1)
        assert updated is not None
        assert updated.status == 1
        assert updated.start_time is not None

    def test_update_status_to_completed(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_comp_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=2)
        assert updated is not None
        assert updated.status == 2
        assert updated.end_time is not None

    def test_update_status_to_failed(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_fail_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=3)
        assert updated is not None
        assert updated.status == 3
        assert updated.end_time is not None

    def test_update_status_to_stopped(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_stop_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=4)
        assert updated is not None
        assert updated.status == 4
        assert updated.end_time is not None

    def test_update_status_nonexistent(self, db, testProject):
        result = update_test_task_status(db=db, task_id=99999, project_id=testProject.id, status=1)
        assert result is None

    def test_update_status_pending_no_time_set(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_pending_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_status(db=db, task_id=task.id, project_id=testProject.id, status=0)
        assert updated is not None
        assert updated.start_time is None
        assert updated.end_time is None


class TestUpdateTestTaskProgress:
    def test_update_progress_normal(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_prog_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1, 2, 3],
            executor_id=testUser.id,
        )
        updated = update_test_task_progress(
            db=db, task_id=task.id, project_id=testProject.id, progress=50
        )
        assert updated is not None
        assert updated.progress == 50

    def test_update_progress_with_counts(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_cnt_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1, 2, 3],
            executor_id=testUser.id,
        )
        updated = update_test_task_progress(
            db=db,
            task_id=task.id,
            project_id=testProject.id,
            progress=100,
            success_count=2,
            fail_count=1,
        )
        assert updated.progress == 100
        assert updated.success_count == 2
        assert updated.fail_count == 1

    def test_update_progress_partial_counts(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_part_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1, 2],
            executor_id=testUser.id,
        )
        updated = update_test_task_progress(
            db=db,
            task_id=task.id,
            project_id=testProject.id,
            progress=50,
            success_count=1,
        )
        assert updated.success_count == 1
        assert updated.fail_count == 0

    def test_update_progress_nonexistent(self, db, testProject):
        result = update_test_task_progress(
            db=db, task_id=99999, project_id=testProject.id, progress=50
        )
        assert result is None

    def test_update_progress_boundary_zero(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_zero_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_progress(
            db=db, task_id=task.id, project_id=testProject.id, progress=0
        )
        assert updated.progress == 0

    def test_update_progress_boundary_hundred(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_full_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        updated = update_test_task_progress(
            db=db, task_id=task.id, project_id=testProject.id, progress=100
        )
        assert updated.progress == 100


class TestDeleteTestTask:
    def test_delete_test_task_normal(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_del_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        result = delete_test_task(db=db, task_id=task.id, project_id=testProject.id)
        assert result is True
        found = get_test_task_by_id(db=db, task_id=task.id, project_id=testProject.id)
        assert found is None

    def test_delete_test_task_nonexistent(self, db, testProject):
        result = delete_test_task(db=db, task_id=99999, project_id=testProject.id)
        assert result is False

    def test_delete_test_task_wrong_project(self, db, testProject, testUser):
        task = create_test_task(
            db=db,
            task_name=f"task_wdel_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            case_ids=[1],
            executor_id=testUser.id,
        )
        result = delete_test_task(db=db, task_id=task.id, project_id=99999)
        assert result is False
