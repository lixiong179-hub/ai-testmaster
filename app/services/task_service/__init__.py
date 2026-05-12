from app.services.task_service.core_mixin import TaskCoreMixin
from app.services.task_service.execution_mixin import TaskExecutionMixin
from app.services.task_service.push_mixin import TaskPushMixin


class TaskService(TaskCoreMixin, TaskExecutionMixin, TaskPushMixin):
    """任务执行服务"""

    def __init__(self):
        TaskCoreMixin.__init__(self)
        TaskPushMixin.__init__(self)


TestTaskService = TaskService
