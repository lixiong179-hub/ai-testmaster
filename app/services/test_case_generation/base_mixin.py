"""
Test Case Generation Service - 基础方法Mixin
包含内容清洗器、上下文获取、UI描述构建等基础能力
"""
import re
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.requirement import Requirement
from app.models.test_point import TestPoint
from app.models.test_case import TestCase
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import test_point as test_point_crud
from app.crud import file as file_crud
from app.services.test_case_generation.test_point_loader import _extract_function_from_ai_prompt
from app.services.file_content_extractor import get_file_content

DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500
DEFAULT_CONTEXT_TOKEN_BUDGET = 5000
DEFAULT_MATCHED_REQUIREMENT_LIMIT = 3
DEFAULT_MATCHED_UI_SCREEN_LIMIT = 3
DEFAULT_ADJACENT_UI_SCREEN_LIMIT = 2
REQUIRED_UI_ELEMENT_HINTS = (
    "忘记密码",
    "验证码",
    "提交",
    "下一步",
    "上一步",
    "登录",
    "注册",
    "搜索",
    "支付",
    "结算",
    "加入购物车",
    "保存",
    "取消",
    "确认",
)

TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"


def _dedupe_ints(values: Optional[List[int]]) -> List[int]:
    if not values:
        return []
    result: List[int] = []
    seen = set()
    for value in values:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _safe_json_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _extract_terms(*parts: Any) -> set[str]:
    text = " ".join(str(part or "") for part in parts).lower()
    raw_tokens = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    terms: set[str] = set()
    for token in raw_tokens:
        if len(token) < 2:
            continue
        terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token) and len(token) > 2:
            terms.update(token[i:i + 2] for i in range(len(token) - 1))
    return {term for term in terms if len(term) >= 2}


def _score_terms(terms: set[str], *parts: Any) -> int:
    if not terms:
        return 0
    text = " ".join(_safe_json_text(part) for part in parts).lower()
    return sum(1 for term in terms if term and term in text)


def _warning(code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": detail or {}}


def _test_point_entry(point: TestPoint) -> Dict[str, Any]:
    return {
        "id": point.id,
        "module": point.module,
        "function": _extract_function_from_ai_prompt(point.ai_prompt),
        "point": point.point,
        "priority": point.priority,
        "requirement_id": point.requirement_id,
    }


def _test_point_search_text(points: List[TestPoint]) -> str:
    return " ".join(
        f"{point.module or ''} {point.point or ''} {point.ai_prompt or ''}"
        for point in points
    )


def _requirement_ref(requirement: Requirement) -> Dict[str, Any]:
    return {
        "id": requirement.id,
        "req_no": requirement.req_no,
        "title": requirement.title,
        "status": requirement.status,
        "source_file_id": requirement.source_file_id,
    }


def _screen_ref(screen: UIPrototypeScreen, confidence: str) -> Dict[str, Any]:
    return {
        "id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "confidence": confidence,
        "parse_status": screen.parse_status,
        "element_count": screen.element_count or 0,
    }


def _screen_desc(screen: UIPrototypeScreen, confidence: str = "matched") -> Dict[str, Any]:
    return {
        "screen_id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "parse_status": screen.parse_status,
        "summary": screen.summary or "",
        "element_count": screen.element_count or 0,
        "button_count": screen.button_count or 0,
        "input_count": screen.input_count or 0,
        "description": screen.summary or "",
        "match_confidence": confidence,
    }


def _collect_navigation_screen_ids(screen: UIPrototypeScreen) -> List[int]:
    ids: List[int] = []

    def collect(value: Any) -> None:
        if isinstance(value, int):
            ids.append(value)
        elif isinstance(value, str):
            if value.isdigit():
                ids.append(int(value))
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in {"id", "screen_id", "target", "target_id", "to", "next"}:
                    collect(item)
                elif isinstance(item, (dict, list)):
                    collect(item)

    collect(screen.related_screens)
    collect(screen.navigation_flow)
    return _dedupe_ints(ids)


def _has_flow_intent(text: str) -> bool:
    keywords = ("进入", "跳转", "提交", "返回", "下一步", "上一步", "flow", "next", "submit", "back")
    lower_text = (text or "").lower()
    return any(keyword in lower_text for keyword in keywords)


def _normalize_match_text(value: Any) -> str:
    return re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", _safe_json_text(value)).lower()


def _find_missing_required_ui_terms(search_text: str, ui_specs: List[Dict[str, Any]]) -> List[str]:
    if not search_text or not ui_specs:
        return []
    required_terms = [
        term for term in REQUIRED_UI_ELEMENT_HINTS
        if term.lower() in search_text.lower()
    ]
    if not required_terms:
        return []

    ui_text = _normalize_match_text([
        item.get("ui_spec")
        for item in ui_specs
        if isinstance(item, dict)
    ])
    missing = [
        term for term in required_terms
        if _normalize_match_text(term) not in ui_text
    ]
    return _dedupe_strings(missing)


def _dedupe_strings(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


class ContextBudgetController:
    """Lightweight context budget helper using a deterministic token estimate."""

    def __init__(self, max_tokens: int = DEFAULT_CONTEXT_TOKEN_BUDGET) -> None:
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(value: Any) -> int:
        text = _safe_json_text(value)
        if not text:
            return 0
        ascii_count = sum(1 for ch in text if ord(ch) < 128)
        non_ascii_count = len(text) - ascii_count
        return max(1, ascii_count // 4 + non_ascii_count // 2)

    def trim_text(self, text: str, token_budget: int) -> str:
        if not text or self.estimate_tokens(text) <= token_budget:
            return text or ""
        # Approximate two CJK chars per token. Keep the front matter because it
        # usually contains the requirement title and explicit constraints.
        char_budget = max(200, token_budget * 2)
        return text[:char_budget] + f"\n\n[上下文已按预算裁剪，原始长度 {len(text)} 字符]"


def _trim_requirement_text(
    text: str,
    terms: set[str],
    budget: ContextBudgetController,
    token_budget: int,
) -> tuple[str, bool]:
    if not text:
        return "", False
    if len(text) <= 800:
        return budget.trim_text(text, token_budget), False

    chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[。！？；;\n])\s*", text)
        if chunk and chunk.strip()
    ]
    scored_chunks = []
    for index, chunk in enumerate(chunks):
        score = _score_terms(terms, chunk)
        if score > 0:
            scored_chunks.append((score, index, chunk))

    if not scored_chunks:
        trimmed = budget.trim_text(text, token_budget)
        return trimmed, len(trimmed) < len(text)

    scored_chunks.sort(key=lambda item: (-item[0], item[1]))
    selected_indexes = set()
    for _, index, _ in scored_chunks[:4]:
        selected_indexes.add(index)
        if index > 0:
            selected_indexes.add(index - 1)
        if index + 1 < len(chunks):
            selected_indexes.add(index + 1)

    selected_text = "\n".join(chunks[index] for index in sorted(selected_indexes))
    if len(selected_text) < 500:
        selected_text = "\n".join([selected_text, text[:500]]).strip()
    trimmed = budget.trim_text(selected_text, token_budget)
    return trimmed, True


class ContentSanitizer:
    """
    内容清洗器 - 防止Prompt注入攻击
    对用户输入的内容进行清洗和转义，确保AI输出安全可靠
    """

    INJECTION_PATTERNS = [
        r'```system',
        r'```prompt',
        r'忽略.*指令',
        r'忽略.*规则',
        r'你是一个.*而不是',
        r'你现在是',
        r'/system',
        r'<system>',
        r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容，防止Prompt注入"""
        if not content:
            return ""
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content)
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """清洗内容用于日志记录（更严格的截断）"""
        if not content:
            return ""
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


class TestCaseGenerationBaseMixin:
    """测试用例生成服务 - 基础方法Mixin"""

    def __init__(self, db: Session):
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """获取测试用例生成的上下文信息"""
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

        context = {
            "requirement_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "files_used": [],
            "warnings": [],
            "cache_info": {}
        }

        if requirement_file_ids:
            for file_id in requirement_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "requirement":
                    content = file_record.content or ""
                    if force_refresh or not content:
                        content = await get_file_content(file_id)
                    if content:
                        context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                        context["files_used"].append(file_id)

        if not context["requirement_content"]:
            all_req_files = file_crud.get_project_files_by_type(self.db, project_id, "requirement")
            for file_record in all_req_files:
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_record.id)
                if content:
                    context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                    context["files_used"].append(file_record.id)

        if ui_screen_ids:
            found_screen_ids = set()
            for screen_id in ui_screen_ids:
                screen = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id
                ).first()
                if screen:
                    found_screen_ids.add(screen.id)
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    if not screen.summary and screen.parse_status != "completed":
                        ui_desc["description"] = "该屏幕尚未完成AI解析，仅可基于页面名称和流程顺序生成基础用例"
                        context["warnings"].append(
                            f"屏幕「{screen.screen_name}」尚未完成解析，AI可用的UI元素信息有限"
                        )
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
                else:
                    context["warnings"].append(f"未找到UI屏幕ID: {screen_id}")
            missing_count = len(set(ui_screen_ids) - found_screen_ids)
            if missing_count:
                context["warnings"].append(f"{missing_count}个UI屏幕未被纳入上下文")
        elif ui_file_ids:
            for file_id in ui_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "ui_mockup":
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_id)

                    linked_screens = self.db.query(UIPrototypeScreen).filter(
                        UIPrototypeScreen.project_id == project_id,
                        UIPrototypeScreen.prototype_name == file_record.file_name,
                        UIPrototypeScreen.parse_status == "completed",
                        UIPrototypeScreen.ui_spec.isnot(None)
                    ).all()
                    for screen in linked_screens:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })

        if not context["ui_descriptions"] and not context["ui_specs"]:
            screens_with_spec = self.db.query(UIPrototypeScreen).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.parse_status == "completed",
                UIPrototypeScreen.ui_spec.isnot(None)
            ).order_by(UIPrototypeScreen.screen_order).all()

            if screens_with_spec:
                for screen in screens_with_spec:
                    ui_desc = {
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name,
                        "parse_status": screen.parse_status,
                        "summary": screen.summary or "",
                        "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0,
                        "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
            else:
                all_ui_files = file_crud.get_project_files_by_type(self.db, project_id, "ui_mockup")
                for file_record in all_ui_files:
                    ui_desc = {
                        "file_name": file_record.file_name,
                        "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_record.id)

        if test_point_ids:
            for point_id in test_point_ids:
                point = test_point_crud.get_test_point_by_id(self.db, point_id, project_id)
                if point:
                    context["test_points"].append({
                        "id": point.id,
                        "module": point.module,
                        "function": _extract_function_from_ai_prompt(point.ai_prompt),
                        "point": point.point,
                        "priority": point.priority
                    })
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
            all_points = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).all()
            total_count = len(all_points)
            all_points.sort(
                key=lambda point: (
                    point.id in covered_test_point_ids,
                    point.priority or 99,
                    point.id,
                )
            )
            page_points = all_points[skip: skip + page_limit]

            for point in page_points:
                context["test_points"].append({
                    "id": point.id,
                    "module": point.module,
                    "function": _extract_function_from_ai_prompt(point.ai_prompt),
                    "point": point.point,
                    "priority": point.priority
                })

            context["pagination"] = {
                "page": test_point_page,
                "page_size": len(page_points),
                "total": total_count,
                "has_more": (skip + page_limit) < total_count,
                "uncovered_first": True,
                "covered_test_point_count": len(covered_test_point_ids)
            }

        return context

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
        requirement_file_ids = _dedupe_ints(requirement_file_ids)
        ui_file_ids = _dedupe_ints(ui_file_ids)
        ui_screen_ids = _dedupe_ints(ui_screen_ids)
        test_point_ids = _dedupe_ints(test_point_ids)
        budget = ContextBudgetController()
        context: Dict[str, Any] = {
            "requirement_content": "",
            "ui_descriptions": [],
            "ui_specs": [],
            "test_points": [],
            "files_used": [],
            "warnings": [],
            "cache_info": {},
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

        if requirement_file_ids:
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

        if not context["requirement_content"]:
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

        if ui_screen_ids:
            found_screen_ids = set()
            for screen_id in ui_screen_ids:
                screen = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id,
                ).first()
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
        elif ui_file_ids:
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

        if not context["ui_descriptions"] and not context["ui_specs"]:
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

        missing_required_ui_terms = _find_missing_required_ui_terms(search_text, context["ui_specs"])
        if missing_required_ui_terms:
            context["warnings"].append(_warning(
                "UI_REQUIRED_ELEMENT_MISSING",
                "当前页面解析数据可能缺少测试点所需的UI元素",
                {"missing_terms": missing_required_ui_terms},
            ))

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

        return context

    def enrich_context_with_trust_and_scoring(
        self,
        context: Dict[str, Any],
        project_id: int,
        history_case_ids: list[int] | None = None,
        history_limit: int = 10,
    ) -> None:
        from app.api.v1.endpoints.test_case_ai_generate._context import (
            _extract_terms, _score_terms, _assess_history_trust, _summarize_history_case,
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
            query_terms = _extract_terms(*search_terms) if search_terms else set()
            all_cases = self.db.query(TestCase).filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
                TestCase.lifecycle_status.notin_(['archived', 'deprecated']),
            ).order_by(TestCase.id).all()
            if query_terms:
                scored_cases = []
                for case in all_cases:
                    score = _score_terms(
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

    async def _get_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Optional[str]:
        """获取文件内容（支持自动提取）"""
        if file.content and file.extract_status == 'completed' and not force_refresh:
            return file.content
        if not file.content or file.extract_status in ['pending', 'failed']:
            from app.services.file_content_extractor import FileContentExtractor
            extractor = FileContentExtractor(self.db)
            result = await extractor.extract_file_content(file, force_refresh)
            if result.get("success"):
                return result.get("content") or ""
        return file.content

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
