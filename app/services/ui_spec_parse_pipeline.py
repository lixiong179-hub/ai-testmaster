"""UI Spec Parse Pipeline - 兼容代理模块

所有实现已迁移到 ui_spec_parser/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.ui_spec_parser.pipeline_mixin import (
    UISpecParsePipelineMixin as UISpecParsePipeline,
    UISpecParseService,
)

__all__ = ["UISpecParsePipeline", "UISpecParseService"]
