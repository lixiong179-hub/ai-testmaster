# 测试用例类型区分 Spec

## Why
AI生成的测试用例没有正确区分用例类型，导致：
1. 所有用例都被当作"功能测试"，没有区分UI自动化、手工测试、接口自动化
2. 执行引擎尝试执行所有用例，包括手工测试用例，导致执行失败
3. 缺少正确的用例分类标签，无法正确管理和筛选不同类型的测试用例

## What Changes
- **修复AI生成用例的类型设置** — AI生成时正确设置 `case_type` 和 `test_category`
- **修复执行引擎的用例类型检查** — 只执行自动化测试类型的用例（ui_automation、api_automation），跳过手工测试
- **修复保存用例时的字段映射** — 正确保存 `case_type` 和 `test_category` 字段
- **修复前端显示的用例类型标签** — 正确显示用例的类型和分类

## Impact
- Affected specs: ai-test-case-executability-optimization
- Affected code:
  - `app/utils/ai_client.py` — AI生成用例时设置类型
  - `app/api/v1/endpoints/test_case.py` — 保存用例时的字段映射
  - `app/services/test_execution_engine_v2.py` — 执行时检查用例类型
  - `app/models/test_case.py` — 已有的字段定义无需修改

## ADDED Requirements

### Requirement: AI生成用例时正确设置类型
系统 SHALL 在AI生成测试用例时，正确设置用例的类型和分类。

#### Scenario: 生成UI自动化测试用例
- **GIVEN** 测试点描述为"点击登录按钮"、"在输入框中输入"等UI操作
- **WHEN** AI生成测试用例
- **THEN** `case_type` 设置为 "UI"
- **AND** `test_category` 设置为 "ui_automation"

#### Scenario: 生成接口测试用例
- **GIVEN** 测试点描述为"调用接口"、"返回JSON"等接口操作
- **WHEN** AI生成测试用例
- **THEN** `case_type` 设置为 "API"
- **AND** `test_category` 设置为 "api_automation"

#### Scenario: 生成手工测试用例
- **GIVEN** 测试点描述为"人工审核"、"查看效果"等手工操作
- **WHEN** AI生成测试用例
- **THEN** `case_type` 设置为 "UI"
- **AND** `test_category` 设置为 "manual"

### Requirement: 执行引擎检查用例类型
系统 SHALL 在执行测试任务时，检查每个用例的类型，只执行自动化测试用例。

#### Scenario: 执行UI自动化测试用例
- **GIVEN** 测试用例 `test_category` 为 "ui_automation"
- **WHEN** 执行引擎处理该用例
- **THEN** 正常执行该用例

#### Scenario: 执行接口自动化测试用例
- **GIVEN** 测试用例 `test_category` 为 "api_automation"
- **WHEN** 执行引擎处理该用例
- **THEN** 正常执行该用例（注：当前只有UI自动化引擎，接口测试可后续实现）

#### Scenario: 跳过手工测试用例
- **GIVEN** 测试用例 `test_category` 为 "manual" 或为空
- **WHEN** 执行引擎处理该用例
- **THEN** 跳过该用例，标记为"手工测试，跳过执行"
- **AND** 不影响任务的总体状态，该用例不计入成功/失败统计

### Requirement: 保存用例时正确映射类型字段
系统 SHALL 在保存测试用例时，正确保存 `case_type` 和 `test_category` 字段。

#### Scenario: 保存新创建的用例
- **GIVEN** 前端创建用例时传入 `case_type` 和 `test_category`
- **WHEN** 后端保存该用例
- **THEN** `TestCase.case_type` 正确设置
- **AND** `TestCase.test_category` 正确设置

#### Scenario: 更新用例时的类型字段
- **GIVEN** 前端更新用例时传入新的 `case_type` 和 `test_category`
- **WHEN** 后端更新该用例
- **THEN** `TestCase.case_type` 正确更新
- **AND** `TestCase.test_category` 正确更新

## MODIFIED Requirements

### Requirement: 用例类型字段值规范
原实现：`case_type` 取值为 "API/UI/接口"，`test_category` 取值为 ui_automation/manual/api_automation

修改后：
- `case_type` 标准化为："UI"、"API"、"功能"
- `test_category` 标准化为："ui_automation"、"manual"、"api_automation"
- 保持向后兼容，旧值仍可使用

## REMOVED Requirements
无
