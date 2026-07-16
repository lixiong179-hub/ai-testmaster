"""XMind 导入 API 集成测试。

覆盖范围:
    - POST /api/v1/test-point/import-xmind 导入端点
    - 预览模式（preview=true）：解析不写入
    - 导入模式（preview=false）：解析并写入
    - 文件格式校验（非 .xmind 文件）
    - 空文件/无效 ZIP
    - 权限校验

使用真实 MySQL 数据库和 FastAPI TestClient。
"""
import os
import zipfile
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.endpoints.auth import get_current_user
from app.utils.ai_client_core import (
    AIAuthenticationError,
    AIPermissionError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)

SAMPLE_XMIND = r"C:\Users\Administrator\Desktop\听写任务.xmind"
NS = "urn:xmind:xmap:xmlns:content:2.0"


def _create_xmind_file(path: str, content_xml: str) -> str:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        zf.writestr("meta.xml", '<?xml version="1.0" encoding="UTF-8"?>')
    return path


def _build_content_xml(topics_xml: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-content xmlns="{NS}" version="2.0">
<sheet id="test-sheet">
<topic id="root" structure-class="org.xmind.ui.logic.right">
<title>根主题</title>
<children><topics type="attached">
{topics_xml}
</topics></children>
</topic>
</sheet>
</xmap-content>"""


@pytest.fixture(scope="function")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_headers(client):
    from app.services.captcha_service import captcha_service
    captcha_service._store.clear()
    captcha_service._used.clear()
    captcha_service._ip_limits.clear()

    captcha_resp = client.get("/api/v1/auth/captcha/generate")
    assert captcha_resp.status_code == 200
    captcha_data = captcha_resp.json()

    login_resp = client.post("/api/v1/auth/login", data={
        "username": "admin",
        "password": "admin123",
        "captcha_id": captcha_data["data"]["captcha_id"],
        "captcha_code": captcha_data["data"]["code"],
    })

    if login_resp.status_code == 200:
        token = login_resp.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}
    pytest.skip("无法登录，跳过需要认证的测试")


@pytest.fixture(scope="function")
def test_project(client, auth_headers):
    resp = client.get("/api/v1/project/list", headers=auth_headers)
    if resp.status_code == 200 and resp.json().get("data", {}).get("items"):
        projects = resp.json()["data"]["items"]
        if projects:
            return projects[0]["id"]
    create_resp = client.post(
        "/api/v1/project",
        json={"name": "XMind导入测试项目"},
        headers=auth_headers,
    )
    if create_resp.status_code == 200:
        return create_resp.json()["data"]["id"]
    pytest.skip("无法创建/获取测试项目")


@pytest.fixture
def valid_xmind(tmp_path) -> str:
    topics = """<topic id="l1"><title>登录模块</title>
<children><topics type="attached">
<topic id="l2"><title>用户登录</title>
<children><topics type="attached">
<topic id="l3"><title>输入正确密码登录</title></topic>
<topic id="l3b"><title>输入错误密码提示</title></topic>
</topics></children>
</topic>
</topics></children>
</topic>"""
    content = _build_content_xml(topics)
    return _create_xmind_file(str(tmp_path / "test_import.xmind"), content)


class TestImportXmindPreview:
    """预览模式测试。"""

    def test_preview_returns_parsed_data(
        self, client, auth_headers, test_project, valid_xmind
    ) -> None:
        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["preview_mode"] == "test_points"
        assert "total" in data
        assert "items" in data
        assert "case_total" in data
        assert "case_items" in data
        assert "skipped_count" in data
        assert "skipped_reasons" in data
        assert data["total"] >= 1

    def test_preview_does_not_write_to_db(
        self, client, auth_headers, test_project, valid_xmind
    ) -> None:
        list_resp = client.get(
            f"/api/v1/test-point/list/{test_project}",
            headers=auth_headers,
        )
        count_before = len(list_resp.json().get("data", {}).get("items", []))

        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )
        assert resp.status_code == 200

        list_resp2 = client.get(
            f"/api/v1/test-point/list/{test_project}",
            headers=auth_headers,
        )
        count_after = len(list_resp2.json().get("data", {}).get("items", []))
        assert count_after == count_before

    def test_preview_second_level_leaf_becomes_test_point(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        topics = """<topic id="l1"><title>登录模块</title>
<children><topics type="attached">
<topic id="l2"><title>用户登录</title></topic>
</topics></children>
</topic>"""
        xmind_file = _create_xmind_file(
            str(tmp_path / "second_level_only.xmind"),
            _build_content_xml(topics),
        )

        with open(xmind_file, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["preview_mode"] == "test_points"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["case_total"] == 0
        assert data["case_items"] == []
        assert data["items"][0]["point"] == "用户登录"
        assert data["skipped_count"] == 0
        assert data["skipped_reasons"] == []


class TestImportXmindFull:
    """导入模式测试。"""

    def test_import_saves_to_db(
        self, client, auth_headers, test_project, valid_xmind
    ) -> None:
        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "false"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_count"] >= 1
        assert data["total_parsed"] >= 1

    @pytest.mark.skipif(
        not os.path.exists(SAMPLE_XMIND),
        reason="样例文件不存在",
    )
    def test_import_sample_file(
        self, client, auth_headers, test_project
    ) -> None:
        with open(SAMPLE_XMIND, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("听写任务.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "false"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_count"] > 0

    def test_import_second_level_leaf_becomes_test_point(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        topics = """<topic id="l1"><title>登录模块</title>
<children><topics type="attached">
<topic id="l2"><title>用户登录</title></topic>
</topics></children>
</topic>"""
        xmind_file = _create_xmind_file(
            str(tmp_path / "second_level_only_import.xmind"),
            _build_content_xml(topics),
        )

        with open(xmind_file, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "false"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_count"] == 1
        assert data["total_parsed"] == 1
        assert data["skipped_count"] == 0
        assert data["skipped_reasons"] == []

    def test_import_case_style_xmind_creates_cases_and_points(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        topics = """<topic id="module"><title>字词听写</title>
<children><topics type="attached">
<topic id="content"><title>有教材内容</title>
<children><topics type="attached">
<topic id="action"><title>点击听写记录</title>
<children><topics type="attached">
<topic id="condition"><title>有记录</title>
<children><topics type="attached">
<topic id="leaf"><title>界面显示最近的听写记录</title></topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>"""
        xmind_file = _create_xmind_file(
            str(tmp_path / "case_style_import.xmind"),
            _build_content_xml(topics),
        )

        with open(xmind_file, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("case-style.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "false"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_count"] == 1
        assert data["saved_case_count"] == 1
        assert data["total_parsed"] == 1

    def test_preview_case_style_xmind_returns_dual_views(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        topics = """<topic id="module"><title>字词听写</title>
<children><topics type="attached">
<topic id="content"><title>有教材内容</title>
<children><topics type="attached">
<topic id="action"><title>点击听写记录</title>
<children><topics type="attached">
<topic id="condition"><title>有记录</title>
<children><topics type="attached">
<topic id="leaf"><title>界面显示最近的听写记录</title></topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>"""
        xmind_file = _create_xmind_file(
            str(tmp_path / "case_style_preview.xmind"),
            _build_content_xml(topics),
        )

        with open(xmind_file, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("case-style-preview.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["preview_mode"] == "test_cases"
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["case_total"] == 1
        assert len(data["case_items"]) == 1
        assert data["case_items"][0]["title"] == "点击听写记录，界面显示最近的听写记录"
        assert data["case_items"][0]["step_count"] == 1
        assert data["case_items"][0]["steps"][0]["action"] == "点击听写记录"

    def test_import_deep_point_tree_does_not_switch_to_case_mode(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        topics = """<topic id="module"><title>登录模块</title>
<children><topics type="attached">
<topic id="function"><title>账号密码登录</title>
<children><topics type="attached">
<topic id="scene"><title>错误密码场景</title>
<children><topics type="attached">
<topic id="action"><title>点击登录按钮</title>
<children><topics type="attached">
<topic id="leaf"><title>提示密码错误</title></topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>"""
        xmind_file = _create_xmind_file(
            str(tmp_path / "deep_point_tree.xmind"),
            _build_content_xml(topics),
        )

        with open(xmind_file, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("deep-point.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "false"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["saved_count"] == 1
        assert data["saved_case_count"] == 1


# ---------------------------------------------------------------------------
# Mock-based AI enhance tests – 不依赖真实登录和数据库
# ---------------------------------------------------------------------------

def _fake_current_user():
    """构造一个假用户对象，用于依赖注入覆盖。"""
    user = MagicMock()
    user.id = 1
    user.username = "test_user"
    return user


@pytest.fixture()
def ai_client(valid_xmind):
    """返回绕过认证和权限校验的 TestClient。"""
    app.dependency_overrides[get_current_user] = _fake_current_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.pop(get_current_user, None)


class TestImportXmindAiEnhance:
    """AI增强模式异常映射测试。

    通过 mock XmindAIParser.parse_paths 和 check_project_permission，
    验证各 AI 异常分支返回正确的 HTTP 状态码和提示文案。
    """

    _PATCH_PARSE = "app.api.v1.endpoints.test_point_import.XmindAIParser"
    _PATCH_PERM = "app.api.v1.endpoints.test_point_import.check_project_permission"

    def _post_ai(self, ai_client, valid_xmind, preview="true"):
        with open(valid_xmind, "rb") as f:
            return ai_client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": "1", "preview": preview, "ai_enhance": "true"},
            )

    def test_ai_timeout_returns_408(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = AITimeoutError()
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 408
        assert "超时" in resp.json()["msg"]

    def test_ai_auth_error_returns_503(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = AIAuthenticationError()
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 503
        assert "认证" in resp.json()["msg"]

    def test_ai_rate_limit_returns_429(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = AIRateLimitError()
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 429
        assert "频繁" in resp.json()["msg"]

    def test_ai_permission_error_returns_503(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = AIPermissionError()
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 503
        assert "权限" in resp.json()["msg"]

    def test_ai_service_error_returns_502(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = AIServiceError(
                "模型暂时不可用", error_code="MODEL_UNAVAILABLE"
            )
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 502
        assert "模型暂时不可用" in resp.json()["msg"]

    def test_ai_unknown_error_returns_500(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.side_effect = RuntimeError("unexpected")
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 500
        # 不应泄露内部异常信息
        assert "unexpected" not in resp.json()["msg"]
        assert "未知错误" in resp.json()["msg"]

    def test_ai_empty_result_returns_422(self, ai_client, valid_xmind):
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser:
            MockParser.return_value.parse_paths.return_value = []
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 422
        assert "空结果" in resp.json()["msg"]

    _PATCH_HANDLE = "app.api.v1.endpoints.test_point_import.handle_ai_enhanced_import"

    def test_ai_success_returns_preview(self, ai_client, valid_xmind):
        from app.schemas.test_point import (
            TestPointXmindPreviewResponse,
            TestPointXmindPreviewItem,
            TestPointXmindPreviewCaseItem,
            TestPointXmindPreviewCaseStep,
        )
        fake_response = TestPointXmindPreviewResponse(
            preview_mode="test_cases",
            total=1,
            items=[TestPointXmindPreviewItem(
                module="登录模块", point="输入正确密码", priority=2,
            )],
            case_total=1,
            case_items=[TestPointXmindPreviewCaseItem(
                module="登录模块", title="测试登录",
                precondition="", expected_result="登录成功", priority=2,
                step_count=1,
                steps=[TestPointXmindPreviewCaseStep(
                    step_number=1, action="输入密码", expected_result="成功",
                )],
            )],
            skipped_count=0,
            skipped_reasons=[],
            ai_timeout=False,
        )
        with patch(self._PATCH_PERM), \
             patch(self._PATCH_PARSE) as MockParser, \
             patch(self._PATCH_HANDLE, return_value=fake_response):
            MockParser.return_value.parse_paths.return_value = [{"fake": True}]
            resp = self._post_ai(ai_client, valid_xmind)
        assert resp.status_code == 200
        body = resp.json()
        # 端点直接返回 pydantic model，无 code/data 包装
        payload = body.get("data", body)
        assert payload["preview_mode"] == "test_cases"
        assert payload["case_total"] == 1


class TestImportXmindValidation:
    """文件校验测试。"""

    def test_invalid_file_format(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a xmind file")
        with open(str(txt_file), "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.txt", f, "text/plain")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )
        assert resp.status_code == 400 or (
            resp.status_code == 200 and resp.json().get("code") == 400
        )

    def test_invalid_zip_file(
        self, client, auth_headers, test_project, tmp_path
    ) -> None:
        fake_file = tmp_path / "fake.xmind"
        fake_file.write_text("this is not a zip file")
        with open(str(fake_file), "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("fake.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true"},
                headers=auth_headers,
            )
        assert resp.status_code == 400 or (
            resp.status_code == 200 and resp.json().get("code") == 400
        )

    def test_no_auth_returns_401(self, client, valid_xmind) -> None:
        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": "1", "preview": "true"},
            )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 真实 AI 端到端集成测试 – 需要登录 + DeepSeek API Key
# ---------------------------------------------------------------------------


def _ai_key_configured() -> bool:
    from app.core.config import settings
    return bool(settings.DEEPSEEK_API_KEY and not settings.DEEPSEEK_API_KEY.startswith("your"))


@pytest.fixture
def ai_xmind(tmp_path) -> str:
    """构造一份多层结构的 XMind，覆盖前置条件/操作/预期结果等语义。"""
    topics = """<topic id="m1"><title>字词听写</title>
<children><topics type="attached">
<topic id="f1"><title>有教材内容</title>
<children><topics type="attached">
<topic id="a1"><title>点击听写记录</title>
<children><topics type="attached">
<topic id="c1"><title>有记录</title>
<children><topics type="attached">
<topic id="r1"><title>界面显示最近的听写记录</title></topic>
</topics></children>
</topic>
<topic id="c2"><title>无记录</title>
<children><topics type="attached">
<topic id="r2"><title>提示暂无听写记录</title></topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>
</topics></children>
</topic>"""
    return _create_xmind_file(
        str(tmp_path / "ai_real_test.xmind"),
        _build_content_xml(topics),
    )


@pytest.fixture()
def real_ai_client():
    """绕过认证但真实调用 AI 的 TestClient。"""
    app.dependency_overrides[get_current_user] = _fake_current_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.real_api
class TestImportXmindAiReal:
    """真实 AI 端到端测试。

    调用实际 DeepSeek API，验证：
    - AI 能正确返回结构化用例
    - 返回字段与 schema 兼容
    - 预览模式均正常工作

    使用 dependency override 绕过登录，通过 mock check_project_permission 绕过项目权限。
    环境要求：DEEPSEEK_API_KEY 已配置，不满足时自动 skip。
    """

    _PATCH_PERM = "app.api.v1.endpoints.test_point_import.check_project_permission"

    @pytest.mark.skipif(not _ai_key_configured(), reason="DeepSeek API Key 未配置")
    def test_ai_preview_returns_structured_cases(
        self, real_ai_client, ai_xmind
    ) -> None:
        """AI 增强预览模式应返回包含用例的结构化响应。"""
        with patch(self._PATCH_PERM):
            with open(ai_xmind, "rb") as f:
                resp = real_ai_client.post(
                    "/api/v1/test-point/import-xmind",
                    files={"file": ("ai_test.xmind", f, "application/octet-stream")},
                    data={
                        "project_id": "1",
                        "preview": "true",
                        "ai_enhance": "true",
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)

        # 基础结构校验
        assert data["preview_mode"] == "test_cases"
        assert data["case_total"] >= 1
        assert len(data["case_items"]) >= 1

        # 校验每个 case_item 包含必需字段
        for case_item in data["case_items"]:
            assert "module" in case_item
            assert "title" in case_item
            assert "priority" in case_item
            assert case_item["priority"] in (1, 2, 3)
            assert "step_count" in case_item
            assert isinstance(case_item["steps"], list)
            for step in case_item["steps"]:
                assert "action" in step
                assert "expected_result" in step

        # test_point 侧也应有对应数据
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        for item in data["items"]:
            assert "module" in item
            assert "point" in item

    @pytest.mark.skipif(
        not os.path.exists(SAMPLE_XMIND) or not _ai_key_configured(),
        reason="样例文件不存在或 DeepSeek API Key 未配置",
    )
    def test_ai_preview_real_sample_file(
        self, real_ai_client
    ) -> None:
        """使用真实 XMind 样例文件测试 AI 增强预览。"""
        with patch(self._PATCH_PERM):
            with open(SAMPLE_XMIND, "rb") as f:
                resp = real_ai_client.post(
                    "/api/v1/test-point/import-xmind",
                    files={"file": ("听写任务.xmind", f, "application/octet-stream")},
                    data={
                        "project_id": "1",
                        "preview": "true",
                        "ai_enhance": "true",
                    },
                )

        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body)
        assert data["case_total"] >= 1
        assert len(data["case_items"]) >= 1
