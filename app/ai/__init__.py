"""
AI 抽象层包

本包定义了 Pipeline 所需的统一 AI 调用抽象，所有 Step 必须通过此层调用模型，
禁止直接调用模型 API。

核心组件：
    - AIClient Protocol : AI 调用抽象接口
    - AIResponse        : AI 响应数据类
    - TokenUsage        : Token 用量数据类
    - OpenAIClient      : OpenAI 兼容实现
    - MockAIClient      : 测试用 Mock 实现
    - FallbackAIClient  : 主备切换实现
    - AICallLog         : AI 调用日志模型
    - check_budget      : Token 预算检查
"""
from app.ai.client import AIClient, AIResponse, TokenUsage

__all__ = [
    "AIClient",
    "AIResponse",
    "TokenUsage",
]
