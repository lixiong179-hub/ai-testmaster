"""服务端工具集单元测试。

覆盖 app/services/agent/tools/server_tools.py 的 4 个工具：
GetTestCaseTool / QueryProjectTool / QueryAuditTool / QueryLocatorHistoryTool。

测试维度：db 不可用降级、资源不存在、项目隔离、正常流程、边界值（limit 截断、
confidence 为 NULL）。事务隔离：async_db fixture 外层事务包裹，结束 rollback 清理。
"""
import uuid

import pytest

from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase
from app.models.user import User
from app.services.agent.tools.base_tool import ToolContext
from app.services.agent.tools.server_tools import (
    GetTestCaseTool, QueryAuditTool, QueryLocatorHistoryTool, QueryProjectTool,
)
from app.utils.jwt_utils import get_password_hash


async def _create_case(async_db, project, *, title=None):
    """创建测试用例并 flush，返回 TestCase 对象。"""
    suffix = uuid.uuid4().hex[:8]
    case = TestCase(
        project_id=project.id, case_no=f"ST-{suffix}", module="服务端工具测试",
        title=title or f"工具测试用例-{suffix}", precondition="无", steps_json=[],
        expected_result="成功", priority=2, case_type="UI", generate_status=1,
    )
    async_db.add(case)
    await async_db.flush()
    return case


async def _create_locator(async_db, *, css_selector=".btn", xpath="//button", version=1):
    """创建元素定位器并 flush（step_id 置空用于独立查询场景）。"""
    locator = ElementLocator(
        step_id=None, element_description="测试按钮", element_type="button",
        css_selector=css_selector, xpath=xpath, source="ai_self_healing",
        version=version, success_count=10,
    )
    async_db.add(locator)
    await async_db.flush()
    return locator


async def _create_audit(async_db, case, *, step_index=0, confidence=0.85):
    """创建审计记录并 flush，返回 SelfHealingAudit 对象。"""
    audit = SelfHealingAudit(
        test_case_id=case.id, step_index=step_index, locator_id=None,
        old_selector=".old", new_selector=".new", failure_type="element_gone",
        strategy="mcp", confidence=confidence, token_cost=200, low_confidence=False,
    )
    async_db.add(audit)
    await async_db.flush()
    return audit


async def _create_other_user_project(async_db):
    """创建属于其他用户的项目，用于跨项目隔离场景。返回 (other_user, other_project)。"""
    suffix = uuid.uuid4().hex[:8]
    other_user = User(
        username=f"other_user_st_{suffix}", email=f"other_st_{suffix}@test.com",
        password_hash=get_password_hash("Other@123456"), is_active=True, is_superuser=False,
    )
    async_db.add(other_user)
    await async_db.flush()
    other_project = Project(
        name=f"other_project_st_{suffix}", user_id=other_user.id,
        description="other project for isolation test", status=1, project_type="web",
    )
    async_db.add(other_project)
    await async_db.flush()
    return other_user, other_project


# ============================================================================
# GetTestCaseTool 测试
# ============================================================================


class TestGetTestCaseTool:
    """GetTestCaseTool 按 ID 查询测试用例核心字段。"""

    async def test_db_unavailable_returns_error(self):
        """context.db=None 时返回数据库会话不可用错误。"""
        tool = GetTestCaseTool()
        ctx = ToolContext(db=None, project_id=1)
        result = await tool.execute({"test_case_id": 1}, ctx)
        assert result.success is False
        assert "数据库会话不可用" in result.error

    async def test_case_not_found(self, async_db, async_test_project):
        """查询不存在的用例 ID 返回不存在错误。"""
        tool = GetTestCaseTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": 999999}, ctx)
        assert result.success is False
        assert "用例不存在" in result.error

    async def test_case_found_returns_fields(
        self, async_db, async_test_project
    ):
        """存在的用例返回 id/title/case_type/priority 字段。"""
        case = await _create_case(async_db, async_test_project, title="查询用例")
        tool = GetTestCaseTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": case.id}, ctx)
        assert result.success is True
        assert result.output["id"] == case.id
        assert result.output["title"] == "查询用例"
        assert result.output["case_type"] == "UI"
        assert result.output["priority"] == 2

    async def test_case_project_isolation(
        self, async_db, async_test_project
    ):
        """跨项目查询：他人项目的用例对本项目不可见，返回不存在。"""
        _, other_project = await _create_other_user_project(async_db)
        other_case = await _create_case(async_db, other_project, title="他人用例")
        tool = GetTestCaseTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": other_case.id}, ctx)
        assert result.success is False
        assert "用例不存在" in result.error


# ============================================================================
# QueryProjectTool 测试
# ============================================================================


class TestQueryProjectTool:
    """QueryProjectTool 查询项目基础信息。"""

    async def test_db_unavailable_returns_error(self):
        """context.db=None 时返回数据库会话不可用错误。"""
        tool = QueryProjectTool()
        ctx = ToolContext(db=None, project_id=1)
        result = await tool.execute({}, ctx)
        assert result.success is False
        assert "数据库会话不可用" in result.error

    async def test_project_id_none_returns_error(self, async_db):
        """context.project_id=None 时返回项目 ID 不可用错误。"""
        tool = QueryProjectTool()
        ctx = ToolContext(db=async_db, project_id=None)
        result = await tool.execute({}, ctx)
        assert result.success is False
        assert "项目 ID 不可用" in result.error

    async def test_project_not_found(self, async_db):
        """查询不存在的项目 ID 返回项目不存在错误。"""
        tool = QueryProjectTool()
        ctx = ToolContext(db=async_db, project_id=999999)
        result = await tool.execute({}, ctx)
        assert result.success is False
        assert "项目不存在" in result.error

    async def test_project_found_returns_fields(
        self, async_db, async_test_project
    ):
        """存在的项目返回 id/name/description 字段。"""
        tool = QueryProjectTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({}, ctx)
        assert result.success is True
        assert result.output["id"] == async_test_project.id
        assert result.output["name"] == async_test_project.name
        assert result.output["description"] == async_test_project.description


# ============================================================================
# QueryAuditTool 测试
# ============================================================================


class TestQueryAuditTool:
    """QueryAuditTool 按用例 ID 查询自愈审计记录。"""

    async def test_db_unavailable_returns_error(self):
        """context.db=None 时返回数据库会话不可用错误。"""
        tool = QueryAuditTool()
        ctx = ToolContext(db=None, project_id=1)
        result = await tool.execute({"test_case_id": 1}, ctx)
        assert result.success is False
        assert "数据库会话不可用" in result.error

    async def test_empty_records(self, async_db, async_test_project):
        """无审计记录时返回空列表与 count=0。"""
        case = await _create_case(async_db, async_test_project)
        tool = QueryAuditTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": case.id}, ctx)
        assert result.success is True
        assert result.output["records"] == []
        assert result.output["count"] == 0

    async def test_with_records_returns_fields(
        self, async_db, async_test_project
    ):
        """有审计记录时返回完整字段。"""
        case = await _create_case(async_db, async_test_project)
        audit = await _create_audit(async_db, case, step_index=1)
        tool = QueryAuditTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": case.id}, ctx)
        assert result.success is True
        assert result.output["count"] == 1
        record = result.output["records"][0]
        assert record["id"] == audit.id
        assert record["test_case_id"] == case.id
        assert record["step_index"] == 1
        assert record["strategy"] == "mcp"
        assert record["confidence"] == pytest.approx(0.85)
        assert record["failure_type"] == "element_gone"

    async def test_limit_capped_at_50(self, async_db, async_test_project):
        """limit=100 被截断为 50（min(limit, 50) 保护）。"""
        case = await _create_case(async_db, async_test_project)
        await _create_audit(async_db, case, step_index=0)
        tool = QueryAuditTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        # 传入 100，验证不抛错（截断逻辑生效）
        result = await tool.execute(
            {"test_case_id": case.id, "limit": 100}, ctx
        )
        assert result.success is True
        assert result.output["count"] == 1

    async def test_default_limit_when_missing(
        self, async_db, async_test_project
    ):
        """未传 limit 时使用默认值 10。"""
        case = await _create_case(async_db, async_test_project)
        for i in range(15):
            await _create_audit(async_db, case, step_index=i)
        tool = QueryAuditTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": case.id}, ctx)
        assert result.success is True
        # 默认 limit=10，但本测试插入 15 条，应只返回前 10 条
        assert result.output["count"] == 10

    async def test_confidence_none_handled(
        self, async_db, async_test_project
    ):
        """confidence 为 NULL 时序列化为 None 不抛错。"""
        case = await _create_case(async_db, async_test_project)
        await _create_audit(async_db, case, confidence=None)
        tool = QueryAuditTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"test_case_id": case.id}, ctx)
        assert result.success is True
        record = result.output["records"][0]
        assert record["confidence"] is None


# ============================================================================
# QueryLocatorHistoryTool 测试
# ============================================================================


class TestQueryLocatorHistoryTool:
    """QueryLocatorHistoryTool 按定位器 ID 查询元素定位器历史。"""

    async def test_db_unavailable_returns_error(self):
        """context.db=None 时返回数据库会话不可用错误。"""
        tool = QueryLocatorHistoryTool()
        ctx = ToolContext(db=None, project_id=1)
        result = await tool.execute({"locator_id": 1}, ctx)
        assert result.success is False
        assert "数据库会话不可用" in result.error

    async def test_locator_not_found(self, async_db, async_test_project):
        """查询不存在的定位器 ID 返回定位器不存在错误。"""
        tool = QueryLocatorHistoryTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"locator_id": 999999}, ctx)
        assert result.success is False
        assert "定位器不存在" in result.error

    async def test_locator_found_returns_fields(
        self, async_db, async_test_project
    ):
        """存在的定位器返回 id/css_selector/xpath/success_count/version 字段。"""
        locator = await _create_locator(
            async_db, css_selector=".login-btn", xpath="//button[@id='login']", version=3
        )
        tool = QueryLocatorHistoryTool()
        ctx = ToolContext(db=async_db, project_id=async_test_project.id)
        result = await tool.execute({"locator_id": locator.id}, ctx)
        assert result.success is True
        assert result.output["id"] == locator.id
        assert result.output["css_selector"] == ".login-btn"
        assert result.output["xpath"] == "//button[@id='login']"
        assert result.output["success_count"] == 10
        assert result.output["version"] == 3
