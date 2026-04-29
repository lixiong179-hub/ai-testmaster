"""自愈策略Mixin - 实现多种自愈定位策略。
"""
import re
import json
from typing import Optional, Dict, Any
from loguru import logger

from app.models.element_locator import ElementLocator
from app.services.test_execution_engine.models import ActionType


class SelfHealingStrategyMixin:

    async def _ai_self_heal_action(self, step, action_info: Dict[str, Any]) -> bool:
        if not self.vision_model or not self.browser:
            return False
        try:
            screenshot = await self.browser.take_screenshot()
            action_text = action_info.get("text", step.action)
            prompt = f"""页面操作失败，需要重新定位元素。

操作描述: {action_text}
请重新识别目标元素的位置。

返回JSON格式:
{{
    "x": 元素x坐标,
    "y": 元素y坐标,
    "width": 元素宽度,
    "height": 元素高度,
    "confidence": 置信度
}}"""
            response = self.vision_model.analyze_image(screenshot, prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                element_info = json.loads(json_match.group())
                confidence = element_info.get("confidence", 0)
                if confidence < 0.8:
                    return False
                x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                action_type = action_info.get("type", ActionType.CLICK)
                if action_type == ActionType.CLICK:
                    await self.browser.click(x, y)
                elif action_type == ActionType.INPUT:
                    await self.browser.click(x, y)
                    import asyncio
                    await asyncio.sleep(0.3)
                    input_value = action_info.get("input_value", "test")
                    await self.browser.execute_javascript("""
                        (function() {
                            var el = document.activeElement;
                            if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, arguments[0]);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        })()
                    """, input_value)
                elif action_type == ActionType.HOVER:
                    await self.browser.execute_javascript(f"""
                        var el = document.elementFromPoint({x}, {y});
                        if (el) {{ el.dispatchEvent(new MouseEvent('mouseover', {{bubbles: true}})); }}
                    """)

                await self._update_locator_after_healing(step, element_info)
                return True
            return False
        except Exception as e:
            logger.warning(f"AI自愈失败: {e}")
            return False

    async def _local_ai_self_heal(self, step, action_info: Dict[str, Any]) -> bool:
        try:
            element_info = await self.smart_locate_with_ai_fallback(
                action_info.get("text", step.action)
            )
            if element_info:
                action_type = action_info.get("type", ActionType.CLICK)
                if action_type == ActionType.CLICK:
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    await self.browser.click(x, y)
                elif action_type == ActionType.INPUT:
                    x = element_info.get("x", 0) + element_info.get("width", 0) // 2
                    y = element_info.get("y", 0) + element_info.get("height", 0) // 2
                    await self.browser.click(x, y)
                    import asyncio
                    await asyncio.sleep(0.3)
                    input_value = action_info.get("input_value", "test")
                    await self.browser.execute_javascript("""
                        (function() {
                            var el = document.activeElement;
                            if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                                var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                                setter.call(el, arguments[0]);
                                el.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        })()
                    """, input_value)

                await self._update_locator_after_healing(step, element_info)
                return True
            return False
        except Exception as e:
            logger.warning(f"本地AI自愈失败: {e}")
            return False

    async def _stagehand_self_heal(self, step, action_info: Dict[str, Any]) -> bool:
        stagehand = self._get_stagehand()
        if not stagehand:
            return False
        try:
            action_text = action_info.get("text", step.action)
            nl_description = self._get_nl_description(action_text)
            action_type = action_info.get("type", ActionType.CLICK)

            if action_type == ActionType.CLICK:
                result = await stagehand.click(nl_description)
            elif action_type == ActionType.INPUT:
                input_value = action_info.get("input_value", "test")
                result = await stagehand.fill(nl_description, input_value)
            elif action_type == ActionType.HOVER:
                result = await stagehand.hover(nl_description)
            else:
                result = await stagehand.click(nl_description)

            if result:
                logger.info(f"Stagehand自愈成功: {nl_description}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Stagehand自愈失败: {e}")
            return False

    def _get_stagehand(self) -> Any:
        if self._stagehand_instance is None:
            try:
                from app.services.stagehand_service import StagehandService
                self._stagehand_instance = StagehandService()
            except Exception as e:
                logger.warning(f"Stagehand服务初始化失败: {e}")
        return self._stagehand_instance

    @staticmethod
    def _get_nl_description(action_text: str) -> str:
        text = re.sub(r'[点击输入填写选择悬停验证等待滚动刷新按下]', '', action_text)
        text = re.sub(r'(按钮|链接|输入框|下拉框|复选框|元素|菜单|选项|标签|图标)', '', text)
        text = text.strip()
        if not text:
            text = action_text
        return text

    @staticmethod
    def _sanitize_css_identifier(value: str) -> str:
        if not value:
            return ""
        value = re.sub(r'^[0-9]', r'_\0', value)
        value = re.sub(r'[^a-zA-Z0-9_-]', '_', value)
        return value

    @staticmethod
    def _build_healed_selector(element_attrs: Dict[str, Any]) -> Optional[str]:
        if not element_attrs:
            return None
        element_id = element_attrs.get("id")
        if element_id:
            return f"#{SelfHealingStrategyMixin._sanitize_css_identifier(element_id)}"
        data_testid = element_attrs.get("data-testid")
        if data_testid:
            return f"[data-testid='{SelfHealingStrategyMixin._sanitize_css_identifier(data_testid)}']"
        name = element_attrs.get("name")
        if name:
            return f"[name='{SelfHealingStrategyMixin._sanitize_css_identifier(name)}']"
        tag = element_attrs.get("tag", "")
        element_class = element_attrs.get("class")
        if element_class and tag:
            classes = element_class.split()[:2]
            safe_classes = [SelfHealingStrategyMixin._sanitize_css_identifier(c) for c in classes]
            return f"{tag}.{'.'.join(safe_classes)}"
        return None

    async def _update_locator_after_healing(self, step, element_info: Dict[str, Any]) -> None:
        try:
            step_id = getattr(step, 'id', None)
            if not step_id:
                return
            locator = self.db.query(ElementLocator).filter(
                ElementLocator.step_id == step_id
            ).first()
            if locator:
                if element_info.get("css_selector"):
                    locator.css_selector = element_info["css_selector"]
                coordinate = {
                    "x": element_info.get("x", 0),
                    "y": element_info.get("y", 0),
                    "width": element_info.get("width", 0),
                    "height": element_info.get("height", 0)
                }
                locator.ai_coordinate = coordinate
                locator.ai_confidence = element_info.get("confidence", 0)
                locator.source = "ai_self_healing"
                self.db.commit()
                logger.info(f"步骤 {step.step_number}: 自愈定位信息已更新")
        except Exception as e:
            logger.warning(f"更新自愈定位信息失败: {e}")

    def get_self_healing_summary(self) -> Dict[str, Any]:
        return self._self_healing_stats.copy()
