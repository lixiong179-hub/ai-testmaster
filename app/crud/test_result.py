"""
测试结果CRUD操作模块

提供测试结果（TestResult）的增删改查数据库操作。测试结果记录每条用例在
测试任务中的执行情况，包括执行状态、日志、错误信息、截图等。

核心函数概览：
    - create_test_result: 创建单条执行结果
    - get_test_results_by_task: 获取任务的所有执行结果（按创建时间排序）
    - get_test_result_by_case: 获取指定任务和用例的执行结果
    - update_test_result: 更新执行结果（状态/日志/错误/截图），自动记录执行时间
    - get_test_results_count: 获取执行结果数量（支持状态过滤）
    - delete_test_results_by_task: 批量删除任务的所有执行结果

与Model/Schema的对应关系：
    - Model: app.models.test_result.TestResult

与其他CRUD模块的调用关系：
    - 被 test_task 模块引用：任务执行过程中逐条创建执行结果
    - 被 test_report 模块引用：生成报告时聚合执行结果统计数据

事务处理方式：
    - 所有写操作均自动commit
    - delete_test_results_by_task 使用批量delete，单次commit

执行状态枚举：
    - 0: 未执行
    - 1: 执行成功
    - 2: 执行失败
    - 3: 阻塞
"""
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.models.test_result import TestResult
from app.utils.db_time import utcnow


def create_test_result(
    db: Session,
    task_id: int,
    project_id: int,
    case_id: int,
    case_no: str,
    exec_status: int,
    exec_log: Optional[str] = None,
    error_msg: Optional[str] = None,
    screenshot_url: Optional[str] = None
) -> TestResult:
    """
    创建执行结果

    记录一条用例在测试任务中的执行情况。通常在任务开始执行时创建，
    后续通过 update_test_result 更新执行状态和结果。

    Args:
        db: 数据库会话
        task_id: 所属测试任务ID
        project_id: 所属项目ID
        case_id: 测试用例ID
        case_no: 用例编号，冗余存储便于查询展示
        exec_status: 执行状态，0=未执行/1=执行成功/2=执行失败/3=阻塞
        exec_log: 执行日志（可选），完整的执行过程记录
        error_msg: 错误信息（可选），失败时的错误摘要
        screenshot_url: 截图路径（可选），失败时的界面截图

    Returns:
        TestResult: 创建成功后的执行结果对象（已commit并refresh）
    """
    test_result = TestResult(
        task_id=task_id,
        project_id=project_id,
        case_id=case_id,
        case_no=case_no,
        exec_status=exec_status,
        exec_log=exec_log,
        error_msg=error_msg,
        screenshot_url=screenshot_url
    )
    db.add(test_result)
    db.commit()
    db.refresh(test_result)
    return test_result


def get_test_results_by_task(
    db: Session,
    task_id: int,
    project_id: int
) -> List[TestResult]:
    """
    获取任务的执行结果列表

    查询指定任务下所有用例的执行结果，按创建时间升序排列，
    保持与用例执行顺序一致。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        List[TestResult]: 执行结果列表，按创建时间升序

    Note:
        此查询未加分页，适用于单任务用例数量可控的场景。
        若单任务用例可能较多，建议增加分页参数。
    """
    return db.query(TestResult).filter(
        TestResult.task_id == task_id,
        TestResult.project_id == project_id
    ).order_by(TestResult.create_time).all()


def get_test_result_by_case(
    db: Session,
    task_id: int,
    case_id: int,
    project_id: int
) -> Optional[TestResult]:
    """
    获取指定任务和用例的执行结果

    通过任务ID+用例ID+项目ID三重过滤，精确定位某条用例在某次任务中的执行结果。

    Args:
        db: 数据库会话
        task_id: 任务ID
        case_id: 用例ID
        project_id: 项目ID

    Returns:
        Optional[TestResult]: 执行结果对象，不存在则返回None

    Note:
        同一用例在不同任务中可能有不同的执行结果，
        因此需要task_id+case_id联合定位。
    """
    return db.query(TestResult).filter(
        TestResult.task_id == task_id,
        TestResult.case_id == case_id,
        TestResult.project_id == project_id
    ).first()


def update_test_result(
    db: Session,
    result_id: int,
    project_id: int,
    exec_status: Optional[int] = None,
    exec_log: Optional[str] = None,
    error_msg: Optional[str] = None,
    screenshot_url: Optional[str] = None
) -> Optional[TestResult]:
    """
    更新执行结果

    更新用例执行的状态、日志、错误信息和截图。每次更新自动记录执行时间（exec_time）。
    仅传入非None的参数会被更新，未传入的参数保持原值不变。

    Args:
        db: 数据库会话
        result_id: 执行结果ID
        project_id: 项目ID，用于权限校验
        exec_status: 执行状态（可选）
        exec_log: 执行日志（可选）
        error_msg: 错误信息（可选）
        screenshot_url: 截图路径（可选）

    Returns:
        Optional[TestResult]: 更新后的执行结果对象，不存在则返回None

    Note:
        使用 `is not None` 判断每个字段是否需要更新，
        因为0（待执行）和空字符串都是有效值。
    """
    test_result = db.query(TestResult).filter(
        TestResult.id == result_id,
        TestResult.project_id == project_id
    ).first()

    if not test_result:
        return None

    # 仅更新传入的非None字段
    if exec_status is not None:
        test_result.exec_status = exec_status

    if exec_log is not None:
        test_result.exec_log = exec_log

    if error_msg is not None:
        test_result.error_msg = error_msg

    if screenshot_url is not None:
        test_result.screenshot_url = screenshot_url

    # 每次更新自动记录执行时间
    test_result.exec_time = utcnow()

    db.commit()
    db.refresh(test_result)
    return test_result


def get_test_results_count(
    db: Session,
    task_id: int,
    project_id: int,
    exec_status: Optional[int] = None
) -> int:
    """
    获取执行结果数量

    用于统计任务中不同状态的用例数量，支持按执行状态过滤。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID
        exec_status: 执行状态（可选），0=未执行/1=执行成功/2=执行失败/3=阻塞

    Returns:
        int: 符合条件的结果数量
    """
    query = db.query(TestResult).filter(
        TestResult.task_id == task_id,
        TestResult.project_id == project_id
    )

    if exec_status is not None:
        query = query.filter(TestResult.exec_status == exec_status)

    return query.count()


def delete_test_results_by_task(db: Session, task_id: int, project_id: int) -> int:
    """
    删除任务的所有执行结果

    批量删除指定任务下的所有执行结果，用于任务删除前的级联清理。
    使用SQLAlchemy的批量delete操作，单次commit完成。

    Args:
        db: 数据库会话
        task_id: 任务ID
        project_id: 项目ID，用于权限校验

    Returns:
        int: 删除的结果数量

    Note:
        此函数应在删除测试任务（delete_test_task）之前调用，
        确保关联数据被正确清理，避免孤立记录。
    """
    deleted = db.query(TestResult).filter(
        TestResult.task_id == task_id,
        TestResult.project_id == project_id
    ).delete()  # 批量删除：单次SQL DELETE语句，无需逐条查询
    db.commit()
    return deleted


async def create_test_result_async(
    db: AsyncSession,
    task_id: int,
    project_id: int,
    case_id: int,
    case_no: str,
    exec_status: int,
    exec_log: Optional[str] = None,
    error_msg: Optional[str] = None,
    screenshot_url: Optional[str] = None
) -> TestResult:
    """
    创建执行结果（异步版本）

    create_test_result 的异步实现，记录一条用例在测试任务中的执行情况。

    Args:
        db: 异步数据库会话
        task_id: 所属测试任务ID
        project_id: 所属项目ID
        case_id: 测试用例ID
        case_no: 用例编号
        exec_status: 执行状态，0=未执行/1=执行成功/2=执行失败/3=阻塞
        exec_log: 执行日志（可选）
        error_msg: 错误信息（可选）
        screenshot_url: 截图路径（可选）

    Returns:
        TestResult: 创建成功后的执行结果对象（已commit并refresh）
    """
    test_result = TestResult(
        task_id=task_id,
        project_id=project_id,
        case_id=case_id,
        case_no=case_no,
        exec_status=exec_status,
        exec_log=exec_log,
        error_msg=error_msg,
        screenshot_url=screenshot_url
    )
    db.add(test_result)
    await db.commit()
    await db.refresh(test_result)
    return test_result
