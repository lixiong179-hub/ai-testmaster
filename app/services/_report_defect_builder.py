"""报告缺陷维度数据构建器 - 从 report_service.py 拆分。

包含缺陷概览、缺陷明细、缺陷分布、隐性缺陷、安全发现、覆盖评估等
缺陷维度数据的构建逻辑。所有方法为静态方法，通过 ReportService 继承暴露。
"""
import json
from typing import Dict, Any, List

from sqlalchemy.orm import Session, joinedload

from app.models.test_result import TestResult
from app.models.test_case import TestCase


class _ReportDefectDimensionBuilder:
    """报告缺陷维度构建器：缺陷概览/明细/分布/隐性/安全/覆盖评估。"""

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
            .options(joinedload(Bug.test_result))
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
                "fix_suggestion": _ReportDefectDimensionBuilder._generate_fix_suggestion(
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
            .options(joinedload(Bug.test_case), joinedload(Bug.test_result))
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
            .options(joinedload(Bug.test_case))
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
            .options(joinedload(Bug.test_result))
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
            .options(joinedload(Bug.test_case))
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
