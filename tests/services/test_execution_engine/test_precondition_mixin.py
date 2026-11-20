"""PreconditionMixin 行为护栏（G-8 B4 拆分前置测试）。

覆盖环境配置解析、浏览器会话复用/重建、前置步骤的动作解析与分派、失败兜底。
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.test_execution_engine.models import ActionType, ExecutionStatus
from app.services.test_execution_engine.precondition_mixin import PreconditionMixin

SLEEP_TARGET = "app.services.test_execution_engine.precondition_mixin.asyncio.sleep"


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def _step(**kwargs) -> _Obj:
    base = {"step_number": 1, "action": "点击登录", "id": 10, "action_type": "click", "input_value": ""}
    base.update(kwargs)
    return _Obj(**base)


class _Stub(PreconditionMixin):
    def __init__(self) -> None:
        self.precondition_service = None
        self.locator_service = MagicMock()
        self.browser = None
        self.db = MagicMock()
        self.calls: list[tuple[str, object]] = []
        self.locate_result: dict | None = {"css_selector": "#login"}
        self.direct_action_error: Exception | None = None
        self.simple_error: Exception | None = None

    def _parse_step_action(self, action_text):
        return {"type": ActionType.NAVIGATE, "text": action_text}

    # ---- 动作执行桩 ----
    async def _execute_navigate(self, action_info):
        self.calls.append(("navigate", action_info))

    async def _execute_verify(self, action_info, step_id):
        self.calls.append(("verify", (action_info, step_id)))

    async def _execute_wait(self, action_info):
        self.calls.append(("wait", action_info))

    async def _execute_scroll(self, action_info):
        self.calls.append(("scroll", action_info))

    async def _execute_captcha(self, action_info, step_id):
        self.calls.append(("captcha", (action_info, step_id)))

    async def _execute_refresh(self, action_info):
        self.calls.append(("refresh", action_info))

    async def _execute_keypress(self, action_info):
        self.calls.append(("keypress", action_info))

    async def _execute_click(self, action_info, step_id, step_test_data=None):
        self.calls.append(("click", (action_info, step_id)))
        if self.simple_error:
            raise self.simple_error

    async def _execute_action_directly(self, action_type, action_info, locator):
        self.calls.append(("direct", (action_type, locator)))
        if self.direct_action_error:
            raise self.direct_action_error

    async def smart_locate_with_ai_fallback(self, action):
        self.calls.append(("ai_locate", action))
        return self.locate_result


def _mock_service(*, browser_ready: bool = True, login_valid: bool = True, url: str = "https://x.test") -> MagicMock:
    service = MagicMock()
    service.is_browser_ready = browser_ready
    service.check_login_status = AsyncMock(return_value=login_valid)
    service.test_object_info = _Obj(url=url)
    service.browser_controller = MagicMock()
    service.browser_controller.navigate = AsyncMock()
    service.cleanup = AsyncMock()
    service.read_test_object_info = AsyncMock()
    service.execute_web_precondition = AsyncMock(return_value=None)
    return service


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_skips_without_service():
    stub = _Stub()
    await stub._execute_precondition(1)
    assert stub.db.query.called is False


async def test_precondition_reuses_logged_in_session():
    stub = _Stub()
    stub.precondition_service = _mock_service()
    stub.precondition_service.execute_web_precondition = AsyncMock(
        return_value=MagicMock(_page=object())
    )

    with patch(SLEEP_TARGET, new=AsyncMock()):
        await stub._execute_precondition(1)

    stub.precondition_service.browser_controller.navigate.assert_awaited_once_with("https://x.test")
    stub.precondition_service.read_test_object_info.assert_not_awaited()
    assert stub.browser is stub.precondition_service.browser_controller


async def test_precondition_rebuilds_when_login_invalid():
    stub = _Stub()
    service = _mock_service(login_valid=False)
    browser = MagicMock(_page=object())
    service.execute_web_precondition = AsyncMock(return_value=browser)
    stub.precondition_service = service
    project = _Obj(id=1, web_env_configs={"test": {"url": "https://t"}})
    stub.db.query.return_value.filter.return_value.first.return_value = project

    with patch(SLEEP_TARGET, new=AsyncMock()):
        await stub._execute_precondition(1, target_env="test")

    service.cleanup.assert_awaited_once()
    service.read_test_object_info.assert_awaited_once()
    assert service.read_test_object_info.await_args.kwargs["env_config"] == {"url": "https://t"}
    assert stub.browser is browser


async def test_precondition_project_missing_returns():
    stub = _Stub()
    stub.precondition_service = _mock_service(browser_ready=False)
    stub.db.query.return_value.filter.return_value.first.return_value = None

    with patch(SLEEP_TARGET, new=AsyncMock()):
        await stub._execute_precondition(99)

    stub.precondition_service.read_test_object_info.assert_not_awaited()


def test_resolve_web_env_config_target_hit():
    stub = _Stub()
    project = _Obj(web_env_configs={"test": {"url": "https://t"}, "prod": {"url": "https://p"}})
    assert stub._resolve_web_env_config(project, "prod") == {"url": "https://p"}


def test_resolve_web_env_config_double_encoded_json():
    stub = _Stub()
    raw = json.dumps(json.dumps({"uat": {"url": "https://u"}}))
    assert stub._resolve_web_env_config(_Obj(web_env_configs=raw), "uat") == {"url": "https://u"}


def test_resolve_web_env_config_falls_back_to_first_env():
    stub = _Stub()
    project = _Obj(web_env_configs='{"dev": {"url": "https://d"}}')
    assert stub._resolve_web_env_config(project, "prod") == {"url": "https://d"}


def test_resolve_web_env_config_empty():
    assert _Stub()._resolve_web_env_config(_Obj(web_env_configs=None), "test") == {}


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_uses_explicit_action_type():
    stub = _Stub()
    stub.browser = MagicMock()
    stub.browser.take_screenshot = AsyncMock(return_value="shot.png")
    stub.db.query.return_value.filter.return_value.first.return_value = None
    result = await stub._execute_precondition_step(_step(action_type="wait"))

    assert result.status == ExecutionStatus.PASSED
    assert stub.calls == [("wait", {"type": ActionType.WAIT, "text": "点击登录"})]
    assert result.screenshot == "shot.png"


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_parses_action_when_type_missing():
    stub = _Stub()
    stub.browser = None
    result = await stub._execute_precondition_step(_step(action_type=None, action="导航到首页"))

    assert result.status == ExecutionStatus.PASSED
    assert stub.calls[0][0] == "navigate"


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_uses_locator_record_directly():
    stub = _Stub()
    stub.browser = None
    locator = MagicMock()
    stub.db.query.return_value.filter.return_value.first.return_value = locator
    await stub._execute_precondition_step(_step())

    assert stub.calls[0][0] == "direct"
    assert stub.calls[0][1][0] == ActionType.CLICK
    assert stub.calls[0][1][1] is locator


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_ai_pick_fallback_builds_temp_locator():
    stub = _Stub()
    stub.browser = None
    stub.db.query.return_value.filter.return_value.first.return_value = None
    await stub._execute_precondition_step(_step())

    assert ("ai_locate", "点击登录") in stub.calls
    kinds = [c[0] for c in stub.calls]
    assert kinds == ["ai_locate", "direct"]


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_unlocatable_fails():
    stub = _Stub()
    stub.browser = None
    stub.locate_result = None
    stub.db.query.return_value.filter.return_value.first.return_value = None
    result = await stub._execute_precondition_step(_step())

    assert result.status == ExecutionStatus.FAILED
    assert "unable to locate element" in result.error_message


@patch(SLEEP_TARGET, new=AsyncMock())
async def test_precondition_step_failure_captures_screenshot():
    stub = _Stub()
    stub.browser = MagicMock()
    stub.browser.take_screenshot = AsyncMock(return_value="fail.png")
    stub.direct_action_error = RuntimeError("boom")
    stub.db.query.return_value.filter.return_value.first.return_value = None
    result = await stub._execute_precondition_step(_step(action_type="click"))

    assert result.status == ExecutionStatus.FAILED
    assert result.error_message == "boom"
    assert result.screenshot == "fail.png"
    assert result.end_time is not None
    assert result.duration_ms is not None
