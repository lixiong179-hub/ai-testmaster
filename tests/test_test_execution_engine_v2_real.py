"""
测试执行引擎V2真实测试

注意：由于此文件创建独立数据库引擎会污染pytest会话级testEngine，
导致其他测试出现级联"Table doesn't exist"错误。
部分使用真实浏览器的测试需要Playwright环境。
"""
import pytest
from datetime import datetime

from app.models.test_case import TestCase, TestStep, TestCaseExecution
from app.models.project import Project
from app.services.test_execution_engine import (
    TestExecutionEngineV2,
    ExecutionStatus,
    ActionType,
    StepExecutionResult,
    TestExecutionResult,
    ExecutionError,
    StepExecutionError,
    VerificationError,
)


@pytest.fixture(scope="function")
def db_session(db):
    return db


@pytest.fixture
def eng_project(db, testUser):
    project = Project(
        name="测试项目-引擎",
        description="用于测试的项目",
        user_id=testUser.id,
        project_type="web",
        web_env_configs={"test": {"url": "https://www.example.com"}},
        status=1,
    )
    db.add(project)
    db.flush()
    return project


@pytest.fixture
def eng_test_case(db, eng_project):
    test_case = TestCase(
        project_id=eng_project.id,
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
        generate_status=1,
    )
    db.add(test_case)
    db.flush()
    return test_case


@pytest.fixture
def eng_test_steps(db, eng_test_case):
    steps = []
    for i in range(1, 3):
        step = TestStep(
            test_case_id=eng_test_case.id,
            step_number=i,
            action=f"步骤{i}: 测试操作",
            expected_result=f"预期结果{i}",
        )
        db.add(step)
        steps.append(step)
    db.flush()
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


@pytest.mark.skip(reason="ActionType/StepExecutionResult API已重构")
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

@pytest.mark.skip(reason="ActionType/StepExecutionResult API已重构")
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


@pytest.mark.skip(reason="ActionType/StepExecutionResult API已重构")
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


@pytest.mark.skip(reason="ActionType/StepExecutionResult API已重构")
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
async def test_execution_engine_initialization(db):
    """测试执行引擎初始化"""
    engine = TestExecutionEngineV2(db=db)

    assert engine.db == db
    assert engine._current_execution is None
    assert len(engine._step_results) == 0


@pytest.mark.asyncio
async def test_execution_engine_without_browser(db):
    """测试没有浏览器的执行引擎"""
    engine = TestExecutionEngineV2(db=db)

    assert engine.db == db
    assert engine.browser is None
    assert engine.vision_model is None


# ==================== 动作解析测试 ====================

@pytest.mark.asyncio
async def test_parse_navigate_action(db):
    """测试解析导航动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("导航到 https://example.com")

    assert action_info["type"] == ActionType.NAVIGATE
    assert "https://example.com" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_click_action(db):
    """测试解析点击动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("点击登录按钮")

    assert action_info["type"] == ActionType.CLICK
    assert "点击" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_input_action(db):
    """测试解析输入动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("输入用户名 'admin'")

    assert action_info["type"] == ActionType.INPUT
    assert "输入" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_verify_action(db):
    """测试解析验证动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("验证页面标题")

    assert action_info["type"] == ActionType.VERIFY
    assert "验证" in action_info["text"]


@pytest.mark.asyncio
async def test_parse_wait_action(db):
    """测试解析等待动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("等待3秒")

    assert action_info["type"] == ActionType.WAIT
    assert "等待" in action_info["text"]


@pytest.mark.skip(reason="ActionType.CAPTCHA已移除，改为VERIFY_CAPTCHA")
@pytest.mark.asyncio
async def test_parse_captcha_action():
    pass


@pytest.mark.asyncio
async def test_parse_refresh_action(db):
    """测试解析刷新动作"""
    engine = TestExecutionEngineV2(db=db)
    action_info = engine._parse_step_action("刷新页面")

    assert action_info["type"] == ActionType.REFRESH


@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_parse_keypress_action():
    pass


# ==================== URL提取测试 ====================

@pytest.mark.asyncio
async def test_extract_url_from_text(db):
    """测试从文本中提取URL"""
    engine = TestExecutionEngineV2(db=db)
    url = engine._extract_url("导航到 https://example.com/page")
    assert url == "https://example.com/page"


@pytest.mark.asyncio
async def test_extract_url_with_quotes(db):
    """测试从带引号的文本中提取URL"""
    engine = TestExecutionEngineV2(db=db)
    url = engine._extract_url("访问 'https://example.com'")
    assert url == "https://example.com"


@pytest.mark.asyncio
async def test_extract_url_not_found(db):
    """测试提取不存在的URL"""
    engine = TestExecutionEngineV2(db=db)
    url = engine._extract_url("点击按钮")
    assert url is None


# ==================== 输入文本提取测试 ====================

@pytest.mark.asyncio
async def test_extract_input_text_with_quotes(db):
    """测试提取带引号的输入文本"""
    engine = TestExecutionEngineV2(db=db)
    text = engine._extract_input_text("输入 'admin123'")
    assert text == "admin123"


@pytest.mark.asyncio
async def test_extract_input_text_with_chinese_quotes(db):
    """测试提取带中文引号的输入文本"""
    engine = TestExecutionEngineV2(db=db)
    text = engine._extract_input_text('输入 "admin123"')
    assert text == "admin123"


@pytest.mark.asyncio
async def test_extract_input_text_direct(db):
    """测试直接提取输入文本"""
    engine = TestExecutionEngineV2(db=db)
    text = engine._extract_input_text("输入 admin123")
    assert text == "admin123"


# ==================== 等待时间提取测试 ====================

@pytest.mark.asyncio
async def test_extract_wait_time_seconds(db):
    """测试提取秒数"""
    engine = TestExecutionEngineV2(db=db)
    seconds = engine._extract_wait_time("等待5秒")
    assert seconds == 5


@pytest.mark.asyncio
async def test_extract_wait_time_default(db):
    """测试默认等待时间"""
    engine = TestExecutionEngineV2(db=db)
    seconds = engine._extract_wait_time("等待一会儿")
    assert seconds == 2


# ==================== 按键提取测试 ====================

@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_extract_key_enter():
    pass


@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_extract_key_tab():
    pass


@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_extract_key_default():
    pass


# ==================== 执行摘要生成测试 ====================

@pytest.mark.skip(reason="StepExecutionResult API已重构")
@pytest.mark.asyncio
async def test_generate_execution_summary_all_passed():
    pass


@pytest.mark.skip(reason="StepExecutionResult API已重构")
@pytest.mark.asyncio
async def test_generate_execution_summary_with_failures():
    pass


# ==================== 执行历史查询测试 ====================

@pytest.mark.asyncio
async def test_get_execution_history(db, eng_test_case):
    engine = TestExecutionEngineV2(db=db)
    for i in range(3):
        execution = TestCaseExecution(
            test_case_id=eng_test_case.id,
            status=ExecutionStatus.PASSED.value,
            started_at=datetime.utcnow(),
        )
        db.add(execution)
    db.flush()

    history = engine.get_execution_history(test_case_id=eng_test_case.id)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_get_execution_history_with_limit(db, eng_test_case):
    engine = TestExecutionEngineV2(db=db)
    for i in range(5):
        execution = TestCaseExecution(
            test_case_id=eng_test_case.id,
            status=ExecutionStatus.PASSED.value,
            started_at=datetime.utcnow(),
        )
        db.add(execution)
    db.flush()

    history = engine.get_execution_history(test_case_id=eng_test_case.id, limit=2)
    assert len(history) == 2


# ==================== 集成测试 ====================

@pytest.mark.skip(reason="需要真实浏览器环境")
@pytest.mark.asyncio
async def test_execute_simple_test_case():
    pass


@pytest.mark.skip(reason="需要真实浏览器环境")
@pytest.mark.asyncio
async def test_execute_navigate_step():
    pass


@pytest.mark.skip(reason="需要真实浏览器环境")
@pytest.mark.asyncio
async def test_execute_wait_step():
    pass


@pytest.mark.skip(reason="需要真实浏览器环境")
@pytest.mark.asyncio
async def test_execute_refresh_step():
    pass


@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_execute_keypress_step():
    pass


# ==================== 错误处理测试 ====================

@pytest.mark.asyncio
async def test_execute_navigate_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.NAVIGATE, "text": "导航到 https://example.com"}

    with pytest.raises(StepExecutionError):
        await engine._execute_navigate(action_info)


@pytest.mark.skip(reason="需要真实浏览器环境")
@pytest.mark.asyncio
async def test_execute_navigate_invalid_url():
    pass


@pytest.mark.asyncio
async def test_execute_click_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.CLICK, "text": "点击按钮"}

    with pytest.raises(StepExecutionError):
        await engine._execute_click(action_info, None)


@pytest.mark.asyncio
async def test_execute_input_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.INPUT, "text": "输入文本"}

    with pytest.raises(StepExecutionError):
        await engine._execute_input(action_info, None)


@pytest.mark.asyncio
async def test_execute_verify_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.VERIFY, "text": "验证页面"}

    with pytest.raises(StepExecutionError):
        await engine._execute_verify(action_info, None)


@pytest.mark.asyncio
async def test_execute_scroll_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.SCROLL, "text": "向下滚动"}

    with pytest.raises(StepExecutionError):
        await engine._execute_scroll(action_info)


@pytest.mark.asyncio
async def test_execute_refresh_without_browser(db):
    engine = TestExecutionEngineV2(db=db)
    engine.browser = None
    action_info = {"type": ActionType.REFRESH, "text": "刷新页面"}

    with pytest.raises(StepExecutionError):
        await engine._execute_refresh(action_info)


@pytest.mark.skip(reason="ActionType.KEYPRESS已移除")
@pytest.mark.asyncio
async def test_execute_keypress_without_browser():
    pass


# ==================== 装饰器测试 ====================

@pytest.mark.asyncio
async def test_handle_execution_errors_decorator():
    from app.services.test_execution_engine import handle_execution_errors

    @handle_execution_errors
    async def test_func():
        raise ValueError("测试错误")

    with pytest.raises(ExecutionError) as exc_info:
        await test_func()

    assert "测试错误" in str(exc_info.value)
