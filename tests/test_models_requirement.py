import pytest
from app.models.requirement import Requirement
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="req_test_user",
        email="req_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(Requirement).filter(Requirement.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="需求测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestRequirementModel:
    def test_create_requirement(self, db, test_project):
        req = Requirement(
            project_id=test_project.id,
            req_no="REQ-MODEL-001",
            title="用户登录需求",
            description="支持账号密码登录",
            priority=1
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.id is not None
        assert req.project_id == test_project.id
        assert req.req_no == "REQ-MODEL-001"
        assert req.title == "用户登录需求"
        assert req.description == "支持账号密码登录"
        assert req.priority == 1
        assert req.status == "draft"
        assert req.create_time is not None
        db.delete(req)
        db.commit()

    def test_requirement_default_values(self, db, test_project):
        req = Requirement(
            project_id=test_project.id,
            req_no="REQ-DEF-001",
            title="默认需求",
            description="描述",
            priority=2
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.status == "draft"
        assert req.source_file_id is None
        assert req.update_time is not None
        db.delete(req)
        db.commit()

    def test_requirement_unique_req_no(self, db, test_project):
        req1 = Requirement(project_id=test_project.id, req_no="REQ-UNIQUE-001", title="唯一1", description="描述", priority=1)
        db.add(req1)
        db.commit()
        nested = db.begin_nested()
        req2 = Requirement(project_id=test_project.id, req_no="REQ-UNIQUE-001", title="唯一2", description="描述", priority=1)
        db.add(req2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_requirement_status_values(self, db, test_project):
        for status in ["draft", "approved", "developing", "testing", "completed", "cancelled"]:
            req = Requirement(
                project_id=test_project.id,
                req_no=f"REQ-STA-{status}",
                title=f"状态{status}",
                description="描述",
                priority=1,
                status=status
            )
            db.add(req)
            db.commit()
            db.refresh(req)
            assert req.status == status
            db.delete(req)
            db.commit()

    def test_requirement_priority_values(self, db, test_project):
        for priority in [1, 2, 3]:
            req = Requirement(
                project_id=test_project.id,
                req_no=f"REQ-PRI-{priority}",
                title=f"优先级{priority}",
                description="描述",
                priority=priority
            )
            db.add(req)
            db.commit()
            db.refresh(req)
            assert req.priority == priority
            db.delete(req)
            db.commit()

    def test_requirement_with_source_file(self, db, test_project):
        from app.models.project import ProjectFile
        pf = ProjectFile(
            project_id=test_project.id,
            file_name="需求文档.docx",
            file_type="docx",
            file_url="/uploads/req.docx"
        )
        db.add(pf)
        db.commit()
        db.refresh(pf)
        req = Requirement(
            project_id=test_project.id,
            req_no="REQ-SRC-001",
            title="来源需求",
            description="描述",
            priority=1,
            source_file_id=pf.id
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        assert req.source_file_id == pf.id
        db.delete(req)
        db.delete(pf)
        db.commit()

    def test_requirement_repr(self, db, test_project):
        req = Requirement(
            project_id=test_project.id,
            req_no="REQ-REPR-001",
            title="Repr需求",
            description="描述",
            priority=1
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        repr_str = repr(req)
        assert "Requirement" in repr_str
        assert "REQ-REPR-001" in repr_str
        db.delete(req)
        db.commit()

    def test_requirement_relationships(self):
        assert hasattr(Requirement, 'project')
        assert hasattr(Requirement, 'source_file')
        assert hasattr(Requirement, 'test_points')
