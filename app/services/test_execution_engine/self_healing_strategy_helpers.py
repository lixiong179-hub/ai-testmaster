"""自愈策略辅助函数 - 置信度计算与 Token 预估。

从 SelfHealingStrategyMixin 抽离的纯函数，避免 mixin 文件超 350 行。
仅依赖标准类型，无外部服务耦合，可独立单测。
"""
from typing import Any, Dict, Optional

# 置信度评分权重：坐标匹配 + 属性匹配 + 模型输出
_CONF_WEIGHT_COORD = 0.4
_CONF_WEIGHT_ATTR = 0.4
_CONF_WEIGHT_MODEL = 0.2
# Token 预估固定开销与最低值
_TOKEN_BASE_OVERHEAD = 200
_TOKEN_MINIMUM = 100


def compute_confidence(
    element_info: Dict[str, Any],
    element_attrs: Optional[Dict[str, Any]],
) -> float:
    """计算视觉自愈的综合置信度。

    评分构成:
        - 坐标匹配度 0.4: element_info 含 x/y/width/height 且均 > 0
        - 属性匹配度 0.4: element_attrs 非空且含 id/name/class 任一
        - 模型输出置信度 0.2: element_info 含 confidence 字段则用，否则默认 0.5

    Args:
        element_info: 视觉模型返回的元素坐标与置信度。
        element_attrs: 从坐标反查到的元素属性，可为 None。

    Returns:
        float: 0.0-1.0 的综合置信度。
    """
    score = 0.0
    coord_keys = ("x", "y", "width", "height")
    coord_valid = all(
        isinstance(element_info.get(k), (int, float)) and element_info.get(k, 0) > 0
        for k in coord_keys
    )
    if coord_valid:
        score += _CONF_WEIGHT_COORD

    if element_attrs:
        attr_keys = ("id", "name", "class")
        if any(element_attrs.get(k) for k in attr_keys):
            score += _CONF_WEIGHT_ATTR

    model_conf = element_info.get("confidence", 0.5)
    if not isinstance(model_conf, (int, float)):
        model_conf = 0.5
    score += _CONF_WEIGHT_MODEL * float(model_conf)

    return max(0.0, min(1.0, score))


def estimate_token_cost(nl_description: str) -> int:
    """根据自然语言描述长度预估单次自愈 Token 消耗。

    粗略估算: 中文字符按 1:1，ASCII 按 4:1，叠加固定开销 200。
    用于调用前单次预算校验，非精确计量。

    Args:
        nl_description: 步骤自然语言描述。

    Returns:
        int: 预估 Token 消耗，最低 100。
    """
    if not nl_description:
        return _TOKEN_MINIMUM
    cjk_count = sum(1 for ch in nl_description if ord(ch) > 127)
    ascii_count = len(nl_description) - cjk_count
    estimated = cjk_count + (ascii_count // 4) + _TOKEN_BASE_OVERHEAD
    return max(_TOKEN_MINIMUM, estimated)
