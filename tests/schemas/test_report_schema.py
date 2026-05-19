import pytest
from app.schemas.test_report import (
    TestReportBase,
    TestReportCreate,
    TestReportUpdate,
    TestCaseResult,
    TestReportDetail,
    TestReportResponse,
    TestReportList,
    ReportExportRequest,
    ReportGenerateRequest,
)


class TestTestReportBase:
    def test_create(self):
        base = TestReportBase(name="报告", project_id=1)
        assert base.name == "报告"
        assert base.project_id == 1
        assert base.description is None
        assert base.test_task_id is None

    def test_with_optional_fields(self):
        base = TestReportBase(
            name="报告", project_id=1,
            description="描述", test_task_id=2,
        )
        assert base.description == "描述"
        assert base.test_task_id == 2


class TestTestReportCreate:
    def test_inherits_base(self):
        create = TestReportCreate(name="创建报告", project_id=1)
        assert create.name == "创建报告"


class TestTestReportUpdate:
    def test_all_optional(self):
        update = TestReportUpdate()
        assert update.name is None
        assert update.status is None

    def test_partial_update(self):
        update = TestReportUpdate(name="新名称")
        assert update.name == "新名称"
        assert update.description is None


class TestTestCaseResult:
    def test_create(self):
        result = TestCaseResult(case_id=1, case_name="登录测试", status="passed")
        assert result.case_id == 1
        assert result.execution_time is None
        assert result.steps is None

    def test_with_all_fields(self):
        result = TestCaseResult(
            case_id=1, case_name="测试", status="failed",
            execution_time=1.5, error_message="超时",
            steps=[{"step": 1, "action": "click"}],
        )
        assert result.error_message == "超时"
        assert len(result.steps) == 1


class TestTestReportDetail:
    def test_create(self):
        detail = TestReportDetail(
            test_cases=[],
            statistics={"total": 0},
        )
        assert len(detail.test_cases) == 0
        assert detail.environment is None

    def test_with_environment(self):
        detail = TestReportDetail(
            test_cases=[],
            statistics={"total": 1},
            environment={"platform": "Linux"},
        )
        assert detail.environment["platform"] == "Linux"


class TestReportExportRequest:
    def test_pdf_format(self):
        req = ReportExportRequest(report_id=1, format="pdf")
        assert req.format == "pdf"

    def test_html_format(self):
        req = ReportExportRequest(report_id=1, format="html")
        assert req.format == "html"

    def test_invalid_format(self):
        with pytest.raises(Exception):
            ReportExportRequest(report_id=1, format="docx")


class TestReportGenerateRequest:
    def test_create(self):
        req = ReportGenerateRequest(project_id=1, name="生成报告")
        assert req.test_task_id is None

    def test_with_task_id(self):
        req = ReportGenerateRequest(project_id=1, name="报告", test_task_id=2)
        assert req.test_task_id == 2
