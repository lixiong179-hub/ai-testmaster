# 测试用例类型区分 - 实施计划

## [x] Task 1: 修改AI生成用例，正确设置 case_type 和 test_category
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 `_normalize_new_format` 函数，根据步骤内容推断用例类型
  - 修改 `_normalize_old_format` 函数，同样推断用例类型
  - 如果步骤包含 UI 操作（点击、输入、导航）→ case_type="UI"，test_category="ui_automation"
  - 如果步骤包含 API/接口操作 → case_type="API"，test_category="api_automation"
  - 如果步骤包含手工操作（人工、查看、检查等）→ case_type="UI"，test_category="manual"
  - 同时在返回结果中添加 `test_category` 字段
- **Acceptance Criteria Addressed**: 所有关于AI生成用例类型的AC
- **Test Requirements**:
  - `programmatic` TR-1.1: 生成的用例包含正确的 case_type 和 test_category 字段
  - `human-judgement` TR-1.2: 用例类型根据测试点内容合理推断
- **Notes**: 优先通过 prompt 让AI自己判断，如果AI没有返回，再通过关键词推断

## [x] Task 2: 修改后端保存用例，正确保存 case_type 和 test_category
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 修改 `create_test_case` 函数，从请求中读取 `test_category` 并保存
  - 修改 `ai_generate_test_case` 函数，从AI生成结果中读取 `test_category` 并保存
  - 修改 `update_test_case` 函数，支持更新 `case_type` 和 `test_category`
- **Acceptance Criteria Addressed**: 所有关于保存用例类型的AC
- **Test Requirements**:
  - `programmatic` TR-2.1: 数据库中 test_cases 表的 case_type 和 test_category 正确保存
  - `programmatic` TR-2.2: API响应中返回的用例包含正确的 case_type 和 test_category
- **Notes**: 需要修改 TestCaseCreate/TestCaseUpdate schema 以支持 test_category 字段

## [x] Task 3: 修改执行引擎，检查用例类型并跳过手工测试
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 修改 `_execute_single_case` 方法，在执行前检查用例类型
  - 如果 test_category == "ui_automation" → 正常执行
  - 如果 test_category == "api_automation" → 跳过（记录日志，当前只支持UI自动化）
  - 如果 test_category == "manual" 或为空 → 跳过，标记为"手工测试，跳过执行"
  - 跳过的用例不计入 success_count/fail_count，但要记录到测试结果中
- **Acceptance Criteria Addressed**: 所有关于执行引擎检查用例类型的AC
- **Test Requirements**:
  - `programmatic` TR-3.1: 手工测试用例被正确跳过，不影响任务执行
  - `programmatic` TR-3.2: 跳过的用例在测试结果中有正确的标记和备注
- **Notes**: 需要在 TestCaseExecution 中添加跳过的用例的状态和备注

## [x] Task 4: 修改 schema，添加 test_category 字段支持
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改 `app/schemas/test_case.py` 中的 TestCaseBase/TestCaseCreate/TestCaseUpdate，添加 test_category 字段
  - test_category 为 Optional[str]，描述说明取值范围（ui_automation/manual/api_automation）
- **Acceptance Criteria Addressed**: AC-1（后端支持 test_category 字段）
- **Test Requirements**:
  - `programmatic` TR-4.1: TestCaseCreate/TestCaseUpdate 包含 test_category 字段
  - `programmatic` TR-4.2: test_category 字段有正确的描述和约束
- **Notes**: 保持向后兼容，现有字段不变

## [x] Task 5: 修复前端，正确显示和保存用例类型
- **Priority**: P1
- **Depends On**: Task 1, Task 4
- **Description**: 
  - 修改前端用例展示页面，正确显示 case_type 和 test_category
  - 修改前端用例创建/编辑页面，支持选择用例类型
  - 修改前端保存用例时，正确传递 case_type 和 test_category
- **Acceptance Criteria Addressed**: AC-2（前端支持用例类型）
- **Test Requirements**:
  - `human-judgement` TR-5.1: 前端页面正确显示用例类型标签
  - `human-judgement` TR-5.2: 前端页面可以选择和编辑用例类型
- **Notes**: 优先检查是否已有相关代码

# Task Dependencies
- Task 2, Task 4 依赖 Task 1
- Task 3 依赖 Task 2
- Task 5 依赖 Task 1 和 Task 4
