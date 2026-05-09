import uuid
import pytest
from app.services.visibility_config_service import VisibilityConfigService, VisibilityConfig
from app.services.cost_statistics_service import CostStatisticsService
from app.services.cost_statistics_models import CostStatistics, CostReport
from app.services.task_service import TaskService
from app.services.execution_mode_selector import ExecutionModeSelector, ExecutionMode, ExecutionStrategy


class TestVisibilityConfigService:
    def test_service_initialization(self):
        service = VisibilityConfigService()
        assert service is not None

    def test_get_global_config(self):
        service = VisibilityConfigService()
        config = service.get_global_config()
        assert isinstance(config, VisibilityConfig)

    def test_set_global_config(self):
        service = VisibilityConfigService()
        new_config = VisibilityConfig(
            headless=False,
            record_video=True,
            video_resolution=(1280, 720),
            video_fps=60
        )
        service.set_global_config(new_config)
        config = service.get_global_config()
        assert config.headless is False
        assert config.record_video is True

    def test_get_task_config(self, db, testUser, testProject):
        service = VisibilityConfigService()
        from app.models.test_task import TestTask
        task = TestTask(
            task_name=f"config_task_{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            executor_id=testUser.id,
            case_ids=[],
            total_count=1,
            status=0,
            success_count=0,
            fail_count=0,
            progress=0
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        config = service.get_task_config(task)
        assert isinstance(config, VisibilityConfig)

    def test_validate_config(self):
        service = VisibilityConfigService()
        valid, msg = service.validate_config(VisibilityConfig())
        assert valid is True
        invalid_config = VisibilityConfig(execution_speed="invalid_speed")
        valid, msg = service.validate_config(invalid_config)
        assert valid is False
        assert msg is not None

    @pytest.mark.skip(reason="get_recommended_config已移除，VisibilityConfigService API重构为分层配�?)
    def test_get_recommended_config(self):
        service = VisibilityConfigService()
        debug_config = service.get_recommended_config("debug")
        assert debug_config.headless is False
        ci_config = service.get_recommended_config("ci")
        assert ci_config.headless is True

    @pytest.mark.skip(reason="VALID_SPEEDS常量已移除，VisibilityConfigService API重构")
    def test_speed_delay_map(self):
        service = VisibilityConfigService()
        assert service.VALID_SPEEDS == ('slow', 'normal', 'fast')

    @pytest.mark.skip(reason="VALID_RESOLUTIONS常量已移除，VisibilityConfigService API重构")
    def test_valid_resolutions(self):
        service = VisibilityConfigService()
        assert (1280, 720) in service.VALID_RESOLUTIONS
        assert (1920, 1080) in service.VALID_RESOLUTIONS


class TestCostStatisticsService:
    def test_service_initialization(self, db):
        service = CostStatisticsService(db)
        assert service is not None
        assert service.db == db

    def test_cost_statistics_models(self):
        cost = CostStatistics(
            total_steps=10,
            ai_vision_calls=5,
            cache_hits=3,
            css_selector_used=2,
            xpath_used=0,
            estimated_cost=1.0,
            actual_cost=0.7,
            cost_savings=0.3,
            savings_rate=0.3,
            cache_hit_rate=0.6,
            ai_dependency_rate=0.5
        )
        assert cost.total_steps == 10
        assert cost.ai_vision_calls == 5

    def test_cost_report_model(self):
        report = CostReport(
            report_id="r1",
            project_id=1,
            start_date=None,
            end_date=None,
            overall_statistics=None,
            case_statistics=[],
            daily_statistics=[],
            optimization_suggestions=[],
            trend_data=[]
        )
        assert report.report_id == "r1"
        assert report.project_id == 1


class TestTaskService:
    @pytest.mark.skip(reason="TaskService构造函数已重构为无参数，使用内部get_db()")
    def test_service_initialization(self, db):
        service = TaskService(db)
        assert service is not None
        assert service.db == db

    @pytest.mark.skip(reason="TaskService构造函数已重构，start_task签名改为(task_id, project_id, case_ids)")
    def test_start_task_nonexistent(self, db):
        service = TaskService(db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            service.start_task(99999, db)
        )
        assert result["success"] is False
        assert "不存�? in result["error"]

    @pytest.mark.skip(reason="TaskService构造函数已重构，stop_task不再需要db参数")
    def test_stop_task_nonexistent(self, db):
        service = TaskService(db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            service.stop_task(99999, db)
        )
        assert result["success"] is False
        assert "不存�? in result["error"]


class TestExecutionModeSelector:
    def test_select_mode_ui_case(self):
        mode = ExecutionModeSelector.select_mode("UI")
        assert mode == ExecutionMode.AI_VISION

        mode = ExecutionModeSelector.select_mode("ui")
        assert mode == ExecutionMode.AI_VISION

        mode = ExecutionModeSelector.select_mode("功能")
        assert mode == ExecutionMode.AI_VISION

    def test_select_mode_api_case(self):
        mode = ExecutionModeSelector.select_mode("API")
        assert mode == ExecutionMode.API

        mode = ExecutionModeSelector.select_mode("api")
        assert mode == ExecutionMode.API

        mode = ExecutionModeSelector.select_mode("接口")
        assert mode == ExecutionMode.API

    def test_select_mode_empty(self):
        mode = ExecutionModeSelector.select_mode("")
        assert mode == ExecutionMode.AI_VISION

    def test_select_mode_unknown(self):
        mode = ExecutionModeSelector.select_mode("unknown_type")
        assert mode == ExecutionMode.AI_VISION

    def test_select_mode_none(self):
        mode = ExecutionModeSelector.select_mode(None)
        assert mode == ExecutionMode.AI_VISION

    def test_is_ai_vision_case(self):
        assert ExecutionModeSelector.is_ai_vision_case("UI") is True
        assert ExecutionModeSelector.is_ai_vision_case("功能") is True
        assert ExecutionModeSelector.is_ai_vision_case("API") is False

    def test_is_api_case(self):
        assert ExecutionModeSelector.is_api_case("API") is True
        assert ExecutionModeSelector.is_api_case("接口") is True
        assert ExecutionModeSelector.is_api_case("UI") is False

    def test_select_strategy_strict(self):
        strategy = ExecutionModeSelector.select_strategy("strict")
        assert strategy == ExecutionStrategy.STRICT

    def test_select_strategy_smart(self):
        strategy = ExecutionModeSelector.select_strategy("smart")
        assert strategy == ExecutionStrategy.SMART

    def test_select_strategy_fast(self):
        strategy = ExecutionModeSelector.select_strategy("fast")
        assert strategy == ExecutionStrategy.FAST

    def test_select_strategy_empty(self):
        strategy = ExecutionModeSelector.select_strategy("")
        assert strategy == ExecutionStrategy.SMART

    def test_select_strategy_none(self):
        strategy = ExecutionModeSelector.select_strategy(None)
        assert strategy == ExecutionStrategy.SMART

    def test_get_strategy_config_strict(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.STRICT)
        assert config.max_retries == 3
        assert config.ai_timeout == 45
        assert config.confidence_threshold == 0.95

    def test_get_strategy_config_smart(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.SMART)
        assert config.max_retries == 1
        assert config.ai_timeout == 30
        assert config.confidence_threshold == 0.9

    def test_get_strategy_config_fast(self):
        config = ExecutionModeSelector.get_strategy_config(ExecutionStrategy.FAST)
        assert config.max_retries == 0
        assert config.ai_timeout == 20
        assert config.confidence_threshold == 0.85

    def test_get_execution_config_default(self):
        config = ExecutionModeSelector.get_execution_config("UI")
        assert config.mode == ExecutionMode.AI_VISION
        assert config.strategy == ExecutionStrategy.SMART
        assert config.headless is True
        assert config.record_video is False

    def test_get_execution_config_with_strategy(self):
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            case_strategy="strict"
        )
        assert config.strategy == ExecutionStrategy.STRICT
        assert config.strategy_config.max_retries == 3

    def test_get_execution_config_strategy_priority(self):
        config = ExecutionModeSelector.get_execution_config(
            "UI",
            global_strategy="fast",
            task_strategy="smart",
            case_strategy="strict"
        )
        assert config.strategy == ExecutionStrategy.STRICT

    def test_get_execution_config_api_mode(self):
        config = ExecutionModeSelector.get_execution_config("API")
        assert config.mode == ExecutionMode.API
        assert config.is_api() is True
        assert config.is_ai_vision() is False

    def test_execution_mode_values(self):
        assert ExecutionMode.AI_VISION.value == "ai_vision"
        assert ExecutionMode.API.value == "api"
        assert ExecutionMode.UNKNOWN.value == "unknown"

    def test_execution_strategy_values(self):
        assert ExecutionStrategy.STRICT.value == "strict"
        assert ExecutionStrategy.SMART.value == "smart"
        assert ExecutionStrategy.FAST.value == "fast"

    def test_case_type_mapping(self):
        mapping = ExecutionModeSelector.CASE_TYPE_MAPPING
        assert mapping["UI"] == ExecutionMode.AI_VISION
        assert mapping["API"] == ExecutionMode.API
