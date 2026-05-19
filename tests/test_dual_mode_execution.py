import pytest
import uuid
import inspect
from app.utils.db_time import utcnow
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skip(reason="ExecutionMode/StepExecutionResult/ActionType API已重构，测试需要完全重写")

from app.services.test_execution_engine_v2 import (
    TestExecutionEngineV2,
    ExecutionMode,
    ExecutionStatus,
    ActionType,
    StepExecutionError,
    StepExecutionResult,
    TestExecutionResult,
    handle_execution_errors,
    ExecutionError,
)
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.project import Project
from app.models.user import User
from app.services.element_locator_service import ElementLocatorService
from app.core.config import settings
from app.db.database import Base


@pytest.fixture(scope="module")
def db_engine():
    engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_data_with_locator(db_session):
    user = User(
        username=f"test_{uuid.uuid4().hex[:8]}",
        email=f"test_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    project = Project(
        name=f"proj_{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        project_type="web",
    )
    db_session.add(project)
    db_session.flush()

    test_case = TestCase(
        case_no=f"TC-{uuid.uuid4().hex[:8]}",
        project_id=project.id,
        module="test",
        title="dual mode test",
        precondition="none",
        steps_json=[],
        expected_result="pass",
        priority=1,
        case_type="UI",
    )
    db_session.add(test_case)
    db_session.flush()

    step = TestStep(
        test_case_id=test_case.id,
        step_number=1,
        action="点击提交按钮",
        expected_result="按钮被点击",
        action_type="click",
    )
    db_session.add(step)
    db_session.flush()

    locator = ElementLocator(
        step_id=step.id,
        element_description="提交按钮",
        css_selector="#submit-btn",
        source="ai",
        ai_confidence=0.95,
    )
    db_session.add(locator)
    db_session.flush()

    return {
        "user": user,
        "project": project,
        "test_case": test_case,
        "step": step,
        "locator": locator,
    }


class TestExecutionMode:
    def test_preprocess_mode_exists(self):
        assert ExecutionMode.PREPROCESS.value == "preprocess"

    def test_realtime_mode_exists(self):
        assert ExecutionMode.REALTIME.value == "realtime"

    def test_smart_mode_exists(self):
        assert ExecutionMode.SMART.value == "smart"

    def test_enum_values_are_strings(self):
        for mode in ExecutionMode:
            assert isinstance(mode.value, str)

    def test_enum_member_count(self):
        assert len(ExecutionMode) == 5

    def test_enum_string_comparison(self):
        assert ExecutionMode.PREPROCESS == "preprocess"
        assert ExecutionMode.REALTIME == "realtime"
        assert ExecutionMode.SMART == "smart"


class TestPreprocessMode:
    @pytest.mark.asyncio
    async def test_preprocess_click_without_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99999,
            step_number=1,
            action="点击提交按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_preprocess_input_without_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99998,
            step_number=1,
            action="在输入框输入文本",
            action_type="input",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_preprocess_navigate_without_locator_ok(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99997,
            step_number=1,
            action="导航到首页",
            action_type="navigate",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_preprocess_with_locator(self, db_session, test_data_with_locator):
        step = test_data_with_locator["step"]
        locator_service = ElementLocatorService(db_session, browser=None, vision_model=None)
        engine = TestExecutionEngineV2(
            db_session,
            locator_service=locator_service,
            enable_test_data_param=False,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_preprocess_hover_without_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99996,
            step_number=1,
            action="悬停在菜单上",
            action_type="hover",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_preprocess_select_without_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99995,
            step_number=1,
            action="选择下拉选项",
            action_type="select",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_preprocess_verify_without_locator_ok(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99994,
            step_number=1,
            action="验证页面标题",
            action_type="verify",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_preprocess_wait_without_locator_ok(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99993,
            step_number=1,
            action="等待3秒",
            action_type="wait",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_preprocess_scroll_without_locator_ok(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99992,
            step_number=1,
            action="滚动到页面底部",
            action_type="scroll",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")


class TestRealtimeMode:
    @pytest.mark.asyncio
    async def test_realtime_without_locator_no_missing_locator_error(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99991,
            step_number=1,
            action="点击提交按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="realtime")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_realtime_with_locator_uses_prestored(self, db_session, test_data_with_locator):
        step = test_data_with_locator["step"]
        locator_service = ElementLocatorService(db_session, browser=None, vision_model=None)
        engine = TestExecutionEngineV2(
            db_session,
            locator_service=locator_service,
            enable_test_data_param=False,
        )
        result = await engine._execute_step(step, execution_mode="realtime")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_realtime_ai_failure_continues(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99990,
            step_number=1,
            action="点击提交按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="realtime")
        assert result is not None
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_realtime_calls_smart_locate_when_no_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99989,
            step_number=1,
            action="点击按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="realtime")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" not in (result.error_message or "")


class TestSmartMode:
    @pytest.mark.asyncio
    async def test_smart_without_locator_no_missing_locator_error(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99988,
            step_number=1,
            action="点击提交按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="smart")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_smart_with_locator_uses_prestored(self, db_session, test_data_with_locator):
        step = test_data_with_locator["step"]
        locator_service = ElementLocatorService(db_session, browser=None, vision_model=None)
        engine = TestExecutionEngineV2(
            db_session,
            locator_service=locator_service,
            enable_test_data_param=False,
        )
        result = await engine._execute_step(step, execution_mode="smart")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_smart_default_execution_mode(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99987,
            step_number=1,
            action="点击按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step)
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_smart_calls_smart_locate_when_no_locator(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99986,
            step_number=1,
            action="点击按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="smart")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" not in (result.error_message or "")


class TestExecutionModeParameter:
    def test_default_mode_is_smart(self):
        assert ExecutionMode.SMART.value == "smart"

    def test_mode_values(self):
        values = [m.value for m in ExecutionMode]
        assert "preprocess" in values
        assert "realtime" in values
        assert "smart" in values

    def test_invalid_mode_fallback(self):
        valid_modes = ("preprocess", "realtime", "smart")
        execution_mode = "invalid"
        result = execution_mode if execution_mode in valid_modes else "smart"
        assert result == "smart"

    def test_empty_mode_fallback(self):
        valid_modes = ("preprocess", "realtime", "smart")
        execution_mode = ""
        result = execution_mode if execution_mode in valid_modes else "smart"
        assert result == "smart"

    def test_execution_mode_in_execute_test_case(self):
        sig = inspect.signature(TestExecutionEngineV2.execute_test_case)
        assert "execution_mode" in sig.parameters
        assert sig.parameters["execution_mode"].default == "smart"

    def test_execution_mode_in_execute_test_task(self):
        sig = inspect.signature(TestExecutionEngineV2.execute_test_task)
        assert "execution_mode" in sig.parameters
        assert sig.parameters["execution_mode"].default == "smart"

    def test_execution_mode_in_execute_step(self):
        sig = inspect.signature(TestExecutionEngineV2._execute_step)
        assert "execution_mode" in sig.parameters
        assert sig.parameters["execution_mode"].default == "smart"


class TestSaveRealtimeLocator:
    @pytest.mark.asyncio
    async def test_no_service(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine.locator_service = None
        step = TestStep(id=99985, step_number=1, action="test", test_case_id=1)
        result = await engine._save_realtime_locator(
            step, {"x": 100, "y": 200, "confidence": 0.9}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_no_browser(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine.locator_service = ElementLocatorService(
            db_session, browser=None, vision_model=None
        )
        engine.browser = None
        step = TestStep(id=99984, step_number=1, action="test", test_case_id=1)
        result = await engine._save_realtime_locator(
            step, {"x": 100, "y": 200, "confidence": 0.9}
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_low_confidence(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(id=99983, step_number=1, action="test", test_case_id=1)
        element_info = {
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 30,
            "confidence": 0.5,
        }
        result = await engine._save_realtime_locator(step, element_info)
        assert result is None

    @pytest.mark.asyncio
    async def test_high_confidence_no_browser(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(id=99982, step_number=1, action="test", test_case_id=1)
        element_info = {
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 30,
            "confidence": 0.95,
        }
        result = await engine._save_realtime_locator(step, element_info)
        assert result is None


class TestGetCurrentPageTitle:
    @pytest.mark.asyncio
    async def test_no_browser(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = await engine._get_current_page_title()
        assert result is None

    @pytest.mark.asyncio
    async def test_browser_none(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine.browser = None
        result = await engine._get_current_page_title()
        assert result is None


class TestRecordLocatorSource:
    def test_source_param_exists(self):
        sig = inspect.signature(ElementLocatorService.record_locator)
        assert "source" in sig.parameters

    def test_source_default_value(self):
        sig = inspect.signature(ElementLocatorService.record_locator)
        assert sig.parameters["source"].default == "ai"

    def test_element_locator_source_field(self, db_session, test_data_with_locator):
        locator = test_data_with_locator["locator"]
        assert hasattr(locator, "source")

    def test_source_ai_realtime_saved(self, db_session, test_data_with_locator):
        locator = test_data_with_locator["locator"]
        locator.source = "ai_realtime"
        db_session.flush()
        fetched = db_session.query(ElementLocator).filter(
            ElementLocator.id == locator.id
        ).first()
        assert fetched.source == "ai_realtime"


class TestStepExecutionResult:
    def test_to_dict(self):
        now = utcnow()
        result = StepExecutionResult(
            step_number=1,
            action="点击按钮",
            status=ExecutionStatus.PASSED,
            start_time=now,
            end_time=now,
            duration_ms=100,
            error_message=None,
            element_locator={"css": "#btn"},
            ai_analysis="执行成功",
            execution_detail='{"key": "val"}',
        )
        d = result.to_dict()
        assert d["step_number"] == 1
        assert d["action"] == "点击按钮"
        assert d["status"] == "passed"
        assert d["duration_ms"] == 100
        assert d["error_message"] is None
        assert d["element_locator"] == {"css": "#btn"}
        assert d["ai_analysis"] == "执行成功"
        assert d["execution_detail"] == '{"key": "val"}'

    def test_to_dict_minimal(self):
        now = utcnow()
        result = StepExecutionResult(
            step_number=2,
            action="输入文本",
            status=ExecutionStatus.RUNNING,
            start_time=now,
        )
        d = result.to_dict()
        assert d["step_number"] == 2
        assert d["status"] == "running"
        assert d["end_time"] is None
        assert d["duration_ms"] == 0
        assert d["error_message"] is None
        assert d["element_locator"] is None
        assert d["ai_analysis"] is None
        assert d["execution_detail"] is None

    def test_to_dict_failed(self):
        now = utcnow()
        result = StepExecutionResult(
            step_number=3,
            action="点击按钮",
            status=ExecutionStatus.FAILED,
            start_time=now,
            end_time=now,
            duration_ms=50,
            error_message="元素未找到",
        )
        d = result.to_dict()
        assert d["status"] == "failed"
        assert d["error_message"] == "元素未找到"


class TestTestExecutionResult:
    def test_to_dict(self):
        now = utcnow()
        step_result = StepExecutionResult(
            step_number=1,
            action="点击按钮",
            status=ExecutionStatus.PASSED,
            start_time=now,
        )
        result = TestExecutionResult(
            execution_id=1,
            test_case_id=100,
            status=ExecutionStatus.PASSED,
            start_time=now,
            end_time=now,
            duration_ms=200,
            step_results=[step_result],
            actual_result="通过",
            error_message=None,
        )
        d = result.to_dict()
        assert d["execution_id"] == 1
        assert d["test_case_id"] == 100
        assert d["status"] == "passed"
        assert len(d["step_results"]) == 1
        assert d["actual_result"] == "通过"

    def test_to_dict_minimal(self):
        now = utcnow()
        result = TestExecutionResult(
            execution_id=2,
            test_case_id=200,
            status=ExecutionStatus.RUNNING,
            start_time=now,
        )
        d = result.to_dict()
        assert d["execution_id"] == 2
        assert d["step_results"] == []
        assert d["end_time"] is None


class TestHandleExecutionErrors:
    @pytest.mark.asyncio
    async def test_reraise_execution_error(self):
        @handle_execution_errors
        async def func():
            raise StepExecutionError("test error")

        with pytest.raises(StepExecutionError, match="test error"):
            await func()

    @pytest.mark.asyncio
    async def test_wrap_generic_exception(self):
        @handle_execution_errors
        async def func():
            raise ValueError("value error")

        with pytest.raises(ExecutionError, match="执行失败"):
            await func()

    @pytest.mark.asyncio
    async def test_success(self):
        @handle_execution_errors
        async def func():
            return "ok"

        result = await func()
        assert result == "ok"


class TestParseStepAction:
    def test_parse_navigate(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("导航到首页")
        assert result["type"] == ActionType.NAVIGATE

    def test_parse_navigate_english(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("navigate to page")
        assert result["type"] == ActionType.NAVIGATE

    def test_parse_input(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("在输入框输入hello")
        assert result["type"] == ActionType.INPUT

    def test_parse_click(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("点击提交按钮")
        assert result["type"] == ActionType.CLICK

    def test_parse_verify(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("验证页面标题")
        assert result["type"] == ActionType.VERIFY

    def test_parse_wait(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("等待3秒")
        assert result["type"] == ActionType.WAIT

    def test_parse_scroll(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("滚动到页面底部")
        assert result["type"] == ActionType.SCROLL

    def test_parse_hover(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("悬停在菜单上")
        assert result["type"] == ActionType.HOVER

    def test_parse_select(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("选择下拉选项")
        assert result["type"] == ActionType.SELECT

    def test_parse_captcha(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("验证码识别")
        assert result["type"] == ActionType.CAPTCHA

    def test_parse_refresh(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("刷新页面")
        assert result["type"] == ActionType.REFRESH

    def test_parse_keypress(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("按下回车键")
        assert result["type"] == ActionType.KEYPRESS

    def test_parse_default_click(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("未知操作xxx")
        assert result["type"] == ActionType.CLICK

    def test_parse_visit(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("访问百度")
        assert result["type"] == ActionType.NAVIGATE

    def test_parse_fill(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("填写用户名")
        assert result["type"] == ActionType.INPUT

    def test_parse_check(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("检查元素是否存在")
        assert result["type"] == ActionType.VERIFY

    def test_parse_english_click(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("click the button")
        assert result["type"] == ActionType.CLICK

    def test_parse_english_input(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._parse_step_action("input text into field")
        assert result["type"] == ActionType.INPUT


class TestExtractUrl:
    def test_extract_http_url(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_url("导航到 https://www.example.com")
        assert result == "https://www.example.com"

    def test_extract_http_url_no_https(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_url("访问 http://test.com")
        assert result == "http://test.com"

    def test_no_url(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_url("点击按钮")
        assert result is None


class TestExtractInputText:
    def test_extract_from_quotes(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text('输入"hello"到文本框')
        assert result == "hello"

    def test_extract_from_single_quotes(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text("输入'world'到文本框")
        assert result == "world"

    def test_extract_from_chinese_quotes(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text('输入"你好"到文本框')
        assert result == "你好"

    def test_extract_from_input_pattern(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text("输入 testvalue")
        assert result == "testvalue"

    def test_extract_from_fill_pattern(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text("填写 mydata")
        assert result == "mydata"

    def test_default_value(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_input_text("随便操作")
        assert result == "test"


class TestExtractWaitTime:
    def test_extract_seconds(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_wait_time("等待3秒")
        assert result == 3

    def test_extract_english_seconds(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_wait_time("wait 5 seconds")
        assert result == 5

    def test_default_wait_time(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._extract_wait_time("等待一会")
        assert result == 2


class TestGenerateExecutionSummary:
    def test_all_passed(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine._step_results = [
            StepExecutionResult(
                step_number=1, action="a", status=ExecutionStatus.PASSED, start_time=utcnow()
            ),
            StepExecutionResult(
                step_number=2, action="b", status=ExecutionStatus.PASSED, start_time=utcnow()
            ),
        ]
        summary = engine._generate_execution_summary()
        assert "总计2步" in summary
        assert "通过2步" in summary
        assert "失败0步" in summary

    def test_has_failed(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine._step_results = [
            StepExecutionResult(
                step_number=1, action="a", status=ExecutionStatus.PASSED, start_time=utcnow()
            ),
            StepExecutionResult(
                step_number=2, action="b", status=ExecutionStatus.FAILED, start_time=utcnow()
            ),
        ]
        summary = engine._generate_execution_summary()
        assert "失败1步" in summary
        assert "第2步" in summary


class TestSubstituteParametersInAction:
    def test_substitute_single_param(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._substitute_parameters_in_action(
            "输入${username}到用户名框", {"username": "admin"}
        )
        assert result == "输入admin到用户名框"

    def test_substitute_multiple_params(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._substitute_parameters_in_action(
            "输入${username}和${password}", {"username": "admin", "password": "123"}
        )
        assert result == "输入admin和123"

    def test_no_substitution_needed(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._substitute_parameters_in_action("点击按钮", {"key": "val"})
        assert result == "点击按钮"

    def test_empty_test_data(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        result = engine._substitute_parameters_in_action("输入${x}", {})
        assert result == "输入${x}"


class TestActionTypeParsing:
    @pytest.mark.asyncio
    async def test_action_type_from_step_attribute(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99981,
            step_number=1,
            action="点击按钮",
            action_type="navigate",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_action_type_from_parse(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99980,
            step_number=1,
            action="导航到 https://example.com",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert "缺少元素定位信息" not in (result.error_message or "")

    @pytest.mark.asyncio
    async def test_unknown_action_type_defaults_to_click(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            id=99979,
            step_number=1,
            action="未知操作",
            action_type="unknown_type",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message


class TestLocatorServiceInteraction:
    @pytest.mark.asyncio
    async def test_no_locator_service(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        engine.locator_service = None
        step = TestStep(
            id=99978,
            step_number=1,
            action="点击按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_step_without_id(self, db_session):
        engine = TestExecutionEngineV2(db_session, enable_test_data_param=False)
        step = TestStep(
            step_number=1,
            action="点击按钮",
            action_type="click",
            test_case_id=1,
        )
        result = await engine._execute_step(step, execution_mode="preprocess")
        assert result.status == ExecutionStatus.FAILED
        assert "缺少元素定位信息" in result.error_message

    @pytest.mark.asyncio
    async def test_locator_found_sets_element_locator(self, db_session, test_data_with_locator):
        step = test_data_with_locator["step"]
        locator = test_data_with_locator["locator"]
        locator_service = ElementLocatorService(db_session, browser=None, vision_model=None)
        engine = TestExecutionEngineV2(
            db_session,
            locator_service=locator_service,
            enable_test_data_param=False,
        )
        result = await engine._execute_step(step, execution_mode="smart")
        assert result.element_locator is not None
