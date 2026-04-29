from typing import Any
from celery import Celery
from app.core.config import settings
from app.services.task_service import TaskService
from loguru import logger

celery_app = Celery(
    'test_task',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)

@celery_app.task
def execute_test_task(task_id: int, project_id: int, case_ids: list[int]) -> dict[str, Any]:
    try:
        logger.info(f"Celery执行任务: {task_id}, 项目: {project_id}, 用例数: {len(case_ids)}")
        task_service = TaskService()
        task_service.start_task(task_id, project_id, case_ids)
        logger.info(f"Celery任务启动成功: {task_id}")
        return {"status": "success", "task_id": task_id}
    except Exception as e:
        logger.error(f"Celery执行任务失败: {e}")
        return {"status": "error", "task_id": task_id, "error": str(e)}

@celery_app.task
def stop_test_task(task_id: int) -> dict[str, Any]:
    try:
        logger.info(f"Celery停止任务: {task_id}")
        task_service = TaskService()
        task_service.stop_task(task_id)
        logger.info(f"Celery任务停止成功: {task_id}")
        return {"status": "success", "task_id": task_id}
    except Exception as e:
        logger.error(f"Celery停止任务失败: {e}")
        return {"status": "error", "task_id": task_id, "error": str(e)}
