"""
项目流程数据CRUD操作模块

提供项目流程数据（ProjectFlowData）的保存与查询操作。项目流程数据是用户在
AI用例生成流程中对页面流程图（FlowSortEditor）的编辑结果，每个项目仅保留
一条记录（project_id唯一）。

核心函数概览：
    - save_project_flow_data: 保存流程数据（存在则更新，不存在则新增）
    - get_project_flow_data: 查询流程数据

与Model/Schema的对应关系：
    - Model: app.models.project_flow_data.ProjectFlowData

事务处理方式：
    - 写操作自动commit
"""
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.models.project_flow_data import ProjectFlowData
from app.utils.db_time import utcnow


def save_project_flow_data(
    db: Session,
    project_id: int,
    flow_data: Dict[str, Any],
) -> ProjectFlowData:
    """
    Upsert项目流程数据

    根据project_id查询已有记录：若存在则更新flow_data与update_time；
    若不存在则插入新记录。每个项目仅保留一条流程数据记录。

    Args:
        db: 数据库会话
        project_id: 项目ID
        flow_data: 完整流程数据（nodes/edges/module_info等）

    Returns:
        ProjectFlowData: 保存后的流程数据对象（已commit并refresh）
    """
    existing = (
        db.query(ProjectFlowData)
        .filter(ProjectFlowData.project_id == project_id)
        .first()
    )

    if existing:
        existing.flow_data = flow_data
        existing.update_time = utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    record = ProjectFlowData(
        project_id=project_id,
        flow_data=flow_data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_project_flow_data(
    db: Session,
    project_id: int,
) -> Optional[ProjectFlowData]:
    """
    查询项目流程数据

    根据project_id查询项目的流程编辑数据，不存在时返回None。

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        Optional[ProjectFlowData]: 流程数据对象，不存在则返回None
    """
    return (
        db.query(ProjectFlowData)
        .filter(ProjectFlowData.project_id == project_id)
        .first()
    )
