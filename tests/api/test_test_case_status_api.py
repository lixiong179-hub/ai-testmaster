"""测试用例状态端点 async 测试。

覆盖 test_case_status.py 5 个端点的正常/异常/边界/权限场景：
    - GET  /api/v1/test-case/{test_case_id}/workflow             - 获取工作流状态
    - POST /api/v1/test-case/{test_case_id}/workflow/transition  - 工作流状态转换
    - GET  /api/v1/test-case/{test_case_id}/correction-status    - 获取纠正状态
    - POST /api/v1/test-case/{test_case_id}/start-correction     - 开始纠正
    - POST /api/v1/test-case/{test_case_id}/submit-verification  - 提交验证

使用 tests/api/conftest.py 的 async_db / async_auth_client fixture。
所有 async fixture 通过 async_db 事务隔离，测试结束 rollback 不落库。

注意：lifecycle_status 有 _guard_lifecycle_status 保护机制，直接赋值会触发 RuntimeError。
      测试 success 路径需用 enable_lifecycle_transition() 临时绕过。
      correction_status 无 guard，可直接赋值。
"""
import pytest

from app.models.test_case import TestCase


async def _create_test_case(
    db,
    *,
    project_id: int,
    title: str = "test_case_for_status",
    lifecycle_status: str = "draft",
    correction_status: str | None = None,
    case_no: str | None = None,
) -> TestCase:
    """直接通过 ORM 创建一条测试用例，供状态端点测试使用"""
    case = TestCase(
        case_no=case_no or f"TC-STATUS-{title}",
        project_id=project_id,
        module="test_module",
        title=title,
        precondition="无",
        steps_json=[{"step": 1, "action": "打开页面", "param": ""}],
        expected_result="页面正常显示",
        priority=2,
        case_type="UI",
        lifecycle_status=lifecycle_status,
        correction_status=correction_status,
    )
    db.add(case)
    await db.flush()
    return case


class TestGetTestCaseWorkflow:
    """GET /api/v1/test-case/{test_case_id}/workflow 获取工作流状态。"""

    async def test_get_workflow_draft_status(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """草稿状态返回正确的允许转换列表"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="draft",
        )
        resp = await async_auth_client.get(f"/api/v1/test-case/{case.id}/workflow")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["test_case_id"] == case.id
        assert data["current_status"] == "draft"
        assert data["current_status_label"] == "草稿"
        allowed = [t["status"] for t in data["allowed_transitions"]]
        assert "pending_review" in allowed
        assert "deprecated" in allowed

    async def test_get_workflow_active_status(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """active 状态返回其允许的转换"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="active",
        )
        resp = await async_auth_client.get(f"/api/v1/test-case/{case.id}/workflow")
        assert resp.status_code == 200
        allowed = [t["status"] for t in resp.json()["data"]["allowed_transitions"]]
        assert "needs_modify" in allowed
        assert "locator_broken" in allowed
        assert "deprecated" in allowed

    async def test_get_workflow_archived_no_transitions(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """archived 终态返回空允许转换列表"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="archived",
        )
        resp = await async_auth_client.get(f"/api/v1/test-case/{case.id}/workflow")
        assert resp.status_code == 200
        assert resp.json()["data"]["allowed_transitions"] == []

    async def test_get_workflow_nonexistent(self, async_auth_client) -> None:
        """不存在的用例返回 404"""
        resp = await async_auth_client.get("/api/v1/test-case/99999/workflow")
        assert resp.status_code == 404
        assert resp.json()["msg"] == "测试用例不存在"

    async def test_get_workflow_deleted_case_not_found(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """已删除用例返回 404"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
        )
        case.is_deleted = True
        await async_db.flush()
        resp = await async_auth_client.get(f"/api/v1/test-case/{case.id}/workflow")
        assert resp.status_code == 404


class TestWorkflowTransition:
    """POST /api/v1/test-case/{test_case_id}/workflow/transition 工作流状态转换。"""

    async def test_transition_draft_to_pending_review_success(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """draft → pending_review 转换成功（端点内部已用 enable_lifecycle_transition 绕过 guard）"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="draft",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/workflow/transition",
            json={"target_status": "pending_review", "comment": "提交审核"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["previous_status"] == "draft"
        assert data["current_status"] == "pending_review"
        assert data["comment"] == "提交审核"

    async def test_transition_invalid_path_rejected(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """draft → active 不在允许转换列表中，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="draft",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/workflow/transition",
            json={"target_status": "active"},
        )
        assert resp.status_code == 400
        assert "不允许" in resp.json()["msg"]

    async def test_transition_archived_no_outgoing(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """archived 终态无任何允许转换，所有 target_status 都返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, lifecycle_status="archived",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/workflow/transition",
            json={"target_status": "draft"},
        )
        assert resp.status_code == 400

    async def test_transition_nonexistent_case(self, async_auth_client) -> None:
        """不存在的用例返回 404"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/99999/workflow/transition",
            json={"target_status": "active"},
        )
        assert resp.status_code == 404

    async def test_transition_invalid_target_status_validation(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """target_status 不在 TestCaseLifecycleStatus 枚举中，触发 Pydantic 校验错误返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/workflow/transition",
            json={"target_status": "invalid_status_xyz"},
        )
        assert resp.status_code == 400


class TestGetCorrectionStatus:
    """GET /api/v1/test-case/{test_case_id}/correction-status 获取纠正状态。"""

    async def test_get_correction_status_none(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """无纠正状态（None）时返回 '无' 标签"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, correction_status=None,
        )
        resp = await async_auth_client.get(
            f"/api/v1/test-case/{case.id}/correction-status"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["correction_status"] is None
        assert data["correction_status_label"] == "无"
        allowed = [t["status"] for t in data["allowed_transitions"]]
        assert "failed_correction" in allowed

    async def test_get_correction_status_correcting(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """correcting 状态返回其允许的转换"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="correcting",
        )
        resp = await async_auth_client.get(
            f"/api/v1/test-case/{case.id}/correction-status"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["correction_status"] == "correcting"
        assert data["correction_status_label"] == "纠正中"
        allowed = [t["status"] for t in data["allowed_transitions"]]
        assert "verifying" in allowed
        assert "failed_correction" in allowed

    async def test_get_correction_status_nonexistent(self, async_auth_client) -> None:
        """不存在的用例返回 404"""
        resp = await async_auth_client.get(
            "/api/v1/test-case/99999/correction-status"
        )
        assert resp.status_code == 404


class TestStartCorrection:
    """POST /api/v1/test-case/{test_case_id}/start-correction 开始纠正。"""

    async def test_start_correction_from_none(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """无纠正状态时开始纠正成功"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, correction_status=None,
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/start-correction"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["correction_status"] == "correcting"
        assert data["correction_status_label"] == "纠正中"

    async def test_start_correction_from_failed(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """failed_correction 状态开始纠正成功"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="failed_correction",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/start-correction"
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["correction_status"] == "correcting"

    async def test_start_correction_idempotent(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """correcting 状态再次开始纠正仍成功（幂等）"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="correcting",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/start-correction"
        )
        assert resp.status_code == 200

    async def test_start_correction_blocked_when_verified(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """verified 状态不允许开始纠正，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="verified",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/start-correction"
        )
        assert resp.status_code == 400
        assert "已验证通过" in resp.json()["msg"]

    async def test_start_correction_blocked_when_verifying(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """verifying 状态不允许开始纠正，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="verifying",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/start-correction"
        )
        assert resp.status_code == 400
        assert "验证中" in resp.json()["msg"]

    async def test_start_correction_nonexistent(self, async_auth_client) -> None:
        """不存在的用例返回 404"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/99999/start-correction"
        )
        assert resp.status_code == 404


class TestSubmitVerification:
    """POST /api/v1/test-case/{test_case_id}/submit-verification 提交验证。"""

    async def test_submit_verification_from_correcting(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """correcting 状态提交验证成功"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="correcting",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/submit-verification"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["correction_status"] == "verifying"
        assert data["correction_status_label"] == "验证中"

    async def test_submit_verification_blocked_when_none(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """无纠正状态时不允许提交验证，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id, correction_status=None,
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/submit-verification"
        )
        assert resp.status_code == 400
        assert "纠正中" in resp.json()["msg"]

    async def test_submit_verification_blocked_when_verifying(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """verifying 状态不允许重复提交，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="verifying",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/submit-verification"
        )
        assert resp.status_code == 400

    async def test_submit_verification_blocked_when_verified(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """verified 状态不允许提交验证，返回 400"""
        case = await _create_test_case(
            async_db, project_id=async_test_project.id,
            correction_status="verified",
        )
        resp = await async_auth_client.post(
            f"/api/v1/test-case/{case.id}/submit-verification"
        )
        assert resp.status_code == 400

    async def test_submit_verification_nonexistent(self, async_auth_client) -> None:
        """不存在的用例返回 404"""
        resp = await async_auth_client.post(
            "/api/v1/test-case/99999/submit-verification"
        )
        assert resp.status_code == 404


class TestCaseStatusPermissions:
    """测试用例状态端点鉴权场景。"""

    async def test_get_workflow_unauthenticated(self, async_client) -> None:
        resp = await async_client.get("/api/v1/test-case/1/workflow")
        assert resp.status_code == 401

    async def test_workflow_transition_unauthenticated(self, async_client) -> None:
        resp = await async_client.post(
            "/api/v1/test-case/1/workflow/transition",
            json={"target_status": "active"},
        )
        assert resp.status_code == 401

    async def test_get_correction_status_unauthenticated(self, async_client) -> None:
        resp = await async_client.get("/api/v1/test-case/1/correction-status")
        assert resp.status_code == 401

    async def test_start_correction_unauthenticated(self, async_client) -> None:
        resp = await async_client.post("/api/v1/test-case/1/start-correction")
        assert resp.status_code == 401

    async def test_submit_verification_unauthenticated(self, async_client) -> None:
        resp = await async_client.post("/api/v1/test-case/1/submit-verification")
        assert resp.status_code == 401
