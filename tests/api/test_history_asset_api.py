import io
import json
import zipfile

import pytest
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


def _create_test_case(db, projectId: int, userId: int, caseNo: str) -> TestCase:
    case = TestCase(
        case_no=caseNo,
        project_id=projectId,
        module="测试模块",
        title=f"用例_{caseNo}",
        precondition="无",
        steps_json=[{"step": 1, "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="manual",
        generate_status=1,
    )
    db.add(case)
    db.flush()
    return case


class TestHistoryAssetPermission:
    def test_upload_without_token_returns_401(self, client):
        resp = client.post(f"{BASE}/upload", files={"file": ("t.xlsx", b"", "application/octet-stream")}, data={"project_id": "1", "asset_type": "excel"})
        assert resp.status_code in (401, 403)

    def test_get_asset_without_token_returns_401(self, client):
        resp = client.get(f"{BASE}/1")
        assert resp.status_code in (401, 403)

    def test_list_without_token_returns_401(self, client):
        resp = client.get(BASE, params={"project_id": 1})
        assert resp.status_code in (401, 403)

    def test_align_without_token_returns_401(self, client):
        resp = client.post(f"{BASE}/align", json={"project_id": 1, "history_asset_ids": [1]})
        assert resp.status_code in (401, 403)


class TestHistoryAssetUpload:
    def test_upload_excel_success(self, db, client, authHeaders, testProject):
        excelBytes = _make_excel_bytes()
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.xlsx", io.BytesIO(excelBytes), "application/octet-stream")},
            data={"project_id": str(testProject.id), "asset_type": "excel"},
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "excel"
        assert data["parse_status"] == "completed"

    def test_upload_xmind_success(self, db, client, authHeaders, testProject):
        xmindBytes = _make_xmind_bytes()
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.xmind", io.BytesIO(xmindBytes), "application/octet-stream")},
            data={"project_id": str(testProject.id), "asset_type": "xmind"},
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "xmind"

    def test_upload_invalid_asset_type_returns_400(self, client, authHeaders, testProject):
        excelBytes = _make_excel_bytes()
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.xlsx", io.BytesIO(excelBytes), "application/octet-stream")},
            data={"project_id": str(testProject.id), "asset_type": "invalid"},
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_upload_wrong_ext_returns_400(self, client, authHeaders, testProject):
        resp = client.post(
            f"{BASE}/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
            data={"project_id": str(testProject.id), "asset_type": "excel"},
            headers=authHeaders,
        )
        assert resp.status_code == 400


class TestHistoryAssetListAndGet:
    def test_list_returns_project_assets(self, db, client, authHeaders, testProject):
        asset = HistoryAsset(
            project_id=testProject.id,
            user_id=testProject.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="list_test.xlsx",
            parse_status="completed",
            case_count=2,
        )
        db.add(asset)
        db.flush()

        resp = client.get(BASE, params={"project_id": testProject.id}, headers=authHeaders)
        assert resp.status_code == 200, resp.text
        items = resp.json()["data"]
        assert any(a["id"] == asset.id for a in items)

    def test_get_asset_detail(self, db, client, authHeaders, testProject):
        asset = HistoryAsset(
            project_id=testProject.id,
            user_id=testProject.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="detail_test.xlsx",
            parse_status="completed",
            parsed_cases_json=[{"title": "用例1"}],
            case_count=1,
        )
        db.add(asset)
        db.flush()

        resp = client.get(f"{BASE}/{asset.id}", headers=authHeaders)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["id"] == asset.id
        assert data["parse_status"] == "completed"
        assert len(data["parsed_cases"]) == 1

    def test_get_other_user_asset_returns_403(self, db, client, adminAuthHeaders, testProject):
        asset = HistoryAsset(
            project_id=testProject.id,
            user_id=testProject.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="other_user.xlsx",
            parse_status="completed",
            case_count=0,
        )
        db.add(asset)
        db.flush()

        resp = client.get(f"{BASE}/{asset.id}", headers=adminAuthHeaders)
        assert resp.status_code == 403

    def test_get_nonexistent_asset_returns_404(self, client, authHeaders):
        resp = client.get(f"{BASE}/99999", headers=authHeaders)
        assert resp.status_code == 404


class TestHistoryAssetAlign:
    def test_align_returns_classification(self, db, client, authHeaders, testProject):
        asset = HistoryAsset(
            project_id=testProject.id,
            user_id=testProject.user_id,
            asset_type="excel",
            file_path=None,
            original_filename="align_test.xlsx",
            parse_status="completed",
            parsed_cases_json=[{"title": "用例1"}, {"title": "用例2"}],
            case_count=2,
        )
        db.add(asset)
        db.flush()

        resp = client.post(
            f"{BASE}/align",
            data={
                "project_id": testProject.id,
                "history_asset_ids": json.dumps([asset.id]),
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["summary"]["total"] == 2
        assert len(data["items"]) == 2
        for item in data["items"]:
            assert item["classification"] in ("REUSE_CASE", "UPDATE_CASE", "NEW_CASE", "DEPRECATED_CASE", "CONFIRM_REQUIRED")
            assert item["confidence"] >= 0.0
            assert item["reason"] != ""

    def test_align_with_nonexistent_asset_returns_404(self, client, authHeaders, testProject):
        resp = client.post(
            f"{BASE}/align",
            data={
                "project_id": testProject.id,
                "history_asset_ids": json.dumps([99999]),
            },
            headers=authHeaders,
        )
        assert resp.status_code == 404


class TestHistoryAssetImportSystemCases:
    def test_import_system_cases_success(self, db, client, authHeaders, testProject):
        case = _create_test_case(db, testProject.id, testProject.user_id, "IMP-CASE-001")

        resp = client.post(
            f"{BASE}/import-system-cases",
            data={
                "project_id": testProject.id,
                "case_ids": json.dumps([case.id]),
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["asset_type"] == "system_cases"
        assert data["parse_status"] == "completed"
        assert data["case_count"] == 1

    def test_import_nonexistent_cases_returns_404(self, client, authHeaders, testProject):
        resp = client.post(
            f"{BASE}/import-system-cases",
            data={
                "project_id": testProject.id,
                "case_ids": json.dumps([99999]),
            },
            headers=authHeaders,
        )
        assert resp.status_code == 404
