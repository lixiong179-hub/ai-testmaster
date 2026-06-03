"""
缺陷严重度自动评估与 Bug 自动记录单元测试

覆盖场景：
    - P0/P1/P2/P3 各场景严重度评估
    - ux_category 映射正确性
    - Bug 自动创建（含 ux_category 字段）
    - P0/P1 立即通知（mock WebSocket）
    - P2/P3 不立即通知
    - Bug 列表 ux_category 筛选
    - 非自测项目不创建 Bug
    - ux_category 非法值校验
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from app.models.bug import Bug, VALID_UX_CATEGORIES
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.user import User
from app.services.self_test_service import (
    _assess_defect_severity,
    _auto_create_defect_bug,
    _notify_critical_defect_bug,
    _generate_bug_no,
)
from app.tasks.self_test_scheduler import SelfTestScheduler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bugTestUser(db: Session) -> User:
    user = User(
        username="defect_severity_user",
        email="defect_severity@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    yield user


@pytest.fixture
def selfTestProject(db: Session, bugTestUser: User) -> Project:
    project = Project(
        name="缺陷严重度自测项目",
        user_id=bugTestUser.id,
        status=1,
        project_type="web",
        is_self_test=True,
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def normalProject(db: Session, bugTestUser: User) -> Project:
    project = Project(
        name="缺陷严重度普通项目",
        user_id=bugTestUser.id,
        status=1,
        project_type="web",
        is_self_test=False,
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def selfTestTask(db: Session, selfTestProject: Project, bugTestUser: User) -> TestTask:
    task = TestTask(
        task_name="缺陷严重度自测任务",
        project_id=selfTestProject.id,
        executor_id=bugTestUser.id,
        case_ids=[],
        total_count=1,
    )
    db.add(task)
    db.flush()
    yield task


@pytest.fixture
def defectTestCase(db: Session, selfTestProject: Project) -> TestCase:
    case = TestCase(
        case_no="DEFECT-001",
        project_id=selfTestProject.id,
        module="缺陷评估模块",
        title="缺陷评估测试用例",
        precondition="前置条件",
        steps_json=[],
        expected_result="预期结果",
        priority=1,
        case_type="UI",
    )
    db.add(case)
    db.flush()
    yield case


@pytest.fixture
def defectTestResult(
    db: Session, selfTestProject: Project, defectTestCase: TestCase, selfTestTask: TestTask
) -> TestResult:
    result = TestResult(
        task_id=selfTestTask.id,
        project_id=selfTestProject.id,
        case_id=defectTestCase.id,
        case_no=defectTestCase.case_no,
        exec_status=2,
        error_msg="功能缺陷: 页面显示异常",
        exec_log="执行步骤1: 打开页面",
    )
    db.add(result)
    db.flush()
    yield result


# ---------------------------------------------------------------------------
# 严重度评估测试
# ---------------------------------------------------------------------------


class TestAssessDefectSeverityP0:
    """P0 严重度评估测试"""

    def test_no_sensitive_data_is_p0(self) -> None:
        severity, ux_cat = _assess_defect_severity("no_sensitive_data")
        assert severity == 1
        assert ux_cat == "security"

    def test_no_xss_is_p0(self) -> None:
        severity, ux_cat = _assess_defect_severity("no_xss")
        assert severity == 1
        assert ux_cat == "security"

    def test_crash_500_is_p0(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="页面白屏，500错误"
        )
        assert severity == 1
        assert ux_cat is None

    def test_blank_page_is_p0(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="blank page detected"
        )
        assert severity == 1

    def test_internal_server_error_is_p0(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="internal server error"
        )
        assert severity == 1


class TestAssessDefectSeverityP1:
    """P1 严重度评估测试"""

    def test_element_not_found_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity("element_not_found")
        assert severity == 2
        assert ux_cat is None

    def test_locator_failure_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity("locator_failure")
        assert severity == 2

    def test_no_such_element_in_error_message_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="no such element found"
        )
        assert severity == 2

    def test_no_network_errors_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity("no_network_errors")
        assert severity == 2
        assert ux_cat == "response_performance"

    def test_5xx_network_failure_is_p1(self) -> None:
        evidence = {
            "network_failures": [{"url": "/api/data", "status": 500, "method": "GET"}]
        }
        severity, ux_cat = _assess_defect_severity(
            "unknown", defect_evidence=evidence
        )
        assert severity == 2
        assert ux_cat == "response_performance"

    def test_503_network_failure_is_p1(self) -> None:
        evidence = {
            "network_failures": [{"url": "/api/data", "status": 503, "method": "GET"}]
        }
        severity, ux_cat = _assess_defect_severity(
            "unknown", defect_evidence=evidence
        )
        assert severity == 2

    def test_data_inconsistency_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="数据不一致，显示错误"
        )
        assert severity == 2

    def test_permission_bypass_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity(
            "unknown", error_message="权限绕过漏洞"
        )
        assert severity == 2

    def test_memory_leak_suspect_is_p1(self) -> None:
        severity, ux_cat = _assess_defect_severity("memory_leak_suspect")
        assert severity == 2
        assert ux_cat == "response_performance"

    def test_memory_leak_in_evidence_is_p1(self) -> None:
        evidence = {"memory_leak_suspect": {"heap_growth_mb": 150}}
        severity, ux_cat = _assess_defect_severity(
            "unknown", defect_evidence=evidence
        )
        assert severity == 2
        assert ux_cat == "response_performance"


class TestAssessDefectSeverityP2:
    """P2 严重度评估测试"""

    def test_loading_hidden_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("loading_hidden")
        assert severity == 3
        assert ux_cat == "loading_experience"

    def test_loading_visible_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("loading_visible")
        assert severity == 3
        assert ux_cat == "loading_experience"

    def test_response_time_lt_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("response_time_lt")
        assert severity == 3
        assert ux_cat == "response_performance"

    def test_text_not_empty_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("text_not_empty")
        assert severity == 3
        assert ux_cat == "empty_state"

    def test_visible_assertion_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("visible")
        assert severity == 3
        assert ux_cat == "visual_consistency"

    def test_not_visible_assertion_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("not_visible")
        assert severity == 3
        assert ux_cat == "visual_consistency"

    def test_text_contains_is_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("text_contains")
        assert severity == 3
        assert ux_cat == "visual_consistency"


class TestAssessDefectSeverityP3:
    """P3 严重度评估测试"""

    def test_no_console_errors_is_p3(self) -> None:
        severity, ux_cat = _assess_defect_severity("no_console_errors")
        assert severity == 4
        assert ux_cat == "error_feedback"

    def test_url_contains_is_p3(self) -> None:
        severity, ux_cat = _assess_defect_severity("url_contains")
        assert severity == 4
        assert ux_cat is None

    def test_url_equals_is_p3(self) -> None:
        severity, ux_cat = _assess_defect_severity("url_equals")
        assert severity == 4
        assert ux_cat is None


class TestAssessDefectSeverityDefault:
    """默认严重度评估测试"""

    def test_unknown_failure_type_defaults_to_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("some_unknown_type")
        assert severity == 3
        assert ux_cat is None

    def test_empty_failure_type_defaults_to_p2(self) -> None:
        severity, ux_cat = _assess_defect_severity("")
        assert severity == 3

    def test_case_insensitive_matching(self) -> None:
        severity, ux_cat = _assess_defect_severity("NO_SENSITIVE_DATA")
        assert severity == 1
        assert ux_cat == "security"

    def test_no_xss_case_insensitive(self) -> None:
        severity, ux_cat = _assess_defect_severity("No_Xss")
        assert severity == 1


# ---------------------------------------------------------------------------
# ux_category 映射正确性测试
# ---------------------------------------------------------------------------


class TestUxCategoryMapping:
    """ux_category 映射正确性测试"""

    def test_security_mapping(self) -> None:
        for ft in ("no_sensitive_data", "no_xss"):
            _, ux_cat = _assess_defect_severity(ft)
            assert ux_cat == "security", f"{ft} 应映射到 security"

    def test_loading_experience_mapping(self) -> None:
        for ft in ("loading_hidden", "loading_visible"):
            _, ux_cat = _assess_defect_severity(ft)
            assert ux_cat == "loading_experience", f"{ft} 应映射到 loading_experience"

    def test_error_feedback_mapping(self) -> None:
        _, ux_cat = _assess_defect_severity("no_console_errors")
        assert ux_cat == "error_feedback"

    def test_response_performance_mapping(self) -> None:
        for ft in ("no_network_errors", "response_time_lt", "memory_leak_suspect"):
            _, ux_cat = _assess_defect_severity(ft)
            assert ux_cat == "response_performance", f"{ft} 应映射到 response_performance"

    def test_empty_state_mapping(self) -> None:
        _, ux_cat = _assess_defect_severity("text_not_empty")
        assert ux_cat == "empty_state"

    def test_valid_ux_categories_constant(self) -> None:
        """验证 VALID_UX_CATEGORIES 包含所有合法值"""
        expected = {
            "loading_experience", "error_feedback", "response_performance",
            "visual_consistency", "empty_state", "security",
        }
        assert VALID_UX_CATEGORIES == expected


# ---------------------------------------------------------------------------
# Bug 自动创建测试
# ---------------------------------------------------------------------------


class TestAutoCreateDefectBug:
    """Bug 自动创建测试"""

    def test_auto_create_bug_for_self_test_project(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db,
            project=selfTestProject,
            failure_type="no_sensitive_data",
            error_message="敏感数据暴露",
            step_description="检查敏感数据",
        )
        assert bug is not None
        assert bug.id is not None
        assert bug.source == "self_test"
        assert bug.status == "open"
        assert bug.severity == 1
        assert bug.ux_category == "security"
        assert bug.project_id == selfTestProject.id
        assert bug.reporter_id == selfTestProject.user_id

    def test_auto_create_bug_with_evidence(
        self, db: Session, selfTestProject: Project
    ) -> None:
        evidence = {
            "console_errors": [{"type": "error", "message": "Uncaught TypeError"}],
            "network_failures": [],
        }
        bug = _auto_create_defect_bug(
            db=db,
            project=selfTestProject,
            failure_type="no_console_errors",
            error_message="控制台存在错误",
            defect_evidence=evidence,
        )
        assert bug is not None
        assert bug.severity == 4
        assert bug.ux_category == "error_feedback"
        assert "缺陷证据" in bug.description

    def test_auto_create_bug_with_test_result(
        self, db: Session, selfTestProject: Project,
        defectTestCase: TestCase, defectTestResult: TestResult,
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db,
            project=selfTestProject,
            failure_type="loading_hidden",
            error_message="加载指示器未在10秒内隐藏",
            test_case_id=defectTestCase.id,
            test_result_id=defectTestResult.id,
            step_description="等待加载完成",
        )
        assert bug is not None
        assert bug.test_case_id == defectTestCase.id
        assert bug.test_result_id == defectTestResult.id
        assert bug.severity == 3
        assert bug.ux_category == "loading_experience"

    def test_no_bug_for_normal_project(
        self, db: Session, normalProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db,
            project=normalProject,
            failure_type="no_sensitive_data",
            error_message="敏感数据暴露",
        )
        assert bug is None

    def test_bug_priority_mapping(
        self, db: Session, selfTestProject: Project
    ) -> None:
        """验证 severity 到 priority 的映射"""
        # P0 → priority 1
        bug_p0 = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_xss", error_message="XSS漏洞",
        )
        assert bug_p0.priority == 1

        # P1 → priority 1
        bug_p1 = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="element_not_found", error_message="元素未找到",
        )
        assert bug_p1.priority == 1

        # P2 → priority 2
        bug_p2 = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="loading_hidden", error_message="加载超时",
        )
        assert bug_p2.priority == 2

        # P3 → priority 3
        bug_p3 = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_console_errors", error_message="控制台错误",
        )
        assert bug_p3.priority == 3

    def test_bug_title_contains_severity_prefix(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_sensitive_data",
            error_message="敏感数据暴露",
            step_description="安全检查",
        )
        assert "[P1]" in bug.title

    def test_bug_description_contains_ux_category(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_xss", error_message="XSS漏洞",
        )
        assert "UX分类: security" in bug.description

    def test_bug_description_shows_functional_bug_when_no_ux_category(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="element_not_found", error_message="元素未找到",
        )
        assert "UX分类: 功能Bug" in bug.description


# ---------------------------------------------------------------------------
# Bug 编号生成测试
# ---------------------------------------------------------------------------


class TestGenerateBugNo:
    """Bug 编号生成测试"""

    def test_bug_no_format(self, db: Session, selfTestProject: Project) -> None:
        bug_no = _generate_bug_no(db, selfTestProject.id)
        assert bug_no.startswith(f"BUG-{selfTestProject.id}-")
        # 序号部分应为4位数字
        parts = bug_no.split("-")
        assert len(parts[-1]) == 4
        assert parts[-1].isdigit()

    def test_bug_no_increments(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug_no1 = _generate_bug_no(db, selfTestProject.id)
        # 在两次调用之间插入一条 Bug 记录，使 count 递增
        from app.models.bug import Bug as BugModel
        temp_bug = BugModel(
            bug_no=bug_no1,
            project_id=selfTestProject.id,
            title="临时Bug",
            description="描述",
            severity=3,
            priority=2,
            reporter_id=selfTestProject.user_id,
        )
        db.add(temp_bug)
        db.flush()
        bug_no2 = _generate_bug_no(db, selfTestProject.id)
        seq1 = int(bug_no1.split("-")[-1])
        seq2 = int(bug_no2.split("-")[-1])
        assert seq2 > seq1


# ---------------------------------------------------------------------------
# P0/P1 立即通知测试
# ---------------------------------------------------------------------------


class TestNotifyCriticalDefectBug:
    """P0/P1 缺陷立即通知测试"""

    @pytest.mark.asyncio
    async def test_p0_bug_triggers_notification(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_sensitive_data",
            error_message="敏感数据暴露",
        )
        assert bug is not None

        with patch("app.core.websocket.manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await _notify_critical_defect_bug(bug, selfTestProject)
            mock_ws.broadcast.assert_called_once()

            call_args = mock_ws.broadcast.call_args
            channel = call_args[0][0]
            message = call_args[0][1]
            assert channel == str(selfTestProject.id)
            assert message["type"] == "critical_defect_notification"
            assert message["bug_no"] == bug.bug_no
            assert message["severity"] == 1
            assert message["ux_category"] == "security"

    @pytest.mark.asyncio
    async def test_p1_bug_triggers_notification(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="element_not_found",
            error_message="元素未找到",
        )
        assert bug is not None

        with patch("app.core.websocket.manager") as mock_ws:
            mock_ws.broadcast = AsyncMock()
            await _notify_critical_defect_bug(bug, selfTestProject)
            mock_ws.broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_notification_failure_does_not_raise(
        self, db: Session, selfTestProject: Project
    ) -> None:
        """WebSocket 通知失败不应抛出异常"""
        bug = _auto_create_defect_bug(
            db=db, project=selfTestProject,
            failure_type="no_xss", error_message="XSS漏洞",
        )
        assert bug is not None

        with patch("app.core.websocket.manager") as mock_ws:
            mock_ws.broadcast = AsyncMock(side_effect=Exception("连接失败"))
            # 不应抛出异常
            await _notify_critical_defect_bug(bug, selfTestProject)


class TestSchedulerHandleStepFailure:
    """SelfTestScheduler.handle_step_failure 集成测试"""

    @pytest.mark.asyncio
    async def test_p0_bug_notified_immediately(
        self, db: Session, selfTestProject: Project
    ) -> None:
        scheduler = SelfTestScheduler()

        with patch(
            "app.tasks.self_test_scheduler._notify_critical_defect_bug"
        ) as mock_notify:
            mock_notify.return_value = None
            bug = await scheduler.handle_step_failure(
                db=db,
                project=selfTestProject,
                failure_type="no_sensitive_data",
                error_message="敏感数据暴露",
            )
            assert bug is not None
            assert bug.severity == 1
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_p2_bug_not_notified(
        self, db: Session, selfTestProject: Project
    ) -> None:
        scheduler = SelfTestScheduler()

        with patch(
            "app.tasks.self_test_scheduler._notify_critical_defect_bug"
        ) as mock_notify:
            mock_notify.return_value = None
            bug = await scheduler.handle_step_failure(
                db=db,
                project=selfTestProject,
                failure_type="loading_hidden",
                error_message="加载指示器未在10秒内隐藏",
            )
            assert bug is not None
            assert bug.severity == 3
            # P2 缺陷不应触发立即通知
            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_p3_bug_not_notified(
        self, db: Session, selfTestProject: Project
    ) -> None:
        scheduler = SelfTestScheduler()

        with patch(
            "app.tasks.self_test_scheduler._notify_critical_defect_bug"
        ) as mock_notify:
            mock_notify.return_value = None
            bug = await scheduler.handle_step_failure(
                db=db,
                project=selfTestProject,
                failure_type="no_console_errors",
                error_message="控制台存在错误",
            )
            assert bug is not None
            assert bug.severity == 4
            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_project_returns_none(
        self, db: Session, normalProject: Project
    ) -> None:
        scheduler = SelfTestScheduler()

        with patch(
            "app.tasks.self_test_scheduler._notify_critical_defect_bug"
        ) as mock_notify:
            bug = await scheduler.handle_step_failure(
                db=db,
                project=normalProject,
                failure_type="no_sensitive_data",
                error_message="敏感数据暴露",
            )
            assert bug is None
            mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Bug 列表 ux_category 筛选测试
# ---------------------------------------------------------------------------


class TestBugListUxCategoryFilter:
    """Bug 列表 API ux_category 筛选测试"""

    def test_list_bugs_with_ux_category_filter(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        """测试 ux_category 筛选功能"""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.database import get_db
        from app.utils.jwt_utils import create_access_token

        # 创建不同 ux_category 的 Bug（使用唯一编号避免冲突）
        import uuid
        unique_suffix = uuid.uuid4().hex[:8]
        bug1 = Bug(
            bug_no=f"BUG-FILTER-SEC-{unique_suffix}",
            project_id=selfTestProject.id,
            title="安全缺陷",
            description="安全缺陷描述",
            severity=1,
            priority=1,
            source="self_test",
            ux_category="security",
            reporter_id=bugTestUser.id,
        )
        bug2 = Bug(
            bug_no=f"BUG-FILTER-LOAD-{unique_suffix}",
            project_id=selfTestProject.id,
            title="加载体验缺陷",
            description="加载体验描述",
            severity=3,
            priority=2,
            source="self_test",
            ux_category="loading_experience",
            reporter_id=bugTestUser.id,
        )
        db.add(bug1)
        db.add(bug2)
        db.flush()

        # 生成认证 token
        token = create_access_token(
            {"sub": str(bugTestUser.id), "username": bugTestUser.username}
        )

        def overrideGetDb():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = overrideGetDb

        try:
            with TestClient(app) as client:
                # 筛选 security
                resp = client.get(
                    "/api/v1/bugs/list",
                    params={"project_id": selfTestProject.id, "ux_category": "security"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                security_bugs = [b for b in data["items"] if b["ux_category"] == "security"]
                assert len(security_bugs) >= 1

                # 筛选 loading_experience
                resp2 = client.get(
                    "/api/v1/bugs/list",
                    params={"project_id": selfTestProject.id, "ux_category": "loading_experience"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp2.status_code == 200
                data2 = resp2.json()["data"]
                loading_bugs = [b for b in data2["items"] if b["ux_category"] == "loading_experience"]
                assert len(loading_bugs) >= 1
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_list_bugs_invalid_ux_category(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        """测试非法 ux_category 返回 400"""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.database import get_db
        from app.utils.jwt_utils import create_access_token

        token = create_access_token(
            {"sub": str(bugTestUser.id), "username": bugTestUser.username}
        )

        def overrideGetDb():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = overrideGetDb

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/api/v1/bugs/list",
                    params={"project_id": selfTestProject.id, "ux_category": "invalid_category"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_list_bugs_without_ux_category_filter(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        """测试不传 ux_category 时返回全部 Bug"""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db.database import get_db
        from app.utils.jwt_utils import create_access_token

        token = create_access_token(
            {"sub": str(bugTestUser.id), "username": bugTestUser.username}
        )

        def overrideGetDb():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = overrideGetDb

        try:
            with TestClient(app) as client:
                resp = client.get(
                    "/api/v1/bugs/list",
                    params={"project_id": selfTestProject.id},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert "items" in data
                assert "total" in data
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Bug 模型 ux_category 字段测试
# ---------------------------------------------------------------------------


class TestBugModelUxCategory:
    """Bug 模型 ux_category 字段测试"""

    def test_ux_category_nullable(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        bug = Bug(
            bug_no="BUG-UX-001",
            project_id=selfTestProject.id,
            title="无UX分类Bug",
            description="描述",
            severity=2,
            priority=2,
            reporter_id=bugTestUser.id,
            source="manual",
            ux_category=None,
        )
        db.add(bug)
        db.flush()
        assert bug.ux_category is None

    def test_ux_category_with_value(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        bug = Bug(
            bug_no="BUG-UX-002",
            project_id=selfTestProject.id,
            title="安全分类Bug",
            description="描述",
            severity=1,
            priority=1,
            reporter_id=bugTestUser.id,
            source="self_test",
            ux_category="security",
        )
        db.add(bug)
        db.flush()
        assert bug.ux_category == "security"

    def test_all_valid_ux_categories(
        self, db: Session, selfTestProject: Project, bugTestUser: User
    ) -> None:
        """验证所有合法 ux_category 值均可写入"""
        for idx, cat in enumerate(sorted(VALID_UX_CATEGORIES), start=10):
            bug = Bug(
                bug_no=f"BUG-UX-CAT-{idx:03d}",
                project_id=selfTestProject.id,
                title=f"{cat}分类Bug",
                description="描述",
                severity=3,
                priority=2,
                reporter_id=bugTestUser.id,
                source="self_test",
                ux_category=cat,
            )
            db.add(bug)
            db.flush()
            assert bug.ux_category == cat
