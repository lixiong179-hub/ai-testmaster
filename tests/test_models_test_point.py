import pytest
from app.models.test_point import TestPoint
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="tp_test_user",
        email="tp_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestPoint).filter(TestPoint.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="测试点项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestTestPointModel:
    def test_create_test_point(self, db, test_project):
        tp = TestPoint(
            project_id=test_project.id,
            module="登录模块",
            function="账号密码登录",
            point="验证用户登录功能",
            priority=1
        )
        db.add(tp)
        db.commit()
        db.refresh(tp)
        assert tp.id is not None
        assert tp.project_id == test_project.id
        assert tp.module == "登录模块"
        assert tp.function == "账号密码登录"
        assert tp.point == "验证用户登录功能"
        assert tp.priority == 1
        assert tp.create_time is not None
        db.delete(tp)
        db.commit()

    def test_test_point_default_values(self, db, test_project):
        tp = TestPoint(
            project_id=test_project.id,
            module="模块",
            function="功能",
            point="测试点",
            priority=2
        )
        db.add(tp)
        db.commit()
        db.refresh(tp)
        assert tp.requirement_id is None
        assert tp.ai_prompt is None
        db.delete(tp)
        db.commit()

    def test_test_point_priority_values(self, db, test_project):
        for priority in [1, 2, 3]:
            tp = TestPoint(
                project_id=test_project.id,
                module="模块",
                function="功能",
                point=f"优先级{priority}",
                priority=priority
            )
            db.add(tp)
            db.commit()
            db.refresh(tp)
            assert tp.priority == priority
            db.delete(tp)
            db.commit()

    def test_test_point_with_ai_prompt(self, db, test_project):
        tp = TestPoint(
            project_id=test_project.id,
            module="模块",
            function="功能",
            point="AI测试点",
            priority=1,
            ai_prompt="请分析登录功能的测试点"
        )
        db.add(tp)
        db.commit()
        db.refresh(tp)
        assert tp.ai_prompt == "请分析登录功能的测试点"
        db.delete(tp)
        db.commit()

    def test_test_point_relationships(self):
        assert hasattr(TestPoint, 'project')
        assert hasattr(TestPoint, 'requirement')
