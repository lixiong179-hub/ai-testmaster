import pytest
from app.models.requirement_link import RequirementLink
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="rl_test_user",
        email="rl_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(RequirementLink).filter(RequirementLink.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="链接测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestRequirementLinkModel:
    def test_create_requirement_link(self, db, test_project, test_user):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="需求文档v1.0",
            link_type="requirement",
            link_url="https://docs.example.com/req",
            created_by=test_user.id
        )
        db.add(rl)
        db.commit()
        db.refresh(rl)
        assert rl.id is not None
        assert rl.project_id == test_project.id
        assert rl.link_name == "需求文档v1.0"
        assert rl.link_type == "requirement"
        assert rl.link_url == "https://docs.example.com/req"
        assert rl.auth_type == "none"
        assert rl.is_active is True
        assert rl.create_time is not None
        db.delete(rl)
        db.commit()

    def test_requirement_link_default_values(self, db, test_project):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="默认链接",
            link_type="requirement",
            link_url="https://example.com"
        )
        db.add(rl)
        db.commit()
        db.refresh(rl)
        assert rl.auth_type == "none"
        assert rl.auth_config_encrypted is None
        assert rl.is_active is True
        assert rl.description is None
        assert rl.last_fetch_time is None
        assert rl.last_fetch_status is None
        assert rl.cached_content is None
        assert rl.cache_expire_minutes == 60
        assert rl.created_by is None
        db.delete(rl)
        db.commit()

    def test_requirement_link_type_values(self, db, test_project):
        for lt in ["requirement", "ui_mockup", "api_doc", "other"]:
            rl = RequirementLink(
                project_id=test_project.id,
                link_name=f"链接-{lt}",
                link_type=lt,
                link_url="https://example.com"
            )
            db.add(rl)
            db.commit()
            db.refresh(rl)
            assert rl.link_type == lt
            db.delete(rl)
            db.commit()

    def test_requirement_link_auth_type_values(self, db, test_project):
        for at in ["none", "basic", "bearer", "api_key", "cookie"]:
            rl = RequirementLink(
                project_id=test_project.id,
                link_name=f"认证-{at}",
                link_type="requirement",
                link_url="https://example.com",
                auth_type=at
            )
            db.add(rl)
            db.commit()
            db.refresh(rl)
            assert rl.auth_type == at
            db.delete(rl)
            db.commit()

    def test_requirement_link_auth_config_property(self, db, test_project):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="认证配置链接",
            link_type="requirement",
            link_url="https://example.com",
            auth_type="basic"
        )
        rl.auth_config = {"username": "admin", "password": "secret"}
        assert rl.auth_config_encrypted is not None
        assert rl.auth_config_encrypted.get("_encrypted") is not None
        decrypted = rl.auth_config
        assert decrypted["username"] == "admin"
        assert decrypted["password"] == "secret"
        db.add(rl)
        db.commit()
        db.delete(rl)
        db.commit()

    def test_requirement_link_auth_config_set_none(self, db, test_project):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="空认证链接",
            link_type="requirement",
            link_url="https://example.com"
        )
        rl.auth_config = None
        assert rl.auth_config_encrypted is None

    def test_requirement_link_auth_config_set_empty(self, db, test_project):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="空字典认证链接",
            link_type="requirement",
            link_url="https://example.com"
        )
        rl.auth_config = {}
        assert rl.auth_config_encrypted is None

    def test_requirement_link_auth_config_get_empty(self, db, test_project):
        rl = RequirementLink(
            project_id=test_project.id,
            link_name="无认证链接",
            link_type="requirement",
            link_url="https://example.com"
        )
        db.add(rl)
        db.commit()
        db.refresh(rl)
        assert rl.auth_config == {}
        db.delete(rl)
        db.commit()

    def test_requirement_link_fetch_status(self, db, test_project):
        for status in ["success", "failed"]:
            rl = RequirementLink(
                project_id=test_project.id,
                link_name=f"获取状态-{status}",
                link_type="requirement",
                link_url="https://example.com",
                last_fetch_status=status
            )
            db.add(rl)
            db.commit()
            db.refresh(rl)
            assert rl.last_fetch_status == status
            db.delete(rl)
            db.commit()

    def test_requirement_link_relationships(self):
        assert hasattr(RequirementLink, 'project')
        assert hasattr(RequirementLink, 'creator')
