"""失败历史 Artifact。

承载最近 N 次同类失败的修复策略与置信度，用于 LocatorHealingAgent 与
FailureAnalysisAgent 跨会话经验复用，避免重复试错。
"""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar, List, Optional

from pydantic import BaseModel, Field

from app.services.agent.artifacts.base import Artifact


class FailureRecord(BaseModel):
    """单条失败记录。

    Attributes:
        failure_type: 失败类型（element_gone/dom_changed/load_delay/env_noise）。
        selector: 失败时的旧选择器。
        healed_selector: 自愈后的新选择器，自愈失败时为 None。
        confidence: 自愈置信度（0.0-1.0）。
        occurred_at: 失败发生时间（UTC）。
        strategy: 命中的自愈策略（mcp/vision/stagehand/retry/skip）。
    """

    failure_type: str
    selector: Optional[str] = None
    healed_selector: Optional[str] = None
    confidence: float = 0.0
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    strategy: str = ""


class FailureHistoryArtifact(Artifact):
    """失败历史 Artifact。

    Attributes:
        recent_failures: 最近 N 次同类失败记录列表，按时间倒序排列。
    """

    artifact_type: ClassVar[str] = "failure_history"
    description: ClassVar[str] = "近期同类失败记录与修复策略，用于经验复用"

    recent_failures: List[FailureRecord] = []


__all__ = ["FailureHistoryArtifact", "FailureRecord"]
