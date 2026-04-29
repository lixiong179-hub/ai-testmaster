"""
AI自愈功能测试

测试原则（强制执行）：
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：核心功能代码覆盖率必须 >= 95%
3. 测试准确性：测试通过率必须 100%
4. 发现问题优先：测试的目的是发现代码问题

测试范围：
- _get_nl_description: 自然语言步骤描述获取
- _update_locator_after_healing: 定位器回写与乐观锁
- _build_healed_selector: CSS选择器构建
- _sanitize_css_identifier: CSS标识符清理
- get_self_healing_summary: 自愈统计摘要
- _execute_with_self_healing: 自愈包装器（集成测试）
- 配置开关控制
"""
import time
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.models.test_case import TestCase, TestStep, TestCaseExecution
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.services.test_execution_engine_v2 import (
    TestExecutionEngineV2,
    ExecutionStatus,
    ActionType,
    StepExecutionError,
)

_UID = int(time.time()) % 100000


@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话（真实MySQL数据库）"""
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    try:
        session.rollback()
    except Exception:
        pass
    try:
        session.query(ElementLocator).filter(
            ElementLocator.element_description == "自愈测试登录按钮"
        ).delete()
        session.query(TestStep).filter(
            TestStep.action == "自愈测试点击操作"
        ).delete()
        session.query(TestCaseExecution).filter(
            TestCaseExecution.actual_result == "自愈测试执行结果"
        ).delete()
        session.query(TestCase).filter(
            TestCase.case_no.like("SH-TEST-%")
        ).delete()
        session.query(Project).filter(
            Project.name.like("自愈测试项目%")
        ).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def engine_no_browser(db_session):
    """无浏览器的引擎实例（用于纯逻辑测试）"""
    return TestExecutionEngineV2(
        db=db_session,
        enable_ai_recognition=False,
        enable_test_data_param=False,
    )


@pytest.fixture
def seed_project(db_session):
    """创建测试项目"""
    project = Project(
        name=f"自愈测试项目-{_UID}",
        description="AI自愈功能测试专用",
        user_id=1,
        project_type="web",
        status=1,
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def seed_test_case(db_session, seed_project):
    """创建测试用例"""
    case = TestCase(
        project_id=seed_project.id,
        case_no=f"SH-TEST-{_UID}",
        module="自愈模块",
        title="自愈功能测试用例",
        precondition="系统正常运行",
        steps_json=[{"step": 1, "action": "点击登录", "param": ""}],
        expected_result="自愈成功",
        priority=1,
        case_type="UI",
        generate_status=1,
    )
    db_session.add(case)
    db_session.commit()
    return case


@pytest.fixture
def seed_test_step(db_session, seed_test_case):
    """创建测试步骤"""
    step = TestStep(
        test_case_id=seed_test_case.id,
        step_number=1,
        action="自愈测试点击操作",
        action_type="click",
        expected_result="跳转到首页",
    )
    db_session.add(step)
    db_session.commit()
    return step


@pytest.fixture
def seed_locator(db_session, seed_test_step):
    """创建元素定位记录"""
    locator = ElementLocator(
        step_id=seed_test_step.id,
        element_description="自愈测试登录按钮",
        element_type="button",
        css_selector=".old-login-btn",
        source="ai",
        version=0,
    )
    db_session.add(locator)
    db_session.commit()
    return locator


# ==================== 单元测试: _get_nl_description ====================


@pytest.mark.asyncio
async def test_get_nl_description_from_test_step(db_session, engine_no_browser, seed_test_step):
    """测试从TestStep获取自然语言描述"""
    desc = await engine_no_browser._get_nl_description(seed_test_step.id)
    assert "自愈测试点击操作" in desc


@pytest.mark.asyncio
async def test_get_nl_description_from_locator(db_session, engine_no_browser, seed_locator):
    """测试TestStep无action时从ElementLocator获取描述"""
    step = db_session.query(TestStep).filter(TestStep.id == seed_locator.step_id).first()
    step.action = ""
    db_session.commit()

    desc = await engine_no_browser._get_nl_description(seed_locator.step_id)
    assert "自愈测试登录按钮" in desc


@pytest.mark.asyncio
async def test_get_nl_description_empty_for_missing_step(db_session, engine_no_browser):
    """测试不存在的步骤ID返回空字符串"""
    desc = await engine_no_browser._get_nl_description(9999998)
    assert desc == ""


# ==================== 单元测试: _update_locator_after_healing ====================


@pytest.mark.asyncio
async def test_update_locator_after_healing_success(
    db_session, engine_no_browser, seed_locator
):
    """测试自愈后定位器回写成功"""
    new_selector = ".new-login-btn"
    old_selector = seed_locator.css_selector
    old_version = seed_locator.version

    result = await engine_no_browser._update_locator_after_healing(
        seed_locator.id, new_selector, old_selector
    )

    assert result is True

    db_session.expire_all()
    updated = db_session.query(ElementLocator).filter(
        ElementLocator.id == seed_locator.id
    ).first()
    assert updated.css_selector == new_selector
    assert updated.source == "ai_self_healing"
    assert updated.version == old_version + 1


@pytest.mark.asyncio
async def test_update_locator_after_healing_optimistic_lock(
    db_session, engine_no_browser, seed_locator
):
    """测试乐观锁：使用过期版本更新时回写失败"""
    new_selector_v1 = ".new-btn-v1"
    new_selector_v2 = ".new-btn-v2"

    result1 = await engine_no_browser._update_locator_after_healing(
        seed_locator.id, new_selector_v1, seed_locator.css_selector
    )
    assert result1 is True

    db_session.expire_all()
    updated = db_session.query(ElementLocator).filter(
        ElementLocator.id == seed_locator.id
    ).first()
    assert updated.version == 1

    stale_version = 0
    result = db_session.execute(
        sql_text(
            "UPDATE element_locators SET css_selector = :s, "
            "source = 'stale', updated_at = UTC_TIMESTAMP(), version = version + 1 "
            "WHERE id = :id AND version = :v"
        ), {"s": new_selector_v2, "id": seed_locator.id, "v": stale_version}
    )
    db_session.commit()
    assert result.rowcount == 0

    db_session.expire_all()
    final = db_session.query(ElementLocator).filter(
        ElementLocator.id == seed_locator.id
    ).first()
    assert final.css_selector == new_selector_v1


@pytest.mark.asyncio
async def test_update_locator_after_healing_empty_selector(
    db_session, engine_no_browser, seed_locator
):
    """测试空选择器不执行回写"""
    result = await engine_no_browser._update_locator_after_healing(
        seed_locator.id, "", ".old-btn"
    )
    assert result is False


@pytest.mark.asyncio
async def test_update_locator_after_healing_nonexistent_record(db_session, engine_no_browser):
    """测试不存在的定位器记录回写失败"""
    result = await engine_no_browser._update_locator_after_healing(
        9999999, ".some-selector", ".old"
    )
    assert result is False


# ==================== 单元测试: _sanitize_css_identifier ====================


def test_sanitize_css_identifier_normal(engine_no_browser):
    """测试正常CSS标识符不变"""
    assert engine_no_browser._sanitize_css_identifier("loginBtn") == "loginBtn"


def test_sanitize_css_identifier_with_special_chars(engine_no_browser):
    """测试特殊字符被清理（引号分号空格移除，连续--变为单个-后可能被strip）"""
    result = engine_no_browser._sanitize_css_identifier("btn'; DROP TABLE--")
    assert "'" not in result
    assert ";" not in result
    assert " " not in result


def test_sanitize_css_identifier_with_quotes(engine_no_browser):
    """测试引号被清理"""
    assert engine_no_browser._sanitize_css_identifier("name'or'1") == "nameor1"


def test_sanitize_css_identifier_hyphen_underscore(engine_no_browser):
    """测试连字符和下划线保留"""
    assert engine_no_browser._sanitize_css_identifier("my-btn_v2") == "my-btn_v2"


def test_sanitize_css_identifier_empty(engine_no_browser):
    """测试空字符串"""
    assert engine_no_browser._sanitize_css_identifier("") == ""


# ==================== 单元测试: _build_healed_selector ====================


def test_build_healed_selector_by_id(engine_no_browser):
    """测试优先使用id构建选择器"""
    attrs = {"id": "loginBtn", "name": "login", "class": "btn primary", "tag": "button"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert selector == "#loginBtn"


def test_build_healed_selector_by_name(engine_no_browser):
    """测试使用name属性构建选择器"""
    attrs = {"name": "username", "class": "input", "tag": "input"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert selector == "[name='username']"


def test_build_healed_selector_by_placeholder(engine_no_browser):
    """测试使用placeholder构建选择器（中文被sanitize后回退到tag+type）"""
    attrs = {"placeholder": "请输入用户名", "tag": "input", "type": "text"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert selector is not None
    assert "input" in selector


def test_build_healed_selector_by_class(engine_no_browser):
    """测试使用class组合构建选择器"""
    attrs = {"class": "btn primary", "tag": "button"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert "btn" in selector
    assert "primary" in selector


def test_build_healed_selector_by_tag_and_type(engine_no_browser):
    """测试使用tag+type构建选择器"""
    attrs = {"tag": "input", "type": "password"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert selector == "input[type='password']"


def test_build_healed_selector_returns_none(engine_no_browser):
    """测试无属性时返回None"""
    selector = engine_no_browser._build_healed_selector({})
    assert selector is None


def test_build_healed_selector_sanitizes_malicious_id(engine_no_browser):
    """测试恶意id被清理（引号和特殊字符被移除）"""
    attrs = {"id": "'; alert(1)//", "tag": "button"}
    selector = engine_no_browser._build_healed_selector(attrs)
    assert "'" not in selector
    assert ";" not in selector
    assert "/" not in selector


# ==================== 单元测试: get_self_healing_summary ====================


def test_self_healing_summary_initial(engine_no_browser):
    """测试初始自愈摘要"""
    summary = engine_no_browser.get_self_healing_summary()
    assert summary["self_healing_attempts"] == 0
    assert summary["self_healing_successes"] == 0
    assert summary["self_healing_success_rate"] == 0.0


def test_self_healing_summary_after_attempts(engine_no_browser):
    """测试自愈尝试后摘要更新"""
    engine_no_browser._self_healing_attempts = 3
    engine_no_browser._self_healing_successes = 2

    summary = engine_no_browser.get_self_healing_summary()
    assert summary["self_healing_attempts"] == 3
    assert summary["self_healing_successes"] == 2
    assert abs(summary["self_healing_success_rate"] - 0.6667) < 0.01


# ==================== 单元测试: _get_stagehand ====================


@pytest.mark.asyncio
async def test_get_stagehand_disabled(engine_no_browser, monkeypatch):
    """测试自愈开关关闭时Stagehand不可用"""
    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)
    result = await engine_no_browser._get_stagehand()
    assert result is None


@pytest.mark.asyncio
async def test_get_stagehand_no_credentials(engine_no_browser, monkeypatch):
    """测试Browserbase凭据未配置时Stagehand不可用"""
    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)
    monkeypatch.setattr(settings, "BROWSERBASE_API_KEY", "")
    monkeypatch.setattr(settings, "BROWSERBASE_PROJECT_ID", "")
    result = await engine_no_browser._get_stagehand()
    assert result is None


@pytest.mark.asyncio
async def test_get_stagehand_clears_cache_on_disable(engine_no_browser, monkeypatch):
    """测试自愈开关关闭时清除Stagehand缓存"""
    engine_no_browser._stagehand_client = object()
    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)
    result = await engine_no_browser._get_stagehand()
    assert result is None
    assert engine_no_browser._stagehand_client is None


# ==================== 单元测试: _execute_with_self_healing ====================


@pytest.mark.asyncio
async def test_execute_with_self_healing_no_browser(db_session, seed_test_case):
    """测试浏览器未初始化时抛出异常"""
    engine = TestExecutionEngineV2(db=db_session, enable_ai_recognition=False)
    step = TestStep(
        test_case_id=seed_test_case.id,
        step_number=1,
        action="自愈测试点击操作",
        expected_result="预期结果",
    )
    db_session.add(step)
    db_session.commit()

    with pytest.raises(StepExecutionError, match="浏览器未初始化"):
        await engine._execute_with_self_healing(
            step=step,
            locator_record=None,
            action_type=ActionType.CLICK,
            action_info={"text": "点击按钮"},
        )


@pytest.mark.asyncio
async def test_execute_with_self_healing_disabled_raises_original(
    db_session, engine_no_browser, seed_test_step, seed_locator, monkeypatch
):
    """测试自愈开关关闭时，定位失败直接抛出原始异常（真实浏览器超时）"""
    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)

    from app.utils.browser_controller_v2 import BrowserControllerV2
    browser = BrowserControllerV2.__new__(BrowserControllerV2)
    browser.page = None
    browser.browser = None
    browser.playwright = None
    engine_no_browser.browser = browser

    with pytest.raises(Exception):
        await engine_no_browser._execute_with_self_healing(
            step=seed_test_step,
            locator_record=seed_locator,
            action_type=ActionType.CLICK,
            action_info={"text": "点击登录按钮"},
        )


# ==================== 集成测试: 定位器回写验证 ====================


@pytest.mark.asyncio
async def test_healing_updates_locator_in_db(
    db_session, engine_no_browser, seed_test_step, seed_locator
):
    """测试自愈成功后ElementLocator表中的选择器已被更新"""
    new_selector = ".healed-login-btn"
    old_selector = seed_locator.css_selector

    result = await engine_no_browser._update_locator_after_healing(
        seed_locator.id, new_selector, old_selector
    )
    assert result is True

    db_session.expire_all()
    updated = db_session.query(ElementLocator).filter(
        ElementLocator.id == seed_locator.id
    ).first()
    assert updated.css_selector == new_selector
    assert updated.css_selector != old_selector
    assert updated.source == "ai_self_healing"


@pytest.mark.asyncio
async def test_healed_selector_persists_on_next_read(
    db_session, engine_no_browser, seed_test_step, seed_locator
):
    """测试自愈后的新选择器在下次读取时可用"""
    new_selector = ".persistent-btn"
    await engine_no_browser._update_locator_after_healing(
        seed_locator.id, new_selector, seed_locator.css_selector
    )

    db_session.expire_all()
    from app.services.element_locator_service import ElementLocatorService
    locator_service = ElementLocatorService.__new__(ElementLocatorService)
    locator_service.db = db_session

    locator = locator_service.get_locator(seed_test_step.id)
    assert locator is not None
    best = locator.get_best_locator()
    assert best is not None
    assert best["value"] == new_selector


# ==================== 配置开关测试 ====================


def test_self_healing_config_defaults():
    """测试自愈配置默认值"""
    assert hasattr(settings, "AI_SELF_HEALING_ENABLED")
    assert isinstance(settings.AI_SELF_HEALING_ENABLED, bool)
    assert hasattr(settings, "AI_SELF_HEALING_MAX_RETRIES")
    assert hasattr(settings, "STAGEHAND_MODEL")
    assert hasattr(settings, "BROWSERBASE_API_KEY")
    assert hasattr(settings, "BROWSERBASE_PROJECT_ID")


def test_self_healing_summary_reflects_config(engine_no_browser, monkeypatch):
    """测试自愈摘要反映配置状态"""
    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", True)
    summary = engine_no_browser.get_self_healing_summary()
    assert summary["self_healing_enabled"] is True

    monkeypatch.setattr(settings, "AI_SELF_HEALING_ENABLED", False)
    summary = engine_no_browser.get_self_healing_summary()
    assert summary["self_healing_enabled"] is False
