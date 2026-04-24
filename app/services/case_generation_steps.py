"""Case Generation Steps - 兼容代理模块

所有实现已迁移到 case_generation/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.case_generation.steps_mixin import StepsMixin

__all__ = ["StepsMixin"]
