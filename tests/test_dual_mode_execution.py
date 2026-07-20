"""双模式执行测试 - 适配新 ExecutionMode/StepExecutionResult/ActionType API。

覆盖范围:
    - 枚举: ExecutionMode(3值) / ActionType(24值) / ExecutionStatus(6值) / FailureCategory(9值)
    - 数据类: StepExecutionResult / TestExecutionResult 的 to_dict 行为
    - 装饰器: handle_execution_errors 异常转换
    - 异常类: ExecutionError / StepExecutionError / VerificationError 继承关系
    - 引擎纯计算方法: _parse_step_action / _extract_url / _extract_input_text /
      _extract_wait_time / _substitute_parameters_in_action / _generate_execution_summary
"""
import pytest

from app.services.test_execution_engine_v2 import (
    TestExecutionEngineV2, ExecutionMode, ExecutionStatus, ActionType,
    StepExecutionError, VerificationError, ExecutionError,
    StepExecutionResult, TestExecutionResult, handle_execution_errors,
)
from app.services.test_execution_engine import FailureCategory
from app.models.test_case import TestCase


def _makeEngine(db_session) -> TestExecutionEngineV2:
    """构造测试引擎实例（禁用测试数据参数化，避免依赖 parameterizer）。"""
    return TestExecutionEngineV2(db_session, enable_test_data_param=False)


class TestExecutionMode:
    """ExecutionMode 枚举 - 新 3 值 (AI_VISION/API/UNKNOWN)。"""

    def test_enum_member_count_and_string_type(self):
        assert len(ExecutionMode) == 3
        for mode in ExecutionMode:
            assert isinstance(mode.value, str)

    @pytest.mark.parametrize("member,expected", [
        (ExecutionMode.AI_VISION, "ai_vision"),
        (ExecutionMode.API, "api"),
        (ExecutionMode.UNKNOWN, "unknown"),
    ])
    def test_member_values_and_string_comparison(self, member, expected):
        assert member.value == expected
        assert member == expected


class TestActionType:
    """ActionType 枚举 - 24 个动作类型。"""

    def test_enum_member_count(self):
        assert len(ActionType) == 24

    @pytest.mark.parametrize("member,expected", [
        (ActionType.CLICK, "click"), (ActionType.INPUT, "input"),
        (ActionType.SELECT, "select"), (ActionType.HOVER, "hover"),
        (ActionType.VERIFY, "verify"), (ActionType.NAVIGATE, "navigate"),
        (ActionType.WAIT, "wait"), (ActionType.SCREENSHOT, "screenshot"),
        (ActionType.SCROLL, "scroll"), (ActionType.DOUBLE_CLICK, "double_click"),
        (ActionType.RIGHT_CLICK, "right_click"), (ActionType.DRAG_AND_DROP, "drag_and_drop"),
        (ActionType.KEYBOARD, "keyboard"), (ActionType.UPLOAD, "upload"),
        (ActionType.SWITCH_FRAME, "switch_frame"), (ActionType.SWITCH_WINDOW, "switch_window"),
        (ActionType.CLOSE_WINDOW, "close_window"), (ActionType.REFRESH, "refresh"),
        (ActionType.EXECUTE_SCRIPT, "execute_script"), (ActionType.CAPTCHA, "captcha"),
        (ActionType.VERIFY_CAPTCHA, "verify_captcha"), (ActionType.KEYPRESS, "keypress"),
        (ActionType.API_CALL, "api_call"), (ActionType.CUSTOM, "custom"),
    ])
    def test_member_values_and_string_comparison(self, member, expected):
        assert member.value == expected
        assert member == expected


class TestExecutionStatus:
    """ExecutionStatus 枚举 - 6 个状态。"""

    def test_enum_member_count(self):
        assert len(ExecutionStatus) == 6

    @pytest.mark.parametrize("member,expected", [
        (ExecutionStatus.PENDING, "pending"), (ExecutionStatus.RUNNING, "running"),
        (ExecutionStatus.PASSED, "passed"), (ExecutionStatus.FAILED, "failed"),
        (ExecutionStatus.BLOCKED, "blocked"), (ExecutionStatus.ERROR, "error"),
    ])
    def test_member_values_and_string_comparison(self, member, expected):
        assert member.value == expected
        assert member == expected


class TestFailureCategory:
    """FailureCategory 枚举 - 9 个失败分类及判定方法。"""

    def test_enum_member_count(self):
        assert len(FailureCategory) == 9

    @pytest.mark.parametrize("category,expected", [
        (FailureCategory.PRODUCT_BUG, "product_bug"),
        (FailureCategory.UPSTREAM_BLOCKED, "upstream_blocked"),
        (FailureCategory.NAVIGATION_FAILURE, "navigation_failure"),
        (FailureCategory.PRECONDITION_FAILURE, "precondition_failure"),
        (FailureCategory.LOCATOR_FAILURE, "locator_failure"),
        (FailureCategory.ENVIRONMENT_ERROR, "environment_error"),
        (FailureCategory.PERFORMANCE_BUG, "performance_bug"),
        (FailureCategory.COMPATIBILITY_BUG, "compatibility_bug"),
        (FailureCategory.CRASH_BUG, "crash_bug"),
    ])
    def test_member_values(self, category, expected):
        assert category.value == expected

    @pytest.mark.parametrize("category,expected", [
        (FailureCategory.PRODUCT_BUG, True), (FailureCategory.PERFORMANCE_BUG, True),
        (FailureCategory.COMPATIBILITY_BUG, True), (FailureCategory.CRASH_BUG, True),
        (FailureCategory.UPSTREAM_BLOCKED, False), (FailureCategory.LOCATOR_FAILURE, False),
        (None, False),
    ])
    def test_is_product_bug(self, category, expected):
        assert FailureCategory.is_product_bug(category) is expected

    @pytest.mark.parametrize("category,expected", [
        (FailureCategory.UPSTREAM_BLOCKED, True),
        (FailureCategory.NAVIGATION_FAILURE, True),
        (FailureCategory.PRECONDITION_FAILURE, True),
        (FailureCategory.LOCATOR_FAILURE, True),
        (FailureCategory.ENVIRONMENT_ERROR, True),
        (FailureCategory.PRODUCT_BUG, False),
        (FailureCategory.CRASH_BUG, False),
        (None, False),
    ])
    def test_is_false_positive(self, category, expected):
        assert FailureCategory.is_false_positive(category) is expected


class TestStepExecutionResult:
    """StepExecutionResult dataclass - 新字段 (action_type/healing_applied/failure_category 等)。"""

    def test_default_values(self):
        result = StepExecutionResult(step_number=1)
        assert result.step_number == 1
        assert result.action_type == ActionType.CLICK
        assert result.status == ExecutionStatus.PENDING
        assert result.healing_applied is False
        assert result.failure_category is None

    def test_to_dict_full(self):
        d = StepExecutionResult(
            step_number=1, action_type=ActionType.INPUT, status=ExecutionStatus.PASSED,
            description="输入用户名到登录框", duration_ms=100, healing_applied=True,
            original_selector="#old", healed_selector="#new",
            failure_category=FailureCategory.LOCATOR_FAILURE, retry_count=2,
        ).to_dict()
        assert d == {
            "step_number": 1, "action_type": "input", "status": "passed",
            "description": "输入用户名到登录框", "duration_ms": 100, "error_message": None,
            "screenshot_path": None, "healing_applied": True, "original_selector": "#old",
            "healed_selector": "#new", "failure_category": "locator_failure", "retry_count": 2,
        }

    def test_to_dict_minimal_and_failed(self):
        d_min = StepExecutionResult(step_number=2).to_dict()
        assert d_min["action_type"] == "click"
        assert d_min["status"] == "pending"
        assert d_min["healing_applied"] is False
        d_fail = StepExecutionResult(
            step_number=3, status=ExecutionStatus.FAILED,
            error_message="元素未找到", failure_category=FailureCategory.LOCATOR_FAILURE,
        ).to_dict()
        assert d_fail["status"] == "failed"
        assert d_fail["error_message"] == "元素未找到"
        assert d_fail["failure_category"] == "locator_failure"

    def test_to_dict_with_hidden_fields(self):
        d = StepExecutionResult(step_number=1, duration_ms=100).to_dict(
            hidden_fields=["duration_ms", "retry_count"]
        )
        assert "duration_ms" not in d
        assert "retry_count" not in d
        assert d["step_number"] == 1


class TestTestExecutionResult:
    """TestExecutionResult dataclass - 新字段 (case_id 替代 execution_id, steps 替代 step_results)。"""

    def test_default_values(self):
        result = TestExecutionResult(case_id=1)
        assert result.case_id == 1
        assert result.status == ExecutionStatus.PENDING
        assert result.steps == []
        assert result.failure_category is None

    def test_to_dict_with_steps(self):
        step = StepExecutionResult(
            step_number=1, action_type=ActionType.CLICK, status=ExecutionStatus.PASSED,
        )
        d = TestExecutionResult(
            case_id=100, status=ExecutionStatus.PASSED, duration_ms=200,
            total_steps=1, passed_steps=1, steps=[step],
        ).to_dict()
        assert d["case_id"] == 100
        assert d["status"] == "passed"
        assert d["total_steps"] == 1
        assert d["failure_category"] is None
        assert len(d["steps"]) == 1
        assert d["steps"][0]["step_number"] == 1

    def test_to_dict_minimal_and_hidden_fields(self):
        d = TestExecutionResult(case_id=200, status=ExecutionStatus.RUNNING).to_dict()
        assert d["case_id"] == 200
        assert d["status"] == "running"
        assert d["steps"] == []
        d_hidden = TestExecutionResult(case_id=1, duration_ms=100).to_dict(
            hidden_fields=["duration_ms", "navigation_level"]
        )
        assert "duration_ms" not in d_hidden
        assert "navigation_level" not in d_hidden
        assert d_hidden["case_id"] == 1


class TestHandleExecutionErrors:
    """handle_execution_errors 装饰器 - 异常转换语义与异常类继承关系。"""

    def test_exception_hierarchy(self):
        assert issubclass(StepExecutionError, ExecutionError)
        assert issubclass(VerificationError, ExecutionError)

    @pytest.mark.asyncio
    async def test_reraise_execution_error(self):
        @handle_execution_errors
        async def func():
            raise StepExecutionError("step error")

        with pytest.raises(StepExecutionError, match="step error"):
            await func()

    @pytest.mark.asyncio
    async def test_wrap_generic_exception_into_step_error(self):
        @handle_execution_errors
        async def func():
            raise ValueError("value error")

        with pytest.raises(StepExecutionError, match="执行失败") as exc_info:
            await func()
        assert isinstance(exc_info.value.__cause__, ValueError)

    @pytest.mark.asyncio
    async def test_success(self):
        @handle_execution_errors
        async def func():
            return "ok"

        assert await func() == "ok"


class TestParseStepAction:
    """_parse_step_action - 动作文本解析为 ActionType。"""

    @pytest.mark.parametrize("action,expected", [
        ("导航到首页", ActionType.NAVIGATE), ("navigate to page", ActionType.NAVIGATE),
        ("访问百度", ActionType.NAVIGATE), ("在输入框输入hello", ActionType.INPUT),
        ("填写用户名", ActionType.INPUT), ("input text into field", ActionType.INPUT),
        ("点击提交按钮", ActionType.CLICK), ("click the button", ActionType.CLICK),
        ("验证页面标题", ActionType.VERIFY), ("检查元素是否存在", ActionType.VERIFY),
        ("等待3秒", ActionType.WAIT), ("滚动到页面底部", ActionType.SCROLL),
        ("悬停在菜单上", ActionType.HOVER), ("选择下拉选项", ActionType.SELECT),
        ("验证码识别", ActionType.CAPTCHA), ("刷新页面", ActionType.REFRESH),
        ("按下回车键", ActionType.KEYPRESS), ("未知操作xxx", ActionType.CLICK),
    ])
    def test_parse_action_type(self, db_session, action, expected):
        assert _makeEngine(db_session)._parse_step_action(action)["type"] == expected

    def test_parse_returns_text_field(self, db_session):
        assert _makeEngine(db_session)._parse_step_action("点击提交按钮")["text"] == "点击提交按钮"


class TestExtractUrl:
    """_extract_url - 从文本中提取 URL。"""

    @pytest.mark.parametrize("text,expected", [
        ("导航到 https://www.example.com", "https://www.example.com"),
        ("访问 http://test.com", "http://test.com"),
        ("点击按钮", None), ("无URL文本", None),
    ])
    def test_extract_url(self, db_session, text, expected):
        assert _makeEngine(db_session)._extract_url(text) == expected


class TestExtractInputText:
    """_extract_input_text - 从文本中提取输入内容。"""

    @pytest.mark.parametrize("text,expected", [
        ('输入"hello"到文本框', "hello"), ("输入'world'到文本框", "world"),
        ('输入"你好"到文本框', "你好"), ("输入 testvalue", "testvalue"),
        ("填写 mydata", "mydata"), ("随便操作", "test"),
    ])
    def test_extract_input_text(self, db_session, text, expected):
        assert _makeEngine(db_session)._extract_input_text(text) == expected


class TestExtractWaitTime:
    """_extract_wait_time - 从文本中提取等待秒数。"""

    @pytest.mark.parametrize("text,expected", [
        ("等待3秒", 3), ("wait 5 seconds", 5),
        ("等待一会", 2), ("无等待时间文本", 2),
    ])
    def test_extract_wait_time(self, db_session, text, expected):
        assert _makeEngine(db_session)._extract_wait_time(text) == expected


class TestSubstituteParametersInAction:
    """_substitute_parameters_in_action - ${field} 占位符替换。"""

    @pytest.mark.parametrize("action,test_data,expected", [
        ("输入${username}到用户名框", {"username": "admin"}, "输入admin到用户名框"),
        ("输入${username}和${password}", {"username": "admin", "password": "123"}, "输入admin和123"),
        ("点击按钮", {"key": "val"}, "点击按钮"),
        ("输入${x}", {}, "输入${x}"),
    ])
    def test_substitute(self, db_session, action, test_data, expected):
        result = _makeEngine(db_session)._substitute_parameters_in_action(action, test_data)
        assert result == expected


class TestGenerateExecutionSummary:
    """_generate_execution_summary - 返回字典格式摘要 (新签名 result, test_case)。"""

    def test_summary_passed(self, db_session):
        result = TestExecutionResult(
            case_id=1, status=ExecutionStatus.PASSED, total_steps=2,
            passed_steps=2, failed_steps=0, duration_ms=200,
        )
        summary = _makeEngine(db_session)._generate_execution_summary(
            result, TestCase(case_no="TC-001", title="测试用例")
        )
        assert summary == {
            "case_id": 1, "case_no": "TC-001", "title": "测试用例", "status": "passed",
            "total_steps": 2, "passed_steps": 2, "failed_steps": 0, "duration_ms": 200,
            "failure_category": None, "navigation_level": None,
        }

    def test_summary_failed_with_category(self, db_session):
        result = TestExecutionResult(
            case_id=2, status=ExecutionStatus.FAILED, total_steps=3,
            failure_category=FailureCategory.PRODUCT_BUG, navigation_level="level2",
        )
        summary = _makeEngine(db_session)._generate_execution_summary(
            result, TestCase(case_no="TC-002", title="失败用例")
        )
        assert summary["status"] == "failed"
        assert summary["failure_category"] == "product_bug"
        assert summary["navigation_level"] == "level2"
