"""
测试用例CRUD主入口模块

本模块是测试用例（TestCase）CRUD操作的统一入口，采用"查询/变更分离"架构，
将读操作和写操作分别拆分到不同子模块中，降低单文件复杂度。

架构设计：
    - test_case_query.py: 负责所有只读查询操作（get/count/list）
    - test_case_mutate.py: 负责所有变更操作（create/update/delete/batch_create）
    - test_case.py（本文件）: 统一导出入口，对外暴露完整API

导出的查询函数（来自 test_case_query）：
    - get_test_case_by_id: 根据ID获取测试用例
    - get_test_case_by_case_no: 根据用例编号获取测试用例
    - get_test_cases_by_project: 获取项目的测试用例列表（支持多条件动态过滤）
    - get_test_cases_by_project_and_user: 获取用户项目的测试用例列表（带权限过滤）
    - get_test_cases_count: 获取测试用例数量
    - get_failed_test_cases: 获取生成失败的测试用例

导出的变更函数（来自 test_case_mutate）：
    - create_test_case: 创建单个测试用例
    - update_test_case: 更新测试用例
    - delete_test_case: 删除测试用例
    - batch_create_test_cases: 批量创建测试用例

与Model/Schema的对应关系：
    - Model: app.models.test_case.TestCase
    - 关联Model: app.models.project.Project（用于JOIN查询实现用户权限过滤）

使用方式：
    from app.crud.test_case import create_test_case, get_test_cases_by_project
"""
from app.crud.test_case_query import (
    get_test_case_by_id,
    get_test_case_by_case_no,
    get_test_cases_by_project,
    get_test_cases_by_project_and_user,
    get_test_cases_count,
    get_failed_test_cases,
)
from app.crud.test_case_mutate import (
    create_test_case,
    update_test_case,
    delete_test_case,
    batch_create_test_cases,
)
