from typing import Any, Dict, List
from loguru import logger

from app.models.test_case import TestCase
from app.models.enums import ExecStatus
from app.services.test_execution_engine.models import ExecutionError


class _HelpersMixin:

    def _resolve_execution_order(self, cases: List[TestCase]) -> List[TestCase]:
        has_dependency = any(getattr(c, 'depends_on', None) for c in cases)
        if not has_dependency:
            return cases

        graph = self._build_dependency_graph(cases)
        sorted_cases = self._topological_sort_cases(cases, graph)

        main_count = sum(1 for c in sorted_cases if not getattr(c, 'depends_on', None))
        dep_count = len(sorted_cases) - main_count
        logger.info(
            f"依赖解析完成: 主干用例 {main_count} 条, "
            f"依赖用例 {dep_count} 条, "
            f"快照锚点 {len(self._collect_anchor_steps(sorted_cases))} 个"
        )
        return sorted_cases

    def _collect_anchor_steps(self, cases: List[TestCase]) -> List[int]:
        steps = []
        for case in cases:
            anchor = getattr(case, 'anchor_step', None)
            if anchor is not None:
                steps.append(anchor)
        return steps

    def _build_anchor_step_index(self, cases: List[TestCase]) -> Dict[tuple, bool]:
        index: Dict[tuple, bool] = {}
        for case in cases:
            depends_on = getattr(case, 'depends_on', None)
            anchor = getattr(case, 'anchor_step', None)
            if depends_on and anchor is not None:
                index[(depends_on, anchor)] = True
        return index

    def _get_task_summary(self, task_id: int) -> Dict[str, Any]:
        from app.models.test_task import TestTask
        from app.models.test_result import TestResult

        task = self.db.query(TestTask).filter(TestTask.id == task_id).first()
        if not task:
            raise ExecutionError(f"测试任务不存在: {task_id}")

        results = self.db.query(TestResult).filter(TestResult.task_id == task_id).all()

        total = len(results)
        passed = len([r for r in results if r.exec_status == ExecStatus.PASSED])
        failed = len([r for r in results if r.exec_status == ExecStatus.FAILED])
        blocked = len([r for r in results if r.exec_status == ExecStatus.BLOCKED])

        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "task_id": task.id,
            "task_name": task.task_name,
            "status": str(task.status),
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "blocked_cases": blocked,
            "pass_rate": f"{pass_rate:.2f}%",
            "start_time": task.start_time.strftime("%Y-%m-%d %H:%M:%S") if task.start_time else None,
            "end_time": task.end_time.strftime("%Y-%m-%d %H:%M:%S") if task.end_time else None,
        }

    def get_task_execution_summary(self, task_id: int) -> Dict[str, Any]:
        return self._get_task_summary(task_id)
