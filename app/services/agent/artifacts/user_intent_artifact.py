"""用户意图 Artifact。

承载用户的自然语言请求与约束，是 TestGenerationAgent 等「请求驱动」
Agent 的输入起点，所有迭代围绕满足 user_intent 展开。
"""
from __future__ import annotations

from typing import ClassVar, List

from app.services.agent.artifacts.base import Artifact


class UserIntentArtifact(Artifact):
    """用户意图 Artifact。

    Attributes:
        natural_language_request: 用户的自然语言请求原文。
        origin: 请求来源（"user" / "api" / "mcp"），用于审计与限流。
        priority: 优先级（"low" / "normal" / "high"），影响调度顺序。
        constraints: 约束列表（如 ["仅生成正向用例", "覆盖边界值"]）。
    """

    artifact_type: ClassVar[str] = "user_intent"
    description: ClassVar[str] = "用户自然语言请求与约束，Agent 执行的起点"

    natural_language_request: str
    origin: str = "user"
    priority: str = "normal"
    constraints: List[str] = []


__all__ = ["UserIntentArtifact"]
