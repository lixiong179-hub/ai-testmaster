"""MCP Server - 暴露 5 个 MCP 工具供外部 LLM Agent 调用。

工具：generate_test_case / query_test_case / run_test_case /
      query_execution_result / query_self_healing_audit

设计原则：
    - 工具与端点解耦：MCPServer 不感知 HTTP，端点层负责鉴权与 SSE 流式封装
    - 依赖注入：handler 接收 (db, user, arguments)，由端点注入
    - 单例模式：get_mcp_server() 返回进程级唯一实例，工具模块级注册
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.user import User
from app.services.agent.agents import (
    CreateTestCaseTool, ValidateTestCaseSyntaxTool)
from app.services.agent.artifacts import (
    ProjectContextArtifact, UserIntentArtifact)
from app.services.agent.audit_service import AgentAuditService
from app.services.agent.runtime import AgentRuntime
from app.services.agent.session_service import SessionService
from app.services.agent.tools import ToolRegistry

ToolHandler = Callable[
    [AsyncSession, User, Dict[str, Any]],
    Awaitable[Dict[str, Any]],
]


@dataclass
class MCPTool:
    """MCP 工具描述符。

    Attributes:
        name: 工具唯一标识，对应 MCP 协议的 tool name。
        description: 工具用途，注入 MCP tool list 与 OpenAPI 文档。
        input_schema: JSON Schema dict，描述入参结构。
        handler: async (db, user, arguments) -> dict 工具执行函数。
    """

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolHandler


class MCPServer:
    """MCP Server - 工具注册表与执行入口。"""

    def __init__(self) -> None:
        self._tools: Dict[str, MCPTool] = {}

    def register_tool(self, tool: MCPTool) -> None:
        """注册 MCP 工具，重复注册抛 ValueError。"""
        if tool.name in self._tools:
            raise ValueError(f"MCP 工具已注册: {tool.name}")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """按名称查询工具，不存在返回 None。"""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """返回所有工具的 MCP 元信息，按 name 排序。"""
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in sorted(self._tools.values(), key=lambda x: x.name)
        ]

    async def call_tool(
        self, name: str, arguments: Dict[str, Any],
        db: AsyncSession, user: User,
    ) -> Dict[str, Any]:
        """调用指定 MCP 工具。

        Raises:
            KeyError: 工具未注册。
            Exception: handler 抛出的原始异常向上传播，由端点层转译。
        """
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"MCP 工具未注册: {name}")
        try:
            return await tool.handler(db, user, arguments or {})
        except Exception as e:
            logger.exception(f"MCP 工具 {name} 执行失败: {e}")
            raise


# ── 5 个工具 handler 实现 ──


async def _ensure_project_access(
    db: AsyncSession, project_id: int, user: User,
) -> None:
    """校验用户对指定项目的访问权限，超级管理员绕过。

    复用 pipeline_deps.verify_project_access_async 实现项目归属校验，
    防止 MCP handler 按 resource id 越权查询任意租户数据。handler 抛出的
    HTTPException 由端点层 SSE try/except 捕获并转译为 error 事件。
    """
    if user.is_superuser:
        return
    from app.api.v1.endpoints.pipeline_deps import verify_project_access_async
    await verify_project_access_async(db, project_id, user)


async def _generate_test_case_handler(
    db: AsyncSession, user: User, arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """generate_test_case - 创建 TestGenerationAgent 会话并执行。

    llm_provider 留空时 runtime 降级返回固定响应，会话正常关闭，
    test_case_id 为 None，调用方据此判断是否需要重试。
    """
    project_id: int = arguments["project_id"]
    await _ensure_project_access(db, project_id, user)
    user_intent: str = arguments["user_intent"]
    context: Dict[str, Any] = arguments.get("context") or {}

    intent_artifact = UserIntentArtifact(
        natural_language_request=user_intent, origin="mcp",
        priority=context.get("priority", "normal"),
        constraints=context.get("constraints") or [],
    )
    project_artifact = ProjectContextArtifact(
        project_id=project_id,
        name=context.get("project_name", f"project-{project_id}"),
        tech_stack=context.get("tech_stack") or [],
        env_config=context.get("env_config") or {},
        base_url=context.get("base_url"),
    )
    # 为每次调用构造独立 ToolRegistry，避免跨请求状态污染
    tool_registry = ToolRegistry()
    tool_registry.register(CreateTestCaseTool(), agent_types=["test_generation"])
    tool_registry.register(
        ValidateTestCaseSyntaxTool(), agent_types=["test_generation"])
    runtime = AgentRuntime(
        db=db, session_service=SessionService(),
        audit_service=AgentAuditService(), tool_registry=tool_registry,
    )
    session = await runtime.run(
        agent_type="test_generation", project_id=project_id,
        initial_artifacts=[intent_artifact, project_artifact],
        created_by=user.id,
    )
    return {"session_id": session.id, "test_case_id": None, "status": session.status}


async def _query_test_case_handler(
    db: AsyncSession, user: User, arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """query_test_case - 按 ID 查询测试用例。"""
    test_case_id: int = arguments["test_case_id"]
    result = await db.execute(
        select(TestCase).where(
            TestCase.id == test_case_id, TestCase.is_deleted.is_(False)))
    tc = result.scalar_one_or_none()
    if tc is None:
        return {"test_case": None, "message": f"用例不存在: id={test_case_id}"}
    await _ensure_project_access(db, tc.project_id, user)
    return {"test_case": {
        "id": tc.id, "case_no": tc.case_no, "project_id": tc.project_id,
        "module": tc.module, "title": tc.title, "case_type": tc.case_type,
        "priority": tc.priority, "precondition": tc.precondition,
        "steps_json": tc.steps_json, "expected_result": tc.expected_result,
        "review_status": tc.review_status, "lifecycle_status": tc.lifecycle_status,
        "generate_status": tc.generate_status,
        "create_time": tc.create_time.isoformat() if tc.create_time else None,
    }}


async def _run_test_case_handler(
    db: AsyncSession, user: User, arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """run_test_case - 当前降级返回 REST API 提示。

    任务创建涉及执行引擎、用例状态校验等复杂逻辑，统一引导调用方走 REST API。
    即便当前为降级提示，仍校验 project_id 归属防止越权探测。
    """
    project_id: int = arguments["project_id"]
    await _ensure_project_access(db, project_id, user)
    return {
        "task_id": None,
        "message": "请通过 REST API /api/v1/test-task 创建测试任务",
    }


async def _query_execution_result_handler(
    db: AsyncSession, user: User, arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """query_execution_result - 按 task_id 查询测试结果列表。"""
    task_id: int = arguments["task_id"]
    task_result = await db.execute(
        select(TestTask).where(TestTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task is None:
        return {"result": []}
    await _ensure_project_access(db, task.project_id, user)
    result = await db.execute(
        select(TestResult).where(TestResult.task_id == task_id))
    rows = result.scalars().all()
    return {"result": [{
        "id": r.id, "task_id": r.task_id, "case_id": r.case_id,
        "case_no": r.case_no, "exec_status": r.exec_status,
        "error_msg": r.error_msg, "screenshot_url": r.screenshot_url,
        "exec_time": r.exec_time.isoformat() if r.exec_time else None,
    } for r in rows]}


async def _query_self_healing_audit_handler(
    db: AsyncSession, user: User, arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """query_self_healing_audit - 分页查询自愈审计记录。

    非超级管理员仅返回其项目下用例触发的自愈记录，通过 test_case_id 关联
    TestCase.project_id → Project.user_id 实现行级过滤，防止跨租户越权。
    """
    limit: int = arguments.get("limit", 10)
    offset: int = arguments.get("offset", 0)
    stmt = (
        select(SelfHealingAudit)
        .order_by(SelfHealingAudit.id.desc())
        .offset(offset).limit(limit)
    )
    count_stmt = select(func.count(SelfHealingAudit.id))
    if not user.is_superuser:
        accessible_case_ids = (
            select(TestCase.id)
            .join(Project, Project.id == TestCase.project_id)
            .where(Project.user_id == user.id)
        )
        stmt = stmt.where(SelfHealingAudit.test_case_id.in_(accessible_case_ids))
        count_stmt = count_stmt.where(
            SelfHealingAudit.test_case_id.in_(accessible_case_ids))
    result = await db.execute(stmt)
    audits = result.scalars().all()
    count_result = await db.execute(count_stmt)
    total = int(count_result.scalar() or 0)
    return {"audits": [a.to_dict() for a in audits], "total": total}


_TOOL_SPECS: List[Dict[str, Any]] = [
    {
        "name": "generate_test_case",
        "description": "根据用户意图与项目上下文生成测试用例",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目 ID"},
                "user_intent": {"type": "string", "description": "用户的自然语言测试意图"},
                "context": {"type": "object", "description": "可选项目上下文（tech_stack / base_url 等）"},
            },
            "required": ["project_id", "user_intent"],
        },
        "handler": _generate_test_case_handler,
    },
    {
        "name": "query_test_case",
        "description": "按 ID 查询测试用例详情",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_case_id": {"type": "integer", "description": "测试用例 ID"},
            },
            "required": ["test_case_id"],
        },
        "handler": _query_test_case_handler,
    },
    {
        "name": "run_test_case",
        "description": "创建测试任务执行测试用例（当前降级返回 REST API 提示）",
        "input_schema": {
            "type": "object",
            "properties": {
                "test_case_id": {"type": "integer", "description": "测试用例 ID"},
                "project_id": {"type": "integer", "description": "项目 ID"},
            },
            "required": ["test_case_id", "project_id"],
        },
        "handler": _run_test_case_handler,
    },
    {
        "name": "query_execution_result",
        "description": "按任务 ID 查询测试执行结果列表",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "测试任务 ID"},
            },
            "required": ["task_id"],
        },
        "handler": _query_execution_result_handler,
    },
    {
        "name": "query_self_healing_audit",
        "description": "分页查询自愈审计记录",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回条数，默认 10", "default": 10},
                "offset": {"type": "integer", "description": "偏移量，默认 0", "default": 0},
            },
        },
        "handler": _query_self_healing_audit_handler,
    },
]

_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """获取 MCPServer 单例，首次调用时构造并注册 5 个内置工具。"""
    global _mcp_server
    if _mcp_server is None:
        server = MCPServer()
        for spec in _TOOL_SPECS:
            server.register_tool(MCPTool(**spec))
        _mcp_server = server
    return _mcp_server


__all__ = ["MCPTool", "MCPServer", "get_mcp_server"]
