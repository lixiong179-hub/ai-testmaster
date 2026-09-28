"""Artifacts 子包 - Agent 上下文的自描述单元。

每个 artifact 类通过 pydantic schema 校验数据完整性，通过 artifact_type
标识类型，通过 to_prompt_section() 输出注入 LLM prompt 的文本段。

内置 6 个 artifact：
    - TestCaseArtifact : 测试用例上下文
    - ExecutionStateArtifact : 测试执行状态
    - ApplicationStateArtifact : 被测应用状态
    - ProjectContextArtifact : 项目上下文
    - FailureHistoryArtifact : 失败历史
    - UserIntentArtifact : 用户意图
"""
from app.services.agent.artifacts.application_state_artifact import (
    ApplicationStateArtifact,
)
from app.services.agent.artifacts.base import Artifact
from app.services.agent.artifacts.execution_state_artifact import (
    ExecutionStateArtifact,
)
from app.services.agent.artifacts.failure_history_artifact import (
    FailureHistoryArtifact,
    FailureRecord,
)
from app.services.agent.artifacts.project_context_artifact import (
    ProjectContextArtifact,
)
from app.services.agent.artifacts.test_case_artifact import TestCaseArtifact
from app.services.agent.artifacts.user_intent_artifact import UserIntentArtifact

__all__ = [
    "Artifact",
    "TestCaseArtifact",
    "ExecutionStateArtifact",
    "ApplicationStateArtifact",
    "ProjectContextArtifact",
    "FailureHistoryArtifact",
    "FailureRecord",
    "UserIntentArtifact",
]
