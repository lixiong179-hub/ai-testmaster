"""工具子包 - Agent function calling 工具系统。

工具分为三类：
    - 服务端工具（server_tools.py）：AgentRuntime 直接 await execute，如查询数据库
    - 客户端工具（client_tools.py）：通过 execution_callback 回调测试执行引擎
    - 外部工具（external_tools.py）：Jira/ADO/GitHub Issues 适配器，仅 schema 注册

工具通过 ToolRegistry 注册，按 agent_type 路由，AgentRuntime.list_for_agent()
获取当前 Agent 可用工具列表构造 LLM function schema。
"""
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult
from app.services.agent.tools.client_tools import (
    ClickElementTool,
    GetDomTool,
    InputElementTool,
    ScreenshotTool,
    ScrollTool,
    WaitTool,
)
from app.services.agent.tools.external_tools import (
    CreateAzureDevOpsBugTool,
    CreateGitHubIssueTool,
    CreateJiraIssueTool,
    QueryJiraIssuesTool,
)
from app.services.agent.tools.registry import ToolRegistry
from app.services.agent.tools.server_tools import (
    GetTestCaseTool,
    QueryAuditTool,
    QueryLocatorHistoryTool,
    QueryProjectTool,
)

__all__ = [
    # 基类
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolRegistry",
    # 服务端工具
    "GetTestCaseTool",
    "QueryProjectTool",
    "QueryAuditTool",
    "QueryLocatorHistoryTool",
    # ValidateTestCaseSyntaxTool 已迁移至 app.services.agent.agents._test_case_tools
    # 客户端工具
    "ClickElementTool",
    "InputElementTool",
    "ScreenshotTool",
    "GetDomTool",
    "ScrollTool",
    "WaitTool",
    # 外部工具
    "CreateJiraIssueTool",
    "QueryJiraIssuesTool",
    "CreateAzureDevOpsBugTool",
    "CreateGitHubIssueTool",
]
