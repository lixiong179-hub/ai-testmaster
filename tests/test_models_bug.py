import pytest
from app.models.bug import Bug
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="bug_test_user",
        email="bug_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(Bug).filter(Bug.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="Bug测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestBugModel:
    def test_create_bug(self, db, test_project, test_user):
        bug = Bug(
            bug_no="BUG-MODEL-001",
            project_id=test_project.id,
            title="登录按钮无法点击",
            description="点击登录按钮无响�?,
            severity=1,
            priority=1,
            reporter_id=test_user.id
        )
        db.add(bug)
        db.commit()
        db.refresh(bug)
        assert bug.id is not None
        assert bug.bug_no == "BUG-MODEL-001"
        assert bug.project_id == test_project.id
        assert bug.title == "登录按钮无法点击"
        assert bug.description == "点击登录按钮无响�?
        assert bug.severity == 1
        assert bug.priority == 1
        assert bug.reporter_id == test_user.id
        assert bug.update_time is not None
        db.delete(bug)
        db.commit()

    def test_bug_default_values(self, db, test_project, test_user):
        bug = Bug(
            bug_no="BUG-DEF-001",
            project_id=test_project.id,
            title="默认值Bug",
            description="描述",
            severity=2,
            priority=2,
            reporter_id=test_user.id
        )
        db.add(bug)
        db.commit()
        db.refresh(bug)
        assert bug.assignee_id is None
        assert bug.test_case_id is None
        assert bug.test_result_id is None
        assert bug.reproduction_steps is None
        assert bug.expected_behavior is None
        assert bug.actual_behavior is None
        assert bug.attachments is None
        db.delete(bug)
        db.commit()

    def test_bug_unique_bug_no(self, db, test_project, test_user):
        bug1 = Bug(bug_no="BUG-UNIQUE-001", project_id=test_project.id, title="唯一1", description="描述", severity=1, priority=1, reporter_id=test_user.id)
        db.add(bug1)
        db.commit()
        nested = db.begin_nested()
        bug2 = Bug(bug_no="BUG-UNIQUE-001", project_id=test_project.id, title="唯一2", description="描述", severity=1, priority=1, reporter_id=test_user.id)
        db.add(bug2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_bug_severity_values(self, db, test_project, test_user):
        for sev in [1, 2, 3, 4]:
            bug = Bug(
                bug_no=f"BUG-SEV-{sev}",
                project_id=test_project.id,
                title=f"严重程度{sev}",
                description="描述",
                severity=sev,
                priority=1,
                reporter_id=test_user.id
            )
            db.add(bug)
            db.commit()
            db.refresh(bug)
            assert bug.severity == sev
            db.delete(bug)
            db.commit()

    def test_bug_with_assignee(self, db, test_project, test_user):
        assignee = User(
            username="bug_assignee",
            email="bug_assignee@example.com",
            password_hash="hash"
        )
        db.add(assignee)
        db.commit()
        db.refresh(assignee)
        bug = Bug(
            bug_no="BUG-ASSIGN-001",
            project_id=test_project.id,
            title="指派Bug",
            description="描述",
            severity=1,
            priority=1,
            reporter_id=test_user.id,
            assignee_id=assignee.id
        )
        db.add(bug)
        db.commit()
        db.refresh(bug)
        assert bug.assignee_id == assignee.id
        db.delete(bug)
        db.delete(assignee)
        db.commit()

    def test_bug_reproduction_info(self, db, test_project, test_user):
        bug = Bug(
            bug_no="BUG-REPRO-001",
            project_id=test_project.id,
            title="复现Bug",
            description="描述",
            severity=1,
            priority=1,
            reporter_id=test_user.id,
            reproduction_steps="1.打开页面 2.点击按钮",
            expected_behavior="按钮响应",
            actual_behavior="按钮无响�?,
            attachments='["screenshot.png"]'
        )
        db.add(bug)
        db.commit()
        db.refresh(bug)
        assert bug.reproduction_steps == "1.打开页面 2.点击按钮"
        assert bug.expected_behavior == "按钮响应"
        assert bug.actual_behavior == "按钮无响�?
        assert bug.attachments == '["screenshot.png"]'
        db.delete(bug)
        db.commit()

    def test_bug_repr(self, db, test_project, test_user):
        bug = Bug(
            bug_no="BUG-REPR-001",
            project_id=test_project.id,
            title="Repr测试",
            description="描述",
            severity=1,
            priority=1,
            reporter_id=test_user.id
        )
        db.add(bug)
        db.commit()
        db.refresh(bug)
        repr_str = repr(bug)
        assert "Bug" in repr_str
        assert "BUG-REPR-001" in repr_str
        db.delete(bug)
        db.commit()

    def test_bug_relationships(self):
        assert hasattr(Bug, 'project')
        assert hasattr(Bug, 'reporter')
        assert hasattr(Bug, 'assignee')
