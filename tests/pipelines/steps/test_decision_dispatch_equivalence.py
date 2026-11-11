"""R3-2 等价性安全网：DecisionDispatch 8 个 action 的输出契约。

在规则外置（`_rules.py` + 分派表）重构**之前**用本文件锁定行为，
重构后必须逐条仍通过。断言只覆盖对外可见契约：

    - `generation_tasks` 的 task_type 序列
    - `deprecation_suggestions` 条数
    - `stats` 各计数增量
    - 分支特有字段（`need_locator_fix` / `skip_reason`）
"""
from unittest.mock import MagicMock

import pytest

from app.pipelines.steps.decision_dispatch import DecisionDispatch


def _make_ctx(action: str, budget_ok: bool = True):
    """构造单条裁决的 mock 上下文。"""
    verdict = {"action": action, "case_id": 100, "reason": f"reason_{action}"}
    if action == "add_new":
        verdict["candidate_index"] = 0

    ctx = MagicMock()
    ctx.get_artifact = MagicMock(side_effect=lambda kind: {
        "merged_verdicts": {"project_id": 1, "verdicts": [verdict], "total_count": 1},
        "aligned_testpoints": None,
        "history_fingerprints": {
            "fingerprints": [{"case_id": 100, "title": "用例100", "module": "模块"}]
        },
        "scenario_candidates": {
            "candidates": [{"description": "候选0", "module": "模块0", "priority": 1}]
        },
    }.get(kind))
    ctx.check_budget = MagicMock(return_value=budget_ok)
    ctx.iteration_id = 1
    return ctx


def _execute(step: DecisionDispatch, action: str):
    return step.execute(_make_ctx(action))


# action → (期望 task_type 序列, 期望 deprecation 数, 期望 stats 增量)
EXPECTED = [
    ("keep", [], 0, {"keep_count": 1}),
    ("deprecate", [], 1, {"deprecate_count": 1}),
    ("needs_modify", ["modify"], 0, {"modify_count": 1}),
    ("locator_broken", ["locator_fix"], 0, {"locator_fix_count": 1}),
    ("locator_and_modify", ["modify"], 0, {"modify_count": 1}),
    ("add_new", ["create"], 0, {"create_count": 1}),
    ("conflict", ["skip"], 0, {"skip_count": 1, "conflict_count": 1}),
    ("pending_review", ["skip"], 0, {"skip_count": 1}),
]

_ZERO_STATS = {
    "keep_count": 0,
    "modify_count": 0,
    "create_count": 0,
    "locator_fix_count": 0,
    "deprecate_count": 0,
    "skip_count": 0,
    "conflict_count": 0,
}


@pytest.mark.parametrize("action,task_types,deps,stats_delta", EXPECTED)
def test_action_output_contract(action, task_types, deps, stats_delta):
    """8 个 action 的产物结构与计数契约。"""
    step = DecisionDispatch()

    result = step.execute(_make_ctx(action))

    assert result.success is True
    payload = result.artifact_payload
    assert [t["task_type"] for t in payload["generation_tasks"]] == task_types
    assert len(payload["deprecation_suggestions"]) == deps

    expected_stats = dict(_ZERO_STATS)
    expected_stats.update(stats_delta)
    assert payload["stats"] == expected_stats
    assert payload["total_tasks"] == len(task_types)
    assert payload["total_deprecations"] == deps


def test_locator_and_modify_sets_locator_flag():
    """locator_and_modify 必须带 need_locator_fix=True（区别于 needs_modify）。"""
    payload = DecisionDispatch().execute(_make_ctx("locator_and_modify")).artifact_payload

    assert payload["generation_tasks"][0].get("need_locator_fix") is True

    payload = DecisionDispatch().execute(_make_ctx("needs_modify")).artifact_payload
    assert "need_locator_fix" not in payload["generation_tasks"][0]


def test_conflict_skip_reason_is_prefixed():
    """conflict 的 skip_reason 带「冲突:」前缀，供下游审核记录识别。"""
    payload = DecisionDispatch().execute(_make_ctx("conflict")).artifact_payload

    assert payload["generation_tasks"][0]["skip_reason"] == "冲突: reason_conflict"


def test_pending_review_skip_reason_is_deferred():
    """pending_review 使用固定延后文案。"""
    payload = DecisionDispatch().execute(_make_ctx("pending_review")).artifact_payload

    assert payload["generation_tasks"][0]["skip_reason"] == "pending_review deferred"


def test_unknown_action_counts_as_skip():
    """未知 action 只累加 skip_count，不产任务。"""
    payload = DecisionDispatch().execute(_make_ctx("__unknown__")).artifact_payload

    assert payload["generation_tasks"] == []
    assert payload["stats"]["skip_count"] == 1


def test_mixed_verdicts_keep_order():
    """混合裁决保持输入顺序，统计值可累加。"""
    step = DecisionDispatch()
    ctx = MagicMock()
    ctx.get_artifact = MagicMock(side_effect=lambda kind: {
        "merged_verdicts": {
            "project_id": 1,
            "verdicts": [
                {"action": "keep", "case_id": 1},
                {"action": "needs_modify", "case_id": 2, "reason": "r2"},
                {"action": "add_new", "candidate_index": 0, "reason": "r3"},
                {"action": "deprecate", "case_id": 4, "reason": "r4"},
            ],
            "total_count": 4,
        },
        "aligned_testpoints": None,
        "history_fingerprints": {"fingerprints": []},
        "scenario_candidates": {"candidates": [{"description": "c0"}]},
    }.get(kind))
    ctx.check_budget = MagicMock(return_value=True)
    ctx.iteration_id = 1

    payload = step.execute(ctx).artifact_payload

    assert [t["task_type"] for t in payload["generation_tasks"]] == ["modify", "create"]
    assert payload["stats"]["keep_count"] == 1
    assert payload["stats"]["modify_count"] == 1
    assert payload["stats"]["create_count"] == 1
    assert payload["stats"]["deprecate_count"] == 1
    assert len(payload["deprecation_suggestions"]) == 1


def test_budget_exhausted_pauses():
    """预算耗尽时暂停并要求确认，已生成任务保留。"""
    step = DecisionDispatch()
    ctx = _make_ctx("needs_modify", budget_ok=False)

    result = step.execute(ctx)

    assert result.success is True
    assert result.pause_for_confirmation is True
    assert result.artifact_payload["generation_tasks"] == []
