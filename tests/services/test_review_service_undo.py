import pytest
from app.services.review_service._errors import (
    REVIEW_UNDO_WINDOW_MINUTES,
    ReviewError,
    ReviewFinalizedError,
    ReviewLockConflictError,
    ReviewDecisionImmutableError,
    ReviewUndoWindowExpiredError,
    ReviewNotFinalizedError,
)
from app.services.review_service._undo import (
    undo_decision,
    undo_finalize,
    _reverse_lifecycle,
    _deprecate_child_cases,
    _restore_archived_case,
    _record_undo_metric,
)


class TestReviewErrorHierarchy:
    def test_base_error(self):
        assert issubclass(ReviewError, Exception)

    def test_finalized_error(self):
        assert issubclass(ReviewFinalizedError, ReviewError)

    def test_lock_conflict_error(self):
        assert issubclass(ReviewLockConflictError, ReviewError)

    def test_decision_immutable_error(self):
        assert issubclass(ReviewDecisionImmutableError, ReviewError)

    def test_undo_window_expired_error(self):
        assert issubclass(ReviewUndoWindowExpiredError, ReviewError)

    def test_not_finalized_error(self):
        assert issubclass(ReviewNotFinalizedError, ReviewError)

    def test_raise_errors(self):
        with pytest.raises(ReviewError):
            raise ReviewFinalizedError("finalized")
        with pytest.raises(ReviewError):
            raise ReviewLockConflictError("conflict")
        with pytest.raises(ReviewError):
            raise ReviewDecisionImmutableError("immutable")
        with pytest.raises(ReviewError):
            raise ReviewUndoWindowExpiredError("expired")
        with pytest.raises(ReviewError):
            raise ReviewNotFinalizedError("not finalized")


class TestUndoWindowMinutes:
    def test_value(self):
        assert REVIEW_UNDO_WINDOW_MINUTES == 60


class TestUndoDecision:
    def test_nonexistent_decision(self, db):
        result = undo_decision(db, decision_id=99999, user_id=1)
        assert result is None


class TestUndoFinalize:
    def test_nonexistent_review(self, db):
        result = undo_finalize(db, review_id=99999, user_id=1)
        assert result is None


class TestReverseLifecycle:
    def test_nonexistent_case(self, db):
        _reverse_lifecycle(db, case_id=99999)


class TestDeprecateChildCases:
    def test_no_children(self, db):
        _deprecate_child_cases(db, parent_case_id=99999)


class TestRecordUndoMetric:
    def test_nonexistent_target(self, db):
        _record_undo_metric(db, target_id=99999)

    def test_none_target(self, db):
        _record_undo_metric(db, target_id=None)
