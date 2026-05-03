"""AI响应解析Mixin - AI返回内容的JSON提取与解析。

本模块提供AI响应内容的解析逻辑，复用 app.utils.ai_client_parser 的
fix_common_json_issues 和 clean_json_string 工具方法，
避免重复实现 JSON 修复策略。

核心类:
    - AIParseMixin: AI响应解析Mixin

设计模式:
    作为Mixin模块，通过多继承组合到AIMixin中，提供:
    - _parse_ai_response: AI响应解析
"""
import json
import re
from typing import Dict, Any


class AIParseMixin:
    """AI响应解析Mixin - 解析AI返回的JSON格式用例数据。

    职责:
        - 解析AI响应内容为结构化JSON数据
        - 复用 ai_client_parser 的 JSON 修复工具链

    解析策略（按优先级）:
        1. 直接JSON解析
        2. fix_common_json_issues 修复注释和尾逗号
        3. clean_json_string 多策略修复
        4. 正则提取JSON对象
        5. 解析失败抛出ValueError
    """

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """解析AI响应内容为JSON格式用例数据。

        Args:
            content: AI返回的原始文本内容。

        Returns:
            解析后的用例数据字典。

        Raises:
            ValueError: 无法解析AI响应内容。
        """
        from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        fixed = fix_common_json_issues(content)
        if fixed:
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

        cleaned = clean_json_string(content)
        if cleaned:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            matched = json_match.group(0)
            fixed_match = fix_common_json_issues(matched)
            if fixed_match:
                try:
                    return json.loads(fixed_match)
                except json.JSONDecodeError:
                    pass
            cleaned_match = clean_json_string(matched)
            if cleaned_match:
                try:
                    return json.loads(cleaned_match)
                except json.JSONDecodeError:
                    pass

        raise ValueError("无法解析AI响应内容")
