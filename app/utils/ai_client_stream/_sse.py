"""流式响应（SSE）通用解析：增量文本提取与错误分片构造。"""

import json
from collections.abc import AsyncIterator
from typing import Any


async def iter_sse_deltas(response: Any) -> AsyncIterator[str]:
    """逐行解析 SSE，产出 delta.content；忽略非 data 行与非法 JSON。"""
    async for line in response.aiter_lines():
        if not line.startswith("data: "):
            continue
        data_part = line[6:]
        if data_part == "[DONE]":
            break
        try:
            chunk_data = json.loads(data_part)
        except json.JSONDecodeError:
            continue
        if "choices" not in chunk_data:
            continue
        delta = chunk_data["choices"][0].get("delta", {})
        if "content" in delta:
            yield delta["content"]


def error_chunk(message: str) -> dict[str, Any]:
    """构造流式响应的终止错误分片。"""
    return {"progress": 100, "message": message, "status": "error", "error": True}
