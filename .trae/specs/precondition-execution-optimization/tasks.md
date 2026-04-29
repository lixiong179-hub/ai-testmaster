# Tasks

## 任务1: 新增登录状态检测机制

* [x] 子任务 1.1: 在 `PreconditionService` 中新增 `check_login_status()` 方法

  * 检测URL不含登录关键词

  * 检测页面标题不含登录关键词

  * 检测存在登录后特有元素（如用户头像、退出按钮等）

* [x] 子任务 1.2: 在 `TestExecutionEngineV2` 中新增 `_check_precondition_status()` 方法

  * 在执行用例前检测登录状态

  * 根据检测结果决定是否需要重新登录

## 任务2: 调整前置条件执行逻辑

* [x] 子任务 2.1: 修改 `TestExecutionEngineV2.execute_test_case()` 中的 `skip_precondition` 逻辑

  * 将 `skip_precondition=True` 改为智能检测模式

  * 仅当登录状态失效时才执行登录

* [x] 子任务 2.2: 修改 `task_service.py` 中的任务级执行逻辑

  * 移除硬编码的 `skip_precondition=True`

  * 改为调用登录状态检测方法

## 任务3: AI生成用例时自动解析前置条件

* [x] 子任务 3.1: 在 `test_case_generation_service.py` 生成用例后自动调用前置条件解析

  * 检查生成用例的前置条件文本是否非空

  * 调用 `parse_precondition_to_steps()` 解析

  * 保存解析结果到 `TestCasePreconditionStep` 表

* [x] 子任务 3.2: 新增配置项控制是否自动解析（`AUTO_PARSE_PRECONDITION`）

## 任务4: 技术视图完善前置条件步骤信息

* [x] 子任务 4.1: 在 `TestCaseViewService.get_technical_view()` 中完善前置条件步骤信息

  * 展示每个步骤的定位器类型（css/xpath/mcp）

  * 展示定位器值

  * 展示执行状态

* [x] 子任务 4.2: 前端 `CaseDetail.vue` 技术视图中展示完整的前置条件步骤信息

## 任务5: 代码评审与自测

* [x] 子任务 5.1: 审查新增代码是否符合项目规范

* [x] 子任务 5.2: 编写并执行单元测试验证功能

# Task Dependencies

* \[任务2] 依赖于 \[任务1]

* \[任务3] 依赖于 \[任务1]

* \[任务4] 依赖于 \[任务1]

* \[任务5] 依赖于 \[任务1, 任务2, 任务3, 任务4]

