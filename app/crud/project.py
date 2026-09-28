"""
项目CRUD主入口模块

提供项目（Project）的增删改查数据库操作，是系统最基础的数据隔离单元。
所有业务实体（测试用例、测试点、测试任务等）均以项目为顶层归属。

本模块采用"查询/变更分离"架构，将读操作和写操作分别拆分到不同子模块中，
降低单文件复杂度（与 test_case.py / test_task.py 同一模式）。

架构设计：
    - project_query.py: 负责所有只读查询操作（get/list）
    - project_mutate.py: 负责所有变更操作（create/update/delete）
    - project.py（本文件）: 统一导出入口，对外暴露完整API

导出的查询函数（来自 project_query）：
    - get_projects: 获取用户的所有项目（分页）
    - get_project_by_id: 根据ID获取项目（带用户权限过滤）

导出的变更函数（来自 project_mutate）：
    - create_project: 创建项目，默认状态为启用(1)
    - update_project: 更新项目信息（仅更新传入字段）
    - delete_project: 硬删除项目（带用户权限过滤）

与Model/Schema的对应关系：
    - Model: app.models.project.Project
    - Create Schema: app.schemas.project.ProjectCreate
    - Update Schema: app.schemas.project.ProjectUpdate

事务处理方式：
    - 所有写操作（create/update/delete）均自动commit
    - 无需调用方手动管理事务

注意：删除为硬删除，会物理移除数据库记录，关联数据需在调用方处理级联清理。

使用方式：
    from app.crud.project import create_project, get_projects
"""

__all__ = [
    # 查询函数（来自 project_query）
    "get_projects",
    "get_project_by_id",
    # 变更函数（来自 project_mutate）
    "create_project",
    "update_project",
    "delete_project",
]

from app.crud.project_query import (
    get_projects,
    get_project_by_id,
)
from app.crud.project_mutate import (
    create_project,
    update_project,
    delete_project,
)
