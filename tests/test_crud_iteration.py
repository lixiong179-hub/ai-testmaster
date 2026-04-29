import uuid
import pytest
from datetime import datetime
from app.crud.iteration import (
    create_iteration,
    get_iteration,
    get_iterations_by_project,
    get_iterations_count_by_project,
    update_iteration,
    delete_iteration,
)
from tests.helpers import createTestProject, createTestUser


class TestCreateIteration:
    def test_create_iteration_normal(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"sprint_{uuid.uuid4().hex[:8]}",
        )
        assert iteration is not None
        assert iteration.id is not None
        assert iteration.project_id == testProject.id
        assert iteration.version == "v1.0"
        assert iteration.status == "planning"

    def test_create_iteration_with_all_fields(self, db, testProject):
        now = datetime.now()
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"full_iter_{uuid.uuid4().hex[:8]}",
            version="v2.0",
            description="full iteration test",
            status="active",
            start_date=now,
            end_date=now,
        )
        assert iteration.version == "v2.0"
        assert iteration.description == "full iteration test"
        assert iteration.status == "active"
        assert iteration.start_date is not None
        assert iteration.end_date is not None

    def test_create_iteration_duplicate_name(self, db, testProject):
        name = f"dup_{uuid.uuid4().hex[:8]}"
        create_iteration(db=db, project_id=testProject.id, name=name)
        with pytest.raises(ValueError, match="项目下已存在同名迭代"):
            create_iteration(db=db, project_id=testProject.id, name=name)

    def test_create_iteration_different_project_same_name(self, db, testUser):
        proj1 = createTestProject(db=db, userId=testUser.id, name=f"proj1_{uuid.uuid4().hex[:8]}")
        proj2 = createTestProject(db=db, userId=testUser.id, name=f"proj2_{uuid.uuid4().hex[:8]}")
        name = f"same_name_{uuid.uuid4().hex[:8]}"
        iter1 = create_iteration(db=db, project_id=proj1.id, name=name)
        iter2 = create_iteration(db=db, project_id=proj2.id, name=name)
        assert iter1.project_id != iter2.project_id
        assert iter1.name == iter2.name

    def test_create_iteration_status_values(self, db, testProject):
        for status in ["planning", "active", "completed", "archived"]:
            iteration = create_iteration(
                db=db,
                project_id=testProject.id,
                name=f"status_{status}_{uuid.uuid4().hex[:8]}",
                status=status,
            )
            assert iteration.status == status


class TestGetIteration:
    def test_get_iteration_normal(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"get_iter_{uuid.uuid4().hex[:8]}",
        )
        found = get_iteration(db=db, iteration_id=iteration.id)
        assert found is not None
        assert found.id == iteration.id

    def test_get_iteration_nonexistent(self, db):
        found = get_iteration(db=db, iteration_id=99999)
        assert found is None


class TestGetIterationsByProject:
    def test_get_iterations_by_project_normal(self, db, testProject):
        for i in range(3):
            create_iteration(
                db=db,
                project_id=testProject.id,
                name=f"list_iter_{i}_{uuid.uuid4().hex[:8]}",
            )
        iterations = get_iterations_by_project(db=db, project_id=testProject.id)
        assert len(iterations) >= 3

    def test_get_iterations_by_project_pagination(self, db, testProject):
        for i in range(5):
            create_iteration(
                db=db,
                project_id=testProject.id,
                name=f"page_iter_{i}_{uuid.uuid4().hex[:8]}",
            )
        first = get_iterations_by_project(db=db, project_id=testProject.id, skip=0, limit=2)
        assert len(first) <= 2

    def test_get_iterations_by_project_empty(self, db):
        iterations = get_iterations_by_project(db=db, project_id=99999)
        assert iterations == []


class TestGetIterationsCountByProject:
    def test_get_iterations_count_normal(self, db, testProject):
        create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"cnt_iter_{uuid.uuid4().hex[:8]}",
        )
        count = get_iterations_count_by_project(db=db, project_id=testProject.id)
        assert count >= 1

    def test_get_iterations_count_empty(self, db):
        count = get_iterations_count_by_project(db=db, project_id=99999)
        assert count == 0


class TestUpdateIteration:
    def test_update_iteration_normal(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"upd_iter_{uuid.uuid4().hex[:8]}",
        )
        updated = update_iteration(
            db=db,
            iteration_id=iteration.id,
            description="updated description",
            status="active",
        )
        assert updated is not None
        assert updated.description == "updated description"
        assert updated.status == "active"
        assert updated.update_time is not None

    def test_update_iteration_name(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"rename_iter_{uuid.uuid4().hex[:8]}",
        )
        newName = f"renamed_{uuid.uuid4().hex[:8]}"
        updated = update_iteration(db=db, iteration_id=iteration.id, name=newName)
        assert updated.name == newName

    def test_update_iteration_duplicate_name(self, db, testProject):
        name1 = f"exist_{uuid.uuid4().hex[:8]}"
        name2 = f"other_{uuid.uuid4().hex[:8]}"
        create_iteration(db=db, project_id=testProject.id, name=name1)
        iter2 = create_iteration(db=db, project_id=testProject.id, name=name2)
        with pytest.raises(ValueError, match="项目下已存在同名迭代"):
            update_iteration(db=db, iteration_id=iter2.id, name=name1)

    def test_update_iteration_nonexistent(self, db):
        result = update_iteration(db=db, iteration_id=99999, description="should not update")
        assert result is None

    def test_update_iteration_same_name_allowed(self, db, testProject):
        name = f"same_{uuid.uuid4().hex[:8]}"
        iteration = create_iteration(db=db, project_id=testProject.id, name=name)
        updated = update_iteration(db=db, iteration_id=iteration.id, name=name)
        assert updated is not None
        assert updated.name == name

    def test_update_iteration_none_values_ignored(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"none_iter_{uuid.uuid4().hex[:8]}",
            description="keep this",
        )
        updated = update_iteration(db=db, iteration_id=iteration.id, description=None)
        assert updated.description == "keep this"


class TestDeleteIteration:
    def test_delete_iteration_normal(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"del_iter_{uuid.uuid4().hex[:8]}",
        )
        result = delete_iteration(db=db, iteration_id=iteration.id)
        assert result is True
        found = get_iteration(db=db, iteration_id=iteration.id)
        assert found is None

    def test_delete_iteration_nonexistent(self, db):
        result = delete_iteration(db=db, iteration_id=99999)
        assert result is False

    def test_delete_iteration_with_cleanup_callback(self, db, testProject):
        callbackCalled = {"value": False}

        def cleanup():
            callbackCalled["value"] = True

        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"cb_iter_{uuid.uuid4().hex[:8]}",
        )
        result = delete_iteration(db=db, iteration_id=iteration.id, cleanup_callback=cleanup)
        assert result is True
        assert callbackCalled["value"] is True

    def test_delete_iteration_without_cleanup_callback(self, db, testProject):
        iteration = create_iteration(
            db=db,
            project_id=testProject.id,
            name=f"nocb_iter_{uuid.uuid4().hex[:8]}",
        )
        result = delete_iteration(db=db, iteration_id=iteration.id, cleanup_callback=None)
        assert result is True
