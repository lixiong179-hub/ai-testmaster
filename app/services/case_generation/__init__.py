"""
Test Case Generation Service - 聚合入口
整合需求文档（文件）、UI原型图（文件）和测试点，生成高质量测试用例
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.case_generation.core_mixin import (
    CoreMixin as TestCaseGenerationBaseMixin,
    ContentSanitizer,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TEST_CATEGORY_UI_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_API_AUTO,
    get_test_case_context,
)
from app.services.case_generation.ai_mixin import AIMixin as TestCaseGenerationAiMixin
from app.services.case_generation.steps_mixin import StepsMixin as TestCaseGenerationBatchMixin


class TestCaseGenerationService(
    TestCaseGenerationBatchMixin,
    TestCaseGenerationAiMixin,
    TestCaseGenerationBaseMixin,
):
    """
    测试用例生成服务

    主要功能：
    1. 获取需求文档内容（从链接缓存或实时获取）
    2. 获取UI原型图描述（通过视觉模型解析）
    3. 获取测试点信息（支持分页）
    4. 整合所有信息，调用AI生成高质量测试用例
    """
    pass


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
