"""业务领域 Few-shot 示例模块（Task 7）。

从项目已有高质量用例中提取领域示例，注入 Prompt 提升生成质量。
按 case_category 分类提取：1 条 positive + 1 条 exception + 1 条 boundary，
不足 3 类时返回 None（由调用方保留通用示例作为 fallback）。

Task 13: P2-2 重复查询消除 — 改为调用 case_quality.history_cache 共享缓存层，
避免同项目多次调用重复查询 DB。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_DOMAIN_EXAMPLE_MIN_SCORE = 80.0
# spec L110-119 要求 positive/exception/boundary 各 1 条
_DOMAIN_REQUIRED_CATEGORIES = ("positive", "exception", "boundary")
# 候选池上限：每类最多取质量分最高的 1 条，候选池需足够大以保证三类齐全
_DOMAIN_CANDIDATE_LIMIT = 15


def get_domain_examples(
    db: Optional[Session], project_id: Optional[int]
) -> Optional[str]:
    """从项目已有高质量用例中提取领域 Few-shot 示例文本。

    按 case_category 分类提取：positive/exception/boundary 各 1 条。
    通过 history_cache 共享缓存层获取历史高质量用例，同项目多次调用
    只查询一次 DB，消除重复查询。

    Args:
        db: 数据库会话，为 None 时返回 None。
        project_id: 项目ID，为 None 时返回 None。

    Returns:
        格式化的领域示例文本；当项目无历史用例或三类用例不齐全时返回 None
        （由调用方保留通用"登录"示例作为 fallback）。
    """
    if db is None or project_id is None:
        return None
    try:
        from app.services.case_quality.history_cache import (
            get_history_cases_for_project,
        )
        candidates = get_history_cases_for_project(
            db,
            project_id,
            min_score=_DOMAIN_EXAMPLE_MIN_SCORE,
            limit=_DOMAIN_CANDIDATE_LIMIT,
        )
    except Exception as e:
        logger.warning(f"加载领域示例失败: {e}")
        return None

    if not candidates:
        return None

    # 按 case_category 分组，每类取质量分最高的 1 条
    selected: Dict[str, Dict[str, Any]] = {}
    for case in candidates:
        category = case.get("case_category") or ""
        if category in _DOMAIN_REQUIRED_CATEGORIES and category not in selected:
            selected[category] = case
        if len(selected) == len(_DOMAIN_REQUIRED_CATEGORIES):
            break

    # spec L119 要求"不足3条时保留通用示例"，即三类不齐全时返回 None
    if len(selected) < len(_DOMAIN_REQUIRED_CATEGORIES):
        logger.info(
            f"项目 {project_id} 领域示例不齐全（{len(selected)}/3 类），"
            f"保留通用示例"
        )
        return None

    sections: List[str] = ["## 同项目高质量用例参考（Few-shot 示例）："]
    for category in _DOMAIN_REQUIRED_CATEGORIES:
        case = selected[category]
        steps = _safe_parse_steps(case.get("steps_json"))
        # 防御性：steps_json 来源是 JSON 反序列化结果，元素可能是 dict/str/None；
        # action 字段也可能为 None（dict 中键存在但值为 None），此时 .get('action', '')
        # 返回 None 而非默认空串，None[:30] 会抛 TypeError。统一用 str() 兜底。
        steps_summary = " → ".join(
            (str(s.get("action") or "") if isinstance(s, dict) else str(s))[:30]
            for s in steps[:4]
        )
        sections.append(
            f"- [{category}] 标题: {case.get('title', '')}\n"
            f"  前置条件: {(case.get('precondition') or '')[:60]}\n"
            f"  步骤摘要: {steps_summary}\n"
            f"  预期结果: {(case.get('expected_result') or '')[:60]}\n"
            f"  分类: {case.get('case_category') or 'N/A'} | "
            f"质量分: {case.get('prior_quality_score')}"
        )
    sections.append(
        "请参考以上高质量用例的描述粒度和结构，但不要照搬内容。"
    )
    return "\n".join(sections)


def _safe_parse_steps(steps_json: Any) -> List[Dict[str, Any]]:
    """安全解析 steps_json 字段，解析失败时返回空列表。"""
    if not steps_json:
        return []
    if isinstance(steps_json, list):
        return steps_json
    if isinstance(steps_json, str):
        try:
            parsed = json.loads(steps_json)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []
