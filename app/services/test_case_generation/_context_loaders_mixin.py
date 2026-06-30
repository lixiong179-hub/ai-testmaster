"""Test Case Generation - 需求与 UI 加载器 Mixin

从 base_mixin.py 拆分，包含：
    - _load_requirement_from_files: 按文件ID加载需求内容
    - _load_requirement_from_test_points: 按测试点关联/关键词匹配加载需求
    - _assess_requirement_quality: 需求质量预检（字数+操作动词）
    - _load_ui_descriptions: UI 描述加载分发器
    - _load_ui_from_screen_ids: 按屏幕ID批量加载 UI
    - _load_ui_from_file_ids: 按 UI 文件加载已解析屏幕
    - _load_ui_by_keyword_match: 按测试点关键词匹配 UI 屏幕

拆分理由：base_mixin.py 单文件 694 行超 350 行规范（项目规则第三章）。
"""
from typing import Any, Dict, List, Optional

from app.crud import file as file_crud
from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen
from app.services.file_content_extractor import get_file_content
from app.services.test_case_generation._base_helpers import (
    DEFAULT_ADJACENT_UI_SCREEN_LIMIT,
    DEFAULT_MATCHED_REQUIREMENT_LIMIT,
    DEFAULT_MATCHED_UI_SCREEN_LIMIT,
    ContextBudgetController,
    _assess_requirement_quality,
    _collect_navigation_screen_ids,
    _dedupe_ints,
    _has_flow_intent,
    _requirement_ref,
    _score_terms,
    _screen_desc,
    _screen_ref,
    _trim_requirement_text,
    _warning,
)


class TestCaseGenerationContextLoadersMixin:
    """测试用例生成服务 - 需求与 UI 加载器 Mixin"""

    __test__ = False

    async def _load_requirement_from_files(
        self,
        context: Dict[str, Any],
        project_id: int,
        requirement_file_ids: List[int],
        budget: ContextBudgetController,
        force_refresh: bool,
    ) -> None:
        """按文件ID加载需求文档内容，force_refresh 时实时获取"""
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
        """按测试点关联需求或关键词匹配加载需求内容"""
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
        """需求文档质量预检：基于字数与操作动词判定 requirement_quality"""
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
        """UI 描述加载分发器：屏幕ID > 文件ID > 关键词匹配"""
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
        """按屏幕ID批量查询 UI（规避 N+1）"""
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
        """按 UI 文件加载已解析屏幕"""
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
        """按测试点关键词匹配 UI 屏幕，必要时扩展相邻导航屏幕"""
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
