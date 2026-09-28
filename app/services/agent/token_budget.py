"""Agent 场景 Token 预算守卫。

继承 BaseTokenBudgetGuard 的通用 Redis 累计 + 内存降级逻辑，
按 agent_type + project_id 隔离 Redis key，实现单 Agent 单项目的独立预算。

Redis key 约定：
    counter_key = f"agent:token:{agent_type}:{project_id}:{YYYYMMDD}"
    marker_key  = f"agent:token:{agent_type}:{project_id}:{YYYYMMDD}:marker"

隔离原因：
    不同 Agent 类型（test_generation / failure_analysis）的调用频次与成本
    差异巨大，若共用 key 会导致低频 Agent 被高频 Agent 饿死。按项目隔离
    则防止单项目异常消耗拖垮其他项目。
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.services.common.token_budget import BaseTokenBudgetGuard

# Agent Token 计数 Redis key 前缀模板，{agent_type}/{project_id} 在构造时填充
_AGENT_TOKEN_NAMESPACE_TEMPLATE = "agent:token:{agent_type}:{project_id}:"


class AgentTokenBudgetGuard(BaseTokenBudgetGuard):
    """Agent Token 预算守卫，按 agent_type + project_id 隔离。

    继承 BaseTokenBudgetGuard 的 consume / _get_consumed 通用实现，
    仅实现 check_single_call / is_daily_budget_exhausted 以绑定 Agent 配置项。

    使用方式：
        guard = AgentTokenBudgetGuard(
            redis_client=redis_client,
            agent_type="test_generation",
            project_id=1,
        )
        if guard.check_single_call(estimate):
            raise TokenBudgetExceeded(...)
        guard.consume(actual_cost)
        if guard.is_daily_budget_exhausted():
            # 拒绝新会话创建
            ...
    """

    def __init__(
        self,
        redis_client: Optional[Any],
        *,
        agent_type: str,
        project_id: int,
    ) -> None:
        """注入 Redis 客户端与隔离维度。

        Args:
            redis_client: 同步 redis.Redis 实例；为 None 时走内存降级。
            agent_type: Agent 类型标识（test_generation/failure_analysis/...）。
            project_id: 项目 ID，与 agent_type 一起构成隔离维度。
        """
        namespace = _AGENT_TOKEN_NAMESPACE_TEMPLATE.format(
            agent_type=agent_type,
            project_id=project_id,
        )
        super().__init__(redis_client=redis_client, namespace=namespace)
        self._agent_type = agent_type
        self._project_id = project_id

    def check_single_call(self, token_estimate: int) -> bool:
        """校验单次 Token 预估是否超 AI_AGENT_TOKEN_LIMIT。

        Args:
            token_estimate: 单轮迭代预估 Token 消耗。

        Returns:
            bool: True 表示预估超限，应熔断本轮迭代。
        """
        return token_estimate > settings.AI_AGENT_TOKEN_LIMIT

    def is_daily_budget_exhausted(self) -> bool:
        """判断当日累计消耗是否超 AI_AGENT_DAILY_TOKEN_BUDGET。

        Returns:
            bool: True 表示日预算已耗尽，应拒绝新会话创建。
        """
        consumed = self._get_consumed()
        return consumed >= settings.AI_AGENT_DAILY_TOKEN_BUDGET


__all__ = ["AgentTokenBudgetGuard"]
