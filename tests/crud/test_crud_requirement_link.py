"""需求链接CRUD操作单元测试"""
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


@pytest.fixture
def test_project(db, testUser):
    project = Project(
        name="link_test_project",
        user_id=testUser.id,
        description="project for link crud tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project
    try:
        db.query(RequirementLink).filter(
            RequirementLink.project_id == project.id
        ).delete()
        db.query(Project).filter(Project.id == project.id).delete()
        db.flush()
    except Exception:
        db.rollback()


def _create_link(db, project_id, **kwargs):
    defaults = {
        "link_name": "测试链接",
        "link_type": "requirement",
        "link_url": "https://example.com/req",
    }
    defaults.update(kwargs)
    return create_requirement_link(db, project_id=project_id, **defaults)


class TestCreateRequirementLink:
    def test_create_basic(self, db, test_project):
        link = _create_link(db, test_project.id)
        assert link.id is not None
        assert link.project_id == test_project.id
        assert link.link_type == "requirement"
        assert link.auth_type == "none"
        assert link.is_active is True

    def test_create_with_auth(self, db, test_project):
        link = _create_link(
            db,
            test_project.id,
            auth_type="basic",
            auth_config={"username": "admin", "password": "123"},
            link_name="带认证链接",
        )
        assert link.auth_type == "basic"

    def test_create_with_all_fields(self, db, test_project, testUser):
        link = _create_link(
            db,
            test_project.id,
            created_by=testUser.id,
            description="描述",
            cache_expire_minutes=120,
        )
        assert link.description == "描述"
        assert link.cache_expire_minutes == 120


class TestGetRequirementLinkById:
    def test_found(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = get_requirement_link_by_id(db, link.id)
        assert result is not None
        assert result.id == link.id

    def test_with_project_filter(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = get_requirement_link_by_id(db, link.id, test_project.id)
        assert result is not None
        result2 = get_requirement_link_by_id(db, link.id, 99999)
        assert result2 is None

    def test_not_found(self, db, test_project):
        result = get_requirement_link_by_id(db, 99999)
        assert result is None


class TestGetRequirementLinksByProject:
    def test_basic_query(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_name="L1")
        _create_link(db, test_project.id, link_name="L2")
        links = get_requirement_links_by_project(
            db, test_project.id, testUser.id
        )
        assert len(links) == 2

    def test_filter_by_type(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_type="requirement")
        _create_link(db, test_project.id, link_type="ui_mockup")
        links = get_requirement_links_by_project(
            db, test_project.id, testUser.id, link_type="requirement"
        )
        assert len(links) == 1

    def test_filter_by_active(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_name="active")
        link2 = _create_link(db, test_project.id, link_name="inactive")
        link2.is_active = False
        db.commit()
        links = get_requirement_links_by_project(
            db, test_project.id, testUser.id, is_active=True
        )
        assert len(links) == 1


class TestGetRequirementLinksCount:
    def test_count(self, db, test_project, testUser):
        _create_link(db, test_project.id)
        _create_link(db, test_project.id, link_type="ui_mockup")
        count = get_requirement_links_count(db, test_project.id, testUser.id)
        assert count == 2

    def test_count_with_filter(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_type="requirement")
        _create_link(db, test_project.id, link_type="ui_mockup")
        count = get_requirement_links_count(
            db, test_project.id, testUser.id, link_type="requirement"
        )
        assert count == 1


class TestGetRequirementLinksByTypes:
    def test_filter_by_types(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_type="requirement")
        _create_link(db, test_project.id, link_type="api_doc")
        _create_link(db, test_project.id, link_type="ui_mockup")
        links = get_requirement_links_by_types(
            db, test_project.id, testUser.id, ["requirement", "api_doc"]
        )
        assert len(links) == 2

    def test_excludes_inactive(self, db, test_project, testUser):
        link1 = _create_link(db, test_project.id, link_type="requirement")
        link1.is_active = False
        db.commit()
        links = get_requirement_links_by_types(
            db, test_project.id, testUser.id, ["requirement"]
        )
        assert len(links) == 0


class TestUpdateRequirementLink:
    def test_update_fields(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = update_requirement_link(
            db, link.id, link_name="新名称", description="新描述"
        )
        assert result is not None
        assert result.link_name == "新名称"
        assert result.description == "新描述"
        assert result.update_time is not None

    def test_protected_fields_ignored(self, db, test_project):
        link = _create_link(db, test_project.id)
        original_created_by = link.created_by
        # created_by is a protected field and should be ignored
        result = update_requirement_link(
            db, link.id, created_by=99999, link_name="新名称"
        )
        assert result.created_by == original_created_by
        assert result.link_name == "新名称"

    def test_with_project_filter(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = update_requirement_link(
            db, link.id, test_project.id, link_name="filtered"
        )
        assert result is not None
        result2 = update_requirement_link(db, link.id, 99999, link_name="nope")
        assert result2 is None

    def test_nonexistent(self, db, test_project):
        result = update_requirement_link(db, 99999, link_name="x")
        assert result is None


class TestDeleteRequirementLink:
    def test_delete_success(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = delete_requirement_link(db, link.id)
        assert result is True
        assert get_requirement_link_by_id(db, link.id) is None

    def test_delete_with_project_filter(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = delete_requirement_link(db, link.id, test_project.id)
        assert result is True
        result2 = delete_requirement_link(db, 99999, test_project.id)
        assert result2 is False

    def test_delete_nonexistent(self, db, test_project):
        result = delete_requirement_link(db, 99999)
        assert result is False


class TestUpdateLinkCache:
    def test_update_success(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = update_link_cache(db, link.id, "cached content", "success")
        assert result is not None
        assert result.cached_content == "cached content"
        assert result.last_fetch_status == "success"
        assert result.last_fetch_time is not None

    def test_update_failed_status(self, db, test_project):
        link = _create_link(db, test_project.id)
        result = update_link_cache(db, link.id, "", "failed")
        assert result.last_fetch_status == "failed"

    def test_nonexistent(self, db, test_project):
        result = update_link_cache(db, 99999, "content", "success")
        assert result is None


class TestGetActiveLinksByProject:
    def test_returns_active_only(self, db, test_project, testUser):
        _create_link(db, test_project.id, link_name="active")
        link2 = _create_link(db, test_project.id, link_name="inactive")
        link2.is_active = False
        db.commit()
        links = get_active_links_by_project(db, test_project.id, testUser.id)
        assert len(links) == 1


class TestToggleLinkActive:
    def test_toggle_off(self, db, test_project, testUser):
        link = _create_link(db, test_project.id)
        assert link.is_active is True
        result = toggle_link_active(
            db, link.id, test_project.id, testUser.id
        )
        assert result.is_active is False

    def test_toggle_on(self, db, test_project, testUser):
        link = _create_link(db, test_project.id)
        link.is_active = False
        db.commit()
        result = toggle_link_active(
            db, link.id, test_project.id, testUser.id
        )
        assert result.is_active is True

    def test_not_found(self, db, test_project, testUser):
        result = toggle_link_active(db, 99999, test_project.id, testUser.id)
        assert result is None


class TestCheckLinkExists:
    def test_exists(self, db, test_project):
        _create_link(db, test_project.id, link_url="https://example.com/a")
        assert check_link_exists(db, test_project.id, "https://example.com/a") is True

    def test_not_exists(self, db, test_project):
        assert check_link_exists(db, test_project.id, "https://no.com") is False

    def test_different_project(self, db, test_project):
        _create_link(db, test_project.id, link_url="https://example.com/b")
        assert check_link_exists(db, 99999, "https://example.com/b") is False
