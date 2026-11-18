"""历史用例检索、信任度评估与摘要（从 endpoints/test_case_ai_generate/_context.py 下沉）。

纯计算 + 只读 ORM 查询，不含 HTTP 语义；供端点层与
`_history_scoring_mixin` 共用。保持原函数名以兼容既有调用点与测试 patch 目标。
"""

import json
import re
from datetime import datetime, UTC
from typing import Any

from sqlalchemy.orm import Session

from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.test_point import TestPoint

DEFAULT_HISTORY_CASE_LIMIT = 10


def _safe_text(value: Any) -> str:
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
            terms.update(token[i : i + 2] for i in range(len(token) - 1))
    return {term for term in terms if len(term) >= 2}


def _score_terms(terms: set[str], *parts: Any) -> int:
    if not terms:
        return 0
    text = " ".join(_safe_text(part) for part in parts).lower()
    return sum(1 for term in terms if term in text)


def _infer_design_tag(case: TestCase, steps: Any) -> str:
    text = " ".join(
        [
            case.title or "",
            case.summary or "",
            case.expected_result or "",
            _safe_text(steps),
        ]
    )
    if any(keyword in text for keyword in ("空", "为空", "必填", "超长", "最大", "最小", "边界", "长度")):
        return "边界值"
    if any(keyword in text for keyword in ("失败", "错误", "异常", "无权限", "断网", "超时", "锁定")):
        return "异常流程"
    if isinstance(steps, list) and len(steps) >= 5:
        return "组合场景"
    return "常规流程"


def _assess_history_trust(
    case: TestCase,
    current_requirement_ids: set[int],
    current_ui_screen_ids: set[int],
    db: Session,
) -> tuple[str, str]:
    staleness_reasons: list[str] = []

    if case.test_point_id:
        tp = db.query(TestPoint).filter(TestPoint.id == case.test_point_id).first()
        if tp and tp.requirement_id and tp.requirement_id not in current_requirement_ids:
            staleness_reasons.append("requirement_mismatch")
        if tp and tp.requirement_id:
            req = db.query(Requirement).filter(Requirement.id == tp.requirement_id).first()
            if (
                req
                and isinstance(req.update_time, datetime)
                and isinstance(case.update_time, datetime)
                and req.update_time > case.update_time
            ):
                staleness_reasons.append("requirement_newer_than_case")

    if isinstance(case.update_time, datetime):
        now = datetime.now(UTC)
        case_update = case.update_time.replace(tzinfo=UTC) if case.update_time.tzinfo is None else case.update_time
        case_age_days = (now - case_update).days
        if case_age_days > 90:
            staleness_reasons.append("case_older_than_90_days")

    if not case.summary and not case.summary_version:
        staleness_reasons.append("summary_missing")

    if current_ui_screen_ids:
        try:
            case_ui_screen_ids = {s.id for s in case.linked_ui_screens} if case.linked_ui_screens else set()
        except Exception:
            case_ui_screen_ids = set()
        if case_ui_screen_ids and not case_ui_screen_ids.intersection(current_ui_screen_ids):
            staleness_reasons.append("ui_screen_mismatch")

    if staleness_reasons:
        if "requirement_mismatch" in staleness_reasons:
            return "low", "HISTORY_REQUIREMENT_MISMATCH"
        if any(r in staleness_reasons for r in ("requirement_newer_than_case", "case_older_than_90_days")):
            return "medium", "HISTORY_POTENTIALLY_STALE"
        return "medium", ",".join(staleness_reasons)

    return "high", ""


def _summarize_history_case(
    case: TestCase,
    similarity: float | None = None,
    trust_level: str = "high",
    staleness_reason: str = "",
) -> dict[str, Any]:
    steps = case.steps_json or []
    steps_summary = ""
    if isinstance(steps, list) and steps:
        actions = [s.get("action", s.get("description", "")) for s in steps[:3] if isinstance(s, dict)]
        steps_summary = " -> ".join(a for a in actions if a)
    summary = (case.summary or steps_summary or case.expected_result or "")[:150]
    result = {
        "id": case.id,
        "case_no": case.case_no,
        "module": case.module or "",
        "title": case.title,
        "summary": summary,
        "covered_scene": summary,
        "design_tag": _infer_design_tag(case, steps),
        "trust_level": trust_level,
        "staleness_reason": staleness_reason,
    }
    if similarity is not None:
        result["similarity"] = round(similarity, 2)
    return result
