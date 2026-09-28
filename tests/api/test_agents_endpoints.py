"""Agent API 端点集成测试。

覆盖 /api/v1/agents 下 7 个端点: 创建/查询/取消会话、消息流、列表分页、
审批、回滚。使用 async_auth_client 真实调用 HTTP, 测试数据经 async_db
直接创建(共享事务), 覆盖正常/异常/边界场景。
"""
from app.models.agent_audit import AgentAudit
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession


# ── 测试数据辅助函数 ──


async def _create_session(async_db, *, project_id, created_by=None,
                          agent_type="test_generation", status="running") -> AgentSession:
    """通过 async_db 创建 AgentSession 记录。"""
    session = AgentSession(
        project_id=project_id, agent_type=agent_type, status=status,
        token_cost=0, iteration_count=0, loop_detected=False, created_by=created_by,
    )
    async_db.add(session)
    await async_db.flush()
    await async_db.refresh(session)
    return session


async def _append_message(async_db, *, session_id, role="assistant",
                          content=None, token_cost=0) -> AgentMessage:
    """通过 async_db 追加 AgentMessage 记录。"""
    message = AgentMessage(
        session_id=session_id, role=role,
        content=content or {"text": "test message"}, token_cost=token_cost,
    )
    async_db.add(message)
    await async_db.flush()
    await async_db.refresh(message)
    return message


async def _create_audit(async_db, *, session_id, iteration=1,
                        action_type="tool_call", action_detail=None,
                        decision_confidence=None) -> AgentAudit:
    """通过 async_db 创建 AgentAudit 记录(human_approved=0 待审批)。"""
    audit = AgentAudit(
        session_id=session_id, iteration=iteration, action_type=action_type,
        action_detail=action_detail or {}, decision_confidence=decision_confidence,
        human_approved=0,
    )
    async_db.add(audit)
    await async_db.flush()
    await async_db.refresh(audit)
    return audit


async def _create_other_user(async_db):
    """创建第二个测试用户（非 async_auth_client 认证用户），用于 IDOR 越权测试。"""
    import uuid
    from app.models.user import User
    from app.utils.jwt_utils import get_password_hash
    suffix = uuid.uuid4().hex[:8]
    other = User(
        username=f"async_other_user_{suffix}",
        email=f"async_other_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"),
        is_active=True,
        is_superuser=False,
    )
    async_db.add(other)
    await async_db.flush()
    await async_db.refresh(other)
    return other


# ── 1. POST /agents/sessions 创建会话 ──


class TestCreateSession:
    async def test_create_session_success(self, async_auth_client, async_test_project, async_test_user):
        resp = await async_auth_client.post(
            "/api/v1/agents/sessions",
            json={"agent_type": "test_generation", "project_id": async_test_project.id,
                  "initial_artifacts": []},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        data = body["data"]
        assert data["id"] > 0
        assert data["project_id"] == async_test_project.id
        assert data["agent_type"] == "test_generation"
        assert data["status"] == "running"
        assert data["created_by"] == async_test_user.id

    async def test_create_session_invalid_agent_type(self, async_auth_client, async_test_project):
        resp = await async_auth_client.post(
            "/api/v1/agents/sessions",
            json={"agent_type": "unknown", "project_id": async_test_project.id},
        )
        assert resp.status_code == 400

    async def test_create_session_nonexistent_project(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/agents/sessions",
            json={"agent_type": "test_generation", "project_id": 999999},
        )
        assert resp.status_code == 403

    async def test_create_session_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/agents/sessions",
            json={"agent_type": "test_generation", "project_id": 1},
        )
        assert resp.status_code == 401


# ── 2. GET /agents/sessions/{session_id} 查询会话 ──


class TestGetSession:
    async def test_get_session_success(self, async_auth_client, async_test_project,
                                       async_test_user, async_db):
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=async_test_user.id,
        )
        resp = await async_auth_client.get(f"/api/v1/agents/sessions/{session.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["id"] == session.id
        assert body["data"]["agent_type"] == "test_generation"

    async def test_get_session_not_found(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/agents/sessions/999999")
        assert resp.status_code == 404

    async def test_get_session_forbidden_idor(self, async_auth_client, async_test_project, async_db):
        other = await _create_other_user(async_db)
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=other.id,
        )
        resp = await async_auth_client.get(f"/api/v1/agents/sessions/{session.id}")
        assert resp.status_code == 403


# ── 3. GET /agents/sessions/{session_id}/messages 查询消息 ──


class TestListMessages:
    async def test_list_messages_success(self, async_auth_client, async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        await _append_message(async_db, session_id=session.id, role="user",
                              content={"text": "hello"})
        await _append_message(async_db, session_id=session.id, role="assistant",
                              content={"text": "hi"})
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions/{session.id}/messages",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        messages = body["data"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    async def test_list_messages_limit(self, async_auth_client, async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        for i in range(5):
            await _append_message(async_db, session_id=session.id,
                                  content={"text": f"msg-{i}"})
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions/{session.id}/messages?limit=2",
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    async def test_list_messages_forbidden_idor(self, async_auth_client, async_test_project, async_db):
        other = await _create_other_user(async_db)
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=other.id,
        )
        await _append_message(async_db, session_id=session.id, content={"text": "secret"})
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions/{session.id}/messages",
        )
        assert resp.status_code == 403


# ── 4. POST /agents/sessions/{session_id}/cancel 取消会话 ──


class TestCancelSession:
    async def test_cancel_session_success(self, async_auth_client, async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        resp = await async_auth_client.post(f"/api/v1/agents/sessions/{session.id}/cancel")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["status"] == "cancelled"
        assert body["data"]["completed_at"] is not None

    async def test_cancel_session_not_found(self, async_auth_client):
        resp = await async_auth_client.post("/api/v1/agents/sessions/999999/cancel")
        assert resp.status_code == 400

    async def test_cancel_session_forbidden_idor(self, async_auth_client, async_test_project, async_db):
        other = await _create_other_user(async_db)
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=other.id,
        )
        resp = await async_auth_client.post(f"/api/v1/agents/sessions/{session.id}/cancel")
        assert resp.status_code == 403


# ── 5. GET /agents/sessions 列表查询 ──


class TestListSessions:
    async def test_list_by_project(self, async_auth_client, async_test_project, async_db):
        await _create_session(async_db, project_id=async_test_project.id)
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions?project_id={async_test_project.id}",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["total"] >= 1
        for item in body["data"]["items"]:
            assert item["project_id"] == async_test_project.id

    async def test_list_by_agent_type(self, async_auth_client, async_test_project, async_db):
        await _create_session(async_db, project_id=async_test_project.id,
                              agent_type="failure_analysis")
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions?project_id={async_test_project.id}"
            "&agent_type=failure_analysis",
        )
        assert resp.status_code == 200
        for item in resp.json()["data"]["items"]:
            assert item["agent_type"] == "failure_analysis"

    async def test_list_by_status(self, async_auth_client, async_test_project, async_db):
        await _create_session(async_db, project_id=async_test_project.id, status="completed")
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions?project_id={async_test_project.id}&status=completed",
        )
        assert resp.status_code == 200
        for item in resp.json()["data"]["items"]:
            assert item["status"] == "completed"

    async def test_list_pagination(self, async_auth_client, async_test_project, async_db):
        for _ in range(3):
            await _create_session(async_db, project_id=async_test_project.id)
        resp = await async_auth_client.get(
            f"/api/v1/agents/sessions?project_id={async_test_project.id}&offset=0&limit=2",
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]["items"]) <= 2
        assert body["data"]["total"] >= 3


# ── 6. POST /agents/audits/{audit_id}/approve 审批 ──


class TestApproveAudit:
    async def test_approve_true(self, async_auth_client, async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        audit = await _create_audit(async_db, session_id=session.id)
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/approve", json={"approved": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["human_approved"] == 1

    async def test_approve_false(self, async_auth_client, async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        audit = await _create_audit(async_db, session_id=session.id)
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/approve", json={"approved": False},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["human_approved"] == 2

    async def test_approve_not_found(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/agents/audits/999999/approve", json={"approved": True},
        )
        assert resp.status_code == 400

    async def test_approve_forbidden_idor(self, async_auth_client, async_test_project, async_db):
        other = await _create_other_user(async_db)
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=other.id,
        )
        audit = await _create_audit(async_db, session_id=session.id)
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/approve", json={"approved": True},
        )
        assert resp.status_code == 403


# ── 7. POST /agents/audits/{audit_id}/rollback 回滚 ──


class TestRollbackAudit:
    async def test_rollback_create_test_case_success(self, async_auth_client,
                                                     async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        audit = await _create_audit(
            async_db, session_id=session.id, action_type="create_test_case",
            action_detail={"test_case_id": 99999},
        )
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/rollback", json={"reason": "测试回滚"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["rolled_back"] is True
        assert body["data"]["original_action_type"] == "create_test_case"
        assert body["data"]["new_audit_id"] > 0

    async def test_rollback_not_found(self, async_auth_client):
        resp = await async_auth_client.post(
            "/api/v1/agents/audits/999999/rollback", json={"reason": "测试"},
        )
        assert resp.status_code == 400

    async def test_rollback_unknown_action_type(self, async_auth_client,
                                                 async_test_project, async_test_user, async_db):
        session = await _create_session(async_db, project_id=async_test_project.id, created_by=async_test_user.id)
        audit = await _create_audit(async_db, session_id=session.id, action_type="tool_call")
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/rollback", json={"reason": "测试"},
        )
        assert resp.status_code == 501

    async def test_rollback_forbidden_idor(self, async_auth_client, async_test_project, async_db):
        other = await _create_other_user(async_db)
        session = await _create_session(
            async_db, project_id=async_test_project.id, created_by=other.id,
        )
        audit = await _create_audit(
            async_db, session_id=session.id, action_type="create_test_case",
            action_detail={"test_case_id": 99999},
        )
        resp = await async_auth_client.post(
            f"/api/v1/agents/audits/{audit.id}/rollback", json={"reason": "测试回滚"},
        )
        assert resp.status_code == 403
