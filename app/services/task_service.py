"""Task Service - 兼容代理模块

所有实现已迁移到 task_service/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.task_service import TaskService

__all__ = ["TaskService"]
