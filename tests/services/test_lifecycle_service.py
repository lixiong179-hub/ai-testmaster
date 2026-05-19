import pytest
from datetime import datetime, timezone, timedelta

from app.services.lifecycle_service import (
    can_transition,
    transition,
    IllegalStateTransition,
    MissingReviewError,
    CooldownNotElapsedError,
    MissingDeprecateReasonError,
    TRANSITION_RULES,
)
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.models.enums import TestCaseLifecycleStatus
from app.models.project import Project
from app.models.user import User
from app.models.code_review import CodeReview


@pytest.fixture
def lc_user(db):
    user = User(username="lc_cov_user", email="lc_cov@test.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    db.query(CodeReview).filter(
        (CodeReview.reviewer_id == user.id) | (CodeReview.author_id == user.id)
    ).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.flush()


@pytest.fixture
def lc_project(db, lc_user):
    project = Project(name="LC覆盖项目", user_id=lc_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_case(db, project_id, lifecycle_status="active", **kwargs):
    case = TestCase(
        project_id=project_id,
        case_no=kwargs.get("case_no", f"LC-{datetime.now().strftime('%H%M%S%f')}"),
        module="测试模块",
        title="生命周期覆盖用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI",
        lifecycle_status=lifecycle_status,
    )
    enable_lifecycle_transition()
    try:
        db.add(case)
        db.flush()
        db.refresh(case)
    finally:
        disable_lifecycle_transition()
    return case


def _make_review(db, user_id):
    review = CodeReview(
        title="LC覆盖评审",
        repository="https://example.com/repo",
        branch="main",
        reviewer_id=user_id,
        author_id=user_id,
    )
    db.add(review)
    db.flush()
    db.refresh(review)
    return review


class TestCanTransitionCoverage:

    def test_all_rules_valid(self):
        for (from_s, to_s) in TRANSITION_RULES:
            assert can_transition(from_s, to_s) is True

    def test_unknown_from_status(self):
        assert can_transition("unknown_status", "active") is False

    def test_archived_no_transitions(self):
        for status in TestCaseLifecycleStatus:
            assert can_transition("archived", status.value) is False

    def test_same_status_not_allowed(self):
        for status in TestCaseLifecycleStatus:
            assert can_transition(status.value, status.value) is False


class TestTransitionCoverage:

    def test_draft_to_deprecated_with_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="draft")
        result = transition(db, tc.id, "deprecated", reason="不再需要")
        assert result.lifecycle_status == "deprecated"

    def test_needs_modify_to_deprecated_with_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="needs_modify")
        result = transition(db, tc.id, "deprecated", reason="废弃修改")
        assert result.lifecycle_status == "deprecated"

    def test_needs_modify_to_active(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="needs_modify")
        result = transition(db, tc.id, "active")
        assert result.lifecycle_status == "active"

    def test_deprecated_to_active(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="deprecated")
        result = transition(db, tc.id, "active")
        assert result.lifecycle_status == "active"

    def test_pending_review_to_active_auto_approve(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="pending_review")
        result = transition(db, tc.id, "active", auto_approve=True)
        assert result.lifecycle_status == "active"

    def test_active_to_deprecated_without_review_with_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="active")
        result = transition(db, tc.id, "deprecated", reason="功能下线")
        assert result.lifecycle_status == "deprecated"
        assert result.deprecated_at is not None

    def test_review_id_recorded(self, db, lc_project, lc_user):
        tc = _make_case(db, lc_project.id, lifecycle_status="active")
        review = _make_review(db, lc_user.id)
        result = transition(db, tc.id, "needs_modify", review_id=review.id, modification_hint="需修改")
        assert result.last_review_id == review.id

    def test_nonexistent_case_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            transition(db, 999999, "active")

    def test_illegal_transition_raises(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="active")
        with pytest.raises(IllegalStateTransition):
            transition(db, tc.id, "draft")

    def test_active_to_needs_modify_without_review_raises(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="active")
        with pytest.raises(MissingReviewError):
            transition(db, tc.id, "needs_modify")

    def test_deprecated_to_archived_cooldown_raises(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="deprecated")
        with pytest.raises(CooldownNotElapsedError):
            transition(db, tc.id, "archived")

    def test_deprecated_to_archived_after_cooldown(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="deprecated")
        enable_lifecycle_transition()
        try:
            tc.deprecated_at = datetime.now(timezone.utc) - timedelta(hours=25)
            db.flush()
            db.refresh(tc)
        finally:
            disable_lifecycle_transition()
        result = transition(db, tc.id, "archived")
        assert result.lifecycle_status == "archived"

    def test_needs_modify_to_pending_review_creates_version(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="needs_modify")
        result = transition(db, tc.id, "pending_review", modification_hint="修改步骤")
        db.refresh(tc)
        assert tc.lifecycle_status == "archived"
        new_case = db.query(TestCase).filter(
            TestCase.parent_case_id == tc.id,
            TestCase.lifecycle_status == "pending_review",
        ).first()
        assert new_case is not None


class TestIllegalStateTransitionDetail:

    def test_exception_str_contains_statuses(self):
        exc = IllegalStateTransition("active", "draft", detail="不允许回退")
        assert "active" in str(exc)
        assert "draft" in str(exc)
        assert "不允许回退" in str(exc)

    def test_exception_without_detail(self):
        exc = IllegalStateTransition("active", "draft")
        assert "active" in str(exc)
        assert "draft" in str(exc)


class TestMissingDeprecateReasonError:

    def test_pending_review_to_deprecated_without_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="pending_review")
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated")

    def test_locator_broken_to_deprecated_without_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="locator_broken")
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated")

    def test_draft_to_deprecated_without_reason(self, db, lc_project):
        tc = _make_case(db, lc_project.id, lifecycle_status="draft")
        with pytest.raises(MissingDeprecateReasonError):
            transition(db, tc.id, "deprecated")
