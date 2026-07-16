"""posterior_quality_service 服务层测试。

覆盖范围:
    - compute_posterior_quality: 后验质量分计算（空项目/评审/执行/修改率/完整公式/meets_min_executions）
    - compute_and_persist_posterior: 计算并回填到 TestCase.posterior_quality_score
        - 低于最低执行次数：跳过回填
        - 达到最低执行次数：回填并更新
        - 分数已相同：不重复更新
    - check_review_rejection_alert: 评审拒绝率告警
        - 低于阈值：不触发
        - 高于阈值但评审数不足 5：不触发
        - 高于阈值且评审数 >= 5：触发告警
    - run_posterior_quality_batch: 批量采集
        - 空项目列表
        - 自动检测项目
        - 多项目批量
        - 单项目异常不影响其他项目

DB 使用真实 MySQL 测试库（tests/conftest.py 的 db fixture，事务隔离回滚）。
record_metric 使用独立 Session 提交，会绕过测试事务隔离污染真实库，
故通过 monkeypatch 替换为 no-op（record_metric 已在 test_metrics_service 中覆盖）。
"""
from datetime import timedelta

import pytest

from app.models.project import Project
from app.models.test_case import TestCase, TestCaseExecution
from app.models.user import User
from app.services.posterior_quality_service import (
    REVIEW_REJECTION_RATE_THRESHOLD,
    POSTERIOR_MIN_EXECUTIONS,
    compute_posterior_quality,
    compute_and_persist_posterior,
    check_review_rejection_alert,
    run_posterior_quality_batch,
)
from app.utils.db_time import utcnow


# ==================== Fixtures ====================

@pytest.fixture
def pq_user(db):
    user = User(
        username="pq_cov_user",
        email="pq_cov@test.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    return user


@pytest.fixture
def pq_project(db, pq_user):
    project = Project(name="PQ覆盖项目", user_id=pq_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    return project


@pytest.fixture(autouse=True)
def _stub_record_metric(monkeypatch):
    """禁用 record_metric 的独立 Session 提交，避免污染真实测试库。

    record_metric 已在 test_metrics_service 中覆盖，本测试聚焦后验质量分计算逻辑。
    """
    def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.metrics_service.record_metric", _noop
    )


# ==================== 辅助构造函数 ====================

def _make_case(db, project_id, **kwargs):
    case = TestCase(
        project_id=project_id,
        case_no=kwargs.pop("case_no", f"PQ-{utcnow().strftime('%H%M%S%f')}"),
        module=kwargs.get("module", "默认模块"),
        title=kwargs.get("title", "后验覆盖用例"),
        precondition=kwargs.get("precondition", "前置"),
        steps_json=kwargs.get("steps_json", []),
        expected_result=kwargs.get("expected_result", "预期"),
        priority=kwargs.get("priority", 1),
        case_type=kwargs.get("case_type", "manual"),
        review_status=kwargs.get("review_status", "pending"),
        is_deleted=kwargs.get("is_deleted", False),
        posterior_quality_score=kwargs.get("posterior_quality_score"),
    )
    if "create_time" in kwargs:
        case.create_time = kwargs["create_time"]
    if "update_time" in kwargs:
        case.update_time = kwargs["update_time"]
    db.add(case)
    db.flush()
    db.refresh(case)
    return case


def _make_execution(db, test_case_id, status="passed"):
    execution = TestCaseExecution(
        test_case_id=test_case_id,
        status=status,
    )
    db.add(execution)
    db.flush()
    return execution


# ==================== compute_posterior_quality ====================

class TestComputePosteriorQuality:

    def test_empty_project_returns_zeros(self, db, pq_project):
        result = compute_posterior_quality(db, pq_project.id)
        assert result["project_id"] == pq_project.id
        assert result["total_reviewed"] == 0
        assert result["total_executed"] == 0
        assert result["total_cases"] == 0
        assert result["review_pass_rate"] == 0.0
        assert result["review_rejection_rate"] == 0.0
        assert result["execution_pass_rate"] == 0.0
        assert result["modification_rate"] == 0.0
        # 空项目：posterior = 0.5*0 + 0.3*0 + 0.2*(1-0) = 0.2 → 20.0
        assert result["posterior_quality_score"] == 20.0
        assert result["meets_min_executions"] is False

    def test_review_pass_rate_calculation(self, db, pq_project):
        _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="rejected")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_reviewed"] == 3
        assert result["review_pass_rate"] == round(2 / 3, 4)
        assert result["review_rejection_rate"] == round(1 / 3, 4)

    def test_review_excludes_needs_optimization(self, db, pq_project):
        """needs_optimization 为中间态，不计入评审通过率分母。"""
        _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="needs_optimization")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_reviewed"] == 1
        assert result["review_pass_rate"] == 1.0

    def test_execution_pass_rate_calculation(self, db, pq_project):
        case1 = _make_case(db, pq_project.id, review_status="approved")
        case2 = _make_case(db, pq_project.id, review_status="approved")
        _make_execution(db, case1.id, status="passed")
        _make_execution(db, case1.id, status="passed")
        _make_execution(db, case2.id, status="failed")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_executed"] == 3
        assert result["execution_pass_rate"] == round(2 / 3, 4)

    def test_execution_excludes_other_statuses(self, db, pq_project):
        """pending/running/blocked 不计入执行通过率。"""
        case = _make_case(db, pq_project.id, review_status="approved")
        _make_execution(db, case.id, status="passed")
        _make_execution(db, case.id, status="running")
        _make_execution(db, case.id, status="blocked")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_executed"] == 1
        assert result["execution_pass_rate"] == 1.0

    def test_modification_rate_calculation(self, db, pq_project):
        """update_time > create_time 视为已修改。"""
        now = utcnow()
        past = now - timedelta(days=1)
        _make_case(db, pq_project.id, review_status="approved", create_time=past, update_time=now)
        _make_case(db, pq_project.id, review_status="approved", create_time=now, update_time=now)
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_cases"] == 2
        assert result["modification_rate"] == 0.5

    def test_full_formula_score(self, db, pq_project):
        """完整公式：posterior = 0.5*review + 0.3*exec + 0.2*(1-mod)，转 0-100 分制。"""
        now = utcnow()
        past = now - timedelta(days=1)
        # 2 approved, 1 rejected → review_pass_rate = 2/3
        c1 = _make_case(db, pq_project.id, review_status="approved", create_time=past, update_time=now)
        c2 = _make_case(db, pq_project.id, review_status="approved", create_time=past, update_time=now)
        c3 = _make_case(db, pq_project.id, review_status="rejected", create_time=now, update_time=now)
        # 3 passed, 0 failed → execution_pass_rate = 1.0
        _make_execution(db, c1.id, status="passed")
        _make_execution(db, c2.id, status="passed")
        _make_execution(db, c3.id, status="passed")
        # 2 modified of 3 → modification_rate = 2/3
        result = compute_posterior_quality(db, pq_project.id)
        expected = round(
            (0.5 * (2 / 3) + 0.3 * 1.0 + 0.2 * (1.0 - 2 / 3)) * 100, 2
        )
        assert result["posterior_quality_score"] == expected

    def test_meets_min_executions_flag(self, db, pq_project):
        case = _make_case(db, pq_project.id, review_status="approved")
        for _ in range(POSTERIOR_MIN_EXECUTIONS):
            _make_execution(db, case.id, status="passed")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_executed"] == POSTERIOR_MIN_EXECUTIONS
        assert result["meets_min_executions"] is True

    def test_below_min_executions_flag(self, db, pq_project):
        case = _make_case(db, pq_project.id, review_status="approved")
        _make_execution(db, case.id, status="passed")
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_executed"] == 1
        assert result["meets_min_executions"] is False

    def test_deleted_cases_excluded(self, db, pq_project):
        _make_case(db, pq_project.id, review_status="approved", is_deleted=True)
        _make_case(db, pq_project.id, review_status="approved", is_deleted=False)
        result = compute_posterior_quality(db, pq_project.id)
        assert result["total_reviewed"] == 1
        assert result["total_cases"] == 1


# ==================== compute_and_persist_posterior ====================

class TestComputeAndPersistPosterior:

    def test_skip_persist_when_below_min_executions(self, db, pq_project):
        case = _make_case(db, pq_project.id, review_status="approved")
        _make_execution(db, case.id, status="passed")
        result = compute_and_persist_posterior(db, pq_project.id)
        assert result["meets_min_executions"] is False
        db.refresh(case)
        assert case.posterior_quality_score is None

    def test_persist_score_when_meets_min_executions(self, db, pq_project):
        case = _make_case(db, pq_project.id, review_status="approved")
        for _ in range(POSTERIOR_MIN_EXECUTIONS):
            _make_execution(db, case.id, status="passed")
        result = compute_and_persist_posterior(db, pq_project.id)
        assert result["meets_min_executions"] is True
        db.refresh(case)
        assert case.posterior_quality_score == result["posterior_quality_score"]

    def test_persist_skips_unchanged_score(self, db, pq_project):
        """分数已相同时不重复赋值（updated 计数为 0 仍 flush）。"""
        case = _make_case(db, pq_project.id, review_status="approved")
        for _ in range(POSTERIOR_MIN_EXECUTIONS):
            _make_execution(db, case.id, status="passed")
        # 第一次回填
        result1 = compute_and_persist_posterior(db, pq_project.id)
        score = result1["posterior_quality_score"]
        db.refresh(case)
        assert case.posterior_quality_score == score
        # 第二次回填，分数应保持不变
        result2 = compute_and_persist_posterior(db, pq_project.id)
        assert result2["posterior_quality_score"] == score
        db.refresh(case)
        assert case.posterior_quality_score == score

    def test_persist_updates_all_non_deleted_cases(self, db, pq_project):
        c1 = _make_case(db, pq_project.id, review_status="approved")
        c2 = _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="approved", is_deleted=True)
        for _ in range(POSTERIOR_MIN_EXECUTIONS):
            _make_execution(db, c1.id, status="passed")
        result = compute_and_persist_posterior(db, pq_project.id)
        score = result["posterior_quality_score"]
        db.refresh(c1)
        db.refresh(c2)
        assert c1.posterior_quality_score == score
        assert c2.posterior_quality_score == score


# ==================== check_review_rejection_alert ====================

class TestCheckReviewRejectionAlert:

    def test_no_alert_when_below_threshold(self, db, pq_project):
        for _ in range(6):
            _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="rejected")
        triggered = check_review_rejection_alert(db, pq_project.id)
        assert triggered is False

    def test_no_alert_when_fewer_than_five_reviews(self, db, pq_project):
        """拒绝率超阈值但评审总数 < 5 时不告警。"""
        _make_case(db, pq_project.id, review_status="approved")
        _make_case(db, pq_project.id, review_status="rejected")
        _make_case(db, pq_project.id, review_status="rejected")
        triggered = check_review_rejection_alert(db, pq_project.id)
        assert triggered is False

    def test_alert_triggered_when_above_threshold_and_min_reviews(self, db, pq_project):
        """拒绝率 > 30% 且评审数 >= 5 时触发告警。"""
        for _ in range(3):
            _make_case(db, pq_project.id, review_status="approved")
        for _ in range(4):
            _make_case(db, pq_project.id, review_status="rejected")
        triggered = check_review_rejection_alert(db, pq_project.id)
        assert triggered is True

    def test_no_alert_on_empty_project(self, db, pq_project):
        triggered = check_review_rejection_alert(db, pq_project.id)
        assert triggered is False

    def test_threshold_boundary_not_triggered(self, db, pq_project):
        """拒绝率恰好等于 30% 时不触发（使用 > 而非 >=）。"""
        for _ in range(7):
            _make_case(db, pq_project.id, review_status="approved")
        for _ in range(3):
            _make_case(db, pq_project.id, review_status="rejected")
        triggered = check_review_rejection_alert(db, pq_project.id)
        assert triggered is False


# ==================== run_posterior_quality_batch ====================

class TestRunPosteriorQualityBatch:

    def test_empty_project_list_returns_empty(self, db):
        results = run_posterior_quality_batch(db, project_ids=[])
        assert results == []

    def test_auto_detect_empty_returns_empty(self, db, pq_project):
        """无评审记录的项目不被自动检测。"""
        results = run_posterior_quality_batch(db, project_ids=None)
        # pq_project 无 approved/rejected 用例，不应被检测
        assert all(r.get("project_id") != pq_project.id for r in results)

    def test_auto_detect_with_reviewed_project(self, db, pq_project):
        _make_case(db, pq_project.id, review_status="approved")
        results = run_posterior_quality_batch(db, project_ids=None)
        matched = [r for r in results if r.get("project_id") == pq_project.id]
        assert len(matched) == 1
        assert "posterior_quality_score" in matched[0]

    def test_explicit_project_ids(self, db, pq_project):
        results = run_posterior_quality_batch(db, project_ids=[pq_project.id])
        assert len(results) == 1
        assert results[0]["project_id"] == pq_project.id

    def test_multiple_projects(self, db, pq_user):
        proj1 = Project(name="PQ批量1", user_id=pq_user.id)
        proj2 = Project(name="PQ批量2", user_id=pq_user.id)
        db.add_all([proj1, proj2])
        db.flush()
        _make_case(db, proj1.id, review_status="approved")
        _make_case(db, proj2.id, review_status="rejected")
        results = run_posterior_quality_batch(db, project_ids=[proj1.id, proj2.id])
        assert len(results) == 2
        ids = {r["project_id"] for r in results}
        assert ids == {proj1.id, proj2.id}

    def test_error_in_one_project_does_not_block_others(self, db, pq_project):
        """不存在的项目返回零分结果（不报错），其他项目仍正常采集。"""
        results = run_posterior_quality_batch(
            db, project_ids=[99999999, pq_project.id]
        )
        assert len(results) == 2
        ids = {r["project_id"] for r in results}
        assert ids == {99999999, pq_project.id}
        # 两个项目都应正常返回（非存在项目返回零分）
        for r in results:
            assert "posterior_quality_score" in r
