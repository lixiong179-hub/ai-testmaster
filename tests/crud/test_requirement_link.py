import pytest

from app.crud.requirement_link import (
    create_requirement_link,
    get_requirement_link_by_id,
    get_requirement_links_by_project,
    get_requirement_links_count,
    get_requirement_links_by_types,
    update_requirement_link,
    delete_requirement_link,
    update_link_cache,
    get_active_links_by_project,
    toggle_link_active,
    check_link_exists,
)
from app.models.project import Project
from app.models.requirement_link import RequirementLink
from app.models.user import User


@pytest.fixture
def rl_user(db):
    user = User(username="rl_test_user", email="rl_test@test.com", password_hash="hash", is_active=True)
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    try:
        db.query(RequirementLink).filter(
            RequirementLink.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture
def rl_project(db, rl_user):
    project = Project(name="rl_test_project", user_id=rl_user.id, description="rl test", status=1, project_type="web")
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_link(db, project_id, **kwargs):
    defaults = {
        "link_name": "测试链接",
        "link_type": "requirement",
        "link_url": f"https://example.com/req/{id(db)}",
    }
    defaults.update(kwargs)
    return create_requirement_link(db, project_id=project_id, **defaults)


class TestCreateRequirementLink:

    def test_create_basic(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        assert link.id is not None
        assert link.project_id == rl_project.id
        assert link.auth_type == "none"
        assert link.is_active is True

    def test_create_with_auth(self, db, rl_project):
        link = _make_link(
            db, rl_project.id,
            auth_type="basic",
            auth_config={"username": "admin", "password": "123"},
            link_name="带认证链接",
        )
        assert link.auth_type == "basic"

    def test_create_with_all_fields(self, db, rl_project, rl_user):
        link = _make_link(
            db, rl_project.id,
            created_by=rl_user.id,
            description="描述",
            cache_expire_minutes=120,
        )
        assert link.description == "描述"
        assert link.cache_expire_minutes == 120


class TestGetRequirementLinkById:

    def test_found(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = get_requirement_link_by_id(db, link.id)
        assert result is not None
        assert result.id == link.id

    def test_with_project_filter(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = get_requirement_link_by_id(db, link.id, rl_project.id)
        assert result is not None
        result2 = get_requirement_link_by_id(db, link.id, 99999)
        assert result2 is None

    def test_not_found(self, db):
        result = get_requirement_link_by_id(db, 99999)
        assert result is None


class TestGetRequirementLinksByProject:

    def test_basic_query(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_name="L1", link_url="https://a.com/1")
        _make_link(db, rl_project.id, link_name="L2", link_url="https://a.com/2")
        links = get_requirement_links_by_project(db, rl_project.id, rl_user.id)
        assert len(links) == 2

    def test_filter_by_type(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_type="requirement", link_url="https://a.com/r")
        _make_link(db, rl_project.id, link_type="ui_mockup", link_url="https://a.com/u")
        links = get_requirement_links_by_project(db, rl_project.id, rl_user.id, link_type="requirement")
        assert len(links) == 1

    def test_filter_by_active(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_name="active", link_url="https://a.com/act")
        link2 = _make_link(db, rl_project.id, link_name="inactive", link_url="https://a.com/inact")
        link2.is_active = False
        db.commit()
        links = get_requirement_links_by_project(db, rl_project.id, rl_user.id, is_active=True)
        assert len(links) == 1

    def test_pagination(self, db, rl_project, rl_user):
        for i in range(5):
            _make_link(db, rl_project.id, link_name=f"P{i}", link_url=f"https://a.com/p{i}")
        links = get_requirement_links_by_project(db, rl_project.id, rl_user.id, skip=0, limit=2)
        assert len(links) == 2


class TestGetRequirementLinksCount:

    def test_count(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_url="https://a.com/c1")
        _make_link(db, rl_project.id, link_type="ui_mockup", link_url="https://a.com/c2")
        count = get_requirement_links_count(db, rl_project.id, rl_user.id)
        assert count == 2

    def test_count_with_filter(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_type="requirement", link_url="https://a.com/cf1")
        _make_link(db, rl_project.id, link_type="ui_mockup", link_url="https://a.com/cf2")
        count = get_requirement_links_count(db, rl_project.id, rl_user.id, link_type="requirement")
        assert count == 1


class TestGetRequirementLinksByTypes:

    def test_filter_by_types(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_type="requirement", link_url="https://a.com/t1")
        _make_link(db, rl_project.id, link_type="api_doc", link_url="https://a.com/t2")
        _make_link(db, rl_project.id, link_type="ui_mockup", link_url="https://a.com/t3")
        links = get_requirement_links_by_types(db, rl_project.id, rl_user.id, ["requirement", "api_doc"])
        assert len(links) == 2

    def test_excludes_inactive(self, db, rl_project, rl_user):
        link1 = _make_link(db, rl_project.id, link_type="requirement", link_url="https://a.com/ti")
        link1.is_active = False
        db.commit()
        links = get_requirement_links_by_types(db, rl_project.id, rl_user.id, ["requirement"])
        assert len(links) == 0


class TestUpdateRequirementLink:

    def test_update_fields(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = update_requirement_link(db, link.id, link_name="新名称", description="新描述")
        assert result is not None
        assert result.link_name == "新名称"
        assert result.description == "新描述"

    def test_protected_fields_ignored(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        original_id = link.id
        result = update_requirement_link(db, link.id, id=99999, link_name="新名称")
        assert result.id == original_id

    def test_nonexistent(self, db):
        result = update_requirement_link(db, 99999, link_name="x")
        assert result is None


class TestDeleteRequirementLink:

    def test_delete_success(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = delete_requirement_link(db, link.id)
        assert result is True
        assert get_requirement_link_by_id(db, link.id) is None

    def test_delete_nonexistent(self, db):
        result = delete_requirement_link(db, 99999)
        assert result is False


class TestUpdateLinkCache:

    def test_update_success(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = update_link_cache(db, link.id, "cached content", "success")
        assert result is not None
        assert result.cached_content == "cached content"
        assert result.last_fetch_status == "success"

    def test_update_failed_status(self, db, rl_project):
        link = _make_link(db, rl_project.id)
        result = update_link_cache(db, link.id, "", "failed")
        assert result.last_fetch_status == "failed"

    def test_nonexistent(self, db):
        result = update_link_cache(db, 99999, "content", "success")
        assert result is None


class TestGetActiveLinksByProject:

    def test_returns_active_only(self, db, rl_project, rl_user):
        _make_link(db, rl_project.id, link_name="active", link_url="https://a.com/al")
        link2 = _make_link(db, rl_project.id, link_name="inactive", link_url="https://a.com/il")
        link2.is_active = False
        db.commit()
        links = get_active_links_by_project(db, rl_project.id, rl_user.id)
        assert len(links) == 1


class TestToggleLinkActive:

    def test_toggle_off(self, db, rl_project, rl_user):
        link = _make_link(db, rl_project.id)
        assert link.is_active is True
        result = toggle_link_active(db, link.id, rl_project.id, rl_user.id)
        assert result.is_active is False

    def test_toggle_on(self, db, rl_project, rl_user):
        link = _make_link(db, rl_project.id)
        link.is_active = False
        db.commit()
        result = toggle_link_active(db, link.id, rl_project.id, rl_user.id)
        assert result.is_active is True

    def test_not_found(self, db, rl_project, rl_user):
        result = toggle_link_active(db, 99999, rl_project.id, rl_user.id)
        assert result is None


class TestCheckLinkExists:

    def test_exists(self, db, rl_project):
        _make_link(db, rl_project.id, link_url="https://example.com/unique_a")
        assert check_link_exists(db, rl_project.id, "https://example.com/unique_a") is True

    def test_not_exists(self, db, rl_project):
        assert check_link_exists(db, rl_project.id, "https://no.com") is False
