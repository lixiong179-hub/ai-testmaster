"""Backward-compatible entry for test case generation services.

New code should import from ``app.services.test_case_generation`` directly.
This package-level entry keeps old import paths working while delegating the
service implementation to the current package.
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
