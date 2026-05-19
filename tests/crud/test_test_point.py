import pytest
from app.crud.test_point import (
    create_test_point,
    get_test_point_by_id,
    get_test_points_by_project,
    get_test_points_by_project_and_user,
    get_test_points_count,
    update_test_point,
    delete_test_point,
    batch_create_test_points,
)


class TestCreateTestPoint:
    def test_create_normal(self, db, testProject):
        tp = create_test_point(
            db=db,
            project_id=testProject.id,
            module="登录模块",
            point="用户名验证",
            priority=1,
            created_by="tester",
        )
        assert tp.id is not None
        assert tp.module == "登录模块"
        assert tp.point == "用户名验证"
        assert tp.priority == 1
        assert tp.created_by == "tester"

    def test_create_with_optional_fields(self, db, testProject):
        tp = create_test_point(
            db=db,
            project_id=testProject.id,
            module="注册",
            point="邮箱格式",
            priority=2,
            ai_prompt='{"function": "注册"}',
        )
        assert tp.ai_prompt == '{"function": "注册"}'

    def test_create_default_status(self, db, testProject):
        tp = create_test_point(
            db=db,
            project_id=testProject.id,
            module="M",
            point="P",
            priority=3,
        )
        assert tp.status == "active"


class TestGetTestPointById:
    def test_get_existing(self, db, testProject):
        tp = create_test_point(
            db=db, project_id=testProject.id, module="M", point="P", priority=2,
        )
        result = get_test_point_by_id(db, tp.id, testProject.id)
        assert result is not None
        assert result.id == tp.id

    def test_get_nonexistent(self, db, testProject):
        result = get_test_point_by_id(db, 99999, testProject.id)
        assert result is None

    def test_get_wrong_project(self, db, testProject):
        tp = create_test_point(
            db=db, project_id=testProject.id, module="M", point="P", priority=2,
        )
        result = get_test_point_by_id(db, tp.id, 99999)
        assert result is None


class TestGetTestPointsByProject:
    def test_get_all(self, db, testProject):
        for i in range(3):
            create_test_point(
                db=db, project_id=testProject.id,
                module=f"M{i}", point=f"P{i}", priority=2,
            )
        results = get_test_points_by_project(db, testProject.id)
        assert len(results) >= 3

    def test_filter_by_module(self, db, testProject):
        create_test_point(
            db=db, project_id=testProject.id,
            module="唯一模块", point="P1", priority=2,
        )
        results = get_test_points_by_project(db, testProject.id, module="唯一模块")
        assert all(tp.module == "唯一模块" for tp in results)

    def test_filter_by_priority(self, db, testProject):
        create_test_point(
            db=db, project_id=testProject.id,
            module="M", point="P优先", priority=1,
        )
        results = get_test_points_by_project(db, testProject.id, priority=1)
        assert all(tp.priority == 1 for tp in results)

    def test_pagination(self, db, testProject):
        for i in range(5):
            create_test_point(
                db=db, project_id=testProject.id,
                module=f"PageM{i}", point=f"PageP{i}", priority=2,
            )
        results = get_test_points_by_project(db, testProject.id, skip=0, limit=2)
        assert len(results) <= 2


class TestGetTestPointsByProjectAndUser:
    def test_get_by_user(self, db, testProject):
        create_test_point(
            db=db, project_id=testProject.id, module="UM", point="UP", priority=2,
        )
        results = get_test_points_by_project_and_user(
            db, testProject.id, testProject.user_id,
        )
        assert len(results) >= 1

    def test_wrong_user_returns_empty(self, db, testProject):
        results = get_test_points_by_project_and_user(db, testProject.id, 99999)
        assert len(results) == 0


class TestGetTestPointsCount:
    def test_count(self, db, testProject):
        create_test_point(
            db=db, project_id=testProject.id, module="CM", point="CP", priority=2,
        )
        count = get_test_points_count(db, testProject.id, testProject.user_id)
        assert count >= 1


class TestUpdateTestPoint:
    def test_update_module(self, db, testProject):
        tp = create_test_point(
            db=db, project_id=testProject.id, module="Old", point="P", priority=2,
        )
        old_version = tp.version
        updated = update_test_point(db, tp.id, testProject.id, module="New")
        assert updated is not None
        assert updated.module == "New"
        assert updated.version == (old_version or 1) + 1

    def test_update_nonexistent(self, db, testProject):
        result = update_test_point(db, 99999, testProject.id, module="X")
        assert result is None


class TestDeleteTestPoint:
    def test_delete_existing(self, db, testProject):
        tp = create_test_point(
            db=db, project_id=testProject.id, module="DM", point="DP", priority=2,
        )
        result = delete_test_point(db, tp.id, testProject.id)
        assert result is True
        assert get_test_point_by_id(db, tp.id, testProject.id) is None

    def test_delete_nonexistent(self, db, testProject):
        result = delete_test_point(db, 99999, testProject.id)
        assert result is False


class TestBatchCreateTestPoints:
    def test_batch_create(self, db, testProject):
        data = [
            {"module": "BM1", "point": "BP1", "priority": 1},
            {"module": "BM2", "point": "BP2", "priority": 2},
        ]
        results = batch_create_test_points(
            db=db, project_id=testProject.id,
            test_points_data=data, created_by="batch_user",
        )
        assert len(results) == 2
        assert results[0].module == "BM1"
        assert results[1].created_by == "batch_user"

    def test_batch_create_empty(self, db, testProject):
        results = batch_create_test_points(
            db=db, project_id=testProject.id,
            test_points_data=[], created_by="batch_user",
        )
        assert len(results) == 0
