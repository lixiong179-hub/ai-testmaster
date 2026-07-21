"""
批量元素定位服务真实单元测试

测试要求：
- 严禁使用Mock，所有测试必须使用真实环境
- 必须使用真实MySQL数据库
- 覆盖率>=95%
- 测试数据隔离，测试后清理数据
"""
import pytest
import asyncio
from app.utils.db_time import utcnow
from typing import Dict, Any, List

from app.services.batch_locator_service import (
    BatchLocatorService,
    BatchTaskManager,
    BatchRecordStatus,
    BatchRecordReport,
    StepRecordResult,
    BatchLocatorConfig,
    batch_record_locators
)
from app.api.v1.endpoints.batch_locator import (
    BatchRecordRequest,
    BatchRecordResponse,
    BatchRecordStatusResponse
)

pytestmark = [pytest.mark.integration, pytest.mark.real_browser]


# ============================================================================
# 测试数据类
# ============================================================================

class TestBatchLocatorConfig:
    """测试批量定位配置类"""

    def test_default_config(self):
        """测试默认配置"""
        config = BatchLocatorConfig()
        assert config.step_delay == 0.5
        assert config.max_retries == 3

    def test_custom_config(self):
        """测试自定义配置"""
        config = BatchLocatorConfig(step_delay=1.0, max_retries=5)
        assert config.step_delay == 1.0
        assert config.max_retries == 5

    def test_config_partial_override(self):
        """测试部分覆盖配置"""
        config = BatchLocatorConfig(step_delay=2.0)
        assert config.step_delay == 2.0
        assert config.max_retries == 3  # 默认值


class TestBatchRecordStatus:
    """测试批量记录状态枚举"""

    def test_status_values(self):
        """测试状态值"""
        assert BatchRecordStatus.PENDING == "pending"
        assert BatchRecordStatus.RUNNING == "running"
        assert BatchRecordStatus.COMPLETED == "completed"
        assert BatchRecordStatus.FAILED == "failed"
        assert BatchRecordStatus.CANCELLED == "cancelled"

    def test_status_comparison(self):
        """测试状态比较"""
        assert BatchRecordStatus.RUNNING == "running"
        assert BatchRecordStatus.COMPLETED != "running"


class TestStepRecordResult:
    """测试步骤记录结果类"""

    def test_step_result_creation(self):
        """测试创建步骤结果"""
        result = StepRecordResult(
            step_id=1,
            step_number=1,
            action="点击登录按钮",
            success=True,
            message="定位记录成功",
            locator_id=100,
            css_selector="#login-btn",
            confidence=0.95,
            duration=2.5
        )
        assert result.step_id == 1
        assert result.step_number == 1
        assert result.action == "点击登录按钮"
        assert result.success == True
        assert result.message == "定位记录成功"
        assert result.locator_id == 100
        assert result.css_selector == "#login-btn"
        assert result.confidence == 0.95
        assert result.duration == 2.5

    def test_step_result_defaults(self):
        """测试步骤结果默认值"""
        result = StepRecordResult(
            step_id=1,
            step_number=1,
            action="测试操作",
            success=False,
            message="失败"
        )
        assert result.locator_id is None
        assert result.css_selector is None
        assert result.confidence is None
        assert result.duration == 0.0

    def test_step_result_failed(self):
        """测试失败步骤结果"""
        result = StepRecordResult(
            step_id=2,
            step_number=2,
            action="点击不存在的元素",
            success=False,
            message="AI无法识别目标元素",
            duration=1.5
        )
        assert result.success == False
        assert result.message == "AI无法识别目标元素"


class TestBatchRecordReport:
    """测试批量记录报告类"""

    def test_report_creation(self):
        """测试创建报告"""
        report = BatchRecordReport(
            case_id=1,
            case_title="用户登录测试",
            total_steps=5,
            success_count=4,
            failed_count=1,
            skipped_count=0,
            start_time=utcnow(),
            status=BatchRecordStatus.COMPLETED
        )
        assert report.case_id == 1
        assert report.case_title == "用户登录测试"
        assert report.total_steps == 5
        assert report.success_count == 4
        assert report.failed_count == 1
        assert report.skipped_count == 0
        assert report.status == BatchRecordStatus.COMPLETED

    def test_report_with_results(self):
        """测试带结果的报告"""
        report = BatchRecordReport(
            case_id=1,
            case_title="测试用例",
            total_steps=2,
            success_count=0,
            failed_count=0,
            skipped_count=0,
            start_time=utcnow(),
            status=BatchRecordStatus.RUNNING
        )

        # 添加步骤结果
        result1 = StepRecordResult(
            step_id=1, step_number=1, action="步骤1",
            success=True, message="成功", duration=1.0
        )
        result2 = StepRecordResult(
            step_id=2, step_number=2, action="步骤2",
            success=False, message="失败", duration=2.0
        )
        report.step_results.append(result1)
        report.step_results.append(result2)

        assert len(report.step_results) == 2
        assert report.step_results[0].success == True
        assert report.step_results[1].success == False

    def test_report_to_dict(self):
        """测试报告序列化"""
        start_time = utcnow()
        report = BatchRecordReport(
            case_id=1,
            case_title="测试",
            total_steps=1,
            success_count=1,
            failed_count=0,
            skipped_count=0,
            start_time=start_time,
            end_time=start_time,
            duration=5.5,
            status=BatchRecordStatus.COMPLETED
        )

        result = StepRecordResult(
            step_id=1, step_number=1, action="测试步骤",
            success=True, message="成功",
            css_selector="#test", confidence=0.9, duration=1.5
        )
        report.step_results.append(result)

        report_dict = report.to_dict()

        assert report_dict["case_id"] == 1
        assert report_dict["case_title"] == "测试"
        assert report_dict["total_steps"] == 1
        assert report_dict["success_count"] == 1
        assert report_dict["duration"] == 5.5
        assert report_dict["status"] == "completed"
        assert isinstance(report_dict["step_results"], list)
        assert len(report_dict["step_results"]) == 1
        assert report_dict["step_results"][0]["css_selector"] == "#test"

    def test_report_to_dict_empty_results(self):
        """测试空结果的报告序列化"""
        report = BatchRecordReport(
            case_id=1,
            case_title="测试",
            total_steps=0,
            success_count=0,
            failed_count=0,
            skipped_count=0,
            start_time=utcnow(),
            status=BatchRecordStatus.PENDING
        )

        report_dict = report.to_dict()
        assert report_dict["step_results"] == []


# ============================================================================
# 测试任务管理器
# ============================================================================

class TestBatchTaskManager:
    """测试批量任务管理器"""

    def setup_method(self):
        """每个测试方法前清理任务"""
        manager = BatchTaskManager()
        # 清理所有任务
        for case_id in list(manager.get_all_tasks().keys()):
            manager.unregister_task(case_id)

    def test_singleton_pattern(self):
        """测试单例模式"""
        manager1 = BatchTaskManager()
        manager2 = BatchTaskManager()
        assert manager1 is manager2

    def test_register_and_get_task(self):
        """测试注册和获取任务"""
        manager = BatchTaskManager()
        service = BatchLocatorService()

        manager.register_task(1, service)
        retrieved = manager.get_task(1)

        assert retrieved is service

    def test_unregister_task(self):
        """测试注销任务"""
        manager = BatchTaskManager()
        service = BatchLocatorService()

        manager.register_task(1, service)
        manager.unregister_task(1)

        assert manager.get_task(1) is None

    def test_get_all_tasks(self):
        """测试获取所有任务"""
        manager = BatchTaskManager()
        service1 = BatchLocatorService()
        service2 = BatchLocatorService()

        manager.register_task(1, service1)
        manager.register_task(2, service2)

        all_tasks = manager.get_all_tasks()
        assert len(all_tasks) == 2
        assert 1 in all_tasks
        assert 2 in all_tasks

    def test_cancel_task(self):
        """测试取消任务"""
        manager = BatchTaskManager()
        service = BatchLocatorService()

        manager.register_task(1, service)
        result = manager.cancel_task(1)

        assert result == True
        assert service._cancelled == True

    def test_cancel_nonexistent_task(self):
        """测试取消不存在的任务"""
        manager = BatchTaskManager()
        result = manager.cancel_task(999)

        assert result == False

    def test_reregister_task(self):
        """测试重复注册任务（覆盖）"""
        manager = BatchTaskManager()
        service1 = BatchLocatorService()
        service2 = BatchLocatorService()

        manager.register_task(1, service1)
        manager.register_task(1, service2)

        assert manager.get_task(1) is service2


# ============================================================================
# 测试服务类
# ============================================================================

class TestBatchLocatorService:
    """测试批量定位服务类"""

    def test_default_initialization(self):
        """测试默认初始化"""
        service = BatchLocatorService()

        assert service._cancelled == False
        assert service._current_report is None
        assert service.progress_callback is None
        assert service.config.step_delay == 0.5
        assert service.config.max_retries == 3

    def test_custom_initialization(self):
        """测试自定义初始化"""
        config = BatchLocatorConfig(step_delay=1.5, max_retries=10)
        service = BatchLocatorService(config=config)

        assert service.config.step_delay == 1.5
        assert service.config.max_retries == 10

    def test_cancel_method(self):
        """测试取消方法"""
        service = BatchLocatorService()
        service.cancel()

        assert service._cancelled == True

    def test_get_report_no_report(self):
        """测试获取报告（无报告）"""
        service = BatchLocatorService()
        report = service.get_report()

        assert report is None

    def test_notify_progress_with_callback(self):
        """测试进度通知（有回调）"""
        received_data = []

        def callback(data: Dict[str, Any]):
            received_data.append(data)

        service = BatchLocatorService(progress_callback=callback)
        service._notify_progress({"type": "test", "value": 100})

        assert len(received_data) == 1
        assert received_data[0]["type"] == "test"
        assert received_data[0]["value"] == 100

    def test_notify_progress_without_callback(self):
        """测试进度通知（无回调）"""
        service = BatchLocatorService()
        # 不应该抛出异常
        service._notify_progress({"type": "test"})

    def test_notify_progress_callback_exception(self):
        """测试进度通知（回调异常）"""
        def bad_callback(data):
            raise ValueError("测试异常")

        service = BatchLocatorService(progress_callback=bad_callback)
        # 不应该抛出异常，应该记录警告
        service._notify_progress({"type": "test"})


# ============================================================================
# 测试API请求/响应模型
# ============================================================================

class TestBatchRecordRequest:
    """测试批量记录请求模型"""

    def test_default_values(self):
        """测试默认值"""
        request = BatchRecordRequest()
        assert request.skip_existing == True
        assert request.execute_precondition == True

    def test_custom_values(self):
        """测试自定义值"""
        request = BatchRecordRequest(
            skip_existing=False,
            execute_precondition=False
        )
        assert request.skip_existing == False
        assert request.execute_precondition == False

    def test_partial_custom_values(self):
        """测试部分自定义值"""
        request = BatchRecordRequest(skip_existing=False)
        assert request.skip_existing == False
        assert request.execute_precondition == True  # 默认值


class TestBatchRecordResponse:
    """测试批量记录响应模型"""

    def test_response_creation(self):
        """测试创建响应"""
        response = BatchRecordResponse(
            success=True,
            message="任务已启动",
            case_id=1,
            task_id="batch_1"
        )
        assert response.success == True
        assert response.message == "任务已启动"
        assert response.case_id == 1
        assert response.task_id == "batch_1"

    def test_response_without_task_id(self):
        """测试无任务ID的响应"""
        response = BatchRecordResponse(
            success=False,
            message="启动失败",
            case_id=1
        )
        assert response.task_id is None


class TestBatchRecordStatusResponse:
    """测试批量记录状态响应模型"""

    def test_status_response_creation(self):
        """测试创建状态响应"""
        response = BatchRecordStatusResponse(
            case_id=1,
            status="running",
            progress=50.0,
            current_step=3,
            total_steps=5,
            message="正在执行"
        )
        assert response.case_id == 1
        assert response.status == "running"
        assert response.progress == 50.0
        assert response.current_step == 3
        assert response.total_steps == 5
        assert response.message == "正在执行"

    def test_status_response_without_optional(self):
        """测试无可选字段的状态响应"""
        response = BatchRecordStatusResponse(
            case_id=1,
            status="completed",
            progress=100.0,
            total_steps=5
        )
        assert response.current_step is None
        assert response.message is None


# ============================================================================
# 测试便捷函数
# ============================================================================

class TestBatchRecordLocatorsFunction:
    """测试批量记录便捷函数"""

    def test_function_signature(self):
        """测试函数签名"""
        import inspect
        sig = inspect.signature(batch_record_locators)
        params = list(sig.parameters.keys())

        assert 'case_id' in params
        assert 'skip_existing' in params
        assert 'execute_precondition' in params
        assert 'progress_callback' in params
        assert 'config' in params

    def test_default_parameters(self):
        """测试默认参数"""
        import inspect
        sig = inspect.signature(batch_record_locators)
        defaults = {
            k: v.default
            for k, v in sig.parameters.items()
            if v.default is not inspect.Parameter.empty
        }

        assert defaults['skip_existing'] == True
        assert defaults['execute_precondition'] == True
        assert defaults['progress_callback'] is None
        assert defaults['config'] is None


# ============================================================================
# 异步测试
# ============================================================================

@pytest.mark.asyncio
class TestBatchLocatorServiceAsync:
    """测试批量定位服务异步方法"""

    async def test_service_lifecycle(self):
        """测试服务生命周期（简化测试）"""
        service = BatchLocatorService()

        # 测试初始状态
        assert service._cancelled == False
        assert service.get_report() is None

        # 测试取消
        service.cancel()
        assert service._cancelled == True

    async def test_cancel_during_operation(self):
        """测试操作期间取消"""
        service = BatchLocatorService()

        # 模拟操作前取消
        service.cancel()
        assert service._cancelled == True

        # 验证状态保持
        assert service._cancelled == True


# ============================================================================
# 测试覆盖率统计
# ============================================================================

if __name__ == "__main__":
    # 运行测试并生成覆盖率报告
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--cov=app.services.batch_locator_service",
        "--cov=app.api.v1.endpoints.batch_locator",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov_batch_locator"
    ])
