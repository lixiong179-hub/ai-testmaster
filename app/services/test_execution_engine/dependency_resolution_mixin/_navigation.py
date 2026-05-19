import json
import re
from typing import Any, Dict, List, Optional
from loguru import logger

from app.models.test_case import TestCase


class _NavigationMixin:

    async def _execute_fallback_navigation(
        self, case: TestCase
    ) -> bool:
        fallback_steps_raw = getattr(case, 'fallback_steps', None)
        if not fallback_steps_raw:
            logger.info(f"用例 {case.case_no} 无 fallback_steps，跳过降级导航")
            return False

        try:
            if isinstance(fallback_steps_raw, str):
                fallback_steps = json.loads(fallback_steps_raw)
            elif isinstance(fallback_steps_raw, list):
                fallback_steps = fallback_steps_raw
            else:
                logger.warning(f"fallback_steps 类型异常: {type(fallback_steps_raw)}")
                return False
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"fallback_steps 解析失败: {e}")
            return False

        if not fallback_steps:
            return False

        is_mobile = getattr(self, '_mobile_device_id', None) is not None

        if is_mobile:
            return await self._execute_mobile_fallback_navigation(fallback_steps)

        if not self.browser or not getattr(self.browser, '_page', None):
            logger.warning("浏览器未初始化，无法执行降级导航")
            return False

        logger.info(
            f"开始降级导航: 用例 {case.case_no}, "
            f"共 {len(fallback_steps)} 个导航步骤"
        )

        for fb_step in fallback_steps:
            success = await self._execute_fallback_step(fb_step)
            if not success:
                logger.warning(
                    f"降级导航步骤 {fb_step.get('step', '?')} 执行失败，"
                    f"中止降级导航"
                )
                return False

        logger.info(f"降级导航完成: 用例 {case.case_no}")
        return True

    async def _execute_fallback_step(self, step: Dict[str, Any]) -> bool:
        action_type = (step.get("action_type") or "click").lower()
        action_text = step.get("action", "")
        input_value = step.get("input_value", "")
        target_element = step.get("target_element", "")

        try:
            if action_type == "navigate":
                url = input_value or action_text
                if url and url.startswith(("http://", "https://", "/")):
                    if url.startswith("/"):
                        current = self.browser.current_url
                        base = "/".join(current.split("/")[:3])
                        url = base + url
                    await self.browser.navigate(url)
                    return True
                logger.warning(f"降级导航步骤URL无效: {url}")
                return False

            if action_type == "input" and input_value:
                action_info = {
                    "type": "input",
                    "text": action_text,
                    "input_value": input_value,
                    "target_element": target_element,
                }
            elif action_type == "click":
                action_info = {
                    "type": "click",
                    "text": action_text,
                    "target_element": target_element,
                }
            else:
                action_info = {
                    "type": action_type,
                    "text": action_text,
                    "input_value": input_value,
                    "target_element": target_element,
                }

            element_info = await self.smart_locate_with_ai_fallback(action_text)
            if not element_info:
                logger.warning(f"降级步骤元素定位失败: {action_text}")
                return False

            from app.models.element_locator import ElementLocator
            temp_locator = ElementLocator(
                css_selector=element_info.get('css_selector'),
                ai_coordinate=element_info,
            )

            from app.services.test_execution_engine.models import ActionType
            atype_map = {
                "click": ActionType.CLICK,
                "input": ActionType.INPUT,
                "select": ActionType.SELECT,
                "hover": ActionType.HOVER,
            }
            resolved_type = atype_map.get(action_type, ActionType.CLICK)
            await self._execute_action_directly(resolved_type, action_info, temp_locator)
            return True

        except Exception as e:
            logger.warning(f"降级导航步骤执行异常: {e}")
            return False

    async def _execute_mobile_fallback_navigation(
        self, fallback_steps: List[Dict[str, Any]]
    ) -> bool:
        mobile_executor = getattr(self, '_mobile_executor', None)
        if not mobile_executor:
            logger.warning("移动端执行器未初始化，无法执行Mobile降级导航")
            return False

        adb = getattr(mobile_executor, 'adb', None)
        if not adb:
            logger.warning("ADB控制器未初始化，无法执行Mobile降级导航")
            return False

        logger.info(
            f"开始Mobile降级导航: 共 {len(fallback_steps)} 个步骤"
        )

        for fb_step in fallback_steps:
            action_type = (fb_step.get("action_type") or "click").lower()
            action_text = fb_step.get("action", "")
            input_value = fb_step.get("input_value", "")

            try:
                if action_type == "navigate":
                    url = input_value or action_text
                    if url:
                        try:
                            await mobile_executor.execute_action(
                                description=f"启动应用 {url}",
                                step_id=None,
                                use_cache=False,
                            )
                        except Exception:
                            pass
                        continue

                await mobile_executor.execute_action(
                    description=action_text,
                    step_id=None,
                    use_cache=True,
                )

            except Exception as e:
                logger.warning(
                    f"Mobile降级步骤 {fb_step.get('step', '?')} 执行失败: {e}"
                )
                return False

        logger.info("Mobile降级导航完成")
        return True

    async def _try_direct_url_navigation(
        self, case: TestCase
    ) -> bool:
        is_mobile = getattr(self, '_mobile_device_id', None) is not None

        if is_mobile:
            return await self._try_mobile_activity_navigation(case)

        if not self.browser or not getattr(self.browser, '_page', None):
            return False

        precondition = getattr(case, 'precondition', '') or ''
        url = self._extract_url_from_text(precondition)
        if not url and case.steps_json:
            steps = case.steps_json if isinstance(case.steps_json, list) else []
            for step in steps:
                step_url = self._extract_url_from_text(
                    step.get('action', '') + ' ' + (step.get('input_value') or '')
                )
                if step_url:
                    url = step_url
                    break

        if not url:
            logger.info(f"用例 {case.case_no} 无法提取直接URL，三级降级失败")
            return False

        try:
            if url.startswith("/"):
                current = self.browser.current_url
                base = "/".join(current.split("/")[:3])
                url = base + url
            await self.browser.navigate(url)
            logger.info(f"直接URL导航成功: {url}")
            return True
        except Exception as e:
            logger.warning(f"直接URL导航失败: {e}")
            return False

    async def _try_mobile_activity_navigation(
        self, case: TestCase
    ) -> bool:
        mobile_executor = getattr(self, '_mobile_executor', None)
        if not mobile_executor:
            return False

        adb = getattr(mobile_executor, 'adb', None)
        if not adb:
            return False

        project = getattr(self, '_current_project', None)
        if not project:
            return False

        app_package = getattr(project, 'test_object_app_package', None)
        app_activity = getattr(project, 'test_object_app_activity', None)

        if not app_package:
            return False

        try:
            if app_activity:
                await adb.start_app(app_package, app_activity)
            else:
                await adb.start_app(app_package, f".{app_package.split('.')[-1]}Activity")

            import asyncio
            await asyncio.sleep(1.5)
            logger.info(f"Mobile Activity导航成功: {app_package}")
            return True
        except Exception as e:
            logger.warning(f"Mobile Activity导航失败: {e}")
            return False

    def _extract_url_from_text(self, text: str) -> Optional[str]:
        match = re.search(r'(https?://[^\s\'"<>]+)', text)
        if match:
            return match.group(1)
        match = re.search(r'(/[a-zA-Z0-9_\-/]+)', text)
        if match:
            return match.group(1)
        return None
