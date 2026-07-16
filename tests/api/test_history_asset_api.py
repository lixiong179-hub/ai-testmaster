import io
import json
import zipfile

from openpyxl import Workbook

from app.models.history_asset import HistoryAsset
from app.models.test_case import TestCase

BASE = "/api/v1/history-assets"


def _make_excel_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "用例信息"
    ws.append(["用例标题", "所属模块", "前置条件", "预期结果", "优先级"])
    ws.append(["登录成功", "登录模块", "用户已注册", "跳转首页", 2])
    ws_steps = wb.create_sheet("测试步骤")
    ws_steps.append(["步骤编号", "操作步骤", "预期结果"])
    ws_steps.append([1, "输入账号密码", "输入成功"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _make_xmind_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", '<?xml version="1.0"?><xmap-content><sheet><topic><title>root</title></topic></sheet></xmap-content>')
        zf.writestr("meta.xml", '<?xml version="1.0"?>')
    return buf.getvalue()


async def _create_test_case(async_db, project_id: int, user_id: int, case_no: str) -> TestCase:
    case = TestCase(
        case_no=case_no,
        project_id=project_id,
        module="测试模块",
        title=f"用例_{case_no}",
        precondition="无",
        steps_json=[{"step": 1, "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="manual",
        generate_status=1,
    )
    async_db.add(case)
    await async_db.flush()
    return case


class TestHistoryAssetPermission:
    async def test_upload_without_token_returns_401(self, async_client):
        resp = await async_client.post(f"{BASE}/upload", files={"file": ("t.xlsx", b"", "application/octet-stream")}, data={"project_id": "1", "asset_type": "excel"})
        assert resp.status_code in (401, 403)

    async def test_get_asset_without_token_returns_401(self, async_client):
        resp = await async_client.get(f"{BASE}/1")
        assert resp.status_code in (401, 403)

    async def test_list_without_token_returns_401(self, async_client):
        resp = await async_client.get(BASE, params={"project_id": 1})
        assert resp.status_code in (401, 403)

    async def test_align_without_token_returns_401(self, async_client):
        resp = await async_client.post(f"{BASE}/align", json={"project_id": 1, "history_asset_ids": [1]})
        assert resp.status_code in (401, 403)


class TestHistoryAssetUpload:
    async def test_upload_excel_success(self, async_auth_client, async_test_project):
        excelBytes = _make_excel_bytes()
        resp = await async_auth_client.post(
            f"{BASE}/upload",
            files={"file": ("test.xlsx", io.BytesIO(excelBytes), "application/octet-stream")},
            data={"project_id": str(async_test_project.id), "asset_type": "excel"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "excel"
        assert data["parse_status"] == "completed"

    async def test_upload_xmind_success(self, async_auth_client, async_test_project):
        xmindBytes = _make_xmind_bytes()
        resp = await async_auth_client.post(
            f"{BASE}/upload",
            files={"file": ("test.xmind", io.BytesIO(xmindBytes), "application/octet-stream")},
            data={"project_id": str(async_test_project.id), "asset_type": "xmind"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "xmind"

    async def test_upload_invalid_asset_type_returns_400(self, async_auth_client, async_test_project):
        excelBytes = _make_excel_bytes()
        resp = await async_auth_client.post(
            f"{BASE}/upload",
            files={"file": ("test.xlsx", io.BytesIO(excelBytes), "application/octet-stream")},
            data={"project_id": str(async_test_project.id), "asset_type": "invalid"},
        )
        assert resp.status_code == 400

    async def test_upload_wrong_ext_returns_400(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            f"{BASE}/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
            data={"project_id": str(async_test_project.id), "asset_type": "excel"},
        )
        assert resp.status_code == 400


class TestHistoryAssetListAndGet:
    async def test_list_returns_project_assets(self, async_auth_client, async_test_project, async_db):
        asset = HistoryAsset(
            project_id=async_test_project.id,
            user_id=async_test_project.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="list_test.xlsx",
            parse_status="completed",
            case_count=2,
        )
        async_db.add(asset)
        await async_db.flush()

        resp = await async_auth_client.get(BASE, params={"project_id": async_test_project.id})
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert any(a["id"] == asset.id for a in data["items"])

    async def test_get_asset_detail(self, async_auth_client, async_test_project, async_db):
        asset = HistoryAsset(
            project_id=async_test_project.id,
            user_id=async_test_project.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="detail_test.xlsx",
            parse_status="completed",
            parsed_cases_json=[{"title": "用例1"}],
            case_count=1,
        )
        async_db.add(asset)
        await async_db.flush()

        resp = await async_auth_client.get(f"{BASE}/{asset.id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == asset.id
        assert data["parse_status"] == "completed"
        assert len(data["parsed_cases"]) == 1

    async def test_get_other_user_asset_returns_403(
        self, async_db, async_test_project, async_admin_client
    ):
        asset = HistoryAsset(
            project_id=async_test_project.id,
            user_id=async_test_project.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="other_user.xlsx",
            parse_status="completed",
            case_count=0,
        )
        async_db.add(asset)
        await async_db.flush()

        resp = await async_admin_client.get(f"{BASE}/{asset.id}")
        assert resp.status_code == 403

    async def test_get_nonexistent_asset_returns_404(self, async_auth_client):
        resp = await async_auth_client.get(f"{BASE}/99999")
        assert resp.status_code == 404


class TestHistoryAssetAlign:
    async def test_align_returns_classification(self, async_auth_client, async_test_project, async_db):
        asset = HistoryAsset(
            project_id=async_test_project.id,
            user_id=async_test_project.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="align_test.xlsx",
            parse_status="completed",
            parsed_cases_json=[{"title": "用例1"}, {"title": "用例2"}],
            case_count=2,
        )
        async_db.add(asset)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"{BASE}/align",
            data={
                "project_id": async_test_project.id,
                "history_asset_ids": json.dumps([asset.id]),
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["summary"]["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["classification"] in ("REUSE_CASE", "UPDATE_CASE", "NEW_CASE", "DEPRECATED_CASE", "CONFIRM_REQUIRED")
            assert item["confidence"] >= 0.0
            assert item["reason"] != ""

    async def test_align_with_nonexistent_asset_returns_404(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            f"{BASE}/align",
            data={
                "project_id": async_test_project.id,
                "history_asset_ids": json.dumps([99999]),
            },
        )
        assert resp.status_code == 404


class TestHistoryAssetImportSystemCases:
    async def test_import_system_cases_success(self, async_auth_client, async_test_project, async_db):
        case = await _create_test_case(async_db, async_test_project.id, async_test_project.user_id, "IMP-CASE-001")

        resp = await async_auth_client.post(
            f"{BASE}/import-system-cases",
            data={
                "project_id": async_test_project.id,
                "case_ids": json.dumps([case.id]),
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "system_cases"
        assert data["parse_status"] == "completed"
        assert data["case_count"] == 1

    async def test_import_nonexistent_cases_returns_404(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            f"{BASE}/import-system-cases",
            data={
                "project_id": async_test_project.id,
                "case_ids": json.dumps([99999]),
            },
        )
        assert resp.status_code == 404
