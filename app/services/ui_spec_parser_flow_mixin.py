"""UI解析流程Mixin - 提供多页面流程解析和批量摘要能力。
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger


class UISpecFlowMixin:
    async def parse_multiple_screen_flows(
        self,
        screens_data: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if len(screens_data) < 2:
            return None
        count = len(screens_data)
        image_descriptions = []
        for i, screen in enumerate(screens_data):
            desc = f"【屏幕{i+1}】{screen.get('screen_name', '未知')}\n"
            if screen.get('purpose'):
                desc += f"目的: {screen.get('purpose')}\n"
            interactive_elements = []
            for elem in screen.get('elements', []):
                if elem.get('interactive') and elem.get('type') in ['button', 'link', 'list_item', 'icon']:
                    label = elem.get('label') or elem.get('semantic', '')
                    if label:
                        interactive_elements.append(label)
            if interactive_elements:
                desc += f"可点击元素: {', '.join(interactive_elements[:10])}\n"
            nav = screen.get('navigation', {})
            if nav.get('back_button', {}).get('visible'):
                desc += "存在返回按钮\n"
            if nav.get('tab_bar', {}).get('visible'):
                desc += f"Tab栏: {', '.join(nav['tab_bar'].get('items', []))}\n"
            flows = screen.get('flows', {})
            if flows.get('expected_next_screens'):
                desc += f"预期跳转: {', '.join(flows['expected_next_screens'])}\n"
            if flows.get('trigger_actions'):
                desc += f"触发动作: {', '.join(flows['trigger_actions'])}\n"
            image_descriptions.append(desc)
        image_descriptions_str = "\n\n".join(image_descriptions)
        prompt = self.MULTI_IMAGE_FLOW_PROMPT.replace('{count}', str(count)).replace('{image_descriptions}', image_descriptions_str)
        for attempt in range(self.max_retries):
            try:
                logger.info(f"生成页面流转，模式: {self.parse_mode}，尝试 {attempt + 1}/{self.max_retries}")
                response = await asyncio.to_thread(self.vision_model.analyze_text, prompt)
                result = self._parse_json_response(response)
                if result:
                    logger.info("页面流转生成成功")
                    return result
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except Exception as e:
                logger.error(f"页面流转生成异常: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
        return None

    async def generate_ui_adaptation_test_points(
        self,
        screens_data: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        if not screens_data:
            return None
        simplified = []
        for screen in screens_data:
            simplified.append({
                "screen_id": screen.get("screen_id", "unknown"),
                "screen_name": screen.get("screen_name", ""),
                "layout_constraints": screen.get("layout_constraints", [])
            })
        prompt = self.BATCH_SUMMARY_PROMPT.replace('{ui_specs}', json.dumps(simplified, ensure_ascii=False, indent=2))
        for attempt in range(self.max_retries):
            try:
                logger.info(f"生成UI适配测试点，尝试 {attempt + 1}/{self.max_retries}")
                response = await asyncio.to_thread(self.vision_model.analyze_text, prompt)
                result = self._parse_json_response(response)
                if result and isinstance(result, list):
                    logger.info("UI适配测试点生成成功")
                    return result
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except Exception as e:
                logger.error(f"UI适配测试点生成异常: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
        return None
