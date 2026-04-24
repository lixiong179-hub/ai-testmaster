"""Case Generation AI - 兼容代理模块

所有实现已迁移到 case_generation/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.case_generation.ai_mixin import AIMixin

__all__ = ["AIMixin"]
