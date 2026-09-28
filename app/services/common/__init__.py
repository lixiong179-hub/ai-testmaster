"""跨业务复用的通用服务基类与工具。

当前导出：
    - BaseTokenBudgetGuard : Token 预算守卫抽象基类（自愈 / Agent / Visual AI 共用）
"""
from app.services.common.token_budget import BaseTokenBudgetGuard

__all__ = ["BaseTokenBudgetGuard"]
