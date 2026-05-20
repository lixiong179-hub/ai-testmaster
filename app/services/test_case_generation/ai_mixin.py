"""Test Case Generation Service - AI生成相关Mixin
包含AI调用、Prompt构建、响应解析等能力
"""
import json
from typing import List, Dict, Any, Optional
from loguru import logger

from app.core.config import settings
from app.services.test_case_generation.base_mixin import (
    ContentSanitizer, TEST_CATEGORY_MANUAL, TEST_CATEGORY_UI_AUTO
)
from app.services.prompt_builder import PromptBuilder
from app.services.test_case_generation.ai_response_parser import parse_ai_response


class TestCaseGenerationAiMixin:
    """测试用例生成服务 - AI生成相关Mixin"""

    async def generate_test_case_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        case_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """为单个测试点生成测试用例"""
        ui_description = self._build_ui_description(context.get("ui_descriptions", []))
        requirement_content = ContentSanitizer.sanitize(context.get("requirement_content", ""))
        ui_description = ContentSanitizer.sanitize(ui_description)

        has_ui = bool(ui_description and ui_description.strip()) or bool(context.get("ui_specs", []))

        if not has_ui:
            case_category = TEST_CATEGORY_MANUAL
        else:
            ui_keywords = ['按钮', '表单', '输入框', '下拉框', '复选框', '单选框', '链接', '导航',
                          'button', 'input', 'form', 'dropdown', 'checkbox', 'radio', 'link', 'menu']
            ui_has_interactive = any(k in ui_description.lower() for k in ui_keywords)
            case_category = TEST_CATEGORY_UI_AUTO if ui_has_interactive else TEST_CATEGORY_MANUAL

        generation_context = {
            "requirement_content": requirement_content,
            "ui_description": ui_description,
            "ui_specs": context.get("ui_specs", []),
            "test_point": test_point,
            "case_type": case_type if case_type else "ui_automation",
            "case_category": case_type if case_type else case_category
        }

        return await self._generate_case_with_ai(generation_context)

    async def _generate_case_with_ai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用AI生成测试用例"""
        import httpx
        import asyncio

        test_point = context.get("test_point", {})
        prompt = PromptBuilder.build_linear_prompt(
            requirement_content=context.get("requirement_content", ""),
            ui_description=context.get("ui_description", ""),
            module=test_point.get("module", "未知模块"),
            function=test_point.get("function", "未知功能"),
            point=test_point.get("point", ""),
            priority=test_point.get("priority", 2),
            ui_specs=context.get("ui_specs", [])
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"
        }
        payload = {
            "model": settings.DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,  # 统一低温度，输出稳定
            "max_tokens": 3000
        }

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
                    response = await client.post(
                        settings.DEEPSEEK_API_URL,
                        headers=headers,
                        json=payload
                    )
                    response.raise_for_status()
                    result = response.json()

                    if "choices" not in result:
                        raise ValueError("AI API响应格式错误：缺少choices字段")
                    choices = result["choices"]
                    if not choices or len(choices) == 0:
                        raise ValueError("AI API返回结果为空")
                    first_choice = choices[0]
                    if "message" not in first_choice:
                        raise ValueError("AI响应格式错误：缺少message字段")

                    content = first_choice["message"].get("content", "")
                    if not content:
                        raise ValueError("AI响应内容为空")

                    logger.debug(f"AI原始响应长度: {len(content)} 字符")
                    parsed = parse_ai_response(content)

                    if "cases" in parsed and isinstance(parsed["cases"], list):
                        cases_list = parsed["cases"]
                        if not cases_list:
                            raise ValueError("AI返回的用例数组为空")
                        primary_case = cases_list[0]
                        primary_case["_extra_cases"] = cases_list[1:]
                        return primary_case

                    return parsed

            except httpx.TimeoutException:
                last_error = f"AI API请求超时 (尝试 {attempt + 1}/{max_retries})"
                logger.warning(last_error)
            except httpx.HTTPStatusError as e:
                last_error = f"AI API HTTP错误: {e.response.status_code}"
                logger.error(last_error)
            except httpx.RequestError as e:
                last_error = "AI API请求错误"
                logger.error(f"AI API请求错误: {e}")
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"AI响应解析失败: {e}")
                raise

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)

        logger.error(f"AI生成失败，已重试{max_retries}次: {last_error}")
        raise ValueError(f"AI生成失败: {last_error}")

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """构建UI描述文本"""
        parts = []
        for desc in ui_descriptions:
            if desc.get("description"):
                parts.append(desc["description"])
            elif desc.get("summary"):
                parts.append(desc["summary"])
        return "\n".join(parts)
