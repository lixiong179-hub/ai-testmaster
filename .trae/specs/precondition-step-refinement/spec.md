# 测试用例前置条件细化 Spec

## Why
目前项目的前置操作仅停留在打开浏览器、登录访问地址进入首页，不会像测试用例中的前置条件描述那样进入目标页面。虽然测试用例的前置条件从业务视角分析是符合要求的，但从技术视角来看，前置条件没有被细化为可执行步骤，导致每条用例无法单独执行，必须考虑用例执行顺序。

## What Changes
- 在技术视图中新增**前置条件步骤**区域，可将用例的前置条件文本解析/转换为可执行步骤
- 新增**前置条件步骤模型**，支持将前置条件细化为与测试步骤相同结构的可执行步骤
- 扩展**测试执行引擎**，在执行用例前先执行该用例的前置条件步骤
- 提供**前置条件编辑界面**，支持人工编辑前置条件步骤
- 提供**AI解析前置条件**功能，自动将前置条件文本转换为可执行步骤

## Impact
- Affected specs: 测试用例生成、测试用例执行、批量元素定位补充
- Affected code:
  - `app/models/test_case.py` - 新增前置条件步骤模型
  - `app/schemas/test_case.py` - 新增前置条件步骤Schema
  - `app/api/v1/endpoints/test_case.py` - 新增前置条件步骤CRUD接口
  - `app/services/test_execution_engine_v2.py` - 集成前置条件步骤执行
  - `app/services/batch_locator_service.py` - 集成前置条件步骤执行
  - `app/utils/ai_client.py` - 新增前置条件AI解析功能
  - 前端 `src/views/case/CaseDetail.vue` - 新增前置条件步骤编辑区

## ADDED Requirements

### Requirement: 前置条件步骤模型
系统 SHALL 提供前置条件步骤模型，与测试步骤结构一致，支持以下字段：
- `precondition_step_id` - 前置条件步骤ID
- `test_case_id` - 关联的测试用例ID
- `step_number` - 步骤序号
- `action` - 操作描述
- `action_type` - 操作类型（click/input/navigate等）
- `input_value` - 输入值
- `target_element` - 目标元素描述
- `expected_result` - 预期结果
- `has_locator` - 是否已记录元素定位
- `locator_status` - 定位状态

### Requirement: 前置条件步骤编辑界面
系统 SHALL 在技术视图中提供前置条件步骤编辑界面，支持：
- 查看前置条件文本
- 查看/编辑前置条件步骤列表
- 手动添加/删除/编辑前置条件步骤
- 点击「AI解析」按钮，自动将前置条件文本转换为步骤
- 点击「批量补充定位」按钮，为前置条件步骤补充元素定位

#### Scenario: AI解析前置条件
- **WHEN** 用户点击「AI解析」按钮
- **THEN** 系统调用AI模型解析前置条件文本，生成对应的前置条件步骤列表
- **AND** 生成的步骤自动填充到前置条件步骤编辑区

### Requirement: 测试执行引擎集成前置条件步骤
系统 SHALL 在执行测试用例前，先执行该用例的前置条件步骤：
- 如果用例有前置条件步骤，则优先执行
- 前置条件步骤执行失败时，整个用例执行失败
- 前置条件步骤的执行结果单独记录

#### Scenario: 执行用例带前置条件步骤
- **WHEN** 用户执行测试用例
- **AND** 该用例有前置条件步骤
- **THEN** 系统先执行前置条件步骤
- **AND** 前置条件步骤执行成功后，再执行用例的测试步骤

### Requirement: 批量定位补充集成前置条件步骤
系统 SHALL 在批量补充定位时，先执行前置条件步骤，再为测试步骤补充定位：
- 如果用例有前置条件步骤，则优先执行
- 前置条件步骤也需要补充元素定位

#### Scenario: 批量补充定位带前置条件步骤
- **WHEN** 用户为用例批量补充定位
- **AND** 该用例有前置条件步骤
- **THEN** 系统先执行前置条件步骤（补充定位+执行）
- **AND** 再执行测试步骤的定位补充

## MODIFIED Requirements
无

## REMOVED Requirements
无
