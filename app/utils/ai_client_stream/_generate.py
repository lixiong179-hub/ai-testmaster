import asyncio
import json
from typing import Any
from loguru import logger

import httpx

from app.utils.ai_client_core import (
    AIServiceError,
    _detect_ai_error,
)
from app.utils.ai_client_parser import parse_ai_json_response
from app.utils.ai_client_stream._sse import error_chunk, iter_sse_deltas

_REQUIRED_CASE_FIELDS = ("title", "precondition", "steps", "expected_result", "case_type")


def _load_generated_case(content: str) -> Any:
    """先严格解析，失败再走宽松解析（可能返回 None 或非 dict）。"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return parse_ai_json_response(content)


def _build_generation_result(content: str) -> list[dict[str, Any]]:
    """把累积文本收敛为「一条终态分片」。"""
    generated_case = _load_generated_case(content)
    if not isinstance(generated_case, dict):
        return [error_chunk("AI响应格式错误，无法解析")]

    missing_fields = [field for field in _REQUIRED_CASE_FIELDS if field not in generated_case]
    if missing_fields:
        return [error_chunk(f"AI响应缺少必要字段: {', '.join(missing_fields)}")]
    return [{"progress": 100, "message": "生成完成", "data": generated_case}]


class _GenerateStreamMixin:
    async def generate_test_case_stream(self, test_point: dict[str, Any]):
        headers, data = self._build_generation_request(test_point)
        for attempt in range(self.max_retries):
            try:
                async for chunk in self._stream_generation_once(headers, data, attempt):
                    yield chunk
                return
            except httpx.HTTPError as e:
                logger.error(f"AI生成测试用例失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                yield error_chunk(_detect_ai_error(e).message)
                return
            except AIServiceError as e:
                yield error_chunk(e.message)
                return
            except Exception as e:
                error_message = f"生成失败: {str(e)}"
                logger.error(error_message)
                yield error_chunk(error_message)
                return

    def _build_generation_request(self, test_point: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        prompt = f"""你是一名专业的测试工程师，请根据以下测试点生成可执行的测试用例：

模块：{test_point.get("module", "未知模块")}
功能：{test_point.get("function", "")}
测试点：{test_point.get("point", "")}
优先级：{test_point.get("priority", 2)}（1高/2中/3低）

请按照以下格式生成测试用例：
1. 用例标题（必须具体明确，格式：场景/条件+操作+验证重点）
2. 前置条件
3. 可执行步骤
4. 预期结果
5. 用例类型

请以JSON格式输出，结构如下：
{{
  "title": "场景+操作+验证重点",
  "precondition": "前置条件",
  "steps": [
    {{
      "step": 1,
      "action": "业务操作描述",
      "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
      "input_value": "输入值",
      "target_element": "目标元素描述",
      "expected_result": "该步骤的预期验证条件"
    }}
  ],
  "expected_results": ["步骤1的预期验证条件"],
  "case_type": "UI/API/功能",
  "test_category": "ui_automation/manual/api_automation"
}}

重要要求：只输出JSON，格式正确，步骤详细可执行，action_type使用枚举值
"""
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1500,
            "stream": True,
        }
        return headers, data

    async def _stream_generation_once(self, headers: dict[str, str], data: dict[str, Any], attempt: int):
        """单次流式尝试：边接收边报进度，结束后产出终态分片（每次尝试内容独立）。"""
        logger.debug(f"AI生成测试用例（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
        full_content = ""
        async with (
            httpx.AsyncClient(timeout=60) as client,
            client.stream("POST", self.api_url, headers=headers, json=data) as response,
        ):
            response.raise_for_status()
            async for delta_text in iter_sse_deltas(response):
                full_content += delta_text
                progress = min(int(len(full_content) / 15), 95)
                yield {"progress": progress, "message": "生成中..."}
        for chunk in _build_generation_result(full_content):
            yield chunk
