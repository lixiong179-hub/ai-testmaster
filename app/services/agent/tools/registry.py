"""工具注册表。

设计目的：
    ToolRegistry 集中管理所有工具实例，按 agent_type 分组路由，支持运行时
    启用/禁用。AgentRuntime 在每轮迭代中通过 list_for_agent(agent_type)
    获取当前 Agent 可用的工具列表，构造 LLM function calling schema。

设计原则：
    - 按 agent_type 路由：register(tool, agent_types=["test_generation"]) 限定工具生效范围
    - 全局可用：agent_types=None 表示对所有 Agent 可用
    - 启用/禁用：disabled 的工具不被 list_for_agent 返回，用于运维降级
    - 线程安全：写操作加锁，读操作无锁（CPython GIL 保证读 dict 原子性）
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional, Set

from app.services.agent.tools.base_tool import Tool


class ToolRegistry:
    """工具注册表。

    使用方式：
        registry = ToolRegistry()
        registry.register(GetTestCaseTool(), agent_types=["test_generation"])
        registry.register(ClickElementTool())  # 全局可用
        tools = registry.list_for_agent("test_generation")
        tool = registry.get("click_element")
        registry.disable("click_element")
    """

    def __init__(self) -> None:
        # tool_name -> Tool 实例
        self._tools: Dict[str, Tool] = {}
        # tool_name -> 允许使用的 agent_type 集合；None 表示全局可用
        self._agent_scopes: Dict[str, Optional[Set[str]]] = {}
        # 已禁用的 tool_name 集合
        self._disabled: Set[str] = set()
        self._lock = threading.Lock()

    def register(
        self,
        tool: Tool,
        agent_types: Optional[List[str]] = None,
    ) -> None:
        """注册工具。

        Args:
            tool: Tool 实例，name 必须非空。
            agent_types: 允许使用此工具的 agent_type 列表；None 表示全局可用。

        Raises:
            ValueError: tool.name 为空或重复注册。
        """
        if not tool.name:
            raise ValueError(f"Tool 类 {type(tool).__name__} 未覆盖 name 类属性")
        with self._lock:
            if tool.name in self._tools:
                raise ValueError(f"工具 {tool.name} 已注册")
            self._tools[tool.name] = tool
            self._agent_scopes[tool.name] = (
                set(agent_types) if agent_types is not None else None
            )
            self._disabled.discard(tool.name)

    def get(self, tool_name: str) -> Optional[Tool]:
        """查询工具实例。"""
        return self._tools.get(tool_name)

    def list_for_agent(self, agent_type: str) -> List[Tool]:
        """列出指定 Agent 可用的工具。

        过滤规则：
            1. 工具未被禁用
            2. 工具的 agent_scopes 为 None（全局可用）或包含当前 agent_type

        Args:
            agent_type: Agent 类型标识。

        Returns:
            List[Tool]: 可用工具列表，按 name 字典序排序。
        """
        items = []
        for name, tool in self._tools.items():
            if name in self._disabled:
                continue
            scopes = self._agent_scopes.get(name)
            if scopes is None or agent_type in scopes:
                items.append(tool)
        return sorted(items, key=lambda t: t.name)

    def enable(self, tool_name: str) -> None:
        """启用工具。"""
        with self._lock:
            self._disabled.discard(tool_name)

    def disable(self, tool_name: str) -> None:
        """禁用工具，list_for_agent 将不再返回此工具。"""
        with self._lock:
            if tool_name in self._tools:
                self._disabled.add(tool_name)

    def is_disabled(self, tool_name: str) -> bool:
        """判断工具是否被禁用。"""
        return tool_name in self._disabled

    def clear(self) -> None:
        """清空所有注册（仅测试使用）。"""
        with self._lock:
            self._tools.clear()
            self._agent_scopes.clear()
            self._disabled.clear()


__all__ = ["ToolRegistry"]
