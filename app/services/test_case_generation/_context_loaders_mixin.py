"""test_case_generation - 上下文加载器 mixin。

拆分自 context_builder.py，提供 _ContextLoadersMixin 类，负责：
测试点加载、上下文骨架编排与收尾、需求质量评估。

需求/UI 加载器实现见 _requirement_ui_loaders_mixin.py（_RequirementUiLoadersMixin），
由 _get_context_for_generation_precision 通过 self.* 调用，借助 ContextBuilder 多继承 MRO 解析。
与 _HistoryScoringMixin 组合后由 ContextBuilder（context_builder.py）统一对外暴露。
"""
from typing import Any, Dict, List, Optional, Tuple

from app.crud import test_point as test_point_crud
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.services.test_case_generation.helpers import (
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    ContextBudgetController,
    _assess_requirement_quality,
    _dedupe_ints,
    _extract_terms,
    _find_missing_required_ui_terms,
    _test_point_entry,
    _test_point_search_text,
    _warning,
)


class _ContextLoadersMixin:
    """上下文加载器 mixin：测试点加载、上下文骨架编排与收尾、需求质量评估。

    依赖 self.db（由组合类 ContextBuilder.__init__ 注入）。
    """

    # ── 公开入口 ──
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
        """获取测试用例生成的上下文信息（公开入口）。"""
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
        """构建 UI 描述文本（含屏幕名/功能/元素统计）。"""
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

    # ── 上下文加载编排 ──
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
        """上下文加载编排器：测试点 → 需求 → UI → 质量检查 → 收尾。"""
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
        """初始化上下文骨架（含 stats 与 evidence_refs 默认结构）。"""
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
        """加载测试点，返回 (selected_models, search_text, search_terms)。"""
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
        """检查 UI 元素是否覆盖测试点所需关键词，缺失时记录警告。"""
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
        """去重 files_used/evidence_refs，计算最终统计指标。"""
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

    # ── 需求质量评估 ──
    def _assess_requirement_quality(self, context: Dict[str, Any]) -> None:
        """需求文档质量预检：基于字数与操作动词判定 requirement_quality。"""
        requirement_text = context["requirement_content"].strip()
        requirement_quality, quality_warning = _assess_requirement_quality(requirement_text)
        if requirement_quality == "insufficient":
            context["warnings"].append(_warning(
                "REQUIREMENT_TOO_SHORT",
                "需求文档内容过短（<50字），生成质量可能受限",
                {"char_count": len(requirement_text)},
            ))
        if quality_warning is not None:
            context["warnings"].append(quality_warning)
        context["context_stats"]["requirement_quality"] = requirement_quality
