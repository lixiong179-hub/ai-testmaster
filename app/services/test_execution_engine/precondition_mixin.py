"""Precondition execution mixin for web and mobile test runs."""

import asyncio
import json
from typing import Any, Dict, Optional

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

        if self.precondition_service.is_browser_ready:
            login_valid = await self._check_precondition_status()
            if login_valid:
                info = getattr(self.precondition_service, "test_object_info", None)
                browser = getattr(self.precondition_service, "browser_controller", None)
                if info and getattr(info, "url", None) and browser:
                    try:
                        await browser.navigate(info.url)
                        self.browser = browser
                        if self.locator_service:
                            self.locator_service.browser = browser
                    except Exception as e:
                        logger.warning(f"Failed to reset page before case; rebuilding precondition: {e}")
                    else:
                        logger.info("Reused logged-in browser session for case")
                        return

            logger.info("Browser exists but login state is invalid; rebuilding web precondition")
            await self.precondition_service.cleanup()

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

    def _resolve_web_env_config(self, project, target_env: str) -> Dict[str, Any]:
        raw_web_cfg = getattr(project, "web_env_configs", None)
        resolved_web_cfg = None

        if raw_web_cfg:
            if isinstance(raw_web_cfg, dict):
                resolved_web_cfg = raw_web_cfg
            elif isinstance(raw_web_cfg, str):
                try:
                    parsed = json.loads(raw_web_cfg)
                    if isinstance(parsed, dict):
                        resolved_web_cfg = parsed
                    elif isinstance(parsed, str):
                        inner = json.loads(parsed)
                        if isinstance(inner, dict):
                            resolved_web_cfg = inner
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

        if not resolved_web_cfg:
            return {}

        env_config = resolved_web_cfg.get(target_env, {})
        if env_config:
            return env_config

        available_envs = list(resolved_web_cfg.keys())
        if available_envs:
            fallback_env = available_envs[0]
            logger.warning(f"Target env '{target_env}' not found; fallback to '{fallback_env}'")
            return resolved_web_cfg.get(fallback_env, {})

        logger.warning("No usable web env config found; falling back to project default config")
        return {}

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
            if hasattr(step, "action_type") and step.action_type:
                action_type_str = step.action_type.lower()
                action_type_map = {
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
                action_type = action_type_map.get(action_type_str, ActionType.CLICK)
                action_info = {"type": action_type, "text": step.action}
            else:
                action_info = self._parse_step_action(step.action)
                action_type = action_info.get("type", ActionType.CLICK)

            if action_type == ActionType.INPUT and hasattr(step, "input_value") and step.input_value:
                action_info["input_value"] = step.input_value

            locator_record = None
            if self.locator_service and step.id:
                locator_record = self.db.query(ElementLocator).filter(
                    ElementLocator.precondition_step_id == step.id
                ).first()

            if action_type == ActionType.NAVIGATE:
                await self._execute_navigate(action_info)
            elif action_type in (ActionType.INPUT, ActionType.CLICK, ActionType.HOVER, ActionType.SELECT):
                if locator_record:
                    await self._execute_action_directly(action_type, action_info, locator_record)
                else:
                    element_info = await self.smart_locate_with_ai_fallback(step.action)
                    if element_info:
                        temp_locator = ElementLocator(
                            css_selector=element_info.get("css_selector"),
                            ai_coordinate=element_info,
                        )
                        await self._execute_action_directly(action_type, action_info, temp_locator)
                    else:
                        raise StepExecutionError(
                            f"Precondition step {step.step_number}: unable to locate element - {step.action}"
                        )
            elif action_type == ActionType.VERIFY:
                await self._execute_verify(action_info, step.id)
            elif action_type == ActionType.WAIT:
                await self._execute_wait(action_info)
            elif action_type == ActionType.SCROLL:
                await self._execute_scroll(action_info)
            elif action_type in (ActionType.CAPTCHA, ActionType.VERIFY_CAPTCHA):
                await self._execute_captcha(action_info, step.id)
            elif action_type == ActionType.REFRESH:
                await self._execute_refresh(action_info)
            elif action_type in (ActionType.KEYPRESS, ActionType.KEYBOARD):
                await self._execute_keypress(action_info)
            else:
                await self._execute_click(action_info, step.id)

            await asyncio.sleep(2)

            if self.browser:
                result.screenshot = await self.browser.take_screenshot()

            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)

            result.status = ExecutionStatus.PASSED
            result.end_time = end_time
            result.duration_ms = duration
            result.ai_analysis = f"Precondition step action: {step.action}"

            logger.info(f"Precondition step {step.step_number} passed")

        except Exception as e:
            end_time = utcnow()
            duration = int((end_time - start_time).total_seconds() * 1000)

            result.status = ExecutionStatus.FAILED
            result.end_time = end_time
            result.duration_ms = duration
            result.error_message = str(e)

            if self.browser:
                try:
                    result.screenshot = await self.browser.take_screenshot()
                except Exception as screenshot_error:
                    logger.debug(
                        f"Failed to capture failed precondition step screenshot: {screenshot_error}"
                    )

            logger.error(f"Precondition step {step.step_number} failed: {e}")

        return result

    async def _save_realtime_locator(self, step: TestStep, element_info: Dict[str, Any]) -> Optional[ElementLocator]:
        if not self.locator_service or not self.browser:
            return None
        try:
            confidence = element_info.get("confidence", 0)
            if confidence < 0.8:
                logger.info(
                    f"Step {step.step_number}: realtime locator confidence {confidence} < 0.8; skip cache"
                )
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

    async def _get_current_page_title(self) -> Optional[str]:
        try:
            if self.browser:
                title = await self.browser.execute_javascript("document.title")
                return title if isinstance(title, str) else None
        except Exception as e:
            logger.debug(f"Failed to get current page title: {e}")
        return None

    async def _execute_mobile_step(self, step: TestStep, action_with_data: str, execution_mode: str, result: StepExecutionResult) -> None:
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
