"""
迭代CRUD主入口模块

提供迭代（Iteration）的增删改查数据库操作。迭代是项目管理中的版本规划单元，
用于按版本/阶段组织项目文件、测试用例等资源，实现迭代维度的数据隔离。

本模块采用"查询/变更分离"架构，将读操作和写操作分别拆分到不同子模块中，
降低单文件复杂度（与 test_case.py / test_task.py 同一模式）。

架构设计：
    - iteration_query.py: 负责所有只读查询操作（get/list/count）
    - iteration_mutate.py: 负责所有变更操作（create/update/delete）
    - iteration.py（本文件）: 统一导出入口，对外暴露完整API

导出的查询函数（来自 iteration_query）：
    - get_iteration: 根据ID获取迭代
    - get_iterations_by_project: 获取项目的迭代列表（按创建时间倒序+分页）
    - get_iterations_count_by_project: 获取项目的迭代数量

导出的变更函数（来自 iteration_mutate）：
    - create_iteration: 创建迭代（同名校验，防止项目下重复）
    - update_iteration: 更新迭代（重命名时校验同名，自动更新update_time）
    - delete_iteration: 删除迭代（支持清理回调，异常时自动回滚）

与Model/Schema的对应关系：
    - Model: app.models.iteration.Iteration

与其他CRUD模块的调用关系：
    - file.py: 文件通过iteration_id关联迭代
    - ui_prototype_project.py: UI原型项目通过iteration_id关联迭代
    - 删除迭代时需通过cleanup_callback清理关联资源

事务处理方式：
    - 常规写操作：自动commit
    - delete_iteration: 支持cleanup_callback，异常时自动rollback

软删除/硬删除：
    - delete_iteration 为硬删除，物理移除数据库记录
    - 通过cleanup_callback参数支持删除前的关联资源清理

迭代状态枚举：
    - draft: 草稿
    - in_pipeline: 流水线运行中
    - in_review: 评审中
    - finalized: 已定稿
    - archived: 已归档

使用方式：
    from app.crud.iteration import create_iteration, get_iterations_by_project
"""

__all__ = [
    # 查询函数（来自 iteration_query）
    "get_iteration",
    "get_iterations_by_project",
    "get_iterations_count_by_project",
    # 变更函数（来自 iteration_mutate）
    "create_iteration",
    "update_iteration",
    "delete_iteration",
    # 常量（原单体模块顶层常量，保持向后兼容）
    "MAX_ITERATION_NAME_LENGTH",
]

from app.crud.iteration_query import (
    get_iteration,
    get_iterations_by_project,
    get_iterations_count_by_project,
)
from app.crud.iteration_mutate import (
    # 私有工具函数保持模块级可用：app/services/iteration_async_mixin.py 直接引用
    _normalize_iteration_name,
    MAX_ITERATION_NAME_LENGTH,
    create_iteration,
    update_iteration,
    delete_iteration,
)
