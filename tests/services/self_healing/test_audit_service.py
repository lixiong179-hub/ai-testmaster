"""SelfHealingAuditService 单元测试。

覆盖：
    - record_audit 成功写入（含字段完整性）
    - record_audit new_selector=None 表示失败
    - rollback_audit 成功（css_selector 恢复 + version 递增 + 写入 rollback 审计）
    - rollback_audit 不存在 → 404
    - rollback_audit old_selector=None → ValueError
    - rollback_audit locator 不存在 → 404
    - rollback_audit 乐观锁冲突 → 409
    - list_audits 分页 + project_id 过滤 + test_case_id 过滤
    - get_audit 存在/不存在

被测：app/services/self_healing/audit_service.py（SelfHealingAuditService）
使用真实测试库（db fixture 事务隔离）。
乐观锁冲突分支通过拦截 UPDATE 语句返回 rowcount=0 模拟（同步测试无法
通过并发触发，且该分支为防御性代码，mock 单条 SQL 返回值不违背真实库原则）。
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase, TestStep
from app.services.self_healing.audit_service import SelfHealingAuditService


@pytest.fixture
def seed_project(db: Session, testUser):
    """创建测试项目（事务内）。"""
    project = Project(
        name="audit_test_project",
        user_id=testUser.id,
        description="audit service test",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def seed_test_case(db: Session, seed_project):
    """创建测试用例。"""
    case = TestCase(
        project_id=seed_project.id,
        case_no="AUDIT-TEST-001",
        module="audit_module",
        title="audit service test case",
        precondition="none",
        steps_json=[],
        expected_result="ok",
        priority=1,
        case_type="UI",
    )
    db.add(case)
    db.flush()
    return case


@pytest.fixture
def seed_locator(db: Session, seed_test_case):
    """创建元素定位器（含初始 css_selector 与 version=0）。"""
    step = TestStep(
        test_case_id=seed_test_case.id,
        step_number=1,
        action="click login",
        expected_result="ok",
    )
    db.add(step)
    db.flush()
    locator = ElementLocator(
        step_id=step.id,
        element_description="登录按钮",
        element_type="button",
        css_selector=".old-login-btn",
        source="ai",
        version=0,
    )
    db.add(locator)
    db.flush()
    return locator


class TestRecordAudit:
    """record_audit 写入审计记录。"""

    def test_record_audit_success_full_fields(
        self, db: Session, seed_test_case, seed_locator
    ):
        """成功写入审计记录，字段完整。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=seed_locator.id,
            old_selector=".old-btn",
            new_selector=".new-btn",
            failure_type="element_gone",
            strategy="mcp",
            confidence=0.85,
            token_cost=1500,
            low_confidence=False,
        )
        assert audit.id is not None
        assert audit.test_case_id == seed_test_case.id
        assert audit.step_index == 0
        assert audit.locator_id == seed_locator.id
        assert audit.old_selector == ".old-btn"
        assert audit.new_selector == ".new-btn"
        assert audit.failure_type == "element_gone"
        assert audit.strategy == "mcp"
        assert float(audit.confidence) == 0.85
        assert audit.token_cost == 1500
        assert audit.low_confidence is False

    def test_record_audit_low_confidence_flag(
        self, db: Session, seed_test_case, seed_locator
    ):
        """low_confidence=True 正确写入。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=seed_locator.id,
            old_selector=".old",
            new_selector=".new",
            failure_type="dom_changed",
            strategy="vision",
            confidence=0.3,
            token_cost=2000,
            low_confidence=True,
        )
        assert audit.low_confidence is True

    def test_record_audit_new_selector_none_means_failure(
        self, db: Session, seed_test_case
    ):
        """new_selector=None 表示自愈失败仅留痕。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=None,
            old_selector=".old",
            new_selector=None,
            failure_type="env_noise",
            strategy="skip",
            confidence=None,
            token_cost=0,
            low_confidence=False,
        )
        assert audit.new_selector is None
        assert audit.confidence is None
        assert audit.token_cost == 0

    def test_record_audit_zero_token_cost(self, db: Session, seed_test_case):
        """非 AI 策略 token_cost=0。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=None,
            old_selector=None,
            new_selector=None,
            failure_type="load_delay",
            strategy="retry",
            confidence=None,
            token_cost=0,
            low_confidence=False,
        )
        assert audit.token_cost == 0
        assert audit.strategy == "retry"


class TestRollbackAudit:
    """rollback_audit 回滚逻辑。"""

    def test_rollback_audit_success(
        self, db: Session, seed_test_case, seed_locator
    ):
        """成功回滚：css_selector 恢复 + version 递增 + 写入 rollback 审计。"""
        service = SelfHealingAuditService(db)

        # 先写入一条自愈审计（old_selector 是要恢复的目标）
        original_audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=seed_locator.id,
            old_selector=".original-btn",
            new_selector=".healed-btn",
            failure_type="element_gone",
            strategy="mcp",
            confidence=0.85,
            token_cost=1500,
            low_confidence=False,
        )
        # 模拟自愈后定位器被更新为新选择器
        seed_locator.css_selector = ".healed-btn"
        seed_locator.version = 1
        db.flush()

        # 执行回滚
        rollback_audit = service.rollback_audit(original_audit.id)

        # 验证回滚审计记录
        assert rollback_audit.id is not None
        assert rollback_audit.strategy == "rollback"
        assert rollback_audit.old_selector == ".healed-btn"  # 当前选择器
        assert rollback_audit.new_selector == ".original-btn"  # 恢复后的选择器
        assert rollback_audit.confidence is None
        assert rollback_audit.token_cost == 0
        assert rollback_audit.low_confidence is False

        # 验证定位器已恢复
        db.expire_all()
        restored_locator = db.query(ElementLocator).filter(
            ElementLocator.id == seed_locator.id
        ).first()
        assert restored_locator.css_selector == ".original-btn"
        # version 应递增（自愈后=1，回滚后=2）
        assert restored_locator.version == 2

    def test_rollback_audit_not_found_raises_404(self, db: Session):
        """回滚不存在的审计记录 → 404。"""
        service = SelfHealingAuditService(db)
        with pytest.raises(HTTPException) as exc_info:
            service.rollback_audit(999999)
        assert exc_info.value.status_code == 404
        assert "审计记录" in exc_info.value.detail

    def test_rollback_audit_old_selector_none_raises_value_error(
        self, db: Session, seed_test_case
    ):
        """原审计 old_selector=None → ValueError。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=None,
            old_selector=None,
            new_selector=None,
            failure_type="env_noise",
            strategy="skip",
            confidence=None,
            token_cost=0,
            low_confidence=False,
        )
        with pytest.raises(ValueError, match="old_selector/locator_id 为空"):
            service.rollback_audit(audit.id)

    def test_rollback_audit_locator_id_none_raises_value_error(
        self, db: Session, seed_test_case
    ):
        """原审计 locator_id=None → ValueError。"""
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=None,
            old_selector=".old-but-no-locator",
            new_selector=".new",
            failure_type="dom_changed",
            strategy="mcp",
            confidence=0.8,
            token_cost=100,
            low_confidence=False,
        )
        with pytest.raises(ValueError, match="old_selector/locator_id 为空"):
            service.rollback_audit(audit.id)

    def test_rollback_audit_locator_not_found_raises_404(
        self, db: Session, seed_test_case
    ):
        """locator_id 指向不存在的定位器 → 404。

        外键约束阻止直接插入不存在的 locator_id，需先创建审计记录，
        再用 SET FOREIGN_KEY_CHECKS=0 + UPDATE 模拟"定位器被删除但审计保留"。
        """
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=None,
            old_selector=".old",
            new_selector=".new",
            failure_type="element_gone",
            strategy="mcp",
            confidence=0.85,
            token_cost=100,
            low_confidence=False,
        )
        # 禁用外键检查，更新 locator_id 为不存在的值
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.execute(
            text(
                "UPDATE self_healing_audits SET locator_id = 999999 "
                "WHERE id = :id"
            ),
            {"id": audit.id},
        )
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        db.flush()
        # 让 ORM identity map 失效，service 内部查询时读取最新 locator_id
        db.expire_all()

        with pytest.raises(HTTPException) as exc_info:
            service.rollback_audit(audit.id)
        assert exc_info.value.status_code == 404
        assert "定位器" in exc_info.value.detail

    def test_rollback_audit_optimistic_lock_conflict_raises_409(
        self, db: Session, seed_test_case, seed_locator
    ):
        """乐观锁冲突：UPDATE WHERE version 命中 0 行 → 409。

        同步测试无法通过并发触发乐观锁冲突，通过拦截 UPDATE 语句返回
        rowcount=0 模拟"并发已修改 version"场景。该分支为防御性代码，
        mock 单条 SQL 返回值不违背真实库原则（数据仍写入真实库）。
        """
        service = SelfHealingAuditService(db)
        audit = service.record_audit(
            test_case_id=seed_test_case.id,
            step_index=0,
            locator_id=seed_locator.id,
            old_selector=".original",
            new_selector=".healed",
            failure_type="element_gone",
            strategy="mcp",
            confidence=0.85,
            token_cost=100,
            low_confidence=False,
        )
        original_execute = db.execute

        def mock_execute(stmt, *args, **kwargs):
            result = original_execute(stmt, *args, **kwargs)
            stmt_text = getattr(stmt, "text", None) or str(stmt)
            if (
                "UPDATE element_locators" in stmt_text
                and "version = version + 1" in stmt_text
            ):
                # 模拟乐观锁冲突：rowcount=0
                fake = MagicMock()
                fake.rowcount = 0
                return fake
            return result

        with patch.object(db, "execute", side_effect=mock_execute):
            with pytest.raises(HTTPException) as exc_info:
                service.rollback_audit(audit.id)
        assert exc_info.value.status_code == 409
        assert "版本已变更" in exc_info.value.detail


class TestListAudits:
    """list_audits 分页与过滤。"""

    def test_list_audits_pagination(
        self, db: Session, seed_test_case
    ):
        """分页查询：page_size=2 + page=2 返回第 3-4 条。"""
        service = SelfHealingAuditService(db)
        # 写入 5 条审计
        for i in range(5):
            service.record_audit(
                test_case_id=seed_test_case.id,
                step_index=i,
                locator_id=None,
                old_selector=None,
                new_selector=None,
                failure_type="env_noise",
                strategy="skip",
                confidence=None,
                token_cost=0,
                low_confidence=False,
            )

        page1, total = service.list_audits(
            test_case_id=seed_test_case.id, page=1, page_size=2
        )
        page2, _ = service.list_audits(
            test_case_id=seed_test_case.id, page=2, page_size=2
        )
        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        # 按 id 倒序：page1 的 id 应大于 page2 的 id
        assert page1[0].id > page2[0].id

    def test_list_audits_filter_by_test_case_id(
        self, db: Session, seed_test_case, seed_project
    ):
        """按 test_case_id 过滤。"""
        # 创建第二个用例
        other_case = TestCase(
            project_id=seed_project.id,
            case_no="AUDIT-TEST-002",
            module="audit_module",
            title="other case",
            precondition="none",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        db.add(other_case)
        db.flush()

        service = SelfHealingAuditService(db)
        service.record_audit(
            test_case_id=seed_test_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )
        service.record_audit(
            test_case_id=other_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )

        records, total = service.list_audits(test_case_id=seed_test_case.id)
        assert total == 1
        assert all(r.test_case_id == seed_test_case.id for r in records)

    def test_list_audits_filter_by_project_id(
        self, db: Session, seed_test_case, seed_project, testUser
    ):
        """按 project_id 过滤（join test_cases 表）。"""
        # 创建第二个项目+用例
        other_project = Project(
            name="other_project",
            user_id=testUser.id,
            description="other",
            status=1,
            project_type="web",
        )
        db.add(other_project)
        db.flush()
        other_case = TestCase(
            project_id=other_project.id,
            case_no="AUDIT-OTHER-001",
            module="other",
            title="other project case",
            precondition="none",
            steps_json=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        db.add(other_case)
        db.flush()

        service = SelfHealingAuditService(db)
        service.record_audit(
            test_case_id=seed_test_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )
        service.record_audit(
            test_case_id=other_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )

        records, total = service.list_audits(project_id=seed_project.id)
        assert total == 1
        assert all(r.test_case_id == seed_test_case.id for r in records)

    def test_list_audits_page_less_than_1_treated_as_1(
        self, db: Session, seed_test_case
    ):
        """page < 1 时按 1 处理。"""
        service = SelfHealingAuditService(db)
        service.record_audit(
            test_case_id=seed_test_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )
        records, total = service.list_audits(
            test_case_id=seed_test_case.id, page=0, page_size=10
        )
        assert total == 1
        assert len(records) == 1

    def test_list_audits_empty_result(self, db: Session):
        """无审计记录时返回空列表。"""
        service = SelfHealingAuditService(db)
        records, total = service.list_audits(test_case_id=999999)
        assert records == []
        assert total == 0

    def test_list_audits_default_page_size(
        self, db: Session, seed_test_case
    ):
        """默认 page_size=20。"""
        service = SelfHealingAuditService(db)
        service.record_audit(
            test_case_id=seed_test_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )
        records, total = service.list_audits()
        assert total >= 1
        assert len(records) >= 1


class TestGetAudit:
    """get_audit 单条查询。"""

    def test_get_audit_exists(self, db: Session, seed_test_case):
        """存在的审计记录。"""
        service = SelfHealingAuditService(db)
        created = service.record_audit(
            test_case_id=seed_test_case.id, step_index=0, locator_id=None,
            old_selector=None, new_selector=None,
            failure_type="env_noise", strategy="skip",
            confidence=None, token_cost=0, low_confidence=False,
        )
        fetched = service.get_audit(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.test_case_id == seed_test_case.id

    def test_get_audit_not_exists_returns_none(self, db: Session):
        """不存在的审计记录返回 None。"""
        service = SelfHealingAuditService(db)
        result = service.get_audit(999999)
        assert result is None
