"""
测试任务CRUD操作模块

提供测试任务（TestTask）的增删改查数据库操作。测试任务是测试执行的调度单元，
包含待执行的用例ID列表、执行进度、成功/失败计数等状态信息。

核心函数概览：
    - create_test_task: 创建测试任务，初始化状态和计数
    - get_test_task_by_id: 根据ID获取测试任务（带项目隔离）
    - get_test_tasks_by_project: 获取项目的测试任务列表（支持状态过滤+分页+时间倒序）
    - get_test_tasks_count: 获取测试任务数量（用于分页计算）
    - update_test_task_status: 更新任务状态，自动记录开始/结束时间
    - update_test_task_progress: 更新任务执行进度和成功/失败计数
    - delete_test_task: 删除测试任务（硬删除）

与Model/Schema的对应关系：
    - Model: app.models.test_task.TestTask
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）

与其他CRUD模块的调用关系：
    - 创建任务时引用 test_case 的ID列表（case_ids字段）
    - 任务执行过程中通过 test_result 模块记录每条用例的执行结果
    - 任务完成后可通过 test_report 模块生成测试报告

事务处理方式：
    - 所有写操作均自动commit

状态机设计：
    - 0: 等待执行（初始状态）
    - 1: 执行中（自动记录start_time）
    - 2: 执行完成（自动记录end_time）
    - 3: 执行失败（自动记录end_time）
    - 4: 执行停止（自动记录end_time）

拆分说明：
    - AsyncSession 版本的 CRUD 已拆至 `_test_task_async.py`，避免单文件超 350 行；
    - 本模块通过 re-export 保持 `from app.crud.test_task import xxx_async`
      导入路径不变，调用方零改动。
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.test_task import TestTask
from app.utils.db_time import utcnow

# re-export async CRUD 保持导入路径兼容（实际定义见 _test_task_async.py）
from app.crud._test_task_async import (  # noqa: F401
    create_test_task_async,
    get_test_task_by_id_async,
    update_test_task_status_async,
    update_test_task_progress_async,
)


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


def get_test_task_by_id(db: Session, task_id: int, project_id: int) -> Optional[TestTask]:
    """
    根据ID获取测试任务

    通过任务ID和项目ID联合过滤，确保在项目维度下定位唯一任务。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[TestTask]: 测试任务对象，不存在则返回None
    """
    return db.query(TestTask).filter(
        TestTask.id == task_id,
        TestTask.project_id == project_id
    ).first()


def get_test_tasks_by_project(
    db: Session,
    project_id: int,
    status: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestTask]:
    """
    获取项目的测试任务列表（支持状态过滤+分页+时间倒序）

    按创建时间倒序排列，最新的任务排在前面。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 任务状态（可选），0=等待/1=执行中/2=完成/3=失败/4=停止
        skip: 偏移量，用于分页
        limit: 限制数

    Returns:
        List[TestTask]: 测试任务列表，按创建时间倒序

    Note:
        status 使用 `is not None` 判断，因为0也是有效值（等待执行）。
    """
    query = db.query(TestTask).filter(TestTask.project_id == project_id)

    # status=0 是有效值，必须用 is not None 判断
    if status is not None:
        query = query.filter(TestTask.status == status)

    # 按创建时间倒序，最新任务排在前面
    return query.order_by(TestTask.create_time.desc()).offset(skip).limit(limit).all()


def get_test_tasks_count(db: Session, project_id: int, status: Optional[int] = None) -> int:
    """
    获取项目的测试任务数量

    用于分页计算总条数，查询条件与 get_test_tasks_by_project 一致。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 任务状态（可选）

    Returns:
        int: 符合条件的任务数量
    """
    query = db.query(TestTask).filter(TestTask.project_id == project_id)

    if status is not None:
        query = query.filter(TestTask.status == status)

    return query.count()


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
