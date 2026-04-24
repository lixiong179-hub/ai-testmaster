"""Case Generation Core - 兼容代理模块

所有实现已迁移到 case_generation/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.case_generation.core_mixin import (
    ContentSanitizer,
    CoreMixin,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TEST_CATEGORY_UI_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_API_AUTO,
    get_test_case_context,
)

__all__ = [
    "ContentSanitizer",
    "CoreMixin",
    "DEFAULT_TEST_POINT_PAGE_SIZE",
    "MAX_TEST_POINT_PAGE_SIZE",
    "TEST_CATEGORY_UI_AUTO",
    "TEST_CATEGORY_MANUAL",
    "TEST_CATEGORY_API_AUTO",
    "get_test_case_context",
]
