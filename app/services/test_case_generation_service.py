"""
测试用例生成服务 - 兼容代理模块

所有实现已迁移到 test_case_generation/ 子包，本文件仅保留向后兼容的导入。
"""
from app.services.test_case_generation import (
    TestCaseGenerationService,
    ContentSanitizer,
    get_test_case_context,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TEST_CATEGORY_UI_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_API_AUTO,
)

__all__ = [
    "TestCaseGenerationService",
    "ContentSanitizer",
    "get_test_case_context",
    "DEFAULT_TEST_POINT_PAGE_SIZE",
    "MAX_TEST_POINT_PAGE_SIZE",
    "TEST_CATEGORY_UI_AUTO",
    "TEST_CATEGORY_MANUAL",
    "TEST_CATEGORY_API_AUTO",
]
