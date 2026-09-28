"""测试用例 Artifact。

承载 Agent 生成或查询的测试用例上下文，是 TestGenerationAgent 与
FailureAnalysisAgent 的核心输入/输出载体。
"""
from __future__ import annotations

from typing import ClassVar, List, Optional

from app.services.agent.artifacts.base import Artifact


class TestCaseArtifact(Artifact):
    """测试用例 Artifact。

    Attributes:
        id: 已落库用例的 ID；新生成的用例为 None。
        title: 用例标题。
        steps: 用例步骤列表，每项为结构化 step（action/target/value/expected）。
        preconditions: 前置条件列表。
    """

    artifact_type: ClassVar[str] = "test_case"
    description: ClassVar[str] = "测试用例上下文，含标题、步骤、前置条件"

    id: Optional[int] = None
    title: str
    steps: List[dict]
    preconditions: List[str] = []


__all__ = ["TestCaseArtifact"]
