"""测试报告与测试结果CRUD操作单元测试"""
import pytest
from app.crud.test_report import (
    create_test_report,
    get_test_reports,
    get_test_report_by_id,
    update_test_report,
    delete_test_report,
    get_test_reports_by_task,
)
from app.crud.test_result import (
    create_test_result,
    get_test_results_by_task,
    get_test_result_by_case,
    update_test_result,
    get_test_results_count,
    delete_test_results_by_task,
)
from app.models.project import Project
from app.models.report import TestReport
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.test_case import TestCase
from app.schemas.test_report import TestReportCreate, TestReportUpdate


@pytest.fixture
def test_project(db, testUser):
    project = Project(
        name="report_test_project",
        user_id=testUser.id,
        description="project for report tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def test_task(db, test_project, testUser):
    """Create a valid TestTask for FK constraints."""
    task = TestTask(
        task_name="test_task_for_results",
        project_id=test_project.id,
        case_ids=[],
        executor_id=testUser.id,
        status=0,
    )
    db.add(task)
    db.flush()
    return task


@pytest.fixture
def test_case(db, test_project):
    """Create a valid TestCase for FK constraints."""
    tc = TestCase(
        case_no="RPT-TC-001",
        project_id=test_project.id,
        module="测试模块",
        title="测试用例",
        precondition="�?,
        steps_json=[{"step": "步骤1", "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="API",
    )
    db.add(tc)
    db.flush()
    return tc


def _make_test_result(db, test_task, test_case, **kwargs):
    """Helper to create a TestResult with valid FK references."""
    defaults = dict(
        task_id=test_task.id,
        project_id=test_task.project_id,
        case_id=test_case.id,
        case_no=test_case.case_no,
        exec_status=0,
    )
    defaults.update(kwargs)
    return create_test_result(db, **defaults)


# ================= Test Report CRUD =================


class TestCreateTestReport:
    def test_create_basic(self, db, test_project, test_task):
        report_data = TestReportCreate(
            name="测试报告1",
            description="描述",
            project_id=test_project.id,
            test_task_id=test_task.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        assert report.id is not None
        assert report.name == "测试报告1"
        assert report.project_id == test_project.id

    def test_create_without_task(self, db, test_project):
        report_data = TestReportCreate(
            name="汇总报�?,
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        assert report.test_task_id is None


class TestGetTestReports:
    def test_get_by_project(self, db, test_project):
        for i in range(3):
            report_data = TestReportCreate(
                name=f"报告{i}",
                project_id=test_project.id,
            )
            create_test_report(db, report_data, user_id=1)
        reports = get_test_reports(db, test_project.id)
        assert len(reports) == 3

    def test_pagination(self, db, test_project):
        for i in range(5):
            report_data = TestReportCreate(
                name=f"报告{i}",
                project_id=test_project.id,
            )
            create_test_report(db, report_data, user_id=1)
        reports = get_test_reports(db, test_project.id, skip=0, limit=2)
        assert len(reports) == 2


class TestGetTestReportById:
    def test_found(self, db, test_project):
        report_data = TestReportCreate(
            name="查找报告",
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        result = get_test_report_by_id(db, report.id, test_project.id)
        assert result is not None
        assert result.id == report.id

    def test_wrong_project(self, db, test_project):
        report_data = TestReportCreate(
            name="隔离报告",
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        result = get_test_report_by_id(db, report.id, 99999)
        assert result is None

    def test_not_found(self, db, test_project):
        result = get_test_report_by_id(db, 99999, test_project.id)
        assert result is None


class TestUpdateTestReport:
    def test_update_name(self, db, test_project):
        report_data = TestReportCreate(
            name="旧名�?,
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        update_data = TestReportUpdate(name="新名�?)
        result = update_test_report(db, report.id, test_project.id, update_data)
        assert result is not None
        assert result.name == "新名�?

    def test_update_partial(self, db, test_project):
        report_data = TestReportCreate(
            name="部分更新",
            description="旧描�?,
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        update_data = TestReportUpdate(description="新描�?)
        result = update_test_report(db, report.id, test_project.id, update_data)
        assert result.description == "新描�?
        assert result.name == "部分更新"

    def test_update_nonexistent(self, db, test_project):
        update_data = TestReportUpdate(name="x")
        result = update_test_report(db, 99999, test_project.id, update_data)
        assert result is None


class TestDeleteTestReport:
    def test_delete_success(self, db, test_project):
        report_data = TestReportCreate(
            name="删除报告",
            project_id=test_project.id,
        )
        report = create_test_report(db, report_data, user_id=1)
        result = delete_test_report(db, report.id, test_project.id)
        assert result is True
        assert get_test_report_by_id(db, report.id, test_project.id) is None

    def test_delete_nonexistent(self, db, test_project):
        result = delete_test_report(db, 99999, test_project.id)
        assert result is False


class TestGetTestReportsByTask:
    def test_filter_by_task(self, db, test_project, test_task):
        report_data1 = TestReportCreate(
            name="任务1报告",
            project_id=test_project.id,
            test_task_id=test_task.id,
        )
        report_data2 = TestReportCreate(
            name="无任务报�?,
            project_id=test_project.id,
        )
        create_test_report(db, report_data1, user_id=1)
        create_test_report(db, report_data2, user_id=1)
        reports = get_test_reports_by_task(db, test_task.id, test_project.id)
        assert len(reports) == 1


# ================= Test Result CRUD =================


class TestCreateTestResult:
    def test_create_basic(self, db, test_task, test_case):
        result = _make_test_result(db, test_task, test_case, exec_status=0)
        assert result.id is not None
        assert result.exec_status == 0
        assert result.case_no == test_case.case_no

    def test_create_with_details(self, db, test_task, test_case):
        result = _make_test_result(
            db, test_task, test_case, exec_status=3,
            exec_log="error log", error_msg="fail msg",
            screenshot_url="/screens/1.png"
        )
        assert result.exec_log == "error log"
        assert result.error_msg == "fail msg"
        assert result.screenshot_url == "/screens/1.png"


class TestGetTestResultsByTask:
    def test_get_results(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=0)
        _make_test_result(db, test_task, test_case, exec_status=1)
        results = get_test_results_by_task(db, test_task.id, test_task.project_id)
        assert len(results) == 2

    def test_wrong_project(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=0)
        results = get_test_results_by_task(db, test_task.id, 99999)
        assert len(results) == 0


class TestGetTestResultByCase:
    def test_found(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=1)
        result = get_test_result_by_case(
            db, test_task.id, test_case.id, test_task.project_id
        )
        assert result is not None
        assert result.case_id == test_case.id

    def test_not_found(self, db, test_task, test_case):
        result = get_test_result_by_case(db, 999, 999, test_task.project_id)
        assert result is None


class TestUpdateTestResult:
    def test_update_status(self, db, test_task, test_case):
        r = _make_test_result(db, test_task, test_case, exec_status=0)
        result = update_test_result(db, r.id, test_task.project_id, exec_status=2)
        assert result is not None
        assert result.exec_status == 2
        assert result.exec_time is not None

    def test_update_multiple_fields(self, db, test_task, test_case):
        r = _make_test_result(db, test_task, test_case, exec_status=0)
        result = update_test_result(
            db, r.id, test_task.project_id,
            exec_status=3, error_msg="blocked", exec_log="log detail"
        )
        assert result.exec_status == 3
        assert result.error_msg == "blocked"
        assert result.exec_log == "log detail"

    def test_update_preserves_unset_fields(self, db, test_task, test_case):
        r = _make_test_result(
            db, test_task, test_case, exec_status=0,
            exec_log="original log"
        )
        result = update_test_result(db, r.id, test_task.project_id, exec_status=1)
        assert result.exec_log == "original log"

    def test_update_nonexistent(self, db, test_task, test_case):
        result = update_test_result(db, 99999, test_task.project_id, exec_status=1)
        assert result is None

    def test_update_zero_status(self, db, test_task, test_case):
        r = _make_test_result(db, test_task, test_case, exec_status=1)
        result = update_test_result(db, r.id, test_task.project_id, exec_status=0)
        assert result.exec_status == 0


class TestGetTestResultsCount:
    def test_count_all(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=1)
        _make_test_result(db, test_task, test_case, exec_status=2)
        count = get_test_results_count(db, test_task.id, test_task.project_id)
        assert count == 2

    def test_count_by_status(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=1)
        _make_test_result(db, test_task, test_case, exec_status=2)
        _make_test_result(db, test_task, test_case, exec_status=1)
        count = get_test_results_count(
            db, test_task.id, test_task.project_id, exec_status=1
        )
        assert count == 2

    def test_count_zero_status(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=0)
        count = get_test_results_count(
            db, test_task.id, test_task.project_id, exec_status=0
        )
        assert count == 1


class TestDeleteTestResultsByTask:
    def test_delete_all(self, db, test_task, test_case):
        _make_test_result(db, test_task, test_case, exec_status=1)
        _make_test_result(db, test_task, test_case, exec_status=2)
        deleted = delete_test_results_by_task(db, test_task.id, test_task.project_id)
        assert deleted == 2
        assert get_test_results_count(db, test_task.id, test_task.project_id) == 0

    def test_delete_no_results(self, db, test_task, test_case):
        deleted = delete_test_results_by_task(db, 999, test_task.project_id)
        assert deleted == 0
