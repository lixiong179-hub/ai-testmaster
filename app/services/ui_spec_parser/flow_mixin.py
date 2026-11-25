"""
UI Spec Parser - 流程与适配测试点Mixin
提供多屏页面流转生成、UI适配测试检查点生成能力
"""

import json
import asyncio
from typing import Any
from loguru import logger


_INTERACTIVE_ELEMENT_TYPES = frozenset({"button", "link", "list_item", "icon"})
_MAX_INTERACTIVE_LABELS = 10


def _collect_interactive_labels(elements: list[dict[str, Any]]) -> list[str]:
    """只保留可点击元素的标签（label 优先，回退 semantic），最多 10 个。"""
    labels = []
    for elem in elements:
        if not elem.get("interactive") or elem.get("type") not in _INTERACTIVE_ELEMENT_TYPES:
            continue
        label = elem.get("label") or elem.get("semantic", "")
        if label:
            labels.append(label)
    return labels[:_MAX_INTERACTIVE_LABELS]


def _build_navigation_text(navigation: dict[str, Any]) -> str:
    text = ""
    if (navigation.get("back_button") or {}).get("visible"):
        text += "存在返回按钮\n"
    tab_bar = navigation.get("tab_bar") or {}
    if tab_bar.get("visible"):
        text += f"Tab栏: {', '.join(tab_bar.get('items', []))}\n"
    return text


def _build_flows_text(flows: dict[str, Any]) -> str:
    text = ""
    if flows.get("expected_next_screens"):
        text += f"预期跳转: {', '.join(flows.get('expected_next_screens', []))}\n"
    if flows.get("trigger_actions"):
        text += f"触发动作: {', '.join(flows.get('trigger_actions', []))}\n"
    return text


def _build_screen_description(index: int, screen: dict[str, Any]) -> str:
    """把单屏信息压缩为一段可粘贴进提示词的描述。"""
    desc = f"【屏幕{index}】{screen.get('screen_name', '未知')}\n"
    if screen.get("purpose"):
        desc += f"目的: {screen.get('purpose')}\n"
    labels = _collect_interactive_labels(screen.get("elements", []))
    if labels:
        desc += f"可点击元素: {', '.join(labels)}\n"
    desc += _build_navigation_text(screen.get("navigation") or {})
    desc += _build_flows_text(screen.get("flows") or {})
    return desc


class UISpecFlowMixin:
    """流程与适配测试点方法Mixin"""

    async def parse_multiple_screen_flows(self, screens_data: list[dict[str, Any]]) -> dict[str, Any] | None:
        """
        多图合并生成页面流转（增强版：传入可点击元素）

        Args:
            screens_data: 屏幕数据列表，每项需包含 screen_id, screen_name, summary, elements 等

        Returns:
            页面流转图JSON
        """
        if len(screens_data) < 2:
            return None

        from app.services.prompt_builder import MULTI_IMAGE_FLOW_PROMPT

        image_descriptions = [_build_screen_description(i + 1, screen) for i, screen in enumerate(screens_data)]
        # 模板为模块级常量，f-string 无法延迟求值，按项目规则例外使用 .format()
        prompt = MULTI_IMAGE_FLOW_PROMPT.format(
            count=len(screens_data), image_descriptions="\n\n".join(image_descriptions)
        )

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
        self, screens_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]] | None:
        """
        为已解析的UI屏幕生成UI适配测试检查点（基于layout_constraints）

        Args:
            screens_data: 已解析的ui_spec列表，每项需包含 screen_id

        Returns:
            补充了测试检查点的屏幕数据列表
        """
        if not screens_data:
            return None

        simplified = []
        for screen in screens_data:
            simplified.append(
                {
                    "screen_id": screen.get("screen_id", "unknown"),
                    "screen_name": screen.get("screen_name", ""),
                    "layout_constraints": screen.get("layout_constraints", []),
                }
            )

        from app.services.prompt_builder import BATCH_SUMMARY_PROMPT

        # 模板为模块级常量，f-string 无法延迟求值，按项目规则例外使用 .format()
        prompt = BATCH_SUMMARY_PROMPT.format(ui_specs=json.dumps(simplified, ensure_ascii=False, indent=2))

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
