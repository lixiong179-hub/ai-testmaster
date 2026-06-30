"""Defect discovery rate metrics calculation."""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


# 隐性缺陷判定键：defect_evidence 中这些键任一非空即视为隐性缺陷
_IMPLICIT_DEFECT_EVIDENCE_KEYS = frozenset({
    "console_errors", "network_failures",
    "memory_leak_suspect", "uncaught_exceptions",
})


def _is_implicit_defect(defect_evidence: Optional[Dict[str, Any]]) -> bool:
    """判断 defect_evidence 是否包含隐性缺陷信号。

    隐性缺陷定义：用例通过了（exec_status=passed），但浏览器环境监控
    捕获到 console_errors / network_failures / memory_leak_suspect /
    uncaught_exceptions 中至少一项非空。

    Args:
        defect_evidence: 浏览器缺陷证据字典。

    Returns:
        True 表示存在隐性缺陷信号。
    """
    if not defect_evidence:
        return False
    return any(
        bool(defect_evidence.get(key))
        for key in _IMPLICIT_DEFECT_EVIDENCE_KEYS
    )


def _collect_implicit_evidence(
    test_results: list["TestResult"],
) -> Dict[str, Any]:
    """从测试结果中收集所有隐性缺陷证据，按类型聚合。

    仅收集 exec_status=passed 但 defect_evidence 含隐性信号的记录。

    Args:
        test_results: 测试结果列表。

    Returns:
        按类型聚合的隐性缺陷证据字典。
    """
    from app.models.enums import ExecStatus

    collected: Dict[str, list] = {
        "console_errors": [],
        "network_failures": [],
        "memory_leak_suspect": [],
        "uncaught_exceptions": [],
    }
    for result in test_results:
        if result.exec_status != ExecStatus.PASSED:
            continue
        evidence = result.defect_evidence
        if not evidence or not _is_implicit_defect(evidence):
            continue
        for key in _IMPLICIT_DEFECT_EVIDENCE_KEYS:
            value = evidence.get(key)
            if value:
                existing = collected[key]
                if isinstance(value, list):
                    existing.extend(value)
                else:
                    existing.append(value)
    return collected


def calculate_defect_metrics(
    db: Session,
    project_id: int,
    task_id: int,
) -> Dict[str, Any]:
    """计算缺陷发现率指标。

    指标包括：
        - 缺陷发现数（按 P0/P1/P2/P3 分级统计）
        - 缺陷密度：缺陷数 / 执行用例数
        - 高严重度缺陷占比：(P0+P1) / 总缺陷数
        - 缺陷发现覆盖率：发现缺陷的功能模块数 / 总功能模块数
        - 隐性缺陷发现率：通过 defect_evidence 发现的缺陷 / 总缺陷数

    数据来源：
        - Bug 记录（bugs 表，source="self_test"，按 severity 分级）
        - TestResult（test_results 表，含 defect_evidence JSON）
        - 测试用例模块信息（test_cases 表的 module 字段）

    Args:
        db: 数据库会话。
        project_id: 项目 ID。
        task_id: 测试任务 ID。

    Returns:
        包含所有缺陷指标的字典，结构如下：
        {
            "p0_count": int, "p1_count": int, "p2_count": int, "p3_count": int,
            "total_defects": int,
            "defect_density": float,
            "high_severity_ratio": float,
            "defect_coverage_rate": float,
            "implicit_defect_rate": float,
            "coverage_insufficient_warning": bool,
        }
    """
    from app.models.bug import Bug
    from app.models.test_result import TestResult
    from app.models.test_case import TestCase
    from app.models.enums import ExecStatus

    # --- 1. 查询 Bug 记录（source="self_test"，按 project 过滤） ---
    bugs = (
        db.query(Bug)
        .filter(
            Bug.project_id == project_id,
            Bug.source == "self_test",
        )
        .all()
    )

    # 按 severity 分级统计（severity: 1=P0, 2=P1, 3=P2, 4=P3）
    severity_map: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    for bug in bugs:
        if bug.severity in severity_map:
            severity_map[bug.severity] += 1

    p0_count = severity_map[1]
    p1_count = severity_map[2]
    p2_count = severity_map[3]
    p3_count = severity_map[4]
    total_defects = p0_count + p1_count + p2_count + p3_count

    # --- 2. 查询执行用例数 ---
    executed_count = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
        )
        .count()
    )

    # --- 3. 缺陷密度 ---
    defect_density = round(total_defects / executed_count, 4) if executed_count > 0 else 0.0

    # --- 4. 高严重度缺陷占比 ---
    high_severity_count = p0_count + p1_count
    high_severity_ratio = (
        round(high_severity_count / total_defects, 4) if total_defects > 0 else 0.0
    )

    # --- 5. 缺陷发现覆盖率 ---
    # 发现缺陷的功能模块集合（通过 Bug 关联的 test_case.module 获取）
    modules_with_defects: set[str] = set()
    for bug in bugs:
        if bug.test_case and bug.test_case.module:
            modules_with_defects.add(bug.test_case.module)

    # 项目总功能模块集合（从 test_cases 表获取）
    all_modules_result = (
        db.query(TestCase.module)
        .filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted.is_(False),
        )
        .distinct()
        .all()
    )
    all_modules: set[str] = {row[0] for row in all_modules_result if row[0]}

    total_modules = len(all_modules)
    covered_modules = len(modules_with_defects & all_modules)
    defect_coverage_rate = (
        round(covered_modules / total_modules, 4) if total_modules > 0 else 0.0
    )

    # --- 6. 隐性缺陷发现率 ---
    # 查询任务下所有测试结果
    test_results = (
        db.query(TestResult)
        .filter(
            TestResult.project_id == project_id,
            TestResult.task_id == task_id,
        )
        .all()
    )

    # 统计隐性缺陷数：exec_status=passed 但 defect_evidence 含隐性信号
    implicit_defect_count = 0
    for result in test_results:
        if result.exec_status == ExecStatus.PASSED and _is_implicit_defect(result.defect_evidence):
            implicit_defect_count += 1

    implicit_defect_rate = (
        round(implicit_defect_count / total_defects, 4) if total_defects > 0 else 0.0
    )

    # --- 7. coverage_insufficient_warning ---
    # 100% 用例通过率 + 0 缺陷发现 → true
    passed_count = sum(
        1 for r in test_results if r.exec_status == ExecStatus.PASSED
    )
    all_passed = executed_count > 0 and passed_count == executed_count
    coverage_insufficient_warning = all_passed and total_defects == 0

    return {
        "p0_count": p0_count,
        "p1_count": p1_count,
        "p2_count": p2_count,
        "p3_count": p3_count,
        "total_defects": total_defects,
        "defect_density": defect_density,
        "high_severity_ratio": high_severity_ratio,
        "defect_coverage_rate": defect_coverage_rate,
        "implicit_defect_rate": implicit_defect_rate,
        "coverage_insufficient_warning": coverage_insufficient_warning,
    }
