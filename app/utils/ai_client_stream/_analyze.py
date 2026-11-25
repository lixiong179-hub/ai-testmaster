import asyncio
import json
import re
from collections.abc import Iterator
from typing import Any
from loguru import logger

import httpx

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    _detect_ai_error,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    extract_json_objects_fallback,
)
from app.utils.ai_client_stream._sse import error_chunk, iter_sse_deltas
from app.core.constants import TimeoutConfig

_ANALYSIS_PROMPT_TEMPLATE = (
    "你是一名资深测试工程师，请根据以下需求内容分析并提取结构化测试点：\n\n"
    "需求内容：\n{REQ_CONTENT_PLACEHOLDER}\n\n"
    "## 测试点提取规则\n"
    "1. 按模块分组，每个模块下的测试点要逻辑清晰、不重复\n"
    "2. 每个测试点必须包含：module（模块名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）\n"
    "3. **禁止重复**：同一模块下不允许出现测试价值重复的测试点\n"
    "4. **必须有验证目标**：测试点必须说明要验证什么结果\n"
    "5. **覆盖异常和边界**：必须覆盖无网络、无数据、权限异常、重复提交、边界值等场景\n"
    "6. **优先级合理**：核心流程设为1（高）；一般验证设为2（中）；边缘场景设为3（低）\n\n"
    "请严格以JSON格式输出：\n[\n  {\n"
    '    "module": "模块名称",\n'
    '    "function": "功能名称",\n'
    '    "point": "测试点描述",\n'
    '    "priority": 1\n  }\n]\n'
)

_FENCED_ARRAY_PATTERN = re.compile(r"```(?:json)?\s*\n?(\[[\s\S]*?\])\s*\n?```")
_BRACKET_ARRAY_PATTERN = re.compile(r"(\[\s*\{[\s\S]*\}\s*\])")


def _load_json_array(text: str) -> list[Any] | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    logger.info("AI分析需求（流式响应）成功")
    return data


def _parse_array_with_repair(raw: str) -> tuple[Any, bool]:
    """返回 (解析结果, 是否经过修复)；两次都失败时结果为 None。"""
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        pass
    fixed_json = fix_common_json_issues(raw)
    if not fixed_json:
        return None, True
    try:
        return json.loads(fixed_json), True
    except json.JSONDecodeError:
        return None, True


def _resolve_array_match(match: re.Match | None, source_note: str) -> Any:
    if match is None:
        return None
    data, repaired = _parse_array_with_repair(match.group(1))
    if data is None:
        return None
    suffix = " - JSON已修复" if repaired else ""
    if not repaired and source_note:
        suffix = f" - {source_note}"
    logger.info(f"AI分析需求（流式响应）成功{suffix}")
    return data


def _extract_fenced_json(text: str) -> Any:
    return _resolve_array_match(_FENCED_ARRAY_PATTERN.search(text), "从markdown代码块提取")


def _extract_bracket_json(text: str) -> Any:
    return _resolve_array_match(_BRACKET_ARRAY_PATTERN.search(text), "")


def _iter_json_candidates(text: str) -> Iterator[Any]:
    """按「原文 → 代码块 → 裸数组」顺序惰性产出候选结果。"""
    yield _load_json_array(text)
    yield _extract_fenced_json(text)
    yield _extract_bracket_json(text)


class _AnalyzeStreamMixin:
    DEBUG_DUMP_FILE = "ai_response_debug.txt"

    async def analyze_requirements_stream(self, content: str):
        logger.info(f"开始AI分析需求（流式），输入内容长度: {len(content)} 字符")
        headers, data = self._build_analysis_request(content)
        for attempt in range(self.max_retries):
            try:
                async for chunk in self._stream_analysis_once(headers, data, attempt):
                    yield chunk
                return
            except httpx.HTTPError as e:
                logger.error(f"AI分析需求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                error = _detect_ai_error(e)
                logger.error(error.message)
                yield error_chunk(error.message)
                return
            except AIServiceError as e:
                yield error_chunk(e.message)
                return
            except Exception as e:
                error_message = f"分析失败: {str(e)}"
                logger.error(error_message)
                yield error_chunk(error_message)
                return

    def _build_analysis_request(self, content: str) -> tuple[dict[str, str], dict[str, Any]]:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        prompt = _ANALYSIS_PROMPT_TEMPLATE.replace("{REQ_CONTENT_PLACEHOLDER}", content)
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
            "stream": True,
        }
        return headers, data

    async def _stream_analysis_once(self, headers: dict[str, str], data: dict[str, Any], attempt: int):
        """单次流式尝试：边接收边报进度，结束后解析测试点；解析失败抛 AIResponseParseError。"""
        logger.info(f"AI分析需求（流式响应） - 尝试 {attempt + 1}/{self.max_retries}")
        full_content = ""
        async with (
            httpx.AsyncClient(timeout=TimeoutConfig.AI_API) as client,
            client.stream("POST", self.api_url, headers=headers, json=data) as response,
        ):
            response.raise_for_status()
            async for delta_text in iter_sse_deltas(response):
                full_content += delta_text
                progress = min(int(len(full_content) / 20), 95)
                yield {"progress": progress, "message": "分析中..."}

        logger.info(f"AI流式响应接收完成，内容长度: {len(full_content)} 字符")
        test_points = self._parse_stream_test_points(full_content)
        if test_points is None:
            raise AIResponseParseError()
        yield {"progress": 100, "message": "分析完成", "data": test_points}

    def _parse_stream_test_points(self, full_content: str) -> list[dict[str, Any]] | None:
        for candidate in _iter_json_candidates(full_content):
            if candidate is not None:
                return candidate
        self._dump_stream_debug(full_content)
        return extract_json_objects_fallback(full_content) or None

    def _dump_stream_debug(self, full_content: str) -> None:
        logger.warning(f"AI返回的内容无法解析为JSON。内容长度: {len(full_content)}")
        logger.warning(f"内容前500字符: {full_content[:500]}")
        try:
            with open(self.DEBUG_DUMP_FILE, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info(f"完整AI响应已保存到: {self.DEBUG_DUMP_FILE}")
        except Exception as e:
            logger.warning(f"无法保存调试文件: {e}")
