"""前置条件执行Mixin - 在测试执行前自动完成环境准备。
"""
import json
import asyncio
from typing import Optional, Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep, TestCaseExecution
from app.models.element_locator import ElementLocator
from app.models.enums import LocatorStatus
from app.services.precondition_service import PreconditionService
from app.services.element_locator_service import ElementLocatorService
from app.utils.browser_controller_v2 import BrowserControllerV2
from app.utils.unified_vision_model import UnifiedVisionModel
from app.utils.db_time import utcnow

from app.services.test_execution_engine.models import (
    ExecutionStatus, ActionType, ExecutionMode, StepExecutionError,
    StepExecutionResult, TestExecutionResult, handle_execution_errors,
)


class PreconditionMixin:

    async def _check_precondition_status(self) -> bool:
        if not self.precondition_service:
            return True
        if not self.precondition_service.is_browser_ready:
            return False
        try:
            login_valid = await self.precondition_service.check_login_status()
            if login_valid:
                logger.info("登录状态检测: 有效")
            else:
                logger.info("登录状态检测: 无效，需要重新登录")
            return login_valid
        except Exception as e:
            logger.warning(f"登录状态检测异常: {e}")
            return False

    async def _execute_precondition(
        self,
        project_id: int,
        target_env: str = "test",
        skip_init: bool = False
    ) -> None:
        if not self.precondition_service:
            logger.warning("前置条件服务未初始化，跳过前置条件执行")
            return

        logger.info(f"执行前置条件 (环境={target_env}, 跳过初始化={skip_init})")

        if not self.precondition_service.is_browser_ready:
            from app.models.project import Project
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                env_config = {}
                raw_web_cfg = getattr(project, 'web_env_configs', None)
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

                if resolved_web_cfg:
                    env_config = resolved_web_cfg.get(target_env, {})
                    if not env_config:
                        available_envs = list(resolved_web_cfg.keys())
                        if available_envs:
                            fallback_env = available_envs[0]
                            env_config = resolved_web_cfg.get(fallback_env, {})
                            logger.warning(f"目标环境 '{target_env}' 不存在，回退到 '{fallback_env}'")
                        else:
                            logger.warning(f"项目无可用环境配置，使用项目默认配置")

                await self.precondition_service.read_test_object_info(
                    project,
                    env_config=env_config if env_config else None
                )

                browser = await self.precondition_service.execute_web_precondition(
                    headless=False,
                    auto_login=(not skip_init)
                )
                if browser and hasattr(browser, '_page'):
                    self.browser = browser

                if self.locator_service:
                    self.locator_service.browser = browser

        logger.info("前置条件执行完成")

    async def _execute_precondition_step(self, step) -> StepExecutionResult:
        logger.info(f"执行前置条件步骤 {step.step_number}: {step.action[:50]}...")

        start_time = utcnow()
        result = StepExecutionResult(
            step_number=step.step_number,
            action=step.action,
            status=ExecutionStatus.RUNNING,
            start_time=start_time
        )

        try:
            if hasattr(step, 'action_type') and step.action_type:
                action_type_str = step.action_type.lower()
                action_type_map = {
                    "click": ActionType.CLICK, "input": ActionType.INPUT,
                    "navigate": ActionType.NAVIGATE, "verify": ActionType.VERIFY,
                    "wait": ActionType.WAIT, "scroll": ActionType.SCROLL,
                    "hover": ActionType.HOVER, "select": ActionType.SELECT,
                    "captcha": ActionType.CAPTCHA, "refresh": ActionType.REFRESH,
                    "keypress": ActionType.KEYPRESS,
                }
                action_type = action_type_map.get(action_type_str, ActionType.CLICK)
                action_info = {"type": action_type, "text": step.action}
            else:
                action_info = self._parse_step_action(step.action)
                action_type = action_info.get("type", ActionType.CLICK)

            if action_type == ActionType.INPUT and hasattr(step, 'input_value') and step.input_value:
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
                            css_selector=element_info.get('css_selector'),
                            ai_coordinate=element_info
                        )
                        await self._execute_action_directly(action_type, action_info, temp_locator)
                    else:
                        raise StepExecutionError(f"前置条件步骤 {step.step_number}: 无法定位元素 - {step.action}")
            elif action_type == ActionType.VERIFY:
                await self._execute_verify(action_info, step.id)
            elif action_type == ActionType.WAIT:
                await self._execute_wait(action_info)
            elif action_type == ActionType.SCROLL:
                await self._execute_scroll(action_info)
            elif action_type == ActionType.CAPTCHA:
                await self._execute_captcha(action_info, step.id)
            elif action_type == ActionType.REFRESH:
                await self._execute_refresh(action_info)
            elif action_type == ActionType.KEYPRESS:
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
            result.ai_analysis = f"前置条件步骤执行动作: {step.action}"

            logger.info(f"前置条件步骤 {step.step_number} 执行成功")

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
                except Exception:
                    pass

            logger.error(f"前置条件步骤 {step.step_number} 执行失败: {str(e)}")

        return result

    async def _save_realtime_locator(self, step: TestStep, element_info: Dict[str, Any]) -> Optional[ElementLocator]:
        if not self.locator_service or not self.browser:
            return None
        try:
            confidence = element_info.get("confidence", 0)
            if confidence < 0.8:
                logger.info(f"步骤 {step.step_number}: 实时识别置信度 {confidence} < 0.8，跳过缓存")
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
                source="ai_realtime"
            )
            self.db.add(locator)
            self.db.commit()
            self.db.refresh(locator)
            step_record = self.db.query(TestStep).filter(TestStep.id == step.id).first()
            if step_record:
                step_record.has_locator = 1
                step_record.locator_status = LocatorStatus.RECORDED.value
                self.db.commit()
            logger.info(f"步骤 {step.step_number}: 实时定位信息已缓存，ID={locator.id}")
            return locator
        except Exception as e:
            logger.warning(f"保存实时定位信息失败: {e}")
            return None

    async def _get_current_page_title(self) -> Optional[str]:
        try:
            if self.browser:
                title = await self.browser.execute_javascript("document.title")
                return title if isinstance(title, str) else None
        except Exception as e:
            logger.debug(f"获取页面标题失败: {e}")
        return None

    async def _execute_mobile_step(self, step: TestStep, action_with_data: str, execution_mode: str, result: StepExecutionResult) -> None:
        mobile_executor = self._get_mobile_executor()
        if not mobile_executor:
            raise StepExecutionError("移动端执行器未初始化，请检查ADB连接")
        use_cache = execution_mode == ExecutionMode.MOBILE_SMART.value
        action_result = await mobile_executor.execute_action(
            description=action_with_data, step_id=step.id, use_cache=use_cache,
        )
        if action_result.coordinates:
            result.element_locator = action_result.coordinates
        result.ai_analysis = f"移动端AI执行: {action_with_data}"
        if action_result.used_cache:
            result.ai_analysis += " (缓存命中)"
        if not action_result.success:
            raise StepExecutionError(action_result.error_message or "移动端执行失败")

    def _get_mobile_executor(self) -> Any:
        if self._mobile_executor is None:
            try:
                from app.services.mobile_ai_executor import MobileAIExecutor
                from app.utils.adb_controller import AdbController
                adb = AdbController(udid=self._mobile_device_id)
                self._mobile_executor = MobileAIExecutor(db=self.db, adb=adb)
            except Exception as e:
                logger.warning(f"初始化MobileAIExecutor失败: {e}")
        return self._mobile_executor
