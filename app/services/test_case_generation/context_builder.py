"""test_case_generation - 上下文构建器（组合模式组件）。

合并自 base_mixin.py + _context_precision_mixin.py + _context_loaders_mixin.py
+ _history_scoring_mixin.py，提供 ContextBuilder 类负责测试用例生成的上下文加载、
需求/UI 加载、历史用例信任度评分与完整性评分。

构造函数接收 db: Session，对外保持 get_context_for_generation /
enrich_context_with_trust_and_scoring 公开方法签名兼容。
"""
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.crud import file as file_crud
from app.crud import test_point as test_point_crud
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.services.file_content_extractor import get_file_content
from app.services.test_case_generation.helpers import (
    DEFAULT_ADJACENT_UI_SCREEN_LIMIT,
    DEFAULT_MATCHED_REQUIREMENT_LIMIT,
    DEFAULT_MATCHED_UI_SCREEN_LIMIT,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    ContextBudgetController,
    _assess_requirement_quality,
    _collect_navigation_screen_ids,
    _dedupe_ints,
    _extract_terms,
    _find_missing_required_ui_terms,
    _has_flow_intent,
    _requirement_ref,
    _score_terms,
    _screen_desc,
    _screen_ref,
    _test_point_entry,
    _test_point_search_text,
    _trim_requirement_text,
    _warning,
)


class ContextBuilder:
    """测试用例生成上下文构建器。

    职责：
        1. 加载测试点（指定 ID 或分页+未覆盖优先）
        2. 加载需求文档内容（按文件 ID 或测试点关联/关键词匹配）
        3. 加载 UI 描述（按屏幕 ID/文件 ID/关键词匹配）
        4. 历史用例信任度过滤与完整性评分
    """

    __test__ = False

    def __init__(self, db: Session) -> None:
        self.db = db

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

    # ── 需求与 UI 加载器 ──
    async def _load_requirement_from_files(
        self,
        context: Dict[str, Any],
        project_id: int,
        requirement_file_ids: List[int],
        budget: ContextBudgetController,
        force_refresh: bool,
    ) -> None:
        """按文件 ID 加载需求文档内容，force_refresh 时实时获取。"""
        if not requirement_file_ids:
            return
        for file_id in requirement_file_ids:
            file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
            if file_record and file_record.resource_type == "requirement":
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_id)
                if content:
                    context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{budget.trim_text(content, 1800)}"
                    context["files_used"].append(file_id)
                    context["evidence_refs"]["requirement_files"].append({
                        "id": file_id,
                        "file_name": file_record.file_name,
                    })

    def _load_requirement_from_test_points(
        self,
        context: Dict[str, Any],
        project_id: int,
        selected_point_models: List[TestPoint],
        search_terms: Any,
        budget: ContextBudgetController,
    ) -> None:
        """按测试点关联需求或关键词匹配加载需求内容。"""
        if context["requirement_content"]:
            return
        requirement_ids = _dedupe_ints([p.requirement_id for p in selected_point_models if p.requirement_id])
        requirements: List[Requirement] = []
        if requirement_ids:
            requirements = self.db.query(Requirement).filter(
                Requirement.project_id == project_id,
                Requirement.id.in_(requirement_ids),
            ).order_by(Requirement.update_time.desc(), Requirement.id.desc()).all()
        if requirements:
            for req in requirements:
                content, trimmed = _trim_requirement_text(req.description or "", search_terms, budget, 1800)
                context["requirement_content"] += f"\n\n【{req.req_no} {req.title}】\n{content}"
                context["evidence_refs"]["requirements"].append(_requirement_ref(req))
                if req.source_file_id:
                    context["files_used"].append(req.source_file_id)
                if trimmed:
                    context["warnings"].append(_warning(
                        "REQUIREMENT_TRIMMED_BY_KEYWORDS",
                        "需求文本已基于测试点关键词裁剪",
                        {"requirement_id": req.id},
                    ))
            context["context_stats"]["requirement_strategy"] = "test_point_requirement"
        elif search_terms:
            candidates = []
            all_requirements = self.db.query(Requirement).filter(Requirement.project_id == project_id).all()
            for req in all_requirements:
                score = _score_terms(search_terms, req.req_no, req.title, req.description)
                if score > 0:
                    candidates.append((score, req))
            candidates.sort(key=lambda item: (-item[0], item[1].priority or 99, item[1].id))
            for _, req in candidates[:DEFAULT_MATCHED_REQUIREMENT_LIMIT]:
                content, trimmed = _trim_requirement_text(req.description or "", search_terms, budget, 1200)
                context["requirement_content"] += f"\n\n【{req.req_no} {req.title}】\n{content}"
                context["evidence_refs"]["requirements"].append(_requirement_ref(req))
                if req.source_file_id:
                    context["files_used"].append(req.source_file_id)
                if trimmed:
                    context["warnings"].append(_warning(
                        "REQUIREMENT_TRIMMED_BY_KEYWORDS",
                        "需求文本已基于测试点关键词裁剪",
                        {"requirement_id": req.id},
                    ))
            if candidates:
                context["context_stats"]["requirement_strategy"] = "keyword_top_n"
                context["warnings"].append(_warning(
                    "REQUIREMENT_KEYWORD_MATCH",
                    "未找到测试点直接关联需求，已按测试点关键词匹配需求Top-N",
                    {"matched_requirement_ids": [req.id for _, req in candidates[:DEFAULT_MATCHED_REQUIREMENT_LIMIT]]},
                ))
            else:
                context["warnings"].append(_warning("REQUIREMENT_NOT_FOUND", "未找到与测试点匹配的需求，上下文将缺少精准需求约束"))
                context["context_stats"]["fallbacks"].append("requirement_not_found")
        else:
            context["warnings"].append(_warning("REQUIREMENT_NOT_FOUND", "测试点文本为空，无法按需匹配需求"))
            context["context_stats"]["fallbacks"].append("empty_test_point_for_requirement")

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

    def _load_ui_descriptions(
        self,
        context: Dict[str, Any],
        project_id: int,
        ui_screen_ids: Optional[List[int]],
        ui_file_ids: Optional[List[int]],
        search_text: str,
        search_terms: Any,
    ) -> None:
        """UI 描述加载分发器：屏幕ID > 文件ID > 关键词匹配。"""
        if ui_screen_ids:
            self._load_ui_from_screen_ids(context, project_id, ui_screen_ids)
        elif ui_file_ids:
            self._load_ui_from_file_ids(context, project_id, ui_file_ids)
        if not context["ui_descriptions"] and not context["ui_specs"]:
            self._load_ui_by_keyword_match(context, project_id, search_text, search_terms)

    def _load_ui_from_screen_ids(
        self,
        context: Dict[str, Any],
        project_id: int,
        ui_screen_ids: List[int],
    ) -> None:
        """按屏幕 ID 批量查询 UI（规避 N+1）。"""
        screens = self.db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.id.in_(ui_screen_ids),
            UIPrototypeScreen.project_id == project_id,
        ).all()
        screen_map: Dict[int, UIPrototypeScreen] = {screen.id: screen for screen in screens}
        found_screen_ids = set()
        for screen_id in ui_screen_ids:
            screen = screen_map.get(screen_id)
            if screen:
                found_screen_ids.add(screen.id)
                context["ui_descriptions"].append(_screen_desc(screen, "explicit"))
                context["evidence_refs"]["ui_screens"].append(_screen_ref(screen, "explicit"))
                if screen.ui_spec:
                    context["ui_specs"].append({
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec,
                        "navigation_flow": screen.navigation_flow,
                        "related_screens": screen.related_screens,
                    })
                else:
                    context["warnings"].append(_warning(
                        "UI_SPEC_MISSING",
                        f"屏幕「{screen.screen_name}」缺少ui_spec，交互步骤需标记待确认UI",
                        {"screen_id": screen.id},
                    ))
            else:
                context["warnings"].append(_warning("UI_SCREEN_NOT_FOUND", f"未找到UI屏幕ID: {screen_id}", {"screen_id": screen_id}))
        missing_count = len(set(ui_screen_ids) - found_screen_ids)
        if missing_count:
            context["warnings"].append(_warning("UI_PARTIAL_MATCH", f"{missing_count}个UI屏幕未被纳入上下文"))

    def _load_ui_from_file_ids(
        self,
        context: Dict[str, Any],
        project_id: int,
        ui_file_ids: List[int],
    ) -> None:
        """按 UI 文件加载已解析屏幕。"""
        for file_id in ui_file_ids:
            file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
            if file_record and file_record.resource_type == "ui_mockup":
                context["ui_descriptions"].append({
                    "file_name": file_record.file_name,
                    "file_url": file_record.file_url,
                    "description": file_record.description or "",
                })
                context["files_used"].append(file_id)
                linked_screens = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.project_id == project_id,
                    UIPrototypeScreen.prototype_name == file_record.file_name,
                    UIPrototypeScreen.parse_status == "completed",
                    UIPrototypeScreen.ui_spec.isnot(None),
                ).all()
                if not linked_screens:
                    context["warnings"].append(_warning(
                        "UI_FILE_NO_PARSED_SCREENS",
                        f"UI文件「{file_record.file_name}」无已解析屏幕，无法提供可交互UI元素",
                        {"file_id": file_id, "file_name": file_record.file_name},
                    ))
                for screen in linked_screens:
                    context["ui_descriptions"].append(_screen_desc(screen, "ui_file"))
                    context["evidence_refs"]["ui_screens"].append(_screen_ref(screen, "ui_file"))
                    context["ui_specs"].append({
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec,
                        "navigation_flow": screen.navigation_flow,
                        "related_screens": screen.related_screens,
                    })

    def _load_ui_by_keyword_match(
        self,
        context: Dict[str, Any],
        project_id: int,
        search_text: str,
        search_terms: Any,
    ) -> None:
        """按测试点关键词匹配 UI 屏幕，必要时扩展相邻导航屏幕。"""
        matched_screens: List[UIPrototypeScreen] = []
        if search_terms:
            screen_candidates = []
            screens = self.db.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id == project_id).all()
            for screen in screens:
                score = _score_terms(search_terms, screen.screen_name, screen.prototype_name, screen.summary, screen.ui_spec)
                if score > 0:
                    parse_boost = 1 if screen.ui_spec else 0
                    screen_candidates.append((score, parse_boost, screen))
            screen_candidates.sort(key=lambda item: (-item[0], -item[1], item[2].screen_order or 0, item[2].id))
            matched_screens = [item[2] for item in screen_candidates[:DEFAULT_MATCHED_UI_SCREEN_LIMIT]]

        if matched_screens:
            seen_screen_ids = {screen.id for screen in matched_screens}
            if _has_flow_intent(search_text):
                adjacent_ids: List[int] = []
                for screen in matched_screens:
                    adjacent_ids.extend(_collect_navigation_screen_ids(screen))
                adjacent_ids = [sid for sid in _dedupe_ints(adjacent_ids) if sid not in seen_screen_ids]
                if adjacent_ids:
                    adjacent = self.db.query(UIPrototypeScreen).filter(
                        UIPrototypeScreen.project_id == project_id,
                        UIPrototypeScreen.id.in_(adjacent_ids[:DEFAULT_ADJACENT_UI_SCREEN_LIMIT]),
                    ).all()
                    for screen in adjacent:
                        matched_screens.append(screen)
                        seen_screen_ids.add(screen.id)
            for screen in matched_screens:
                confidence = "matched" if _score_terms(search_terms, screen.screen_name, screen.summary, screen.ui_spec) > 0 else "adjacent"
                context["ui_descriptions"].append(_screen_desc(screen, confidence))
                context["evidence_refs"]["ui_screens"].append(_screen_ref(screen, confidence))
                if screen.ui_spec:
                    context["ui_specs"].append({
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec,
                        "navigation_flow": screen.navigation_flow,
                        "related_screens": screen.related_screens,
                    })
                else:
                    context["warnings"].append(_warning(
                        "UI_SPEC_MISSING",
                        f"UI屏幕《{screen.screen_name}》缺少ui_spec，交互步骤需标记待确认UI",
                        {"screen_id": screen.id},
                    ))
            context["context_stats"]["ui_strategy"] = "keyword_top_n"
        else:
            context["warnings"].append(_warning("UI_NO_MATCH", "未匹配到与测试点相关的UI页面，未回退加载全量UI"))
            context["context_stats"]["fallbacks"].append("ui_not_found")

    # ── 历史用例信任度与完整性评分 ──
    def enrich_context_with_trust_and_scoring(
        self,
        context: Dict[str, Any],
        project_id: int,
        history_case_ids: list[int] | None = None,
        history_limit: int = 10,
    ) -> None:
        """注入历史用例并基于信任度过滤，计算上下文完整性评分。"""
        from app.api.v1.endpoints.test_case_ai_generate._context import (
            _extract_terms as _extract_history_terms, _score_terms as _score_history_terms,
            _assess_history_trust, _summarize_history_case,
        )

        current_requirement_ids: set[int] = set()
        current_ui_screen_ids: set[int] = set()
        for tp in context.get("test_points", []):
            if isinstance(tp, dict) and tp.get("requirement_id"):
                current_requirement_ids.add(tp["requirement_id"])
        for ui_ref in context.get("evidence_refs", {}).get("ui_screens", []):
            if isinstance(ui_ref, dict) and ui_ref.get("id"):
                current_ui_screen_ids.add(ui_ref["id"])

        if history_case_ids is not None and len(history_case_ids) == 0:
            cases = []
            similarity_by_case_id = {}
        elif history_case_ids is not None and len(history_case_ids) > 0:
            cases = self.db.query(TestCase).filter(
                TestCase.id.in_(history_case_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.notin_(['archived', 'deprecated']),
            ).all()
            similarity_by_case_id = {}
        else:
            search_terms = []
            for tp in context.get("test_points", []):
                if isinstance(tp, dict):
                    search_terms.append(f"{tp.get('module', '')} {tp.get('point', '')} {tp.get('function', '')}")
            query_terms = _extract_history_terms(*search_terms) if search_terms else set()
            all_cases = self.db.query(TestCase).filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.notin_(['archived', 'deprecated']),
            ).order_by(TestCase.id).all()
            if query_terms:
                scored_cases = []
                for case in all_cases:
                    score = _score_history_terms(
                        query_terms, case.module, case.title,
                        case.summary, case.expected_result, case.steps_json,
                    )
                    if score > 0:
                        scored_cases.append((score, case))
                scored_cases.sort(key=lambda item: (-item[0], item[1].id))
                max_score = scored_cases[0][0] if scored_cases else 0
                cases = [case for _, case in scored_cases[:history_limit]]
                similarity_by_case_id = {
                    case.id: (score / max_score if max_score else 0.0)
                    for score, case in scored_cases[:history_limit]
                }
                if not cases:
                    context.setdefault("warnings", []).append({
                        "code": "HISTORY_NO_SIMILAR_CASE",
                        "message": "未找到与当前测试点相似的历史用例，默认不注入历史参考",
                        "detail": {"limit": history_limit},
                    })
            else:
                cases = []
                similarity_by_case_id = {}
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_NO_QUERY_TEXT",
                    "message": "测试点文本为空，默认不注入历史用例",
                    "detail": {},
                })

        history_cases = []
        low_trust_filtered_count = 0
        for c in cases:
            trust_level, staleness_reason = _assess_history_trust(
                c, current_requirement_ids, current_ui_screen_ids, self.db,
            )
            if trust_level == "low":
                low_trust_filtered_count += 1
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_LOW_TRUST_FILTERED",
                    "message": f"历史用例「{c.title}」需求不匹配，已从生成上下文中剔除",
                    "detail": {"case_id": c.id, "case_no": c.case_no, "staleness_reason": staleness_reason},
                })
                continue
            if trust_level == "medium":
                low_trust_filtered_count += 1
                context.setdefault("warnings", []).append({
                    "code": "HISTORY_POTENTIALLY_STALE",
                    "message": f"历史用例「{c.title}」可信度不足，已从生成上下文中剔除",
                    "detail": {"case_id": c.id, "case_no": c.case_no, "trust_level": trust_level, "staleness_reason": staleness_reason},
                })
                continue
            history_cases.append(_summarize_history_case(
                c,
                similarity_by_case_id.get(c.id),
                trust_level=trust_level,
                staleness_reason=staleness_reason,
            ))

        context["history_cases"] = history_cases
        context.setdefault("evidence_refs", {})["history_cases"] = [
            {
                "id": item["id"],
                "case_no": item.get("case_no"),
                "design_tag": item.get("design_tag"),
                "similarity": item.get("similarity"),
                "trust_level": item.get("trust_level", "high"),
                "staleness_reason": item.get("staleness_reason", ""),
            }
            for item in history_cases
        ]
        context.setdefault("context_stats", {})["history_cases_used"] = len(history_cases)
        if low_trust_filtered_count > 0:
            context["context_stats"]["history_low_trust_filtered"] = low_trust_filtered_count

        completeness = self._compute_completeness_score(context=context, project_id=project_id)
        context["context_stats"]["completeness_score"] = completeness["score"]
        context["context_stats"]["missing_core_context"] = completeness["missing_core_context"]
        context["context_stats"]["low_confidence_reasons"] = completeness["low_confidence_reasons"]
        if completeness["score"] < 80:
            context.setdefault("warnings", []).append({
                "code": "CONTEXT_COMPLETENESS_LOW",
                "message": (
                    f"上下文完整性评分 {completeness['score']}，"
                    + ("建议人工复核" if completeness["score"] < 50 else "部分步骤可能需标记待确认")
                ),
                "detail": {"score": completeness["score"], "missing": completeness["missing_core_context"]},
            })
        context["evidence_refs"]["warnings"] = context.get("warnings", [])

        try:
            from app.db.database import PrimarySessionLocal
            from app.services.ab_test_service import ABTestService
            _ab_db = PrimarySessionLocal()
            try:
                _ab_service = ABTestService(_ab_db)
                _ab_service.record_metric(
                    experiment_id="context_precision_v1",
                    variant="treatment",
                    project_id=project_id,
                    metric_name="completeness_score",
                    metric_value=float(context["context_stats"].get("completeness_score", 0)),
                    detail={
                        "missing_core_context": context["context_stats"].get("missing_core_context", []),
                        "low_confidence_reasons": context["context_stats"].get("low_confidence_reasons", []),
                    },
                )
                _ab_db.commit()
            except Exception:
                _ab_db.rollback()
            finally:
                _ab_db.close()
        except Exception:
            pass

    def _compute_completeness_score(
        self,
        context: Dict[str, Any],
        project_id: int,
    ) -> Dict[str, Any]:
        """计算上下文完整性评分（测试点/需求/UI/流程/历史 5 维度加权）。"""
        WEIGHT_TEST_POINT = 20
        WEIGHT_REQUIREMENT = 35
        WEIGHT_UI = 25
        WEIGHT_FLOW = 10
        WEIGHT_HISTORY = 10

        missing_core_context: List[str] = []
        low_confidence_reasons: List[str] = []
        score = 0

        test_points = context.get("test_points", [])
        has_test_point = bool(test_points) and all(
            tp.get("point") and tp.get("module") for tp in test_points if isinstance(tp, dict)
        )
        if has_test_point:
            score += WEIGHT_TEST_POINT
        else:
            missing_core_context.append("test_point")

        has_requirement = bool(context.get("requirement_content", "").strip())
        if has_requirement:
            score += WEIGHT_REQUIREMENT
        else:
            missing_core_context.append("requirement")
            low_confidence_reasons.append("REQUIREMENT_NOT_FOUND")

        ui_specs = context.get("ui_specs", [])
        ui_descriptions = context.get("ui_descriptions", [])
        has_ui = bool(ui_specs) or any(
            d.get("parse_status") == "completed" for d in ui_descriptions if isinstance(d, dict)
        )
        project = self.db.query(Project).filter(Project.id == project_id).first() if project_id else None
        is_ui_project = project and (project.project_type or "web") in ("web", "app")

        if has_ui:
            score += WEIGHT_UI
        else:
            if is_ui_project:
                missing_core_context.append("ui")
                low_confidence_reasons.append("UI_NO_MATCH")
            else:
                score += int(WEIGHT_UI * WEIGHT_REQUIREMENT / (WEIGHT_REQUIREMENT + WEIGHT_TEST_POINT))

        has_flow = any(
            _has_flow_intent(f"{tp.get('module', '')} {tp.get('point', '')}")
            for tp in test_points if isinstance(tp, dict)
        )
        if has_flow and has_ui:
            matched_screen_ids = {s.get("screen_id") or s.get("id") for s in ui_descriptions if isinstance(s, dict)}
            has_navigation = any(
                isinstance(s.get("navigation_flow") or s.get("related_screens"), (dict, list))
                for s in ui_specs if isinstance(s, dict)
            )
            if has_navigation or len(matched_screen_ids) > 1:
                score += WEIGHT_FLOW
            else:
                score += WEIGHT_FLOW // 2
                low_confidence_reasons.append("UI_NO_NAVIGATION")
        elif not has_flow:
            score += WEIGHT_FLOW
        else:
            score += WEIGHT_FLOW // 4

        history_cases_used = context.get("context_stats", {}).get("history_cases_used", 0)
        if history_cases_used > 0:
            score += WEIGHT_HISTORY
        elif not missing_core_context:
            score += WEIGHT_HISTORY

        return {
            "score": min(100, score),
            "missing_core_context": missing_core_context,
            "low_confidence_reasons": low_confidence_reasons,
        }


# 向后兼容别名：历史代码以 TestCaseGenerationBaseMixin 名称实例化
TestCaseGenerationBaseMixin = ContextBuilder
