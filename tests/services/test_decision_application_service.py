"""决策应用服务单元测试�?

覆盖 apply_decisions / apply_single 所有动作路径、异常路径、边界场景�?
"""
import pytest
from app.services.decision_application_service import (
    ApplyDecision,
    ApplyResult,
    apply_decisions,
    apply_single,
)
from app.pipelines.steps.reconciliation import MergedAction
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.code_review import CodeReview
from app.models.enums import TestCaseLifecycleStatus


class TestApplyKeep:
    def test_keep_succeeds_without_transition(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=99999,
            merged_action=MergedAction.KEEP,
        )
        result = apply_single(db, decision)
        assert result.success is True
        assert result.action == MergedAction.KEEP
        assert result.error is None

    def test_keep_succeeds_with_none_target(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=None,
            merged_action=MergedAction.KEEP,
        )
        result = apply_single(db, decision)
        assert result.success is True


class TestApplyNeedsModify:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        review = CodeReview(
            title="test review modify",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=testUser.id,
            author_id=testUser.id,
            status="completed",
        )
        db.add(review)
        db.flush()
        self.review_id = review.id

        case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-MODIFY-001",
            module="user",
            title="需要修改的用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()
        self.case_id = case.id

    def test_needs_modify_succeeds(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.NEEDS_MODIFY,
            review_id=self.review_id,
            modification_hint="修改操作步骤",
        )
        result = apply_single(db, decision)
        assert result.success is True

        case = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert case.lifecycle_status == "needs_modify"
        assert case.last_review_id == self.review_id

    def test_needs_modify_case_not_found(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=99999,
            merged_action=MergedAction.NEEDS_MODIFY,
            review_id=self.review_id,
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "not found" in str(result.error)

    def test_needs_modify_missing_review_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.NEEDS_MODIFY,
            review_id=None,
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "review_id" in str(result.error)

    def test_needs_modify_none_target_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=None,
            merged_action=MergedAction.NEEDS_MODIFY,
            review_id=self.review_id,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_needs_modify_already_archived(self, db):
        db.query(TestCase).filter(TestCase.id == self.case_id).update(
            {"lifecycle_status": "archived"}
        )
        db.flush()

        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.NEEDS_MODIFY,
            review_id=self.review_id,
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "Illegal" in str(result.error)


class TestApplyLocatorBroken:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject):
        case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-LB-001",
            module="user",
            title="定位器失效的用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()
        self.case_id = case.id

    def test_locator_broken_succeeds(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.LOCATOR_BROKEN,
        )
        result = apply_single(db, decision)
        assert result.success is True

        case = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert case.lifecycle_status == "locator_broken"

    def test_locator_broken_case_not_found(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=99999,
            merged_action=MergedAction.LOCATOR_BROKEN,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_locator_broken_wrong_state(self, db):
        db.query(TestCase).filter(TestCase.id == self.case_id).update(
            {"lifecycle_status": "archived"}
        )
        db.flush()

        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.LOCATOR_BROKEN,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_locator_broken_none_target_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=None,
            merged_action=MergedAction.LOCATOR_BROKEN,
        )
        result = apply_single(db, decision)
        assert result.success is False


class TestApplyLocatorAndModify:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        review = CodeReview(
            title="test review lam",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=testUser.id,
            author_id=testUser.id,
            status="completed",
        )
        db.add(review)
        db.flush()
        self.review_id = review.id

        case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-LAM-001",
            module="user",
            title="定位失效+需修改",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()
        self.case_id = case.id

    def test_locator_and_modify_creates_new_version(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.LOCATOR_AND_MODIFY,
            review_id=self.review_id,
        )
        result = apply_single(db, decision)
        assert result.success is True
        assert result.new_case_id is not None

        old_case = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert old_case.lifecycle_status == "locator_broken"

        new_case = db.query(TestCase).filter(TestCase.id == result.new_case_id).first()
        assert new_case is not None
        assert new_case.lifecycle_status == "pending_review"
        assert new_case.parent_case_id == self.case_id

    def test_locator_and_modify_case_not_found(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=99999,
            merged_action=MergedAction.LOCATOR_AND_MODIFY,
            review_id=self.review_id,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_locator_and_modify_none_target_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=None,
            merged_action=MergedAction.LOCATOR_AND_MODIFY,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_locator_and_modify_no_review_id_still_creates(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.LOCATOR_AND_MODIFY,
            review_id=None,
        )
        result = apply_single(db, decision)
        assert result.success is True
        assert result.new_case_id is None

        old_case = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert old_case.lifecycle_status == "locator_broken"


class TestApplyDeprecate:
    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        review = CodeReview(
            title="test review dep",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=testUser.id,
            author_id=testUser.id,
            status="completed",
        )
        db.add(review)
        db.flush()
        self.review_id = review.id

        case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-DEP-001",
            module="user",
            title="待废弃用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()
        self.case_id = case.id

    def test_deprecate_succeeds(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.DEPRECATE,
            review_id=self.review_id,
            deprecate_reason="功能已下线",
        )
        result = apply_single(db, decision)
        assert result.success is True

        case = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert case.lifecycle_status == "deprecated"

    def test_deprecate_missing_review_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.DEPRECATE,
            review_id=None,
            deprecate_reason="功能已下�?,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_deprecate_missing_deprecate_reason(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.DEPRECATE,
            review_id=self.review_id,
            deprecate_reason=None,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_deprecate_case_not_found(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=99999,
            merged_action=MergedAction.DEPRECATE,
            review_id=self.review_id,
            deprecate_reason="功能已下�?,
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_deprecate_none_target_id(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=None,
            merged_action=MergedAction.DEPRECATE,
            review_id=self.review_id,
            deprecate_reason="reason",
        )
        result = apply_single(db, decision)
        assert result.success is False

    def test_deprecate_already_archived(self, db):
        db.query(TestCase).filter(TestCase.id == self.case_id).update(
            {"lifecycle_status": "archived"}
        )
        db.flush()

        decision = ApplyDecision(
            target_kind="test_case",
            target_id=self.case_id,
            merged_action=MergedAction.DEPRECATE,
            review_id=self.review_id,
            deprecate_reason="功能已下�?,
        )
        result = apply_single(db, decision)
        assert result.success is False


class TestApplyAddNew:
    def test_add_new_without_case_data_fails(self, db):
        """case_data 为 None 时因缺少 project_id 返回错误"""
        decision = ApplyDecision(
            target_kind="new_case",
            target_id=None,
            merged_action=MergedAction.ADD_NEW,
            case_data=None,
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "project_id" in str(result.error)

    def test_add_new_missing_project_id_fails(self, db):
        """case_data 不含 project_id 时返回错误"""
        decision = ApplyDecision(
            target_kind="new_case",
            target_id=None,
            merged_action=MergedAction.ADD_NEW,
            case_data={"title": "新用例"},
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "project_id" in str(result.error)

    def test_add_new_triggers_pipeline_and_succeeds(self, db, testProject, monkeypatch):
        """case_data 含 project_id 时触发场景4 Pipeline 并返回成功"""
        from app.pipelines.runner import PipelineRunner
        from app.models.pipeline import Artifact

        run_called = []

        def mock_run(self, ctx):
            run_called.append(True)
            ctx.run.status = "completed"
            artifact = Artifact(
                run_id=ctx.run.id,
                kind="persisted_case_ids",
                content_hash="mock_add_new_hash",
                payload={"case_ids": [101, 102, 103]},
            )
            ctx.set_artifact("persisted_case_ids", artifact)
            ctx.db.commit()

        monkeypatch.setattr(PipelineRunner, "run", mock_run)

        decision = ApplyDecision(
            target_kind="new_case",
            target_id=None,
            merged_action=MergedAction.ADD_NEW,
            case_data={
                "project_id": testProject.id,
                "title": "新增检查用例",
                "candidate_description": "用户注册后邮箱校验",
                "candidate_module": "用户模块",
            },
        )
        result = apply_single(db, decision)
        assert result.success is True
        assert result.deferred is False
        assert len(run_called) == 1

    def test_add_new_pipeline_failure_propagates_error(self, db, testProject, monkeypatch):
        """Pipeline 执行失败时返回错误信息"""
        from app.pipelines.runner import PipelineRunner

        def mock_run_fail(self, ctx):
            ctx.run.status = "failed"
            ctx.run.error = "CaseGeneration step failed: AI timeout"
            ctx.db.commit()

        monkeypatch.setattr(PipelineRunner, "run", mock_run_fail)

        decision = ApplyDecision(
            target_kind="new_case",
            target_id=None,
            merged_action=MergedAction.ADD_NEW,
            case_data={
                "project_id": testProject.id,
                "candidate_description": "会失败的场景",
            },
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "failed" in str(result.error).lower()
        assert "AI timeout" in str(result.error)


class TestApplyConflict:
    def test_conflict_fails_manual(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=1,
            merged_action=MergedAction.CONFLICT,
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "manual" in str(result.error).lower()


class TestApplyPendingReview:
    def test_pending_review_succeeds_deferred(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=1,
            merged_action=MergedAction.PENDING_REVIEW,
        )
        result = apply_single(db, decision)
        assert result.success is True
        assert result.deferred is True
        assert "manual" in str(result.deferred_reason).lower()


class TestApplyUnknownAction:
    def test_unknown_action_fails(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=1,
            merged_action="INVALID_ACTION",
        )
        result = apply_single(db, decision)
        assert result.success is False
        assert "Unknown" in str(result.error)


class TestBatchApply:
    def test_batch_apply_mixed_results(self, db, testProject, testUser):
        review = CodeReview(
            title="test review batch",
            repository="https://github.com/test/repo",
            branch="main",
            reviewer_id=testUser.id,
            author_id=testUser.id,
            status="completed",
        )
        db.add(review)
        db.flush()
        review_id = review.id

        keep_case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-BATCH-001",
            module="user",
            title="批量用例1",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(keep_case)
        db.flush()
        keep_id = keep_case.id

        deprecate_case = TestCase(
            project_id=testProject.id,
            case_no="DAS-TEST-BATCH-002",
            module="user",
            title="批量用例2",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(deprecate_case)
        db.flush()
        deprecate_id = deprecate_case.id

        decisions = [
            ApplyDecision(
                target_kind="test_case",
                target_id=keep_id,
                merged_action=MergedAction.KEEP,
            ),
            ApplyDecision(
                target_kind="test_case",
                target_id=deprecate_id,
                merged_action=MergedAction.DEPRECATE,
                review_id=review_id,
                deprecate_reason="功能已下�?,
            ),
            ApplyDecision(
                target_kind="test_case",
                target_id=99999,
                merged_action=MergedAction.NEEDS_MODIFY,
                review_id=review_id,
            ),
        ]
        results = apply_decisions(db, decisions)
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is True
        assert results[2].success is False

        keep_case_refreshed = db.query(TestCase).filter(TestCase.id == keep_id).first()
        assert keep_case_refreshed.lifecycle_status == "active"

        deprecate_case_refreshed = db.query(TestCase).filter(TestCase.id == deprecate_id).first()
        assert deprecate_case_refreshed.lifecycle_status == "deprecated"

    def test_batch_apply_empty_list(self, db):
        results = apply_decisions(db, [])
        assert len(results) == 0
        assert isinstance(results, list)


class TestApplyDecisionFields:
    def test_decision_confidence_preserved(self, db):
        decision = ApplyDecision(
            target_kind="test_case",
            target_id=1,
            merged_action=MergedAction.KEEP,
            confidence=0.95,
        )
        assert decision.confidence == 0.95

    def test_result_contains_all_fields(self, db):
        result = ApplyResult(
            target_kind="test_case",
            target_id=42,
            action=MergedAction.KEEP,
            success=True,
            new_case_id=None,
            error=None,
        )
        assert result.target_id == 42
        assert result.new_case_id is None
        assert result.error is None

    def test_result_failure_contains_error(self, db):
        result = ApplyResult(
            target_kind="test_case",
            target_id=42,
            action=MergedAction.DEPRECATE,
            success=False,
            error="deprecate_reason is required",
        )
        assert result.success is False
        assert "deprecate_reason" in str(result.error)
