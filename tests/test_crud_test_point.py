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
from app.crud.test_point_management import (
    get_requirements_by_project,
    get_test_point_list_stats,
)
from app.models.requirement import Requirement
from tests.helpers import createTestProject, createTestUser, createTestTestCase


class TestCreateTestPoint:
    def test_create_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
            point="valid credentials login",
            priority=1,
        )
        assert point is not None
        assert point.id is not None
        assert point.project_id == testProject.id
        assert point.module == "login"
        assert point.point == "valid credentials login"
        assert point.priority == 1

    def test_create_test_point_with_ai_prompt(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="search",
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
            point="logout clears session",
            priority=3,
        )
        assert point.ai_prompt is None

    def test_create_test_point_with_created_by(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="creator",
            point="creator point",
            priority=2,
            created_by="qa_admin",
        )
        assert point.created_by == "qa_admin"

    def test_create_test_point_boundary_priority(self, db, testProject):
        for p in [1, 2, 3]:
            point = create_test_point(
                db=db,
                project_id=testProject.id,
                module="boundary",
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
            point="point x",
            priority=1,
        )
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="module_y",
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
            point="old point",
            priority=3,
        )
        updated = update_test_point(
            db=db,
            test_point_id=point.id,
            project_id=testProject.id,
            module="new_mod",
            point="new point",
            priority=1,
            ai_prompt="new prompt",
        )
        assert updated.module == "new_mod"
        assert updated.point == "new point"
        assert updated.priority == 1
        assert updated.ai_prompt == "new prompt"


class TestDeleteTestPoint:
    def test_delete_test_point_normal(self, db, testProject):
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="login",
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
                "point": "batch point 1",
                "priority": 1,
            },
            {
                "module": "batch_mod",
                "point": "batch point 2",
                "priority": 2,
                "ai_prompt": "batch prompt",
            },
        ]
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=data)
        assert len(points) == 2
        assert points[1].ai_prompt == "batch prompt"
        assert all(p.project_id == testProject.id for p in points)

    def test_batch_create_single_item(self, db, testProject):
        data = [
            {
                "module": "single_mod",
                "point": "single point",
                "priority": 3,
            },
        ]
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=data)
        assert len(points) == 1

    def test_batch_create_empty_list(self, db, testProject):
        points = batch_create_test_points(db=db, project_id=testProject.id, test_points_data=[])
        assert points == []


class TestTestPointManagementCrud:
    def test_get_test_point_list_stats_counts_cases(self, db, testProject, testUser):
        high_point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="stats_module",
            point="high point",
            priority=1,
            created_by=testUser.username,
        )
        medium_point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="stats_module",
            point="medium point",
            priority=2,
            created_by=testUser.username,
        )
        create_test_point(
            db=db,
            project_id=testProject.id,
            module="stats_module",
            point="low point",
            priority=3,
            created_by=testUser.username,
        )
        createTestTestCase(
            db=db,
            projectId=testProject.id,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            module="stats_module",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=1,
            case_type="manual",
            test_point_id=high_point.id,
        )
        createTestTestCase(
            db=db,
            projectId=testProject.id,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            module="stats_module",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="manual",
            test_point_id=medium_point.id,
        )

        stats = get_test_point_list_stats(
            db=db,
            project_id=testProject.id,
            user_id=testUser.id,
            module="stats_module",
        )

        assert stats["total"] == 3
        assert stats["high_priority_count"] == 1
        assert stats["medium_priority_count"] == 1
        assert stats["low_priority_count"] == 1
        assert stats["generated_case_count"] == 2

    def test_get_requirements_by_project_returns_project_scoped_items(self, db, testProject, testUser):
        other_user = createTestUser(db=db)
        other_project = createTestProject(db=db, userId=other_user.id)
        visible_requirement = Requirement(
            project_id=testProject.id,
            req_no=f"REQ-{uuid.uuid4().hex[:8]}",
            title="Visible requirement",
            description="visible",
            priority=1,
            status="draft",
        )
        hidden_requirement = Requirement(
            project_id=other_project.id,
            req_no=f"REQ-{uuid.uuid4().hex[:8]}",
            title="Hidden requirement",
            description="hidden",
            priority=1,
            status="draft",
        )
        db.add_all([visible_requirement, hidden_requirement])
        db.flush()

        requirements = get_requirements_by_project(
            db=db,
            project_id=testProject.id,
            user_id=testUser.id,
        )

        assert [item.id for item in requirements] == [visible_requirement.id]

    def test_batch_create_uses_default_created_by(self, db, testProject):
        data = [
            {
                "module": "creator_mod",
                "point": "creator point 1",
                "priority": 1,
            },
            {
                "module": "creator_mod",
                "point": "creator point 2",
                "priority": 2,
            },
        ]
        points = batch_create_test_points(
            db=db,
            project_id=testProject.id,
            test_points_data=data,
            created_by="batch_user",
        )
        assert len(points) == 2
        assert all(point.created_by == "batch_user" for point in points)
