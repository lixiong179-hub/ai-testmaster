"""自愈体系数据模型 - 定义失败类型枚举与分析结果数据结构。

本模块为自愈体系的基础数据层，不依赖任何外部服务，可独立导入使用。
"""
import enum
from dataclasses import dataclass, field
from typing import Any, Optional


class FailureType(enum.Enum):
    """元素定位失败类型枚举。

    Attributes:
        ELEMENT_GONE: 元素从 DOM 消失，需重新生成选择器。
        DOM_CHANGED: DOM 结构变更但元素可能存在，需校正定位器。
        LOAD_DELAY: 元素未及时加载或不可见，重试即可恢复。
        ENV_NOISE: 环境噪声（弹窗/网络异常/浏览器崩溃），应跳过而非自愈。
    """
    ELEMENT_GONE = "element_gone"
    DOM_CHANGED = "dom_changed"
    LOAD_DELAY = "load_delay"
    ENV_NOISE = "env_noise"


@dataclass
class FailureAnalysis:
    """失败分析结果 - 描述失败类型、分类置信度与建议的自愈策略。

    Attributes:
        failure_type: 失败类型分类结果。
        confidence: 分类置信度，取值范围 0.0-1.0。
        suggested_strategy: 建议策略，取值为 "retry" / "ai_heal" / "skip"。
        evidence: 分类依据，如 matched_keywords、dom_check_result 等可追溯证据。
    """
    failure_type: FailureType
    confidence: float
    suggested_strategy: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealResult:
    """自愈执行结果 - 描述自愈后的选择器、置信度与本次 Token 消耗。

    Attributes:
        selector: 自愈后的新选择器，自愈失败时为 None。
        confidence: 自愈置信度，取值范围 0.0-1.0。
        token_cost: 本次自愈消耗的 Token 数量。
        strategy: 实际命中的自愈策略，取值为 "mcp" / "vision" / "stagehand" / "retry" / "skip"。
    """
    selector: Optional[str]
    confidence: float
    token_cost: int
    strategy: str


__all__ = ["FailureType", "FailureAnalysis", "HealResult"]
