"""Agent 架构与自愈体系兼容性测试（Task 15 兼容性测试）。

验证 Agent 框架与现有自愈体系的 4 个集成点不退化：
    1. BaseTokenBudgetGuard 共享：AgentTokenBudgetGuard 与自愈 TokenBudgetGuard
       在同一 Redis 实例下互不污染（namespace 隔离 + 独立累计 + TTL 一致）。
    2. HealResult 类型引用：agent 包重新导出 HealResult，可在 Agent 工具中
       作为返回类型使用，保持跨模块类型契约。
    3. Prometheus 指标独立：agent_* 与 self_heal_* 指标名无冲突，两套指标
       可同时被 prometheus_client 默认 REGISTRY 采集。
    4. MCP Server 与自愈审计互操作：query_self_healing_audit 工具能查询
       SelfHealingAudit 表，且响应可被 JSON 序列化（满足 SSE 传输要求）。

被测：
    - app/services/agent/__init__.py（HealResult re-export）
    - app/services/agent/token_budget.py（AgentTokenBudgetGuard）
    - app/services/agent/metrics.py（agent_* 指标）
    - app/services/self_healing/token_budget.py（TokenBudgetGuard）
    - app/services/self_healing/metrics.py（self_heal_* 指标）
    - app/services/agent/mcp_server.py（query_self_healing_audit handler）

设计原则：
    - 真实组件：使用真实的 TokenBudgetGuard / AgentTokenBudgetGuard /
      SelfHealingAudit 模型与 MCP handler，不 Mock 被测对象本身。
    - 外部依赖隔离：Redis 用 fakeredis（项目规则允许）；DB 用 async_db
      事务回滚隔离；prometheus_client 默认 REGISTRY 通过增量断言避免重置。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

import fakeredis
import pytest

from app.core.config import settings
from app.models.self_healing_audit import SelfHealingAudit
from app.services.agent import (
    AgentTokenBudgetGuard,
    HealResult,
    MCPServer,
    ToolResult,
)
from app.services.agent.mcp_server import (
    _query_self_healing_audit_handler,
    get_mcp_server,
)
from app.services.common.token_budget import BaseTokenBudgetGuard
from app.services.self_healing.metrics import (
    SELF_HEAL_ATTEMPTS,
    SELF_HEAL_DURATION,
    SELF_HEAL_FAILURE,
    SELF_HEAL_SUCCESS,
)
from app.services.self_healing.token_budget import (
    TokenBudgetGuard as SelfHealingTokenBudgetGuard,
)


# ============================================================================
# 1. BaseTokenBudgetGuard 共享行为：Agent vs Self-Healing 真实互操作
# ============================================================================


@pytest.fixture
def shared_fake_redis():
    """所有测试用例共享一个 fakeredis 实例，模拟生产中单 Redis 部署。"""
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.flushall()


class TestBaseTokenBudgetGuardSharing:
    """Agent 与自愈 TokenBudgetGuard 在同一 Redis 下的隔离行为。

    场景：生产环境单 Redis 实例同时服务 Agent 和自愈两套预算守卫，
    必须保证二者计数互不污染、TTL 行为一致、降级路径独立。
    """

    def test_both_guards_inherit_same_base(self):
        """二者均继承 BaseTokenBudgetGuard，保证通用逻辑来源一致。"""
        assert issubclass(AgentTokenBudgetGuard, BaseTokenBudgetGuard)
        assert issubclass(SelfHealingTokenBudgetGuard, BaseTokenBudgetGuard)

    def test_namespace_isolation_in_shared_redis(self, shared_fake_redis):
        """同一 Redis 下 Agent 与自愈计数完全隔离。"""
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )

        agent_guard.consume(1500)
        self_heal_guard.consume(2500)

        # 各自读取自己的累计，互不影响
        assert agent_guard._get_consumed() == 1500
        assert self_heal_guard._get_consumed() == 2500

    def test_namespace_isolation_by_agent_type_and_project(
        self, shared_fake_redis
    ):
        """不同 agent_type + project_id 的 Agent 守卫彼此隔离。"""
        guard_a = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        guard_b = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="failure_analysis",
            project_id=2,
        )
        guard_a.consume(800)
        guard_b.consume(1200)
        assert guard_a._get_consumed() == 800
        assert guard_b._get_consumed() == 1200

    def test_ttl_consistency_between_agent_and_self_heal(
        self, shared_fake_redis
    ):
        """二者 TTL 均为 25h，跨时区覆盖一天的设计一致。"""
        day = datetime.now().strftime("%Y%m%d")
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )
        agent_guard.consume(100)
        self_heal_guard.consume(100)

        agent_ttl = shared_fake_redis.ttl(agent_guard._build_counter_key(day))
        self_heal_ttl = shared_fake_redis.ttl(
            self_heal_guard._build_counter_key(day)
        )
        # 允许 5 秒误差（两个 consume 之间的耗时）
        assert abs(agent_ttl - self_heal_ttl) < 10
        # 均在 25h 附近（25 * 3600 = 90000 秒）
        assert 89000 <= agent_ttl <= 90000

    def test_redis_failure_falls_back_to_independent_memory(
        self,
    ):
        """Redis 异常时，Agent 与自愈守卫各自降级到独立内存计数。"""
        from unittest.mock import MagicMock

        broken_redis_a = MagicMock()
        broken_redis_a.pipeline.side_effect = Exception("connection lost")
        broken_redis_b = MagicMock()
        broken_redis_b.pipeline.side_effect = Exception("connection lost")

        agent_guard = AgentTokenBudgetGuard(
            redis_client=broken_redis_a,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=broken_redis_b
        )
        agent_guard.consume(500)
        self_heal_guard.consume(700)

        # 各自的内存计数独立
        assert agent_guard._memory_counter == 500
        assert self_heal_guard._memory_counter == 700

    def test_agent_daily_budget_check_not_affected_by_self_heal_consumption(
        self, shared_fake_redis
    ):
        """自愈大量消耗 Token 不应触发 Agent 的日预算熔断。"""
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )
        # 自愈消耗接近其自身预算
        self_heal_guard.consume(settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET - 1)
        # Agent 只消耗少量
        agent_guard.consume(1000)
        # Agent 不应因自愈消耗而熔断
        assert agent_guard.is_daily_budget_exhausted() is False
        # 自愈自身应接近熔断但未熔断
        assert self_heal_guard.is_daily_budget_exhausted() is False

    def test_self_heal_daily_budget_check_not_affected_by_agent_consumption(
        self, shared_fake_redis
    ):
        """Agent 大量消耗 Token 不应触发自愈的日预算熔断。"""
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )
        # Agent 消耗接近其自身预算
        agent_guard.consume(settings.AI_AGENT_DAILY_TOKEN_BUDGET - 1)
        # 自愈只消耗少量
        self_heal_guard.consume(1000)
        # 自愈不应因 Agent 消耗而熔断
        assert self_heal_guard.is_daily_budget_exhausted() is False
        # Agent 自身应接近熔断但未熔断
        assert agent_guard.is_daily_budget_exhausted() is False


# ============================================================================
# 2. HealResult 类型引用契约
# ============================================================================


class TestHealResultImportContract:
    """HealResult 从 self_healing.models 导出并被 agent 包重新导出。"""

    def test_heal_result_re_exported_from_agent_package(self):
        """agent 包必须重新导出 HealResult 供 Agent 子类引用。"""
        from app.services.agent import HealResult as AgentHealResult
        from app.services.self_healing.models import (
            HealResult as SourceHealResult,
        )

        assert AgentHealResult is SourceHealResult

    def test_heal_result_can_be_tool_result_output(self):
        """HealResult 实例可被 ToolResult.output 字段承载。"""
        result = HealResult(
            selector="//button[@id='submit']",
            confidence=0.92,
            token_cost=850,
            strategy="mcp",
        )
        tool_result = ToolResult(success=True, output=result, error=None)
        assert tool_result.success is True
        assert tool_result.output is result
        assert tool_result.output.selector == "//button[@id='submit']"
        assert tool_result.output.confidence == 0.92

    def test_heal_result_none_selector_for_failure(self):
        """自愈失败时 selector=None，仍可被 ToolResult 承载。"""
        result = HealResult(
            selector=None, confidence=0.0, token_cost=0, strategy="skip"
        )
        tool_result = ToolResult(success=False, output=result, error="元素未找到")
        assert tool_result.success is False
        assert tool_result.output.selector is None
        assert tool_result.error == "元素未找到"


# ============================================================================
# 3. Prometheus 指标独立：agent_* 与 self_heal_* 无命名冲突
# ============================================================================


def _collect_metric_names() -> set:
    """收集 prometheus_client 默认 REGISTRY 中所有指标族名。

    prometheus_client 的 Counter/Histogram/Gauge 对象本身没有公开 name 属性，
    需通过 REGISTRY.collect() 返回的 Metric 对象访问 .name（指标族名，不含
    _total / _count 等后缀）。
    """
    from prometheus_client import REGISTRY

    names = set()
    for metric in REGISTRY.collect():
        names.add(metric.name)
    return names


class TestMetricsNamespaceIndependence:
    """agent_* 与 self_heal_* 指标命名独立，不冲突。"""

    def test_agent_and_self_heal_metric_names_coexist(self):
        """两套指标同时注册到默认 REGISTRY 无冲突。"""
        names = _collect_metric_names()
        # 自愈指标族名（不含 _total 后缀）
        assert "self_heal_attempts" in names
        assert "self_heal_success" in names
        assert "self_heal_failure" in names
        assert "self_heal_duration_seconds" in names
        # Agent 指标族名
        assert "agent_sessions" in names
        assert "agent_iterations" in names
        assert "agent_tool_calls" in names
        assert "agent_session_duration_seconds" in names

    def test_no_metric_name_overlap_between_agent_and_self_heal(self):
        """agent_* 与 self_heal_* 指标名前缀完全分离，零重叠。"""
        # 通过 REGISTRY.collect() 收集所有指标族名，避免访问 Counter 私有 _name
        all_names = _collect_metric_names()
        self_heal_names = {n for n in all_names if n.startswith("self_heal_")}
        agent_names = {n for n in all_names if n.startswith("agent_")}
        # 无任何名称重叠
        assert self_heal_names.isdisjoint(agent_names)
        # 验证关键指标都存在
        assert "self_heal_attempts" in self_heal_names
        assert "self_heal_success" in self_heal_names
        assert "agent_sessions" in agent_names
        assert "agent_iterations" in agent_names

    def test_both_metric_sets_can_be_incremented_independently(self):
        """同时递增 agent 与 self_heal 指标互不干扰。"""
        from app.services.agent.metrics import (
            AGENT_SESSIONS_TOTAL,
            AgentMetrics,
        )
        from app.services.self_healing.metrics import (
            SELF_HEAL_ATTEMPTS,
            record_attempt,
        )

        agent_labels = {"agent_type": "compat_test", "status": "completed"}
        before_agent = 0.0
        for sample in AGENT_SESSIONS_TOTAL.collect():
            for s in sample.samples:
                if all(s.labels.get(k) == v for k, v in agent_labels.items()):
                    before_agent = s.value
                    break

        before_self_heal = 0.0
        for sample in SELF_HEAL_ATTEMPTS.collect():
            for s in sample.samples:
                before_self_heal = s.value
                break

        # 同时埋点
        AgentMetrics().record_session_end("compat_test", "completed", 0.5, 100)
        record_attempt()

        after_agent = 0.0
        for sample in AGENT_SESSIONS_TOTAL.collect():
            for s in sample.samples:
                if all(s.labels.get(k) == v for k, v in agent_labels.items()):
                    after_agent = s.value
                    break
        after_self_heal = 0.0
        for sample in SELF_HEAL_ATTEMPTS.collect():
            for s in sample.samples:
                after_self_heal = s.value
                break

        # 各自只递增 1，互不污染
        assert after_agent == before_agent + 1
        assert after_self_heal == before_self_heal + 1


# ============================================================================
# 4. MCP Server 与自愈审计互操作
# ============================================================================


class TestMCPServerSelfHealingAuditInterop:
    """MCP Server query_self_healing_audit 工具与自愈审计表互操作。

    场景：外部 LLM Agent 通过 MCP 协议调用 query_self_healing_audit
    工具查询自愈审计记录，验证：
    - 工具已注册到 MCPServer 单例
    - handler 能正确查询 SelfHealingAudit 表
    - 响应可被 JSON 序列化（SSE 传输要求）
    - 分页参数生效
    """

    def test_query_self_healing_audit_tool_registered(self):
        """工具已注册到 MCPServer 单例。"""
        server = get_mcp_server()
        tool = server.get_tool("query_self_healing_audit")
        assert tool is not None
        assert tool.name == "query_self_healing_audit"
        assert "自愈审计" in tool.description or "audit" in tool.description.lower()
        # schema 为 object 类型，含 limit/offset 属性
        assert tool.input_schema["type"] == "object"
        assert "limit" in tool.input_schema["properties"]
        assert "offset" in tool.input_schema["properties"]

    @pytest.mark.asyncio
    async def test_handler_returns_empty_when_no_audits(
        self, async_db, async_test_user
    ):
        """无审计记录时返回空列表与 total=0。"""
        result = await _query_self_healing_audit_handler(
            async_db, async_test_user, {}
        )
        assert result["total"] == 0
        assert result["audits"] == []

    @pytest.mark.asyncio
    async def test_handler_returns_audits_with_correct_fields(
        self, async_db, async_test_user, async_test_project
    ):
        """有审计记录时返回完整字段，且可 JSON 序列化。"""
        # 构造测试用例与审计记录（TestCase.module 为 NOT NULL，必须设置）
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no=f"COMPAT-{datetime.now().strftime('%H%M%S')}",
            module="兼容性测试模块",
            title="兼容性测试用例",
            precondition="无",
            steps_json=[],
            expected_result="成功",
            priority=1,
            case_type="UI",
            generate_status=1,
            created_by=async_test_user.id,
        )
        async_db.add(case)
        await async_db.flush()

        audit = SelfHealingAudit(
            test_case_id=case.id,
            step_index=0,
            locator_id=None,
            old_selector="//button[@id='old']",
            new_selector="//button[@id='new']",
            failure_type="element_gone",
            strategy="mcp",
            confidence=0.85,
            token_cost=500,
            low_confidence=False,
        )
        async_db.add(audit)
        await async_db.flush()

        result = await _query_self_healing_audit_handler(
            async_db, async_test_user, {}
        )
        assert result["total"] >= 1
        # 找到刚插入的审计记录
        target = next(
            (a for a in result["audits"] if a["id"] == audit.id), None
        )
        assert target is not None
        assert target["test_case_id"] == case.id
        assert target["step_index"] == 0
        assert target["old_selector"] == "//button[@id='old']"
        assert target["new_selector"] == "//button[@id='new']"
        assert target["failure_type"] == "element_gone"
        assert target["strategy"] == "mcp"
        assert target["confidence"] == 0.85
        assert target["token_cost"] == 500
        assert target["low_confidence"] is False

        # 验证可被 JSON 序列化（SSE 传输要求）
        serialized = json.dumps(result, ensure_ascii=False, default=str)
        assert "element_gone" in serialized

    @pytest.mark.asyncio
    async def test_handler_pagination_works(
        self, async_db, async_test_user, async_test_project
    ):
        """分页参数 limit/offset 生效。"""
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no=f"COMPAT-PG-{datetime.now().strftime('%H%M%S')}",
            module="分页测试模块",
            title="分页测试用例",
            precondition="无",
            steps_json=[],
            expected_result="成功",
            priority=1,
            case_type="UI",
            generate_status=1,
            created_by=async_test_user.id,
        )
        async_db.add(case)
        await async_db.flush()

        # 插入 5 条审计记录
        for i in range(5):
            audit = SelfHealingAudit(
                test_case_id=case.id,
                step_index=i,
                locator_id=None,
                old_selector=f"//old[{i}]",
                new_selector=f"//new[{i}]",
                failure_type="dom_changed",
                strategy="vision",
                confidence=0.7 + i * 0.05,
                token_cost=100 * (i + 1),
                low_confidence=(i == 0),
            )
            async_db.add(audit)
        await async_db.flush()

        # 第一页：limit=2 offset=0
        page1 = await _query_self_healing_audit_handler(
            async_db, async_test_user, {"limit": 2, "offset": 0}
        )
        assert page1["total"] >= 5
        assert len(page1["audits"]) == 2

        # 第二页：limit=2 offset=2
        page2 = await _query_self_healing_audit_handler(
            async_db, async_test_user, {"limit": 2, "offset": 2}
        )
        assert len(page2["audits"]) == 2

        # 两页的 id 不重叠
        page1_ids = {a["id"] for a in page1["audits"]}
        page2_ids = {a["id"] for a in page2["audits"]}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_handler_default_limit_is_10(
        self, async_db, async_test_user, async_test_project
    ):
        """不传 limit 时默认返回 10 条。"""
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no=f"COMPAT-DEF-{datetime.now().strftime('%H%M%S')}",
            module="默认分页模块",
            title="默认分页用例",
            precondition="无",
            steps_json=[],
            expected_result="成功",
            priority=1,
            case_type="UI",
            generate_status=1,
            created_by=async_test_user.id,
        )
        async_db.add(case)
        await async_db.flush()

        # 插入 12 条审计记录
        for i in range(12):
            audit = SelfHealingAudit(
                test_case_id=case.id,
                step_index=i,
                locator_id=None,
                old_selector=f"//old[{i}]",
                new_selector=f"//new[{i}]",
                failure_type="load_delay",
                strategy="retry",
                confidence=None,
                token_cost=0,
                low_confidence=False,
            )
            async_db.add(audit)
        await async_db.flush()

        result = await _query_self_healing_audit_handler(
            async_db, async_test_user, {}
        )
        # 默认 limit=10
        assert len(result["audits"]) == 10
        assert result["total"] >= 12

    @pytest.mark.asyncio
    async def test_handler_results_ordered_by_id_desc(
        self, async_db, async_test_user, async_test_project
    ):
        """结果按 id 倒序返回（最新记录在前）。"""
        from app.models.test_case import TestCase

        case = TestCase(
            project_id=async_test_project.id,
            case_no=f"COMPAT-ORD-{datetime.now().strftime('%H%M%S')}",
            module="排序测试模块",
            title="排序测试用例",
            precondition="无",
            steps_json=[],
            expected_result="成功",
            priority=1,
            case_type="UI",
            generate_status=1,
            created_by=async_test_user.id,
        )
        async_db.add(case)
        await async_db.flush()

        ids = []
        for i in range(3):
            audit = SelfHealingAudit(
                test_case_id=case.id,
                step_index=i,
                locator_id=None,
                old_selector=f"//old[{i}]",
                new_selector=f"//new[{i}]",
                failure_type="env_noise",
                strategy="skip",
                confidence=None,
                token_cost=0,
                low_confidence=False,
            )
            async_db.add(audit)
            await async_db.flush()
            ids.append(audit.id)

        result = await _query_self_healing_audit_handler(
            async_db, async_test_user, {"limit": 10}
        )
        # 找到本次插入的记录
        result_ids = [a["id"] for a in result["audits"] if a["id"] in ids]
        # 应按倒序排列
        assert result_ids == sorted(result_ids, reverse=True)

    @pytest.mark.asyncio
    async def test_mcp_server_call_tool_routes_to_handler(
        self, async_db, async_test_user
    ):
        """MCPServer.call_tool 能正确路由到 query_self_healing_audit。"""
        server = get_mcp_server()
        result = await server.call_tool(
            "query_self_healing_audit",
            {"limit": 5},
            async_db,
            async_test_user,
        )
        assert "audits" in result
        assert "total" in result
        assert isinstance(result["audits"], list)

    @pytest.mark.asyncio
    async def test_mcp_server_call_unknown_tool_raises(
        self, async_db, async_test_user
    ):
        """调用未注册的 MCP 工具抛 KeyError。"""
        server = get_mcp_server()
        with pytest.raises(KeyError, match="MCP 工具未注册"):
            await server.call_tool(
                "nonexistent_tool", {}, async_db, async_test_user
            )

    def test_mcp_server_lists_query_self_healing_audit_tool(self):
        """MCPServer.list_tools 包含 query_self_healing_audit。"""
        server = get_mcp_server()
        tools = server.list_tools()
        names = {t["name"] for t in tools}
        assert "query_self_healing_audit" in names
        # 验证 tool 描述含 input_schema
        audit_tool = next(t for t in tools if t["name"] == "query_self_healing_audit")
        assert "input_schema" in audit_tool
        assert audit_tool["input_schema"]["type"] == "object"


# ============================================================================
# 5. 端到端：Agent Runtime 调用不破坏自愈 Token 预算
# ============================================================================


class TestAgentRuntimeSelfHealBudgetIsolation:
    """AgentRuntime 消耗 Token 不应触发自愈日预算熔断。

    场景：Agent 与自愈共享 Redis 实例，Agent 大量调用 LLM 后，
    自愈仍能正常工作（不被 Agent 的 Token 消耗拖垮）。
    """

    def test_agent_consume_does_not_affect_self_heal_budget(
        self, shared_fake_redis
    ):
        """Agent consume 大量 Token 后，自愈预算检查仍返回 False。

        is_daily_budget_exhausted 使用 >= 判断，消耗达预算值即熔断。
        AI_AGENT_DAILY_TOKEN_BUDGET=1000000, AI_SELF_HEALING_DAILY_TOKEN_BUDGET=500000。
        """
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )

        # Agent 消耗达自身日预算（>= 触发熔断）
        agent_guard.consume(settings.AI_AGENT_DAILY_TOKEN_BUDGET)
        # 自愈检查自身预算，应仍为未耗尽
        assert self_heal_guard.is_daily_budget_exhausted() is False
        # Agent 自身应已熔断
        assert agent_guard.is_daily_budget_exhausted() is True

    def test_self_heal_consume_does_not_affect_agent_budget(
        self, shared_fake_redis
    ):
        """自愈 consume 大量 Token 后，Agent 预算检查仍返回 False。"""
        agent_guard = AgentTokenBudgetGuard(
            redis_client=shared_fake_redis,
            agent_type="test_generation",
            project_id=1,
        )
        self_heal_guard = SelfHealingTokenBudgetGuard(
            redis_client=shared_fake_redis
        )

        # 自愈消耗达自身日预算（>= 触发熔断）
        self_heal_guard.consume(settings.AI_SELF_HEALING_DAILY_TOKEN_BUDGET)
        # Agent 检查自身预算，应仍为未耗尽
        assert agent_guard.is_daily_budget_exhausted() is False
        # 自愈自身应已熔断
        assert self_heal_guard.is_daily_budget_exhausted() is True
