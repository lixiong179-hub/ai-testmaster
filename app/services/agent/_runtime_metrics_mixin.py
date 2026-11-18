"""AgentRuntime 的 metrics 埋点混入。

从 `runtime.py` 拆出：R2-1 收口后的 `ruff format` 把 runtime.py 由 352 行折行至
404 行，越过 `tests/services/test_service_refactor.py::TestFileLineLimit` 的
400 行护栏。这里迁出的是与主循环无耦合的埋点方法（调用方须提供 `self.metrics`），
`AgentRuntime` 通过继承获得同名方法，外部 API 与行为均不变。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from app.models.agent_session import AgentSession


class RuntimeMetricsMixin:
    """会话级 metrics 埋点（`self.metrics` 为 None 时静默降级）。"""

    metrics: Any

    def _safe(self, fn: Any) -> None:
        """安全执行 metrics 埋点调用，吞掉异常不阻断主流程。"""
        if self.metrics is None:
            return
        try:
            fn(self.metrics)
        except Exception as e:
            logger.warning(f"metrics 埋点失败: {e}")

    def _record_session_end(
        self,
        agent_type: str,
        status: str,
        session: AgentSession,
        start_time: float,
    ) -> None:
        """会话结束埋点：sessions_total{status} + active_sessions-1 + 时长与 token 观察。"""
        if self.metrics is None:
            return
        duration = time.monotonic() - start_time
        self._safe(
            lambda m: m.record_session_end(
                agent_type,
                status,
                duration,
                session.token_cost or 0,
            )
        )


__all__ = ["RuntimeMetricsMixin"]
