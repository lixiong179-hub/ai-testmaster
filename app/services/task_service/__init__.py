from typing import List, Dict, Any
from datetime import datetime
import asyncio
from app.db.database import get_db
from app.crud.test_task import (
    update_test_task_status,
    update_test_task_progress
)
from app.crud.test_result import (
    create_test_result,
    update_test_result
)
from app.models.test_case import TestCase
from app.core.config import settings
from app.utils.websocket import manager
from loguru import logger

from app.services.task_service.core_mixin import TaskCoreMixin
from app.services.task_service.execution_mixin import TaskExecutionMixin
from app.services.task_service.push_mixin import TaskPushMixin


class TaskService(TaskCoreMixin, TaskExecutionMixin, TaskPushMixin):
    """任务执行服务"""

    def __init__(self):
        TaskCoreMixin.__init__(self)
        TaskPushMixin.__init__(self)


TestTaskService = TaskService
