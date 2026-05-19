import pytest
from app.services.decision_application_service._core import (
    ApplyDecision,
    ApplyResult,
    apply_decisions,
    apply_single,
    _handle_keep,
    _handle_locator_broken,
    _ensure_target_exists,
    _build_result,
)
from app.services.decision_application_service._handlers import (
    _handle_deprecate,
    _handle_add_new,
    _handle_locator_and_modify,
    _handle_conflict,
    _handle_pending_review,
    _verdict_to_action,
    _load_decisions_from_review,
)
from app.pipelines.steps.reconciliation import MergedAction


class TestApplyDecisionDataclass:
    def test_defaults(self):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="keep")
        assert d.target_kind == "test_case"
        assert d.target_id == 1
        assert d.merged_action == "keep"
        assert d.modification_hint is None
        assert d.deprecate_reason is None
        assert d.confidence == 0.0
        assert d.review_id is None
        assert d.case_data is None

    def test_with_all_fields(self):
        d = ApplyDecision(
            target_kind="test_case", target_id=5,
            merged_action="needs_modify",
            modification_hint="更新步骤",
            deprecate_reason="需求变更",
            confidence=0.85,
            review_id=10,
            case_data={"title": "新用例"},
        )
        assert d.confidence == 0.85
        assert d.review_id == 10
        assert d.case_data["title"] == "新用例"


class TestApplyResultDataclass:
    def test_defaults(self):
        r = ApplyResult(target_kind="tc", target_id=1, action="keep", success=True)
        assert r.new_case_id is None
        assert r.error is None
        assert r.deferred is False
        assert r.deferred_reason is None


class TestHandleKeep:
    def test_success(self):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="keep")
        result = _handle_keep(d)
        assert result.success is True
        assert result.action == "keep"

    def test_no_target_id(self):
        d = ApplyDecision(target_kind="test_case", target_id=None, merged_action="keep")
        result = _handle_keep(d)
        assert result.success is True


class TestHandleConflict:
    def test_returns_error(self):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="conflict")
        result = _handle_conflict(d)
        assert result.success is False
        assert "manual resolution" in result.error


class TestHandlePendingReview:
    def test_deferred(self):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="pending_review")
        result = _handle_pending_review(d)
        assert result.success is True
        assert result.deferred is True
        assert result.deferred_reason is not None


class TestHandleLocatorBroken:
    def test_no_target_id(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=None, merged_action="locator_broken")
        result = _handle_locator_broken(db, d, actor_id=1)
        assert result.success is False
        assert "target_id" in result.error

    def test_nonexistent_target(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=99999, merged_action="locator_broken")
        result = _handle_locator_broken(db, d, actor_id=1)
        assert result.success is False
        assert "not found" in result.error


class TestHandleDeprecate:
    def test_no_target_id(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=None, merged_action="deprecate")
        result = _handle_deprecate(db, d, actor_id=1)
        assert result.success is False
        assert "target_id" in result.error

    def test_nonexistent_target(self, db):
        d = ApplyDecision(
            target_kind="test_case", target_id=99999,
            merged_action="deprecate", review_id=10, deprecate_reason="原因",
        )
        result = _handle_deprecate(db, d, actor_id=1)
        assert result.success is False
        assert "not found" in result.error

    def test_no_deprecate_reason(self, db):
        d = ApplyDecision(
            target_kind="test_case", target_id=1,
            merged_action="deprecate", review_id=10,
        )
        result = _handle_deprecate(db, d, actor_id=1)
        assert result.success is False


class TestHandleAddNew:
    def test_no_project_id(self, db):
        d = ApplyDecision(
            target_kind="test_case", target_id=None,
            merged_action="add_new", case_data={},
        )
        result = _handle_add_new(db, d, actor_id=1)
        assert result.success is False
        assert "project_id" in result.error

    def test_case_data_none(self, db):
        d = ApplyDecision(
            target_kind="test_case", target_id=None,
            merged_action="add_new", case_data=None,
        )
        result = _handle_add_new(db, d, actor_id=1)
        assert result.success is False


class TestHandleLocatorAndModify:
    def test_no_target_id(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=None, merged_action="locator_and_modify")
        result = _handle_locator_and_modify(db, d, actor_id=1)
        assert result.success is False
        assert "target_id" in result.error

    def test_nonexistent_target(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=99999, merged_action="locator_and_modify")
        result = _handle_locator_and_modify(db, d, actor_id=1)
        assert result.success is False
        assert "not found" in result.error


class TestApplySingle:
    def test_unknown_action(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="unknown_action")
        result = apply_single(db, d)
        assert result.success is False
        assert "Unknown action" in result.error

    def test_keep_action(self, db):
        d = ApplyDecision(target_kind="test_case", target_id=1, merged_action="keep")
        result = apply_single(db, d)
        assert result.success is True


class TestApplyDecisions:
    def test_empty_list(self, db):
        results = apply_decisions(db, decisions=[])
        assert results == []

    def test_none_decisions(self, db):
        results = apply_decisions(db, decisions=None)
        assert results == []

    def test_keep_decisions(self, db):
        decisions = [
            ApplyDecision(target_kind="test_case", target_id=1, merged_action="keep"),
            ApplyDecision(target_kind="test_case", target_id=2, merged_action="keep"),
        ]
        results = apply_decisions(db, decisions=decisions)
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True


class TestVerdictToAction:
    def test_keep(self):
        assert _verdict_to_action("keep", False) == MergedAction.KEEP

    def test_modify(self):
        assert _verdict_to_action("modify", False) == MergedAction.NEEDS_MODIFY

    def test_deprecate(self):
        assert _verdict_to_action("deprecate", False) == MergedAction.DEPRECATE

    def test_conflict_marker(self):
        assert _verdict_to_action("keep", True) == MergedAction.CONFLICT

    def test_unknown_verdict(self):
        assert _verdict_to_action("unknown", False) == MergedAction.PENDING_REVIEW


class TestLoadDecisionsFromReview:
    def test_nonexistent_review(self, db):
        result = _load_decisions_from_review(99999, db)
        assert result == []


class TestEnsureTargetExists:
    def test_nonexistent(self, db):
        result = _ensure_target_exists(db, 99999)
        assert result is None


class TestBuildResult:
    def test_success(self):
        d = ApplyDecision(target_kind="tc", target_id=1, merged_action="keep")
        r = _build_result(d, success=True)
        assert r.success is True
        assert r.error is None

    def test_failure(self):
        d = ApplyDecision(target_kind="tc", target_id=1, merged_action="keep")
        r = _build_result(d, success=False, error="出错了")
        assert r.success is False
        assert r.error == "出错了"

    def test_with_new_case_id(self):
        d = ApplyDecision(target_kind="tc", target_id=1, merged_action="add_new")
        r = _build_result(d, success=True, new_case_id=42)
        assert r.new_case_id == 42
