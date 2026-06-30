"""Test Case Generation - 上下文精准加载 Mixin

从 base_mixin.py 拆分，包含：
    - _get_context_for_generation_precision: 上下文加载编排器（调用各 loader）
    - _init_context_skeleton: 初始化上下文骨架
    - _load_test_points: 测试点加载（指定ID 或 分页+未覆盖优先）
    - _check_required_ui_terms: 检查 UI 元素是否覆盖测试点所需关键词
    - _finalize_context: 去重 + 统计收尾

拆分理由：base_mixin.py 单文件 694 行超 350 行规范（项目规则第三章）。
"""
from typing import Any, Dict, List, Optional, Tuple

from app.crud import test_point as test_point_crud
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.services.test_case_generation._base_helpers import (
    ContextBudgetController,
    _dedupe_ints,
    _extract_terms,
    _find_missing_required_ui_terms,
    _test_point_entry,
    _test_point_search_text,
    _warning,
)

DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500


class TestCaseGenerationContextPrecisionMixin:
    """测试用例生成服务 - 上下文精准加载 Mixin"""

    __test__ = False

    async def _get_context_for_generation_precision(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
    ) -> Dict[str, Any]:
        """上下文加载编排器：测试点 → 需求 → UI → 质量检查 → 收尾"""
        requirement_file_ids = _dedupe_ints(requirement_file_ids)
        ui_file_ids = _dedupe_ints(ui_file_ids)
        ui_screen_ids = _dedupe_ints(ui_screen_ids)
        test_point_ids = _dedupe_ints(test_point_ids)
        budget = ContextBudgetController()
        context = self._init_context_skeleton(budget)

        selected_point_models, search_text, search_terms = self._load_test_points(
            context, project_id, test_point_ids, test_point_page, test_point_page_size
        )

        await self._load_requirement_from_files(
            context, project_id, requirement_file_ids, budget, force_refresh
        )
        self._load_requirement_from_test_points(
            context, project_id, selected_point_models, search_terms, budget
        )
        self._assess_requirement_quality(context)

        self._load_ui_descriptions(
            context, project_id, ui_screen_ids, ui_file_ids, search_text, search_terms
        )
        self._check_required_ui_terms(context, search_text)
        self._finalize_context(context, budget)

        return context

    def _init_context_skeleton(self, budget: ContextBudgetController) -> Dict[str, Any]:
        """初始化上下文骨架（含 stats 与 evidence_refs 默认结构）"""
        return {
            "requirement_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "files_used": [],
            "warnings": [],
            "context_stats": {
                "strategy": "precision",
                "token_budget": budget.max_tokens,
                "requirements_used": 0,
                "ui_screens_used": 0,
                "test_points_loaded": 0,
                "fallbacks": [],
            },
            "evidence_refs": {
                "requirements": [],
                "requirement_files": [],
                "ui_screens": [],
                "history_cases": [],
                "warnings": [],
            },
        }

    def _load_test_points(
        self,
        context: Dict[str, Any],
        project_id: int,
        test_point_ids: Optional[List[int]],
        test_point_page: int,
        test_point_page_size: int,
    ) -> Tuple[List[TestPoint], str, Any]:
        """加载测试点，返回 (selected_models, search_text, search_terms)"""
        selected_point_models: List[TestPoint] = []
        if test_point_ids:
            for point_id in test_point_ids:
                point = test_point_crud.get_test_point_by_id(self.db, point_id, project_id)
                if point:
                    selected_point_models.append(point)
                    context["test_points"].append(_test_point_entry(point))
                else:
                    context["warnings"].append(
                        _warning("TEST_POINT_NOT_FOUND", f"未找到测试点ID: {point_id}", {"test_point_id": point_id})
                    )
        else:
            skip = (test_point_page - 1) * test_point_page_size
            page_limit = min(test_point_page_size, MAX_TEST_POINT_PAGE_SIZE)
            covered_test_point_ids = {
                row[0]
                for row in self.db.query(TestCase.test_point_id)
                .filter(
                    TestCase.project_id == project_id,
                    TestCase.is_deleted == False,  # noqa: E712
                    TestCase.generate_status == 1,
                    TestCase.test_point_id.isnot(None),
                )
                .distinct()
                .all()
                if row[0] is not None
            }
            all_points = self.db.query(TestPoint).filter(TestPoint.project_id == project_id).all()
            total_count = len(all_points)
            all_points.sort(
                key=lambda point: (
                    point.id in covered_test_point_ids,
                    point.priority or 99,
                    point.id,
                )
            )
            selected_point_models = all_points[skip: skip + page_limit]
            for point in selected_point_models:
                context["test_points"].append(_test_point_entry(point))
            context["pagination"] = {
                "page": test_point_page,
                "page_size": len(selected_point_models),
                "total": total_count,
                "has_more": (skip + page_limit) < total_count,
                "uncovered_first": True,
                "covered_test_point_count": len(covered_test_point_ids),
            }

        context["context_stats"]["test_points_loaded"] = len(context["test_points"])
        search_text = _test_point_search_text(selected_point_models)
        search_terms = _extract_terms(search_text)
        return selected_point_models, search_text, search_terms

    def _check_required_ui_terms(
        self,
        context: Dict[str, Any],
        search_text: str,
    ) -> None:
        """检查 UI 元素是否覆盖测试点所需关键词，缺失时记录警告"""
        missing_required_ui_terms = _find_missing_required_ui_terms(search_text, context["ui_specs"])
        if missing_required_ui_terms:
            context["warnings"].append(_warning(
                "UI_REQUIRED_ELEMENT_MISSING",
                "当前页面解析数据可能缺少测试点所需的UI元素",
                {"missing_terms": missing_required_ui_terms},
            ))

    def _finalize_context(
        self,
        context: Dict[str, Any],
        budget: ContextBudgetController,
    ) -> None:
        """去重 files_used/evidence_refs，计算最终统计指标"""
        context["files_used"] = _dedupe_ints(context["files_used"])
        seen_requirement_ids = set()
        context["evidence_refs"]["requirements"] = [
            ref for ref in context["evidence_refs"]["requirements"]
            if not (ref["id"] in seen_requirement_ids or seen_requirement_ids.add(ref["id"]))
        ]
        seen_file_ids = set()
        context["evidence_refs"]["requirement_files"] = [
            ref for ref in context["evidence_refs"]["requirement_files"]
            if not (ref["id"] in seen_file_ids or seen_file_ids.add(ref["id"]))
        ]
        seen_screen_ids = set()
        context["evidence_refs"]["ui_screens"] = [
            ref for ref in context["evidence_refs"]["ui_screens"]
            if not (ref["id"] in seen_screen_ids or seen_screen_ids.add(ref["id"]))
        ]
        context["context_stats"]["requirements_used"] = (
            len(context["evidence_refs"]["requirements"]) +
            len(context["evidence_refs"]["requirement_files"])
        )
        context["context_stats"]["ui_screens_used"] = len(context["evidence_refs"]["ui_screens"])
        context["context_stats"]["estimated_tokens"] = {
            "requirement_content": budget.estimate_tokens(context["requirement_content"]),
            "ui_specs": budget.estimate_tokens(context["ui_specs"]),
            "ui_descriptions": budget.estimate_tokens(context["ui_descriptions"]),
        }
        context["evidence_refs"]["warnings"] = context["warnings"]
