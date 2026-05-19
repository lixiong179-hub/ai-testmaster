import pytest
from app.crud.iteration import (
    create_iteration,
    get_iteration,
    get_iterations_by_project,
    get_iterations_count_by_project,
    update_iteration,
    delete_iteration,
)


class TestCreateIterationCrud:
    def test_create_basic(self, db, testProject):
        it = create_iteration(db, testProject.id, "crud_iter_1")
        assert it.id is not None
        assert it.name == "crud_iter_1"
        assert it.status == "draft"

    def test_duplicate_name_raises(self, db, testProject):
        create_iteration(db, testProject.id, "dup_crud_iter")
        with pytest.raises(ValueError, match="同名迭代"):
            create_iteration(db, testProject.id, "dup_crud_iter")

    def test_create_with_all_fields(self, db, testProject):
        from datetime import datetime
        it = create_iteration(
            db, testProject.id, "full_iter",
            version="v2.0", description="描述", status="in_pipeline",
            start_date=datetime.now(), end_date=datetime.now(),
        )
        assert it.version == "v2.0"
        assert it.description == "描述"
        assert it.status == "in_pipeline"


class TestGetIteration:
    def test_found(self, db, testProject):
        it = create_iteration(db, testProject.id, "get_iter")
        found = get_iteration(db, it.id)
        assert found is not None

    def test_not_found(self, db):
        assert get_iteration(db, 99999) is None


class TestGetIterationsByProject:
    def test_returns_iterations(self, db, testProject):
        create_iteration(db, testProject.id, "list_iter_1")
        create_iteration(db, testProject.id, "list_iter_2")
        result = get_iterations_by_project(db, testProject.id)
        assert len(result) >= 2

    def test_empty_project(self, db):
        result = get_iterations_by_project(db, 99999)
        assert len(result) == 0


class TestGetIterationsCountByProject:
    def test_count(self, db, testProject):
        create_iteration(db, testProject.id, "count_iter")
        count = get_iterations_count_by_project(db, testProject.id)
        assert count >= 1


class TestUpdateIteration:
    def test_update_name(self, db, testProject):
        it = create_iteration(db, testProject.id, "upd_iter")
        updated = update_iteration(db, it.id, name="new_name")
        assert updated.name == "new_name"

    def test_update_same_name_allowed(self, db, testProject):
        it = create_iteration(db, testProject.id, "same_name_iter")
        updated = update_iteration(db, it.id, name="same_name_iter")
        assert updated.name == "same_name_iter"

    def test_update_duplicate_name_raises(self, db, testProject):
        create_iteration(db, testProject.id, "existing_name")
        it2 = create_iteration(db, testProject.id, "other_name")
        with pytest.raises(ValueError, match="同名迭代"):
            update_iteration(db, it2.id, name="existing_name")

    def test_update_status_forbidden(self, db, testProject):
        it = create_iteration(db, testProject.id, "status_iter")
        with pytest.raises(ValueError, match="禁止直接修改"):
            update_iteration(db, it.id, status="finalized")

    def test_update_nonexistent(self, db):
        result = update_iteration(db, 99999, name="x")
        assert result is None

    def test_update_description(self, db, testProject):
        it = create_iteration(db, testProject.id, "desc_iter")
        updated = update_iteration(db, it.id, description="新描述")
        assert updated.description == "新描述"


class TestDeleteIteration:
    def test_delete_existing(self, db, testProject):
        it = create_iteration(db, testProject.id, "del_iter")
        result = delete_iteration(db, it.id)
        assert result is True
        assert get_iteration(db, it.id) is None

    def test_delete_nonexistent(self, db):
        result = delete_iteration(db, 99999)
        assert result is False

    def test_delete_with_cleanup_callback(self, db, testProject):
        it = create_iteration(db, testProject.id, "callback_iter")
        callback_called = []
        def cleanup():
            callback_called.append(True)
        result = delete_iteration(db, it.id, cleanup_callback=cleanup)
        assert result is True
        assert len(callback_called) == 1
