"""报告服务模块 - 测试报告生成、统计与查询。

本模块负责测试报告的全生命周期管理，包括报告生成、数据统计、
内容构建和详情查询。报告数据来源于TestResult执行结果记录，
经过统计聚合后生成结构化报告内容。

核心类:
    - ReportService: 报告服务，提供报告生成与查询的静态方法

依赖关系:
    - app.models.report: TestReport ORM模型
    - app.models.test_result: TestResult ORM模型
    - app.schemas.test_report: 报告相关Schema
    - app.crud.test_report: 报告CRUD操作

设计说明:
    采用静态方法设计，服务不持有状态，数据库会话由调用方传入。
    报告生成流程为：查询结果 -> 统计计算 -> 内容构建 -> 持久化。
    统计指标包括总数、通过数、失败数、阻塞数和通过率。
"""
import json
from sqlalchemy.orm import Session
from app.models.report import TestReport
from app.models.test_result import TestResult
from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.schemas.test_report import TestReportCreate, TestCaseResult, TestReportDetail
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger


class ReportService:
    """报告生成服务 - 管理测试报告的生成、统计与查询。

    职责:
        - 根据项目/任务维度生成测试报告
        - 统计测试结果数据（通过/失败/阻塞/通过率）
        - 构建报告内容（用例明细+环境信息）
        - 生成报告摘要文本
        - 查询报告详情

    使用场景:
        - 任务执行完成后自动生成报告
        - 用户在报告页面手动生成报告
        - 报告详情页查询完整报告内容

    设计意图:
        将报告生成逻辑封装为独立服务，与CRUD层职责划分:
        - ReportService: 业务逻辑（统计、内容构建、摘要生成）
        - test_report CRUD: 数据持久化（创建记录、查询记录）
    """

    @staticmethod
    def _generate_fix_suggestion(analysis_text: str | None) -> str | None:
        if not analysis_text:
            return None
        if "功能" in analysis_text or "业务" in analysis_text:
            return "建议优先检查业务逻辑、接口返回与状态流转。"
        if "显示" in analysis_text or "渲染" in analysis_text or "数据" in analysis_text:
            return "建议检查前端渲染、数据绑定与接口字段映射。"
        if "预期" in analysis_text or "不符" in analysis_text:
            return "建议核对预期行为、产品规则与实际实现差异。"
        return "建议结合执行日志、截图和复现步骤定位根因。"

    @staticmethod
    def _build_self_test_bug_list(db: Session, project_id: int) -> List[Dict[str, Any]]:
        from app.models.bug import Bug

        bugs = (
            db.query(Bug)
            .filter(Bug.project_id == project_id, Bug.source == "self_test")
            .order_by(Bug.create_time.desc())
            .all()
        )
        return [
            {
                "bug_no": bug.bug_no,
                "title": bug.title,
                "severity": bug.severity,
                "priority": bug.priority,
                "status": bug.status,
                "screenshot_url": bug.test_result.screenshot_url if bug.test_result else None,
                "ai_analysis": bug.test_result.ai_analysis if bug.test_result else None,
                "fix_suggestion": ReportService._generate_fix_suggestion(
                    bug.description or (bug.test_result.ai_analysis if bug.test_result else None)
                ),
            }
            for bug in bugs
        ]

    @staticmethod
    def _build_defect_overview(
        db: Session,
        project_id: int,
        task_id: int,
    ) -> Dict[str, Any]:
        """构建缺陷概览数据，调用 calculate_defect_metrics 获取指标。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。
            task_id: 测试任务 ID。

        Returns:
            defect_overview 结构字典。
        """
        from app.services.self_test_service import calculate_defect_metrics

        metrics = calculate_defect_metrics(db, project_id, task_id)
        return {
            "p0_count": metrics["p0_count"],
            "p1_count": metrics["p1_count"],
            "p2_count": metrics["p2_count"],
            "p3_count": metrics["p3_count"],
            "total_defects": metrics["total_defects"],
            "defect_density": metrics["defect_density"],
            "high_severity_ratio": metrics["high_severity_ratio"],
            "defect_coverage_rate": metrics["defect_coverage_rate"],
            "implicit_defect_rate": metrics["implicit_defect_rate"],
            "coverage_insufficient_warning": metrics["coverage_insufficient_warning"],
        }

    @staticmethod
    def _build_defect_list(
        db: Session,
        project_id: int,
    ) -> List[Dict[str, Any]]:
        """构建缺陷明细列表，包含 Bug 详情和关联证据。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。

        Returns:
            缺陷明细列表。
        """
        from app.models.bug import Bug

        bugs = (
            db.query(Bug)
            .filter(Bug.project_id == project_id, Bug.source == "self_test")
            .order_by(Bug.severity.asc(), Bug.create_time.desc())
            .all()
        )
        defect_list: List[Dict[str, Any]] = []
        for bug in bugs:
            entry: Dict[str, Any] = {
                "bug_no": bug.bug_no,
                "title": bug.title,
                "severity": bug.severity,
                "ux_category": bug.ux_category,
                "module": bug.test_case.module if bug.test_case else None,
                "description": bug.description,
                "reproduction_steps": bug.reproduction_steps,
            }
            # 关联 test_result 的 defect_evidence
            if bug.test_result and bug.test_result.defect_evidence:
                entry["defect_evidence"] = bug.test_result.defect_evidence
            else:
                entry["defect_evidence"] = None
            defect_list.append(entry)
        return defect_list

    @staticmethod
    def _build_defect_distribution(
        db: Session,
        project_id: int,
    ) -> Dict[str, Any]:
        """构建缺陷分布统计（按模块/类型/严重度）。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。

        Returns:
            缺陷分布统计字典。
        """
        from app.models.bug import Bug

        bugs = (
            db.query(Bug)
            .filter(Bug.project_id == project_id, Bug.source == "self_test")
            .all()
        )

        by_module: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}

        for bug in bugs:
            # 按模块统计
            module = bug.test_case.module if bug.test_case else "未分类"
            by_module[module] = by_module.get(module, 0) + 1

            # 按类型统计
            ux_cat = bug.ux_category or "functional"
            by_type[ux_cat] = by_type.get(ux_cat, 0) + 1

            # 按严重度统计（severity: 1=P0, 2=P1, 3=P2, 4=P3）
            severity_key = f"p{bug.severity - 1}"
            if severity_key in by_severity:
                by_severity[severity_key] += 1

        return {
            "by_module": by_module,
            "by_type": by_type,
            "by_severity": by_severity,
        }

    @staticmethod
    def _build_implicit_defects(
        db: Session,
        project_id: int,
        task_id: int,
    ) -> Dict[str, Any]:
        """构建隐性缺陷证据聚合数据。

        从测试结果中收集 exec_status=passed 但 defect_evidence 含
        隐性信号的证据，按类型聚合。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。
            task_id: 测试任务 ID。

        Returns:
            隐性缺陷证据字典。
        """
        from app.services.self_test_service import _collect_implicit_evidence

        test_results = (
            db.query(TestResult)
            .filter(
                TestResult.project_id == project_id,
                TestResult.task_id == task_id,
            )
            .all()
        )
        return _collect_implicit_evidence(test_results)

    @staticmethod
    def _build_security_findings(
        db: Session,
        project_id: int,
    ) -> List[Dict[str, Any]]:
        """构建安全发现列表，从 ux_category=security 的 Bug 中提取。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。

        Returns:
            安全发现列表。
        """
        from app.models.bug import Bug

        security_bugs = (
            db.query(Bug)
            .filter(
                Bug.project_id == project_id,
                Bug.source == "self_test",
                Bug.ux_category == "security",
            )
            .all()
        )
        findings: List[Dict[str, Any]] = []
        for bug in security_bugs:
            # 从 Bug 描述中推断安全类型
            desc = bug.description or ""
            sec_type = "sensitive_data_exposure"
            if "xss" in desc.lower():
                sec_type = "xss_vulnerability"
            elif "权限" in desc or "permission" in desc.lower():
                sec_type = "permission_bypass"

            evidence_str = ""
            if bug.test_result and bug.test_result.defect_evidence:
                try:
                    evidence_str = json.dumps(
                        bug.test_result.defect_evidence,
                        ensure_ascii=False,
                        default=str,
                    )
                except (TypeError, ValueError):
                    evidence_str = str(bug.test_result.defect_evidence)

            findings.append({
                "type": sec_type,
                "description": bug.title,
                "evidence": evidence_str,
            })
        return findings

    @staticmethod
    def _build_coverage_assessment(
        db: Session,
        project_id: int,
    ) -> Dict[str, Any]:
        """构建覆盖评估数据，对比有缺陷模块和无缺陷模块。

        Args:
            db: 数据库会话。
            project_id: 项目 ID。

        Returns:
            覆盖评估字典。
        """
        from app.models.bug import Bug

        # 有缺陷的模块集合
        bugs = (
            db.query(Bug)
            .filter(Bug.project_id == project_id, Bug.source == "self_test")
            .all()
        )
        modules_with_defects: set[str] = set()
        for bug in bugs:
            if bug.test_case and bug.test_case.module:
                modules_with_defects.add(bug.test_case.module)

        # 项目所有模块
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

        modules_without_defects = sorted(all_modules - modules_with_defects)
        total_modules = len(all_modules)
        covered = len(modules_with_defects & all_modules)

        warning = ""
        if total_modules > 0 and covered < total_modules:
            warning = f"覆盖不足：仅 {covered}/{total_modules} 个模块发现缺陷"

        return {
            "modules_with_defects": sorted(modules_with_defects),
            "modules_without_defects": modules_without_defects,
            "total_modules": total_modules,
            "covered_modules": covered,
            "warning": warning,
        }

    @staticmethod
    def generate_report(db: Session, project_id: int, test_task_id: int = None, name: str = None, description: str = None, user_id: int = None) -> TestReport:
        """生成测试报告，包含统计数据、用例明细、缺陷维度和执行时间。

        生成流程:
            1. 按项目ID查询测试结果（可选按任务ID过滤）
            2. 计算统计数据（通过/失败/阻塞/通过率）
            3. 构建报告内容（用例明细+环境信息+缺陷维度数据）
            4. 创建报告记录并填充统计数据
            5. 计算执行时间范围

        Args:
            db: 数据库会话。
            project_id: 项目ID，必填，确定报告范围。
            test_task_id: 任务ID，可选，指定则仅统计该任务的结果。
            name: 报告名称，默认自动生成（含时间戳）。
            description: 报告描述，默认"自动生成的测试报告"。
            user_id: 创建者用户ID，默认1（系统用户）。

        Returns:
            生成完成的TestReport ORM实例。
        """
        # 构建查询条件，支持按任务ID过滤
        query = db.query(TestResult).filter(
            TestResult.project_id == project_id,
            TestResult.test_case.has(TestCase.is_deleted.is_(False))
        )
        if test_task_id:
            query = query.filter(TestResult.task_id == test_task_id)

        # 获取测试结果集
        test_results = query.all()

        # 统计数据计算
        statistics = ReportService._calculate_statistics(test_results)

        report_content = ReportService._generate_report_content(test_results, statistics)

        # 聚合缺陷维度数据（仅在关联任务时填充）
        if test_task_id:
            try:
                report_content["defect_overview"] = ReportService._build_defect_overview(
                    db, project_id, test_task_id
                )
                report_content["defect_list"] = ReportService._build_defect_list(
                    db, project_id
                )
                report_content["defect_distribution"] = ReportService._build_defect_distribution(
                    db, project_id
                )
                report_content["implicit_defects"] = ReportService._build_implicit_defects(
                    db, project_id, test_task_id
                )
                report_content["security_findings"] = ReportService._build_security_findings(
                    db, project_id
                )
                report_content["coverage_assessment"] = ReportService._build_coverage_assessment(
                    db, project_id
                )
            except Exception as exc:
                logger.warning(f"报告缺陷维度数据聚合失败，不影响报告生成: {exc}")

        report_data = TestReportCreate(
            name=name or f"测试报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=description or "自动生成的测试报告",
            project_id=project_id,
            test_task_id=test_task_id
        )

        from app.crud.test_report import create_test_report
        report = create_test_report(db, report_data, user_id=user_id or 1)

        report.total_cases = statistics['total']
        report.passed_cases = statistics['passed']
        report.failed_cases = statistics['failed']
        report.blocked_cases = statistics['blocked']
        report.status = "completed"
        report.content = report_content
        report.summary = ReportService._generate_summary(statistics)

        # 计算执行时间范围（最早开始到最晚结束）
        if test_results:
            start_time = min(result.exec_time for result in test_results)
            end_time = max(result.exec_time for result in test_results)
            report.start_time = start_time
            report.end_time = end_time
            report.execution_time = int((end_time - start_time).total_seconds())

        db.commit()
        db.refresh(report)
        return report

    @staticmethod
    def _calculate_statistics(test_results: List[TestResult]) -> Dict[str, int]:
        """计算测试结果统计数据。

        统计指标:
            - total: 总用例数
            - passed: 通过数（exec_status=1）
            - failed: 失败数（exec_status=2）
            - blocked: 阻塞数（exec_status=3）
            - pass_rate: 通过率百分比，保留两位小数

        Args:
            test_results: 测试结果列表。

        Returns:
            包含total/passed/failed/blocked/pass_rate的统计字典。
        """
        total = len(test_results)
        passed = sum(1 for result in test_results if result.exec_status == ExecStatus.PASSED)
        failed = sum(1 for result in test_results if result.exec_status == ExecStatus.FAILED)
        blocked = sum(1 for result in test_results if result.exec_status == ExecStatus.BLOCKED)

        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'blocked': blocked,
            'pass_rate': round(passed / total * 100, 2) if total > 0 else 0
        }

    @staticmethod
    def _generate_report_content(test_results: List[TestResult], statistics: Dict[str, int]) -> Dict[str, Any]:
        """生成报告内容，包含用例明细、统计和环境信息。

        内容结构:
            {
                "test_cases": [用例结果列表],
                "statistics": 统计数据,
                "environment": 生成环境信息
            }

        Args:
            test_results: 测试结果列表。
            statistics: 统计数据字典。

        Returns:
            报告内容字典，用于存储到report.content字段。
        """
        test_cases = []
        for result in test_results:
            # exec_status数值到语义字符串的映射
            status_map = {0: "pending", 1: "passed", 2: "failed", 3: "blocked"}
            test_case = TestCaseResult(
                case_id=result.case_id,
                case_name=result.test_case.title if result.test_case else f"用例_{result.case_id}",
                status=status_map.get(result.exec_status, "unknown"),
                execution_time=None,  # 可从执行日志中提取
                error_message=result.error_msg,
                steps=None  # 可从执行日志中提取
            )
            test_cases.append(test_case.model_dump())

        return {
            'test_cases': test_cases,
            'statistics': statistics,
            'environment': {
                'generate_time': datetime.now().isoformat(),
                'platform': 'AI TestMaster',
                'version': '1.0.0'
            }
        }

    @staticmethod
    def _generate_summary(statistics: Dict[str, int]) -> str:
        """生成报告摘要文本，概括测试执行结果。

        Args:
            statistics: 统计数据字典。

        Returns:
            摘要文本，格式如"共执行 10 个测试用例，通过 8 个，失败 1 个，阻塞 1 个，通过率 80.0%。"
        """
        return f"共执行 {statistics['total']} 个测试用例，通过 {statistics['passed']} 个，失败 {statistics['failed']} 个，阻塞 {statistics['blocked']} 个，通过率 {statistics['pass_rate']}%。"

    @staticmethod
    def get_report_detail(db: Session, report_id: int, project_id: int) -> TestReportDetail:
        """获取报告详细信息，解析content字段为结构化对象。

        Args:
            db: 数据库会话。
            report_id: 报告ID。
            project_id: 项目ID，用于权限校验。

        Returns:
            TestReportDetail实例，包含完整的报告结构化数据。

        Raises:
            ValueError: 报告不存在或报告内容为空。
        """
        from app.crud.test_report import get_test_report_by_id
        report = get_test_report_by_id(db, report_id, project_id)
        if not report:
            raise ValueError("Report not found")

        if not report.content:
            raise ValueError("Report content not found")

        return TestReportDetail(**report.content)
