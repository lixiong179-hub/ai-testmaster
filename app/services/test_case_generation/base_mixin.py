"""
Test Case Generation Service - 基础方法Mixin（聚合入口）

本文件为薄聚合层，实际实现拆分到 3 个子 Mixin：
    - _context_precision_mixin.py: 上下文精准加载编排器 + 测试点加载 + 收尾
    - _context_loaders_mixin.py: 需求与 UI 加载器
    - _history_scoring_mixin.py: 历史用例信任度 + 完整性评分

`TestCaseGenerationBaseMixin` 聚合上述 3 个子 Mixin，对外保持类名与
直接实例化契约（测试用 `TestCaseGenerationBaseMixin(self.db)`）。

向后兼容 re-export：
    - _base_helpers 的符号（_warning/_dedupe_ints/ContextBudgetController 等）
    - _content_sanitizer 的 ContentSanitizer
    - 分页与分类常量
"""
from typing import Any, Dict, List

from sqlalchemy.orm import Session

# 从拆分模块 re-export，保持向后兼容
from app.services.test_case_generation._base_helpers import (  # noqa: F401
    ContextBudgetController,
    DEFAULT_ADJACENT_UI_SCREEN_LIMIT,
    DEFAULT_CONTEXT_TOKEN_BUDGET,
    DEFAULT_MATCHED_REQUIREMENT_LIMIT,
    DEFAULT_MATCHED_UI_SCREEN_LIMIT,
    REQUIRED_UI_ELEMENT_HINTS,
    REQUIREMENT_ACTION_VERBS,
    REQUIREMENT_MIN_CHAR_COUNT,
    _assess_requirement_quality,
    _collect_navigation_screen_ids,
    _dedupe_ints,
    _dedupe_strings,
    _extract_terms,
    _find_missing_required_ui_terms,
    _has_flow_intent,
    _normalize_match_text,
    _requirement_ref,
    _safe_json_text,
    _score_terms,
    _screen_desc,
    _screen_ref,
    _test_point_entry,
    _test_point_search_text,
    _trim_requirement_text,
    _warning,
)
from app.services.test_case_generation._content_sanitizer import ContentSanitizer  # noqa: F401
from app.services.test_case_generation._context_precision_mixin import (  # noqa: F401
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TestCaseGenerationContextPrecisionMixin,
)
from app.services.test_case_generation._context_loaders_mixin import (  # noqa: F401
    TestCaseGenerationContextLoadersMixin,
)
from app.services.test_case_generation._history_scoring_mixin import (  # noqa: F401
    TestCaseGenerationHistoryScoringMixin,
)

TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"


class TestCaseGenerationBaseMixin(
    TestCaseGenerationContextPrecisionMixin,
    TestCaseGenerationContextLoadersMixin,
    TestCaseGenerationHistoryScoringMixin,
):
    """测试用例生成服务 - 基础方法Mixin（聚合 3 个子 Mixin）"""

    __test__ = False

    def __init__(self, db: Session):
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: List[int] | None = None,
        ui_file_ids: List[int] | None = None,
        ui_screen_ids: List[int] | None = None,
        test_point_ids: List[int] | None = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
    ) -> Dict[str, Any]:
        """获取测试用例生成的上下文信息（公开入口，委托到 _get_context_for_generation_precision）"""
        return await self._get_context_for_generation_precision(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            force_refresh=force_refresh,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size,
        )

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """构建UI描述文本"""
        if not ui_descriptions:
            return ""
        parts = []
        for ui_desc in ui_descriptions:
            if ui_desc.get("screen_name"):
                name = ui_desc["screen_name"]
                summary = ui_desc.get("summary", "")
                element_count = ui_desc.get("element_count", 0)
                button_count = ui_desc.get("button_count", 0)
                input_count = ui_desc.get("input_count", 0)
                desc_parts = [f"【{name}】"]
                if summary:
                    desc_parts.append(f"功能：{summary}")
                if element_count:
                    desc_parts.append(f"元素：{element_count}个（按钮{button_count}个，输入框{input_count}个）")
                parts.append("\n".join(desc_parts))
            else:
                name = ui_desc.get("screen_name") or ui_desc.get("file_name") or ui_desc.get("name", "未命名")
                file_id = ui_desc.get("file_id", "")
                content = ui_desc.get("content", "")
                description = ui_desc.get("description", "")
                if content:
                    parts.append(f"【{name}】\n{content}")
                elif description:
                    parts.append(f"【{name}】\n{description}")
                else:
                    parts.append(f"【{name}】(文件ID: {file_id}，内容待提取)")
        return "\n\n".join(parts)
