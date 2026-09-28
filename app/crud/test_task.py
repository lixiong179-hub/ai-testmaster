"""
测试任务CRUD主入口模块

本模块是测试任务（TestTask）CRUD操作的统一入口，采用"查询/变更分离"架构，
将读操作和写操作分别拆分到不同子模块中，降低单文件复杂度。

架构设计：
    - test_task_query.py: 负责所有只读查询操作（get/list/count）
    - test_task_mutate.py: 负责所有变更操作（create/update/delete）
    - test_task.py（本文件）: 统一导出入口，对外暴露完整API（含异步兼容导出）

导出的查询函数（来自 test_task_query）：
    - get_test_task_by_id: 根据ID获取测试任务（带项目隔离）
    - get_test_tasks_by_project: 获取项目的测试任务列表（支持状态过滤+分页+时间倒序）
    - get_test_tasks_count: 获取测试任务数量（用于分页计算）

导出的变更函数（来自 test_task_mutate）：
    - create_test_task: 创建测试任务，初始化状态和计数
    - update_test_task_status: 更新任务状态，自动记录开始/结束时间
    - update_test_task_progress: 更新任务执行进度和成功/失败计数
    - delete_test_task: 删除测试任务（硬删除）

异步兼容导出（来自 _test_task_async.py）：
    - create_test_task_async
    - get_test_task_by_id_async
    - update_test_task_status_async
    - update_test_task_progress_async

使用方式：
    from app.crud.test_task import create_test_task, get_test_task_by_id
"""

from app.crud.test_task_query import (
    get_test_task_by_id,
    get_test_tasks_by_project,
    get_test_tasks_count,
)
from app.crud.test_task_mutate import (
    create_test_task,
    update_test_task_status,
    update_test_task_progress,
    delete_test_task,
)
from app.crud._test_task_async import (
    create_test_task_async,
    get_test_task_by_id_async,
    update_test_task_status_async,
    update_test_task_progress_async,
)

__all__ = [
    "get_test_task_by_id",
    "get_test_tasks_by_project",
    "get_test_tasks_count",
    "create_test_task",
    "update_test_task_status",
    "update_test_task_progress",
    "delete_test_task",
    "create_test_task_async",
    "get_test_task_by_id_async",
    "update_test_task_status_async",
    "update_test_task_progress_async",
]
