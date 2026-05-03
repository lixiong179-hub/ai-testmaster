"""review_service 单元测试

覆盖范围:
    - create_review / start_review / finalize_review / cancel_review
    - add_decision / set_human_verdict / rollback_decision
    - undo_decision / undo_finalize（M2-T11）
    - acquire_lock / release_lock / cleanup_expired_locks
    - ReviewDecision 不可变（finalize 后禁止修改）
    - ReviewLock 独占（锁定期内不能同时锁定）
    - conflict_marker（AI 与人工判定不一致）
    - accepted_low_confidence（AI 置信度 < 70）
    - ai_verdict / human_verdict 合法值校验
    - ai_confidence 范围校验

使用真实 MySQL 数据库。
"""
import pytest
from datetime import datetime, timedelta

from app.models.iteration import Iteration
from app.models.review import IterationReview, ReviewDecision, ReviewLock
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.services import review_service
from app.services.review_service import (
    ReviewError,
    ReviewFinalizedError,
    ReviewLockConflictError,
    ReviewDecisionImmutableError,
    ReviewNotFinalizedError,
    ReviewUndoWindowExpiredError,
)
from app.utils.db_time import utcnow


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="review_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def reviewer_id(testUser):
    return testUser.id


@pytest.fixture
def test_review(db, test_iteration):
    return review_service.create_review(
        db=db,
        iteration_id=test_iteration.id,
        kind="forward",
    )


@pytest.fixture
def test_review_in_progress(db, test_review):
    return review_service.start_review(db=db, review_id=test_review.id)


class TestCreateReview:
    def test_creates_draft_review(self, db, test_iteration):
        review = review_service.create_review(
            db=db, iteration_id=test_iteration.id, kind="forward",
        )
        assert review.id is not None
        assert review.status == "draft"
        assert review.kind == "forward"

    def test_invalid_kind_raises(self, db, test_iteration):
        with pytest.raises(ReviewError, match="Invalid review kind"):
            review_service.create_review(
                db=db, iteration_id=test_iteration.id, kind="invalid",
            )


class TestStartReview:
    def test_draft_to_in_progress(self, db, test_review):
        review = review_service.start_review(db=db, review_id=test_review.id)
        assert review.status == "in_progress"

    def test_non_draft_raises(self, db, test_review_in_progress):
        with pytest.raises(ReviewError, match="not in draft"):
            review_service.start_review(db=db, review_id=test_review_in_progress.id)

    def test_nonexistent_returns_none(self, db):
        result = review_service.start_review(db=db, review_id=999999)
        assert result is None


class TestAddDecision:
    def test_adds_decision(self, db, test_review):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=1,
            ai_verdict="keep", ai_confidence=90,
            ai_reason="No changes detected",
        )
        assert decision.id is not None
        assert decision.final_verdict == "keep"
        assert decision.conflict_marker is False
        assert decision.accepted_low_confidence is False

    def test_low_confidence_flag(self, db, test_review):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=2,
            ai_verdict="modify", ai_confidence=50,
        )
        assert decision.accepted_low_confidence is True

    def test_invalid_target_kind_raises(self, db, test_review):
        with pytest.raises(ReviewError, match="Invalid target_kind"):
            review_service.add_decision(
                db=db, review_id=test_review.id,
                target_kind="invalid", target_id=1,
                ai_verdict="keep", ai_confidence=90,
            )

    def test_finalized_review_raises(self, db, test_review_in_progress, reviewer_id):
        review_service.finalize_review(db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id)
        with pytest.raises(ReviewFinalizedError):
            review_service.add_decision(
                db=db, review_id=test_review_in_progress.id,
                target_kind="case", target_id=1,
                ai_verdict="keep", ai_confidence=90,
            )


class TestSetHumanVerdict:
    def test_overrides_ai_verdict(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=10,
            ai_verdict="keep", ai_confidence=90,
        )
        updated = review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="modify", human_user_id=reviewer_id,
            human_reason="Need more steps",
        )
        assert updated.final_verdict == "modify"
        assert updated.conflict_marker is True

    def test_same_verdict_no_conflict(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=11,
            ai_verdict="keep", ai_confidence=90,
        )
        updated = review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=reviewer_id,
        )
        assert updated.final_verdict == "keep"
        assert updated.conflict_marker is False

    def test_finalized_review_raises(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=12,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.finalize_review(db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id)
        with pytest.raises(ReviewFinalizedError):
            review_service.set_human_verdict(
                db=db, decision_id=decision.id,
                human_verdict="modify", human_user_id=reviewer_id,
            )

    def test_nonexistent_returns_none(self, db, reviewer_id):
        result = review_service.set_human_verdict(
            db=db, decision_id=999999,
            human_verdict="keep", human_user_id=reviewer_id,
        )
        assert result is None


class TestRollbackDecision:
    def test_rollback_resets_human_verdict(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=20,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="modify", human_user_id=reviewer_id,
        )
        rolled_back = review_service.rollback_decision(
            db=db, decision_id=decision.id, user_id=reviewer_id,
        )
        assert rolled_back.human_verdict is None
        assert rolled_back.final_verdict == "keep"
        assert rolled_back.conflict_marker is False

    def test_finalized_review_raises(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=21,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.finalize_review(db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id)
        with pytest.raises(ReviewDecisionImmutableError):
            review_service.rollback_decision(
                db=db, decision_id=decision.id, user_id=reviewer_id,
            )

    def test_nonexistent_returns_none(self, db):
        result = review_service.rollback_decision(db=db, decision_id=999999, user_id=999999)
        assert result is None


class TestFinalizeReview:
    def test_finalize_clears_locks(self, db, test_review_in_progress, reviewer_id):
        review_service.acquire_lock(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=30,
        )
        review = review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        assert review.status == "finalized"
        assert review.finalized_at is not None
        assert review.finalized_by == reviewer_id
        assert len(review.locks) == 0

    def test_non_in_progress_raises(self, db, test_review, reviewer_id):
        with pytest.raises(ReviewError, match="not in_progress"):
            review_service.finalize_review(db=db, review_id=test_review.id, finalized_by=reviewer_id)

    def test_nonexistent_returns_none(self, db, reviewer_id):
        result = review_service.finalize_review(db=db, review_id=999999, finalized_by=reviewer_id)
        assert result is None


class TestCancelReview:
    def test_cancel_draft(self, db, test_review):
        review = review_service.cancel_review(db=db, review_id=test_review.id)
        assert review.status == "cancelled"

    def test_cancel_finalized_raises(self, db, test_review_in_progress, reviewer_id):
        review_service.finalize_review(db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id)
        with pytest.raises(ReviewFinalizedError):
            review_service.cancel_review(db=db, review_id=test_review_in_progress.id)


class TestAcquireLock:
    def test_acquire_lock(self, db, test_review):
        lock = review_service.acquire_lock(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=40,
        )
        assert lock.id is not None
        assert lock.expires_at > utcnow()

    def test_duplicate_lock_raises(self, db, test_review):
        review_service.acquire_lock(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=41,
        )
        with pytest.raises(ReviewLockConflictError):
            review_service.acquire_lock(
                db=db, review_id=test_review.id,
                target_kind="case", target_id=41,
            )

    def test_finalized_review_raises(self, db, test_review_in_progress, reviewer_id):
        review_service.finalize_review(db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id)
        with pytest.raises(ReviewFinalizedError):
            review_service.acquire_lock(
                db=db, review_id=test_review_in_progress.id,
                target_kind="case", target_id=42,
            )


class TestReleaseLock:
    def test_release_lock(self, db, test_review):
        lock = review_service.acquire_lock(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=50,
        )
        result = review_service.release_lock(db=db, lock_id=lock.id)
        assert result is True

    def test_nonexistent_returns_false(self, db):
        result = review_service.release_lock(db=db, lock_id=999999)
        assert result is False


class TestCleanupExpiredLocks:
    def test_cleanup_expired(self, db, test_review):
        expired_lock = ReviewLock(
            review_id=test_review.id,
            target_kind="case",
            target_id=60,
            locked_at=utcnow() - timedelta(hours=25),
            expires_at=utcnow() - timedelta(hours=1),
        )
        db.add(expired_lock)
        db.flush()

        count = review_service.cleanup_expired_locks(db=db)
        assert count >= 1


class TestComputeFinalVerdict:
    def test_human_overrides_ai(self):
        verdict, conflict = ReviewDecision.compute_final_verdict("keep", "modify")
        assert verdict == "modify"
        assert conflict is True

    def test_no_human_uses_ai(self):
        verdict, conflict = ReviewDecision.compute_final_verdict("keep", None)
        assert verdict == "keep"
        assert conflict is False

    def test_no_ai_defaults_keep(self):
        verdict, conflict = ReviewDecision.compute_final_verdict(None, None)
        assert verdict == "keep"
        assert conflict is False

    def test_same_verdict_no_conflict(self):
        verdict, conflict = ReviewDecision.compute_final_verdict("deprecate", "deprecate")
        assert verdict == "deprecate"
        assert conflict is False


class TestListReviews:
    def test_returns_reviews(self, db, test_iteration):
        review_service.create_review(db=db, iteration_id=test_iteration.id, kind="forward")
        reviews = review_service.list_reviews(db=db, iteration_id=test_iteration.id)
        assert len(reviews) >= 1

    def test_filter_by_status(self, db, test_iteration):
        review_service.create_review(db=db, iteration_id=test_iteration.id, kind="backward")
        reviews = review_service.list_reviews(
            db=db, iteration_id=test_iteration.id, status="draft",
        )
        assert all(r.status == "draft" for r in reviews)


class TestAddDecisionValidation:
    def test_invalid_ai_verdict_raises(self, db, test_review):
        with pytest.raises(ReviewError, match="Invalid ai_verdict"):
            review_service.add_decision(
                db=db, review_id=test_review.id,
                target_kind="case", target_id=1,
                ai_verdict="invalid", ai_confidence=90,
            )

    def test_confidence_below_zero_raises(self, db, test_review):
        with pytest.raises(ReviewError, match="Invalid ai_confidence"):
            review_service.add_decision(
                db=db, review_id=test_review.id,
                target_kind="case", target_id=1,
                ai_verdict="keep", ai_confidence=-1,
            )

    def test_confidence_above_100_raises(self, db, test_review):
        with pytest.raises(ReviewError, match="Invalid ai_confidence"):
            review_service.add_decision(
                db=db, review_id=test_review.id,
                target_kind="case", target_id=1,
                ai_verdict="keep", ai_confidence=101,
            )

    def test_confidence_boundary_zero(self, db, test_review):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=2,
            ai_verdict="keep", ai_confidence=0,
        )
        assert decision.accepted_low_confidence is True

    def test_confidence_boundary_100(self, db, test_review):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=3,
            ai_verdict="keep", ai_confidence=100,
        )
        assert decision.accepted_low_confidence is False


class TestSetHumanVerdictValidation:
    def test_invalid_human_verdict_raises(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=70,
            ai_verdict="keep", ai_confidence=90,
        )
        with pytest.raises(ReviewError, match="Invalid human_verdict"):
            review_service.set_human_verdict(
                db=db, decision_id=decision.id,
                human_verdict="invalid", human_user_id=reviewer_id,
            )

    def test_human_verdict_resets_low_confidence(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=71,
            ai_verdict="modify", ai_confidence=50,
        )
        assert decision.accepted_low_confidence is True
        updated = review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="modify", human_user_id=reviewer_id,
        )
        assert updated.accepted_low_confidence is False


class TestRollbackDecisionRecalculation:
    def test_rollback_restores_low_confidence_flag(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=80,
            ai_verdict="modify", ai_confidence=50,
        )
        assert decision.accepted_low_confidence is True
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="modify", human_user_id=reviewer_id,
        )
        rolled_back = review_service.rollback_decision(
            db=db, decision_id=decision.id, user_id=reviewer_id,
        )
        assert rolled_back.accepted_low_confidence is True


class TestCancelReviewClearsLocks:
    def test_cancel_clears_locks(self, db, test_review):
        review_service.acquire_lock(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=90,
        )
        review = review_service.cancel_review(db=db, review_id=test_review.id)
        assert review.status == "cancelled"
        assert len(review.locks) == 0


class TestAddDecisionReviewNotFound:
    def test_add_decision_nonexistent_review_raises(self, db):
        with pytest.raises(ReviewError, match="not found"):
            review_service.add_decision(
                db=db, review_id=99999,
                target_kind="case", target_id=1,
                ai_verdict="keep", ai_confidence=90,
            )


class TestCancelReviewNotFound:
    def test_cancel_nonexistent_returns_none(self, db):
        result = review_service.cancel_review(db=db, review_id=99999)
        assert result is None


class TestAcquireLockReviewNotFound:
    def test_acquire_lock_nonexistent_review_raises(self, db):
        with pytest.raises(ReviewError, match="not found"):
            review_service.acquire_lock(
                db=db, review_id=99999,
                target_kind="case", target_id=1,
            )


class TestGetReview:
    def test_get_existing_review(self, db, test_review):
        found = review_service.get_review(db=db, review_id=test_review.id)
        assert found is not None
        assert found.id == test_review.id

    def test_get_nonexistent_review(self, db):
        found = review_service.get_review(db=db, review_id=99999)
        assert found is None


class TestGetDecisions:
    def test_get_decisions_without_filter(self, db, test_review):
        review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=200,
            ai_verdict="keep", ai_confidence=80,
        )
        decisions = review_service.get_decisions(db=db, review_id=test_review.id)
        assert len(decisions) >= 1

    def test_get_decisions_with_target_kind_filter(self, db, test_review):
        review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=201,
            ai_verdict="keep", ai_confidence=80,
        )
        review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="testpoint", target_id=202,
            ai_verdict="modify", ai_confidence=60,
        )
        decisions = review_service.get_decisions(
            db=db, review_id=test_review.id, target_kind="case",
        )
        assert all(d.target_kind == "case" for d in decisions)

    def test_get_decisions_empty_result(self, db, test_review):
        decisions = review_service.get_decisions(
            db=db, review_id=test_review.id, target_kind="nonexistent",
        )
        assert len(decisions) == 0


class TestUndoDecision:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, reviewer_id):
        self.case = TestCase(
            project_id=testProject.id,
            case_no="REV-UNDO-001",
            module="user",
            title="undo test case",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.case)
        db.flush()
        self.case_id = self.case.id

    def test_undo_deprecate_restores_active(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="deprecate", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="deprecate", human_user_id=reviewer_id,
        )
        enable_lifecycle_transition()
        self.case.lifecycle_status = "deprecated"
        db.flush()
        disable_lifecycle_transition()

        review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        db.flush()

        result = review_service.undo_decision(db, decision.id, reviewer_id)
        assert result is not None
        assert result.human_verdict is None
        assert result.final_verdict == "deprecate"

        db.refresh(self.case)
        assert self.case.lifecycle_status == "active"

    def test_undo_within_window_succeeds(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=reviewer_id,
        )
        review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        db.flush()

        result = review_service.undo_decision(db, decision.id, reviewer_id)
        assert result is not None
        assert result.human_verdict is None
        assert result.final_verdict == "keep"
        assert result.conflict_marker is False

    def test_undo_window_expired_raises(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=reviewer_id,
        )
        review = review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        review.finalized_at = utcnow() - timedelta(minutes=61)
        db.flush()

        with pytest.raises(ReviewUndoWindowExpiredError):
            review_service.undo_decision(db, decision.id, reviewer_id)

    def test_undo_not_finalized_raises(self, db, test_review, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="keep", ai_confidence=90,
        )
        with pytest.raises(ReviewNotFinalizedError):
            review_service.undo_decision(db, decision.id, reviewer_id)

    def test_undo_nonexistent_returns_none(self, db):
        result = review_service.undo_decision(db, 999999, 1)
        assert result is None

    def test_undo_with_child_cases_deprecates_children(self, db, test_review_in_progress, reviewer_id):
        child = TestCase(
            project_id=self.case.project_id,
            case_no="REV-UNDO-CHILD-001",
            module="user",
            title="child case",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="pending_review",
            parent_case_id=self.case_id,
        )
        db.add(child)
        db.flush()

        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="modify", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="modify", human_user_id=reviewer_id,
        )
        enable_lifecycle_transition()
        self.case.lifecycle_status = "needs_modify"
        db.flush()
        disable_lifecycle_transition()

        review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        db.flush()

        review_service.undo_decision(db, decision.id, reviewer_id)

        db.refresh(child)
        assert child.lifecycle_status == "deprecated"

    def test_undo_archived_case_creates_draft_copy(self, db, test_review_in_progress, reviewer_id):
        enable_lifecycle_transition()
        self.case.lifecycle_status = "archived"
        db.flush()
        disable_lifecycle_transition()

        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        db.flush()

        review_service.undo_decision(db, decision.id, reviewer_id)

        restored_cases = (
            db.query(TestCase)
            .filter(TestCase.case_no.like(f"{self.case.case_no}%-restored%"))
            .all()
        )
        assert len(restored_cases) >= 1
        assert restored_cases[0].lifecycle_status == "draft"


class TestUndoFinalize:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, reviewer_id):
        self.case = TestCase(
            project_id=testProject.id,
            case_no="REV-UF-001",
            module="user",
            title="undo finalize test case",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(self.case)
        db.flush()
        self.case_id = self.case.id

    def test_undo_finalize_restores_in_progress(self, db, test_review_in_progress, reviewer_id):
        decision = review_service.add_decision(
            db=db, review_id=test_review_in_progress.id,
            target_kind="case", target_id=self.case_id,
            ai_verdict="deprecate", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="deprecate", human_user_id=reviewer_id,
        )
        enable_lifecycle_transition()
        self.case.lifecycle_status = "deprecated"
        db.flush()
        disable_lifecycle_transition()

        review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        db.flush()

        result = review_service.undo_finalize(db, test_review_in_progress.id, reviewer_id)
        assert result is not None
        assert result.status == "in_progress"
        assert result.finalized_at is None

        db.refresh(decision)
        assert decision.human_verdict is None
        assert decision.final_verdict == "deprecate"

        db.refresh(self.case)
        assert self.case.lifecycle_status == "active"

    def test_undo_finalize_window_expired_raises(self, db, test_review_in_progress, reviewer_id):
        review = review_service.finalize_review(
            db=db, review_id=test_review_in_progress.id, finalized_by=reviewer_id,
        )
        review.finalized_at = utcnow() - timedelta(minutes=61)
        db.flush()

        with pytest.raises(ReviewUndoWindowExpiredError):
            review_service.undo_finalize(db, test_review_in_progress.id, reviewer_id)

    def test_undo_finalize_not_finalized_raises(self, db, test_review):
        with pytest.raises(ReviewNotFinalizedError):
            review_service.undo_finalize(db, test_review.id, 1)

    def test_undo_finalize_nonexistent_returns_none(self, db):
        result = review_service.undo_finalize(db, 999999, 1)
        assert result is None
