"""批量任务管理器 - 管理并发批量定位任务。
"""
from typing import Dict, Optional, Any
from loguru import logger
from app.utils.db_time import utcnow

from app.services.batch_locator.models import BatchRecordReport


class BatchTaskManager:

    _instance = None
    _tasks: Dict[int, Any] = {}
    _reports: Dict[int, tuple] = {}

    def __new__(cls) -> 'BatchTaskManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_task(self, case_id: int, service: Any) -> None:
        self._tasks[case_id] = service
        logger.info(f"批量任务已注册: case_id={case_id}")

    def unregister_task(self, case_id: int) -> None:
        service = self._tasks.get(case_id)
        if service:
            report = service.get_report()
            if report:
                self._reports[case_id] = (report, utcnow())
            if case_id in self._tasks:
                del self._tasks[case_id]
            logger.info(f"批量任务已注销: case_id={case_id}")
        self._cleanup_expired_reports()

    def get_task(self, case_id: int) -> Any | None:
        return self._tasks.get(case_id)

    def get_report(self, case_id: int) -> Optional[Any]:
        service = self._tasks.get(case_id)
        if service:
            return service.get_report()
        cached = self._reports.get(case_id)
        if cached:
            return cached[0]
        return None

    def cancel_task(self, case_id: int) -> bool:
        service = self._tasks.get(case_id)
        if service:
            service.cancel()
            return True
        return False

    def get_all_tasks(self) -> Dict[int, Any]:
        return self._tasks.copy()

    def _cleanup_expired_reports(self) -> None:
        now = utcnow()
        expired = [
            case_id for case_id, (_, completed_at) in self._reports.items()
            if (now - completed_at).total_seconds() > 1800
        ]
        for case_id in expired:
            del self._reports[case_id]
