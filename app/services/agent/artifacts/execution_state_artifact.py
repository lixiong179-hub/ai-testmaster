"""执行状态 Artifact。

承载测试执行引擎的当前状态，用于 FailureAnalysisAgent 在失败自愈场景
感知「执行到哪一步、报什么错、有无截图」。
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, Optional

from pydantic import Field

from app.services.agent.artifacts.base import Artifact


class ExecutionStateArtifact(Artifact):
    """执行状态 Artifact。

    Attributes:
        current_step: 当前执行步骤的描述（如 "click login button"）。
        last_error: 最近一次错误的详细信息（异常类型 + message）。
        screenshot_url: 失败时截图的对象存储 URL。
        timestamp: 状态采集时间（UTC）。
    """

    artifact_type: ClassVar[str] = "execution_state"
    description: ClassVar[str] = "测试执行状态，含当前步骤、错误信息、截图"

    current_step: Optional[str] = None
    last_error: Optional[str] = None
    screenshot_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


__all__ = ["ExecutionStateArtifact"]
