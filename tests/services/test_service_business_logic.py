"""Service层业务逻辑测试 - 扩展覆盖率"""
import pytest
from datetime import datetime
from app.services.case_quality.models import CaseQualityAnalysisRequest, CaseQualityReport
from app.services.cost_statistics.models import CostStatisticsRequest, CostReportData
from app.services.visibility_config.models import ResourceVisibilityRequest
from app.services.video.models import VideoRecordStatus
from app.services.execution_replay.models import SessionStatus, ActionType
from app.services.test_execution_engine.models import ExecutionConfig, ExecutionResult


class TestCaseQualityModels:
    def test_case_quality_analysis_request_creation(self):
        req = CaseQualityAnalysisRequest(
            project_id=1,
            test_case_ids=[1, 2, 3],
            include_complexity=True,
            include_redundancy=True,
            include_coverage=True
        )
        assert req.project_id == 1
        assert req.test_case_ids == [1, 2, 3]
        assert req.include_complexity is True
        assert req.include_redundancy is True
        assert req.include_coverage is True

    def test_case_quality_report_creation(self):
        report = CaseQualityReport(
            project_id=1,
            total_cases=100,
            complexity_score=75.5,
            redundancy_score=80.0,
            coverage_score=90.0,
            overall_score=81.8,
            suggestions=["优化复杂用例", "减少重复步骤"]
        )
        assert report.project_id == 1
        assert report.total_cases == 100
        assert report.complexity_score == 75.5
        assert report.redundancy_score == 80.0
        assert report.coverage_score == 90.0
        assert report.overall_score == 81.8
        assert len(report.suggestions) == 2


class TestCostStatisticsModels:
    def test_cost_statistics_request_creation(self):
        req = CostStatisticsRequest(
            project_id=1,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            group_by="day"
        )
        assert req.project_id == 1
        assert req.group_by == "day"

    def test_cost_report_data_creation(self):
        report = CostReportData(
            project_id=1,
            total_cost=125.50,
            total_tokens=50000,
            avg_cost_per_request=0.025,
            daily_costs=[{"date": "2024-01-01", "cost": 5.0}]
        )
        assert report.project_id == 1
        assert report.total_cost == 125.50
        assert report.total_tokens == 50000
        assert report.avg_cost_per_requests == 0.025
        assert len(report.daily_costs) == 1


class TestVisibilityConfigModels:
    def test_resource_visibility_request_creation(self):
        req = ResourceVisibilityRequest(
            resource_type="test_case",
            resource_id=10,
            user_id=100,
            user_roles=["admin"]
        )
        assert req.resource_type == "test_case"
        assert req.resource_id == 10
        assert req.user_id == 100
        assert "admin" in req.user_roles


class TestVideoModels:
    def test_video_record_status_values(self):
        assert VideoRecordStatus.PENDING == "pending"
        assert VideoRecordStatus.RECORDING == "recording"
        assert VideoRecordStatus.COMPLETED == "completed"
        assert VideoRecordStatus.FAILED == "failed"


class TestExecutionReplayModels:
    def test_session_status_values(self):
        assert SessionStatus.PENDING == "pending"
        assert SessionStatus.PLAYING == "playing"
        assert SessionStatus.PAUSED == "paused"
        assert SessionStatus.COMPLETED == "completed"

    def test_action_type_values(self):
        assert ActionType.CLICK == "click"
        assert ActionType.INPUT == "input"
        assert ActionType.SCROLL == "scroll"
        assert ActionType.NAVIGATE == "navigate"


class TestTestExecutionEngineModels:
    def test_execution_config_creation(self):
        config = ExecutionConfig(
            timeout=30,
            retry_count=3,
            screenshot_on_failure=True
        )
        assert config.timeout == 30
        assert config.retry_count == 3
        assert config.screenshot_on_failure is True

    def test_execution_result_creation(self):
        result = ExecutionResult(
            status="success",
            duration=120.5,
            steps_passed=10,
            steps_failed=2
        )
        assert result.status == "success"
        assert result.duration == 120.5
        assert result.steps_passed == 10
        assert result.steps_failed == 2


class TestConstants:
    def test_core_constants_exist(self):
        from app.core.constants import TestTaskStatus, TestCaseStatus
        assert hasattr(TestTaskStatus, 'PENDING')
        assert hasattr(TestTaskStatus, 'RUNNING')
        assert hasattr(TestTaskStatus, 'COMPLETED')
        assert hasattr(TestTaskStatus, 'FAILED')
        assert hasattr(TestCaseStatus, 'DRAFT')
        assert hasattr(TestCaseStatus, 'ENABLED')
        assert hasattr(TestCaseStatus, 'DISABLED')

    def test_http_status_constants(self):
        from app.core.constants import HTTPStatus
        assert HTTPStatus.OK == 200
        assert HTTPStatus.CREATED == 201
        assert HTTPStatus.BAD_REQUEST == 400
        assert HTTPStatus.UNAUTHORIZED == 401
        assert HTTPStatus.FORBIDDEN == 403
        assert HTTPStatus.NOT_FOUND == 404


class TestUtilsFunctions:
    def test_file_utils_functions(self):
        from app.utils.file_utils import ensure_dir, clean_old_files
        assert callable(ensure_dir)
        assert callable(clean_old_files)

    def test_crypto_functions(self):
        from app.utils.crypto import encrypt_password, verify_password
        assert callable(encrypt_password)
        assert callable(verify_password)


class TestServiceBackwardCompatibility:
    def test_case_generation_service_import(self):
        from app.services.case_generation import TestCaseGenerationService
        assert TestCaseGenerationService is not None

    def test_precondition_service_import(self):
        from app.services.precondition import PreconditionExecutorService
        assert PreconditionExecutorService is not None

    def test_task_service_import(self):
        from app.services.task_service import TestTaskService
        assert TestTaskService is not None

    def test_ui_spec_parser_import(self):
        from app.services.ui_spec_parser import UISpecParserService
        assert UISpecParserService is not None

    def test_link_fetcher_import(self):
        from app.services.link_fetcher import LinkFetcherService
        assert LinkFetcherService is not None

    def test_test_data_import(self):
        from app.services.test_data import TestDataGenerator
        assert TestDataGenerator is not None

    def test_video_service_import(self):
        from app.services.video import VideoRecordService
        assert VideoRecordService is not None

    def test_cost_statistics_import(self):
        from app.services.cost_statistics import CostStatisticsService
        assert CostStatisticsService is not None

    def test_mobile_ai_executor_import(self):
        from app.services.mobile_ai_executor import MobileAIExecutor
        assert MobileAIExecutor is not None

    def test_case_quality_import(self):
        from app.services.case_quality import CaseQualityAnalyzer
        assert CaseQualityAnalyzer is not None

    def test_visibility_config_import(self):
        from app.services.visibility_config import VisibilityConfigService
        assert VisibilityConfigService is not None

    def test_element_locator_import(self):
        from app.services.element_locator import ElementLocatorService
        assert ElementLocatorService is not None

    def test_execution_replay_import(self):
        from app.services.execution_replay import ExecutionReplayService
        assert ExecutionReplayService is not None


class TestNoStrLeakageInServiceReturns:
    def test_error_messages_sanitized(self):
        """验证服务层错误消息不包含敏感异常信息"""
        import inspect
        from app.services.case_quality.analyzer_mixin import CaseQualityAnalyzerMixin
        from app.services.cost_statistics.query_mixin import CostStatisticsQueryMixin
        from app.services.visibility_config.core_mixin import VisibilityConfigCoreMixin
        
        for cls in [CaseQualityAnalyzerMixin, CostStatisticsQueryMixin, VisibilityConfigCoreMixin]:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if not name.startswith('_'):
                    source = inspect.getsource(method)
                    assert 'str(e)' not in source or 'str(e)' in source and 'desensitiz' in source.lower() or 'f"执行失败"' in source, f"Method {name} in {cls.__name__} may leak exception info"


class TestFileLineLimits:
    def test_all_service_files_under_300_lines(self):
        """验证所有Service文件不超过300行"""
        import subprocess
        result = subprocess.run(
            ['powershell', '-Command', '''
                Get-ChildItem -Path "app/services/**/*.py" -Recurse |
                Where-Object { $_.Length -gt 0 } |
                ForEach-Object {
                    $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
                    if ($lines -gt 300) {
                        Write-Output "$($_.FullName): $lines lines"
                    }
                }
            '''],
            capture_output=True,
            text=True,
            cwd="d:/PythonFile/ai-testmaster"
        )
        assert result.stdout.strip() == "", f"Files exceeding 300 lines: {result.stdout}"


class TestTypeAnnotations:
    def test_service_methods_have_return_types(self):
        """验证服务方法有返回类型注解"""
        import inspect
        from app.services.task_service.core_mixin import TestTaskCoreMixin
        
        for name, method in inspect.getmembers(TestTaskCoreMixin, predicate=inspect.isfunction):
            if not name.startswith('_'):
                sig = inspect.signature(method)
                assert sig.return_annotation != inspect.Parameter.empty, f"Method {name} missing return type"

    def test_execution_replay_methods_have_return_types(self):
        """验证执行回放方法有返回类型注解"""
        import inspect
        from app.services.execution_replay.legacy_service import ExecutionReplayService
        
        service = ExecutionReplayService()
        for name, method in inspect.getmembers(service, predicate=inspect.ismethod):
            if not name.startswith('_'):
                sig = inspect.signature(method)
                assert sig.return_annotation != inspect.Parameter.empty, f"Method {name} missing return type"
