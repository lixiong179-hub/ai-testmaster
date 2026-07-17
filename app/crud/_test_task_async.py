"""测试任务异步 CRUD 操作。

从 `app/crud/test_task.py` 拆分而来，集中存放 AsyncSession 版本的 CRUD，
避免单文件超过 350 行。sync 版本仍保留在 `test_task.py`。

函数清单：
    - create_test_task_async: 创建测试任务（异步）
    - get_test_task_by_id_async: 根据 ID 获取测试任务（异步）
    - update_test_task_status_async: 更新任务状态（异步）
    - update_test_task_progress_async: 更新任务进度（异步）

兼容性：`test_task.py` 通过 re-export 保持 `from app.crud.test_task import
create_test_task_async` 等导入路径不变，调用方零改动。
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_task import TestTask
from app.utils.db_time import utcnow


async def create_test_task_async(
    db: AsyncSession,
    task_name: str,
    project_id: int,
    case_ids: List[int],
    executor_id: int
) -> TestTask:
    """创建测试任务（异步版本）。

    create_test_task 的异步实现，使用 AsyncSession 进行数据库操作。
    创建一个新的测试执行任务，初始化所有计数器为0，状态为"等待执行"。

    Args:
        db: 异步数据库会话
        task_name: 任务名称
        project_id: 所属项目ID
        case_ids: 待执行的用例ID列表
        executor_id: 执行用户ID

    Returns:
        TestTask: 创建成功后的测试任务对象（已commit并refresh）
    """
    total_count = len(case_ids)
    test_task = TestTask(
        task_name=task_name,
        project_id=project_id,
        case_ids=case_ids,
        executor_id=executor_id,
        total_count=total_count,
        status=0,
        progress=0,
        success_count=0,
        fail_count=0
    )
    db.add(test_task)
    await db.commit()
    await db.refresh(test_task)
    return test_task


async def get_test_task_by_id_async(db: AsyncSession, task_id: int, project_id: int) -> Optional[TestTask]:
    """根据ID获取测试任务（异步版本）。

    get_test_task_by_id 的异步实现，通过任务ID和项目ID联合过滤定位唯一任务。

    Args:
        db: 异步数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[TestTask]: 测试任务对象，不存在则返回None
    """
    result = await db.execute(
        select(TestTask).where(
            TestTask.id == task_id,
            TestTask.project_id == project_id
        )
    )
    return result.scalars().first()


async def update_test_task_status_async(
    db: AsyncSession,
    task_id: int,
    project_id: int,
    status: int
) -> Optional[TestTask]:
    """更新测试任务状态（异步版本）。

    update_test_task_status 的异步实现，根据新状态自动记录开始时间或结束时间。

    Args:
        db: 异步数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于存在性校验
        status: 新状态值，0=等待/1=执行中/2=完成/3=失败/4=停止

    Returns:
        Optional[TestTask]: 更新后的测试任务对象，不存在则返回None
    """
    test_task = await get_test_task_by_id_async(db, task_id, project_id)
    if not test_task:
        return None

    test_task.status = status

    if status == 1:  # 开始执行
        test_task.start_time = utcnow()
    elif status in [2, 3, 4]:  # 执行完成/失败/停止
        test_task.end_time = utcnow()

    await db.commit()
    await db.refresh(test_task)
    return test_task


async def update_test_task_progress_async(
    db: AsyncSession,
    task_id: int,
    project_id: int,
    progress: int,
    success_count: Optional[int] = None,
    fail_count: Optional[int] = None
) -> Optional[TestTask]:
    """更新测试任务进度（异步版本）。

    update_test_task_progress 的异步实现，更新任务执行进度和成功/失败计数。

    Args:
        db: 异步数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于存在性校验
        progress: 执行进度，0-100的百分比值
        success_count: 成功用例数（可选）
        fail_count: 失败用例数（可选）

    Returns:
        Optional[TestTask]: 更新后的测试任务对象，不存在则返回None
    """
    test_task = await get_test_task_by_id_async(db, task_id, project_id)
    if not test_task:
        return None

    test_task.progress = progress

    if success_count is not None:
        test_task.success_count = success_count

    if fail_count is not None:
        test_task.fail_count = fail_count

    await db.commit()
    await db.refresh(test_task)
    return test_task
