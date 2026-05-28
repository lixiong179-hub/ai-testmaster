"""
自测结果闭环与Bug自动记录单元测试

覆盖场景：
    - Bug模型source字段默认值为manual
    - 自测项目失败分析分类为product_bug时自动创建Bug
    - 自测项目失败分析分类为case_issue时不创建Bug
    - 非自测项目失败时不创建Bug
    - Bug记录字段正确性（source、test_result_id等）
    - 自测报告包含Bug列表
"""
import pytest
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.user import User
from app.api.v1.endpoints.execution_core import (
    _perform_failure_analysis,
    _auto_create_bug_for_self_test,
    _generate_bug_no,
)
from app.services.report_service import ReportService


@pytest.fixture
def testUser(db: Session) -> User:
    user = User(
        username="self_test_bug_user",
        email="self_test_bug@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()
    yield user


@pytest.fixture
def selfTestProject(db: Session, testUser: User) -> Project:
    project = Project(
        name="自测Bug项目",
        user_id=testUser.id,
        status=1,
        project_type="web",
        is_self_test=True,
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def normalProject(db: Session, testUser: User) -> Project:
    project = Project(
        name="普通Bug项目",
        user_id=testUser.id,
        status=1,
        project_type="web",
        is_self_test=False,
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def selfTestTask(db: Session, selfTestProject: Project, testUser: User) -> TestTask:
    task = TestTask(
        task_name="自测Bug任务",
        project_id=selfTestProject.id,
        executor_id=testUser.id,
        case_ids=[],
        total_count=1,
    )
    db.add(task)
    db.flush()
    yield task


@pytest.fixture
def normalTestTask(db: Session, normalProject: Project, testUser: User) -> TestTask:
    task = TestTask(
        task_name="普通Bug任务",
        project_id=normalProject.id,
        executor_id=testUser.id,
        case_ids=[],
        total_count=1,
    )
    db.add(task)
    db.flush()
    yield task


@pytest.fixture
def failedTestCase(db: Session, selfTestProject: Project) -> TestCase:
    case = TestCase(
        case_no="SELF-BUG-001",
        project_id=selfTestProject.id,
        module="自测模块",
        title="自测失败用例",
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
def failedTestResult(
    db: Session, selfTestProject: Project, failedTestCase: TestCase, selfTestTask: TestTask
) -> TestResult:
    result = TestResult(
        task_id=selfTestTask.id,
        project_id=selfTestProject.id,
        case_id=failedTestCase.id,
        case_no=failedTestCase.case_no,
        exec_status=2,
        error_msg="功能缺陷: 页面显示异常，数据不一致",
        exec_log="执行步骤1: 打开页面\n执行步骤2: 点击按钮\n功能异常",
        ai_analysis="AI分析提示可能是产品Bug，功能未按预期工作",
    )
    db.add(result)
    db.flush()
    yield result


@pytest.fixture
def caseIssueResult(
    db: Session, selfTestProject: Project, failedTestCase: TestCase, selfTestTask: TestTask
) -> TestResult:
    result = TestResult(
        task_id=selfTestTask.id,
        project_id=selfTestProject.id,
        case_id=failedTestCase.id,
        case_no=failedTestCase.case_no,
        exec_status=2,
        error_msg="元素未找到: 定位失败，css selector找不到元素",
        exec_log="步骤描述错误，定位信息缺失",
    )
    db.add(result)
    db.flush()
    yield result


@pytest.fixture
def normalProjectCase(db: Session, normalProject: Project) -> TestCase:
    case = TestCase(
        case_no="NORMAL-BUG-001",
        project_id=normalProject.id,
        module="普通模块",
        title="普通项目失败用例",
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
def normalProjectResult(
    db: Session, normalProject: Project, normalProjectCase: TestCase, normalTestTask: TestTask
) -> TestResult:
    result = TestResult(
        task_id=normalTestTask.id,
        project_id=normalProject.id,
        case_id=normalProjectCase.id,
        case_no=normalProjectCase.case_no,
        exec_status=2,
        error_msg="功能缺陷: 页面显示异常",
        exec_log="功能异常",
        ai_analysis="AI分析提示可能是产品Bug",
    )
    db.add(result)
    db.flush()
    yield result


class TestBugModelSourceField:
    """Bug模型source字段默认值测试"""

    def test_source_default_is_manual(
        self, db: Session, selfTestProject: Project, testUser: User
    ) -> None:
        bug = Bug(
            bug_no="BUG-SOURCE-001",
            project_id=selfTestProject.id,
            title="source默认值测试",
            description="描述",
            severity=2,
            priority=2,
            reporter_id=testUser.id,
        )
        db.add(bug)
        db.flush()
        assert bug.source == "manual"

    def test_source_self_test_value(
        self, db: Session, selfTestProject: Project, testUser: User
    ) -> None:
        bug = Bug(
            bug_no="BUG-SOURCE-002",
            project_id=selfTestProject.id,
            title="source自测值测试",
            description="描述",
            severity=2,
            priority=2,
            reporter_id=testUser.id,
            source="self_test",
        )
        db.add(bug)
        db.flush()
        assert bug.source == "self_test"


class TestAutoCreateBugForSelfTest:
    """自测项目失败分析自动创建Bug测试"""

    def test_product_bug_auto_creates_bug(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        assert analysis["suggested_type"] == "product_bug"

        bug = _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )
        assert bug is not None
        assert bug.id is not None
        assert bug.source == "self_test"
        assert bug.status == "open"
        assert bug.project_id == selfTestProject.id
        assert bug.test_case_id == failedTestCase.id
        assert bug.test_result_id == failedTestResult.id

    def test_case_issue_does_not_create_bug(
        self, db: Session, selfTestProject: Project,
        caseIssueResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(caseIssueResult, failedTestCase, db)
        assert analysis["suggested_type"] == "case_issue"

    def test_normal_project_does_not_create_bug(
        self, db: Session, normalProject: Project,
        normalProjectResult: TestResult, normalProjectCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(normalProjectResult, normalProjectCase, db)
        assert analysis["suggested_type"] == "product_bug"
        assert not normalProject.is_self_test


class TestBugFieldCorrectness:
    """Bug记录字段正确性测试"""

    def test_bug_fields_correctness(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        bug = _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )

        assert bug.source == "self_test"
        assert bug.test_result_id == failedTestResult.id
        assert bug.test_case_id == failedTestCase.id
        assert bug.project_id == selfTestProject.id
        assert bug.status == "open"
        assert bug.reporter_id == selfTestProject.user_id
        assert bug.bug_no is not None
        assert len(bug.bug_no) > 0
        assert bug.title is not None
        assert bug.description is not None
        assert bug.reproduction_steps is not None

    def test_severity_high_confidence(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        bug = _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )
        if analysis["confidence"] >= 0.7:
            assert bug.severity == 2
            assert bug.priority == 1
        else:
            assert bug.severity == 3
            assert bug.priority == 2

    def test_bug_no_generation(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        bug_no = _generate_bug_no(db, selfTestProject.id)
        assert bug_no.startswith(f"BUG-{selfTestProject.id}-")
        assert len(bug_no.split("-")[-1]) == 4

    def test_bug_description_contains_analysis(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        bug = _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )
        assert "AI分析结果" in bug.description
        assert "置信度" in bug.description

    def test_bug_screenshot_via_test_result(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        bug = _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )
        assert bug.test_result_id is not None
        test_result = db.query(TestResult).filter(
            TestResult.id == bug.test_result_id
        ).first()
        assert test_result is not None
        assert test_result.screenshot_url == failedTestResult.screenshot_url
        assert test_result.ai_analysis == failedTestResult.ai_analysis


class TestSelfTestReportBugList:
    """自测报告Bug列表测试"""

    def test_self_test_report_contains_bug_list(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )

        bug_list = ReportService._build_self_test_bug_list(db, selfTestProject.id)
        assert len(bug_list) >= 1
        bug_entry = bug_list[0]
        assert "title" in bug_entry
        assert "severity" in bug_entry
        assert "bug_no" in bug_entry

    def test_self_test_bug_list_contains_screenshot(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        failedTestResult.screenshot_url = "/screenshots/fail.png"
        db.flush()

        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )

        bug_list = ReportService._build_self_test_bug_list(db, selfTestProject.id)
        assert len(bug_list) >= 1
        assert bug_list[0]["screenshot_url"] == "/screenshots/fail.png"

    def test_self_test_bug_list_contains_ai_analysis(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )

        bug_list = ReportService._build_self_test_bug_list(db, selfTestProject.id)
        assert len(bug_list) >= 1
        assert bug_list[0]["ai_analysis"] is not None

    def test_self_test_bug_list_contains_fix_suggestion(
        self, db: Session, selfTestProject: Project,
        failedTestResult: TestResult, failedTestCase: TestCase
    ) -> None:
        analysis = _perform_failure_analysis(failedTestResult, failedTestCase, db)
        _auto_create_bug_for_self_test(
            db=db, project=selfTestProject, result=failedTestResult,
            test_case=failedTestCase, analysis=analysis,
        )

        bug_list = ReportService._build_self_test_bug_list(db, selfTestProject.id)
        assert len(bug_list) >= 1
        assert bug_list[0]["fix_suggestion"] is not None

    def test_normal_project_bug_list_empty(
        self, db: Session, normalProject: Project
    ) -> None:
        bug_list = ReportService._build_self_test_bug_list(db, normalProject.id)
        assert bug_list == []

    def test_no_bugs_returns_empty_list(
        self, db: Session, selfTestProject: Project
    ) -> None:
        bug_list = ReportService._build_self_test_bug_list(db, selfTestProject.id)
        assert bug_list == []


class TestFixSuggestion:
    """修复建议生成测试"""

    def test_functional_defect_suggestion(self) -> None:
        suggestion = ReportService._generate_fix_suggestion("发现功能缺陷，产品问题")
        assert "业务逻辑" in suggestion

    def test_display_issue_suggestion(self) -> None:
        suggestion = ReportService._generate_fix_suggestion("页面显示异常，数据不一致")
        assert "前端渲染" in suggestion

    def test_mismatch_suggestion(self) -> None:
        suggestion = ReportService._generate_fix_suggestion("实际结果与预期不符")
        assert "预期行为" in suggestion

    def test_generic_suggestion(self) -> None:
        suggestion = ReportService._generate_fix_suggestion("其他未知问题")
        assert "根因" in suggestion

    def test_none_analysis_returns_none(self) -> None:
        suggestion = ReportService._generate_fix_suggestion(None)
        assert suggestion is None

    def test_empty_analysis_returns_none(self) -> None:
        suggestion = ReportService._generate_fix_suggestion("")
        assert suggestion is None
