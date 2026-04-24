"""Precondition Executor - 兼容代理模块

所有实现已迁移到 precondition/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.precondition.executor_mixin import ExecutorMixin

__all__ = ["ExecutorMixin"]
