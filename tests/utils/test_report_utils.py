import pytest
from app.utils.report_utils import ReportUtils


class TestReportUtilsGenerateHtml:
    def test_generate_html_report_basic(self):
        report_data = {
            "statistics": {
                "total": 10,
                "passed": 7,
                "failed": 2,
                "skipped": 1,
                "pass_rate": 70,
            },
            "test_cases": [
                {
                    "case_id": "TC001",
                    "case_name": "登录测试",
                    "status": "passed",
                    "error_message": "",
                },
                {
                    "case_id": "TC002",
                    "case_name": "注册测试",
                    "status": "failed",
                    "error_message": "超时",
                },
            ],
            "summary": "测试摘要",
            "environment": {
                "generate_time": "2026-01-01T00:00:00",
                "platform": "Linux",
                "version": "2.0.0",
            },
        }
        result = ReportUtils.generate_html_report(report_data, "测试报告")
        assert "<html" in result
        assert "测试报告" in result
        assert "10" in result
        assert "7" in result
        assert "2" in result
        assert "1" in result
        assert "70" in result
        assert "TC001" in result
        assert "TC002" in result
        assert "超时" in result
        assert "Linux" in result
        assert "2.0.0" in result

    def test_generate_html_report_empty_cases(self):
        report_data = {
            "statistics": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "pass_rate": 0},
            "test_cases": [],
            "summary": "",
            "environment": {},
        }
        result = ReportUtils.generate_html_report(report_data, "空报告")
        assert "空报告" in result
        assert "0" in result

    def test_generate_html_report_missing_statistics(self):
        report_data = {
            "test_cases": [],
            "summary": "无统计",
        }
        result = ReportUtils.generate_html_report(report_data, "部分数据报告")
        assert "部分数据报告" in result

    def test_generate_html_report_case_with_error_message(self):
        report_data = {
            "statistics": {"total": 1, "passed": 0, "failed": 1, "skipped": 0, "pass_rate": 0},
            "test_cases": [
                {"case_id": "TC001", "case_name": "失败用例", "status": "failed", "error_message": "断言失败"},
            ],
            "summary": "",
        }
        result = ReportUtils.generate_html_report(report_data, "错误报告")
        assert "error-message" in result
        assert "断言失败" in result

    def test_generate_html_report_case_without_error_message(self):
        report_data = {
            "statistics": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "pass_rate": 100},
            "test_cases": [
                {"case_id": "TC001", "case_name": "通过用例", "status": "passed"},
            ],
            "summary": "",
        }
        result = ReportUtils.generate_html_report(report_data, "通过报告")
        assert "status-passed" in result


class TestReportUtilsPieChart:
    def test_generate_pie_chart_returns_base64(self):
        result = ReportUtils._generate_pie_chart([7, 2, 1], ["通过", "失败", "跳过"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_pie_chart_empty_data(self):
        result = ReportUtils._generate_pie_chart([0, 0, 0], ["通过", "失败", "跳过"])
        assert isinstance(result, str)
        assert len(result) > 0


class TestReportUtilsExportReport:
    def test_export_html_format(self):
        report_data = {
            "statistics": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "pass_rate": 100},
            "test_cases": [],
            "summary": "",
        }
        content, content_type, filename = ReportUtils.export_report(report_data, "报告", "html")
        assert content_type == "text/html"
        assert filename == "报告.html"
        assert "<html" in content

    def test_export_unsupported_format(self):
        with pytest.raises(ValueError, match="Unsupported format"):
            ReportUtils.export_report({}, "报告", "xlsx")

    def test_export_pdf_format_without_weasyprint(self):
        try:
            import weasyprint
            content, content_type, filename = ReportUtils.export_report(
                {"statistics": {"total": 0}, "test_cases": [], "summary": ""}, "报告", "pdf"
            )
            assert content_type == "application/pdf"
            assert filename == "报告.pdf"
        except (ImportError, OSError):
            with pytest.raises((ImportError, OSError)):
                ReportUtils.export_report(
                    {"statistics": {"total": 0}, "test_cases": [], "summary": ""}, "报告", "pdf"
                )


class TestReportUtilsGeneratePdf:
    def test_generate_pdf_without_weasyprint(self):
        try:
            import weasyprint
            result = ReportUtils.generate_pdf_report("<html><body>test</body></html>")
            assert isinstance(result, bytes)
        except (ImportError, OSError):
            with pytest.raises((ImportError, OSError)):
                ReportUtils.generate_pdf_report("<html><body>test</body></html>")
