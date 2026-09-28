"""端到端自愈流程集成测试。

覆盖自愈完整链路: 失败分类 → 策略路由 → 审计写入 → 指标埋点。
使用真实测试库（sync db fixture 事务隔离），browser 用 Mock
（Playwright 浏览器无法在测试环境真实启动）。

测试用例:
    - load_delay 场景: 定位超时 → retry → 不触发 AI 自愈
    - env_noise 场景: 网络错误 → skip → 不触发自愈
    - element_gone 场景: 元素不存在 → ai_heal → 审计写入
    - dom_changed 场景: DOM 变更 → ai_heal → 审计写入
    - 置信度低: confidence < 0.7 → 不回写定位器 → 审计 low_confidence=True
    - 置信度高: confidence ≥ 0.7 → 回写定位器 → 审计 low_confidence=False
    - Token 治理: 单次超限 → 跳过 AI 自愈
    - Token 治理: 日预算耗尽 → 跳过 AI 自愈
    - 灰度开关: 项目配置 enabled=False → 不触发自愈
    - 灰度开关: 全局关 → 不触发自愈
    - 指标埋点: 自愈后 Prometheus 指标递增

设计要点:
    1. browser 用 MagicMock + AsyncMock（参考 tests/test_self_healing.py 既有方式）
    2. db/审计/定位器用真实测试库，db fixture 事务隔离自动清理
    3. _execute_action_directly 用 AsyncMock side_effect 控制定位失败
    4. _ai_self_heal_action 用 AsyncMock 返回 HealResult 控制 AI 自愈结果
    5. monkeypatch AI_SELF_HEALING_ENABLED=True 与 RETRY_WAIT_SECONDS=0
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.self_healing_audit import SelfHealingAudit
from app.models.test_case import TestCase, TestStep
from app.services.self_healing import HealResult
from app.services.self_healing.metrics import (
    SELF_HEAL_ATTEMPTS,
    SELF_HEAL_SUCCESS,
    SELF_HEAL_FAILURE,
    SELF_HEAL_FAILURE_TYPE,
)
from app.services.test_execution_engine import (
    TestExecutionEngineV2,
    ActionType,
    StepExecutionError,
)


# ============================================================================
# 辅助函数与 fixture
# ============================================================================


def _make_mock_browser(dom_snapshot: str = "") -> MagicMock:
    """构造 Mock 浏览器，execute_javascript 返回指定 DOM 快照。

    capture_dom_snapshot 内部调用 browser.execute_javascript，
    Mock 为 AsyncMock 返回空字符串以跳过 DOM 校正，保留 error 分类。
    """
    browser = MagicMock()
    browser.execute_javascript = AsyncMock(return_value=dom_snapshot)
    browser.page = None
    browser.browser = None
    browser.playwright = None
    return browser


def _make_engine(db, browser=None) -> TestExecutionEngineV2:
    """构造测试引擎实例，默认关闭 AI 识别与测试数据参数化。"""
    engine = TestExecutionEngineV2(
        db=db,
        enable_ai_recognition=False,
        enable_test_data_param=False,
    )
    if browser is not None:
        engine.browser = browser
    return engine


def _get_counter_value(counter) -> float:
    """获取 Prometheus Counter 当前累计值。"""
    return counter._value.get()


@pytest.fixture
def seed_data(db, testUser):
    """创建自愈集成测试所需的项目/用例/步骤/定位器。

    db fixture 事务隔离保证测试后自动回滚，无需手动清理。
    """
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        name=f"sh_integration_{suffix}",
        user_id=testUser.id,
        description="自愈集成测试项目",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()

    case = TestCase(
        project_id=project.id,
        case_no=f"SH-INT-{suffix}",
        module="自愈集成",
        title="自愈集成测试用例",
        precondition="无",
        steps_json=[{"step": 1, "action": "点击按钮", "param": ""}],
        expected_result="成功",
        priority=1,
        case_type="UI",
        generate_status=1,
    )
    db.add(case)
    db.flush()

    step = TestStep(
        test_case_id=case.id,
        step_number=1,
        action="点击登录按钮",
        action_type="click",
        expected_result="跳转首页",
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

    return {
        "project": project,
        "case": case,
        "step": step,
        "locator": locator,
    }


def _count_audits(db, case_id: int) -> int:
    """统计指定用例的审计记录数。"""
    return (
        db.query(SelfHealingAudit)
        .filter(SelfHealingAudit.test_case_id == case_id)
        .count()
    )


def _get_latest_audit(db, case_id: int) -> SelfHealingAudit | None:
    """获取指定用例的最新审计记录。"""
    return (
        db.query(SelfHealingAudit)
        .filter(SelfHealingAudit.test_case_id == case_id)
        .order_by(SelfHealingAudit.id.desc())
        .first()
    )


# ============================================================================
# 失败分类与策略路由测试
# ============================================================================


class TestFailureClassificationAndRouting:
    """失败分类 → 策略路由 → 审计写入 端到端测试。"""

    @pytest.mark.asyncio
    async def test_load_delay_retry_strategy(
        self, db, seed_data, monkeypatch
    ):
        """load_delay 场景: 定位超时 → retry 等待 → 重试成功 → 不触发 AI 自愈。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)
        monkeypatch.setattr(settings, "AI_SELF_HEALING_RETRY_WAIT_SECONDS", 0)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        # 第一次抛超时异常（触发自愈），第二次成功（retry）
        engine._execute_action_directly = AsyncMock(side_effect=[
            Exception("timeout waiting for element"),
            None,
        ])
        # AI 自愈不应被调用
        engine._ai_self_heal_action = AsyncMock(return_value=None)

        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)
        success_before = _get_counter_value(SELF_HEAL_SUCCESS)

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        # 验证 AI 自愈未被调用
        engine._ai_self_heal_action.assert_not_called()

        # 验证指标递增
        assert _get_counter_value(SELF_HEAL_ATTEMPTS) > attempts_before
        assert _get_counter_value(SELF_HEAL_SUCCESS) > success_before

        # 验证 retry 成功路径不写审计（仅失败路径写审计）
        # retry 成功不调用 _audit_failure
        db.expire_all()
        latest_audit = _get_latest_audit(db, case.id)
        # 成功路径无新审计（或如果有，strategy 不为 retry）
        if latest_audit is not None:
            # 确保不是本次 retry 写的失败审计
            assert latest_audit.strategy != "retry" or latest_audit.id < locator.id

    @pytest.mark.asyncio
    async def test_env_noise_skip_strategy(
        self, db, seed_data, monkeypatch
    ):
        """env_noise 场景: 网络错误 → skip → 不触发 AI 自愈 → 审计写入。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        # 错误消息包含 "network"（env_noise 关键词）和 "not found"（定位关键词）
        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("network error: element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=None)

        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)

        with pytest.raises(Exception, match="network error"):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        # 验证 AI 自愈未被调用
        engine._ai_self_heal_action.assert_not_called()

        # 验证指标递增
        assert _get_counter_value(SELF_HEAL_ATTEMPTS) > attempts_before

        # 验证审计写入 strategy="skip"
        db.expire_all()
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.strategy == "skip"
        assert audit.failure_type == "env_noise"

    @pytest.mark.asyncio
    async def test_element_gone_ai_heal_strategy(
        self, db, seed_data, monkeypatch
    ):
        """element_gone 场景: 元素不存在 → ai_heal → 审计写入 → 定位器回写。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=HealResult(
            selector=".new-login-btn",
            confidence=0.9,
            token_cost=100,
            strategy="mcp",
        ))

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        # 验证定位器已回写
        db.expire_all()
        updated_locator = db.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert updated_locator.css_selector == ".new-login-btn"
        assert updated_locator.source == "ai_self_healing"

        # 验证审计写入
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.strategy == "mcp"
        assert audit.failure_type == "element_gone"
        assert audit.low_confidence is False
        assert audit.new_selector == ".new-login-btn"
        assert audit.old_selector == ".old-login-btn"

    @pytest.mark.asyncio
    async def test_dom_changed_ai_heal_strategy(
        self, db, seed_data, monkeypatch
    ):
        """dom_changed 场景: DOM 变更 → ai_heal → 审计写入。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        # "selector" 匹配定位关键词，但不匹配 env_noise/element_gone/load_delay
        # → 默认分类 dom_changed
        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("selector validation failed")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=HealResult(
            selector=".healed-btn",
            confidence=0.85,
            token_cost=150,
            strategy="vision",
        ))

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        # 验证审计写入 failure_type="dom_changed"
        db.expire_all()
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.failure_type == "dom_changed"
        assert audit.strategy == "vision"
        assert audit.new_selector == ".healed-btn"


# ============================================================================
# 置信度处理测试
# ============================================================================


class TestConfidenceHandling:
    """置信度阈值处理: 低于 0.7 不回写定位器，仅写审计。"""

    @pytest.mark.asyncio
    async def test_low_confidence_no_writeback(
        self, db, seed_data, monkeypatch
    ):
        """置信度 0.5 < 0.7 → 不回写 element_locators → 审计 low_confidence=True。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)
        # 确保置信度阈值为 0.7
        monkeypatch.setattr(settings, "AI_SELF_HEALING_CONFIDENCE_THRESHOLD", 0.7)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=HealResult(
            selector=".low-conf-btn",
            confidence=0.5,  # 低于阈值
            token_cost=80,
            strategy="mcp",
        ))

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        # 验证定位器未回写（css_selector 保持旧值）
        db.expire_all()
        updated_locator = db.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert updated_locator.css_selector == ".old-login-btn"

        # 验证审计 low_confidence=True
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.low_confidence is True
        assert audit.confidence == 0.5

    @pytest.mark.asyncio
    async def test_high_confidence_writeback(
        self, db, seed_data, monkeypatch
    ):
        """置信度 0.9 ≥ 0.7 → 回写 element_locators → 审计 low_confidence=False。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)
        monkeypatch.setattr(settings, "AI_SELF_HEALING_CONFIDENCE_THRESHOLD", 0.7)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=HealResult(
            selector=".high-conf-btn",
            confidence=0.9,  # 高于阈值
            token_cost=120,
            strategy="mcp",
        ))

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        # 验证定位器已回写
        db.expire_all()
        updated_locator = db.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert updated_locator.css_selector == ".high-conf-btn"

        # 验证审计 low_confidence=False
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.low_confidence is False
        assert float(audit.confidence) == 0.9


# ============================================================================
# Token 预算治理测试
# ============================================================================


class TestTokenBudget:
    """Token 治理: 单次超限 / 日预算耗尽 → 跳过 AI 自愈。"""

    @pytest.mark.asyncio
    async def test_single_call_limit_skips_ai_heal(
        self, db, seed_data, monkeypatch
    ):
        """单次 Token 预估超限 → 熔断 AI 自愈 → 不调用 _local_ai_self_heal。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )

        # 设置 mock _token_guard：单次超限
        engine._token_guard = MagicMock()
        engine._token_guard.is_daily_budget_exhausted.return_value = False
        engine._token_guard.check_single_call.return_value = True  # 单次超限
        engine._token_guard.consume = MagicMock()

        # Mock _local_ai_self_heal 验证未被调用
        engine._local_ai_self_heal = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="element not found"):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        # 验证 AI 自愈被熔断，_local_ai_self_heal 未被调用
        engine._local_ai_self_heal.assert_not_called()

        # 验证定位器未回写
        db.expire_all()
        updated_locator = db.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert updated_locator.css_selector == ".old-login-btn"

    @pytest.mark.asyncio
    async def test_daily_budget_exhausted_skips_ai_heal(
        self, db, seed_data, monkeypatch
    ):
        """日预算耗尽 → 熔断 AI 自愈 → 不调用 _local_ai_self_heal。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]
        case = seed_data["case"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )

        # 设置 mock _token_guard：日预算耗尽
        engine._token_guard = MagicMock()
        engine._token_guard.is_daily_budget_exhausted.return_value = True
        engine._token_guard.check_single_call.return_value = False
        engine._token_guard.consume = MagicMock()

        engine._local_ai_self_heal = AsyncMock(return_value=None)

        with pytest.raises(Exception, match="element not found"):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        # 验证 AI 自愈被熔断
        engine._local_ai_self_heal.assert_not_called()

        # 验证定位器未回写
        db.expire_all()
        updated_locator = db.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert updated_locator.css_selector == ".old-login-btn"

        # 验证审计写入（失败路径 strategy="ai_heal"）
        audit = _get_latest_audit(db, case.id)
        assert audit is not None
        assert audit.strategy == "ai_heal"
        assert audit.token_cost == 0


# ============================================================================
# 灰度开关测试
# ============================================================================


class TestGraySwitch:
    """灰度开关: 项目配置 enabled=False / 全局关 → 不触发自愈。"""

    @pytest.mark.asyncio
    async def test_project_config_disabled_skips_healing(
        self, db, seed_data, monkeypatch
    ):
        """项目配置 enabled=False → 不触发自愈 → 直接抛原始异常。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        project = seed_data["project"]
        step = seed_data["step"]
        case = seed_data["case"]
        locator = seed_data["locator"]

        # 设置项目配置 enabled=False
        project.config = {
            "self_healing_config": {
                "enabled": False,
                "strategies": ["mcp"],
                "token_limit": 2000,
            }
        }
        db.flush()

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=None)

        audits_before = _count_audits(db, case.id)
        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)

        with pytest.raises(Exception, match="element not found"):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        # 验证自愈未触发：无新审计、指标未递增
        engine._ai_self_heal_action.assert_not_called()
        assert _count_audits(db, case.id) == audits_before
        assert _get_counter_value(SELF_HEAL_ATTEMPTS) == attempts_before

    @pytest.mark.asyncio
    async def test_global_switch_disabled_skips_healing(
        self, db, seed_data, monkeypatch
    ):
        """全局开关关 → 不触发自愈 → 直接抛原始异常。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)

        step = seed_data["step"]
        case = seed_data["case"]
        locator = seed_data["locator"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=None)

        audits_before = _count_audits(db, case.id)
        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)

        with pytest.raises(Exception, match="element not found"):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        # 验证自愈未触发
        engine._ai_self_heal_action.assert_not_called()
        assert _count_audits(db, case.id) == audits_before
        assert _get_counter_value(SELF_HEAL_ATTEMPTS) == attempts_before


# ============================================================================
# 指标埋点测试
# ============================================================================


class TestMetricsRecording:
    """自愈后 Prometheus 指标递增验证。"""

    @pytest.mark.asyncio
    async def test_metrics_increment_after_ai_heal_success(
        self, db, seed_data, monkeypatch
    ):
        """ai_heal 成功 → SELF_HEAL_ATTEMPTS / SELF_HEAL_SUCCESS 递增。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("element not found")
        )
        engine._ai_self_heal_action = AsyncMock(return_value=HealResult(
            selector=".metrics-btn",
            confidence=0.9,
            token_cost=100,
            strategy="mcp",
        ))

        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)
        success_before = _get_counter_value(SELF_HEAL_SUCCESS)

        await engine._execute_with_self_healing(
            step=step,
            locator_record=locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )

        assert _get_counter_value(SELF_HEAL_ATTEMPTS) > attempts_before
        assert _get_counter_value(SELF_HEAL_SUCCESS) > success_before

    @pytest.mark.asyncio
    async def test_metrics_increment_after_skip_failure(
        self, db, seed_data, monkeypatch
    ):
        """env_noise skip → SELF_HEAL_ATTEMPTS / SELF_HEAL_FAILURE 递增。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("network error: element not found")
        )

        attempts_before = _get_counter_value(SELF_HEAL_ATTEMPTS)
        failure_before = _get_counter_value(SELF_HEAL_FAILURE)

        with pytest.raises(Exception):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        assert _get_counter_value(SELF_HEAL_ATTEMPTS) > attempts_before
        assert _get_counter_value(SELF_HEAL_FAILURE) > failure_before

    @pytest.mark.asyncio
    async def test_failure_type_metric_labeled_correctly(
        self, db, seed_data, monkeypatch
    ):
        """env_noise 失败 → SELF_HEAL_FAILURE_TYPE labels(type=env_noise) 递增。"""
        monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)

        step = seed_data["step"]
        locator = seed_data["locator"]

        browser = _make_mock_browser(dom_snapshot="")
        engine = _make_engine(db, browser=browser)

        engine._execute_action_directly = AsyncMock(
            side_effect=Exception("network error: element not found")
        )

        env_noise_before = _get_counter_value(
            SELF_HEAL_FAILURE_TYPE.labels(type="env_noise")
        )

        with pytest.raises(Exception):
            await engine._execute_with_self_healing(
                step=step,
                locator_record=locator,
                action_type=ActionType.CLICK,
                action_info={"text": "点击登录按钮"},
            )

        env_noise_after = _get_counter_value(
            SELF_HEAL_FAILURE_TYPE.labels(type="env_noise")
        )
        assert env_noise_after > env_noise_before
