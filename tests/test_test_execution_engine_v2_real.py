"""
测试执行引擎V2真实测试

测试原则（强制执行）：
1. 真实执行优先：所有测试必须使用真实环境，严禁使用Mock
2. 覆盖率要求：单元测试覆盖率必须 >= 95%
3. 测试准确性：测试通过率必须 100%
4. 发现问题优先：测试的目的是发现代码问题

注意：这些测试使用真实浏览器和MySQL数据库，需要安装Playwright
"""
import pytest
import pytest_asyncio
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.database import Base
from app.models.test_case import TestCase, TestStep, TestCaseExecution
from app.models.project import Project
from app.services.test_execution_engine_v2 import (
    TestExecutionEngineV2,
    ExecutionStatus,
    ActionType,
    StepExecutionResult,
    TestExecutionResult,
    ExecutionError,
    StepExecutionError,
    VerificationError
)
from app.utils.browser_controller_v2 import create_browser_controller_v2
from app.utils.unified_vision_model import get_default_vision_model


# ==================== Fixtures ====================

@pytest.fixture(scope="function")
def db_session():
    """创建测试数据库会话（真实MySQL数据库）"""
    engine = create_engine(settings.DATABASE_URL)
    
    # 创建测试表
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    yield session
    
    # 清理测试数据
    session.query(TestCaseExecution).filter(TestCaseExecution.test_case_id >= 10000).delete()
    session.query(TestStep).filter(TestStep.test_case_id >= 10000).delete()
    session.query(TestCase).filter(TestCase.id >= 10000).delete()
    session.query(Project).filter(Project.id >= 10000).delete()
    session.commit()
    session.close()


@pytest_asyncio.fixture
async def browser():
    """真实浏览器控制器 fixture"""
    controller = await create_browser_controller_v2(
        browser_type="chromium",
        headless=True
    )
    yield controller
    await controller.close()


@pytest_asyncio.fixture
async def vision_model():
    """真实视觉模型 fixture"""
    return get_default_vision_model()


@pytest_asyncio.fixture
async def execution_engine(db_session, browser, vision_model):
    """真实测试执行引擎 fixture"""
    engine = TestExecutionEngineV2(
        db=db_session,
        browser=browser,
        vision_model=vision_model
    )
    yield engine


@pytest.fixture
def test_project(db_session):
    """创建测试项目"""
    project = Project(
        id=10001,
        name="测试项目",
        description="用于测试的项目",
        user_id=1,
        project_type="web",
        web_env_configs={"test": {"url": "https://www.example.com"}},
        status=1
    )
    db_session.add(project)
    db_session.commit()
    return project


@pytest.fixture
def test_case(db_session, test_project):
    """创建测试用例"""
    test_case = TestCase(
        id=10001,
        project_id=test_project.id,
        case_no="TC001",
        module="登录模块",
        title="测试登录功能",
        precondition="系统正常运行",
        steps_json=[
            {"step": 1, "action": "打开页面", "param": ""},
            {"step": 2, "action": "点击按钮", "param": ""}
        ],
        expected_result="登录成功",
        priority=1,
        case_type="UI",
        generate_status=1
    )
    db_session.add(test_case)
    db_session.commit()
    return test_case


@pytest.fixture
def test_steps(db_session, test_case):
    """创建测试步骤"""
    steps = []
    for i in range(1, 3):
        step = TestStep(
            test_case_id=test_case.id,
            step_number=i,
            action=f"步骤{i}: 测试操作",
            expected_result=f"预期结果{i}"
        )
        db_session.add(step)
        steps.append(step)
    db_session.commit()
    return steps


# ==================== 枚举类测试 ====================

def test_execution_status_values():
    """测试执行状态枚举值"""
    assert ExecutionStatus.PENDING.value == "pending"
    assert ExecutionStatus.RUNNING.value == "running"
    assert ExecutionStatus.PASSED.value == "passed"
    assert ExecutionStatus.FAILED.value == "failed"
    assert ExecutionStatus.SKIPPED.value == "skipped"
    assert ExecutionStatus.ERROR.value == "error"


def test_action_type_values():
    """测试操作类型枚举值"""
    assert ActionType.CLICK.value == "click"
    assert ActionType.INPUT.value == "input"
    assert ActionType.NAVIGATE.value == "navigate"
    assert ActionType.VERIFY.value == "verify"
    assert ActionType.WAIT.value == "wait"
    assert ActionType.SCROLL.value == "scroll"
    assert ActionType.HOVER.value == "hover"
    assert ActionType.SELECT.value == "select"
    assert ActionType.CAPTCHA.value == "captcha"
    assert ActionType.REFRESH.value == "refresh"
    assert ActionType.KEYPRESS.value == "keypress"


# ==================== 结果类测试 ====================

def test_step_execution_result_creation():
    """测试步骤执行结果创建"""
    result = StepExecutionResult(
        step_number=1,
        action="点击按钮",
        status=ExecutionStatus.PASSED,
        start_time=datetime.utcnow()
    )
    
    assert result.step_number == 1
    assert result.action == "点击按钮"
    assert result.status == ExecutionStatus.PASSED
    assert result.duration_ms == 0
    
    # 测试to_dict方法
    result_dict = result.to_dict()
    assert result_dict["step_number"] == 1
    assert result_dict["action"] == "点击按钮"
    assert result_dict["status"] == "passed"


def test_step_execution_result_with_error():
    """测试带错误的步骤执行结果"""
    result = StepExecutionResult(
        step_number=2,
        action="输入文本",
        status=ExecutionStatus.FAILED,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        duration_ms=1000,
        error_message="元素未找到"
    )
    
    result_dict = result.to_dict()
    assert result_dict["status"] == "failed"
    assert result_dict["error_message"] == "元素未找到"
    assert result_dict["duration_ms"] == 1000


def test_test_execution_result_creation():
    """测试测试执行结果创建"""
    result = TestExecutionResult(
        execution_id=1,
        test_case_id=100,
        status=ExecutionStatus.PASSED,
        start_time=datetime.utcnow()
    )
    
    assert result.execution_id == 1
    assert result.test_case_id == 100
    assert result.status == ExecutionStatus.PASSED
    assert len(result.step_results) == 0
    
    # 测试to_dict方法
    result_dict = result.to_dict()
    assert result_dict["execution_id"] == 1
    assert result_dict["status"] == "passed"


# ==================== 异常类测试 ====================

def test_execution_error():
    """测试执行错误异常"""
    error = ExecutionError("测试错误")
    assert str(error) == "测试错误"
    
    # 测试异常链
    try:
        try:
            raise ValueError("原始错误")
        except ValueError as original_error:
            raise ExecutionError("包装错误") from original_error
    except ExecutionError as wrapped_error:
        assert wrapped_error.__cause__ is not None
        assert isinstance(wrapped_error.__cause__, ValueError)


def test_step_execution_error():
    """测试步骤执行错误异常"""
    error = StepExecutionError("步骤执行失败")
    assert str(error) == "步骤执行失败"
    assert isinstance(error, ExecutionError)


def test_verification_error():
    """测试验证错误异常"""
    error = VerificationError("验证失败")
    assert str(error) == "验证失败"
    assert isinstance(error, ExecutionError)


# ==================== 引擎初始化测试 ====================

@pytest.mark.asyncio
async def test_execution_engine_initialization(db_session, browser, vision_model):
    """测试执行引擎初始化"""
    engine = TestExecutionEngineV2(
        db=db_session,
        browser=browser,
        vision_model=vision_model
    )
    
    assert engine.db == db_session
    assert engine.browser == browser
    assert engine.vision_model == vision_model
    assert engine._current_execution is None
    assert len(engine._step_results) == 0


@pytest.mark.asyncio
async def test_execution_engine_without_browser(db_session):
    """测试没有浏览器的执行引擎"""
    engine = TestExecutionEngineV2(db=db_session)
    
    assert engine.db == db_session
    assert engine.browser is None
    assert engine.vision_model is None


# ==================== 动作解析测试 ====================

@pytest.mark.asyncio
async def test_parse_navigate_action(execution_engine):
    """测试解析导航动作"""
    action_info = execution_engine._parse_step_action("导航到 https://example.com")
    
    assert action_info["type"] == ActionType.NAVIGATE
    assert "https://example.com" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_click_action(execution_engine):
    """测试解析点击动作"""
    action_info = execution_engine._parse_step_action("点击登录按钮")
    
    assert action_info["type"] == ActionType.CLICK
    assert "点击" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_input_action(execution_engine):
    """测试解析输入动作"""
    action_info = execution_engine._parse_step_action("输入用户名 'admin'")
    
    assert action_info["type"] == ActionType.INPUT
    assert "输入" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_verify_action(execution_engine):
    """测试解析验证动作"""
    action_info = execution_engine._parse_step_action("验证页面标题")
    
    assert action_info["type"] == ActionType.VERIFY
    assert "验证" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_wait_action(execution_engine):
    """测试解析等待动作"""
    action_info = execution_engine._parse_step_action("等待3秒")
    
    assert action_info["type"] == ActionType.WAIT
    assert "等待" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_captcha_action(execution_engine):
    """测试解析验证码动作"""
    action_info = execution_engine._parse_step_action("识别验证码")
    
    assert action_info["type"] == ActionType.CAPTCHA
    assert "验证码" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_refresh_action(execution_engine):
    """测试解析刷新动作"""
    action_info = execution_engine._parse_step_action("刷新页面")
    
    assert action_info["type"] == ActionType.REFRESH
    assert "刷新" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_keypress_action(execution_engine):
    """测试解析按键动作"""
    action_info = execution_engine._parse_step_action("按下Enter键")
    
    assert action_info["type"] == ActionType.KEYPRESS
    assert "按下" in action_info["text"]


# ==================== URL提取测试 ====================

@pytest.mark.asyncio
async def test_extract_url_from_text(execution_engine):
    """测试从文本中提取URL"""
    url = execution_engine._extract_url("导航到 https://example.com/page")
    assert url == "https://example.com/page"


@pytest.mark.asyncio
async def test_extract_url_with_quotes(execution_engine):
    """测试从带引号的文本中提取URL"""
    url = execution_engine._extract_url("访问 'https://example.com'")
    assert url == "https://example.com"


@pytest.mark.asyncio
async def test_extract_url_not_found(execution_engine):
    """测试提取不存在的URL"""
    url = execution_engine._extract_url("点击按钮")
    assert url is None


# ==================== 输入文本提取测试 ====================

@pytest.mark.asyncio
async def test_extract_input_text_with_quotes(execution_engine):
    """测试提取带引号的输入文本"""
    text = execution_engine._extract_input_text("输入 'admin123'")
    assert text == "admin123"


@pytest.mark.asyncio
async def test_extract_input_text_with_chinese_quotes(execution_engine):
    """测试提取带中文引号的输入文本"""
    text = execution_engine._extract_input_text('输入 "admin123"')
    assert text == "admin123"


@pytest.mark.asyncio
async def test_extract_input_text_direct(execution_engine):
    """测试直接提取输入文本"""
    text = execution_engine._extract_input_text("输入 admin123")
    assert text == "admin123"


# ==================== 等待时间提取测试 ====================

@pytest.mark.asyncio
async def test_extract_wait_time_seconds(execution_engine):
    """测试提取秒数"""
    seconds = execution_engine._extract_wait_time("等待5秒")
    assert seconds == 5


@pytest.mark.asyncio
async def test_extract_wait_time_default(execution_engine):
    """测试默认等待时间"""
    seconds = execution_engine._extract_wait_time("等待一会儿")
    assert seconds == 2  # 默认值


# ==================== 按键提取测试 ====================

@pytest.mark.asyncio
async def test_extract_key_enter(execution_engine):
    """测试提取Enter键"""
    key = execution_engine._extract_key("按下Enter键")
    assert key == "Enter"


@pytest.mark.asyncio
async def test_extract_key_tab(execution_engine):
    """测试提取Tab键"""
    key = execution_engine._extract_key("按下Tab键")
    assert key == "Tab"


@pytest.mark.asyncio
async def test_extract_key_default(execution_engine):
    """测试默认按键"""
    key = execution_engine._extract_key("按下按键")
    assert key == "Enter"  # 默认值


# ==================== 执行摘要生成测试 ====================

@pytest.mark.asyncio
async def test_generate_execution_summary_all_passed(execution_engine):
    """测试生成全部通过的执行摘要"""
    execution_engine._step_results = [
        StepExecutionResult(1, "步骤1", ExecutionStatus.PASSED, datetime.utcnow()),
        StepExecutionResult(2, "步骤2", ExecutionStatus.PASSED, datetime.utcnow()),
    ]
    
    summary = execution_engine._generate_execution_summary()
    assert "总计2步" in summary
    assert "通过2步" in summary
    assert "失败0步" in summary


@pytest.mark.asyncio
async def test_generate_execution_summary_with_failures(execution_engine):
    """测试生成有失败的执行摘要"""
    execution_engine._step_results = [
        StepExecutionResult(1, "步骤1", ExecutionStatus.PASSED, datetime.utcnow()),
        StepExecutionResult(2, "步骤2", ExecutionStatus.FAILED, datetime.utcnow()),
    ]
    
    summary = execution_engine._generate_execution_summary()
    assert "总计2步" in summary
    assert "通过1步" in summary
    assert "失败1步" in summary


# ==================== 执行历史查询测试 ====================

@pytest.mark.asyncio
async def test_get_execution_history(execution_engine, db_session, test_case):
    """测试获取执行历史"""
    # 创建一些执行记录
    for i in range(3):
        execution = TestCaseExecution(
            test_case_id=test_case.id,
            status=ExecutionStatus.PASSED.value,
            started_at=datetime.utcnow()
        )
        db_session.add(execution)
    db_session.commit()
    
    # 查询执行历史
    history = execution_engine.get_execution_history(test_case_id=test_case.id)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_get_execution_history_with_limit(execution_engine, db_session, test_case):
    """测试限制数量的执行历史查询"""
    # 创建5条执行记录
    for i in range(5):
        execution = TestCaseExecution(
            test_case_id=test_case.id,
            status=ExecutionStatus.PASSED.value,
            started_at=datetime.utcnow()
        )
        db_session.add(execution)
    db_session.commit()
    
    # 查询限制2条
    history = execution_engine.get_execution_history(test_case_id=test_case.id, limit=2)
    assert len(history) == 2


# ==================== 集成测试 ====================

@pytest.mark.asyncio
async def test_execute_simple_test_case(execution_engine, test_case, test_steps):
    """测试执行简单测试用例"""
    result = await execution_engine.execute_test_case(
        test_case=test_case,
        project_id=10001,
        skip_precondition=True
    )
    
    assert result is not None
    assert result.test_case_id == test_case.id
    assert len(result.step_results) > 0
    
    # 验证执行记录已保存到数据库
    execution = execution_engine.db.query(TestCaseExecution).filter_by(
        test_case_id=test_case.id
    ).first()
    assert execution is not None


@pytest.mark.asyncio
async def test_execute_navigate_step(execution_engine, browser):
    """测试执行导航步骤"""
    action_info = {"type": ActionType.NAVIGATE, "text": "导航到 https://www.example.com"}
    
    await execution_engine._execute_navigate(action_info)
    
    assert browser.current_url.startswith("https://www.example.com")


@pytest.mark.asyncio
async def test_execute_wait_step(execution_engine):
    """测试执行等待步骤"""
    import time
    start_time = time.time()
    
    action_info = {"type": ActionType.WAIT, "text": "等待2秒"}
    await execution_engine._execute_wait(action_info)
    
    elapsed = time.time() - start_time
    assert elapsed >= 1.9  # 至少等待约2秒（允许微小计时误差）


@pytest.mark.asyncio
async def test_execute_refresh_step(execution_engine, browser):
    """测试执行刷新步骤"""
    await browser.navigate("https://www.example.com")
    initial_title = await browser.execute_javascript("document.title")
    
    action_info = {"type": ActionType.REFRESH, "text": "刷新页面"}
    await execution_engine._execute_refresh(action_info)
    
    refreshed_title = await browser.execute_javascript("document.title")
    assert initial_title == refreshed_title  # 标题应该相同


@pytest.mark.asyncio
async def test_execute_keypress_step(execution_engine, browser):
    """测试执行按键步骤"""
    await browser.navigate("https://www.example.com")
    
    action_info = {"type": ActionType.KEYPRESS, "text": "按下Tab键"}
    await execution_engine._execute_keypress(action_info)
    # 按键操作应该正常执行，不抛出异常


# ==================== 错误处理测试 ====================

@pytest.mark.asyncio
async def test_execute_navigate_without_browser(execution_engine):
    """测试没有浏览器时执行导航"""
    execution_engine.browser = None
    action_info = {"type": ActionType.NAVIGATE, "text": "导航到 https://example.com"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_navigate(action_info)


@pytest.mark.asyncio
async def test_execute_navigate_invalid_url(execution_engine, browser):
    """测试导航到无效URL"""
    action_info = {"type": ActionType.NAVIGATE, "text": "导航到 invalid-url"}

    with pytest.raises((ValueError, StepExecutionError)):
        await execution_engine._execute_navigate(action_info)


@pytest.mark.asyncio
async def test_execute_click_without_browser(execution_engine):
    """测试没有浏览器时执行点击"""
    execution_engine.browser = None
    action_info = {"type": ActionType.CLICK, "text": "点击按钮"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_click(action_info, None)


@pytest.mark.asyncio
async def test_execute_input_without_browser(execution_engine):
    """测试没有浏览器时执行输入"""
    execution_engine.browser = None
    action_info = {"type": ActionType.INPUT, "text": "输入文本"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_input(action_info, None)


@pytest.mark.asyncio
async def test_execute_verify_without_browser(execution_engine):
    """测试没有浏览器时执行验证"""
    execution_engine.browser = None
    action_info = {"type": ActionType.VERIFY, "text": "验证页面"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_verify(action_info, None)


@pytest.mark.asyncio
async def test_execute_scroll_without_browser(execution_engine):
    """测试没有浏览器时执行滚动"""
    execution_engine.browser = None
    action_info = {"type": ActionType.SCROLL, "text": "向下滚动"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_scroll(action_info)


@pytest.mark.asyncio
async def test_execute_refresh_without_browser(execution_engine):
    """测试没有浏览器时执行刷新"""
    execution_engine.browser = None
    action_info = {"type": ActionType.REFRESH, "text": "刷新页面"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_refresh(action_info)


@pytest.mark.asyncio
async def test_execute_keypress_without_browser(execution_engine):
    """测试没有浏览器时执行按键"""
    execution_engine.browser = None
    action_info = {"type": ActionType.KEYPRESS, "text": "按下Enter"}
    
    with pytest.raises(StepExecutionError):
        await execution_engine._execute_keypress(action_info)


# ==================== 装饰器测试 ====================

@pytest.mark.asyncio
async def test_handle_execution_errors_decorator():
    """测试错误处理装饰器"""
    from app.services.test_execution_engine_v2 import handle_execution_errors
    
    @handle_execution_errors
    async def test_func():
        raise ValueError("测试错误")
    
    with pytest.raises(ExecutionError) as exc_info:
        await test_func()
    
    assert "测试错误" in str(exc_info.value)
