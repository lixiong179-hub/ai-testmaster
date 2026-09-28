"""自愈体系子包 - 提供元素定位失败分析与自愈结果数据结构。

核心导出:
    - FailureAnalyzer: 失败分析器，基于错误信息与 DOM 快照判定失败类型
    - FailureType: 失败类型枚举
    - FailureAnalysis: 失败分析结果
    - HealResult: 自愈执行结果
"""
from app.services.self_healing.models import FailureAnalysis, FailureType, HealResult
from app.services.self_healing.failure_analyzer import FailureAnalyzer

__all__ = [
    "FailureAnalyzer",
    "FailureType",
    "FailureAnalysis",
    "HealResult",
]
