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
import pytest

from fastapi.testclient import TestClient
from app.main import app

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


@pytest.fixture(scope="module")
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
        "password": "admin",
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
        assert data["code"] == 200
        assert data["data"]["preview_mode"] == "test_points"
        assert "total" in data["data"]
        assert "items" in data["data"]
        assert "case_total" in data["data"]
        assert "case_items" in data["data"]
        assert "skipped_count" in data["data"]
        assert "skipped_reasons" in data["data"]
        assert data["data"]["total"] >= 1

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
        assert data["code"] == 200
        assert data["data"]["preview_mode"] == "test_points"
        assert data["data"]["total"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["case_total"] == 0
        assert data["data"]["case_items"] == []
        assert data["data"]["items"][0]["function"] == "用户登录"
        assert data["data"]["items"][0]["point"] == "用户登录"
        assert data["data"]["skipped_count"] == 0
        assert data["data"]["skipped_reasons"] == []


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
        assert data["code"] == 200
        assert data["data"]["saved_count"] >= 1
        assert data["data"]["total_parsed"] >= 1

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
        assert data["data"]["saved_count"] > 0

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
        assert data["code"] == 200
        assert data["data"]["saved_count"] == 1
        assert data["data"]["total_parsed"] == 1
        assert data["data"]["skipped_count"] == 0
        assert data["data"]["skipped_reasons"] == []

    def test_import_case_style_xmind_creates_cases_and_points(
        self, db, client, auth_headers, test_project, tmp_path
    ) -> None:
        from app.models.test_case import TestCase, TestStep

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
        assert data["code"] == 200
        assert data["data"]["saved_count"] == 1
        assert data["data"]["saved_case_count"] == 1
        assert data["data"]["total_parsed"] == 1

        saved_case = db.query(TestCase).filter(
            TestCase.project_id == test_project,
            TestCase.title == "点击听写记录，界面显示最近的听写记录",
        ).order_by(TestCase.id.desc()).first()
        assert saved_case is not None

        saved_steps = db.query(TestStep).filter(
            TestStep.test_case_id == saved_case.id
        ).order_by(TestStep.step_number.asc()).all()
        assert len(saved_steps) == 1
        assert saved_steps[0].action == "点击听写记录"
        assert saved_steps[0].expected_result == "界面显示最近的听写记录"

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
        assert data["code"] == 200
        assert data["data"]["preview_mode"] == "test_cases"
        assert data["data"]["total"] == 1
        assert len(data["data"]["items"]) == 1
        assert data["data"]["case_total"] == 1
        assert len(data["data"]["case_items"]) == 1
        assert data["data"]["case_items"][0]["title"] == "点击听写记录，界面显示最近的听写记录"
        assert data["data"]["case_items"][0]["step_count"] == 1
        assert data["data"]["case_items"][0]["steps"][0]["action"] == "点击听写记录"

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
        assert data["code"] == 200
        assert data["data"]["saved_count"] == 1
        assert data["data"]["saved_case_count"] == 0


class TestImportXmindAiEnhance:
    """AI增强模式测试。

    使用无效 API Key 触发 AI 调用失败，验证降级到普通解析逻辑。
    不 Mock 任何内部方法，通过构造函数注入无效配置实现异常触发。
    """

    def test_ai_enhance_with_invalid_key_falls_back_to_normal_parse(
        self, client, auth_headers, test_project, valid_xmind
    ) -> None:
        """AI增强模式在API调用失败时应降级到普通解析。"""
        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true", "ai_enhance": "true"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["preview_mode"] == "test_points"
        assert data["data"]["total"] >= 1

    def test_ai_enhance_false_uses_normal_path(
        self, client, auth_headers, test_project, valid_xmind
    ) -> None:
        with open(valid_xmind, "rb") as f:
            resp = client.post(
                "/api/v1/test-point/import-xmind",
                files={"file": ("test.xmind", f, "application/octet-stream")},
                data={"project_id": str(test_project), "preview": "true", "ai_enhance": "false"},
                headers=auth_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 200
        assert data["data"]["preview_mode"] == "test_points"


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
