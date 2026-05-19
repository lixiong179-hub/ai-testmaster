from typing import Any, Dict, List, Optional

from loguru import logger


def _resolve_original_case(
    case_id: Optional[int],
    fp_by_case_id: Dict[int, Dict[str, Any]],
    db: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    if case_id is None:
        return None

    fp = fp_by_case_id.get(case_id)
    if fp is None:
        return None

    original: Dict[str, Any] = {
        "title": fp.get("title", ""),
        "module": fp.get("module", ""),
        "steps_json": None,
        "precondition": "",
        "expected_result": "",
    }

    if db is not None:
        try:
            from app.models.test_case import TestCase as _TestCase

            db_case = db.query(_TestCase).filter(_TestCase.id == case_id).first()
            if db_case is not None:
                original["steps_json"] = _safe_json(db_case.steps_json)
                original["precondition"] = db_case.precondition or ""
                original["expected_result"] = db_case.expected_result or ""
        except Exception as e:
            logger.debug("从 DB 补全原始用例信息失败 case_id={}: {}", case_id, e)

    return original


def _safe_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        import json as _json
        try:
            return _json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _build_modify_task(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
    need_locator_fix: bool,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    task_id = f"modify_{case_id}" if case_id is not None else "modify_unknown"
    task: Dict[str, Any] = {
        "task_type": "modify",
        "task_id": task_id,
        "case_id": case_id,
        "original_case": _resolve_original_case(case_id, fp_by_case_id, db=db),
        "change_type": "modified",
        "modification_hint": reason or "需修改",
    }
    if need_locator_fix:
        task["need_locator_fix"] = True
    return task


def _build_locator_fix_task(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    task_id = f"locator_{case_id}" if case_id is not None else "locator_unknown"
    return {
        "task_type": "locator_fix",
        "task_id": task_id,
        "case_id": case_id,
        "original_case": _resolve_original_case(case_id, fp_by_case_id, db=db),
        "change_type": "locator_fix",
        "locator_hint": reason or "元素定位变更",
    }


def _build_create_task(
    candidate_index: Optional[int],
    cands: List[Dict[str, Any]],
    reason: str,
) -> Dict[str, Any]:
    if candidate_index is not None and 0 <= candidate_index < len(cands):
        cand = cands[candidate_index]
    else:
        cand = {}

    task_id = f"create_{candidate_index}" if candidate_index is not None else "create_unknown"
    return {
        "task_type": "create",
        "task_id": task_id,
        "candidate_index": candidate_index,
        "candidate_description": cand.get("description", ""),
        "candidate_module": cand.get("module", ""),
        "candidate_priority": cand.get("priority", 3),
        "candidate_reason": cand.get("reason", reason or "新增场景"),
        "change_type": "added",
    }


def _build_skip_task(
    case_id: Optional[int],
    skip_reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    task_id = f"skip_{case_id}" if case_id is not None else "skip_unknown"
    task: Dict[str, Any] = {
        "task_type": "skip",
        "task_id": task_id,
        "case_id": case_id,
        "skip_reason": skip_reason,
    }
    if case_id is not None:
        original = _resolve_original_case(case_id, fp_by_case_id, db=db)
        if original:
            task["original_case"] = original
    return task


def _build_deprecation_suggestion(
    case_id: Optional[int],
    reason: str,
    fp_by_case_id: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    title = ""
    if case_id is not None:
        fp = fp_by_case_id.get(case_id)
        if fp is not None:
            title = fp.get("title", "")
    return {
        "case_id": case_id,
        "title": title,
        "deprecate_reason": reason or "建议废弃",
    }


def _validate_task_field(task: Dict[str, Any]) -> bool:
    return isinstance(task, dict) and "task_type" in task
