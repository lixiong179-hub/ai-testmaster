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
from sqlalchemy.orm import Session
from app.models.report import TestReport
from app.models.test_result import TestResult
from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.schemas.test_report import TestReportCreate, TestCaseResult, TestReportDetail
from datetime import datetime
from typing import Dict, Any, List


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
    def generate_report(db: Session, project_id: int, test_task_id: int = None, name: str = None, description: str = None, user_id: int = None) -> TestReport:
        """生成测试报告，包含统计数据、用例明细和执行时间。

        生成流程:
            1. 按项目ID查询测试结果（可选按任务ID过滤）
            2. 计算统计数据（通过/失败/阻塞/通过率）
            3. 构建报告内容（用例明细+环境信息）
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
