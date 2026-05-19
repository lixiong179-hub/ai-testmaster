from typing import Any, Dict, List, Optional
from loguru import logger

from app.utils.ai_client_core import AIClientBase, AIServiceError


class _ExtractMixin:

    async def extract_test_points_from_content(
        self,
        content: str,
        project_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not content or not content.strip():
            logger.warning("提取测试点：内容为空")
            return []

        prompt = self._build_extract_prompt(content, context)

        try:
            response = await self.ai_client.complete(
                prompt=prompt,
                system="你是一名资深测试工程师，擅长从需求文档中提取结构化测试点。",
                temperature=0.3,
                max_tokens=4096,
            )
            return self._parse_test_points_response(response.content)
        except AIServiceError as e:
            logger.error(f"AI提取测试点失败: {e}")
            return []
        except Exception as e:
            logger.error(f"提取测试点异常: {e}")
            return []

    async def extract_test_points_from_ui_specs(
        self,
        ui_specs: List[Dict[str, Any]],
        project_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if not ui_specs:
            return []

        content = self._build_ui_extract_content(ui_specs)
        prompt = self._build_ui_extract_prompt(content)

        try:
            response = await self.ai_client.complete(
                prompt=prompt,
                system="你是一名资深测试工程师，擅长从UI设计稿中提取测试点。",
                temperature=0.3,
                max_tokens=4096,
            )
            return self._parse_test_points_response(response.content)
        except AIServiceError as e:
            logger.error(f"AI从UI提取测试点失败: {e}")
            return []
        except Exception as e:
            logger.error(f"从UI提取测试点异常: {e}")
            return []

    def _build_extract_prompt(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        prompt = f"""请从以下需求内容中提取结构化测试点：

需求内容：
{content}

提取规则：
1. 按模块分组，每个模块下的测试点要逻辑清晰、不重复
2. 每个测试点必须包含：module（模块名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）
3. 禁止重复：同一模块下不允许出现测试价值重复的测试点
4. 必须有验证目标：测试点必须说明要验证什么结果
5. 覆盖异常和边界：必须覆盖无网络、无数据、权限异常、重复提交、边界值等场景
6. 优先级合理：核心流程设为1（高）；一般验证设为2（中）；边缘场景设为3（低）

请严格以JSON格式输出：
[
  {{
    "module": "模块名称",
    "function": "功能名称",
    "point": "测试点描述",
    "priority": 1
  }}
]"""
        if context:
            extra = context.get("extra_instructions", "")
            if extra:
                prompt += f"\n\n额外要求：\n{extra}"
        return prompt

    def _build_ui_extract_content(self, ui_specs: List[Dict[str, Any]]) -> str:
        parts = []
        for spec in ui_specs:
            screen_name = spec.get("screen_name", "未知屏幕")
            elements = spec.get("ui_spec", {}).get("elements", [])
            parts.append(f"## {screen_name}")
            for elem in elements:
                text = elem.get("text", "")
                elem_type = elem.get("type", "")
                if text:
                    parts.append(f"- [{elem_type}] {text}")
        return "\n".join(parts)

    def _build_ui_extract_prompt(self, content: str) -> str:
        return f"""请从以下UI设计稿信息中提取结构化测试点：

UI设计信息：
{content}

提取规则：
1. 按屏幕/页面分组
2. 每个测试点必须包含：module（屏幕名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）
3. 覆盖所有可交互元素（按钮、输入框、选择器等）
4. 覆盖显示验证（文本、图标、布局等）
5. 覆盖异常场景（空状态、加载失败、权限等）

请严格以JSON格式输出：
[
  {{
    "module": "屏幕名称",
    "function": "功能名称",
    "point": "测试点描述",
    "priority": 1
  }}
]"""

    def _parse_test_points_response(self, content: str) -> List[Dict[str, Any]]:
        import json
        import re

        if not content:
            return []

        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                for key in ("test_points", "points", "data", "items"):
                    if key in result and isinstance(result[key], list):
                        return result[key]
        except json.JSONDecodeError:
            pass

        json_match = re.search(r'\[[\s\S]*?\]', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析AI返回的测试点，内容长度: {len(content)}")
        return []
