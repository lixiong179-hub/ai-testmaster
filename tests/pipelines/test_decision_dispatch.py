"""T1 DecisionDispatch 单元测试

覆盖场景:
    - 正常流程: KEEP/NEEDS_MODIFY/ADD_NEW/DEPRECATE/CONFLICT/PENDING_REVIEW/LOCATOR_BROKEN
    - 空 verdicts 降级
    - 预算耗尽暂停
    - fallback 降级路径
    - validate_output 校验
    - 辅助函数: _build_modify_task / _build_create_task / _build_skip_task / _build_deprecation_suggestion
"""
import pytest
from unittest.mock import MagicMock, patch

from app.pipelines.steps.decision_dispatch import DecisionDispatch
from app.pipelines.steps.decision_dispatch._builders import (
    _build_modify_task,
    _build_create_task,
    _build_skip_task,
    _build_deprecation_suggestion,
    _validate_task_field,
)
from app.pipelines.base import StepResult


# ── Fixtures ──


def _make_ctx(merged_verdicts=None, aligned=None, fingerprints=None, candidates=None, budget_ok=True):
    """构造 mock PipelineContext。"""
    ctx = MagicMock()
    ctx.get_artifact = MagicMock(side_effect=lambda kind: {
        "merged_verdicts": merged_verdicts,
        "aligned_testpoints": aligned,
        "history_fingerprints": fingerprints,
        "scenario_candidates": candidates,
    }.get(kind))
    ctx.check_budget = MagicMock(return_value=budget_ok)
    ctx.iteration_id = 1
    return ctx


def _make_verdicts(actions):
    """从 action 列表构建 merged_verdicts 产物。"""
    verdicts = []
    for i, action in enumerate(actions):
        v = {"action": action, "case_id": 100 + i, "reason": f"reason_{i}"}
        if action == "add_new":
            v["candidate_index"] = i
        verdicts.append(v)
    return {
        "project_id": 1,
        "verdicts": verdicts,
        "total_count": len(verdicts),
    }


def _make_fingerprints(case_ids=None):
    """构建 history_fingerprints 产物。"""
    if case_ids is None:
        case_ids = [100, 101, 102]
    return {
        "fingerprints": [
            {"case_id": cid, "title": f"用例{cid}", "module": "测试模块"}
            for cid in case_ids
        ],
    }


def _make_candidates(count=2):
    """构建 scenario_candidates 产物。"""
    return {
        "candidates": [
            {"description": f"候选场景{i}", "module": f"模块{i}", "priority": i + 1, "reason": f"新增{i}"}
            for i in range(count)
        ],
    }


def _make_aligned(count=2):
    """构建 aligned_testpoints 产物。"""
    return {
        "project_id": 1,
        "aligned_testpoints": [
            {"test_point": {"point": f"测试点{i}", "module": f"模块{i}", "priority": i + 1}}
            for i in range(count)
        ],
    }


step = DecisionDispatch()


# ── 正常流程 ──


class TestExecuteNormal:
    def test_needs_modify(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["needs_modify"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "modify"
        assert tasks[0]["case_id"] == 100
        assert tasks[0]["change_type"] == "modified"

    def test_add_new(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["add_new"]),
            candidates=_make_candidates(2),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "create"
        assert tasks[0]["change_type"] == "added"

    def test_deprecate(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["deprecate"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        assert len(result.artifact_payload["generation_tasks"]) == 0
        assert len(result.artifact_payload["deprecation_suggestions"]) == 1
        assert result.artifact_payload["deprecation_suggestions"][0]["case_id"] == 100

    def test_conflict(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["conflict"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "skip"
        assert "冲突" in tasks[0]["skip_reason"]

    def test_pending_review(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["pending_review"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "skip"

    def test_keep(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["keep"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        assert len(result.artifact_payload["generation_tasks"]) == 0
        assert result.artifact_payload["stats"]["keep_count"] == 1

    def test_locator_broken(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["locator_broken"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "locator_fix"

    def test_locator_and_modify(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["locator_and_modify"]),
            fingerprints=_make_fingerprints([100]),
        )
        result = step.execute(ctx)
        assert result.success
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "modify"
        assert tasks[0].get("need_locator_fix") is True

    def test_mixed_verdicts(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["keep", "needs_modify", "add_new", "deprecate"]),
            fingerprints=_make_fingerprints([100, 101]),
            candidates=_make_candidates(3),
        )
        result = step.execute(ctx)
        assert result.success
        payload = result.artifact_payload
        assert payload["stats"]["keep_count"] == 1
        assert payload["stats"]["modify_count"] == 1
        assert payload["stats"]["create_count"] == 1
        assert payload["stats"]["deprecate_count"] == 1
        assert len(payload["generation_tasks"]) == 2  # modify + create
        assert len(payload["deprecation_suggestions"]) == 1


# ── 空 verdicts / 缺失产物 ──


class TestExecuteEmpty:
    def test_missing_merged_verdicts(self):
        ctx = _make_ctx(merged_verdicts=None)
        result = step.execute(ctx)
        assert not result.success
        assert "缺少" in result.error

    def test_empty_verdicts(self):
        ctx = _make_ctx(merged_verdicts={"project_id": 1, "verdicts": [], "total_count": 0})
        result = step.execute(ctx)
        assert result.success
        assert len(result.artifact_payload["generation_tasks"]) == 0


# ── 预算耗尽暂停 ──


class TestBudgetExhausted:
    def test_budget_exhausted_mid_loop(self):
        """预算在第2个 verdict 时耗尽，已生成的任务仍输出，标记暂停。"""
        verdicts = _make_verdicts(["needs_modify", "add_new", "needs_modify"])
        # 第1次 check_budget=True，第2次=False
        ctx = _make_ctx(
            merged_verdicts=verdicts,
            fingerprints=_make_fingerprints([100, 101, 102]),
            candidates=_make_candidates(3),
        )
        budget_calls = [True, False]

        def mock_budget():
            if budget_calls:
                return budget_calls.pop(0)
            return False

        ctx.check_budget = MagicMock(side_effect=mock_budget)
        result = step.execute(ctx)
        assert result.success
        # 第1个 needs_modify 处理完，第2个 add_new 时预算耗尽 break
        payload = result.artifact_payload
        assert len(payload["generation_tasks"]) >= 1
        assert result.pause_for_confirmation is True
        assert "预算耗尽" in (result.confirmation_reason or "")

    def test_budget_ok_no_pause(self):
        ctx = _make_ctx(
            merged_verdicts=_make_verdicts(["needs_modify"]),
            fingerprints=_make_fingerprints([100]),
            budget_ok=True,
        )
        result = step.execute(ctx)
        assert result.success
        assert result.pause_for_confirmation is False


# ── fallback 降级 ──


class TestFallback:
    def test_fallback_with_aligned_testpoints(self):
        """merged_verdicts 缺失时，基于 aligned_testpoints 生成默认 create 任务。"""
        ctx = _make_ctx(
            merged_verdicts=None,
            aligned=_make_aligned(3),
        )
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.success
        assert result.degraded is True
        tasks = result.artifact_payload["generation_tasks"]
        assert len(tasks) == 3
        assert all(t["task_type"] == "create" for t in tasks)

    def test_fallback_no_aligned(self):
        """merged_verdicts 和 aligned_testpoints 都缺失时，返回失败。"""
        ctx = _make_ctx(merged_verdicts=None, aligned=None)
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.success is False or result.degraded is True

    def test_fallback_with_verdicts_available(self):
        """merged_verdicts 可用但执行异常时，返回空任务列表。"""
        ctx = _make_ctx(merged_verdicts={"project_id": 1, "verdicts": [], "total_count": 0})
        result = step.fallback(ctx, RuntimeError("test error"))
        assert result.success
        assert len(result.artifact_payload["generation_tasks"]) == 0


# ── validate_output ──


class TestValidateOutput:
    def test_valid_payload(self):
        payload = {
            "generation_tasks": [{"task_type": "create"}],
            "stats": {
                "keep_count": 0, "modify_count": 0, "create_count": 1,
                "locator_fix_count": 0, "deprecate_count": 0,
                "skip_count": 0, "conflict_count": 0,
            },
        }
        assert step.validate_output(payload) is True

    def test_invalid_no_tasks(self):
        payload = {"stats": {"keep_count": 0}}
        assert step.validate_output(payload) is False

    def test_invalid_not_dict(self):
        assert step.validate_output("not_dict") is False

    def test_invalid_task_missing_type(self):
        payload = {
            "generation_tasks": [{"no_task_type": True}],
            "stats": {
                "keep_count": 0, "modify_count": 0, "create_count": 0,
                "locator_fix_count": 0, "deprecate_count": 0,
                "skip_count": 0, "conflict_count": 0,
            },
        }
        assert step.validate_output(payload) is False


# ── 辅助函数 ──


class TestBuildModifyTask:
    def test_basic(self):
        fp = {100: {"case_id": 100, "title": "旧用例", "module": "M1"}}
        task = _build_modify_task(case_id=100, reason="UI变更", fp_by_case_id=fp, need_locator_fix=False)
        assert task["task_type"] == "modify"
        assert task["case_id"] == 100
        assert task["change_type"] == "modified"
        assert task["modification_hint"] == "UI变更"
        assert "need_locator_fix" not in task

    def test_with_locator_fix(self):
        fp = {100: {"case_id": 100, "title": "旧用例", "module": "M1"}}
        task = _build_modify_task(case_id=100, reason="", fp_by_case_id=fp, need_locator_fix=True)
        assert task["need_locator_fix"] is True

    def test_no_fingerprint(self):
        task = _build_modify_task(case_id=999, reason="test", fp_by_case_id={}, need_locator_fix=False)
        assert task["original_case"] is None


class TestBuildCreateTask:
    def test_with_candidate(self):
        cands = [{"description": "新场景", "module": "M1", "priority": 1, "reason": "新增"}]
        task = _build_create_task(candidate_index=0, cands=cands, reason="test")
        assert task["task_type"] == "create"
        assert task["candidate_description"] == "新场景"
        assert task["change_type"] == "added"

    def test_out_of_range_index(self):
        task = _build_create_task(candidate_index=99, cands=[], reason="test")
        assert task["candidate_description"] == ""


class TestBuildSkipTask:
    def test_basic(self):
        task = _build_skip_task(case_id=100, skip_reason="冲突", fp_by_case_id={})
        assert task["task_type"] == "skip"
        assert task["skip_reason"] == "冲突"


class TestBuildDeprecationSuggestion:
    def test_with_fingerprint(self):
        fp = {100: {"case_id": 100, "title": "旧用例"}}
        result = _build_deprecation_suggestion(case_id=100, reason="已废弃", fp_by_case_id=fp)
        assert result["case_id"] == 100
        assert result["title"] == "旧用例"
        assert result["deprecate_reason"] == "已废弃"

    def test_no_fingerprint(self):
        result = _build_deprecation_suggestion(case_id=999, reason="", fp_by_case_id={})
        assert result["title"] == ""
        assert result["deprecate_reason"] == "建议废弃"


class TestValidateTaskField:
    def test_valid(self):
        assert _validate_task_field({"task_type": "create"}) is True

    def test_missing_type(self):
        assert _validate_task_field({"no_type": True}) is False

    def test_not_dict(self):
        assert _validate_task_field("not_dict") is False
