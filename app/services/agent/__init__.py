"""Agent 架构子包 - 共享 Agent 框架核心。

Phase 2 框架核心导出（Task 4）：
    - AgentDefinition : Agent 配置定义 dataclass
    - AgentBase : Agent 抽象基类
    - AgentRegistry / get_global_registry : Agent 注册表单例
    - AgentTokenBudgetGuard : Agent Token 预算守卫
    - AgentError 及子类 : 异常体系

后续阶段导出（待实现）：
    - AgentRuntime : Agent 执行引擎（Task 5）
    - ArtifactRegistry : Artifacts 注册表（Task 6）
    - ToolRegistry : 工具注册表（Task 7）
    - SessionService / AgentAuditService : 会话与审计服务（Task 8）
    - LoopDetector / CircuitBreaker : 循环检测与熔断器（Task 9）
    - TestGenerationAgent : 示范 Agent（Task 11）

设计参考：Mabl V2 共享基座 + Applitools Visual AI Agent 框架。
"""
from app.services.agent.artifact_registry import ArtifactRegistry
from app.services.agent.artifacts import (
    ApplicationStateArtifact,
    Artifact,
    ExecutionStateArtifact,
    FailureHistoryArtifact,
    FailureRecord,
    ProjectContextArtifact,
    TestCaseArtifact,
    UserIntentArtifact,
)
from app.services.agent.audit_service import AgentAuditService
from app.services.agent.base import AgentBase, AgentDefinition
from app.services.agent.circuit_breaker import CircuitBreaker
from app.services.agent.exceptions import (
    AgentError,
    AgentLoopDetected,
    CircuitBreakerOpen,
    ContextTruncated,
    MaxIterationsExceeded,
    TokenBudgetExceeded,
    ToolExecutionError,
)
from app.services.agent.loop_detector import LoopDetector
from app.services.agent.metrics import AgentMetrics, get_metrics
from app.services.agent.registry import AgentRegistry, get_global_registry
from app.services.agent.runtime import AgentRuntime
from app.services.agent.session_service import SessionService
from app.services.agent.token_budget import AgentTokenBudgetGuard
from app.services.agent.tools import (
    ClickElementTool,
    GetTestCaseTool,
    Tool,
    ToolContext,
    ToolRegistry,
    ToolResult,
)

# 业务 Agent 与场景工具（Task 11 + Phase 2 VisualValidationAgent）
from app.services.agent.agents import (
    CreateTestCaseTool,
    TestGenerationAgent,
    ValidateTestCaseSyntaxTool,
    VisualValidationAgent,
)
from app.services.agent._registrations import register_default_agents

# MCP Server（Task 12）
from app.services.agent.mcp_server import MCPServer, get_mcp_server

# 重新导出 HealResult，便于 Agent 子类引用自愈结果类型
from app.services.self_healing.models import HealResult

__all__ = [
    # 基础框架
    "AgentBase",
    "AgentDefinition",
    "AgentRegistry",
    "get_global_registry",
    "AgentTokenBudgetGuard",
    "AgentRuntime",
    # Artifacts 系统
    "ArtifactRegistry",
    "Artifact",
    "TestCaseArtifact",
    "ExecutionStateArtifact",
    "ApplicationStateArtifact",
    "ProjectContextArtifact",
    "FailureHistoryArtifact",
    "FailureRecord",
    "UserIntentArtifact",
    # 工具系统
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    "GetTestCaseTool",
    "ValidateTestCaseSyntaxTool",
    "CreateTestCaseTool",
    "ClickElementTool",
    # 业务 Agent（Task 11 + Phase 2）
    "TestGenerationAgent",
    "VisualValidationAgent",
    "register_default_agents",
    # MCP Server（Task 12）
    "MCPServer",
    "get_mcp_server",
    # 异常体系
    "AgentError",
    "AgentLoopDetected",
    "TokenBudgetExceeded",
    "ToolExecutionError",
    "ContextTruncated",
    "MaxIterationsExceeded",
    "CircuitBreakerOpen",
    # 循环检测与熔断器（Task 9）
    "LoopDetector",
    "CircuitBreaker",
    # 会话与审计服务（Task 8）
    "SessionService",
    "AgentAuditService",
    # 指标埋点（Task 10）
    "AgentMetrics",
    "get_metrics",
    # 复用类型
    "HealResult",
]
