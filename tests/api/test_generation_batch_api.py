import pytest
from app.models.generation_batch import GenerationBatch, GenerationBatchSave
from app.schemas.generation_batch import (
    GenerationBatchCreate,
    GenerationBatchUpdate,
    GenerationBatchSaveRequest,
    PreviewCasePayload,
)

GenerationBatchCreate.__test__ = False
GenerationBatchUpdate.__test__ = False
GenerationBatchSaveRequest.__test__ = False
PreviewCasePayload.__test__ = False


class TestGenerationBatchNoAuth:
    def test_create_without_auth(self, client):
        resp = client.post("/api/v1/generation-batches", json={
            "project_id": 1,
            "scenario_type": "B1_REQUIREMENT_TESTPOINT",
            "generation_strategy": "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        })
        assert resp.status_code in (401, 403)

    def test_get_without_auth(self, client):
        resp = client.get("/api/v1/generation-batches/1")
        assert resp.status_code in (401, 403)

    def test_update_without_auth(self, client):
        resp = client.patch("/api/v1/generation-batches/1", json={"status": "context_ready"})
        assert resp.status_code in (401, 403)

    def test_save_without_auth(self, client):
        resp = client.post("/api/v1/generation-batches/1/save", json={
            "idempotency_key": "test-key",
            "save_mode": "draft",
            "cases": [],
        })
        assert resp.status_code in (401, 403)


class TestGenerationBatchCRUD:
    def test_create_batch(self, db, client, authHeaders, testProject):
        resp = client.post(
            "/api/v1/generation-batches",
            json={
                "project_id": testProject.id,
                "entry_type": "NEW_FEATURE_GENERATION",
                "scenario_type": "B1_REQUIREMENT_TESTPOINT",
                "generation_strategy": "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
                "requirement_file_ids": [],
                "test_point_ids": [1, 2],
                "ui_screen_ids": [],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "created"
        assert data["scenario_type"] == "B1_REQUIREMENT_TESTPOINT"
        assert data["test_point_ids"] == [1, 2]
        assert data["batch_no"].startswith("GB")

    def test_get_batch(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TEST-GET",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="created",
        )
        db.add(batch)
        db.flush()

        resp = client.get(
            f"/api/v1/generation-batches/{batch.id}",
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["batch_no"] == "GB-TEST-GET"
        assert data["status"] == "created"

    def test_get_nonexistent_batch(self, client, authHeaders):
        resp = client.get("/api/v1/generation-batches/99999", headers=authHeaders)
        assert resp.status_code == 404

    def test_get_other_user_batch(self, db, client, adminAuthHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TEST-OTHER",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="created",
        )
        db.add(batch)
        db.flush()

        resp = client.get(
            f"/api/v1/generation-batches/{batch.id}",
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 403


class TestGenerationBatchStatusMachine:
    def test_valid_transition_created_to_context_ready(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TRANS-1",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="created",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "context_ready"},
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "context_ready"

    def test_valid_transition_context_ready_to_generating(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TRANS-2",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="context_ready",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "generating"},
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text

    def test_invalid_transition_created_to_saved(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TRANS-3",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="created",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "saved"},
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_invalid_transition_saved_to_generating(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TRANS-4",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "generating"},
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_valid_transition_failed_to_context_ready(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-TRANS-5",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="failed",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "context_ready"},
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text

    def test_update_context_stats(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-UPDATE-1",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="context_ready",
        )
        db.add(batch)
        db.flush()

        resp = client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={
                "context_stats": {"requirements_used": 3, "test_points_loaded": 5},
                "warnings": [{"code": "UI_NO_MATCH", "message": "test", "detail": {}}],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["context_stats"]["requirements_used"] == 3
        assert len(data["warnings"]) == 1


class TestGenerationBatchSaveIdempotent:
    def test_save_creates_cases(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-SAVE-1",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        resp = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "idem-key-1",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-1",
                        "title": "测试用例1",
                        "module": "登录模块",
                        "precondition": "用户已注册",
                        "steps": [{"step": 1, "action": "打开登录页", "expected_result": "显示登录表单"}],
                        "expected_result": "登录成功",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "passed",
                        "selected_for_save": True,
                    },
                ],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 1


class TestGenerationBatchSaveHashConflict:
    def test_idempotent_key_with_different_content_returns_409(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-HASH-CONFLICT",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        save_body_1 = {
            "idempotency_key": "idem-conflict",
            "save_mode": "draft",
            "cases": [
                {
                    "client_id": "case-original",
                    "title": "原始用例",
                    "steps": [{"step": 1, "action": "操作1", "expected_result": "结果1"}],
                    "expected_result": "预期1",
                    "priority": 2,
                    "case_type": "manual",
                    "quality_status": "passed",
                    "selected_for_save": True,
                },
            ],
        }

        resp1 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body_1,
            headers=authHeaders,
        )
        assert resp1.status_code == 200

        batch.status = "preview_ready"
        db.flush()

        save_body_2 = {
            "idempotency_key": "idem-conflict",
            "save_mode": "draft",
            "cases": [
                {
                    "client_id": "case-changed",
                    "title": "修改后的用例",
                    "steps": [{"step": 1, "action": "操作2", "expected_result": "结果2"}],
                    "expected_result": "预期2",
                    "priority": 1,
                    "case_type": "manual",
                    "quality_status": "passed",
                    "selected_for_save": True,
                },
            ],
        }

        resp2 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body_2,
            headers=authHeaders,
        )
        assert resp2.status_code == 409
        assert "不一致" in resp2.json()["msg"]

    def test_idempotent_key_with_different_save_mode_returns_409(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-HASH-SAVEMODE",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        base_case = {
            "client_id": "case-savemode",
            "title": "保存模式测试",
            "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
            "expected_result": "预期",
            "priority": 2,
            "case_type": "manual",
            "quality_status": "passed",
            "selected_for_save": True,
        }

        resp1 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={"idempotency_key": "idem-savemode", "save_mode": "draft", "cases": [base_case]},
            headers=authHeaders,
        )
        assert resp1.status_code == 200

        batch.status = "preview_ready"
        db.flush()

        resp2 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={"idempotency_key": "idem-savemode", "save_mode": "formal", "cases": [base_case]},
            headers=authHeaders,
        )
        assert resp2.status_code == 409


class TestGenerationBatchReqFileValidation:
    def test_save_with_invalid_requirement_file_id_returns_400(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-REQFILE-INVALID",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        resp = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "idem-reqfile-invalid",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-bad-req",
                        "title": "无效需求文件",
                        "requirement_file_id": 99999,
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                        "expected_result": "预期",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "passed",
                        "selected_for_save": True,
                    },
                ],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 400
        assert "需求文件" in resp.json()["msg"]

    def test_save_idempotent_returns_same_result(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-SAVE-IDEM",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        save_body = {
            "idempotency_key": "idem-key-dup",
            "save_mode": "draft",
            "cases": [
                {
                    "client_id": "case-dup",
                    "title": "幂等测试用例",
                    "steps": [{"step": 1, "action": "操作1", "expected_result": "结果1"}],
                    "expected_result": "预期结果",
                    "priority": 2,
                    "case_type": "manual",
                    "quality_status": "passed",
                    "selected_for_save": True,
                },
            ],
        }

        resp1 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body,
            headers=authHeaders,
        )
        assert resp1.status_code == 200

        batch.status = "preview_ready"
        db.flush()

        resp2 = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body,
            headers=authHeaders,
        )
        assert resp2.status_code == 200
        assert resp2.json()["data"]["saved_count"] == resp1.json()["data"]["saved_count"]

    def test_save_wrong_status_returns_400(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-SAVE-STATUS",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="created",
        )
        db.add(batch)
        db.flush()

        resp = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "idem-wrong-status",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-ws",
                        "title": "状态错误测试",
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                        "expected_result": "预期",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "passed",
                        "selected_for_save": True,
                    },
                ],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 400

    def test_save_passed_only_filters_rejected(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-SAVE-FILTER",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="preview_ready",
        )
        db.add(batch)
        db.flush()

        resp = client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "idem-filter",
                "save_mode": "passed_only",
                "cases": [
                    {
                        "client_id": "case-pass",
                        "title": "通过用例",
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                        "expected_result": "预期",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "passed",
                        "selected_for_save": True,
                    },
                    {
                        "client_id": "case-reject",
                        "title": "拒绝用例",
                        "steps": [{"step": 1, "action": "操作", "expected_result": "结果"}],
                        "expected_result": "预期",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "rejected",
                        "selected_for_save": True,
                    },
                ],
            },
            headers=authHeaders,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 1
