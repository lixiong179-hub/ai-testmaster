"""Visual AI 引擎子包 - 视觉回归测试核心服务。

Phase 2 模块导出：
    - MatchLevelStrategy / StrictMatchLevel / LayoutMatchLevel / IgnoreColorsMatchLevel
        : 三层 Match Level 对比策略（Task 6）
    - ComparisonEngine / ComparisonResult / PixelDiffResult
        : 图像对比引擎，像素级 + LLM 语义（Task 7）
    - BaselineService
        : 基线 CRUD 服务（Task 5）
    - VisualAISDK / VisualCheckResult
        : 统一 SDK 高层 API（Task 9）
    - VisualTokenEstimator / VisualTokenBudgetGuard / TokenEstimate
        : Token 估算精确化与预算守卫（Task 10）

设计参考：Applitools Visual AI 三层 Match Level + Mabl Visual Regression。
"""
from app.services.visual_ai.match_level import (
    IgnoreColorsMatchLevel,
    LayoutMatchLevel,
    MatchLevelStrategy,
    MatchLevelFactory,
    StrictMatchLevel,
)
from app.services.visual_ai.comparison_engine import (
    ComparisonEngine,
    ComparisonResult,
    PixelDiffResult,
)
from app.services.visual_ai.baseline_service import BaselineService
from app.services.visual_ai.sdk import VisualAISDK, VisualCheckResult
from app.services.visual_ai.token_estimator import (
    TokenEstimate,
    VisualTokenBudgetGuard,
    VisualTokenEstimator,
)

__all__ = [
    # Match Level 策略（Task 6）
    "MatchLevelStrategy",
    "StrictMatchLevel",
    "LayoutMatchLevel",
    "IgnoreColorsMatchLevel",
    "MatchLevelFactory",
    # 图像对比引擎（Task 7）
    "ComparisonEngine",
    "ComparisonResult",
    "PixelDiffResult",
    # 基线服务（Task 5）
    "BaselineService",
    # 统一 SDK（Task 9）
    "VisualAISDK",
    "VisualCheckResult",
    # Token 估算（Task 10）
    "TokenEstimate",
    "VisualTokenEstimator",
    "VisualTokenBudgetGuard",
]
