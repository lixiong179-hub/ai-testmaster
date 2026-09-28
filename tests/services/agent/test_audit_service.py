"""AgentAuditService + RollbackHandlers 单元测试。

覆盖 record_action / get_session_audit / list_pending_approvals /
approve_action / rollback_action 全部方法与校验分支，以及
RollbackHandlers 注册表的 get_rollback_handler。

使用真实 async_db fixture 事务隔离，回滚测试使用真实 TestCase /
ElementLocator 数据验证补偿动作，无 Mock 数据库。

被测：
    - app/services/agent/audit_service.py（AgentAuditService）
    - app/services/agent/_rollback_handlers.py（RollbackHandlers）
"""
import pytest
from sqlalchemy import select

from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase
from app.services.agent._rollback_handlers import get_rollback_handler
from app.services.agent.audit_service import AgentAuditService
from app.services.agent.exceptions import AgentError
from app.services.agent.session_service import SessionService


@pytest.fixture
def audit_service() -> AgentAuditService:
    return AgentAuditService()


async def _create_session(async_db, project_id: int) -> int:
    """创建测试会话，返回 session_id。"""
    svc = SessionService()
    session = await svc.create_session(
        async_db, agent_type="test_generation", project_id=project_id,
    )
    return session.id


async def _create_test_case(async_db, project_id: int) -> TestCase:
    """创建真实测试用例。"""
    case = TestCase(
        project_id=project_id, case_no="AUDIT-TC-001",
        module="audit_module", title="audit test case",
        precondition="none", steps_json=[], expected_result="ok",
        priority=1, case_type="UI",
    )
    async_db.add(case)
    await async_db.flush()
    return case


async def _create_locator(async_db) -> ElementLocator:
    """创建真实元素定位器（无需关联 TestStep）。"""
    locator = ElementLocator(
        element_description="test button", element_type="button",
        css_selector=".new-selector", source="ai", version=0,
    )
    async_db.add(locator)
    await async_db.flush()
    return locator


class TestRecordAction:
    """record_action 写入审计记录。"""

    async def test_record_action_success(self, audit_service, async_db, async_test_project):
        """正常记录 → 返回 AgentAudit。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={"tool": "search"},
            decision_confidence=0.85,
        )
        assert audit.id is not None
        assert audit.session_id == session_id
        assert audit.iteration == 1
        assert audit.action_type == "tool_call"
        assert float(audit.decision_confidence) == 0.85
        assert audit.human_approved == 0

    async def test_record_action_invalid_action_type(self, audit_service, async_db, async_test_project):
        """非法 action_type → AgentError。"""
        session_id = await _create_session(async_db, async_test_project.id)
        with pytest.raises(AgentError, match="非法 action_type"):
            await audit_service.record_action(
                async_db, session_id=session_id, iteration=1,
                action_type="invalid_action", action_detail={},
            )

    async def test_record_action_confidence_out_of_range(self, audit_service, async_db, async_test_project):
        """decision_confidence 超范围 → AgentError。"""
        session_id = await _create_session(async_db, async_test_project.id)
        with pytest.raises(AgentError, match="非法 decision_confidence"):
            await audit_service.record_action(
                async_db, session_id=session_id, iteration=1,
                action_type="tool_call", action_detail={},
                decision_confidence=1.5,
            )

    async def test_record_action_confidence_none(self, audit_service, async_db, async_test_project):
        """decision_confidence=None → 正常记录。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={},
            decision_confidence=None,
        )
        assert audit.decision_confidence is None


class TestGetSessionAudit:
    """get_session_audit 查询审计链。"""

    async def test_get_session_audit_ordered_by_iteration(self, audit_service, async_db, async_test_project):
        """返回按 id（即 iteration 顺序）升序的审计列表。"""
        session_id = await _create_session(async_db, async_test_project.id)
        for i in range(3):
            await audit_service.record_action(
                async_db, session_id=session_id, iteration=i,
                action_type="tool_call", action_detail={"iter": i},
            )
        records = await audit_service.get_session_audit(async_db, session_id)
        assert len(records) == 3
        assert [r.iteration for r in records] == [0, 1, 2]


class TestListPendingApprovals:
    """list_pending_approvals 待审批查询。"""

    async def test_list_pending_returns_only_pending(
        self, audit_service, async_db, async_test_user, async_test_project
    ):
        """返回 human_approved=0 的审计。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit1 = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={},
        )
        audit2 = await audit_service.record_action(
            async_db, session_id=session_id, iteration=2,
            action_type="tool_call", action_detail={},
        )
        await audit_service.approve_action(
            async_db, audit_id=audit1.id, approved_by=async_test_user.id,
        )
        pending, total = await audit_service.list_pending_approvals(async_db)
        assert total == 1
        assert len(pending) == 1
        assert pending[0].id == audit2.id

    async def test_list_pending_pagination(self, audit_service, async_db, async_test_project):
        """分页 + total 正确。"""
        session_id = await _create_session(async_db, async_test_project.id)
        for i in range(5):
            await audit_service.record_action(
                async_db, session_id=session_id, iteration=i,
                action_type="tool_call", action_detail={},
            )
        page1, total = await audit_service.list_pending_approvals(async_db, offset=0, limit=2)
        page2, _ = await audit_service.list_pending_approvals(async_db, offset=2, limit=2)
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2


class TestApproveAction:
    """approve_action 审批标记。"""

    async def test_approve_true(self, audit_service, async_db, async_test_user, async_test_project):
        """approved=True → human_approved=1 + approved_by + approved_at。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={},
        )
        result = await audit_service.approve_action(
            async_db, audit_id=audit.id, approved_by=async_test_user.id, approved=True,
        )
        assert result.human_approved == 1
        assert result.approved_by == async_test_user.id
        assert result.approved_at is not None

    async def test_approve_false(self, audit_service, async_db, async_test_user, async_test_project):
        """approved=False → human_approved=2。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={},
        )
        result = await audit_service.approve_action(
            async_db, audit_id=audit.id, approved_by=async_test_user.id, approved=False,
        )
        assert result.human_approved == 2
        assert result.approved_by == async_test_user.id

    async def test_approve_not_found(self, audit_service, async_db):
        """不存在 → AgentError。"""
        with pytest.raises(AgentError, match="审计记录不存在"):
            await audit_service.approve_action(
                async_db, audit_id=999999, approved_by=1,
            )


class TestRollbackAction:
    """rollback_action 回滚操作。"""

    async def test_rollback_create_test_case(
        self, audit_service, async_db, async_test_user, async_test_project
    ):
        """create_test_case 类型 → 删除 TestCase + 写入 rollback 审计。"""
        session_id = await _create_session(async_db, async_test_project.id)
        case = await _create_test_case(async_db, async_test_project.id)
        original = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="create_test_case",
            action_detail={"test_case_id": case.id},
        )
        rollback = await audit_service.rollback_action(
            async_db, audit_id=original.id, rolled_by=async_test_user.id, reason="test rollback",
        )
        assert rollback.action_type == "rollback_create_test_case"
        assert rollback.action_detail["original_audit_id"] == original.id
        assert rollback.human_approved == 1
        # 验证 TestCase 已被软删除（查列值避免 identity map 缓存）
        is_deleted = (
            await async_db.execute(
                select(TestCase.is_deleted).where(TestCase.id == case.id)
            )
        ).scalar_one()
        assert is_deleted is True

    async def test_rollback_update_locator(
        self, audit_service, async_db, async_test_user, async_test_project
    ):
        """update_locator 类型 → 恢复 selector + 写入 rollback 审计。"""
        session_id = await _create_session(async_db, async_test_project.id)
        locator = await _create_locator(async_db)
        original = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="update_locator",
            action_detail={"locator_id": locator.id, "old_selector": ".old-selector"},
        )
        rollback = await audit_service.rollback_action(
            async_db, audit_id=original.id, rolled_by=async_test_user.id,
        )
        assert rollback.action_type == "rollback_update_locator"
        assert rollback.action_detail["original_audit_id"] == original.id
        # 验证 selector 已恢复
        css_selector = (
            await async_db.execute(
                select(ElementLocator.css_selector).where(ElementLocator.id == locator.id)
            )
        ).scalar_one()
        assert css_selector == ".old-selector"

    async def test_rollback_unknown_action_type(self, audit_service, async_db, async_test_project):
        """未知 action_type → NotImplementedError。"""
        session_id = await _create_session(async_db, async_test_project.id)
        audit = await audit_service.record_action(
            async_db, session_id=session_id, iteration=1,
            action_type="tool_call", action_detail={},
        )
        with pytest.raises(NotImplementedError, match="未注册的回滚处理器"):
            await audit_service.rollback_action(
                async_db, audit_id=audit.id, rolled_by=99,
            )

    async def test_rollback_not_found(self, audit_service, async_db):
        """不存在的 audit_id → AgentError。"""
        with pytest.raises(AgentError, match="审计记录不存在"):
            await audit_service.rollback_action(
                async_db, audit_id=999999, rolled_by=99,
            )


class TestRollbackHandlerRegistry:
    """get_rollback_handler 注册表查询。"""

    def test_get_handler_create_test_case(self):
        """create_test_case → 返回 handler。"""
        handler = get_rollback_handler("create_test_case")
        assert handler is not None
        assert callable(handler)

    def test_get_handler_unknown(self):
        """unknown → None。"""
        handler = get_rollback_handler("unknown_action")
        assert handler is None
