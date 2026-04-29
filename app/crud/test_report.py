"""
测试报告CRUD操作模块

提供测试报告（TestReport）的增删改查数据库操作。测试报告是测试任务执行完成后的
汇总文档，包含报告名称、描述、关联的项目和任务等信息。

核心函数概览：
    - create_test_report: 创建测试报告
    - get_test_reports: 获取项目的所有测试报告（分页）
    - get_test_report_by_id: 根据ID获取测试报告（带项目权限过滤）
    - update_test_report: 更新测试报告（仅更新传入字段）
    - delete_test_report: 删除测试报告（硬删除，带项目权限过滤）
    - get_test_reports_by_task: 根据测试任务ID获取报告（带项目权限过滤）

与Model/Schema的对应关系：
    - Model: app.models.report.TestReport
    - Create Schema: app.schemas.test_report.TestReportCreate
    - Update Schema: app.schemas.test_report.TestReportUpdate

与其他CRUD模块的调用关系：
    - 创建报告时关联 test_task（test_task_id字段）
    - 报告内容基于 test_result 的执行结果聚合生成

事务处理方式：
    - 所有写操作均自动commit

软删除/硬删除：
    - delete_test_report 为硬删除，物理移除数据库记录
"""
from sqlalchemy.orm import Session
from app.models.report import TestReport
from app.schemas.test_report import TestReportCreate, TestReportUpdate
from typing import List, Optional


def create_test_report(db: Session, report: TestReportCreate, user_id: int) -> TestReport:
    """
    创建测试报告

    创建一条测试报告记录，关联项目和测试任务。报告内容通常基于
    测试任务的执行结果聚合生成。

    Args:
        db: 数据库会话
        report: 报告创建参数，包含name/description/project_id/test_task_id
        user_id: 创建者用户ID（当前未存储到报告记录中，预留扩展）

    Returns:
        TestReport: 创建成功后的测试报告对象（已commit并refresh）

    Note:
        user_id参数当前未使用，预留用于后续增加创建者字段。
    """
    db_report = TestReport(
        name=report.name,
        description=report.description,
        project_id=report.project_id,
        test_task_id=report.test_task_id
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


def get_test_reports(db: Session, project_id: int, skip: int = 0, limit: int = 100) -> List[TestReport]:
    """
    获取项目的所有测试报告（分页）

    按项目ID过滤报告列表，结果按默认排序返回。

    Args:
        db: 数据库会话
        project_id: 项目ID
        skip: 跳过记录数，用于分页偏移
        limit: 返回记录上限

    Returns:
        List[TestReport]: 测试报告列表

    Note:
        此函数未做用户权限过滤，适用于内部调用；
        对外接口应在Service层增加用户权限校验。
    """
    return db.query(TestReport).filter(
        TestReport.project_id == project_id
    ).offset(skip).limit(limit).all()


def get_test_report_by_id(db: Session, report_id: int, project_id: int) -> Optional[TestReport]:
    """
    根据ID获取测试报告，带项目权限过滤

    通过报告ID和项目ID联合过滤，确保在项目维度下定位唯一报告，
    防止跨项目访问报告数据。

    Args:
        db: 数据库会话
        report_id: 报告ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[TestReport]: 测试报告对象，不存在则返回None
    """
    return db.query(TestReport).filter(
        TestReport.id == report_id,
        TestReport.project_id == project_id
    ).first()


def update_test_report(db: Session, report_id: int, project_id: int, report_update: TestReportUpdate) -> Optional[TestReport]:
    """
    更新测试报告，带项目权限过滤

    仅更新传入的非空字段（exclude_unset=True），未传入的字段保持原值不变。
    先通过 get_test_report_by_id 校验项目权限。

    Args:
        db: 数据库会话
        report_id: 报告ID
        project_id: 项目ID，用于权限校验
        report_update: 报告更新参数，仅包含需要修改的字段

    Returns:
        Optional[TestReport]: 更新后的报告对象，不存在或无权限则返回None

    Note:
        使用 model_dump(exclude_unset=True) 实现"部分更新"语义，
        避免未传入字段被覆盖为None。
    """
    db_report = get_test_report_by_id(db, report_id, project_id)
    if not db_report:
        return None

    # exclude_unset=True: 仅获取用户实际传入的字段
    update_data = report_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_report, field, value)

    db.commit()
    db.refresh(db_report)
    return db_report


def delete_test_report(db: Session, report_id: int, project_id: int) -> bool:
    """
    删除测试报告，带项目权限过滤（硬删除）

    物理删除测试报告记录。删除前通过 get_test_report_by_id 校验项目权限。

    Args:
        db: 数据库会话
        report_id: 报告ID
        project_id: 项目ID，用于权限校验

    Returns:
        bool: 删除成功返回True，报告不存在或无权限返回False
    """
    db_report = get_test_report_by_id(db, report_id, project_id)
    if not db_report:
        return False

    db.delete(db_report)  # 硬删除：物理移除数据库记录
    db.commit()
    return True


def get_test_reports_by_task(db: Session, test_task_id: int, project_id: int) -> List[TestReport]:
    """
    根据测试任务ID获取测试报告，带项目权限过滤

    查询指定测试任务关联的所有报告。一个任务可能生成多份报告
    （如不同时间点的快照报告）。

    Args:
        db: 数据库会话
        test_task_id: 测试任务ID
        project_id: 项目ID，用于权限校验

    Returns:
        List[TestReport]: 关联该任务的报告列表

    Note:
        此查询未加分页，适用于单任务报告数量较少的场景。
    """
    return db.query(TestReport).filter(
        TestReport.test_task_id == test_task_id,
        TestReport.project_id == project_id
    ).all()
