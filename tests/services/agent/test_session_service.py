"""SessionService 单元测试。

覆盖 create_session / append_message / get_history / complete_session /
cancel_session / get_session / list_sessions 全部方法与校验分支，
使用真实 async_db fixture 事务隔离，无 Mock 数据库。

被测：app/services/agent/session_service.py（SessionService）
"""
import pytest

from app.models.project import Project
from app.services.agent.exceptions import AgentError
from app.services.agent.session_service import SessionService


@pytest.fixture
def service() -> SessionService:
    return SessionService()


class TestCreateSession:
    """create_session 创建会话。"""

    async def test_create_session_success(self, service, async_db, async_test_project):
        """正常创建 → 返回 AgentSession，status=running。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        assert session.id is not None
        assert session.agent_type == "test_generation"
        assert session.status == "running"
        assert session.token_cost == 0
        assert session.iteration_count == 0
        assert session.loop_detected is False

    async def test_create_session_invalid_agent_type(self, service, async_db, async_test_project):
        """非法 agent_type → AgentError。"""
        with pytest.raises(AgentError, match="非法 agent_type"):
            await service.create_session(
                async_db, agent_type="invalid_type",
                project_id=async_test_project.id,
            )


class TestAppendMessage:
    """append_message 追加消息。"""

    async def test_append_message_success(self, service, async_db, async_test_project):
        """正常追加 → 返回 AgentMessage。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        msg = await service.append_message(
            async_db, session_id=session.id, role="user",
            content={"text": "hello"}, token_cost=100,
        )
        assert msg.id is not None
        assert msg.session_id == session.id
        assert msg.role == "user"
        assert msg.content == {"text": "hello"}
        assert msg.token_cost == 100

    async def test_append_message_invalid_role(self, service, async_db, async_test_project):
        """非法 role → AgentError。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        with pytest.raises(AgentError, match="非法消息角色"):
            await service.append_message(
                async_db, session_id=session.id, role="invalid",
                content={"text": "x"},
            )


class TestGetHistory:
    """get_history 历史消息查询。"""

    async def test_get_history_ordered_asc(self, service, async_db, async_test_project):
        """返回按 created_at 升序的消息列表。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        for i in range(3):
            await service.append_message(
                async_db, session_id=session.id, role="user",
                content={"text": f"msg-{i}"},
            )
        history = await service.get_history(async_db, session.id)
        assert len(history) == 3
        assert [m.content["text"] for m in history] == ["msg-0", "msg-1", "msg-2"]

    async def test_get_history_limit(self, service, async_db, async_test_project):
        """limit 参数生效。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        for i in range(5):
            await service.append_message(
                async_db, session_id=session.id, role="user",
                content={"text": f"msg-{i}"},
            )
        history = await service.get_history(async_db, session.id, limit=2)
        assert len(history) == 2
        assert history[0].content["text"] == "msg-0"
        assert history[1].content["text"] == "msg-1"


class TestCompleteSession:
    """complete_session 关闭会话。"""

    async def test_complete_session_success(self, service, async_db, async_test_project):
        """正常完成 → status=completed + completed_at 设置。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        completed = await service.complete_session(
            async_db, session_id=session.id, status="completed",
            token_cost=500, iteration_count=3,
        )
        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert completed.token_cost == 500
        assert completed.iteration_count == 3

    async def test_complete_session_invalid_status(self, service, async_db, async_test_project):
        """状态非法 → AgentError。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        with pytest.raises(AgentError, match="非法会话状态"):
            await service.complete_session(
                async_db, session_id=session.id, status="invalid",
            )


class TestCancelSession:
    """cancel_session 取消会话。"""

    async def test_cancel_session(self, service, async_db, async_test_project):
        """取消 → status=cancelled。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        cancelled = await service.cancel_session(async_db, session.id)
        assert cancelled.status == "cancelled"
        assert cancelled.completed_at is not None


class TestGetSession:
    """get_session 单条查询。"""

    async def test_get_session_not_found(self, service, async_db):
        """不存在 → None。"""
        result = await service.get_session(async_db, 999999)
        assert result is None

    async def test_get_session_found(self, service, async_db, async_test_project):
        """存在 → 返回 AgentSession。"""
        session = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        fetched = await service.get_session(async_db, session.id)
        assert fetched is not None
        assert fetched.id == session.id
        assert fetched.agent_type == "test_generation"


class TestListSessions:
    """list_sessions 分页与过滤。"""

    async def test_list_sessions_filter_by_project(
        self, service, async_db, async_test_user, async_test_project
    ):
        """按 project_id 过滤。"""
        other_project = Project(
            name="other_project", user_id=async_test_user.id,
            description="other", status=1, project_type="web",
        )
        async_db.add(other_project)
        await async_db.flush()
        await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        await service.create_session(
            async_db, agent_type="test_generation",
            project_id=other_project.id,
        )
        sessions, total = await service.list_sessions(
            async_db, project_id=async_test_project.id,
        )
        assert total == 1
        assert len(sessions) == 1
        assert sessions[0].project_id == async_test_project.id

    async def test_list_sessions_filter_by_agent_type(self, service, async_db, async_test_project):
        """按 agent_type 过滤。"""
        await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        await service.create_session(
            async_db, agent_type="failure_analysis",
            project_id=async_test_project.id,
        )
        sessions, total = await service.list_sessions(
            async_db, agent_type="failure_analysis",
        )
        assert total == 1
        assert all(s.agent_type == "failure_analysis" for s in sessions)

    async def test_list_sessions_filter_by_status(self, service, async_db, async_test_project):
        """按 status 过滤。"""
        s1 = await service.create_session(
            async_db, agent_type="test_generation",
            project_id=async_test_project.id,
        )
        await service.complete_session(async_db, session_id=s1.id, status="completed")
        await service.create_session(
            async_db, agent_type="failure_analysis",
            project_id=async_test_project.id,
        )
        sessions, total = await service.list_sessions(async_db, status="completed")
        assert total == 1
        assert all(s.status == "completed" for s in sessions)

    async def test_list_sessions_pagination(self, service, async_db, async_test_project):
        """分页 offset/limit + total 正确。"""
        for _ in range(5):
            await service.create_session(
                async_db, agent_type="test_generation",
                project_id=async_test_project.id,
            )
        page1, total = await service.list_sessions(async_db, offset=0, limit=2)
        page2, _ = await service.list_sessions(async_db, offset=2, limit=2)
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        # 按 id 倒序：page1 的 id 应大于 page2 的 id
        assert page1[0].id > page2[0].id

    async def test_list_sessions_no_filter(self, service, async_db, async_test_project):
        """无过滤返回全部。"""
        for _ in range(3):
            await service.create_session(
                async_db, agent_type="test_generation",
                project_id=async_test_project.id,
            )
        sessions, total = await service.list_sessions(async_db)
        assert total == 3
        assert len(sessions) == 3
