"""Tool 抽象基类与 ToolResult 数据结构。

设计目的：
    Agent 通过 function calling 调用工具，工具分为两类：
        - 服务端工具（is_client_side=False）：AgentRuntime 直接 await execute，
          如查询数据库、调用业务服务
        - 客户端工具（is_client_side=True）：通过 execution_callback 回调
          测试执行引擎执行（如 click/input/screenshot），结果返回后再进入下一轮

设计原则：
    - 自描述：每个工具携带 name / description / parameters_schema（JSON Schema）
    - 统一返回：ToolResult.success / output / error / metadata
    - 上下文注入：execute 接收 ToolContext，包含 db / session_id / agent_type / user_id
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolContext:
    """工具执行上下文。

    由 AgentRuntime 在每轮迭代中构造并注入到 Tool.execute。

    Attributes:
        db: 异步数据库会话，服务端工具用于查询/写入。
        session_id: 当前 Agent 会话 ID，用于审计与日志关联。
        agent_type: 当前 Agent 类型标识。
        user_id: 触发会话的用户 ID，用于权限校验。
        project_id: 当前项目 ID，用于数据隔离。
        execution_callback: 客户端工具执行回调，签名 async (tool_name, params) -> ToolResult；
            None 表示无客户端工具调用场景。
    """

    db: Optional["AsyncSession"] = None
    session_id: Optional[int] = None
    agent_type: str = ""
    user_id: Optional[int] = None
    project_id: Optional[int] = None
    execution_callback: Optional[Any] = None


@dataclass
class ToolResult:
    """工具执行结果。

    Attributes:
        success: 是否执行成功。
        output: 成功时的输出数据（dict / str / list），将注入到 LLM 下一轮消息。
        error: 失败时的错误信息。
        metadata: 元数据（如耗时、行数），不注入 LLM 但写入审计。
    """

    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """工具抽象基类。

    子类必须覆盖类属性并实现 execute：
        - name: 工具唯一标识，对应 LLM function calling 的 function name
        - description: 工具用途描述，注入 LLM function schema
        - parameters_schema: JSON Schema dict，描述工具参数
        - is_client_side: True 表示客户端工具（需 execution_callback），False 表示服务端工具
    """

    name: str = ""
    description: str = ""
    parameters_schema: Dict[str, Any] = {}
    is_client_side: bool = False

    @abstractmethod
    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        """执行工具。

        Args:
            params: 工具参数，已按 parameters_schema 校验。
            context: 工具执行上下文。

        Returns:
            ToolResult: 执行结果。
        """


__all__ = ["Tool", "ToolContext", "ToolResult"]
