import uuid
import pytest
from app.crud.test_point import (
    create_test_point,
    get_test_point_by_id,
    get_test_points_by_project,
    get_test_points_by_project_and_user,
    update_test_point,
    delete_test_point,
    get_test_points_count,
    batch_create_test_points,
)
from tests.helpers import createTestProject, createTestUser


class TestCreateTestPoint:
    def test_create_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="password login",
            point="valid credentials login",
            priority=1,
        )
        assert point is not None
        assert point.id is not None
        assert point.project_id == testProject.id
        assert point.module == "login"
        assert point.function == "password login"
        assert point.point == "valid credentials login"
        assert point.priority == 1

    def test_create_test_point_with_ai_prompt(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="search",
            function="keyword search",
            point="search with special chars",
            priority=2,
            ai_prompt="focus on XSS scenarios",
        )
        assert point.ai_prompt == "focus on XSS scenarios"

    def test_create_test_point_without_ai_prompt(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="logout",
            function="session logout",
            point="logout clears session",
            priority=3,
        )
        assert point.ai_prompt is None

    def test_create_test_point_boundary_priority(self, db, testProject):
        for p in [1, 2, 3]:
            point = create_test_point(
                db=db,
                project_id=testProject.id,
                module="boundary",
                function=f"priority {p}",
                point=f"priority {p} test",
                priority=p,
            )
            assert point.priority == p


class TestGetTestPointById:
    def test_get_test_point_by_id_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="valid login",
            priority=1,
        )
        found = get_test_point_by_id(db=db, test_point_id=point.id, project_id=testProject.id)
        assert found is not None
        assert found.id == point.id

    def test_get_test_point_by_id_nonexistent(self, db, testProject):
        found = get_test_point_by_id(db=db, test_point_id=99999, project_id=testProject.id)
        assert found is None

    def test_get_test_point_by_id_wrong_project(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="valid login",
            priority=1,
        )
        found = get_test_point_by_id(db=db, test_point_id=point.id, project_id=99999)
        assert found is None


class TestGetTestPointsByProject:
    def test_get_test_points_by_project_normal(self, db, testProject):
        for i in range(3):
            create_test_point(
                db=db,
                project_id=testProject.id,
                module="list_mod",
                function=f"func_{i}",
                point=f"point_{i}",
                priority=2,
            )
        points = get_test_points_by_project(db=db, project_id=testProject.id)
        assert len(points) >= 3

    def test_get_test_points_by_project_with_module_filter(self, db, testProject):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="module_x",
            function="func_x",
            point="point x",
            priority=1,
        )
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="module_y",
            function="func_y",
            point="point y",
            priority=2,
        )
        points = get_test_points_by_project(db=db, project_id=testProject.id, module="module_x")
        assert all(p.module == "module_x" for p in points)

    def test_get_test_points_by_project_with_priority_filter(self, db, testProject):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="pri_filter",
            function="high pri",
            point="high priority point",
            priority=1,
        )
        points = get_test_points_by_project(db=db, project_id=testProject.id, priority=1)
        assert all(p.priority == 1 for p in points)

    def test_get_test_points_by_project_pagination(self, db, testProject):
        for i in range(5):
            create_test_point(
                db=db,
                project_id=testProject.id,
                module="page_mod",
                function=f"func_{i}",
                point=f"point_{i}",
                priority=2,
            )
        first = get_test_points_by_project(db=db, project_id=testProject.id, skip=0, limit=2)
        assert len(first) <= 2

    def test_get_test_points_by_project_empty(self, db):
        points = get_test_points_by_project(db=db, project_id=99999)
        assert points == []


class TestGetTestPointsByProjectAndUser:
    def test_get_test_points_by_project_and_user_normal(self, db, testProject, testUser):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="user_mod",
            function="user func",
            point="user point",
            priority=1,
        )
        points = get_test_points_by_project_and_user(
            db=db, project_id=testProject.id, user_id=testUser.id
        )
        assert len(points) >= 1

    def test_get_test_points_by_project_and_user_wrong_user(self, db, testProject):
        points = get_test_points_by_project_and_user(
            db=db, project_id=testProject.id, user_id=99999
        )
        assert points == []

    def test_get_test_points_by_project_and_user_with_filters(self, db, testProject, testUser):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="filter_mod",
            function="filter func",
            point="filter point",
            priority=1,
        )
        points = get_test_points_by_project_and_user(
            db=db, project_id=testProject.id, user_id=testUser.id, module="filter_mod", priority=1
        )
        assert all(p.module == "filter_mod" for p in points)


class TestUpdateTestPoint:
    def test_update_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="original point",
            priority=2,
        )
        updated = update_test_point(
            db=db,
            test_point_id=point.id,
            project_id=testProject.id,
            point="updated point",
            priority=1,
        )
        assert updated is not None
        assert updated.point == "updated point"
        assert updated.priority == 1

    def test_update_test_point_nonexistent(self, db, testProject):
        result = update_test_point(
            db=db, test_point_id=99999, project_id=testProject.id, point="should not update"
        )
        assert result is None

    def test_update_test_point_wrong_project(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="original",
            priority=2,
        )
        result = update_test_point(
            db=db, test_point_id=point.id, project_id=99999, point="should not update"
        )
        assert result is None

    def test_update_test_point_multiple_fields(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="old_mod",
            function="old_func",
            point="old point",
            priority=3,
        )
        updated = update_test_point(
            db=db,
            test_point_id=point.id,
            project_id=testProject.id,
            module="new_mod",
            function="new_func",
            point="new point",
            priority=1,
            ai_prompt="new prompt",
        )
        assert updated.module == "new_mod"
        assert updated.function == "new_func"
        assert updated.point == "new point"
        assert updated.priority == 1
        assert updated.ai_prompt == "new prompt"


class TestDeleteTestPoint:
    def test_delete_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="to be deleted",
            priority=2,
        )
        result = delete_test_point(db=db, test_point_id=point.id, project_id=testProject.id)
        assert result is True
        found = get_test_point_by_id(db=db, test_point_id=point.id, project_id=testProject.id)
        assert found is None

    def test_delete_test_point_nonexistent(self, db, testProject):
        result = delete_test_point(db=db, test_point_id=99999, project_id=testProject.id)
        assert result is False

    def test_delete_test_point_wrong_project(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            function="login check",
            point="to be deleted",
            priority=2,
        )
        result = delete_test_point(db=db, test_point_id=point.id, project_id=99999)
        assert result is False


class TestGetTestPointsCount:
    def test_get_test_points_count_normal(self, db, testProject, testUser):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="count_mod",
            function="count func",
            point="count point",
            priority=1,
        )
        count = get_test_points_count(db=db, project_id=testProject.id, user_id=testUser.id)
        assert count >= 1

    def test_get_test_points_count_with_filters(self, db, testProject, testUser):
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="filter_cnt",
            function="filter func",
            point="filter point",
            priority=1,
        )
        count = get_test_points_count(
            db=db, project_id=testProject.id, user_id=testUser.id, module="filter_cnt", priority=1
        )
        assert count >= 1

    def test_get_test_points_count_wrong_user(self, db, testProject):
        count = get_test_points_count(db=db, project_id=testProject.id, user_id=99999)
        assert count == 0


class TestBatchCreateTestPoints:
    def test_batch_create_normal(self, db, testProject):
        data = [
            {
                "module": "batch_mod",
                "function": "batch func 1",
                "point": "batch point 1",
                "priority": 1,
            },
            {
                "module": "batch_mod",
                "function": "batch func 2",
                "point": "batch point 2",
                "priority": 2,
                "ai_prompt": "batch prompt",
            },
        ]
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=data)
        assert len(points) == 2
        assert points[0].function == "batch func 1"
        assert points[1].ai_prompt == "batch prompt"
        assert all(p.project_id == testProject.id for p in points)

    def test_batch_create_single_item(self, db, testProject):
        data = [
            {
                "module": "single_mod",
                "function": "single func",
                "point": "single point",
                "priority": 3,
            },
        ]
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=data)
        assert len(points) == 1

    def test_batch_create_empty_list(self, db, testProject):
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=[])
        assert points == []
