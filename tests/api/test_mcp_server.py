"""MCP Server 端点集成测试。

覆盖 /api/v1/mcp 下的 2 个端点:
    - GET  /mcp/tools   工具列表
    - POST /mcp/sse     SSE 流式调用工具

SSE 解析:
    - 使用 httpx.AsyncClient 的 stream() 方法
    - 解析 event: xxx / data: {json} 格式
    - 验证事件序列(start / progress / result / error)
"""
import json
import uuid

import anyio
import pytest

from app.models.test_case import TestCase


@pytest.fixture(autouse=True)
def _reset_sse_app_status():
    """重置 sse_starlette AppStatus 避免跨测试事件循环绑定问题。

    sse_starlette 的 AppStatus.should_exit_event 在模块导入时创建,
    首次 wait() 后绑定到当时的事件循环。pytest-asyncio function 级
    事件循环导致后续测试跨循环调用 wait() 报错。每个测试前重置
    Event 对象, 使其在当前测试的循环中重新绑定。
    """
    from sse_starlette.sse import AppStatus
    AppStatus.should_exit_event = anyio.Event()
    yield


EXPECTED_TOOL_NAMES = {
    "generate_test_case",
    "query_test_case",
    "run_test_case",
    "query_execution_result",
    "query_self_healing_audit",
}


async def _parse_sse_events(resp) -> list[tuple[str, dict]]:
    """解析 SSE 响应流, 返回 [(event_name, data_dict), ...] 列表。

    sse_starlette 输出格式:
        event: <name>
        data: <json>

    空行分隔事件, 本函数按 event:/data: 配对收集。
    """
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                data = {"raw": data_str}
            if current_event is not None:
                events.append((current_event, data))
                current_event = None
    return events


# ── 1. GET /mcp/tools 工具列表 ──


class TestListMcpTools:
    async def test_list_tools_success(self, async_auth_client):
        resp = await async_auth_client.get("/api/v1/mcp/tools")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        tools = body["data"]
        names = {t["name"] for t in tools}
        assert EXPECTED_TOOL_NAMES.issubset(names)

    async def test_list_tools_without_auth(self, async_client):
        resp = await async_client.get("/api/v1/mcp/tools")
        assert resp.status_code == 401


# ── 2. POST /mcp/sse SSE 流式调用 ──


class TestCallMcpSse:
    async def test_sse_query_test_case_success(
        self, async_auth_client, async_test_project, async_db,
    ):
        # 准备一条真实 TestCase 供 query_test_case 查询
        tc = TestCase(
            case_no=f"TC-MCP-{uuid.uuid4().hex[:8]}",
            project_id=async_test_project.id,
            module="mcp_test",
            title="MCP 查询用例",
            precondition="无",
            steps_json=[{"step": "1", "action": "click"}],
            expected_result="成功",
            priority=2,
            case_type="UI",
        )
        async_db.add(tc)
        await async_db.flush()
        await async_db.refresh(tc)

        async with async_auth_client.stream(
            "POST",
            "/api/v1/mcp/sse",
            json={
                "tool_name": "query_test_case",
                "arguments": {"test_case_id": tc.id},
            },
        ) as resp:
            assert resp.status_code == 200
            events = await _parse_sse_events(resp)

        event_names = [e[0] for e in events]
        assert "start" in event_names
        assert "progress" in event_names
        assert "result" in event_names

        start_events = [e for e in events if e[0] == "start"]
        assert start_events[0][1]["tool_name"] == "query_test_case"

        result_events = [e for e in events if e[0] == "result"]
        assert "test_case" in result_events[0][1]
        assert result_events[0][1]["test_case"]["id"] == tc.id

    async def test_sse_query_test_case_not_found(self, async_auth_client):
        async with async_auth_client.stream(
            "POST",
            "/api/v1/mcp/sse",
            json={
                "tool_name": "query_test_case",
                "arguments": {"test_case_id": 999999},
            },
        ) as resp:
            assert resp.status_code == 200
            events = await _parse_sse_events(resp)

        result_events = [e for e in events if e[0] == "result"]
        assert result_events
        assert result_events[0][1]["test_case"] is None

    async def test_sse_query_test_case_forbidden_idor(
        self, async_auth_client, async_db,
    ):
        # 创建另一用户的项目与用例，验证 handler 项目归属校验阻断越权查询
        import uuid
        from app.models.user import User
        from app.models.project import Project
        from app.utils.jwt_utils import get_password_hash
        suffix = uuid.uuid4().hex[:8]
        other = User(
            username=f"mcp_other_{suffix}", email=f"mcp_other_{suffix}@test.com",
            password_hash=get_password_hash("Other@123456"),
            is_active=True, is_superuser=False,
        )
        async_db.add(other)
        await async_db.flush()
        other_project = Project(
            name=f"mcp_other_project_{suffix}", user_id=other.id,
            description="other", status=1, project_type="web",
        )
        async_db.add(other_project)
        await async_db.flush()
        tc = TestCase(
            case_no=f"TC-IDOR-{suffix[:8]}", project_id=other_project.id,
            module="mcp_idor", title="other user case", precondition="无",
            steps_json=[{"step": "1", "action": "click"}],
            expected_result="成功", priority=2, case_type="UI",
        )
        async_db.add(tc)
        await async_db.flush()
        await async_db.refresh(tc)

        async with async_auth_client.stream(
            "POST", "/api/v1/mcp/sse",
            json={
                "tool_name": "query_test_case",
                "arguments": {"test_case_id": tc.id},
            },
        ) as resp:
            assert resp.status_code == 200
            events = await _parse_sse_events(resp)

        event_names = [e[0] for e in events]
        assert "error" in event_names

    async def test_sse_unknown_tool(self, async_auth_client):
        async with async_auth_client.stream(
            "POST",
            "/api/v1/mcp/sse",
            json={"tool_name": "unknown_tool", "arguments": {}},
        ) as resp:
            assert resp.status_code == 200
            events = await _parse_sse_events(resp)

        event_names = [e[0] for e in events]
        assert "error" in event_names

    async def test_sse_without_auth(self, async_client):
        resp = await async_client.post(
            "/api/v1/mcp/sse",
            json={
                "tool_name": "query_test_case",
                "arguments": {"test_case_id": 1},
            },
        )
        assert resp.status_code == 401
