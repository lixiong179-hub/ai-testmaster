import re
from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.test_execution_engine.models import FailureCategory


class _HelpersMixin:

    def _generate_execution_summary(
        self,
        result: Any,
        test_case: Any,
    ) -> Dict[str, Any]:
        return {
            "case_id": result.case_id,
            "case_no": test_case.case_no,
            "title": test_case.title,
            "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
            "total_steps": result.total_steps,
            "passed_steps": result.passed_steps,
            "failed_steps": result.failed_steps,
            "duration_ms": result.duration_ms,
            "failure_category": result.failure_category.value if result.failure_category else None,
            "navigation_level": result.navigation_level,
        }

    async def get_execution_history(
        self,
        case_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        from app.models.test_result import TestResult
        from app.models.enums import ExecStatus

        results = self.db.query(TestResult).filter(
            TestResult.case_id == case_id,
        ).order_by(TestResult.exec_time.desc()).limit(limit).all()

        history = []
        for r in results:
            history.append({
                "id": r.id,
                "exec_status": r.exec_status,
                "exec_time": r.exec_time,
                "error_msg": r.error_msg,
                "duration_ms": getattr(r, 'duration_ms', None),
            })
        return history

    async def _try_save_anchor_snapshot(
        self,
        case: Any,
        step_number: int,
    ) -> bool:
        try:
            return await self._save_anchor_snapshot(case, step_number)
        except Exception as e:
            logger.warning(f"保存锚点快照失败: {e}")
            return False

    def _infer_failure_category(self, error: Exception) -> FailureCategory:
        error_msg = str(error).lower()

        if self._is_crash_error(error_msg):
            return FailureCategory.CRASH_BUG

        if self._is_performance_error(error_msg):
            return FailureCategory.PERFORMANCE_BUG

        if self._is_device_compatibility_issue(error_msg):
            return FailureCategory.COMPATIBILITY_BUG

        if "locator" in error_msg or "element" in error_msg or "not found" in error_msg:
            return FailureCategory.LOCATOR_FAILURE

        if "navigation" in error_msg or "navigate" in error_msg:
            return FailureCategory.NAVIGATION_FAILURE

        if "precondition" in error_msg or "setup" in error_msg:
            return FailureCategory.PRECONDITION_FAILURE

        if "timeout" in error_msg or "timed out" in error_msg:
            return FailureCategory.ENVIRONMENT_ERROR

        return FailureCategory.PRODUCT_BUG

    @staticmethod
    def _is_crash_error(error_msg: str) -> bool:
        crash_patterns = (
            "crash", "segfault", "signal 11", "signal 6",
            "out of memory", "oom", "stack overflow",
            "anr", "application not responding",
        )
        return any(p in error_msg for p in crash_patterns)

    @staticmethod
    def _is_performance_error(error_msg: str) -> bool:
        perf_patterns = (
            "slow", "performance", "latency", "response time",
            "frame drop", "jank", "fps",
        )
        return any(p in error_msg for p in perf_patterns)

    @staticmethod
    def _is_device_compatibility_issue(error_msg: str) -> bool:
        compat_patterns = (
            "compatibility", "not supported", "incompatible",
            "version mismatch", "api level",
        )
        return any(p in error_msg for p in compat_patterns)
