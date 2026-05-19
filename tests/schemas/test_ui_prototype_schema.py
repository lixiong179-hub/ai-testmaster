import pytest
from app.schemas.ui_prototype._enums import (
    UISourceEnum,
    ParseStatusEnum,
    ReviewStatusEnum,
    UILinkAuthType,
    UI_LINK_SOURCE_OPTIONS,
)
from app.schemas.ui_prototype._project import (
    UIPrototypeProjectBase,
    UIPrototypeProjectCreate,
    UIPrototypeProjectResponse,
)
from app.schemas.ui_prototype._screen import (
    UIScreenBase,
    UIScreenCreate,
    UIScreenParseRequest,
    UIScreenParseResponse,
    UIFlowGenerateRequest,
    UIFlowGenerateResponse,
    UISpecForCaseGeneration,
    UIScreenReviewRequest,
    UIPrototypeUploadRequest,
)
from app.schemas.ui_prototype._link import (
    UILinkBase,
    UILinkCreate,
    UILinkUpdate,
    UIFetchRequest,
)


class TestUISourceEnum:
    def test_values(self):
        assert UISourceEnum.UPLOAD.value == "upload"
        assert UISourceEnum.FETCH.value == "fetch"
        assert UISourceEnum.EXTRACT.value == "extract"

    def test_from_string(self):
        assert UISourceEnum("upload") == UISourceEnum.UPLOAD


class TestParseStatusEnum:
    def test_values(self):
        assert ParseStatusEnum.PENDING.value == "pending"
        assert ParseStatusEnum.PARSING.value == "parsing"
        assert ParseStatusEnum.COMPLETED.value == "completed"
        assert ParseStatusEnum.FAILED.value == "failed"


class TestReviewStatusEnum:
    def test_values(self):
        assert ReviewStatusEnum.PENDING.value == "pending"
        assert ReviewStatusEnum.APPROVED.value == "approved"
        assert ReviewStatusEnum.REJECTED.value == "rejected"


class TestUILinkAuthType:
    def test_values(self):
        assert UILinkAuthType.NONE.value == "none"
        assert UILinkAuthType.BASIC.value == "basic"
        assert UILinkAuthType.BEARER.value == "bearer"
        assert UILinkAuthType.COOKIE.value == "cookie"


class TestUILinkSourceOptions:
    def test_options_count(self):
        assert len(UI_LINK_SOURCE_OPTIONS) == 3

    def test_options_structure(self):
        for opt in UI_LINK_SOURCE_OPTIONS:
            assert "label" in opt
            assert "value" in opt


class TestUIPrototypeProjectBase:
    def test_normal(self):
        proj = UIPrototypeProjectBase(name="测试项目")
        assert proj.name == "测试项目"
        assert proj.description is None

    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            UIPrototypeProjectBase(name="")


class TestUIPrototypeProjectCreate:
    def test_defaults(self):
        proj = UIPrototypeProjectCreate(name="项目")
        assert proj.source == UISourceEnum.UPLOAD

    def test_with_source(self):
        proj = UIPrototypeProjectCreate(name="项目", source=UISourceEnum.FETCH)
        assert proj.source == UISourceEnum.FETCH


class TestUIPrototypeProjectResponse:
    def test_from_attributes(self):
        proj = UIPrototypeProjectResponse(
            id=1, name="项目", source="upload", screen_count=5,
        )
        assert proj.id == 1
        assert proj.screen_count == 5


class TestUIScreenBase:
    def test_normal(self):
        screen = UIScreenBase(title="登录页")
        assert screen.title == "登录页"
        assert screen.url is None

    def test_empty_title_rejected(self):
        with pytest.raises(Exception):
            UIScreenBase(title="")


class TestUIScreenCreate:
    def test_normal(self):
        screen = UIScreenCreate(project_id=1, title="首页")
        assert screen.project_id == 1
        assert screen.source == UISourceEnum.UPLOAD

    def test_with_image_data(self):
        screen = UIScreenCreate(
            project_id=1, title="T", image_data="base64data",
        )
        assert screen.image_data == "base64data"


class TestUIScreenParseRequest:
    def test_defaults(self):
        req = UIScreenParseRequest()
        assert req.force_reparse is False
        assert req.extract_elements is True
        assert req.generate_spec is True


class TestUIScreenParseResponse:
    def test_normal(self):
        resp = UIScreenParseResponse(screen_id=1, parse_status="completed")
        assert resp.screen_id == 1
        assert resp.elements_count == 0
        assert resp.spec_generated is False


class TestUIFlowGenerateRequest:
    def test_normal(self):
        req = UIFlowGenerateRequest(project_id=1)
        assert req.project_id == 1
        assert req.screen_ids is None

    def test_with_screen_ids(self):
        req = UIFlowGenerateRequest(project_id=1, screen_ids=[1, 2])
        assert len(req.screen_ids) == 2


class TestUIFlowGenerateResponse:
    def test_normal(self):
        resp = UIFlowGenerateResponse(project_id=1)
        assert resp.flow_data is None
        assert resp.screen_count == 0


class TestUISpecForCaseGeneration:
    def test_normal(self):
        spec = UISpecForCaseGeneration(screen_id=1, title="首页")
        assert spec.screen_id == 1
        assert spec.elements_json is None


class TestUIScreenReviewRequest:
    def test_normal(self):
        req = UIScreenReviewRequest(review_status=ReviewStatusEnum.APPROVED)
        assert req.review_status == ReviewStatusEnum.APPROVED
        assert req.review_comment is None


class TestUIPrototypeUploadRequest:
    def test_normal(self):
        req = UIPrototypeUploadRequest(project_id=1, files=["file1.png"])
        assert len(req.files) == 1

    def test_empty_files_rejected(self):
        with pytest.raises(Exception):
            UIPrototypeUploadRequest(project_id=1, files=[])


class TestUILinkBase:
    def test_normal(self):
        link = UILinkBase(source_screen_id=1, target_screen_id=2)
        assert link.source_screen_id == 1
        assert link.target_screen_id == 2


class TestUILinkCreate:
    def test_normal(self):
        link = UILinkCreate(project_id=1, source_screen_id=1, target_screen_id=2)
        assert link.source_screen_id == 1
        assert link.auth_type == UILinkAuthType.NONE


class TestUILinkUpdate:
    def test_normal(self):
        link = UILinkUpdate(label="新标签")
        assert link.label == "新标签"


class TestUIFetchRequest:
    def test_normal(self):
        req = UIFetchRequest(project_id=1, url="https://example.com")
        assert req.url == "https://example.com"
