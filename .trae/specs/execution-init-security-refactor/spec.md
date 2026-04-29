# 测试执行初始化流程重构 Spec

## Why

当前系统存在**安全漏洞**和**架构设计缺陷**：

1. **安全隐患**：AI 生成测试用例时，将项目配置的登录账号密码（明文）直接嵌入到测试用例的步骤描述和测试数据中。这些用例存储在数据库中、展示在前端页面，任何有权限的用户都能看到明文密码。
2. **职责混淆**：登录/初始化是**执行时**的操作，不应该作为**用例内容**的一部分。测试用例应该描述"测什么"，而不是"怎么准备环境"。
3. **执行引擎已有基础但未充分利用**：`PreconditionService` 已支持 `auto_login` 参数（`execute_web_precondition(auto_login=True)`），但执行引擎 `test_execution_engine_v2.py:343` 调用时硬编码了 `auto_login=False`，且缺少用户控制入口。
4. **用户视角缺失 — 无环境选择**：项目支持多环境配置（test/staging/prod），但执行测试时无法选择目标环境。用户应该能在执行时动态选择"在哪个环境上跑这批用例"，而不是写死在项目配置里。
5. **流程不完整**：从用户实际使用场景看，整个流程应该是：创建项目(配多环境) → 提取测试点 → 生成用例 → **执行用例(选环境+自动初始化+可选跳过)** → 查看报告。当前缺少"执行时可选择环境和控制是否跳过初始化"的能力。

## What Changes

### 核心原则
- **密码不在用例中明文出现**：测试用例的 precondition/steps/test_data 中不包含任何明文账号密码
- **初始化是执行时行为**：每次执行测试用例时，系统自动从项目配置中读取环境信息并执行初始化（打开浏览器→导航到URL→自动登录）
- **用户可控**：用户在执行测试任务时可以选择"跳过初始化"（用于测试登录页面的场景）
- **安全存储与传输**：数据库中的密码应加密存储；API 返回时脱敏；前端不展示明文

### 具体改动清单

#### A. AI 生成层（移除明文凭据）
- **`app/utils/ai_client.py`**：移除 `_build_project_env_info()` 中将 URL/账号/密码注入 prompt 的逻辑
- **`app/utils/ai_client.py`**：AI 提示词改为告知 AI "前置条件由系统在执行时自动处理，无需在步骤中描述登录操作"
- **`app/api/v1/endpoints/test_case.py`**：`generate-context` 接口不再返回 `project_config` 中的敏感字段（或仅返回脱敏信息）
- **`src/views/case/ai-generate.vue`**：`handleGenerate` 不再从 project_config 构建 envDescription 注入 description

#### B. 执行引擎层（强化自动初始化 + 多环境支持）
- **`app/services/test_execution_engine_v2.py`**：
  - `_execute_precondition()` 中 `auto_login=False` 改为默认 `auto_login=True`
  - 新增参数 `target_env: str = "test"`，根据环境名从项目 web_env_configs 选择对应配置
  - 新增参数 `skip_init: bool = False`，支持用户选择跳过初始化
  - 当 skip_init=True 时，仅启动浏览器和导航到目标环境的 URL，不执行登录
  - 环境选择逻辑：`env_config = project.web_env_configs.get(target_env, {})`
- **`app/services/precondition_service.py`**：确认 `read_test_object_info()` 从 Project.web_env_configs 正确读取环境信息

#### C. API 层（执行控制接口）
- **`app/api/v1/endpoints/test_task.py`**（或对应执行 API）：
  - 执行测试任务的接口新增参数：
    - `target_env: str = "test"` — 目标环境名（test/staging/prod），用于从 web_env_configs 选择对应配置
    - `skip_init: bool = False` — 是否跳过初始化
  - 后端根据 `target_env` 从项目的 `web_env_configs` 中取出对应环境的 URL/username/password
  - 将环境信息和 skip_init 传递给执行引擎

#### D. 前端执行页面（用户控制入口）
- **`src/views/execution/TestExecution.vue`**：
  - 在"开始执行"按钮前增加**环境选择器**（el-select/radio-group），列出项目配置的所有可用环境（test/staging/prod）
    - 每个选项显示：环境名 + URL（密码脱敏）
    - 默认选中 `test` 环境（如有），否则第一个有配置的环境
  - 在环境选择器旁增加**"执行前自动初始化"**开关，默认开启
  - 用户关闭此开关时，传递 `skip_init=true` 给后端
  - 环境变更时自动更新显示的环境摘要信息

#### E. 安全加固
- **数据库层**：Project.web_env_configs 中的 password 字段考虑加密存储（AES-256 或类似）
- **API 层**：返回项目配置时 password 字段脱敏为 `"******"`
- **前端层**：项目详情页展示密码时脱敏显示

### **BREAKING** 变更
- AI 生成的测试用例内容格式会变化（不再包含具体 URL 和登录步骤的明文凭据）
- 执行引擎默认行为变化：从 `auto_login=False` 改为 `auto_login=True`

## Impact
- **Affected specs**: test-case-generation-execution（本 spec 是其增强）
- **Affected code**:
  - `app/utils/ai_client.py` — AI 提示词重构
  - `app/api/v1/endpoints/test_case.py` — generate-context 接口调整
  - `app/services/test_execution_engine_v2.py` — 执行引擎初始化逻辑
  - `app/services/precondition_service.py` — 前置条件服务（可能微调）
  - `src/views/case/ai-generate.vue` — 移除 envDescription 注入
  - `src/views/execution/TestExecution.vue` — 新增初始化开关 UI
  - `app/models/project.py` — 可能需要加密字段
  - 项目相关 API endpoint — 返回数据脱敏

## ADDED Requirements

### Requirement: 测试执行自动初始化
The system SHALL 在每次执行测试用例前，自动使用项目配置的环境信息完成初始化操作。用户可指定目标环境。

#### Scenario: 默认自动初始化（选择测试环境）
- **WHEN** 用户创建测试任务，选择"测试环境"作为目标，开启"自动初始化"，点击"开始执行"
- **THEN** 系统自动执行以下初始化流程：
  1. 从项目的 `web_env_configs.test` 读取该环境的地址、账号、密码
  2. 启动真实浏览器
  3. 导航到**测试环境**的配置地址
  4. 使用**测试环境**配置的账号密码自动完成登录
  5. 初始化完成后开始执行测试用例步骤
- **AND** 测试用例本身不再包含登录步骤

#### Scenario: 切换到正式环境执行
- **WHEN** 用户在执行页面将目标环境从"测试"切换为"正式"(prod)
- **THEN** 系统使用 `web_env_configs.prod` 中的 URL/账号/密码 进行初始化
- **AND** 浏览器导航到**正式环境**地址
- **And**: 用同一批测试用例在不同环境上执行，验证多环境一致性

#### Scenario: 跳过初始化（测试登录页面）
- **WHEN** 用户关闭"自动初始化"开关后点击"开始执行"
- **THEN** 系统启动浏览器并导航到所选环境的测试地址，但**不执行登录**
- **AND** 直接开始执行测试用例步骤（适用于测试登录功能本身的场景）

#### Scenario: 安全性 - 用例不含明文密码
- **WHEN** AI 生成测试用例
- **THEN** 生成的用例 precondition、steps、test_data 中**不包含任何明文账号密码**
- **AND** 不包含具体的测试环境 URL（用占位符如 `{system_url}` 或通用描述代替）
- **AND** 前置条件描述为"系统已自动登录"而非具体登录步骤

### Requirement: 执行时环境选择
The system SHALL 允许用户在执行测试任务时动态选择目标执行环境。

#### Scenario: 环境选择器展示可用环境
- **WHEN** 用户进入测试执行页面且项目配置了多个环境
- **THEN** 页面显示环境选择器，列出所有已配置的环境（如：测试 / 灰度 / 正式）
- **AND** 每个选项显示：环境名称 + 该环境的 URL + 账号名 + 密码(••••••)
- **AND** 默认选中 "test" 环境（如有），否则选中第一个有完整配置的环境

#### Scenario: 环境切换更新摘要信息
- **WHEN** 用户切换目标环境
- **THEN** 页面的环境摘要信息实时更新为新选择的 URL 和账号
- **AND** 执行请求中的 target_env 参数同步更新

### Requirement: 环境配置安全管理
The system SHALL 对项目中的敏感配置信息进行安全保护。

#### Scenario: 数据库加密存储
- **WHEN** 用户在项目中配置登录密码
- **THEN** 密码以加密形式存储在数据库中（非明文）

#### Scenario: API 返回脱敏
- **WHEN** 前端请求项目配置信息
- **THEN** API 返回的 password 字段为 `"******"` 或空字符串

#### Scenario: 前端脱敏展示
- **WHEN** 项目详情页展示环境配置
- **THEN** 密码显示为 `••••••` 或 `******`

### Requirement: 执行时用户控制初始化
The system SHALL 提供用户界面让用户控制是否在执行前自动初始化。

#### Scenario: 执行页面初始化开关
- **WHEN** 用户进入测试执行页面（TestExecution.vue）
- **THEN** 页面显示"执行前自动初始化"开关，默认开启
- **AND** 开关旁显示当前环境信息摘要（如：`测试环境 | http://xxx | admin / ••••••`）
- **AND** 用户可随时切换开关状态

## MODIFIED Requirements

### Requirement: AI 测试用例生成
原需求：生成包含详细步骤的可执行测试用例，步骤中使用真实 URL 和账号密码

修改后：
- 生成的测试用例**聚焦于业务测试步骤**
- 环境/登录相关的准备工作由系统在**执行时自动完成**
- AI 提示词明确告知："前置条件（打开浏览器、导航、登录）由测试框架自动执行，你只需编写业务测试步骤"
- 如果测试点本身涉及登录（如"验证登录成功后的跳转"），则 precondition 写作"系统已完成标准登录"

### Requirement: 测试执行引擎
原需求：支持 UI 自动化测试，执行前置条件时 auto_login=False

修改后：
- **默认 auto_login=True**：每次执行自动完成登录初始化
- 支持 `target_env` 参数：执行时动态选择目标环境（test/staging/prod），从 web_env_configs 读取对应配置
- 支持 `skip_init` 参数：当用户选择跳过时，只做浏览器启动+导航到目标环境 URL，不做登录
- 从项目配置动态读取环境信息，不在代码中硬编码

## REMOVED Requirements

### Requirement: AI 提示词注入明文环境信息
**原因**：安全隐患 + 职责混淆 — 凭据不应出现在用例内容和 AI prompt 中
**迁移**：改为执行时从项目配置读取，AI 只需关注业务测试逻辑

## Technical Specifications

### 数据流对比

```
【修改前 - 有安全隐患】
项目配置(web_env_configs) 
  → generate-context API 返回 project_config(含明文密码)
    → 前端构建 envDescription 注入 description
      → AI prompt 包含 "登录账号: admin, 密码: password123"
        → AI 生成步骤: "步骤1: 打开 http://xxx, 步骤2: 输入 admin/password123"
          → 用例存入数据库(含明文密码!) ❌
            → 前端展示用例(明文密码暴露!) ❌

【修改后 - 安全】
项目配置(web_env_configs, 密码加密存储)
  → generate-context API 返回脱敏/不返回敏感信息
    → AI prompt: "前置条件由系统自动处理，专注业务步骤"
      → AI 生成步骤: "步骤1: 验证首页加载, 步骤2: 点击菜单..."
        → 用例存入数据库(无任何密码) ✅
          → 用户执行用例
            → 执行引擎读取项目配置 → 自动初始化(解密密码) → 登录 → 执行步骤 ✅
```

### 执行初始化流程

```
用户选择目标环境(测试/灰度/正式) + 初始化开关状态
  ↓
后端接收请求 (target_env="test", skip_init=false)
  ↓
_execute_precondition(project_id, target_env, skip_init)
  ↓
env_config = project.web_env_configs[target_env]   // 按环境名选择配置
  ↓ {url, username, password}
PreconditionService.read_test_object_info(project, env_config)
  ↓
BrowserController.initialize()                        // 启动浏览器
  ↓
BrowserController.navigate(env_config.url)            // 导航到目标环境的URL
  ↓
skip_init == false?
  ├─ YES → _perform_login(username, password)        // AI识别表单+输入凭据+点击登录
  └─ NO  → 跳过登录                                  // 仅停留在目标环境页面
  ↓
开始执行测试用例步骤...
```

## Acceptance Criteria

### AC-1: 用例内容不含明文凭据
- **Given**: 项目配置了测试环境地址和登录账号密码
- **When**: AI 生成测试用例
- **Then**: 生成的用例 precondition/steps/test_data 中无明文密码
- **And**: 无具体测试环境 URL（或仅有域名不含路径）
- **Verification**: `programmatic` — 检查生成的用例 JSON 不包含 password 字段值

### AC-2: 执行时自动初始化
- **Given**: 项目配置了有效的测试环境和登录凭据
- **When**: 用户执行测试任务（未关闭初始化开关）
- **Then**: 系统自动完成：启动浏览器 → 导航 → 登录
- **And**: 登录成功后才开始执行第一个测试步骤
- **Verification**: `human-judgment` — 观察浏览器自动化执行过程

### AC-3: 可跳过初始化
- **Given**: 用户正在测试登录页面功能
- **When**: 用户关闭"自动初始化"开关并执行
- **Then**: 系统启动浏览器并导航到目标地址
- **But**: 不执行登录操作
- **And**: 测试步骤从导航后开始执行
- **Verification**: `human-judgment`

### AC-4: API 返回脱敏
- **Given**: 项目配置了登录密码
- **When**: 前端请求项目详情/配置
- **Then**: 返回数据中 password 字段为 `"******"` 或被移除
- **Verification**: `programmatic`

### AC-5: 前端执行页面有初始化控制
- **Given**: 用户进入测试执行页面 TestExecution.vue
- **When**: 页面加载完成
- **Then**: 显示"执行前自动初始化"开关，默认开启
- **And**: 显示环境摘要信息（URL 可见，密码脱敏）
- **Verification**: `visual`

### AC-6: 向后兼容
- **Given**: 已有的测试用例（可能包含旧格式的登录步骤）
- **When**: 执行这些旧用例
- **Then**: 系统仍能正常执行（忽略用例中的登录步骤，以执行引擎的初始化为准）
- **Or**: 至少不因格式变更而报错
- **Verification**: `programmatic`
