# [R4-5 冻结 2026-11-10] 生产代码零引用（仅测试引用），保留备用；接线或删除前请先在《架构优化执行计划清单》登记。
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
