"""DecisionDispatch 裁决动作规则表（R3-2 规则外置）。

把 `action → (任务构造器, stats 计数键)` 的映射从 `_step.py` 的 if/elif 链
外置为数据表：新增/调整动作只需改本文件，分派逻辑保持不变。

规则字段：
    kind    : 动作语义标签（用于日志与文档，不参与分派）
    handler : 构造器，统一签名 `(**kw) -> (task | None, deprecation | None)`
    stats   : 命中该动作时需要累加的 stats 键（顺序无关）
"""
from typing import Any
from collections.abc import Callable

from app.pipelines.steps.decision_dispatch._builders import (
    _build_create_task,
    _build_deprecation_suggestion,
    _build_locator_fix_task,
    _build_modify_task,
    _build_skip_task,
)

HandlerReturn = tuple[dict[str, Any] | None, dict[str, Any] | None]
Handler = Callable[..., HandlerReturn]


def _no_task(**_kw: Any) -> HandlerReturn:
    """keep：仅计数，不产生任务。"""
    return None, None


def _make_deprecation(**_kw: Any) -> HandlerReturn:
    return None, _build_deprecation_suggestion(
        case_id=_kw["case_id"],
        reason=_kw["reason"],
        fp_by_case_id=_kw["fp_by_case_id"],
    )


def _make_modify(**_kw: Any) -> HandlerReturn:
    return _build_modify_task(
        case_id=_kw["case_id"],
        reason=_kw["reason"],
        fp_by_case_id=_kw["fp_by_case_id"],
        need_locator_fix=False,
        db=_kw["db"],
    ), None


def _make_locator_fix(**_kw: Any) -> HandlerReturn:
    return _build_locator_fix_task(
        case_id=_kw["case_id"],
        reason=_kw["reason"],
        fp_by_case_id=_kw["fp_by_case_id"],
        db=_kw["db"],
    ), None


def _make_modify_with_locator(**_kw: Any) -> HandlerReturn:
    return _build_modify_task(
        case_id=_kw["case_id"],
        reason=_kw["reason"],
        fp_by_case_id=_kw["fp_by_case_id"],
        need_locator_fix=True,
        db=_kw["db"],
    ), None


def _make_create(**_kw: Any) -> HandlerReturn:
    return _build_create_task(
        candidate_index=_kw["candidate_index"],
        cands=_kw["cands"],
        reason=_kw["reason"],
    ), None


def _make_conflict_skip(**_kw: Any) -> HandlerReturn:
    reason = _kw["reason"]
    return _build_skip_task(
        case_id=_kw["case_id"],
        skip_reason=f"冲突: {reason}" if reason else "合并冲突，需人工决策",
        fp_by_case_id=_kw["fp_by_case_id"],
        db=_kw["db"],
    ), None


def _make_pending_skip(**_kw: Any) -> HandlerReturn:
    return _build_skip_task(
        case_id=_kw["case_id"],
        skip_reason="pending_review deferred",
        fp_by_case_id=_kw["fp_by_case_id"],
        db=_kw["db"],
    ), None


ACTION_RULES: dict[str, dict[str, Any]] = {
    "keep": {"kind": "keep", "handler": _no_task, "stats": ("keep_count",)},
    "deprecate": {
        "kind": "deprecate", "handler": _make_deprecation, "stats": ("deprecate_count",),
    },
    "needs_modify": {
        "kind": "modify", "handler": _make_modify, "stats": ("modify_count",),
    },
    "locator_broken": {
        "kind": "locator_fix", "handler": _make_locator_fix, "stats": ("locator_fix_count",),
    },
    "locator_and_modify": {
        "kind": "modify_locator", "handler": _make_modify_with_locator,
        "stats": ("modify_count",),
    },
    "add_new": {"kind": "create", "handler": _make_create, "stats": ("create_count",)},
    "conflict": {
        "kind": "conflict", "handler": _make_conflict_skip,
        "stats": ("skip_count", "conflict_count"),
    },
    "pending_review": {
        "kind": "pending_review", "handler": _make_pending_skip, "stats": ("skip_count",),
    },
}


def get_action_rule(action: str) -> dict[str, Any] | None:
    """按 action 取规则；未知 action 返回 None（由调用方计 skip）。"""
    return ACTION_RULES.get(action)


__all__ = ["ACTION_RULES", "get_action_rule"]
