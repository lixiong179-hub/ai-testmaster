"""Agent 注册表。

设计目的：
    AgentRuntime.run(agent_type) 需要按 agent_type 路由到对应的 AgentDefinition
    （system_prompt / tools / max_iterations 等）。AgentRegistry 作为运行时注册
    中心，支持 register / get / list / enable / disable 操作，新增 Agent 仅需
    注册 definition 即可被 Runtime 调用，无需修改 Runtime 代码。

设计原则：
    - 单例：全进程共享一个 AgentRegistry 实例，避免多实例状态不一致
    - 线程安全：register / disable / enable 写操作加锁，get / list 读操作无锁
      （CPython GIL 保证读 dict 原子性，写锁防止并发 register 覆盖）
    - 启用/禁用：disabled 的 Agent 不被 Runtime 接受，用于运维降级
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional

from app.services.agent.base import AgentDefinition
from app.services.agent.exceptions import AgentError


class AgentRegistry:
    """Agent 注册表单例。

    使用方式：
        registry = AgentRegistry()
        registry.register(AgentDefinition(agent_type="test_generation", ...))
        definition = registry.get("test_generation")
        all_agents = registry.list_agents()
        registry.disable("test_generation")
    """

    def __init__(self) -> None:
        self._definitions: Dict[str, AgentDefinition] = {}
        self._disabled: set[str] = set()
        self._lock = threading.Lock()

    def register(self, definition: AgentDefinition) -> None:
        """注册 Agent 定义。

        重复注册同一 agent_type 会覆盖旧定义，用于热更新场景。

        Args:
            definition: Agent 配置定义，agent_type 必须非空。
        """
        if not definition.agent_type:
            raise AgentError("AgentDefinition.agent_type 不能为空")
        with self._lock:
            self._definitions[definition.agent_type] = definition
            # 注册后默认从 disabled 集合移除，确保重新注册的 Agent 可用
            self._disabled.discard(definition.agent_type)

    def get(self, agent_type: str) -> Optional[AgentDefinition]:
        """查询 Agent 定义。

        Args:
            agent_type: Agent 类型标识。

        Returns:
            AgentDefinition 或 None（未注册时）。
        """
        return self._definitions.get(agent_type)

    def get_or_raise(self, agent_type: str) -> AgentDefinition:
        """查询 Agent 定义，未注册或已禁用时抛异常。

        Args:
            agent_type: Agent 类型标识。

        Returns:
            AgentDefinition。

        Raises:
            AgentError: 未注册或已禁用。
        """
        definition = self._definitions.get(agent_type)
        if definition is None:
            raise AgentError(
                f"Agent 类型未注册: {agent_type}",
                agent_type=agent_type,
            )
        if agent_type in self._disabled:
            raise AgentError(
                f"Agent 类型已禁用: {agent_type}",
                agent_type=agent_type,
            )
        return definition

    def list_agents(self, include_disabled: bool = False) -> List[AgentDefinition]:
        """列出所有已注册 Agent。

        Args:
            include_disabled: 是否包含已禁用的 Agent，默认 False 仅返回启用中的。

        Returns:
            List[AgentDefinition]: 已注册 Agent 定义列表，按 agent_type 字典序排序。
        """
        items = []
        for agent_type, definition in self._definitions.items():
            if not include_disabled and agent_type in self._disabled:
                continue
            items.append(definition)
        return sorted(items, key=lambda d: d.agent_type)

    def disable(self, agent_type: str) -> None:
        """禁用指定 Agent 类型，Runtime 将拒绝新会话创建。

        Args:
            agent_type: Agent 类型标识。
        """
        with self._lock:
            if agent_type in self._definitions:
                self._disabled.add(agent_type)

    def enable(self, agent_type: str) -> None:
        """启用指定 Agent 类型。

        Args:
            agent_type: Agent 类型标识。
        """
        with self._lock:
            self._disabled.discard(agent_type)

    def is_disabled(self, agent_type: str) -> bool:
        """判断 Agent 类型是否被禁用。"""
        return agent_type in self._disabled

    def clear(self) -> None:
        """清空所有注册（仅测试使用，生产不应调用）。"""
        with self._lock:
            self._definitions.clear()
            self._disabled.clear()


# 全局单例：进程内共享，新增 Agent 通过 register 接入
_global_registry: Optional[AgentRegistry] = None
_registry_lock = threading.Lock()


def get_global_registry() -> AgentRegistry:
    """获取全局 AgentRegistry 单例。

    首次调用惰性创建，后续调用返回同一实例，确保全进程一致。
    """
    global _global_registry
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = AgentRegistry()
    return _global_registry


__all__ = ["AgentRegistry", "get_global_registry"]
