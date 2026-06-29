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


class TestErrorSanitization:
    """守护 error 字段不泄露异常原始 str(e)（项目规则第四章：日志脱敏）。

    回归守护：5 处业务异常 + 2 处通用 Exception 均改为脱敏消息，
    原始异常通过 logger 记录。若未来回退到 str(e) 将被以下断言拦截。
    """

    _SENSITIVE_MARKER = "IllegalStateTransition"

    def _patch_to_raise(self, monkeypatch, exc):
        """让 lifecycle_transition 与 _ensure_target_exists 协同触发指定异常。

        _ensure_target_exists 返回 sentinel 对象（非 None）使校验通过，
        lifecycle_transition 抛出 exc 触发业务异常分支。
        """
        from app.services.decision_application_service import _core as core_mod
        from app.services.decision_application_service import _handlers as handlers_mod
        from app.models.test_case import TestCase
        sentinel = TestCase(
            project_id=1, case_no="TC-SANIT-0001", module="m",
            title="t", priority=1, case_type="manual",
            generate_status="completed", lifecycle_status="active",
        )
        sentinel.id = 99999
        monkeypatch.setattr(core_mod, "_ensure_target_exists", lambda db, tid: sentinel)
        monkeypatch.setattr(handlers_mod, "_ensure_target_exists", lambda db, tid: sentinel)
        def _raise(*args, **kwargs):
            raise exc
        monkeypatch.setattr(core_mod, "lifecycle_transition", _raise)
        monkeypatch.setattr(handlers_mod, "lifecycle_transition", _raise)
        return sentinel

    def test_locator_broken_sanitizes_illegal_transition(self, db, monkeypatch):
        from app.services.lifecycle_service import IllegalStateTransition
        self._patch_to_raise(monkeypatch, IllegalStateTransition("active", "locator_broken"))
        d = ApplyDecision(target_kind="test_case", target_id=99999, merged_action="locator_broken")
        result = _handle_locator_broken(db, d, actor_id=1)
        assert result.success is False
        assert result.error == "状态转换不合法"
        assert self._SENSITIVE_MARKER not in result.error

    def test_needs_modify_sanitizes_business_exceptions(self, db, monkeypatch):
        from app.services.lifecycle_service import IllegalStateTransition
        self._patch_to_raise(monkeypatch, IllegalStateTransition("active", "needs_modify"))
        d = ApplyDecision(
            target_kind="test_case", target_id=99999,
            merged_action="needs_modify", review_id=10,
        )
        result = apply_single(db, d)
        assert result.success is False
        assert result.error == "业务校验失败，请检查 review_id"
        assert self._SENSITIVE_MARKER not in result.error

    def test_deprecate_sanitizes_business_exceptions(self, db, monkeypatch):
        from app.services.lifecycle_service import MissingDeprecateReasonError
        self._patch_to_raise(monkeypatch, MissingDeprecateReasonError("deprecate"))
        d = ApplyDecision(
            target_kind="test_case", target_id=99999,
            merged_action="deprecate", review_id=10, deprecate_reason="原因",
        )
        from app.services.decision_application_service._handlers import _handle_deprecate
        result = _handle_deprecate(db, d, actor_id=1)
        assert result.success is False
        assert result.error == "业务校验失败，请检查 review_id 与 deprecate_reason"
        assert "MissingDeprecateReasonError" not in result.error

    def test_locator_and_modify_sanitizes_illegal_transition(self, db, monkeypatch):
        from app.services.lifecycle_service import IllegalStateTransition
        self._patch_to_raise(monkeypatch, IllegalStateTransition("active", "locator_broken"))
        d = ApplyDecision(
            target_kind="test_case", target_id=99999,
            merged_action="locator_and_modify", review_id=10,
        )
        from app.services.decision_application_service._handlers import _handle_locator_and_modify
        result = _handle_locator_and_modify(db, d, actor_id=1)
        assert result.success is False
        assert result.error == "状态转换不合法"
        assert self._SENSITIVE_MARKER not in result.error

    def test_add_new_generic_exception_sanitized(self, db, monkeypatch):
        d = ApplyDecision(
            target_kind="test_case", target_id=None,
            merged_action="add_new",
            case_data={"project_id": "not_a_number"},
        )
        from app.services.decision_application_service._handlers import _handle_add_new
        result = _handle_add_new(db, d, actor_id=1)
        assert result.success is False
        assert result.error == "add_new 处理失败，详情见日志"
        assert "int" not in result.error.lower()
        assert "Traceback" not in result.error

    def test_errors_never_contain_exception_str(self, db, monkeypatch):
        from app.services.lifecycle_service import IllegalStateTransition
        sentinel_marker = "SENTINEL_LEAK_MARKER_xyz"
        exc = IllegalStateTransition("active", "locator_broken")
        exc.args = (sentinel_marker,)
        self._patch_to_raise(monkeypatch, exc)
        d = ApplyDecision(target_kind="test_case", target_id=99999, merged_action="locator_broken")
        result = _handle_locator_broken(db, d, actor_id=1)
        assert sentinel_marker not in (result.error or "")
