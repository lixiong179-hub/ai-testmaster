"""test_case_generation - 基础辅助函数、常量、内容清洗、实体引用与测试点加载（thin wrapper）。

实际实现拆分至：
- _helpers_constants.py: 分页/预算/用例类型/需求与 UI 元素关键词常量
- _helpers_sanitizer.py: ContentSanitizer 内容清洗器（防 Prompt 注入）
- _helpers_text.py: 文本/JSON 处理、去重工具与需求质量评估
- _helpers_refs.py: 实体引用构造（测试点/需求/UI 屏幕引用字典、导航 ID 收集）
- _helpers_budget.py: ContextBudgetController 上下文预算控制器与需求文本裁剪
- _helpers_test_point.py: 测试点加载与文件内容获取

本文件保持向后兼容，原有 `from app.services.test_case_generation.helpers import xxx`
路径无需修改。continuous_scorer.py 因被外部模块直接引用保留独立文件。
"""
from app.services.test_case_generation._helpers_constants import (
    DEFAULT_ADJACENT_UI_SCREEN_LIMIT,
    DEFAULT_CONTEXT_TOKEN_BUDGET,
    DEFAULT_MATCHED_REQUIREMENT_LIMIT,
    DEFAULT_MATCHED_UI_SCREEN_LIMIT,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    REQUIRED_UI_ELEMENT_HINTS,
    REQUIREMENT_ACTION_VERBS,
    REQUIREMENT_MIN_CHAR_COUNT,
    TEST_CATEGORY_API_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_UI_AUTO,
)
from app.services.test_case_generation._helpers_sanitizer import ContentSanitizer
from app.services.test_case_generation._helpers_text import (
    _assess_requirement_quality,
    _dedupe_ints,
    _dedupe_strings,
    _extract_function_from_ai_prompt,
    _extract_terms,
    _find_missing_required_ui_terms,
    _has_flow_intent,
    _normalize_match_text,
    _safe_json_text,
    _score_terms,
    _warning,
)
from app.services.test_case_generation._helpers_refs import (
    _collect_navigation_screen_ids,
    _requirement_ref,
    _screen_desc,
    _screen_ref,
    _test_point_entry,
    _test_point_search_text,
)
from app.services.test_case_generation._helpers_budget import (
    ContextBudgetController,
    _trim_requirement_text,
)
from app.services.test_case_generation._helpers_test_point import (
    get_file_content_helper,
    load_test_points,
)


__all__ = [
    "DEFAULT_CONTEXT_TOKEN_BUDGET",
    "DEFAULT_TEST_POINT_PAGE_SIZE",
    "MAX_TEST_POINT_PAGE_SIZE",
    "DEFAULT_MATCHED_REQUIREMENT_LIMIT",
    "DEFAULT_MATCHED_UI_SCREEN_LIMIT",
    "DEFAULT_ADJACENT_UI_SCREEN_LIMIT",
    "REQUIRED_UI_ELEMENT_HINTS",
    "REQUIREMENT_ACTION_VERBS",
    "REQUIREMENT_MIN_CHAR_COUNT",
    "ContentSanitizer",
    "ContextBudgetController",
    "_assess_requirement_quality",
    "_collect_navigation_screen_ids",
    "_dedupe_ints",
    "_dedupe_strings",
    "_extract_function_from_ai_prompt",
    "_extract_terms",
    "_find_missing_required_ui_terms",
    "_get_file_content_helper",
    "_has_flow_intent",
    "_normalize_match_text",
    "_requirement_ref",
    "_safe_json_text",
    "_score_terms",
    "_screen_desc",
    "_screen_ref",
    "_test_point_entry",
    "_test_point_search_text",
    "_trim_requirement_text",
    "_warning",
    "get_file_content_helper",
    "load_test_points",
]

# 向后兼容：_get_file_content_helper 历史别名
_get_file_content_helper = get_file_content_helper
