# Checklist

## Task 1: AI 生成层 — 移除明文凭据注入
- [x] Task 1.1: `ai_client.py` 的 `_build_project_env_info()` 不再将 URL/username/password 明文注入 AI prompt
- [x] Task 1.2: AI 提示词中明确说明"前置条件由系统自动处理"，生成的用例 precondition 不含登录步骤
- [x] Task 1.3: `test_case.py` generate-context 接口不再返回 project_config 中的敏感字段
- [x] Task 1.4: `ai-generate.vue` handleGenerate 中移除 envDescription 构建逻辑

## Task 2: 执行引擎层 — 强化自动初始化 + 多环境
- [x] Task 2.1: `test_execution_engine_v2.py` 的 `_execute_precondition()` 默认 auto_login=True
- [x] Task 2.2: 执行引擎支持 target_env 参数，按环境名从 web_env_configs 选择配置
- [x] Task 2.3: 执行引擎支持 skip_init 参数，skip_init=True 时跳过登录
- [x] Task 2.4: PreconditionService 正确接收并使用指定环境的配置信息
- [x] Task 2.5: 执行引擎完整流程可运行（选环境→初始化→登录→执行步骤→记录结果）

## Task 3: API 层 — 执行控制接口
- [x] Task 3.1: 测试任务执行 API 支持 target_env 和 skip_init 参数
- [x] Task 3.2: target_env 正确用于选择 web_env_configs 中的对应环境配置
- [x] Task 3.3: skip_init 正确传递到执行引擎

## Task 4: 前端执行页面 — 环境选择 + 初始化开关
- [x] Task 4.1: TestExecution.vue 显示环境选择器（el-select），列出所有已配置环境
- [x] Task 4.2: 每个选项显示：名称 + URL + 账号 + 密码(••••••脱敏)
- [x] Task 4.3: 默认选中 test 环境（如有），否则第一个有完整配置的环境
- [x] Task 4.4: 显示"执行前自动初始化"开关，默认开启
- [x] Task 4.5: 切换环境时摘要信息实时更新
- [x] Task 4.6: 开关和环境选择状态正确影响执行请求参数

## Task 5: 安全加固
- [x] Task 5.1: 项目配置 API 返回数据中 password 字段已脱敏（"******"）
- [x] Task 5.2: 项目详情前端页密码展示已脱敏
- [x] Task 5.3: 数据库密码加密存储 — 确认已有 AES-256 encrypt_password() 机制

## Task 6: 验证与兼容性
- [x] Task 6.1: 旧格式测试用例执行不报错 — 所有新参数有默认值
- [x] Task 6.2: AI prompt 和 env_info 均不含明文 URL/密码/账号
- [x] Task 6.3: 后端 Python 5模块 import 全通过，前端 TypeScript 4文件 0 diagnostics

## 整体验证
- [x] 安全性：数据库(API加密存储) / API(返回"******") / 前端(脱敏展示) 三层均无明文密码暴露
- [x] 多环境：用户可通过 UI 在 test/staging/prod 间切换执行目标
- [x] 可用性：用户可通过 UI 开关控制是否自动初始化
- [x] 合理性：从用户角度看整个流程自然顺畅
