import pytest
from app.schemas.test_capability import (
    TestCapabilityBase,
    TestCapabilityCreate,
    TestCapabilityUpdate,
    TestCapabilityResponse,
)


class TestTestCapabilityBase:
    def test_create(self):
        base = TestCapabilityBase(key="LOGIN", title="登录功能")
        assert base.key == "LOGIN"
        assert base.status == "active"
        assert base.description is None

    def test_custom_status(self):
        base = TestCapabilityBase(key="REG", title="注册", status="deprecated")
        assert base.status == "deprecated"

    def test_empty_key_raises(self):
        with pytest.raises(Exception):
            TestCapabilityBase(key="", title="测试")

    def test_empty_title_raises(self):
        with pytest.raises(Exception):
            TestCapabilityBase(key="KEY", title="")


class TestTestCapabilityCreate:
    def test_create(self):
        create = TestCapabilityCreate(project_id=1, key="CAP", title="能力")
        assert create.project_id == 1


class TestTestCapabilityUpdate:
    def test_all_optional(self):
        update = TestCapabilityUpdate()
        assert update.key is None
        assert update.title is None

    def test_partial(self):
        update = TestCapabilityUpdate(title="新标题")
        assert update.title == "新标题"
        assert update.key is None


class TestTestCapabilityResponse:
    def test_create(self):
        from datetime import datetime
        resp = TestCapabilityResponse(
            id=1, project_id=1, key="CAP", title="能力",
            created_at=datetime.now(),
        )
        assert resp.id == 1
        assert resp.updated_at is None
