"""test_case_generation - 基础辅助函数、常量、内容清洗、实体引用与测试点加载。

合并自 _base_helpers.py + _content_sanitizer.py + _entity_refs.py + test_point_loader.py，
提供模块级纯函数、常量与 ContextBudgetController / ContentSanitizer 工具类。

continuous_scorer.py 因被外部模块引用保留独立文件，本模块 re-export compute_continuous_score。
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.crud import test_point as test_point_crud
from app.models.project import ProjectFile
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.ui_prototype import UIPrototypeScreen


# ── 分页与上下文预算常量 ──
DEFAULT_CONTEXT_TOKEN_BUDGET = 5000
DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500
DEFAULT_MATCHED_REQUIREMENT_LIMIT = 3
DEFAULT_MATCHED_UI_SCREEN_LIMIT = 3
DEFAULT_ADJACENT_UI_SCREEN_LIMIT = 2

# ── 用例类型常量（执行方式） ──
TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"

# UI 元素关键词提示：检测需求描述中提到的关键 UI 元素
REQUIRED_UI_ELEMENT_HINTS = (
    "忘记密码", "验证码", "提交", "下一步", "上一步", "登录", "注册",
    "搜索", "支付", "结算", "加入购物车", "保存", "取消", "确认",
)

# 需求文档操作动词集合，用于判定需求描述是否具备可执行的操作意图
REQUIREMENT_ACTION_VERBS = (
    "点击", "输入", "提交", "选择", "查看", "验证", "确认", "核对",
    "观察", "获取", "填写", "勾选", "切换", "按下", "长按", "等待",
    "打开", "进入", "返回",
)
REQUIREMENT_MIN_CHAR_COUNT = 50


# ── 内容清洗器（防 Prompt 注入） ──
class ContentSanitizer:
    """内容清洗器 - 防止 Prompt 注入攻击，对用户输入清洗转义。"""

    INJECTION_PATTERNS = [
        r'```system', r'```prompt', r'忽略.*指令', r'忽略.*规则',
        r'你是一个.*而不是', r'你现在是', r'/system', r'<system>', r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容防止 Prompt 注入。空串原样返回，控制字符剥离，超长截断标注。"""
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
        """清洗内容用于日志记录（更严格截断，单行化）。"""
        if not content:
            return ""
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


# ── 实体引用构造 ──
def _test_point_entry(point: TestPoint) -> Dict[str, Any]:
    """构造测试点引用字典，function 从 ai_prompt JSON 提取。"""
    return {
        "id": point.id,
        "module": point.module,
        "function": _extract_function_from_ai_prompt(point.ai_prompt),
        "point": point.point,
        "priority": point.priority,
        "requirement_id": point.requirement_id,
    }


def _test_point_search_text(points: List[TestPoint]) -> str:
    """拼接测试点的 module/point/ai_prompt 文本，供关键词提取。"""
    return " ".join(
        f"{point.module or ''} {point.point or ''} {point.ai_prompt or ''}"
        for point in points
    )


def _requirement_ref(requirement: Requirement) -> Dict[str, Any]:
    """构造需求引用字典。"""
    return {
        "id": requirement.id,
        "req_no": requirement.req_no,
        "title": requirement.title,
        "status": requirement.status,
        "source_file_id": requirement.source_file_id,
    }


def _screen_ref(screen: UIPrototypeScreen, confidence: str) -> Dict[str, Any]:
    """构造 UI 屏幕引用字典。"""
    return {
        "id": screen.id,
        "screen_name": screen.screen_name,
        "prototype_name": screen.prototype_name,
        "confidence": confidence,
        "parse_status": screen.parse_status,
        "element_count": screen.element_count or 0,
    }


def _screen_desc(screen: UIPrototypeScreen, confidence: str = "matched") -> Dict[str, Any]:
    """构造 UI 屏幕描述字典（含元素统计）。"""
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
    """递归收集屏幕的 related_screens/navigation_flow 中的屏幕 ID。"""
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


def _dedupe_ints(values: List[int]) -> List[int]:
    """整数去重保序。"""
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


def _dedupe_strings(values: List[str]) -> List[str]:
    """字符串去重保序，过滤空值。"""
    result: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


# ── 文本处理与需求质量评估 ──
def _safe_json_text(value: Any) -> str:
    """将任意值转为字符串，dict/list 转 JSON 字符串。"""
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _extract_terms(*parts: Any) -> set[str]:
    """从多个文本片段提取搜索词集合（中文按 2-gram，英文按 token）。"""
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
    """计算 terms 在 parts 文本中的命中数。"""
    if not terms:
        return 0
    text = " ".join(_safe_json_text(part) for part in parts).lower()
    return sum(1 for term in terms if term and term in text)


def _warning(code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """构造警告字典。"""
    return {"code": code, "message": message, "detail": detail or {}}


def _assess_requirement_quality(
    requirement_text: str,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """评估需求文档质量等级并给出警告。

    质量等级：
        - insufficient: 文本过短（< REQUIREMENT_MIN_CHAR_COUNT）
        - vague: 文本足够长但缺乏操作动词
        - sufficient: 文本足够长且包含操作动词
    """
    text = requirement_text or ""
    char_count = len(text)
    has_action_verb = any(verb in text for verb in REQUIREMENT_ACTION_VERBS)
    if char_count < REQUIREMENT_MIN_CHAR_COUNT:
        return ("insufficient", None)
    if not has_action_verb:
        return (
            "vague",
            {
                "code": "REQUIREMENT_VAGUE",
                "severity": "medium",
                "message": "需求文档有内容但缺乏操作动词，请保守生成可执行步骤",
            },
        )
    return ("sufficient", None)


def _has_flow_intent(text: str) -> bool:
    """检测文本是否包含流程跳转意图。"""
    keywords = ("进入", "跳转", "提交", "返回", "下一步", "上一步", "flow", "next", "submit", "back")
    lower_text = (text or "").lower()
    return any(keyword in lower_text for keyword in keywords)


def _normalize_match_text(value: Any) -> str:
    """归一化文本用于匹配：移除标点空白并小写。"""
    return re.sub(r"[\s【】「」\"'`<>《》:：,，。；;、\[\]()（）]", "", _safe_json_text(value)).lower()


def _find_missing_required_ui_terms(search_text: str, ui_specs: List[Dict[str, Any]]) -> List[str]:
    """检查 UI 元素是否覆盖测试点所需关键词，返回缺失词列表。"""
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


# ── 上下文预算控制器 ──
class ContextBudgetController:
    """基于确定性 token 估算的上下文预算控制器。"""

    def __init__(self, max_tokens: int = DEFAULT_CONTEXT_TOKEN_BUDGET) -> None:
        self.max_tokens = max_tokens

    @staticmethod
    def estimate_tokens(value: Any) -> int:
        """估算文本 token 数（ASCII 4字符/token，非 ASCII 2字符/token）。"""
        text = _safe_json_text(value)
        if not text:
            return 0
        ascii_count = sum(1 for ch in text if ord(ch) < 128)
        non_ascii_count = len(text) - ascii_count
        return max(1, ascii_count // 4 + non_ascii_count // 2)

    def trim_text(self, text: str, token_budget: int) -> str:
        """按 token 预算裁剪文本，保留前部（含标题与约束）。"""
        if not text or self.estimate_tokens(text) <= token_budget:
            return text or ""
        char_budget = max(200, token_budget * 2)
        return text[:char_budget] + f"\n\n[上下文已按预算裁剪，原始长度 {len(text)} 字符]"


def _trim_requirement_text(
    text: str,
    terms: set[str],
    budget: ContextBudgetController,
    token_budget: int,
) -> Tuple[str, bool]:
    """按关键词相关性裁剪需求文本，保留高分段落及相邻上下文。"""
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


# ── 测试点加载 ──
def load_test_points(
    db: Session,
    project_id: int,
    test_point_ids: Optional[List[int]] = None,
    page: int = 1,
    page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """加载测试点数据。

    加载策略：
        1. 指定 test_point_ids -> 加载指定测试点
        2. 未指定 -> 分页查询项目测试点（未覆盖优先排序）
    """
    test_points: List[Dict[str, Any]] = []
    pagination: Optional[Dict[str, Any]] = None

    if test_point_ids:
        for point_id in test_point_ids:
            point = test_point_crud.get_test_point_by_id(db, point_id, project_id)
            if point:
                function = _extract_function_from_ai_prompt(point.ai_prompt)
                test_points.append({
                    "id": point.id, "module": point.module,
                    "function": function,
                    "point": point.point, "priority": point.priority,
                })
    else:
        skip = (page - 1) * page_size
        page_limit = min(page_size, MAX_TEST_POINT_PAGE_SIZE)
        covered_test_point_ids = {
            row[0]
            for row in db.query(TestCase.test_point_id)
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
        all_points = db.query(TestPoint).filter(
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
            function = _extract_function_from_ai_prompt(point.ai_prompt)
            test_points.append({
                "id": point.id, "module": point.module,
                "function": function,
                "point": point.point, "priority": point.priority,
            })
        pagination = {
            "page": page, "page_size": len(page_points),
            "total": total_count, "has_more": (skip + page_limit) < total_count,
            "uncovered_first": True,
            "covered_test_point_count": len(covered_test_point_ids),
        }

    return test_points, pagination


def _extract_function_from_ai_prompt(ai_prompt: Optional[str]) -> str:
    """从 ai_prompt JSON 字符串提取 function 字段，失败返回空串。"""
    if not ai_prompt:
        return ""
    try:
        data = json.loads(ai_prompt)
        if isinstance(data, dict):
            return str(data.get('function', '') or '')
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return ""


async def get_file_content_helper(
    db: Session,
    file: ProjectFile,
    force_refresh: bool = False,
) -> Optional[str]:
    """获取文件内容，支持缓存和强制刷新。

    策略：
        1. 已提取完成且不强制刷新 -> 返回缓存
        2. 内容为空或状态 pending/failed -> 重新提取
        3. 提取失败 -> 返回现有内容
    """
    if file.content and file.extract_status == 'completed' and not force_refresh:
        return file.content
    if not file.content or file.extract_status in ['pending', 'failed']:
        from app.services.file_content_extractor import FileContentExtractor
        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(file, force_refresh)
        if result.get("success"):
            return result.get("content") or ""
    return file.content


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
