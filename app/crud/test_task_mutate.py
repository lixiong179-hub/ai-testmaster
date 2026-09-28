"""
测试任务变更操作模块

提供测试任务（TestTask）的所有变更操作（创建/更新状态/更新进度/删除），
与 test_task_query.py 共同构成测试任务的完整CRUD能力。
本模块仅包含变更函数，不涉及对外暴露的查询操作。

核心函数概览：
    - create_test_task: 创建测试任务，初始化状态和计数
    - update_test_task_status: 更新任务状态，自动记录开始/结束时间
    - update_test_task_progress: 更新任务执行进度和成功/失败计数
    - delete_test_task: 删除测试任务（硬删除）

与Model/Schema的对应关系：
    - Model: app.models.test_task.TestTask

依赖关系：
    - 复用 test_task_query.get_test_task_by_id 作为 update/delete 的存在性校验

事务处理方式：
    - 所有写操作均自动 commit

状态机设计：
    - 0: 等待执行（初始状态）
    - 1: 执行中（自动记录start_time）
    - 2: 执行完成（自动记录end_time）
    - 3: 执行失败（自动记录end_time）
    - 4: 执行停止（自动记录end_time）

软删除/硬删除：
    - delete_test_task 为硬删除，物理移除数据库记录
    - 关联的测试结果（TestResult）需在调用方处理级联清理
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.test_task import TestTask
from app.utils.db_time import utcnow
from app.crud.test_task_query import get_test_task_by_id


def create_test_task(
    db: Session,
    task_name: str,
    project_id: int,
    case_ids: List[int],
    executor_id: int
) -> TestTask:
    """
    创建测试任务

    创建一个新的测试执行任务，初始化所有计数器为0，状态为"等待执行"。
    case_ids字段以JSON数组形式存储待执行的用例ID列表。

    Args:
        db: 数据库会话
        task_name: 任务名称，如"回归测试-2024Q1"
        project_id: 所属项目ID
        case_ids: 待执行的用例ID列表，JSON数组存储
        executor_id: 执行用户ID

    Returns:
        TestTask: 创建成功后的测试任务对象（已commit并refresh）

    Note:
        - total_count 由 case_ids 列表长度自动计算
        - 初始状态为0（等待执行），进度为0，成功/失败计数均为0
    """
    total_count = len(case_ids)
    test_task = TestTask(
        task_name=task_name,
        project_id=project_id,
        case_ids=case_ids,
        executor_id=executor_id,
        total_count=total_count,
        status=0,  # 0: 等待执行
        progress=0,
        success_count=0,
        fail_count=0
    )
    db.add(test_task)
    db.commit()
    db.refresh(test_task)
    return test_task


def update_test_task_status(
    db: Session,
    task_id: int,
    project_id: int,
    status: int
) -> Optional[TestTask]:
    """
    更新测试任务状态

    根据新状态自动记录开始时间或结束时间，实现状态机的时间戳管理。
    - 状态变为1（执行中）：自动记录start_time
    - 状态变为2/3/4（完成/失败/停止）：自动记录end_time

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于存在性校验
        status: 新状态值，0=等待/1=执行中/2=完成/3=失败/4=停止

    Returns:
        Optional[TestTask]: 更新后的测试任务对象，不存在则返回None

    Note:
        状态机时间戳自动管理逻辑：
        - 开始执行(1)时记录start_time
        - 执行完成/失败/停止(2/3/4)时记录end_time
        - 等待执行(0)不记录任何时间
    """
    test_task = get_test_task_by_id(db, task_id, project_id)
    if not test_task:
        return None

    test_task.status = status

    if status == 1:  # 开始执行
        test_task.start_time = utcnow()
    elif status in [2, 3, 4]:  # 执行完成/失败/停止
        test_task.end_time = utcnow()

    db.commit()
    db.refresh(test_task)
    return test_task


def update_test_task_progress(
    db: Session,
    task_id: int,
    project_id: int,
    progress: int,
    success_count: Optional[int] = None,
    fail_count: Optional[int] = None
) -> Optional[TestTask]:
    """
    更新任务进度

    在任务执行过程中，由执行引擎定期更新进度和成功/失败计数。
    success_count和fail_count为可选参数，仅在需要更新时传入。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于存在性校验
        progress: 执行进度，0-100的百分比值
        success_count: 成功用例数（可选）
        fail_count: 失败用例数（可选）

    Returns:
        Optional[TestTask]: 更新后的测试任务对象，不存在则返回None

    Note:
        success_count和fail_count使用 `is not None` 判断，
        因为0也是有效值（尚未有成功/失败的用例）。
    """
    test_task = get_test_task_by_id(db, task_id, project_id)
    if not test_task:
        return None

    test_task.progress = progress

    # 仅在传入时更新计数，0也是有效值
    if success_count is not None:
        test_task.success_count = success_count

    if fail_count is not None:
        test_task.fail_count = fail_count

    db.commit()
    db.refresh(test_task)
    return test_task


def delete_test_task(db: Session, task_id: int, project_id: int) -> bool:
    """
    删除测试任务（硬删除）

    物理删除测试任务记录。删除前通过 get_test_task_by_id 校验任务存在性和项目归属。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于存在性校验

    Returns:
        bool: 删除成功返回True，任务不存在返回False

    Warning:
        硬删除操作，关联的测试结果（TestResult）需在调用方处理级联清理，
        否则会产生孤立数据。
    """
    test_task = get_test_task_by_id(db, task_id, project_id)
    if not test_task:
        return False

    db.delete(test_task)  # 硬删除：物理移除数据库记录
    db.commit()
    return True
