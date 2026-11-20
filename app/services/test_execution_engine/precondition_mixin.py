"""Precondition execution mixin for web and mobile test runs."""

import asyncio
import json
from typing import Any

from loguru import logger

from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.models.test_case import TestStep
from app.services.test_execution_engine.models import (
    ActionType,
    ExecutionStatus,
    StepExecutionError,
    StepExecutionResult,
)
from app.utils.db_time import utcnow

_INTERACTIVE_ACTIONS = (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT)

# 显式 action_type 字符串 → 动作类型（未知值回落 CLICK）
_PRECONDITION_ACTION_MAP: dict[str, ActionType] = {
    "click": ActionType.CLICK,
    "input": ActionType.INPUT,
    "navigate": ActionType.NAVIGATE,
    "verify": ActionType.VERIFY,
    "wait": ActionType.WAIT,
    "scroll": ActionType.SCROLL,
    "hover": ActionType.HOVER,
    "select": ActionType.SELECT,
    "captcha": ActionType.CAPTCHA,
    "verify_captcha": ActionType.VERIFY_CAPTCHA,
    "refresh": ActionType.REFRESH,
    "keypress": ActionType.KEYPRESS,
    "keyboard": ActionType.KEYBOARD,
}

# 非交互动作分派表：(方法名, 是否传入 step.id)
_PRECONDITION_HANDLERS: dict[ActionType, tuple[str, bool]] = {
    ActionType.NAVIGATE: ("_execute_navigate", False),
    ActionType.VERIFY: ("_execute_verify", True),
    ActionType.WAIT: ("_execute_wait", False),
    ActionType.SCROLL: ("_execute_scroll", False),
    ActionType.CAPTCHA: ("_execute_captcha", True),
    ActionType.VERIFY_CAPTCHA: ("_execute_captcha", True),
    ActionType.REFRESH: ("_execute_refresh", False),
    ActionType.KEYPRESS: ("_execute_keypress", False),
    ActionType.KEYBOARD: ("_execute_keypress", False),
}


def _parse_env_configs(raw: Any) -> dict[str, Any] | None:
    """解析 web_env_configs（dict / JSON 串 / 双层编码串），失败返回 None。"""
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            inner = json.loads(parsed)
            if isinstance(inner, dict):
                return inner
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    return None


def _pick_env_config(resolved: dict[str, Any], target_env: str) -> dict[str, Any]:
    """取目标环境配置；缺失时回退首个可用环境，完全无配置返回空 dict。"""
    env_config = resolved.get(target_env, {})
    if env_config:
        return env_config
    available_envs = list(resolved.keys())
    if not available_envs:
        logger.warning("No usable web env config found; falling back to project default config")
        return {}
    fallback_env = available_envs[0]
    logger.warning(f"Target env '{target_env}' not found; fallback to '{fallback_env}'")
    return resolved.get(fallback_env, {})


class PreconditionMixin:
    async def _check_precondition_status(self) -> bool:
        if not self.precondition_service:
            return True
        if not self.precondition_service.is_browser_ready:
            return False
        try:
            login_valid = await self.precondition_service.check_login_status()
            logger.info("Login state is valid" if login_valid else "Login state is invalid")
            return login_valid
        except Exception as e:
            logger.warning(f"Login state check failed: {e}")
            return False

    async def _execute_precondition(
        self,
        project_id: int,
        target_env: str = "test",
        skip_init: bool = False,
    ) -> None:
        if not self.precondition_service:
            logger.warning("Precondition service is not initialized; skipping precondition")
            return

        logger.info(f"Executing precondition target_env={target_env}, skip_init={skip_init}")

        if self.precondition_service.is_browser_ready and await self._try_reuse_browser_session():
            return

        await self._rebuild_web_precondition(project_id, target_env, skip_init)

    async def _try_reuse_browser_session(self) -> bool:
        """登录态有效时复用浏览器；返回是否可直接复用。"""
        login_valid = await self._check_precondition_status()
        if not login_valid:
            logger.info("Browser exists but login state is invalid; rebuilding web precondition")
            await self.precondition_service.cleanup()
            return False

        info = getattr(self.precondition_service, "test_object_info", None)
        browser = getattr(self.precondition_service, "browser_controller", None)
        if not (info and getattr(info, "url", None) and browser):
            return False

        try:
            await browser.navigate(info.url)
            self.browser = browser
            if self.locator_service:
                self.locator_service.browser = browser
        except Exception as e:
            logger.warning(f"Failed to reset page before case; rebuilding precondition: {e}")
            return False

        logger.info("Reused logged-in browser session for case")
        return True

    async def _rebuild_web_precondition(self, project_id: int, target_env: str, skip_init: bool) -> None:
        from app.models.project import Project

        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.warning(f"Project not found for precondition: {project_id}")
            return

        env_config = self._resolve_web_env_config(project, target_env)

        await self.precondition_service.read_test_object_info(
            project,
            env_config=env_config if env_config else None,
        )

        browser = await self.precondition_service.execute_web_precondition(
            headless=False,
            auto_login=(not skip_init),
        )
        if browser and hasattr(browser, "_page"):
            self.browser = browser

        if self.locator_service:
            self.locator_service.browser = browser

        logger.info("Precondition execution completed")

    def _resolve_web_env_config(self, project, target_env: str) -> dict[str, Any]:
        resolved = _parse_env_configs(getattr(project, "web_env_configs", None))
        if not resolved:
            return {}
        return _pick_env_config(resolved, target_env)

    async def _execute_precondition_step(self, step) -> StepExecutionResult:
        logger.info(f"Executing precondition step {step.step_number}: {step.action[:50]}...")

        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time,
        )

        try:
            action_type, action_info = self._resolve_precondition_action(step)
            locator_record = self._load_precondition_locator(step)
            await self._dispatch_precondition_action(step, action_type, action_info, locator_record)

            await asyncio.sleep(2)

            if self.browser:
                result.screenshot = await self.browser.take_screenshot()

            self._finish_precondition_result(result, start_time, ExecutionStatus.PASSED)
            result.ai_analysis = f"Precondition step action: {step.action}"

            logger.info(f"Precondition step {step.step_number} passed")

        except Exception as e:
            self._finish_precondition_result(result, start_time, ExecutionStatus.FAILED, str(e))

            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception as screenshot_error:
                    logger.debug(f"Failed to capture failed precondition step screenshot: {screenshot_error}")

            logger.error(f"Precondition step {step.step_number} failed: {e}")

        return result

    def _resolve_precondition_action(self, step) -> tuple[ActionType, dict[str, Any]]:
        """优先用显式 action_type，否则从动作文本解析。"""
        explicit_type = getattr(step, "action_type", None)
        if explicit_type:
            action_type = _PRECONDITION_ACTION_MAP.get(str(explicit_type).lower(), ActionType.CLICK)
            return action_type, {"type": action_type, "text": step.action}
        action_info = self._parse_step_action(step.action)
        return action_info.get("type", ActionType.CLICK), action_info

    def _load_precondition_locator(self, step):
        if not (self.locator_service and step.id):
            return None
        return self.db.query(ElementLocator).filter(ElementLocator.precondition_step_id == step.id).first()

    async def _dispatch_precondition_action(
        self, step, action_type: ActionType, action_info: dict[str, Any], locator_record
    ) -> None:
        if action_type == ActionType.INPUT and getattr(step, "input_value", None):
            action_info["input_value"] = step.input_value
        if action_type in _INTERACTIVE_ACTIONS:
            await self._dispatch_precondition_interactive(step, action_type, action_info, locator_record)
            return
        await self._dispatch_precondition_simple(step, action_type, action_info)

    async def _dispatch_precondition_interactive(
        self, step, action_type: ActionType, action_info: dict[str, Any], locator_record
    ) -> None:
        """已缓存定位直接执行，否则 AI 识别后构造临时定位执行。"""
        if locator_record:
            await self._execute_action_directly(action_type, action_info, locator_record)
            return

        element_info = await self.smart_locate_with_ai_fallback(step.action)
        if not element_info:
            raise StepExecutionError(f"Precondition step {step.step_number}: unable to locate element - {step.action}")
        temp_locator = ElementLocator(
            css_selector=element_info.get("css_selector"),
            ai_coordinate=element_info,
        )
        await self._execute_action_directly(action_type, action_info, temp_locator)

    async def _dispatch_precondition_simple(self, step, action_type: ActionType, action_info: dict[str, Any]) -> None:
        method_name, needs_step_id = _PRECONDITION_HANDLERS.get(action_type, ("_execute_click", True))
        handler = getattr(self, method_name)
        if needs_step_id:
            await handler(action_info, step.id)
        else:
            await handler(action_info)

    def _finish_precondition_result(
        self,
        result: StepExecutionResult,
        start_time,
        status: ExecutionStatus,
        error_message: str | None = None,
    ) -> None:
        end_time = utcnow()
        result.status = status
        result.end_time = end_time
        result.duration_ms = int((end_time - start_time).total_seconds() * 1000)
        if error_message is not None:
            result.error_message = error_message

    async def _save_realtime_locator(self, step: TestStep, element_info: dict[str, Any]) -> ElementLocator | None:
        if not self.locator_service or not self.browser:
            return None
        try:
            confidence = element_info.get("confidence", 0)
            if confidence < 0.8:
                logger.info(f"Step {step.step_number}: realtime locator confidence {confidence} < 0.8; skip cache")
                return None
            element_attrs = await self.locator_service._get_element_attributes(element_info)
            if not element_attrs:
                return None
            css_selector = self.locator_service._generate_css_selector(element_attrs)
            xpath = self.locator_service._generate_xpath(element_attrs)
            coordinate = self.locator_service._normalize_coordinate(element_info)
            locator = ElementLocator(
                step_id=step.id,
                element_description=step.action,
                element_type=element_attrs.get("tag"),
                css_selector=css_selector,
                xpath=xpath,
                element_id=element_attrs.get("id"),
                element_name=element_attrs.get("name"),
                element_class=element_attrs.get("class"),
                element_text=element_attrs.get("text"),
                ai_coordinate=coordinate,
                ai_confidence=confidence,
                source="ai_realtime",
            )
            self.db.add(locator)
            self.db.commit()
            self.db.refresh(locator)
            step_record = self.db.query(TestStep).filter(TestStep.id == step.id).first()
            if step_record:
                step_record.has_locator = 1
                step_record.locator_status = LocatorStatus.RECORDED.value
                self.db.commit()
            logger.info(f"Step {step.step_number}: realtime locator cached, id={locator.id}")
            return locator
        except Exception as e:
            logger.warning(f"Failed to save realtime locator: {e}")
            return None

    async def _get_current_page_title(self) -> str | None:
        try:
            if self.browser:
                title = await self.browser.execute_javascript("document.title")
                return title if isinstance(title, str) else None
        except Exception as e:
            logger.debug(f"Failed to get current page title: {e}")
        return None

    async def _execute_mobile_step(
        self, step: TestStep, action_with_data: str, execution_mode: str, result: StepExecutionResult
    ) -> None:
        mobile_executor = self._get_mobile_executor()
        if not mobile_executor:
            raise StepExecutionError("Mobile executor is not initialized; check ADB connection")
        use_cache = execution_mode == "mobile_smart"
        action_result = await mobile_executor.execute_action(
            description=action_with_data,
            step_id=step.id,
            use_cache=use_cache,
        )
        if action_result.coordinates:
            result.element_locator = action_result.coordinates
        result.ai_analysis = f"Mobile AI execution: {action_with_data}"
        if action_result.used_cache:
            result.ai_analysis += " (cache hit)"
        if not action_result.success:
            raise StepExecutionError(action_result.error_message or "Mobile execution failed")

    def _get_mobile_executor(self) -> Any:
        if self._mobile_executor is None:
            try:
                from app.services.mobile_ai_executor import MobileAIExecutor
                from app.utils.adb_controller import AdbController

                adb = AdbController(udid=self._mobile_device_id)
                self._mobile_executor = MobileAIExecutor(db=self.db, adb=adb)
            except Exception as e:
                logger.warning(f"Failed to initialize MobileAIExecutor: {e}")
        return self._mobile_executor
