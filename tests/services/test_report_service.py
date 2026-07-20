"""报告服务单元测试 - ReportService"""
import pytest
from datetime import datetime
from app.services.report_service import ReportService
from app.crud.test_result import create_test_result
from app.crud.test_report import create_test_report, get_test_report_by_id
from app.models.project import Project
from app.models.report import TestReport
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.schemas.test_report import TestReportCreate

# pytestmark = pytest.mark.skip(reason="数据库DDL不兼容")  # 临时移除排查


@pytest.fixture
def test_project(db, testUser):
    project = Project(
        name="report_svc_project",
        user_id=testUser.id,
        description="project for report service tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def test_task(db, test_project, testUser):
    task = TestTask(
        task_name="svc_test_task",
        project_id=test_project.id,
        case_ids=[],
        executor_id=testUser.id,
        status=0,
    )
    db.add(task)
    db.flush()
    return task


@pytest.fixture
def test_case_obj(db, test_project):
    tc = TestCase(
        case_no="SVC-TC-001",
        project_id=test_project.id,
        module="报告模块",
        title="报告测试用例",
        precondition="无",
        steps_json=[{"step": "步骤1", "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="API",
    )
    db.add(tc)
    db.flush()
    return tc


def _make_result(db, test_task, test_case_obj, **kwargs):
    defaults = dict(
        task_id=test_task.id,
        project_id=test_task.project_id,
        case_id=test_case_obj.id,
        case_no=test_case_obj.case_no,
        exec_status=0,
    )
    defaults.update(kwargs)
    return create_test_result(db, **defaults)


class TestCalculateStatistics:
    def test_empty_results(self):
        stats = ReportService._calculate_statistics([])
        assert stats["total"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["blocked"] == 0
        assert stats["pass_rate"] == 0

    def test_all_passed(self, db, test_task, test_case_obj):
        results = []
        for i in range(3):
            r = _make_result(db, test_task, test_case_obj, exec_status=1)
            results.append(r)
        stats = ReportService._calculate_statistics(results)
        assert stats["total"] == 3
        assert stats["passed"] == 3
        assert stats["pass_rate"] == 100.0

    def test_mixed_results(self, db, test_task, test_case_obj):
        r1 = _make_result(db, test_task, test_case_obj, exec_status=1)
        r2 = _make_result(db, test_task, test_case_obj, exec_status=2)
        r3 = _make_result(db, test_task, test_case_obj, exec_status=3)
        r4 = _make_result(db, test_task, test_case_obj, exec_status=0)
        stats = ReportService._calculate_statistics([r1, r2, r3, r4])
        assert stats["total"] == 4
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["blocked"] == 1
        assert stats["pass_rate"] == 25.0


class TestGenerateSummary:
    def test_basic_summary(self):
        stats = {"total": 10, "passed": 8, "failed": 1, "blocked": 1, "pass_rate": 80.0}
        summary = ReportService._generate_summary(stats)
        assert "10" in summary
        assert "8" in summary
        assert "80.0" in summary

    def test_zero_summary(self):
        stats = {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "pass_rate": 0}
        summary = ReportService._generate_summary(stats)
        assert "0" in summary


class TestGenerateReportContent:
    def test_content_structure(self, db, test_task, test_case_obj):
        r = _make_result(db, test_task, test_case_obj, exec_status=1)
        stats = {"total": 1, "passed": 1, "failed": 0, "blocked": 0, "pass_rate": 100.0}
        content = ReportService._generate_report_content([r], stats)
        assert "test_cases" in content
        assert "statistics" in content
        assert "environment" in content
        assert content["statistics"]["total"] == 1

    def test_status_mapping(self, db, test_task, test_case_obj):
        r0 = _make_result(db, test_task, test_case_obj, exec_status=0)
        r1 = _make_result(db, test_task, test_case_obj, exec_status=1)
        r2 = _make_result(db, test_task, test_case_obj, exec_status=2)
        r3 = _make_result(db, test_task, test_case_obj, exec_status=3)
        stats = {"total": 4, "passed": 1, "failed": 1, "blocked": 1, "pass_rate": 25.0}
        content = ReportService._generate_report_content([r0, r1, r2, r3], stats)
        statuses = [tc["status"] for tc in content["test_cases"]]
        assert "pending" in statuses
        assert "passed" in statuses
        assert "failed" in statuses
        assert "blocked" in statuses


class TestGenerateReport:
    def test_generate_basic(self, db, test_project, test_task, test_case_obj):
        _make_result(db, test_task, test_case_obj, exec_status=1)
        _make_result(db, test_task, test_case_obj, exec_status=2)
        report = ReportService.generate_report(
            db, test_project.id, test_task_id=test_task.id, name="测试报告"
        )
        assert report is not None
        assert report.name == "测试报告"
        assert report.total_cases == 2
        assert report.passed_cases == 1
        assert report.failed_cases == 1
        assert report.status == "completed"
        assert report.summary is not None

    def test_generate_default_name(self, db, test_project, test_task, test_case_obj):
        _make_result(db, test_task, test_case_obj, exec_status=1)
        report = ReportService.generate_report(
            db, test_project.id, test_task_id=test_task.id
        )
        assert "测试报告_" in report.name

    def test_generate_no_results(self, db, test_project, test_task):
        report = ReportService.generate_report(
            db, test_project.id, test_task_id=test_task.id, name="空报告"
        )
        assert report.total_cases == 0


class TestGetReportDetail:
    def test_not_found(self, db, test_project):
        with pytest.raises(ValueError, match="not found"):
            ReportService.get_report_detail(db, 99999, test_project.id)

    def test_no_content(self, db, test_project):
        report_data = TestReportCreate(
            name="空内容报告", project_id=test_project.id
        )
        report = create_test_report(db, report_data, user_id=1)
        with pytest.raises(ValueError, match="content not found"):
            ReportService.get_report_detail(db, report.id, test_project.id)
