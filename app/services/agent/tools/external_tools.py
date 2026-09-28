"""外部工具适配器 - Jira / Azure DevOps / GitHub Issues。

仅完成 schema 注册，execute 抛 NotImplementedError，待后续独立 spec
（add-external-issue-tracker）实现具体 API 调用。

设计原则：
    - schema 优先：LLM function calling 需要提前感知工具存在，schema 注册即可被发现
    - 显式未实现：execute 抛 NotImplementedError 而非返回空结果，避免误判成功
"""
from __future__ import annotations

from typing import Any, Dict

from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult


class _BaseExternalTool(Tool):
    """外部工具基类，execute 统一抛 NotImplementedError。"""

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        raise NotImplementedError(
            f"外部工具 {self.name} 尚未实现，待 add-external-issue-tracker spec 落地"
        )


class CreateJiraIssueTool(_BaseExternalTool):
    """在 Jira 创建缺陷。"""

    name = "create_jira_issue"
    description = "在 Jira 创建缺陷单，关联到指定项目与测试用例"
    parameters_schema = {
        "type": "object",
        "properties": {
            "project_key": {"type": "string", "description": "Jira 项目 key"},
            "summary": {"type": "string", "description": "缺陷标题"},
            "description": {"type": "string", "description": "缺陷描述"},
            "test_case_id": {"type": "integer", "description": "关联测试用例 ID"},
        },
        "required": ["project_key", "summary"],
    }


class QueryJiraIssuesTool(_BaseExternalTool):
    """查询 Jira 缺陷。"""

    name = "query_jira_issues"
    description = "按 JQL 查询 Jira 缺陷列表"
    parameters_schema = {
        "type": "object",
        "properties": {
            "jql": {"type": "string", "description": "JQL 查询语句"},
            "limit": {"type": "integer", "description": "返回上限", "default": 20},
        },
        "required": ["jql"],
    }


class CreateAzureDevOpsBugTool(_BaseExternalTool):
    """在 Azure DevOps 创建 Bug。"""

    name = "create_ado_bug"
    description = "在 Azure DevOps 创建 Bug 工作项"
    parameters_schema = {
        "type": "object",
        "properties": {
            "project": {"type": "string", "description": "ADO 项目名"},
            "title": {"type": "string", "description": "Bug 标题"},
            "repro_steps": {"type": "string", "description": "复现步骤"},
        },
        "required": ["project", "title"],
    }


class CreateGitHubIssueTool(_BaseExternalTool):
    """在 GitHub Issues 创建 Issue。"""

    name = "create_github_issue"
    description = "在 GitHub 仓库创建 Issue"
    parameters_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "仓库名 owner/name"},
            "title": {"type": "string", "description": "Issue 标题"},
            "body": {"type": "string", "description": "Issue 内容"},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "标签列表"},
        },
        "required": ["repo", "title"],
    }


__all__ = [
    "CreateJiraIssueTool",
    "QueryJiraIssuesTool",
    "CreateAzureDevOpsBugTool",
    "CreateGitHubIssueTool",
]
