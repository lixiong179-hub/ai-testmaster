"""测试用例AI生成 - 响应解析工具
"""
import json
import re
from typing import Dict, Any


def parse_ai_response(content: str) -> Dict[str, Any]:
    """解析AI响应内容"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
    raise ValueError("无法解析AI响应内容")
