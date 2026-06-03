"""缺陷发现率指标与缺陷报告单元测试。

覆盖范围：
    - calculate_defect_metrics: 缺陷指标计算（各种场景）
    - _is_implicit_defect: 隐性缺陷判定
    - _collect_implicit_evidence: 隐性缺陷证据收集
    - ReportService._build_defect_overview: 报告缺陷概览
    - ReportService._build_defect_list: 报告缺陷明细
    - ReportService._build_defect_distribution: 报告缺陷分布
    - ReportService._build_implicit_defects: 报告隐性缺陷
    - ReportService._build_security_findings: 报告安全发现
    - ReportService._build_coverage_assessment: 报告覆盖评估
    - coverage_insufficient_warning 逻辑
    - 报告生成含缺陷维度数据
"""
import pytest
from app.services.self_test_service import (
    calculate_defect_metrics,
    _is_implicit_defect,
    _collect_implicit_evidence,
)
from app.services.report_service import ReportService
from app.models.bug import Bug
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_result import TestResult
from app.models.test_task import TestTask
from app.models.enums import ExecStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def defect_project(db, testUser):
    """创建用于缺陷指标测试的项目。"""
    project = Project(
        name="defect_metrics_project",
        user_id=testUser.id,
        description="project for defect metrics tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def defect_task(db, defect_project, testUser):
    """创建用于缺陷指标测试的任务。"""
    task = TestTask(
        task_name="defect_metrics_task",
        project_id=defect_project.id,
        case_ids=[],
        executor_id=testUser.id,
        status=0,
    )
    db.add(task)
    db.flush()
    return task


def _create_test_case(db, project_id: int, module: str, case_no: str) -> TestCase:
    """辅助函数：创建测试用例。"""
    tc = TestCase(
        case_no=case_no,
        project_id=project_id,
        module=module,
        title=f"用例-{module}-{case_no}",
        precondition="无",
        steps_json=[{"step": "步骤1", "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="API",
    )
    db.add(tc)
    db.flush()
    return tc


def _create_test_result(
    db,
    task_id: int,
    project_id: int,
    case_id: int,
    case_no: str,
    exec_status: int,
    defect_evidence: dict = None,
) -> TestResult:
    """辅助函数：创建测试结果。"""
    result = TestResult(
        task_id=task_id,
        project_id=project_id,
        case_id=case_id,
        case_no=case_no,
        exec_status=exec_status,
        defect_evidence=defect_evidence,
    )
    db.add(result)
    db.flush()
    return result


def _create_bug(
    db,
    project_id: int,
    reporter_id: int,
    severity: int,
    ux_category: str = None,
    test_case_id: int = None,
    test_result_id: int = None,
) -> Bug:
    """辅助函数：创建 Bug 记录。"""
    import uuid
    bug_no = f"BUG-{project_id}-TEST-{uuid.uuid4().hex[:6]}"
    bug = Bug(
        bug_no=bug_no,
        project_id=project_id,
        title=f"[P{severity}] 测试缺陷",
        description=f"测试缺陷描述 severity={severity}",
        severity=severity,
        priority=1 if severity <= 2 else 2,
        status="open",
        source="self_test",
        ux_category=ux_category,
        reporter_id=reporter_id,
        test_case_id=test_case_id,
        test_result_id=test_result_id,
    )
    db.add(bug)
    db.flush()
    return bug


# ---------------------------------------------------------------------------
# _is_implicit_defect 测试
# ---------------------------------------------------------------------------


class TestIsImplicitDefect:
    """隐性缺陷判定逻辑测试。"""

    def test_none_evidence(self):
        assert _is_implicit_defect(None) is False

    def test_empty_evidence(self):
        assert _is_implicit_defect({}) is False

    def test_console_errors_non_empty(self):
        assert _is_implicit_defect({"console_errors": ["Uncaught TypeError"]}) is True

    def test_network_failures_non_empty(self):
        assert _is_implicit_defect({"network_failures": [{"status": 500}]}) is True

    def test_memory_leak_suspect_non_empty(self):
        assert _is_implicit_defect({"memory_leak_suspect": {"trend": "increasing"}}) is True

    def test_uncaught_exceptions_non_empty(self):
        assert _is_implicit_defect({"uncaught_exceptions": ["Error at line 42"]}) is True

    def test_all_empty_values(self):
        evidence = {
            "console_errors": [],
            "network_failures": [],
            "memory_leak_suspect": None,
            "uncaught_exceptions": [],
        }
        assert _is_implicit_defect(evidence) is False

    def test_mixed_evidence(self):
        evidence = {
            "console_errors": [],
            "network_failures": [{"status": 502}],
            "other_key": "value",
        }
        assert _is_implicit_defect(evidence) is True

    def test_irrelevant_keys_only(self):
        evidence = {"other_key": "value", "another_key": [1, 2, 3]}
        assert _is_implicit_defect(evidence) is False


# ---------------------------------------------------------------------------
# _collect_implicit_evidence 测试
# ---------------------------------------------------------------------------


class TestCollectImplicitEvidence:
    """隐性缺陷证据收集测试。"""

    def test_empty_results(self):
        result = _collect_implicit_evidence([])
        assert result == {
            "console_errors": [],
            "network_failures": [],
            "memory_leak_suspect": [],
            "uncaught_exceptions": [],
        }

    def test_passed_with_implicit_evidence(self, db, defect_project, defect_task):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-001")
        tr = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={
                "console_errors": ["TypeError: x is not a function"],
                "network_failures": [{"status": 502, "url": "/api/test"}],
            },
        )
        collected = _collect_implicit_evidence([tr])
        assert len(collected["console_errors"]) == 1
        assert len(collected["network_failures"]) == 1

    def test_failed_result_excluded(self, db, defect_project, defect_task):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-002")
        tr = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
            defect_evidence={"console_errors": ["Error"]},
        )
        collected = _collect_implicit_evidence([tr])
        assert len(collected["console_errors"]) == 0

    def test_passed_without_evidence_excluded(self, db, defect_project, defect_task):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-003")
        tr = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence=None,
        )
        collected = _collect_implicit_evidence([tr])
        assert all(len(v) == 0 for v in collected.values())

    def test_multiple_results_aggregated(self, db, defect_project, defect_task):
        tc1 = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-004")
        tc2 = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-005")
        tr1 = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc1.id,
            case_no=tc1.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={"console_errors": ["Error1"]},
        )
        tr2 = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc2.id,
            case_no=tc2.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={"console_errors": ["Error2"]},
        )
        collected = _collect_implicit_evidence([tr1, tr2])
        assert len(collected["console_errors"]) == 2

    def test_memory_leak_suspect_dict_value(self, db, defect_project, defect_task):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-006")
        tr = _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={"memory_leak_suspect": {"trend": "increasing", "delta_mb": 50}},
        )
        collected = _collect_implicit_evidence([tr])
        assert len(collected["memory_leak_suspect"]) == 1


# ---------------------------------------------------------------------------
# calculate_defect_metrics 测试
# ---------------------------------------------------------------------------


class TestCalculateDefectMetrics:
    """缺陷发现率指标计算测试。"""

    def test_no_bugs_no_results(self, db, defect_project, defect_task):
        """无 Bug 无执行结果：所有指标为零。"""
        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["p0_count"] == 0
        assert metrics["p1_count"] == 0
        assert metrics["p2_count"] == 0
        assert metrics["p3_count"] == 0
        assert metrics["total_defects"] == 0
        assert metrics["defect_density"] == 0.0
        assert metrics["high_severity_ratio"] == 0.0
        assert metrics["defect_coverage_rate"] == 0.0
        assert metrics["implicit_defect_rate"] == 0.0
        assert metrics["coverage_insufficient_warning"] is False

    def test_all_passed_no_bugs_triggers_warning(self, db, defect_project, defect_task, testUser):
        """100% 通过率 + 0 缺陷 → coverage_insufficient_warning=True。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-WARN-001")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
        )
        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["coverage_insufficient_warning"] is True
        assert metrics["total_defects"] == 0

    def test_all_passed_with_bugs_no_warning(self, db, defect_project, defect_task, testUser):
        """100% 通过率但有缺陷 → coverage_insufficient_warning=False。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-WARN-002")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
        )
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)
        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["coverage_insufficient_warning"] is False
        assert metrics["total_defects"] == 1

    def test_mixed_results_no_warning(self, db, defect_project, defect_task, testUser):
        """非 100% 通过率 → coverage_insufficient_warning=False。"""
        tc1 = _create_test_case(db, defect_project.id, "认证", "TC-WARN-003")
        tc2 = _create_test_case(db, defect_project.id, "认证", "TC-WARN-004")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc1.id,
            case_no=tc1.case_no,
            exec_status=ExecStatus.PASSED,
        )
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc2.id,
            case_no=tc2.case_no,
            exec_status=ExecStatus.FAILED,
        )
        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["coverage_insufficient_warning"] is False

    def test_severity_distribution(self, db, defect_project, defect_task, testUser):
        """按 P0/P1/P2/P3 分级统计正确。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-SEV-001")
        _create_bug(db, defect_project.id, testUser.id, severity=1, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=3, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=4, test_case_id=tc.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["p0_count"] == 1
        assert metrics["p1_count"] == 1
        assert metrics["p2_count"] == 1
        assert metrics["p3_count"] == 1
        assert metrics["total_defects"] == 4

    def test_defect_density(self, db, defect_project, defect_task, testUser):
        """缺陷密度 = 缺陷数 / 执行用例数。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-DENS-001")
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=3, test_case_id=tc.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["defect_density"] == 2.0

    def test_high_severity_ratio(self, db, defect_project, defect_task, testUser):
        """高严重度占比 = (P0+P1) / 总缺陷数。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-HIGH-001")
        _create_bug(db, defect_project.id, testUser.id, severity=1, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=3, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=4, test_case_id=tc.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        # (1+1)/4 = 0.5
        assert metrics["high_severity_ratio"] == 0.5

    def test_defect_coverage_rate(self, db, defect_project, defect_task, testUser):
        """缺陷发现覆盖率 = 发现缺陷的模块数 / 总模块数。"""
        tc_auth = _create_test_case(db, defect_project.id, "认证", "TC-COV-001")
        tc_proj = _create_test_case(db, defect_project.id, "项目管理", "TC-COV-002")
        tc_report = _create_test_case(db, defect_project.id, "报告", "TC-COV-003")

        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc_auth.id)
        _create_bug(db, defect_project.id, testUser.id, severity=3, test_case_id=tc_proj.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc_auth.id,
            case_no=tc_auth.case_no,
            exec_status=ExecStatus.FAILED,
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        # 3 个模块，2 个有缺陷 → 2/3 ≈ 0.6667
        assert metrics["defect_coverage_rate"] == round(2 / 3, 4)

    def test_implicit_defect_rate(self, db, defect_project, defect_task, testUser):
        """隐性缺陷发现率 = 隐性缺陷数 / 总缺陷数。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-010")
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={
                "console_errors": ["Uncaught ReferenceError"],
                "network_failures": [],
            },
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        # 1 个隐性缺陷 / 1 个总缺陷 = 1.0
        assert metrics["implicit_defect_rate"] == 1.0

    def test_implicit_defect_rate_zero_when_no_bugs(self, db, defect_project, defect_task):
        """无缺陷时隐性缺陷率为 0。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPL-011")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={"console_errors": ["Error"]},
        )
        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["implicit_defect_rate"] == 0.0

    def test_only_self_test_bugs_counted(self, db, defect_project, defect_task, testUser):
        """仅 source="self_test" 的 Bug 被统计。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-SRC-001")
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)

        # 手动创建的 Bug（source="manual"）
        import uuid
        manual_bug = Bug(
            bug_no=f"BUG-{defect_project.id}-MANUAL-{uuid.uuid4().hex[:6]}",
            project_id=defect_project.id,
            title="[P1] 手动发现的缺陷",
            description="手动缺陷",
            severity=2,
            priority=1,
            status="open",
            source="manual",
            reporter_id=testUser.id,
            test_case_id=tc.id,
        )
        db.add(manual_bug)
        db.flush()

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        metrics = calculate_defect_metrics(db, defect_project.id, defect_task.id)
        assert metrics["total_defects"] == 1


# ---------------------------------------------------------------------------
# ReportService 缺陷维度数据构建测试
# ---------------------------------------------------------------------------


class TestBuildDefectOverview:
    """ReportService._build_defect_overview 测试。"""

    def test_overview_structure(self, db, defect_project, defect_task, testUser):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-OV-001")
        _create_bug(db, defect_project.id, testUser.id, severity=1, test_case_id=tc.id)
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        overview = ReportService._build_defect_overview(db, defect_project.id, defect_task.id)
        assert "p0_count" in overview
        assert "p1_count" in overview
        assert "p2_count" in overview
        assert "p3_count" in overview
        assert "total_defects" in overview
        assert "defect_density" in overview
        assert "high_severity_ratio" in overview
        assert "defect_coverage_rate" in overview
        assert "implicit_defect_rate" in overview
        assert "coverage_insufficient_warning" in overview
        assert overview["p0_count"] == 1
        assert overview["total_defects"] == 1


class TestBuildDefectList:
    """ReportService._build_defect_list 测试。"""

    def test_empty_list(self, db, defect_project):
        defect_list = ReportService._build_defect_list(db, defect_project.id)
        assert defect_list == []

    def test_list_with_bugs(self, db, defect_project, testUser):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-DL-001")
        _create_bug(
            db,
            defect_project.id,
            testUser.id,
            severity=2,
            ux_category="security",
            test_case_id=tc.id,
        )

        defect_list = ReportService._build_defect_list(db, defect_project.id)
        assert len(defect_list) == 1
        entry = defect_list[0]
        assert "bug_no" in entry
        assert "title" in entry
        assert "severity" in entry
        assert "ux_category" in entry
        assert "module" in entry
        assert "description" in entry
        assert "reproduction_steps" in entry
        assert "defect_evidence" in entry
        assert entry["severity"] == 2
        assert entry["ux_category"] == "security"
        assert entry["module"] == "认证"


class TestBuildDefectDistribution:
    """ReportService._build_defect_distribution 测试。"""

    def test_empty_distribution(self, db, defect_project):
        dist = ReportService._build_defect_distribution(db, defect_project.id)
        assert dist["by_module"] == {}
        assert dist["by_type"] == {}
        assert dist["by_severity"] == {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

    def test_distribution_with_data(self, db, defect_project, testUser):
        tc_auth = _create_test_case(db, defect_project.id, "认证", "TC-DIST-001")
        tc_proj = _create_test_case(db, defect_project.id, "项目管理", "TC-DIST-002")

        _create_bug(
            db, defect_project.id, testUser.id,
            severity=1, ux_category="security", test_case_id=tc_auth.id,
        )
        _create_bug(
            db, defect_project.id, testUser.id,
            severity=3, ux_category=None, test_case_id=tc_proj.id,
        )

        dist = ReportService._build_defect_distribution(db, defect_project.id)
        assert dist["by_module"]["认证"] == 1
        assert dist["by_module"]["项目管理"] == 1
        assert dist["by_type"]["security"] == 1
        assert dist["by_type"]["functional"] == 1
        assert dist["by_severity"]["p0"] == 1
        assert dist["by_severity"]["p2"] == 1


class TestBuildImplicitDefects:
    """ReportService._build_implicit_defects 测试。"""

    def test_no_implicit_defects(self, db, defect_project, defect_task):
        implicit = ReportService._build_implicit_defects(db, defect_project.id, defect_task.id)
        assert all(len(v) == 0 for v in implicit.values())

    def test_with_implicit_evidence(self, db, defect_project, defect_task):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-IMPD-001")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={"uncaught_exceptions": ["TypeError at line 10"]},
        )

        implicit = ReportService._build_implicit_defects(db, defect_project.id, defect_task.id)
        assert len(implicit["uncaught_exceptions"]) == 1


class TestBuildSecurityFindings:
    """ReportService._build_security_findings 测试。"""

    def test_no_security_bugs(self, db, defect_project):
        findings = ReportService._build_security_findings(db, defect_project.id)
        assert findings == []

    def test_with_security_bugs(self, db, defect_project, testUser):
        tc = _create_test_case(db, defect_project.id, "认证", "TC-SEC-001")
        _create_bug(
            db, defect_project.id, testUser.id,
            severity=1, ux_category="security", test_case_id=tc.id,
        )

        findings = ReportService._build_security_findings(db, defect_project.id)
        assert len(findings) == 1
        assert findings[0]["type"] == "sensitive_data_exposure"
        assert "description" in findings[0]
        assert "evidence" in findings[0]


class TestBuildCoverageAssessment:
    """ReportService._build_coverage_assessment 测试。"""

    def test_no_modules_no_bugs(self, db, defect_project):
        assessment = ReportService._build_coverage_assessment(db, defect_project.id)
        assert assessment["total_modules"] == 0
        assert assessment["covered_modules"] == 0
        assert assessment["warning"] == ""

    def test_partial_coverage_warning(self, db, defect_project, testUser):
        tc_auth = _create_test_case(db, defect_project.id, "认证", "TC-CA-001")
        tc_proj = _create_test_case(db, defect_project.id, "项目管理", "TC-CA-002")
        tc_report = _create_test_case(db, defect_project.id, "报告", "TC-CA-003")

        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc_auth.id)

        assessment = ReportService._build_coverage_assessment(db, defect_project.id)
        assert assessment["total_modules"] == 3
        assert assessment["covered_modules"] == 1
        assert "认证" in assessment["modules_with_defects"]
        assert "覆盖不足" in assessment["warning"]

    def test_full_coverage_no_warning(self, db, defect_project, testUser):
        tc_auth = _create_test_case(db, defect_project.id, "认证", "TC-CA-004")

        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc_auth.id)

        assessment = ReportService._build_coverage_assessment(db, defect_project.id)
        assert assessment["total_modules"] == 1
        assert assessment["covered_modules"] == 1
        assert assessment["warning"] == ""


# ---------------------------------------------------------------------------
# 报告生成含缺陷维度数据测试
# ---------------------------------------------------------------------------


class TestReportGenerationWithDefects:
    """报告生成集成测试：验证缺陷维度数据写入 report.content。"""

    def test_report_contains_defect_dimensions(
        self, db, defect_project, defect_task, testUser
    ):
        """生成报告时包含缺陷维度数据。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-001")
        _create_bug(
            db, defect_project.id, testUser.id,
            severity=2, ux_category="security", test_case_id=tc.id,
        )
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="缺陷维度测试报告",
        )

        content = report.content
        assert "defect_overview" in content
        assert "defect_list" in content
        assert "defect_distribution" in content
        assert "implicit_defects" in content
        assert "security_findings" in content
        assert "coverage_assessment" in content

    def test_report_defect_overview_values(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 defect_overview 指标值正确。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-002")
        _create_bug(db, defect_project.id, testUser.id, severity=1, test_case_id=tc.id)
        _create_bug(db, defect_project.id, testUser.id, severity=3, test_case_id=tc.id)
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="缺陷指标值测试报告",
        )

        overview = report.content["defect_overview"]
        assert overview["p0_count"] == 1
        assert overview["p2_count"] == 1
        assert overview["total_defects"] == 2
        assert overview["defect_density"] == 2.0
        assert overview["high_severity_ratio"] == 0.5

    def test_report_coverage_insufficient_warning(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 coverage_insufficient_warning 在 100% 通过 + 0 缺陷时为 True。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-003")
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="覆盖不足警告测试报告",
        )

        overview = report.content["defect_overview"]
        assert overview["coverage_insufficient_warning"] is True

    def test_report_without_task_id_no_defect_data(
        self, db, defect_project, testUser
    ):
        """不指定 task_id 时报告不含缺陷维度数据。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-004")
        _create_test_result(
            db,
            task_id=None,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=None,
            name="无任务ID报告",
        )

        content = report.content
        assert "defect_overview" not in content
        assert "defect_list" not in content

    def test_report_defect_distribution_structure(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 defect_distribution 结构正确。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-005")
        _create_bug(
            db, defect_project.id, testUser.id,
            severity=2, ux_category="loading_experience", test_case_id=tc.id,
        )
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="缺陷分布结构测试报告",
        )

        dist = report.content["defect_distribution"]
        assert "by_module" in dist
        assert "by_type" in dist
        assert "by_severity" in dist
        assert dist["by_module"]["认证"] == 1
        assert dist["by_type"]["loading_experience"] == 1
        assert dist["by_severity"]["p1"] == 1

    def test_report_implicit_defects_in_content(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 implicit_defects 包含隐性缺陷证据。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-006")
        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc.id)
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.PASSED,
            defect_evidence={
                "console_errors": ["TypeError: cannot read property of undefined"],
                "network_failures": [{"status": 503, "url": "/api/health"}],
            },
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="隐性缺陷报告",
        )

        implicit = report.content["implicit_defects"]
        assert len(implicit["console_errors"]) == 1
        assert len(implicit["network_failures"]) == 1

    def test_report_security_findings_in_content(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 security_findings 包含安全发现。"""
        tc = _create_test_case(db, defect_project.id, "认证", "TC-RPT-007")
        _create_bug(
            db, defect_project.id, testUser.id,
            severity=1, ux_category="security", test_case_id=tc.id,
        )
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc.id,
            case_no=tc.case_no,
            exec_status=ExecStatus.FAILED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="安全发现报告",
        )

        findings = report.content["security_findings"]
        assert len(findings) >= 1
        assert findings[0]["type"] in (
            "sensitive_data_exposure",
            "xss_vulnerability",
            "permission_bypass",
        )

    def test_report_coverage_assessment_in_content(
        self, db, defect_project, defect_task, testUser
    ):
        """报告 coverage_assessment 包含覆盖评估。"""
        tc_auth = _create_test_case(db, defect_project.id, "认证", "TC-RPT-008")
        tc_report = _create_test_case(db, defect_project.id, "报告", "TC-RPT-009")

        _create_bug(db, defect_project.id, testUser.id, severity=2, test_case_id=tc_auth.id)

        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc_auth.id,
            case_no=tc_auth.case_no,
            exec_status=ExecStatus.FAILED,
        )
        _create_test_result(
            db,
            task_id=defect_task.id,
            project_id=defect_project.id,
            case_id=tc_report.id,
            case_no=tc_report.case_no,
            exec_status=ExecStatus.PASSED,
        )

        report = ReportService.generate_report(
            db,
            project_id=defect_project.id,
            test_task_id=defect_task.id,
            name="覆盖评估报告",
        )

        assessment = report.content["coverage_assessment"]
        assert "modules_with_defects" in assessment
        assert "modules_without_defects" in assessment
        assert "total_modules" in assessment
        assert "covered_modules" in assessment
        assert "warning" in assessment
        assert "认证" in assessment["modules_with_defects"]
        assert "报告" in assessment["modules_without_defects"]
