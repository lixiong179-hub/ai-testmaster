"""AgentRuntime 工具调用执行器。

从 runtime.py 拆出，负责单个工具调用的完整生命周期：
    1. 解析 tool_call 参数
    2. 从 ToolRegistry 获取 Tool 实例
    3. 构建 ToolContext
    4. 执行 Tool（区分客户端/服务端）
    5. 记录 tool 消息到会话历史
    6. 记录审计 + 熔断器反馈 + metrics 埋点

抽出目的：
    runtime.py 单文件 ≤350 行约束 + 工具执行逻辑高内聚。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.services.agent.exceptions import ToolExecutionError
from app.services.agent.tools.base_tool import ToolContext, ToolResult


async def execute_tool_call(
    *,
    tool_call: Dict[str, Any],
    session_id: Optional[int],
    iteration: int,
    agent_type: str,
    project_id: int,
    execution_callback: Optional[Any],
    history: List[Dict[str, Any]],
    db: Optional[Any],
    tool_registry: Optional[Any],
    audit_service: Optional[Any],
    circuit_breaker: Optional[Any],
    metrics: Optional[Any],
    append_message_fn: Any,
) -> None:
    """执行单个 tool_call 的完整流程。

    Args:
        tool_call: LLM 返回的工具调用字典，含 id/function.name/function.arguments。
        session_id: 当前 AgentSession.id（降级模式可能为 None）。
        iteration: 当前迭代轮次（用于审计）。
        agent_type: Agent 类型标识（用于熔断器与 metrics 标签）。
        project_id: 项目 ID（注入 ToolContext）。
        execution_callback: 客户端工具回调函数。
        history: 当前会话消息历史列表（追加 tool 消息）。
        db: AsyncSession 实例（注入 ToolContext）。
        tool_registry: ToolRegistry 实例（必填，否则抛 ToolExecutionError）。
        audit_service: AgentAuditService 实例（可选，None 时不记录审计）。
        circuit_breaker: CircuitBreaker 实例（可选，None 时不反馈）。
        metrics: AgentMetrics 实例（可选，None 时不埋点）。
        append_message_fn: 消息追加回调，签名 async (session_id, role, content, tool_name, tool_call_id, token_cost) -> None。

    Raises:
        ToolExecutionError: 参数解析失败 / 工具未注册 / 工具执行异常。
    """
    tool_name = tool_call["function"]["name"]
    try:
        args = json.loads(tool_call["function"].get("arguments") or "{}")
    except json.JSONDecodeError as e:
        raise ToolExecutionError(
            f"工具参数解析失败: {tool_name}: {e}",
            tool_name=tool_name, agent_type=agent_type, session_id=session_id,
        ) from e

    if tool_registry is None:
        raise ToolExecutionError(
            f"工具注册表不可用: {tool_name}",
            tool_name=tool_name, agent_type=agent_type, session_id=session_id,
        )
    tool = tool_registry.get(tool_name)
    if tool is None:
        raise ToolExecutionError(
            f"工具未注册: {tool_name}",
            tool_name=tool_name, agent_type=agent_type, session_id=session_id,
        )

    context = ToolContext(
        db=db, session_id=session_id, agent_type=agent_type,
        project_id=project_id, execution_callback=execution_callback,
    )
    try:
        result: ToolResult = await tool.execute(args, context)
    except NotImplementedError as e:
        _record_tool_call(metrics, tool_name, False)
        raise ToolExecutionError(
            f"工具未实现: {tool_name}: {e}",
            tool_name=tool_name, agent_type=agent_type, session_id=session_id,
        ) from e
    except Exception as e:
        _record_tool_call(metrics, tool_name, False)
        raise ToolExecutionError(
            f"工具执行失败: {tool_name}: {e}",
            tool_name=tool_name, agent_type=agent_type, session_id=session_id,
        ) from e

    _record_tool_call(metrics, tool_name, result.success)

    tool_msg = {
        "tool_call_id": tool_call.get("id"),
        "tool_result": {
            "success": result.success,
            "output": result.output,
            "error": result.error,
        },
    }
    await append_message_fn(
        session_id, "tool", tool_msg,
        tool_name=tool_name, tool_call_id=tool_call.get("id"),
    )
    history.append({"role": "tool", "content": tool_msg})
    if audit_service is not None:
        await audit_service.record_action(
            session_id=session_id, iteration=iteration,
            action_type="tool_call",
            action_detail={"tool_name": tool_name, "args": args, "result": tool_msg["tool_result"]},
            decision_confidence=None,
        )
    if circuit_breaker is not None:
        if result.success:
            await circuit_breaker.record_success(agent_type)
        else:
            await circuit_breaker.record_failure(agent_type)


def _record_tool_call(metrics: Optional[Any], tool_name: str, success: bool) -> None:
    """埋点工具调用结果（吞异常，不阻断主流程）。"""
    if metrics is None:
        return
    try:
        metrics.record_tool_call(tool_name, success)
    except Exception:
        pass


__all__ = ["execute_tool_call"]
