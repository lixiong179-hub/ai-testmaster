"""
UI原型CRUD主入口模块

本模块是UI原型相关CRUD操作的统一入口，采用"项目/页面/变更"三层架构，
将不同维度的操作拆分到不同子模块中，降低单文件复杂度。

架构设计：
    - ui_prototype_project.py: UI原型项目级别的CRUD操作
    - ui_prototype_screen.py: UI原型页面级别的查询操作
    - ui_prototype_screen_mutate.py: UI原型页面级别的变更操作
    - ui_prototype.py（本文件）: 统一导出入口，对外暴露完整API

导出的项目级函数（来自 ui_prototype_project）：
    - create_ui_prototype_project: 创建UI原型项目
    - get_ui_prototype_projects_by_project: 获取项目的UI原型项目列表
    - get_ui_prototype_projects_count: 获取UI原型项目数量
    - update_prototype_project_stats: 更新原型项目统计信息（页面数/解析数/解析状态）
    - update_prototype_project_merged_flow: 更新原型项目的合并流程图

导出的页面查询函数（来自 ui_prototype_screen）：
    - _apply_iteration_filter: 迭代过滤条件构建器（内部函数）
    - get_ui_screen_by_id: 根据ID获取UI页面
    - get_ui_screens_by_project: 获取项目的UI页面列表
    - get_ui_screens_count: 获取UI页面数量
    - get_test_cases_by_screen: 获取页面关联的测试用例ID列表
    - get_parsed_ui_screens_for_case_generation: 获取已解析的UI页面（用于AI用例生成）

导出的页面变更函数（来自 ui_prototype_screen_mutate）：
    - create_ui_screen: 创建UI页面
    - update_ui_screen_parse_result: 更新页面解析结果
    - update_ui_screen_parse_status: 更新页面解析状态
    - update_ui_screen_review: 更新页面审核状态
    - delete_ui_screen: 删除UI页面（级联删除关联链接）
    - link_ui_screen_to_test_case: 关联UI页面与测试用例
    - update_ui_screen_order: 更新页面排序
    - batch_create_ui_screens: 批量创建UI页面

与Model/Schema的对应关系：
    - Model: app.models.ui_prototype.UIPrototypeProject（原型项目）
    - Model: app.models.ui_prototype.UIPrototypeScreen（原型页面）
    - Model: app.models.ui_prototype.UIScreenTestCaseLink（页面-用例关联）

使用方式：
    from app.crud.ui_prototype import create_ui_screen, get_ui_screens_by_project
"""
from app.crud.ui_prototype_project import (
    create_ui_prototype_project,
    get_ui_prototype_projects_by_project,
    get_ui_prototype_projects_count,
    update_prototype_project_stats,
    update_prototype_project_merged_flow,
)
from app.crud.ui_prototype_screen import (
    _apply_iteration_filter,
    get_ui_screen_by_id,
    get_ui_screens_by_project,
    get_ui_screens_count,
    get_test_cases_by_screen,
    get_parsed_ui_screens_for_case_generation,
)
from app.crud.ui_prototype_screen_mutate import (
    create_ui_screen,
    update_ui_screen_parse_result,
    update_ui_screen_parse_status,
    update_ui_screen_review,
    delete_ui_screen,
    link_ui_screen_to_test_case,
    update_ui_screen_order,
    batch_create_ui_screens,
)
