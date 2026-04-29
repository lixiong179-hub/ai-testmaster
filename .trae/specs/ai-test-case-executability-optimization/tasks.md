# Tasks

- [x] Task 1: 扩展TestCaseStep Schema，增加结构化字段
  - [x] SubTask 1.1: 在 `app/schemas/test_case.py` 的 TestCaseStep 中新增 action_type、input_value、target_element 字段
  - [x] SubTask 1.2: 确保 action_type 使用枚举值（click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress）
  - [x] SubTask 1.3: 保持向后兼容，旧字段 step/action/param 仍可使用

- [x] Task 2: 优化AI生成prompt，生成结构化步骤数据
  - [x] SubTask 2.1: 修改 `app/utils/ai_client.py` 中的prompt模板，要求AI返回 action_type、input_value、target_element
  - [x] SubTask 2.2: 修改 `_normalize_new_format` 函数，正确映射结构化字段
  - [x] SubTask 2.3: 修改 `_normalize_old_format` 函数，兼容旧格式并补充默认 action_type
  - [x] SubTask 2.4: 确保 expected_result 严格为验证条件，不包含输入值

- [x] Task 3: 修复后端保存逻辑，正确映射param和expected_result
  - [x] SubTask 3.1: 修改 `app/api/v1/endpoints/test_case.py` 的 create_test_case，TestStep.expected_result 使用 step_data.expected_result 而非 step_data.param
  - [x] SubTask 3.2: 在 TestStep 模型中新增 action_type、input_value、target_element 列（数据库迁移）
  - [x] SubTask 3.3: 保存时将 action_type、input_value、target_element 写入 TestStep
  - [x] SubTask 3.4: steps_json 中同步保存结构化字段

- [x] Task 4: 修复前端保存逻辑，正确传递结构化步骤数据
  - [x] SubTask 4.1: 修改 `src/views/case/ai-generate.vue` 的 handleSaveCase，传递 action_type、input_value、target_element
  - [x] SubTask 4.2: 修改 saveAllCases 批量保存逻辑，同样传递结构化字段
  - [x] SubTask 4.3: param 字段映射为 input_value（而非 expected_result），保持向后兼容

- [x] Task 5: 修复执行引擎，优先使用结构化数据
  - [x] SubTask 5.1: 修改 `app/services/test_execution_engine_v2.py` 的 _execute_step，优先读取 TestStep.action_type
  - [x] SubTask 5.2: 当 action_type 存在时，直接使用枚举值确定操作类型，跳过NLP解析
  - [x] SubTask 5.3: 当 action_type 不存在时（历史数据），降级使用现有的 _parse_step_action 关键词匹配
  - [x] SubTask 5.4: input 类型步骤使用 input_value 作为输入值，而非从自然语言提取

- [x] Task 6: 统一任务状态定义
  - [x] SubTask 6.1: 在 `app/models/test_task.py` 中添加状态常量类，统一定义 0=等待/1=执行中/2=完成-通过/3=完成-失败/4=已停止
  - [x] SubTask 6.2: 修改 `app/services/test_execution_engine_v2.py` 中的状态值，使用统一常量
  - [x] SubTask 6.3: 修改 `src/views/task/TaskList.vue` 中的状态筛选和显示，与后端定义对齐

# Task Dependencies
- [Task 2] depends on [Task 1] — prompt优化需要先确定Schema字段
- [Task 3] depends on [Task 1] — 后端保存逻辑依赖Schema定义
- [Task 4] depends on [Task 1] and [Task 2] — 前端需要传递AI生成的结构化字段
- [Task 5] depends on [Task 3] — 执行引擎需要后端已正确保存结构化数据
- [Task 6] independent — 可并行执行
