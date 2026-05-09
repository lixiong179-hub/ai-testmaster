"""后验质量�?�?数据库集成测�?
覆盖 fetch_posterior_inputs / backfill_posterior_scores �?数据库交互、批量更新、异常路径�?"""
import pytest

from app.models.test_case import TestCase, TestCaseExecution
from app.models.review import ReviewDecision, IterationReview
from app.models.iteration import Iteration
from app.models.enums import ReviewStatus
from app.services.posterior_score_service import (
    fetch_posterior_inputs,
    backfill_posterior_scores,
)


class TestFetchPosteriorInputs:
    """数据库查询测�?""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        case = TestCase(
            project_id=testProject.id,
            case_no="POST-INPUT-001",
            module="posterior",
            title="后验测试用例",
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

        for status in ["passed", "passed", "failed"]:
            exec_record = TestCaseExecution(
                test_case_id=self.case_id,
                status=status,
            )
            db.add(exec_record)
        db.flush()

    def test_fetch_returns_inputs(self, db):
        inputs = fetch_posterior_inputs(db, case_ids=[self.case_id])
        assert len(inputs) >= 1
        matched = [i for i in inputs if i.case_id == self.case_id]
        assert len(matched) == 1
        inp = matched[0]
        assert inp.execution_total == 3
        assert inp.execution_passed_count == 2

    def test_fetch_no_match_returns_empty(self, db):
        inputs = fetch_posterior_inputs(db, case_ids=[-9999])
        assert len(inputs) == 0

    def test_fetch_empty_case_ids_returns_empty(self, db):
        inputs = fetch_posterior_inputs(db, case_ids=[])
        assert len(inputs) == 0

    def test_fetch_none_case_ids_queries_all(self, db):
        inputs = fetch_posterior_inputs(db, case_ids=None)
        assert len(inputs) >= 1


class TestBackfillPosteriorScores:
    """回填集成测试"""

    @pytest.fixture(autouse=True)
    def setup_data(self, db, testProject, testUser):
        case = TestCase(
            project_id=testProject.id,
            case_no="POST-BACKFILL-001",
            module="posterior",
            title="后验回填用例",
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

        for status in ["passed", "passed", "passed", "failed"]:
            exec_record = TestCaseExecution(
                test_case_id=self.case_id,
                status=status,
            )
            db.add(exec_record)
        db.flush()

        iteration = Iteration(
            project_id=testProject.id,
            name="posterior-test-iter",
            version="v1.0",
            status="finalized",
        )
        db.add(iteration)
        db.flush()
        self.iteration_id = iteration.id

        review = IterationReview(
            iteration_id=self.iteration_id,
            kind="backward_scan",
            status=ReviewStatus.FINALIZED.value,
        )
        db.add(review)
        db.flush()
        self.review_id = review.id

        for verdict in ["keep", "keep", "modify"]:
            decision = ReviewDecision(
                review_id=self.review_id,
                target_kind="case",
                target_id=self.case_id,
                final_verdict=verdict,
            )
            db.add(decision)
        db.flush()

    def test_backfill_writes_score(self, db):
        results = backfill_posterior_scores(db, case_ids=[self.case_id])
        assert len(results) >= 1
        matched = [r for r in results if r.case_id == self.case_id]
        assert len(matched) == 1
        result = matched[0]
        assert result.score is not None
        assert result.skipped is False
        assert 0 <= result.score <= 100

        db.flush()
        updated = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        assert updated.posterior_quality_score == result.score

    def test_backfill_skip_insufficient_executions(self, db, testProject):
        case2 = TestCase(
            project_id=testProject.id,
            case_no="POST-BACKFILL-002",
            module="posterior",
            title="执行不足用例",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case2)
        db.flush()
        case2_id = case2.id

        exec_record = TestCaseExecution(
            test_case_id=case2_id,
            status="passed",
        )
        db.add(exec_record)
        db.flush()

        results = backfill_posterior_scores(db, case_ids=[case2_id])
        matched = [r for r in results if r.case_id == case2_id]
        assert len(matched) == 1
        assert matched[0].skipped is True
        assert matched[0].score is None

    def test_backfill_no_cases_returns_empty(self, db):
        results = backfill_posterior_scores(db, case_ids=[-9999])
        assert len(results) == 0

    def test_backfill_empty_case_ids_returns_empty(self, db):
        results = backfill_posterior_scores(db, case_ids=[])
        assert len(results) == 0

    def test_backfill_batch_update_same_score(self, db, testProject):
        """验证相同 score 的用例被批量更新"""
        case2 = TestCase(
            project_id=testProject.id,
            case_no="POST-BACKFILL-BATCH",
            module="posterior",
            title="批量更新测试",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case2)
        db.flush()
        case2_id = case2.id

        for _ in range(4):
            db.add(TestCaseExecution(test_case_id=case2_id, status="passed"))
        db.flush()

        results = backfill_posterior_scores(db, case_ids=[self.case_id, case2_id])
        assert len(results) == 2
        for r in results:
            assert r.score is not None

        db.flush()
        c1 = db.query(TestCase).filter(TestCase.id == self.case_id).first()
        c2 = db.query(TestCase).filter(TestCase.id == case2_id).first()
        assert c1.posterior_quality_score is not None
        assert c2.posterior_quality_score is not None
