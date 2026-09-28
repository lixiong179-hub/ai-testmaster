"""AgentRuntime - Agent 执行引擎。

统一处理「初始化上下文 / 注册工具 / 生成 prompt / 多轮 function calling 循环 /
返回结果」。新增 Agent 仅需定义 system_prompt + 工具集，通过 AgentRegistry 注册
后即可被 Runtime 调用。

设计原则：
    - 依赖注入：10 个依赖通过构造函数注入，Optional 依赖为 None 时降级
    - 终止条件：final_answer 工具调用 / max_iterations 触达 / 异常熔断

循环流程：熔断器检查 → 创建会话 → 迭代（max_iterations 检查 / 循环检测 /
Token 预算检查 / 构建 prompt / 调用 LLM / 执行工具 / 记录消息与审计 / 检查终止）
→ complete_session + metrics 埋点。
"""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.models.agent_session import AgentSession
from app.services.agent._tool_executor import execute_tool_call as _execute_tool_call
from app.services.agent.artifacts.base import Artifact
from app.services.agent.base import AgentDefinition
from app.services.agent.exceptions import (
    AgentError,
    AgentLoopDetected,
    CircuitBreakerOpen,
    MaxIterationsExceeded,
    TokenBudgetExceeded,
)
from app.services.agent.registry import get_global_registry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AgentRuntime:
    """Agent 执行引擎。

    所有依赖通过构造函数注入，Optional 依赖为 None 时降级，保证最小可用循环。
    """

    def __init__(
        self,
        db: Optional["AsyncSession"] = None,
        *,
        llm_provider: Optional[Any] = None,
        token_guard: Optional[Any] = None,
        loop_detector: Optional[Any] = None,
        circuit_breaker: Optional[Any] = None,
        audit_service: Optional[Any] = None,
        session_service: Optional[Any] = None,
        artifact_registry: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        agent_registry: Optional[Any] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        self.db = db
        self.llm_provider = llm_provider
        self.token_guard = token_guard
        self.loop_detector = loop_detector
        self.circuit_breaker = circuit_breaker
        self.audit_service = audit_service
        self.session_service = session_service
        self.artifact_registry = artifact_registry
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry or get_global_registry()
        self.metrics = metrics

    async def run(
        self,
        agent_type: str,
        project_id: int,
        initial_artifacts: List[Artifact],
        execution_callback: Optional[Any] = None,
        created_by: Optional[int] = None,
    ) -> AgentSession:
        """执行 Agent 会话。

        Args:
            agent_type: Agent 类型标识，必须已注册。
            project_id: 项目 ID。
            initial_artifacts: 初始上下文 artifacts。
            execution_callback: 客户端工具执行回调。
            created_by: 触发会话的用户 ID。

        Returns:
            AgentSession: 会话最终状态记录。
        """
        definition = self.agent_registry.get_or_raise(agent_type)
        await self._check_circuit_breaker(agent_type)
        await self._check_token_budget(agent_type, project_id)

        session = await self._create_session(agent_type, project_id, created_by)
        max_iterations = definition.max_iterations or settings.AI_AGENT_MAX_ITERATIONS
        start_time = time.monotonic()
        self._safe(lambda m: m.record_session_start(agent_type))

        try:
            history: List[Dict[str, Any]] = []
            for iteration in range(1, max_iterations + 1):
                iter_start = time.monotonic()
                await self._check_loop(agent_type, session.id, iteration, history)
                messages = self._build_messages(definition, initial_artifacts, history)
                llm_resp = await self._invoke_llm(messages, definition)
                assistant_msg = self._parse_assistant_message(llm_resp)
                await self._append_message(
                    session.id, "assistant", assistant_msg,
                    tool_name=assistant_msg.get("tool_name"),
                    token_cost=llm_resp.get("token_cost", 0),
                )
                history.append({"role": "assistant", "content": assistant_msg})
                self._consume_token(agent_type, project_id, llm_resp.get("token_cost", 0))
                session.token_cost = (session.token_cost or 0) + llm_resp.get("token_cost", 0)
                session.iteration_count = iteration
                self._safe(lambda m: m.record_iteration(agent_type, time.monotonic() - iter_start))

                tool_calls = assistant_msg.get("tool_calls", []) or []
                if not tool_calls:
                    break
                for tc in tool_calls:
                    await _execute_tool_call(
                        tool_call=tc, session_id=session.id, iteration=iteration,
                        agent_type=agent_type, project_id=project_id,
                        execution_callback=execution_callback, history=history,
                        db=self.db, tool_registry=self.tool_registry,
                        audit_service=self.audit_service,
                        circuit_breaker=self.circuit_breaker,
                        metrics=self.metrics,
                        append_message_fn=self._append_message,
                    )
                if self._check_termination(assistant_msg):
                    break
            else:
                raise MaxIterationsExceeded(
                    f"迭代次数触达上限: {max_iterations}",
                    agent_type=agent_type, session_id=session.id,
                )

            await self._complete_session(session, "completed")
            self._record_session_end(agent_type, "completed", session, start_time)
            return session
        except AgentLoopDetected:
            await self._complete_session(session, "loop_detected")
            self._record_session_end(agent_type, "loop_detected", session, start_time)
            raise
        except TokenBudgetExceeded:
            await self._complete_session(session, "token_exhausted")
            self._record_session_end(agent_type, "token_exhausted", session, start_time)
            raise
        except AgentError:
            await self._complete_session(session, "failed")
            self._record_session_end(agent_type, "failed", session, start_time)
            raise
        except Exception as e:
            logger.exception(f"AgentRuntime 未预期异常: {e}")
            await self._complete_session(session, "failed")
            self._record_session_end(agent_type, "failed", session, start_time)
            raise AgentError(str(e), agent_type=agent_type, session_id=session.id) from e

    # ── 内部方法 ──
    async def _check_circuit_breaker(self, agent_type: str) -> None:
        if self.circuit_breaker is None:
            return
        allowed = await self.circuit_breaker.allow(agent_type)
        if not allowed:
            self._safe(lambda m: m.record_circuit_breaker_state(agent_type, "open"))
            raise CircuitBreakerOpen(
                f"熔断器开启: {agent_type}", agent_type=agent_type,
            )

    async def _check_token_budget(self, agent_type: str, project_id: int) -> None:
        if self.token_guard is not None and self.token_guard.is_daily_budget_exhausted():
            raise TokenBudgetExceeded(
                f"日预算耗尽: {agent_type}/{project_id}",
                agent_type=agent_type,
            )

    async def _create_session(
        self, agent_type: str, project_id: int, created_by: Optional[int],
    ) -> AgentSession:
        if self.session_service is not None:
            return await self.session_service.create_session(
                agent_type=agent_type, project_id=project_id, created_by=created_by,
            )
        return AgentSession(
            project_id=project_id, agent_type=agent_type, status="running",
            token_cost=0, iteration_count=0, loop_detected=False, created_by=created_by,
        )

    async def _check_loop(
        self, agent_type: str, session_id: Optional[int],
        iteration: int, history: List[Dict[str, Any]],
    ) -> None:
        """循环检测：基于最近工具调用签名判重，超阈值抛 AgentLoopDetected。"""
        if self.loop_detector is None:
            return
        last_msg = next((m for m in reversed(history) if m["role"] == "assistant"), None)
        if not last_msg:
            return
        tool_calls = (last_msg["content"] or {}).get("tool_calls", []) or []
        for tc in tool_calls:
            tool_name = tc.get("function", {}).get("name", "")
            try:
                args = json.loads(tc.get("function", {}).get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            signature = self.loop_detector._build_signature(tool_name, args)
            detected = await self.loop_detector.check(
                agent_type=agent_type, session_id=session_id,
                tool_call_signature=signature,
            )
            if detected:
                self._safe(lambda m: m.record_loop_detected(agent_type))
                raise AgentLoopDetected(
                    f"检测到循环: {agent_type}", agent_type=agent_type, session_id=session_id,
                )

    def _build_messages(
        self, definition: AgentDefinition, artifacts: List[Artifact],
        history: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        system_prompt = self._build_system_prompt(definition, artifacts, history)
        history_limit = settings.AI_AGENT_HISTORY_MESSAGE_COUNT
        recent = history[-history_limit:]
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.extend({
            "role": m["role"],
            "content": json.dumps(m["content"], ensure_ascii=False, default=str),
        } for m in recent)
        return messages

    def _build_system_prompt(
        self, definition: AgentDefinition, artifacts: List[Artifact],
        history: List[Dict[str, Any]],
    ) -> str:
        parts = [definition.system_prompt]
        if self.artifact_registry is not None:
            index_prompt = self.artifact_registry.build_artifacts_index_prompt()
            if index_prompt:
                parts.append(index_prompt)
        if artifacts:
            parts.append("# Current Artifacts")
            for a in artifacts:
                parts.append(a.to_prompt_section())
        if history:
            parts.append(f"# History (recent {len(history)} messages omitted in prompt, see messages)")
        return "\n\n".join(parts)

    async def _invoke_llm(
        self, messages: List[Dict[str, Any]], definition: AgentDefinition,
    ) -> Dict[str, Any]:
        if self.llm_provider is None:
            return {"content": "LLM provider 不可用", "tool_calls": [], "token_cost": 0}
        tools = self._build_tools_schema(definition)
        return await self.llm_provider.complete(messages=messages, tools=tools)

    def _build_tools_schema(self, definition: AgentDefinition) -> List[Dict[str, Any]]:
        if self.tool_registry is None:
            return []
        schema = []
        for tool in self.tool_registry.list_for_agent(definition.agent_type):
            schema.append({
                "type": "function",
                "function": {
                    "name": tool.name, "description": tool.description,
                    "parameters": tool.parameters_schema,
                },
            })
        return schema

    def _parse_assistant_message(self, llm_resp: Dict[str, Any]) -> Dict[str, Any]:
        tool_calls = llm_resp.get("tool_calls", []) or []
        return {
            "text": llm_resp.get("content", ""),
            "tool_calls": tool_calls,
            "tool_name": tool_calls[0]["function"]["name"] if tool_calls else None,
        }

    async def _append_message(
        self, session_id: Optional[int], role: str, content: Dict[str, Any],
        tool_name: Optional[str] = None, tool_call_id: Optional[str] = None,
        token_cost: int = 0,
    ) -> None:
        if self.session_service is None:
            return
        await self.session_service.append_message(
            session_id=session_id, role=role, content=content,
            tool_name=tool_name, tool_call_id=tool_call_id, token_cost=token_cost,
        )

    def _consume_token(self, agent_type: str, project_id: int, amount: int) -> None:
        if self.token_guard is not None and amount > 0:
            self.token_guard.consume(amount)

    def _check_termination(self, assistant_msg: Dict[str, Any]) -> bool:
        tool_calls = assistant_msg.get("tool_calls", []) or []
        if not tool_calls:
            return True
        return any(
            tc.get("function", {}).get("name") == "final_answer"
            for tc in tool_calls
        )

    async def _complete_session(self, session: AgentSession, status: str) -> None:
        session.status = status
        if status == "loop_detected":
            session.loop_detected = True
        if self.session_service is not None:
            await self.session_service.complete_session(
                session_id=session.id, status=status,
                token_cost=session.token_cost,
                iteration_count=session.iteration_count,
                loop_detected=session.loop_detected,
            )

    def _safe(self, fn: Any) -> None:
        """安全执行 metrics 埋点调用，吞掉异常不阻断主流程。"""
        if self.metrics is None:
            return
        try:
            fn(self.metrics)
        except Exception as e:
            logger.warning(f"metrics 埋点失败: {e}")

    def _record_session_end(
        self, agent_type: str, status: str,
        session: AgentSession, start_time: float,
    ) -> None:
        """会话结束埋点：sessions_total{status} + active_sessions-1 + 时长与 token 观察。"""
        if self.metrics is None:
            return
        duration = time.monotonic() - start_time
        self._safe(lambda m: m.record_session_end(
            agent_type, status, duration, session.token_cost or 0,
        ))


__all__ = ["AgentRuntime"]
