import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.test_execution_engine.action_executor_basic_mixin import ActionExecutorBasicMixin
from app.services.test_execution_engine.action_executor_mixin import ActionExecutorMixin
from app.services.test_execution_engine.models import ActionType, StepExecutionError


class _ConcreteExecutor(ActionExecutorBasicMixin):
    def __init__(self):
        self.browser = None


class TestParseStepAction:
    def setup_method(self):
        self.executor = _ConcreteExecutor()

    def test_navigate_chinese(self):
        result = self.executor._parse_step_action("导航到首页")
        assert result["type"] == ActionType.NAVIGATE

    def test_navigate_visit(self):
        result = self.executor._parse_step_action("访问百度")
        assert result["type"] == ActionType.NAVIGATE

    def test_navigate_open(self):
        result = self.executor._parse_step_action("打开页面")
        assert result["type"] == ActionType.NAVIGATE

    def test_navigate_english(self):
        result = self.executor._parse_step_action("navigate to page")
        assert result["type"] == ActionType.NAVIGATE

    def test_captcha_chinese(self):
        result = self.executor._parse_step_action("验证码识别")
        assert result["type"] == ActionType.VERIFY_CAPTCHA

    def test_captcha_english(self):
        result = self.executor._parse_step_action("solve captcha")
        assert result["type"] == ActionType.VERIFY_CAPTCHA

    def test_refresh_chinese(self):
        result = self.executor._parse_step_action("刷新页面")
        assert result["type"] == ActionType.REFRESH

    def test_refresh_english(self):
        result = self.executor._parse_step_action("refresh page")
        assert result["type"] == ActionType.REFRESH

    def test_keypress_chinese(self):
        result = self.executor._parse_step_action("按下回车键")
        assert result["type"] == ActionType.KEYBOARD

    def test_keypress_english(self):
        result = self.executor._parse_step_action("press key Enter")
        assert result["type"] == ActionType.KEYBOARD

    def test_input_chinese(self):
        result = self.executor._parse_step_action("输入用户名")
        assert result["type"] == ActionType.INPUT

    def test_input_fill(self):
        result = self.executor._parse_step_action("填写密码")
        assert result["type"] == ActionType.INPUT

    def test_input_english(self):
        result = self.executor._parse_step_action("input text")
        assert result["type"] == ActionType.INPUT

    def test_click_chinese(self):
        result = self.executor._parse_step_action("点击登录")
        assert result["type"] == ActionType.CLICK

    def test_click_english(self):
        result = self.executor._parse_step_action("click button")
        assert result["type"] == ActionType.CLICK

    def test_verify_chinese(self):
        result = self.executor._parse_step_action("验证页面内容")
        assert result["type"] == ActionType.VERIFY

    def test_verify_check(self):
        result = self.executor._parse_step_action("检查元素")
        assert result["type"] == ActionType.VERIFY

    def test_verify_english(self):
        result = self.executor._parse_step_action("assert element")
        assert result["type"] == ActionType.VERIFY

    def test_wait_chinese(self):
        result = self.executor._parse_step_action("等待3秒")
        assert result["type"] == ActionType.WAIT

    def test_wait_english(self):
        result = self.executor._parse_step_action("wait for element")
        assert result["type"] == ActionType.WAIT

    def test_scroll_chinese(self):
        result = self.executor._parse_step_action("滚动到底部")
        assert result["type"] == ActionType.SCROLL

    def test_scroll_english(self):
        result = self.executor._parse_step_action("scroll down")
        assert result["type"] == ActionType.SCROLL

    def test_hover_chinese(self):
        result = self.executor._parse_step_action("悬停在菜单上")
        assert result["type"] == ActionType.HOVER

    def test_hover_english(self):
        result = self.executor._parse_step_action("hover over element")
        assert result["type"] == ActionType.HOVER

    def test_select_chinese(self):
        result = self.executor._parse_step_action("选择选项")
        assert result["type"] == ActionType.SELECT

    def test_select_english(self):
        result = self.executor._parse_step_action("select option")
        assert result["type"] == ActionType.SELECT

    def test_unknown_defaults_to_click(self):
        result = self.executor._parse_step_action("未知操作")
        assert result["type"] == ActionType.CLICK


class TestExtractUrl:
    def setup_method(self):
        self.executor = _ConcreteExecutor()

    def test_extract_http_url(self):
        result = self.executor._extract_url("访问 https://example.com/page")
        assert result == "https://example.com/page"

    def test_extract_no_url(self):
        result = self.executor._extract_url("点击按钮")
        assert result is None

    def test_extract_http_url(self):
        result = self.executor._extract_url("打开 http://test.com")
        assert result == "http://test.com"


class TestExtractKey:
    def setup_method(self):
        self.executor = _ConcreteExecutor()

    def test_enter_key(self):
        assert self.executor._extract_key("按下回车") == "Enter"

    def test_enter_english(self):
        assert self.executor._extract_key("press Enter") == "Enter"

    def test_tab_key(self):
        assert self.executor._extract_key("按下Tab") == "Tab"

    def test_tab_chinese(self):
        assert self.executor._extract_key("按下制表键") == "Tab"

    def test_escape_key(self):
        assert self.executor._extract_key("按下Escape") == "Escape"

    def test_esc_key(self):
        assert self.executor._extract_key("按下ESC") == "Escape"

    def test_space_key(self):
        assert self.executor._extract_key("按下空格") == "Space"

    def test_space_english(self):
        assert self.executor._extract_key("press Space") == "Space"

    def test_default_enter(self):
        assert self.executor._extract_key("未知按键") == "Enter"


class TestExtractWaitTime:
    def setup_method(self):
        self.executor = _ConcreteExecutor()

    def test_seconds_chinese(self):
        assert self.executor._extract_wait_time("等待5秒") == 5

    def test_seconds_english(self):
        assert self.executor._extract_wait_time("wait 3 seconds") == 3

    def test_second_english(self):
        assert self.executor._extract_wait_time("wait 1 second") == 1

    def test_default(self):
        assert self.executor._extract_wait_time("等待") == 2

    def test_no_number(self):
        assert self.executor._extract_wait_time("等待片刻") == 2


class TestExecuteNavigate:
    @pytest.mark.asyncio
    async def test_navigate_no_browser(self):
        executor = _ConcreteExecutor()
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await executor._execute_navigate({"text": "访问 https://example.com"})

    @pytest.mark.asyncio
    async def test_navigate_no_url(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        with pytest.raises(StepExecutionError, match="无法从动作中提取URL"):
            await executor._execute_navigate({"text": "点击按钮"})

    @pytest.mark.asyncio
    async def test_navigate_success(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.navigate = AsyncMock()
        await executor._execute_navigate({"text": "访问 https://example.com"})
        executor.browser.navigate.assert_called_once()


class TestExecuteRefresh:
    @pytest.mark.asyncio
    async def test_refresh_no_browser(self):
        executor = _ConcreteExecutor()
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await executor._execute_refresh({})

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.refresh = AsyncMock()
        await executor._execute_refresh({})
        executor.browser.refresh.assert_called_once()


class TestExecuteKeypress:
    @pytest.mark.asyncio
    async def test_keypress_no_browser(self):
        executor = _ConcreteExecutor()
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await executor._execute_keypress({"text": "按下Enter"})

    @pytest.mark.asyncio
    async def test_keypress_success(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.press_key = AsyncMock()
        await executor._execute_keypress({"text": "按下Enter"})
        executor.browser.press_key.assert_called_once_with("Enter")


class TestExecuteWait:
    @pytest.mark.asyncio
    async def test_wait_default(self):
        executor = _ConcreteExecutor()
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await executor._execute_wait({"text": "等待"})
            mock_sleep.assert_called_once_with(2)

    @pytest.mark.asyncio
    async def test_wait_specific(self):
        executor = _ConcreteExecutor()
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await executor._execute_wait({"text": "等待5秒"})
            mock_sleep.assert_called_once_with(5)


class TestExecuteScroll:
    @pytest.mark.asyncio
    async def test_scroll_no_browser(self):
        executor = _ConcreteExecutor()
        with pytest.raises(StepExecutionError, match="浏览器未初始化"):
            await executor._execute_scroll({"text": "向下滚动"})

    @pytest.mark.asyncio
    async def test_scroll_down(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.execute_javascript = AsyncMock()
        await executor._execute_scroll({"text": "向下滚动"})
        executor.browser.execute_javascript.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_up(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.execute_javascript = AsyncMock()
        await executor._execute_scroll({"text": "向上滚动"})
        executor.browser.execute_javascript.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_default(self):
        executor = _ConcreteExecutor()
        executor.browser = MagicMock()
        executor.browser.execute_javascript = AsyncMock()
        await executor._execute_scroll({"text": "滚动"})
        executor.browser.execute_javascript.assert_called_once()


class TestActionExecutorMixin:
    def test_inherits_basic_and_complex(self):
        assert issubclass(ActionExecutorMixin, ActionExecutorBasicMixin)

    @pytest.mark.asyncio
    async def test_execute_action(self):
        class MockExecutor(ActionExecutorMixin):
            def __init__(self):
                self.browser = None

            async def _execute_action_by_type(self, action_type, action_info, step_id, test_data):
                self._called = (action_type, action_info, step_id, test_data)

        executor = MockExecutor()
        step = MagicMock()
        step.id = 42
        action_info = {"type": ActionType.CLICK, "text": "点击按钮"}
        await executor.execute_action(step, action_info)
        assert executor._called[0] == ActionType.CLICK
        assert executor._called[2] == 42

    @pytest.mark.asyncio
    async def test_execute_action_no_step_id(self):
        class MockExecutor(ActionExecutorMixin):
            def __init__(self):
                self.browser = None

            async def _execute_action_by_type(self, action_type, action_info, step_id, test_data):
                self._called_step_id = step_id

        executor = MockExecutor()
        step = MagicMock(spec=[])
        action_info = {"type": ActionType.CLICK, "text": "点击按钮"}
        await executor.execute_action(step, action_info)
        assert executor._called_step_id is None
