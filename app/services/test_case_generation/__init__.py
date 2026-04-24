"""
Test Case Generation Service - 聚合入口
整合需求文档（文件）、UI原型图（文件）和测试点，生成高质量测试用例
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.services.test_case_generation.base_mixin import (
    TestCaseGenerationBaseMixin,
    ContentSanitizer,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TEST_CATEGORY_UI_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_API_AUTO,
)
from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
from app.services.test_case_generation.batch_mixin import TestCaseGenerationBatchMixin
from app.services.test_case_generation.validate_mixin import TestCaseGenerationValidateMixin


class TestCaseGenerationService(
    TestCaseGenerationValidateMixin,
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


async def get_test_case_context(
    db: Session,
    project_id: int,
    user_id: int,
    requirement_file_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None,
    ui_screen_ids: Optional[List[int]] = None,
    test_point_ids: Optional[List[int]] = None,
    test_point_page: int = 1,
    test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> Dict[str, Any]:
    """获取测试用例生成的上下文"""
    service = TestCaseGenerationService(db)
    return await service.get_context_for_generation(
        project_id=project_id,
        user_id=user_id,
        requirement_file_ids=requirement_file_ids,
        ui_file_ids=ui_file_ids,
        ui_screen_ids=ui_screen_ids,
        test_point_ids=test_point_ids,
        test_point_page=test_point_page,
        test_point_page_size=test_point_page_size
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
