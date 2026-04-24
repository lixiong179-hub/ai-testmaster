"""Precondition Login - 兼容代理模块

所有实现已迁移到 precondition/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.precondition.login_mixin import LoginMixin

__all__ = ["LoginMixin"]
