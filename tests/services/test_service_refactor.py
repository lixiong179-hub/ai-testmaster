"""Service层重构验证测试 - 确保拆分后功能完整

测试范围:
    - 所有拆分后的Service模块导入验证
    - 核心类和方法存在性验证
    - 代理模块向后兼容性验证

对应Spec: code-standards-compliance-review
"""
import pytest
import importlib


class TestServiceImports:
    """验证所有Service层模块可正常导入"""

    def test_case_generation_imports(self):
        """test_case_generation新包导入验证（legacy case_generation子包已删除）"""
        from app.services.test_case_generation import TestCaseGenerationService
        from app.services.test_case_generation.helpers import ContentSanitizer
        assert TestCaseGenerationService is not None
        assert ContentSanitizer is not None

    def test_precondition_imports(self):
        """precondition子包导入验证"""
        from app.services.precondition import PreconditionService
        from app.services.precondition.login_mixin import LoginMixin
        from app.services.precondition.login_strategy_mixin import LoginStrategyMixin
        assert PreconditionService is not None
        assert all([LoginMixin, LoginStrategyMixin])

    def test_task_service_imports(self):
        """task_service子包导入验证"""
        from app.services.task_service import TaskService
        from app.services.task_service.core_mixin import TaskCoreMixin
        from app.services.task_service.execution_mixin import TaskExecutionMixin
        from app.services.task_service.push_mixin import TaskPushMixin
        assert TaskService is not None
        assert all([TaskCoreMixin, TaskExecutionMixin, TaskPushMixin])

    def test_ui_spec_parser_imports(self):
        """ui_spec_parser子包导入验证"""
        from app.services.ui_spec_parser import UISpecParser
        from app.services.ui_spec_parser.core_mixin import UISpecCoreMixin
        from app.services.ui_spec_parser.ocr_mixin import UISpecOcrMixin
        from app.services.ui_spec_parser.flow_mixin import UISpecFlowMixin
        from app.services.ui_spec_parser.pipeline_mixin import UISpecParsePipelineMixin
        from app.services.ui_spec_parser.pipeline_upload_mixin import PipelineUploadMixin
        assert UISpecParser is not None
        assert UISpecCoreMixin is not None
        assert UISpecOcrMixin is not None
        assert UISpecFlowMixin is not None
        assert UISpecParsePipelineMixin is not None

    def test_link_fetcher_imports(self):
        """link_fetcher子包导入验证"""
        from app.services.link_fetcher import LinkFetcherService
        from app.services.link_fetcher.core_mixin import LinkFetcherCoreMixin
        from app.services.link_fetcher.content_mixin import LinkFetcherContentMixin
        from app.services.link_fetcher.ui_mixin import LinkFetcherUIMixin
        assert LinkFetcherService is not None
        assert LinkFetcherCoreMixin is not None
        assert LinkFetcherContentMixin is not None
        assert LinkFetcherUIMixin is not None

    def test_test_data_imports(self):
        """test_data子包导入验证"""
        from app.services.test_data import TestDataGenerator
        from app.services.test_data.generator_mixin import GeneratorMixin
        from app.services.test_data.parameterizer_mixin import TestDataParameterizer
        from app.services.test_data.crud_mixin import TestDataCrudMixin
        from app.services.test_data.service_mixin import TestDataServiceMixin
        assert TestDataGenerator is not None
        assert TestDataParameterizer is not None
        assert TestDataCrudMixin is not None
        assert TestDataServiceMixin is not None

    def test_video_service_imports(self):
        """video_service子包导入验证"""
        from app.services.video import VideoService
        assert VideoService is not None

    def test_cost_statistics_imports(self):
        """cost_statistics子包导入验证"""
        from app.services.cost_statistics_service import CostStatisticsService
        from app.services.cost_statistics import CostStatisticsService as CSS2
        assert CostStatisticsService is not None
        assert CSS2 is not None

    def test_mobile_ai_executor_imports(self):
        """mobile_ai_executor子包导入验证"""
        from app.services.mobile_ai_executor import MobileAIExecutor
        from app.services.mobile_ai_executor.types import MobileActionType, MobileAIError
        assert MobileAIExecutor is not None
        assert MobileActionType is not None
        assert MobileAIError is not None

    def test_case_quality_analyzer_imports(self):
        """case_quality_analyzer子包导入验证"""
        from app.services.case_quality_analyzer import CaseQualityAnalyzer
        assert CaseQualityAnalyzer is not None

    def test_visibility_config_imports(self):
        """visibility_config子包导入验证"""
        from app.services.visibility_config_service import VisibilityConfigService
        assert VisibilityConfigService is not None

    def test_element_locator_imports(self):
        """element_locator_service导入验证"""
        from app.services.element_locator_service import ElementLocatorService
        assert ElementLocatorService is not None

    def test_execution_replay_imports(self):
        """execution_replay_service导入验证"""
        from app.services.execution_replay.legacy_service import ExecutionReplayService
        assert ExecutionReplayService is not None


class TestBackwardCompatibility:
    """验证代理模块的向后兼容性"""

    def test_original_import_paths(self):
        """原始导入路径仍然可用"""
        from app.services.test_case_generation_service import TestCaseGenerationService
        from app.services.ui_spec_parser import UISpecParser
        from app.services.element_locator_service import ElementLocatorService
        from app.services.execution_replay.legacy_service import ExecutionReplayService
        from app.services.case_quality_analyzer import CaseQualityAnalyzer
        from app.services.video import VideoService
        from app.services.cost_statistics_service import CostStatisticsService
        from app.services.mobile_ai_executor import MobileAIExecutor
        from app.services.task_service import TaskService
        from app.services.visibility_config_service import VisibilityConfigService
        assert all([
            TestCaseGenerationService, UISpecParser, ElementLocatorService,
            ExecutionReplayService, CaseQualityAnalyzer, VideoService,
            CostStatisticsService, MobileAIExecutor, TaskService, VisibilityConfigService
        ])

    def test_test_execution_engine_v2_import(self):
        """TestExecutionEngineV2导入验证"""
        from app.services.test_execution_engine_v2 import TestExecutionEngineV2
        assert TestExecutionEngineV2 is not None


@pytest.mark.skip(reason="硬编码路径不兼容当前环境")
class TestStrLeakageFix:
    """验证str(e)信息泄露已修复"""

    def test_no_str_e_in_return_values(self):
        """检查Service层返回值中无str(e)"""
        import subprocess
        result = subprocess.run(
            ['powershell', '-Command',
             "Select-String -Path 'd:\\PythonFile\\ai-testmaster\\app\\services\\*.py' -Pattern 'return.*str\\(e\\)' | Measure-Object | Select-Object -ExpandProperty Count"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip())
        assert count == 0, f"仍有 {count} 处 return 中包含 str(e)"


@pytest.mark.skip(reason="硬编码路径不兼容当前环境")
class TestFileLineLimit:
    """验证所有Service文件≤300行"""

    def test_all_service_files_under_300_lines(self):
        """所有Service层Python文件行数≤300"""
        import subprocess
        result = subprocess.run(
            ['powershell', '-Command',
             "Get-ChildItem -Path 'd:\\PythonFile\\ai-testmaster\\app\\services' -Filter '*.py' -Recurse | ForEach-Object { $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines; if ($lines -gt 300) { Write-Output \"$($_.FullName): $lines\" } }"],
            capture_output=True, text=True
        )
        over_limit = result.stdout.strip()
        assert over_limit == "", f"以下文件超过300行:\n{over_limit}"


class TestTypeAnnotations:
    """验证类型注解补全"""

    def test_task_service_methods_have_return_types(self):
        """task_service关键方法有返回类型注解"""
        from app.services.task_service.push_mixin import TaskPushMixin
        import inspect
        methods = ['push_execution_log', 'push_execution_progress']
        for method_name in methods:
            method = getattr(TaskPushMixin, method_name, None)
            if method:
                sig = inspect.signature(method)
                assert sig.return_annotation != inspect.Signature.empty, \
                    f"{method_name} 缺少返回类型注解"

    def test_execution_replay_service_methods_have_return_types(self):
        """execution_replay_service关键方法有返回类型注解"""
        from app.services.execution_replay.legacy_service import ExecutionReplayService
        import inspect
        method = getattr(ExecutionReplayService, 'set_default_speed', None)
        if method:
            sig = inspect.signature(method)
            assert sig.return_annotation != inspect.Signature.empty


class TestConstantsRefactor:
    """验证重复逻辑抽取为常量"""

    def test_login_keywords_constant_exists(self):
        """LOGIN_KEYWORDS常量存在"""
        from app.core.constants import LOGIN_KEYWORDS
        assert isinstance(LOGIN_KEYWORDS, list)
        assert "登录" in LOGIN_KEYWORDS
        assert "username" in LOGIN_KEYWORDS

    def test_auth_failure_keywords_constant_exists(self):
        """AUTH_FAILURE_KEYWORDS常量存在"""
        from app.core.constants import AUTH_FAILURE_KEYWORDS
        assert isinstance(AUTH_FAILURE_KEYWORDS, tuple)

    def test_http_utils_build_auth_headers_exists(self):
        """build_auth_headers工具函数存在"""
        from app.utils.http_utils import build_auth_headers
        assert callable(build_auth_headers)
