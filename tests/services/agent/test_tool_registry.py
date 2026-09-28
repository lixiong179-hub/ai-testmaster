"""ToolRegistry 与内置工具单元测试。

覆盖 10 个用例：
    1. register(agent_types=["test"]) → list_for_agent("test") 含该工具
    2. register(agent_types=None) → 所有 agent_type 可见
    3. register(agent_types=["test"]) → list_for_agent("other") 不含
    4. get(tool_name) → 返回 Tool 实例
    5. get(unknown_name) → 返回 None
    6. enable/disable → list_for_agent 反映状态
    7. is_client_side 属性（客户端 True / 服务端 False）
    8. 内置 5 个服务端工具全部能注册并实例化
    9. 内置 6 个客户端工具全部能注册并实例化
    10. 客户端工具无 execution_callback → 返回 ToolResult(success=False)

测试原则：纯内存操作，无需数据库。
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from app.services.agent.agents._test_case_tools import ValidateTestCaseSyntaxTool
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult
from app.services.agent.tools.client_tools import (
    ClickElementTool,
    GetDomTool,
    InputElementTool,
    ScreenshotTool,
    ScrollTool,
    WaitTool,
)
from app.services.agent.tools.registry import ToolRegistry
from app.services.agent.tools.server_tools import (
    GetTestCaseTool,
    QueryAuditTool,
    QueryLocatorHistoryTool,
    QueryProjectTool,
)


# ── 测试用工具 ──


class _DummyTool(Tool):
    """用于基础注册/路由测试的占位工具。"""

    name = "dummy_tool"
    description = "dummy tool for testing"
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        return ToolResult(success=True)


# ── 用例 1-3：register 与 agent_types 路由 ──


def test_register_with_agent_types_then_listed_for_agent() -> None:
    """用例1: register(agent_types=["test"]) → list_for_agent("test") 含该工具。"""
    registry = ToolRegistry()
    registry.register(_DummyTool(), agent_types=["test_agent"])
    tools = registry.list_for_agent("test_agent")
    assert any(t.name == "dummy_tool" for t in tools)


def test_register_with_none_agent_types_visible_to_all() -> None:
    """用例2: register(agent_types=None) → 所有 agent_type 可见。"""
    registry = ToolRegistry()
    registry.register(_DummyTool(), agent_types=None)
    tools_a = registry.list_for_agent("test_agent")
    tools_b = registry.list_for_agent("other_agent")
    assert any(t.name == "dummy_tool" for t in tools_a)
    assert any(t.name == "dummy_tool" for t in tools_b)


def test_register_with_agent_types_excludes_other_agents() -> None:
    """用例3: register(agent_types=["test"]) → list_for_agent("other") 不含。"""
    registry = ToolRegistry()
    registry.register(_DummyTool(), agent_types=["test_agent"])
    tools = registry.list_for_agent("other_agent")
    assert not any(t.name == "dummy_tool" for t in tools)


# ── 用例 4-5：get 查询 ──


def test_get_returns_tool_instance() -> None:
    """用例4: get(tool_name) → 返回 Tool 实例。"""
    registry = ToolRegistry()
    tool = _DummyTool()
    registry.register(tool)
    fetched = registry.get("dummy_tool")
    assert fetched is tool
    assert isinstance(fetched, _DummyTool)


def test_get_unknown_returns_none() -> None:
    """用例5: get(unknown_name) → 返回 None。"""
    registry = ToolRegistry()
    assert registry.get("unknown") is None


# ── 用例 6：enable / disable ──


def test_disable_enable_reflected_in_list_for_agent() -> None:
    """用例6: disable → list_for_agent 排除；enable → 恢复。"""
    registry = ToolRegistry()
    registry.register(_DummyTool(), agent_types=["test_agent"])
    # disable 后不可见
    registry.disable("dummy_tool")
    assert registry.is_disabled("dummy_tool") is True
    assert not any(t.name == "dummy_tool" for t in registry.list_for_agent("test_agent"))
    # enable 后恢复
    registry.enable("dummy_tool")
    assert registry.is_disabled("dummy_tool") is False
    assert any(t.name == "dummy_tool" for t in registry.list_for_agent("test_agent"))


# ── 用例 7：is_client_side 属性 ──


def test_is_client_side_attribute() -> None:
    """用例7: 客户端工具 is_client_side=True，服务端工具 is_client_side=False。"""
    client_tool = ClickElementTool()
    server_tool = GetTestCaseTool()
    assert client_tool.is_client_side is True
    assert server_tool.is_client_side is False
    # 全部客户端工具
    for tool_cls in [ClickElementTool, InputElementTool, ScreenshotTool, GetDomTool, ScrollTool, WaitTool]:
        assert tool_cls().is_client_side is True
    # 全部服务端工具
    for tool_cls in [GetTestCaseTool, QueryProjectTool, QueryAuditTool, QueryLocatorHistoryTool, ValidateTestCaseSyntaxTool]:
        assert tool_cls().is_client_side is False


# ── 用例 8-9：内置工具注册 ──


def test_all_server_tools_can_register_and_instantiate() -> None:
    """用例8: 内置 5 个服务端工具（4 server_tools + ValidateTestCaseSyntaxTool）全部能注册。"""
    server_tools = [
        GetTestCaseTool(),
        QueryProjectTool(),
        QueryAuditTool(),
        QueryLocatorHistoryTool(),
        ValidateTestCaseSyntaxTool(),
    ]
    registry = ToolRegistry()
    for tool in server_tools:
        registry.register(tool)
    # 验证全部注册成功
    for tool in server_tools:
        assert registry.get(tool.name) is tool
    # list_for_agent 返回所有（agent_types=None 全局可见）
    listed_names = {t.name for t in registry.list_for_agent("any_agent")}
    expected_names = {
        "get_test_case", "query_project", "query_audit", "query_locator_history",
        "validate_test_case_syntax",
    }
    assert expected_names.issubset(listed_names)
    # 列表已按 name 字典序排序
    names = [t.name for t in registry.list_for_agent("any_agent")]
    assert names == sorted(names)


def test_all_client_tools_can_register_and_instantiate() -> None:
    """用例9: 内置 6 个客户端工具全部能注册并实例化。"""
    client_tools = [
        ClickElementTool(),
        InputElementTool(),
        ScreenshotTool(),
        GetDomTool(),
        ScrollTool(),
        WaitTool(),
    ]
    registry = ToolRegistry()
    for tool in client_tools:
        registry.register(tool)
    for tool in client_tools:
        assert registry.get(tool.name) is tool
    listed_names = {t.name for t in registry.list_for_agent("any")}
    expected_names = {
        "click_element", "input_element", "screenshot",
        "get_dom", "scroll", "wait",
    }
    assert expected_names.issubset(listed_names)


# ── 用例 10：客户端工具无 execution_callback ──


async def test_client_tool_without_callback_returns_failure() -> None:
    """用例10: 客户端工具无 execution_callback → 返回 ToolResult(success=False)。"""
    tool = ClickElementTool()
    context = ToolContext(execution_callback=None)
    result = await tool.execute({"selector": "#btn"}, context)
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert result.error is not None
    assert "execution_callback" in result.error


# ── 附加边界用例：重复注册抛 ValueError ──


def test_register_duplicate_raises_value_error() -> None:
    """边界用例: 重复注册同一 tool_name 抛 ValueError。"""
    registry = ToolRegistry()
    registry.register(_DummyTool())
    with pytest.raises(ValueError):
        registry.register(_DummyTool())


# ── 附加边界用例：name 为空抛 ValueError ──


def test_register_empty_name_raises_value_error() -> None:
    """边界用例: tool.name 为空抛 ValueError。"""

    class _NoNameTool(Tool):
        name = ""
        description = "no name"
        parameters_schema = {"type": "object", "properties": {}, "required": []}

        async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
            return ToolResult(success=True)

    registry = ToolRegistry()
    with pytest.raises(ValueError):
        registry.register(_NoNameTool())


# ── 附加边界用例：disable 未知工具不抛错 ──


def test_disable_unknown_tool_is_noop() -> None:
    """边界用例: disable 不存在的工具名不应抛错（仅对已注册工具标记禁用）。"""
    registry = ToolRegistry()
    # 源码实现：disable 内部判断 `if tool_name in self._tools` 才加入 _disabled，
    # 因此对未注册工具调用 disable 是真正的 no-op，不会标记为已禁用。
    registry.disable("non_existent")  # 不抛异常
    assert registry.is_disabled("non_existent") is False
    # list_for_agent 不会返回（因为本身就没注册）
    assert registry.list_for_agent("any") == []


# ── 附加边界用例：客户端工具 callback 返回非 ToolResult ──


async def test_client_tool_callback_returns_non_tool_result() -> None:
    """边界用例: execution_callback 返回非 ToolResult → ToolResult(success=False)。"""

    async def _bad_callback(tool_name: str, params: Dict[str, Any]) -> str:
        return "not a tool result"

    tool = ClickElementTool()
    context = ToolContext(execution_callback=_bad_callback)
    result = await tool.execute({"selector": "#btn"}, context)
    assert result.success is False
    assert "类型错误" in result.error
