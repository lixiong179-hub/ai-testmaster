"""generation_batch.py 端点 async 测试。

覆盖 /api/v1/generation-batches 端点的权限拦截、CRUD、状态机、save 幂等。
使用 tests/api/conftest.py 的 async fixture。

端点概览:
    - POST /                          - 创建生成批次
    - GET  /{batch_id}                - 获取批次
    - PATCH /{batch_id}               - 更新批次（状态/上下文统计）
    - POST /{batch_id}/save           - 保存批次（幂等/状态机校验）
"""
import pytest
from app.models.generation_batch import GenerationBatch
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


def _make_batch(project_id: int, user_id: int, batch_no: str = "GB-ASYNC-1",
                status: str = "created") -> GenerationBatch:
    return GenerationBatch(
        batch_no=batch_no,
        project_id=project_id,
        user_id=user_id,
        entry_type="NEW_FEATURE_GENERATION",
        scenario_type="B1_REQUIREMENT_TESTPOINT",
        generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        status=status,
    )


class TestGenerationBatchAsyncNoAuth:
    async def test_create_without_auth(self, async_client):
        resp = await async_client.post("/api/v1/generation-batches", json={
            "project_id": 1,
            "scenario_type": "B1_REQUIREMENT_TESTPOINT",
            "generation_strategy": "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        })
        assert resp.status_code in (401, 403, 404)

    async def test_get_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/generation-batches/1")
        assert resp.status_code in (401, 403, 404)

    async def test_update_without_auth(self, async_client):
        resp = await async_client.patch(
            "/api/v1/generation-batches/1",
            json={"status": "context_ready"},
        )
        assert resp.status_code in (401, 403, 404)

    async def test_save_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/generation-batches/1/save",
            json={"idempotency_key": "k", "save_mode": "draft", "cases": []},
        )
        assert resp.status_code in (401, 403, 404)


class TestGenerationBatchAsyncCRUD:
    async def test_create_batch(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/generation-batches",
            json={
                "project_id": async_test_project.id,
                "entry_type": "NEW_FEATURE_GENERATION",
                "scenario_type": "B1_REQUIREMENT_TESTPOINT",
                "generation_strategy": "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
                "requirement_file_ids": [],
                "test_point_ids": [1, 2],
                "ui_screen_ids": [],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["status"] == "created"
        assert data["scenario_type"] == "B1_REQUIREMENT_TESTPOINT"
        assert data["test_point_ids"] == [1, 2]
        assert data["batch_no"].startswith("GB")

    async def test_create_unauthorized_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/generation-batches",
            json={
                "project_id": 99999,
                "scenario_type": "B1_REQUIREMENT_TESTPOINT",
                "generation_strategy": "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            },
        )
        assert resp.status_code in (403, 404, 500)

    async def test_get_batch(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id)
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.get(
            f"/api/v1/generation-batches/{batch.id}"
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["batch_no"] == "GB-ASYNC-1"
        assert data["status"] == "created"

    async def test_get_nonexistent_batch(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/generation-batches/99999")
        assert resp.status_code == 404

    async def test_get_other_user_batch(
        self, async_db, async_admin_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-OTHER")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_admin_client.get(
            f"/api/v1/generation-batches/{batch.id}"
        )
        assert resp.status_code == 403


class TestGenerationBatchAsyncStatusMachine:
    async def test_valid_transition_created_to_context_ready(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-T1")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "context_ready"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["status"] == "context_ready"

    async def test_invalid_transition_created_to_saved(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-T2")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "saved"},
        )
        assert resp.status_code == 400

    async def test_invalid_transition_saved_to_generating(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-T3", status="saved")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "generating"},
        )
        assert resp.status_code == 400

    async def test_valid_transition_failed_to_context_ready(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-T4", status="failed")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={"status": "context_ready"},
        )
        assert resp.status_code == 200, resp.text

    async def test_update_context_stats(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-T5", status="context_ready")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.patch(
            f"/api/v1/generation-batches/{batch.id}",
            json={
                "context_stats": {"requirements_used": 3, "test_points_loaded": 5},
                "warnings": [{"code": "UI_NO_MATCH", "message": "test", "detail": {}}],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["context_stats"]["requirements_used"] == 3
        assert len(data["warnings"]) == 1


class TestGenerationBatchAsyncSave:
    async def test_save_creates_cases(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-S1", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-1",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-1",
                        "title": "异步测试用例1",
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
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 1

    async def test_save_wrong_status_returns_400(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-S2", status="created")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-2",
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
        )
        assert resp.status_code == 400

    async def test_save_passed_only_filters_rejected(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-S3", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-3",
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
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 1

    async def test_save_idempotent_returns_same_result(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-S4", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

        save_body = {
            "idempotency_key": "async-idem-4",
            "save_mode": "draft",
            "cases": [
                {
                    "client_id": "case-dup",
                    "title": "幂等测试",
                    "steps": [{"step": 1, "action": "操作1", "expected_result": "结果1"}],
                    "expected_result": "预期",
                    "priority": 2,
                    "case_type": "manual",
                    "quality_status": "passed",
                    "selected_for_save": True,
                },
            ],
        }

        resp1 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body,
        )
        assert resp1.status_code == 200

        # 重置 status 以通过状态机校验
        batch.status = "preview_ready"
        await async_db.flush()

        resp2 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body,
        )
        assert resp2.status_code == 200
        assert (resp2.json()["data"]["saved_count"]
                == resp1.json()["data"]["saved_count"])

    async def test_save_with_invalid_requirement_file_id_returns_400(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-S5", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-5",
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
        )
        assert resp.status_code == 400


class TestGenerationBatchAsyncHistoryUpdate:
    """历史资产更新批次 save 语义测试（update_existing/deprecate）。"""

    async def test_update_case_not_selected_for_save_is_skipped(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        existing = TestCase(
            case_no="TC-ASYNC-UPD-SKIP",
            project_id=async_test_project.id,
            module="登录模块",
            title="原始登录用例",
            precondition="用户已注册",
            steps_json=[{"step": 1, "action": "打开登录页", "expected_result": "显示登录表单"}],
            expected_result="登录成功",
            priority=2,
            case_type="manual",
            lifecycle_status="active",
        )
        async_db.add(existing)
        await async_db.flush()

        original_title = existing.title

        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-UPD-SKIP", status="preview_ready")
        batch.entry_type = "HISTORY_UPDATE"
        batch.scenario_type = "A2_HISTORY_INCREMENTAL_UPDATE"
        batch.generation_strategy = "HISTORY_INCREMENTAL_UPDATE"
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-upd-skip",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-upd-skip",
                        "title": "修改后的登录用例",
                        "module": "登录模块",
                        "precondition": "用户已注册",
                        "steps": [{"step": 1, "action": "打开新登录页", "expected_result": "显示新表单"}],
                        "expected_result": "新登录成功",
                        "priority": 1,
                        "case_type": "manual",
                        "quality_status": "pending_review",
                        "selected_for_save": False,
                        "classification": "UPDATE_CASE",
                        "history_case_id": existing.id,
                        "update_action": "update_existing",
                        "diff_fields": {"title": {"old": "原始登录用例", "new": "修改后的登录用例"}},
                    },
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 0

        await async_db.refresh(existing)
        assert existing.title == original_title

    async def test_deprecated_case_selected_triggers_lifecycle_transition(
        self, async_db, async_auth_client, async_test_project
    ):
        from app.models.test_case import TestCase

        existing = TestCase(
            case_no="TC-ASYNC-DEP-OK",
            project_id=async_test_project.id,
            module="旧功能模块",
            title="即将废弃的用例",
            precondition="无",
            steps_json=[{"step": 1, "action": "执行旧操作", "expected_result": "旧结果"}],
            expected_result="旧预期",
            priority=3,
            case_type="manual",
            lifecycle_status="active",
        )
        async_db.add(existing)
        await async_db.flush()

        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-DEP-OK", status="preview_ready")
        batch.entry_type = "HISTORY_UPDATE"
        batch.scenario_type = "A2_HISTORY_INCREMENTAL_UPDATE"
        batch.generation_strategy = "HISTORY_INCREMENTAL_UPDATE"
        async_db.add(batch)
        await async_db.flush()

        resp = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={
                "idempotency_key": "async-idem-dep-ok",
                "save_mode": "draft",
                "cases": [
                    {
                        "client_id": "case-dep-ok",
                        "title": "",
                        "module": "",
                        "precondition": "",
                        "steps": [],
                        "expected_result": "",
                        "priority": 2,
                        "case_type": "manual",
                        "quality_status": "pending_review",
                        "selected_for_save": True,
                        "classification": "DEPRECATED_CASE",
                        "history_case_id": existing.id,
                        "update_action": "deprecate",
                        "diff_fields": None,
                    },
                ],
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["saved_count"] == 1

        await async_db.refresh(existing)
        assert existing.lifecycle_status == "deprecated"
        assert existing.deprecated_at is not None


class TestGenerationBatchAsyncHashConflict:
    """幂等键冲突返回 409 测试。"""

    async def test_idempotent_key_with_different_content_returns_409(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-HASH-1", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

        save_body_1 = {
            "idempotency_key": "async-idem-conflict",
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

        resp1 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body_1,
        )
        assert resp1.status_code == 200

        batch.status = "preview_ready"
        await async_db.flush()

        save_body_2 = {
            "idempotency_key": "async-idem-conflict",
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

        resp2 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json=save_body_2,
        )
        assert resp2.status_code == 409

    async def test_idempotent_key_with_different_save_mode_returns_409(
        self, async_db, async_auth_client, async_test_project
    ):
        batch = _make_batch(async_test_project.id, async_test_project.user_id,
                            batch_no="GB-ASYNC-HASH-2", status="preview_ready")
        async_db.add(batch)
        await async_db.flush()

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

        resp1 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={"idempotency_key": "async-idem-savemode", "save_mode": "draft", "cases": [base_case]},
        )
        assert resp1.status_code == 200

        batch.status = "preview_ready"
        await async_db.flush()

        resp2 = await async_auth_client.post(
            f"/api/v1/generation-batches/{batch.id}/save",
            json={"idempotency_key": "async-idem-savemode", "save_mode": "formal", "cases": [base_case]},
        )
        assert resp2.status_code == 409
