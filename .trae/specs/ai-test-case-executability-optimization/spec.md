# AI生成测试用例可执行性优化 Spec

## Why
AI生成的测试用例保存后无法被测试执行引擎可靠执行。系统已有业务视图/技术视图双视图架构，但AI生成时只填充了业务视图的自然语言描述，未生成技术视图所需的结构化操作数据（操作类型、输入参数、预期结果），且数据保存链路中 `param` 与 `expected_result` 语义混乱，导致执行引擎拿到的是输入值而非验证条件。

## What Changes
- **修复TestStep数据模型映射** — 后端保存时正确区分 `param`（输入参数）和 `expected_result`（预期结果），消除语义混乱
- **优化AI生成prompt** — 让AI在生成业务视图描述的同时，生成技术视图所需的结构化数据（action_type、input_value、expected_result）
- **修复前端保存逻辑** — 正确传递结构化的步骤数据，不再将预期结果混入param字段
- **修复执行引擎数据读取** — 执行引擎从技术视图读取结构化操作数据，不再依赖NLP解析自然语言
- **统一任务状态定义** — 消除TestTask模型/执行引擎/前端之间的状态值歧义

## Impact
- Affected specs: test-case-generation-execution, ui-automation-enhancement
- Affected code:
  - `app/utils/ai_client.py` — AI生成prompt和结果标准化
  - `app/api/v1/endpoints/test_case.py` — 创建用例时的步骤数据映射
  - `app/schemas/test_case.py` — TestCaseStep schema增加结构化字段
  - `src/views/case/ai-generate.vue` — 前端保存逻辑
  - `app/services/test_execution_engine_v2.py` — 执行引擎步骤解析
  - `app/models/test_task.py` — 任务状态定义统一

## ADDED Requirements

### Requirement: AI生成结构化步骤数据
系统 SHALL 在AI生成测试用例时，同时生成业务视图和技术视图所需的数据。

#### Scenario: 生成包含结构化操作的测试步骤
- **GIVEN** AI为某个测试点生成测试用例
- **WHEN** 生成步骤数据时
- **THEN** 每个步骤包含以下结构化字段：
  - `action`: 业务操作描述（自然语言，如"在用户名输入框中输入有效的用户名"）
  - `action_type`: 操作类型枚举（click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress）
  - `input_value`: 输入值（仅input类型，如"test_user"；非输入操作为空）
  - `expected_result`: 预期结果描述（验证条件，如"输入框显示test_user"）
  - `target_element`: 目标元素描述（如"用户名输入框"）
- **AND** `action_type` 由AI根据操作语义自动判断，无需NLP解析
- **AND** `input_value` 与 `expected_result` 语义严格分离

#### Scenario: 保持业务视图兼容性
- **GIVEN** AI生成了结构化步骤数据
- **WHEN** 在业务视图中展示
- **THEN** 仍然显示自然语言的 `action` 和 `expected_result`
- **AND** 结构化字段（action_type、input_value、target_element）仅在技术视图中显示

### Requirement: TestStep数据模型正确映射
系统 SHALL 在保存测试用例时正确区分输入参数和预期结果。

#### Scenario: 保存输入类型步骤
- **GIVEN** AI生成的步骤 action_type 为 "input"，input_value 为 "test_user"
- **WHEN** 保存到 TestStep 表
- **THEN** `TestStep.action` = 业务操作描述
- **AND** `TestStep.expected_result` = 预期结果（验证条件）
- **AND** `TestStep` 新增字段或复用现有字段存储 action_type 和 input_value

#### Scenario: 保存验证类型步骤
- **GIVEN** AI生成的步骤 action_type 为 "verify"
- **WHEN** 保存到 TestStep 表
- **THEN** `TestStep.action` = 验证操作描述
- **AND** `TestStep.expected_result` = 预期结果（验证条件）
- **AND** input_value 为空

### Requirement: 执行引擎使用结构化数据
系统 SHALL 在执行测试用例时优先使用技术视图的结构化数据，而非NLP解析自然语言。

#### Scenario: 使用action_type直接确定操作类型
- **GIVEN** TestStep 存储了 action_type = "input"
- **WHEN** 执行引擎处理该步骤
- **THEN** 直接使用 action_type 确定操作类型为 INPUT
- **AND** 不再通过关键词匹配（"输入"/"点击"等）推断操作类型
- **AND** 使用 input_value 作为输入值，而非从自然语言中提取

#### Scenario: 兼容无action_type的历史步骤
- **GIVEN** 历史TestStep没有action_type字段
- **WHEN** 执行引擎处理该步骤
- **THEN** 降级使用现有的NLP关键词匹配逻辑
- **AND** 功能不受影响

### Requirement: 统一任务状态定义
系统 SHALL 在所有模块中使用一致的任务状态定义。

#### Scenario: 任务状态值统一
- **GIVEN** 测试任务在不同模块中使用状态值
- **WHEN** 读取或更新任务状态
- **THEN** 使用以下统一定义：
  - 0: 等待执行（pending）
  - 1: 执行中（running）
  - 2: 执行完成-全部通过（completed）
  - 3: 执行完成-有失败（failed）
  - 4: 已停止（stopped）
- **AND** TestTask模型、执行引擎、前端使用相同的值和语义

## MODIFIED Requirements

### Requirement: TestCaseStep Schema扩展
原实现：TestCaseStep 仅有 step、action、param 三个字段

修改后：
- 保留 `step`、`action`、`param` 字段（向后兼容）
- 新增 `action_type` 字段：操作类型枚举
- 新增 `input_value` 字段：输入值（仅input类型）
- 新增 `target_element` 字段：目标元素描述
- `expected_result` 字段语义明确为"预期结果/验证条件"
- `param` 字段保留但标记为deprecated，新代码使用 `input_value`

### Requirement: AI生成prompt优化
原实现：prompt要求AI生成自然语言的steps和expected_results

修改后：
- prompt要求AI同时生成业务描述和技术结构化数据
- steps中每个步骤包含 action_type、input_value、target_element
- expected_results 严格为验证条件，不包含输入值

## REMOVED Requirements
无
