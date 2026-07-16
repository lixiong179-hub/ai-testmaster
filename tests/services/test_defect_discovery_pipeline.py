"""
缺陷挖掘导向全链路自测执行单元测试

覆盖场景：
    - 全链路执行（mock 各步骤的 service 调用）
    - 步骤失败不中断
    - 汇总通知
    - 定时执行模式切换
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.project import Project, ProjectFile
from app.models.user import User
from app.services.self_test_service import (
    run_defect_discovery_self_test,
    _build_step_result,
    _step_requirement_confirmation,
    _step_extract_test_points,
    _step_generate_cases,
    _step_review_and_save,
    _step_create_task,
    _step_assess_severity,
    _step_generate_report,
    _step_cleanup,
    _notify_pipeline_summary,
)
from app.tasks.self_test_scheduler import SelfTestScheduler


# ---------------------------------------------------------------------------
# 辅助方法测试
# ---------------------------------------------------------------------------

class TestBuildStepResult:
    """步骤结果构建测试"""

    def test_success_step(self) -> None:
        result = _build_step_result("需求确认", "success")
        assert result["name"] == "需求确认"
        assert result["status"] == "success"
        assert result["error"] is None
        assert result["duration_ms"] == 0.0

    def test_failed_step(self) -> None:
        result = _build_step_result("执行", "failed", "任务执行失败", 1234.56)
        assert result["name"] == "执行"
        assert result["status"] == "failed"
        assert result["error"] == "任务执行失败"
        assert result["duration_ms"] == 1234.56

    def test_skipped_step(self) -> None:
        result = _build_step_result("用例生成", "skipped", "前置步骤未产出测试点")
        assert result["status"] == "skipped"
        assert result["error"] == "前置步骤未产出测试点"

    def test_duration_rounded(self) -> None:
        result = _build_step_result("测试", "success", duration_ms=1234.5678)
        assert result["duration_ms"] == 1234.57


# ---------------------------------------------------------------------------
# 步骤1: 需求确认
# ---------------------------------------------------------------------------

class TestStepRequirementConfirmation:
    """需求确认步骤测试"""

    async def test_requirement_file_exists(self, async_db, async_test_user: User) -> None:
        project = Project(
            name="req_confirm_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        file_record = ProjectFile(
            project_id=project.id,
            file_name="requirement.md",
            file_type="md",
            file_url="/tmp/requirement.md",
            file_source="auto_import",
            resource_type="requirement",
            extract_status="completed",
            is_active=True,
        )
        async_db.add(file_record)
        await async_db.flush()

        ok, err = await _step_requirement_confirmation(async_db, project.id)
        assert ok is True
        assert err is None

    async def test_no_requirement_file(self, async_db, async_test_user: User) -> None:
        project = Project(
            name="no_req_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        ok, err = await _step_requirement_confirmation(async_db, project.id)
        assert ok is False
        assert "未找到已完成提取的需求文档" in err

    async def test_requirement_file_not_completed(self, async_db, async_test_user: User) -> None:
        project = Project(
            name="pending_req_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        file_record = ProjectFile(
            project_id=project.id,
            file_name="requirement.md",
            file_type="md",
            file_url="/tmp/requirement.md",
            file_source="auto_import",
            resource_type="requirement",
            extract_status="pending",
            is_active=True,
        )
        async_db.add(file_record)
        await async_db.flush()

        ok, err = await _step_requirement_confirmation(async_db, project.id)
        assert ok is False
        assert "未找到已完成提取的需求文档" in err

    async def test_requirement_file_inactive(self, async_db, async_test_user: User) -> None:
        project = Project(
            name="inactive_req_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        file_record = ProjectFile(
            project_id=project.id,
            file_name="requirement.md",
            file_type="md",
            file_url="/tmp/requirement.md",
            file_source="auto_import",
            resource_type="requirement",
            extract_status="completed",
            is_active=False,
        )
        async_db.add(file_record)
        await async_db.flush()

        ok, err = await _step_requirement_confirmation(async_db, project.id)
        assert ok is False


# ---------------------------------------------------------------------------
# 步骤2: 测试点提取
# ---------------------------------------------------------------------------

class TestStepExtractTestPoints:
    """测试点提取步骤测试"""

    async def test_existing_points_skip_extraction(
        self, async_db, async_test_user: User
    ) -> None:
        """已有测试点时跳过提取"""
        from app.models.test_point import TestPoint
        from app.models.enums import TestPointStatus

        project = Project(
            name="existing_tp_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        tp = TestPoint(
            project_id=project.id,
            module="登录模块",
            point="输入错误密码登录",
            priority=1,
            status=TestPointStatus.ACTIVE.value,
        )
        async_db.add(tp)
        await async_db.flush()

        ok, err, point_ids = await _step_extract_test_points(async_db, project.id)
        assert ok is True
        assert err is None
        assert len(point_ids) >= 1

    @patch("app.services.ai_analysis_service.extract_test_points_from_content", new_callable=AsyncMock)
    async def test_extract_from_requirement_content(
        self, mock_extract, async_db, async_test_user: User
    ) -> None:
        """无已有测试点时从需求文档提取"""
        mock_extract.return_value = [
            {"module": "登录模块", "point": "边界值测试", "priority": 1, "function": "登录"},
        ]

        project = Project(
            name="extract_tp_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        file_record = ProjectFile(
            project_id=project.id,
            file_name="requirement.md",
            file_type="md",
            file_url="/tmp/requirement.md",
            file_source="auto_import",
            resource_type="requirement",
            extract_status="completed",
            content="需求文档内容",
            is_active=True,
        )
        async_db.add(file_record)
        await async_db.flush()

        ok, err, point_ids = await _step_extract_test_points(async_db, project.id)
        assert ok is True
        assert err is None
        assert len(point_ids) >= 1
        mock_extract.assert_called_once()

    async def test_no_requirement_content(self, async_db, async_test_user: User) -> None:
        """需求文档内容为空"""
        project = Project(
            name="no_content_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        file_record = ProjectFile(
            project_id=project.id,
            file_name="requirement.md",
            file_type="md",
            file_url="/tmp/requirement.md",
            file_source="auto_import",
            resource_type="requirement",
            extract_status="completed",
            content=None,
            is_active=True,
        )
        async_db.add(file_record)
        await async_db.flush()

        ok, err, point_ids = await _step_extract_test_points(async_db, project.id)
        assert ok is False
        assert "需求文档内容为空" in err
        assert point_ids == []


# ---------------------------------------------------------------------------
# 步骤3: 用例生成
# ---------------------------------------------------------------------------

class TestStepGenerateCases:
    """用例生成步骤测试"""

    async def test_no_test_points(self) -> None:
        """无测试点时返回失败"""
        ok, err, case_ids = await _step_generate_cases(MagicMock(), 1, 1, [])
        assert ok is False
        assert "无可用测试点" in err
        assert case_ids == []

    @patch("app.db.database.PrimarySessionLocal")
    @patch("app.services.test_case_generation.TestCaseGenerationService")
    async def test_generate_cases_success(self, mock_service_cls, mock_session_local) -> None:
        """用例生成成功"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_session_local.return_value = MagicMock()

        async def mock_batch_gen(**kwargs):
            yield {"status": "completed", "case_id": 101}
            yield {"status": "completed", "case_id": 102}
            yield {"status": "running", "progress": 50}

        mock_service.generate_test_cases_batch = mock_batch_gen

        ok, err, case_ids = await _step_generate_cases(MagicMock(), 1, 1, [1, 2, 3])
        assert ok is True
        assert err is None
        assert 101 in case_ids
        assert 102 in case_ids

    @patch("app.db.database.PrimarySessionLocal")
    @patch("app.services.test_case_generation.TestCaseGenerationService")
    async def test_generate_cases_empty_result(self, mock_service_cls, mock_session_local) -> None:
        """用例生成结果为空"""
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service
        mock_session_local.return_value = MagicMock()

        async def mock_batch_gen(**kwargs):
            yield {"status": "running", "progress": 50}
            return

        mock_service.generate_test_cases_batch = mock_batch_gen

        ok, err, case_ids = await _step_generate_cases(MagicMock(), 1, 1, [1, 2])
        assert ok is False
        assert "未产出任何用例" in err


# ---------------------------------------------------------------------------
# 步骤4: 评审保存
# ---------------------------------------------------------------------------

class TestStepReviewAndSave:
    """评审保存步骤测试"""

    async def test_no_case_ids(self) -> None:
        """无用例时直接返回成功"""
        ok, err = await _step_review_and_save(MagicMock(), 1, 1, [])
        assert ok is True
        assert err is None

    async def test_no_iteration_skip_review(
        self, async_db, async_test_user: User
    ) -> None:
        """无迭代时跳过评审"""
        project = Project(
            name="no_iteration_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        ok, err = await _step_review_and_save(async_db, project.id, async_test_user.id, [999])
        assert ok is True
        assert err is None


# ---------------------------------------------------------------------------
# 步骤5: 任务创建
# ---------------------------------------------------------------------------

class TestStepCreateTask:
    """任务创建步骤测试"""

    async def test_no_case_ids(self) -> None:
        """无用例时返回失败"""
        ok, err, task_id = await _step_create_task(MagicMock(), 1, 1, [])
        assert ok is False
        assert "无可用用例" in err
        assert task_id is None

    async def test_create_task_success(
        self, async_db, async_test_user: User
    ) -> None:
        """创建任务成功"""
        from app.models.test_case import TestCase

        project = Project(
            name="task_create_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        test_case = TestCase(
            title="测试用例",
            case_no="TC-TASK-001",
            project_id=project.id,
            module="测试模块",
            precondition="无",
            steps_json=[],
            expected_result="成功",
            priority=2,
            case_type="UI",
        )
        async_db.add(test_case)
        await async_db.flush()

        ok, err, task_id = await _step_create_task(async_db, project.id, async_test_user.id, [test_case.id])
        assert ok is True
        assert err is None
        assert task_id is not None


# ---------------------------------------------------------------------------
# 步骤7: 严重度评估
# ---------------------------------------------------------------------------

class TestStepAssessSeverity:
    """严重度评估步骤测试"""

    async def test_project_not_found(self) -> None:
        """项目不存在"""
        mock_db = AsyncMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = execute_result

        ok, err, counts = await _step_assess_severity(mock_db, 99999, 1)
        assert ok is False
        assert "不存在" in err
        assert counts == {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

    async def test_no_failed_results(
        self, async_db, async_test_user: User
    ) -> None:
        """无失败结果时缺陷统计全为0"""
        project = Project(
            name="severity_no_fail_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        ok, err, counts = await _step_assess_severity(async_db, project.id, 99999)
        assert ok is True
        assert err is None
        assert counts == {"p0": 0, "p1": 0, "p2": 0, "p3": 0}


# ---------------------------------------------------------------------------
# 步骤8: 报告生成
# ---------------------------------------------------------------------------

class TestStepGenerateReport:
    """报告生成步骤测试"""

    @patch("app.db.database.PrimarySessionLocal")
    @patch("app.services.report_service.ReportService")
    async def test_generate_report_success(self, mock_report_cls, mock_session_local) -> None:
        """报告生成成功"""
        mock_report = MagicMock()
        mock_report.id = 42
        mock_report_cls.generate_report.return_value = mock_report
        mock_session_local.return_value = MagicMock()

        ok, err, report_id = await _step_generate_report(MagicMock(), 1, 1, 1)
        assert ok is True
        assert err is None
        assert report_id == 42

    @patch("app.db.database.PrimarySessionLocal")
    @patch("app.services.report_service.ReportService")
    async def test_generate_report_failure(self, mock_report_cls, mock_session_local) -> None:
        """报告生成失败"""
        mock_report_cls.generate_report.side_effect = Exception("报告生成异常")
        mock_session_local.return_value = MagicMock()

        ok, err, report_id = await _step_generate_report(MagicMock(), 1, 1, 1)
        assert ok is False
        assert "报告生成失败" in err
        assert report_id is None


# ---------------------------------------------------------------------------
# 步骤9: 数据清理
# ---------------------------------------------------------------------------

class TestStepCleanup:
    """数据清理步骤测试"""

    async def test_cleanup_success(self, async_db, async_test_user: User) -> None:
        """数据清理成功"""
        project = Project(
            name="cleanup_project",
            user_id=async_test_user.id,
            status=1,
            project_type="web",
            is_self_test=True,
        )
        async_db.add(project)
        await async_db.flush()

        ok, err = await _step_cleanup(async_db, project.id)
        assert ok is True
        assert err is None


# ---------------------------------------------------------------------------
# 全链路执行集成测试
# ---------------------------------------------------------------------------

class TestRunDefectDiscoverySelfTest:
    """全链路执行测试"""

    @patch("app.services.self_test_service._step_cleanup", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_report", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_assess_severity", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_execute", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_create_task", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_review_and_save", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_cases", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_extract_test_points", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_requirement_confirmation", new_callable=AsyncMock)
    @patch("app.services.self_test_service._notify_pipeline_summary", new_callable=AsyncMock)
    async def test_full_pipeline_success(
        self,
        mock_notify,
        mock_step1,
        mock_step2,
        mock_step3,
        mock_step4,
        mock_step5,
        mock_step6,
        mock_step7,
        mock_step8,
        mock_step9,
    ) -> None:
        """全链路成功执行"""
        mock_step1.return_value = (True, None)
        mock_step2.return_value = (True, None, [1, 2, 3])
        mock_step3.return_value = (True, None, [101, 102])
        mock_step4.return_value = (True, None)
        mock_step5.return_value = (True, None, 501)
        mock_step6.return_value = (True, None)
        mock_step7.return_value = (True, None, {"p0": 1, "p1": 2, "p2": 3, "p3": 1})
        mock_step8.return_value = (True, None, 601)
        mock_step9.return_value = (True, None)

        result = await run_defect_discovery_self_test(MagicMock(), 1, 1)

        assert result["project_id"] == 1
        assert result["success"] is True
        assert result["task_id"] == 501
        assert result["report_id"] == 601
        assert len(result["steps"]) == 9
        assert all(s["status"] == "success" for s in result["steps"])
        assert result["defect_summary"]["p0_count"] == 1
        assert result["defect_summary"]["p1_count"] == 2
        assert result["defect_summary"]["p2_count"] == 3
        assert result["defect_summary"]["p3_count"] == 1
        assert result["defect_summary"]["total_defects"] == 7
        mock_notify.assert_called_once()

    @patch("app.services.self_test_service._step_cleanup", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_report", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_assess_severity", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_execute", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_create_task", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_review_and_save", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_cases", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_extract_test_points", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_requirement_confirmation", new_callable=AsyncMock)
    @patch("app.services.self_test_service._notify_pipeline_summary", new_callable=AsyncMock)
    async def test_step_failure_does_not_interrupt(
        self,
        mock_notify,
        mock_step1,
        mock_step2,
        mock_step3,
        mock_step4,
        mock_step5,
        mock_step6,
        mock_step7,
        mock_step8,
        mock_step9,
    ) -> None:
        """步骤2失败不中断全链路，后续步骤标记为 skipped"""
        mock_step1.return_value = (True, None)
        mock_step2.return_value = (False, "AI 提取测试点返回为空", [])
        # 步骤3-8 不会被调用（因为 test_point_ids 为空），但步骤9仍会执行
        mock_step9.return_value = (True, None)

        result = await run_defect_discovery_self_test(MagicMock(), 1, 1)

        assert result["success"] is False
        assert len(result["steps"]) == 9
        # 步骤1成功
        assert result["steps"][0]["status"] == "success"
        # 步骤2失败
        assert result["steps"][1]["status"] == "failed"
        assert "AI 提取测试点返回为空" in result["steps"][1]["error"]
        # 步骤3因无测试点被跳过
        assert result["steps"][2]["status"] == "skipped"
        # 步骤9数据清理仍执行
        assert result["steps"][8]["status"] == "success"
        mock_notify.assert_called_once()

    @patch("app.services.self_test_service._step_cleanup", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_report", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_assess_severity", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_execute", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_create_task", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_review_and_save", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_cases", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_extract_test_points", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_requirement_confirmation", new_callable=AsyncMock)
    @patch("app.services.self_test_service._notify_pipeline_summary", new_callable=AsyncMock)
    async def test_step_exception_does_not_interrupt(
        self,
        mock_notify,
        mock_step1,
        mock_step2,
        mock_step3,
        mock_step4,
        mock_step5,
        mock_step6,
        mock_step7,
        mock_step8,
        mock_step9,
    ) -> None:
        """步骤抛出异常不中断全链路"""
        mock_step1.side_effect = RuntimeError("数据库连接异常")
        mock_step2.return_value = (True, None, [1])
        mock_step3.return_value = (True, None, [101])
        mock_step4.return_value = (True, None)
        mock_step5.return_value = (True, None, 501)
        mock_step6.return_value = (True, None)
        mock_step7.return_value = (True, None, {"p0": 0, "p1": 0, "p2": 0, "p3": 0})
        mock_step8.return_value = (True, None, 601)
        mock_step9.return_value = (True, None)

        result = await run_defect_discovery_self_test(MagicMock(), 1, 1)

        assert result["success"] is False
        assert result["steps"][0]["status"] == "failed"
        assert "数据库连接异常" in result["steps"][0]["error"]
        # 后续步骤仍然执行
        assert len(result["steps"]) == 9

    @patch("app.services.self_test_service._step_cleanup", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_report", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_assess_severity", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_execute", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_create_task", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_review_and_save", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_generate_cases", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_extract_test_points", new_callable=AsyncMock)
    @patch("app.services.self_test_service._step_requirement_confirmation", new_callable=AsyncMock)
    @patch("app.services.self_test_service._notify_pipeline_summary", new_callable=AsyncMock)
    async def test_return_structure(
        self,
        mock_notify,
        mock_step1,
        mock_step2,
        mock_step3,
        mock_step4,
        mock_step5,
        mock_step6,
        mock_step7,
        mock_step8,
        mock_step9,
    ) -> None:
        """返回结构完整性验证"""
        mock_step1.return_value = (True, None)
        mock_step2.return_value = (True, None, [1])
        mock_step3.return_value = (True, None, [101])
        mock_step4.return_value = (True, None)
        mock_step5.return_value = (True, None, 501)
        mock_step6.return_value = (True, None)
        mock_step7.return_value = (True, None, {"p0": 0, "p1": 1, "p2": 2, "p3": 0})
        mock_step8.return_value = (True, None, 601)
        mock_step9.return_value = (True, None)

        result = await run_defect_discovery_self_test(MagicMock(), 42, 7)

        # 验证返回结构
        assert "project_id" in result
        assert "success" in result
        assert "steps" in result
        assert "defect_summary" in result
        assert "report_id" in result
        assert "task_id" in result

        assert result["project_id"] == 42
        assert isinstance(result["success"], bool)
        assert isinstance(result["steps"], list)
        assert isinstance(result["defect_summary"], dict)

        # 验证步骤结构
        for step in result["steps"]:
            assert "name" in step
            assert "status" in step
            assert "error" in step
            assert "duration_ms" in step
            assert step["status"] in ("success", "failed", "skipped")

        # 验证缺陷摘要结构
        ds = result["defect_summary"]
        assert "p0_count" in ds
        assert "p1_count" in ds
        assert "p2_count" in ds
        assert "p3_count" in ds
        assert "total_defects" in ds


# ---------------------------------------------------------------------------
# 汇总通知测试
# ---------------------------------------------------------------------------

class TestNotifyPipelineSummary:
    """汇总通知测试"""

    @patch("app.core.websocket.manager")
    async def test_notify_success(self, mock_ws_manager) -> None:
        """通知推送成功"""
        mock_ws_manager.broadcast = AsyncMock()

        steps = [
            _build_step_result("需求确认", "success"),
            _build_step_result("测试点提取", "success"),
        ]
        defect_summary = {"p0_count": 1, "p1_count": 2, "p2_count": 3, "p3_count": 1, "total_defects": 7}

        await _notify_pipeline_summary(MagicMock(), 1, steps, defect_summary, 42)

        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args
        message = call_args[0][1]
        assert message["type"] == "defect_discovery_pipeline_summary"
        assert message["project_id"] == 1
        assert message["report_id"] == 42
        assert message["report_link"] == "/report/42"
        assert len(message["step_summary"]) == 2
        assert message["defect_summary"]["total_defects"] == 7

    @patch("app.core.websocket.manager")
    async def test_notify_no_report(self, mock_ws_manager) -> None:
        """无报告时通知链接为 None"""
        mock_ws_manager.broadcast = AsyncMock()

        steps = [_build_step_result("需求确认", "failed", "文档不存在")]
        defect_summary = {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0}

        await _notify_pipeline_summary(MagicMock(), 1, steps, defect_summary, None)

        message = mock_ws_manager.broadcast.call_args[0][1]
        assert message["report_id"] is None
        assert message["report_link"] is None

    @patch("app.core.websocket.manager")
    async def test_notify_ws_error_handled(self, mock_ws_manager) -> None:
        """WebSocket 推送失败不抛异常"""
        mock_ws_manager.broadcast = AsyncMock(side_effect=Exception("WS error"))

        steps = [_build_step_result("需求确认", "success")]
        defect_summary = {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0}

        # 不应抛出异常
        await _notify_pipeline_summary(MagicMock(), 1, steps, defect_summary, None)


# ---------------------------------------------------------------------------
# 定时执行模式切换测试
# ---------------------------------------------------------------------------

class TestSelfTestModeSwitch:
    """定时执行模式切换测试"""

    def test_get_self_test_mode_default(self) -> None:
        """默认模式为 ui_automation"""
        project = MagicMock()
        project.config = None
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "ui_automation"

    def test_get_self_test_mode_full_pipeline(self) -> None:
        """配置为 full_pipeline 时返回 full_pipeline"""
        project = MagicMock()
        project.config = {"self_test_mode": "full_pipeline"}
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "full_pipeline"

    def test_get_self_test_mode_ui_automation(self) -> None:
        """配置为 ui_automation 时返回 ui_automation"""
        project = MagicMock()
        project.config = {"self_test_mode": "ui_automation"}
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "ui_automation"

    def test_get_self_test_mode_invalid_fallback(self) -> None:
        """无效配置值回退到 ui_automation"""
        project = MagicMock()
        project.config = {"self_test_mode": "invalid_mode"}
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "ui_automation"

    def test_get_self_test_mode_string_config(self) -> None:
        """config 为字符串时正确解析"""
        project = MagicMock()
        project.config = json.dumps({"self_test_mode": "full_pipeline"})
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "full_pipeline"

    def test_get_self_test_mode_invalid_json(self) -> None:
        """config 为无效 JSON 字符串时回退"""
        project = MagicMock()
        project.config = "not a json"
        mode = SelfTestScheduler._get_self_test_mode(project)
        assert mode == "ui_automation"

    @patch("app.tasks.self_test_scheduler.run_defect_discovery_self_test", new_callable=AsyncMock)
    @patch("app.db.database.AsyncPrimarySessionLocal")
    async def test_full_pipeline_mode_calls_run_defect_discovery(
        self, mock_session_local, mock_run_pipeline
    ) -> None:
        """full_pipeline 模式调用 run_defect_discovery_self_test"""
        mock_db = AsyncMock()
        mock_session_local.return_value = mock_db

        project = MagicMock()
        project.id = 42
        project.user_id = 1
        project.config = {"self_test_mode": "full_pipeline"}
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = project
        mock_db.execute.return_value = execute_result

        mock_run_pipeline.return_value = {
            "success": True,
            "defect_summary": {"p0_count": 0, "p1_count": 0, "p2_count": 0, "p3_count": 0, "total_defects": 0},
        }

        scheduler = SelfTestScheduler()
        await scheduler._execute_self_test(42)

        mock_run_pipeline.assert_called_once_with(
            db=mock_db, project_id=42, user_id=1
        )
        mock_db.close.assert_called_once()

    @patch("app.db.database.AsyncPrimarySessionLocal")
    async def test_ui_automation_mode_calls_execute_ui(
        self, mock_session_local
    ) -> None:
        """ui_automation 模式调用 _execute_ui_automation"""
        mock_db = AsyncMock()
        mock_session_local.return_value = mock_db

        project = MagicMock()
        project.id = 42
        project.user_id = 1
        project.config = {"self_test_mode": "ui_automation"}
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = project
        mock_db.execute.return_value = execute_result

        scheduler = SelfTestScheduler()
        with patch.object(
            scheduler, "_execute_ui_automation", new_callable=AsyncMock
        ) as mock_ui_exec:
            await scheduler._execute_self_test(42)
            mock_ui_exec.assert_called_once_with(mock_db, project)

    @patch("app.db.database.AsyncPrimarySessionLocal")
    async def test_project_not_found(self, mock_session_local) -> None:
        """项目不存在时记录错误日志"""
        mock_db = AsyncMock()
        mock_session_local.return_value = mock_db
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = execute_result

        scheduler = SelfTestScheduler()
        # 不应抛出异常
        await scheduler._execute_self_test(99999)
        mock_db.close.assert_called_once()

    @patch("app.db.database.AsyncPrimarySessionLocal")
    async def test_execution_exception_handled(self, mock_session_local) -> None:
        """执行异常不抛出"""
        mock_db = AsyncMock()
        mock_session_local.return_value = mock_db

        project = MagicMock()
        project.id = 42
        project.user_id = 1
        project.config = {"self_test_mode": "full_pipeline"}
        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = project
        mock_db.execute.return_value = execute_result

        with patch(
            "app.tasks.self_test_scheduler.run_defect_discovery_self_test",
            new_callable=AsyncMock,
            side_effect=RuntimeError("执行异常"),
        ):
            scheduler = SelfTestScheduler()
            # 不应抛出异常
            await scheduler._execute_self_test(42)
        mock_db.close.assert_called_once()
