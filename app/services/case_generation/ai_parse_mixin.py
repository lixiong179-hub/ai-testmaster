"""AI响应解析Mixin - AI返回内容的JSON提取与解析。

本模块提供AI响应内容的解析逻辑，支持直接JSON解析和正则提取回退策略。
作为AIParseMixin被AIMixin组合使用。

核心类:
    - AIParseMixin: AI响应解析Mixin

设计模式:
    作为Mixin模块，通过多继承组合到AIMixin中，提供:
    - _parse_ai_response: AI响应解析

安全设计:
    - 采用宽松匹配策略，兼容AI返回的格式偏差
    - 解析失败抛出ValueError，由上层重试逻辑处理
"""
import json
import re
from typing import Dict, Any


class AIParseMixin:
    """AI响应解析Mixin - 解析AI返回的JSON格式用例数据。

    职责:
        - 解析AI响应内容为结构化JSON数据
        - 支持直接解析和正则提取两种策略

    设计意图:
        将响应解析逻辑从AI调用中抽离，便于:
        1. 独立测试解析逻辑
        2. 适配不同AI模型的输出格式差异
        3. 统一处理解析异常
    """

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """解析AI响应内容为JSON格式用例数据。

        解析策略:
            1. 直接JSON解析（理想情况）
            2. 正则提取JSON对象（AI可能在JSON前后添加说明文字）
            3. 解析失败抛出ValueError

        Args:
            content: AI返回的原始文本内容。

        Returns:
            解析后的用例数据字典。

        Raises:
            ValueError: 无法解析AI响应内容。
        """
        try:
            # 优先尝试直接JSON解析
            return json.loads(content)
        except json.JSONDecodeError:
            # AI可能在JSON前后添加了说明文字，尝试提取JSON部分
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
        raise ValueError("无法解析AI响应内容")
