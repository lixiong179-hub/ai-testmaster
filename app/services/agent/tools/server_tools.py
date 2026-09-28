"""服务端工具集 - 由 AgentRuntime 直接 await execute。

4 个内置服务端工具：
    - GetTestCaseTool : 查询单个测试用例
    - QueryProjectTool : 查询项目信息
    - QueryAuditTool : 查询自愈审计记录
    - QueryLocatorHistoryTool : 查询元素定位器历史

ValidateTestCaseSyntaxTool 已迁移至 app.services.agent.agents._test_case_tools，
与 CreateTestCaseTool 共置以匹配 TestGenerationAgent 场景。

每个工具 <80 行，parameters_schema 严格描述参数，execute 返回 ToolResult。
数据库查询通过 context.db（AsyncSession）执行，结果序列化为 dict 注入 LLM。
"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select

from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase
from app.services.agent.tools.base_tool import Tool, ToolContext, ToolResult


class GetTestCaseTool(Tool):
    """查询单个测试用例。"""

    name = "get_test_case"
    description = "按 ID 查询单个测试用例的标题、类型、优先级等核心字段"
    parameters_schema = {
        "type": "object",
        "properties": {
            "test_case_id": {"type": "integer", "description": "测试用例 ID"},
        },
        "required": ["test_case_id"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="数据库会话不可用")
        test_case_id = params["test_case_id"]
        result = await context.db.execute(
            select(TestCase.id, TestCase.title, TestCase.case_type, TestCase.priority)
            .where(
                TestCase.id == test_case_id,
                TestCase.project_id == context.project_id,
            )
        )
        row = result.first()
        if row is None:
            return ToolResult(success=False, error=f"用例不存在: id={test_case_id}")
        return ToolResult(
            success=True,
            output={"id": row.id, "title": row.title, "case_type": row.case_type, "priority": row.priority},
        )


class QueryProjectTool(Tool):
    """查询项目信息。"""

    name = "query_project"
    description = "按项目 ID 查询项目名称、描述等基础信息"
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="数据库会话不可用")
        if context.project_id is None:
            return ToolResult(success=False, error="项目 ID 不可用")
        result = await context.db.execute(
            select(Project.id, Project.name, Project.description).where(Project.id == context.project_id)
        )
        row = result.first()
        if row is None:
            return ToolResult(success=False, error=f"项目不存在: id={context.project_id}")
        return ToolResult(
            success=True,
            output={"id": row.id, "name": row.name, "description": row.description},
        )


class QueryAuditTool(Tool):
    """查询自愈审计记录。"""

    name = "query_audit"
    description = "按用例 ID 查询最近 N 条自愈审计记录，了解历史失败与修复策略"
    parameters_schema = {
        "type": "object",
        "properties": {
            "test_case_id": {"type": "integer", "description": "测试用例 ID"},
            "limit": {"type": "integer", "description": "返回记录数上限，默认 10", "default": 10},
        },
        "required": ["test_case_id"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="数据库会话不可用")
        limit = min(int(params.get("limit", 10)), 50)
        result = await context.db.execute(
            select(
                SelfHealingAudit.id,
                SelfHealingAudit.test_case_id,
                SelfHealingAudit.step_index,
                SelfHealingAudit.strategy,
                SelfHealingAudit.confidence,
                SelfHealingAudit.failure_type,
                SelfHealingAudit.created_at,
            )
            .where(SelfHealingAudit.test_case_id == params["test_case_id"])
            .order_by(SelfHealingAudit.created_at.desc())
            .limit(limit)
        )
        records = [
            {
                "id": r.id,
                "test_case_id": r.test_case_id,
                "step_index": r.step_index,
                "strategy": r.strategy,
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "failure_type": r.failure_type,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in result.fetchall()
        ]
        return ToolResult(success=True, output={"records": records, "count": len(records)})


class QueryLocatorHistoryTool(Tool):
    """查询元素定位器历史。"""

    name = "query_locator_history"
    description = "按定位器 ID 查询元素定位器的 CSS/XPath 选择器与成功率"
    parameters_schema = {
        "type": "object",
        "properties": {
            "locator_id": {"type": "integer", "description": "元素定位器 ID"},
        },
        "required": ["locator_id"],
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="数据库会话不可用")
        result = await context.db.execute(
            select(
                ElementLocator.id,
                ElementLocator.css_selector,
                ElementLocator.xpath,
                ElementLocator.success_count,
                ElementLocator.version,
            ).where(ElementLocator.id == params["locator_id"])
        )
        row = result.first()
        if row is None:
            return ToolResult(success=False, error=f"定位器不存在: id={params['locator_id']}")
        return ToolResult(
            success=True,
            output={
                "id": row.id,
                "css_selector": row.css_selector,
                "xpath": row.xpath,
                "success_count": row.success_count,
                "version": row.version,
            },
        )


__all__ = [
    "GetTestCaseTool",
    "QueryProjectTool",
    "QueryAuditTool",
    "QueryLocatorHistoryTool",
]
