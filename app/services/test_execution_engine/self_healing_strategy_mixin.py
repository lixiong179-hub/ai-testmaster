"""自愈策略Mixin - 实现多种自愈定位策略。

策略优先级:
    1. 本地AI自愈（MCP识别器 + 视觉模型）
    2. Stagehand云服务自愈（远程浏览器执行）

每个策略独立实现，由 _ai_self_heal_action 统一调度。
自愈成功后通过 _update_locator_after_healing 回写新定位器。
"""
from typing import Optional, Dict, Any
from loguru import logger

from app.services.test_execution_engine.models import ActionType, StepExecutionError


class SelfHealingStrategyMixin:

    async def _ai_self_heal_action(
        self,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """AI自愈核心：使用AI理解自然语言描述并执行操作。

        优先使用本地AI（MCP + 视觉模型），可选使用Stagehand云服务。
        """
        from app.core.config import settings
        max_retries = settings.AI_SELF_HEALING_MAX_RETRIES

        for attempt in range(max_retries):
            try:
                new_selector = await self._local_ai_self_heal(
                    nl_description, action_type, action_info, step_test_data
                )
                if new_selector:
                    return new_selector
            except Exception as e:
                logger.warning(f"本地AI自愈尝试 {attempt + 1}/{max_retries} 失败: {e}")

        stagehand = await self._get_stagehand()
        if stagehand:
            try:
                new_selector = await self._stagehand_self_heal(
                    stagehand, nl_description, action_type, action_info
                )
                if new_selector:
                    return new_selector
            except Exception as e:
                logger.warning(f"Stagehand自愈失败: {e}")

        raise StepExecutionError(f"AI自愈失败，所有策略均无法解析步骤: {nl_description}")

    async def _local_ai_self_heal(
        self,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """本地AI自愈：MCP识别器 + 视觉模型兜底。"""
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        if not hasattr(self, '_mcp_recognizer') or self._mcp_recognizer is None:
            from app.services.recognizers.mcp_recognizer import MCPRecognizer
            self._mcp_recognizer = MCPRecognizer()

        try:
            action_type_str = action_type.value if isinstance(action_type, ActionType) else str(action_type)
            recognition_result = await self._mcp_recognizer.recognize(
                self.browser, nl_description, action_type_str
            )

            if recognition_result and recognition_result.is_valid:
                logger.info(f"MCP自愈成功，定位类型={recognition_result.locator_type}")
                new_selector = self._resolve_locator_value(recognition_result)

                if action_type == ActionType.INPUT:
                    input_text = self._resolve_input_text(action_info, step_test_data)
                    await self._mcp_recognizer.execute_action(recognition_result, input_text)
                    logger.info(f"MCP自愈输入成功: {nl_description} -> {input_text}")
                else:
                    await self._mcp_recognizer.execute_action(recognition_result)
                    logger.info(f"MCP自愈执行成功: {nl_description}")
                return new_selector
        except Exception as e:
            logger.warning(f"MCP自愈异常，降级到视觉模型: {e}")

        return await self._vision_model_self_heal(nl_description, action_type, action_info, step_test_data)

    async def _vision_model_self_heal(
        self,
        nl_description: str,
        action_type: ActionType,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """视觉模型自愈：截图识别 + 坐标执行。"""
        import asyncio
        logger.warning("MCP自愈失败，降级到视觉模型")
        if not self.vision_model:
            raise StepExecutionError("视觉模型未初始化，本地AI自愈不可用")

        screenshot = await self.browser.take_screenshot()
        element_info = await self.recognize_element_with_ai(screenshot, nl_description)
        if not element_info:
            raise StepExecutionError(f"AI视觉识别未找到目标元素: {nl_description}")

        x, y, width, height = (
            element_info.get("x", 0), element_info.get("y", 0),
            element_info.get("width", 0), element_info.get("height", 0)
        )
        if x < 0 or y < 0:
            raise StepExecutionError(
                f"AI视觉识别返回无效坐标: ({x}, {y})，元素描述: {nl_description}"
            )
        if width < 0:
            width = 0
        if height < 0:
            height = 0

        new_selector = None
        element_attrs = await self._get_element_attributes_from_coords(x, y, width, height)
        if element_attrs:
            new_selector = self._build_healed_selector(element_attrs)

        center_x, center_y = x + width // 2, y + height // 2

        if action_type == ActionType.INPUT:
            input_text = self._resolve_input_text(action_info, step_test_data)
            await self.browser.click(center_x, center_y)
            await asyncio.sleep(0.3)
            await self.browser.execute_javascript("""
                (function() {
                    var el = document.activeElement;
                    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
                        var desc = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        );
                        desc.set.call(el, arguments[0]);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                })()
            """, input_text)
            logger.info(f"本地AI自愈输入成功(坐标方式): ({center_x}, {center_y}) -> {input_text}")
        else:
            await self.browser.click(center_x, center_y)
            logger.info(f"本地AI自愈点击成功(坐标方式): ({center_x}, {center_y})")

        return new_selector

    def _resolve_locator_value(self, recognition_result) -> Optional[str]:
        """从识别结果中解析定位器值。"""
        loc_type = recognition_result.locator_type
        loc_value = recognition_result.locator_value
        if loc_type == "css":
            return loc_value
        elif loc_type == "xpath":
            return f"xpath={loc_value}"
        elif loc_type == "id":
            return f"#{loc_value}"
        elif loc_type == "name":
            return f"[name='{loc_value}']"
        elif loc_type in ("role", "text", "ref"):
            return loc_value
        return None

    def _resolve_input_text(
        self,
        action_info: Dict[str, Any],
        step_test_data: Optional[Dict[str, str]] = None
    ) -> str:
        """从操作信息和测试数据中解析输入文本。"""
        input_text = action_info.get("input_value", "") or self._extract_input_text(action_info.get("text", ""))
        if step_test_data:
            for field_name, value in step_test_data.items():
                if field_name in (action_info.get("text") or "").lower():
                    input_text = value
                    break
        return input_text
