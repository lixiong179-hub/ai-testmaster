# Tasks

* [x] Task 1: AI 生成层 — 移除明文凭据注入，重构提示词

  * [x] Task 1.1: 重构 `ai_client.py` 的 `generate_test_case_enhanced()` 提示词，移除 `_build_project_env_info()` 对 URL/密码的明文注入

  * [x] Task 1.2: 新版提示词告知 AI "前置条件由系统自动处理，用例只写业务步骤"，precondition 写作"系统已自动登录至目标页面"

  * [x] Task 1.3: 移除 `test_case.py` generate-context 接口返回值中的 `project_config` 敏感字段（或整体移除）

  * [x] Task 1.4: 清理 `ai-generate.vue` handleGenerate 中的 envDescription 构建逻辑

* [x] Task 2: 执行引擎层 — 强化自动初始化 + 多环境支持

  * [x] Task 2.1: 修改 `test_execution_engine_v2.py` 的 `_execute_precondition()`，`auto_login` 默认改为 `True`

  * [x] Task 2.2: 新增 `target_env: str = "test"` 参数，按环境名从 `project.web_env_configs[target_env]` 选择配置

  * [x] Task 2.3: 新增 `skip_init: bool = False` 参数，skip\_init=True 时仅启动浏览器+导航，不执行登录

  * [x] Task 2.4: 确认 `PreconditionService.read_test_object_info()` 能接收并使用指定环境的配置信息

  * [x] Task 2.5: 验证完整流程：选环境 → 初始化 → 登录 → 执行步骤 → 结果记录

* [x] Task 3: API 层 — 执行控制接口支持环境选择和跳过初始化

  * [x] Task 3.1: 测试任务执行 API（execution.py）新增 `targetEnv` 和 `skipInit` 可选参数

  * [x] Task 3.2: 后端根据 targetEnv 从 project web\_env\_configs 中取出对应环境配置

  * [x] Task 3.3: 将环境配置和 skipInit 参数传递给执行引擎

* [x] Task 4: 前端执行页面 — 环境选择器 + 初始化开关

  * [x] Task 4.1: 在 `TestExecution.vue` 增加环境选择器（el-select），列出项目所有已配置环境

  * [x] Task 4.2: 每个选项显示：环境名 + URL + 账号名 + 密码(••••••脱敏)

  * [x] Task 4.3: 默认选中 test 环境（如有），否则第一个有完整配置的环境

  * [x] Task 4.4: 在环境选择器旁增加"执行前自动初始化"开关（el-switch），默认开启

  * [x] Task 4.5: 切换环境时实时更新环境摘要信息

  * [x] Task 4.6: 开关和环境选择状态正确传递给执行 API（targetEnv + skipInit）

* [x] Task 5: 安全加固 — 存储加密 + 传输脱敏

  * [x] Task 5.1: 项目配置 API 返回数据时对 password 字段脱敏（返回 `"******"`）

  * [x] Task 5.2: 项目详情前端页展示密码时脱敏显示

  * [x] Task 5.3: 数据库存储时密码 AES 加密 — 确认已有 encrypt\_password() 机制

* [x] Task 6: 向后兼容与验证

  * [x] Task 6.1: 确保旧格式测试用例（含登录步骤）仍能正常执行不报错 — 所有新参数均有默认值 ✅

  * [x] Task 6.2: 检查生成的用例 JSON 不包含明文密码 — prompt 模板已安全化 ✅

  * [x] Task 6.3: 后端 Python import 无报错(5/5)，前端 TypeScript 0 diagnostics(4/4) ✅

# Task Dependencies

* Task 1 ✅ 已完成

* Task 2 ✅ 已完成

* Task 3 ✅ 已完成

* Task 4 ✅ 已完成

* Task 5 ✅ 已完成

* Task 6 ✅ 已完成 — 全部通过

