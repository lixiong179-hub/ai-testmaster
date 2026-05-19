import pytest
from app.services.report_service import ReportService
from app.models.enums import ExecStatus


def _make_case(db, testProject, case_no, title):
    from app.models.test_case import TestCase
    case = TestCase(
        project_id=testProject.id, title=title,
        case_no=case_no, lifecycle_status="active",
        module="报告模块", precondition="无",
        steps_json=[{"step": 1, "action": "操作", "param": ""}],
        expected_result="成功", priority=2, case_type="UI",
    )
    db.add(case)
    db.flush()
    return case


def _make_task(db, testProject, testUser):
    from app.crud.test_task import create_test_task
    task = create_test_task(db, "报告任务", testProject.id, [1], testUser.id)
    return task


class TestCalculateStatistics:
    def test_empty_results(self):
        result = ReportService._calculate_statistics([])
        assert result["total"] == 0
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["blocked"] == 0
        assert result["pass_rate"] == 0

    def test_all_passed(self, db, testProject, testUser):
        from app.models.test_result import TestResult
        case = _make_case(db, testProject, "STAT-001", "stat_case")
        task = _make_task(db, testProject, testUser)
        r1 = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.PASSED, task_id=task.id,
        )
        r2 = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.PASSED, task_id=task.id,
        )
        db.add_all([r1, r2])
        db.flush()
        stats = ReportService._calculate_statistics([r1, r2])
        assert stats["total"] == 2
        assert stats["passed"] == 2
        assert stats["pass_rate"] == 100.0

    def test_mixed_results(self, db, testProject, testUser):
        from app.models.test_result import TestResult
        case = _make_case(db, testProject, "MIX-001", "mix_case")
        task = _make_task(db, testProject, testUser)
        r1 = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.PASSED, task_id=task.id,
        )
        r2 = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.FAILED, task_id=task.id,
        )
        r3 = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.BLOCKED, task_id=task.id,
        )
        db.add_all([r1, r2, r3])
        db.flush()
        stats = ReportService._calculate_statistics([r1, r2, r3])
        assert stats["total"] == 3
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["blocked"] == 1
        assert stats["pass_rate"] == pytest.approx(33.33, rel=0.01)


class TestGenerateSummary:
    def test_summary_text(self):
        stats = {"total": 10, "passed": 8, "failed": 1, "blocked": 1, "pass_rate": 80.0}
        summary = ReportService._generate_summary(stats)
        assert "10" in summary
        assert "8" in summary
        assert "80.0" in summary

    def test_zero_total(self):
        stats = {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "pass_rate": 0}
        summary = ReportService._generate_summary(stats)
        assert "0" in summary


class TestGenerateReportContent:
    def test_content_structure(self, db, testProject, testUser):
        from app.models.test_result import TestResult
        case = _make_case(db, testProject, "CONT-001", "content_case")
        task = _make_task(db, testProject, testUser)
        r = TestResult(
            project_id=testProject.id, case_id=case.id, case_no=case.case_no,
            exec_status=ExecStatus.PASSED, task_id=task.id,
        )
        db.add(r)
        db.flush()
        stats = ReportService._calculate_statistics([r])
        content = ReportService._generate_report_content([r], stats)
        assert "test_cases" in content
        assert "statistics" in content
        assert "environment" in content
        assert content["environment"]["platform"] == "AI TestMaster"

    def test_empty_results(self):
        stats = {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "pass_rate": 0}
        content = ReportService._generate_report_content([], stats)
        assert len(content["test_cases"]) == 0


class TestGetReportDetail:
    def test_report_not_found(self, db):
        with pytest.raises(ValueError, match="Report not found"):
            ReportService.get_report_detail(db, 99999, 1)

    def test_report_no_content(self, db, testProject):
        from app.crud.test_report import create_test_report
        from app.schemas.test_report import TestReportCreate
        data = TestReportCreate(
            name="empty_report", description="test",
            project_id=testProject.id, test_task_id=None,
        )
        report = create_test_report(db, data, user_id=1)
        with pytest.raises(ValueError, match="Report content not found"):
            ReportService.get_report_detail(db, report.id, testProject.id)
