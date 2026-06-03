# AI TestMaster 项目需求规格说明书

> 版本: v1.0 | 日期: 2026-06-03 | 用途: 系统性测试验证依据

---

## 一、项目概述

### 1.1 项目定位

AI TestMaster 是一个 AI 驱动的自动化测试平台，核心能力包括：基于需求文档和 UI 原型自动生成测试用例、测试用例全生命周期管理、自动化测试执行与可视化、迭代回归测试流水线、用例质量评估与保鲜。平台面向 QA 工程师和测试管理者，提供从需求分析到测试报告的端到端解决方案。

### 1.2 技术架构

| 层级 | 技术栈 |
|------|--------|
| 前端 | Vue 3 + TypeScript + Pinia + Vue Router + Element Plus + ECharts |
| 后端 | FastAPI + SQLAlchemy + MySQL + Redis + APScheduler |
| AI | OpenAI 兼容接口（DeepSeek/GPT）+ 视觉模型 + MCP |
| 执行引擎 | Playwright（Web）+ ADB/Appium（移动端）+ Stagehand |
| 通信 | REST API + SSE（流式生成）+ WebSocket（实时执行/Pipeline） |

### 1.3 核心设计原则

- **多项目隔离**: 所有业务数据通过 `project_id` 实现租户级数据隔离
- **RBAC 权限体系**: User-Role-Permission 三层权限模型 + Pipeline 独立权限体系
- **JWT 认证**: OAuth2 密码模式，Bearer 令牌
- **生命周期状态机**: 用例、测试点、迭代等实体均有严格的生命周期状态管理
- **Pipeline 引擎**: 可编排的 Step 执行引擎，支持缓存、重试、降级、暂停

---

## 二、功能模块详细需求

---

### 模块 1: 认证与用户管理

#### 2.1.1 功能概述

提供用户注册、登录、权限管理、角色分配等基础认证与授权能力。

#### 2.1.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| AUTH-001 | 图形验证码生成 | 高 | 登录前获取验证码，IP 级别限流 |
| AUTH-002 | 账号密码登录 | 高 | 支持表单和 JSON 两种格式提交 |
| AUTH-003 | 用户注册 | 中 | 用户名+邮箱+密码+确认密码 |
| AUTH-004 | 获取当前用户信息 | 高 | 返回用户基本信息和角色权限 |
| AUTH-005 | 密码安全策略 | 高 | bcrypt 哈希存储，失败登录计数+账户锁定 |
| AUTH-006 | 用户 CRUD | 高 | 创建/查询/更新/删除用户 |
| AUTH-007 | 角色 CRUD | 高 | 创建/查询/更新/删除角色，含权限分配 |
| AUTH-008 | 权限 CRUD | 中 | 创建/查询/更新/删除权限，树形结构 |
| AUTH-009 | 角色分配/移除 | 高 | 为用户分配或移除角色 |
| AUTH-010 | 修改密码 | 中 | 用户修改自身密码 |
| AUTH-011 | 登录日志查询 | 低 | 查询用户登录历史 |

#### 2.1.3 用户操作流程

**登录流程**:
1. 用户访问登录页，系统自动请求验证码
2. 用户输入用户名、密码、验证码
3. 系统校验验证码 → 校验账户状态 → 校验密码 → 生成 JWT 令牌
4. 前端存储 token 到 localStorage，获取用户信息和权限，跳转到项目列表页
5. 支持"记住密码"功能

**用户管理流程**:
1. 管理员进入用户管理页，查看用户列表
2. 创建用户：填写用户名、邮箱、密码，分配角色
3. 编辑用户：修改基本信息、角色分配
4. 删除用户：仅超级管理员可操作

#### 2.1.4 输入输出规范

**登录请求**:
- 输入: `username`(String, 必填, ≤50字符), `password`(String, 必填, ≥6字符), `captcha_id`(String, 必填), `captcha_code`(String, 必填)
- 输出: `access_token`(String), `token_type`("bearer"), `expires_in`(Integer, 秒)

**注册请求**:
- 输入: `username`(String, 必填, ≤50字符, 唯一), `email`(String, 必填, ≤100字符, 唯一), `password`(String, 必填, ≥6字符), `confirm_password`(String, 必填, 须与 password 一致)
- 输出: 用户基本信息

**用户信息响应**:
- `id`(Integer), `username`(String), `email`(String), `is_active`(Boolean), `is_superuser`(Boolean), `roles`(Array<{id, name, permissions}>)

#### 2.1.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| AUTH-R01 | 验证码获取 IP 级别限流，同一 IP 60 秒内最多 5 次 |
| AUTH-R02 | 密码长度 ≥ 6 字符，bcrypt 哈希存储 |
| AUTH-R03 | 连续登录失败 5 次后账户锁定 30 分钟 |
| AUTH-R04 | 用户名和邮箱全局唯一 |
| AUTH-R05 | JWT 令牌有效期 480 分钟 |
| AUTH-R06 | 超级管理员(`is_superuser=True`)拥有所有权限 |
| AUTH-R07 | 权限类型分为 api/menu/data 三种 |
| AUTH-R08 | 权限支持树形结构(`parent_id`) |

#### 2.1.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 用户名或密码错误 | 401 | Invalid credentials |
| 验证码错误 | 401 | Invalid captcha code |
| 账户被禁用 | 403 | Account is disabled |
| 账户被锁定 | 403 | Account is locked |
| 用户名已存在 | 400 | Username already exists |
| 邮箱已注册 | 400 | Email already registered |
| 密码不一致 | 400 | Passwords do not match |
| 验证码获取频繁 | 429 | Too many requests |
| 令牌无效/过期 | 401 | Invalid or expired token |
| 无权限操作 | 403 | Permission denied |

---

### 模块 2: 项目管理

#### 2.2.1 功能概述

管理测试项目，支持 Web/App 两种项目类型，提供多环境配置、被测对象管理、自测项目定时调度等能力。

#### 2.2.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| PROJ-001 | 创建项目 | 高 | 填写项目名称、描述、类型，初始化项目 |
| PROJ-002 | 项目列表 | 高 | 分页查询、关键词搜索、按用户过滤 |
| PROJ-003 | 项目详情 | 高 | 查看项目基本信息、关联文件、环境配置 |
| PROJ-004 | 删除项目 | 高 | 物理删除，级联删除所有子表数据 |
| PROJ-005 | 项目配置 | 高 | 配置项目类型、Web 多环境、设备信息 |
| PROJ-006 | 被测对象管理 | 高 | 配置被测系统 URL、账号、设备信息 |
| PROJ-007 | 自测项目定时调度 | 中 | 配置 cron 表达式，定时执行自测 |
| PROJ-008 | 密码加密存储 | 高 | Web 环境密码加密存储，读取时脱敏 |

#### 2.2.3 用户操作流程

**创建项目流程**:
1. 点击"创建项目"，填写项目名称、描述、项目类型(web/app)
2. Web 项目：配置 test/staging/prod 三套环境（URL、用户名、密码）
3. App 项目：配置设备信息（平台、设备 ID、App 包名、Appium URL）
4. 提交创建

**项目配置流程**:
1. 进入项目详情页，点击"项目配置"
2. 修改项目类型、环境配置、设备配置
3. 保存配置

#### 2.2.4 输入输出规范

**创建项目请求**:
- 输入: `name`(String, 必填, ≤255字符), `description`(String, 可选), `project_type`(Enum: web/app, 默认 web), `web_env_configs`(Object, 可选), `device_config`(Object, 可选)
- 输出: 项目完整信息（含 id, status=1）

**Web 环境配置**:
- `test`/`staging`/`prod`: 各含 `url`(String), `username`(String), `password`(String, 加密存储)

**设备配置**:
- `default_device`(String), `devices`(Array<{platform, device_id, app_package, appium_url}>)

#### 2.2.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| PROJ-R01 | 项目状态: 0=未激活, 1=正常, 2=归档 |
| PROJ-R02 | 项目删除为物理删除，级联删除所有子表数据 |
| PROJ-R03 | 自测项目(`is_self_test=True`)不可删除 |
| PROJ-R04 | Web 环境密码通过 `encrypt_password` 加密存储，API 返回时 `mask_password` 脱敏 |
| PROJ-R05 | 项目数据通过 `user_id` 实现用户级隔离 |
| PROJ-R06 | 自测项目支持 cron 表达式定时执行 |

#### 2.2.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 项目名称为空 | 400 | Project name is required |
| 项目不存在 | 404 | Project not found |
| 非项目所有者 | 403 | Not project owner |
| 自测项目不可删除 | 400 | Self-test project cannot be deleted |

---

### 模块 3: 需求资源管理

#### 2.3.1 功能概述

管理项目下的需求文档、UI 原型图等资源文件，支持文件上传、URL 提交、内容提取、UI 原型解析。

#### 2.3.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| RES-001 | 单文件上传 | 高 | 上传需求文档、UI 原型图等文件 |
| RES-002 | 批量文件上传 | 高 | 批量上传多个文件 |
| RES-003 | URL 资源提交 | 中 | 提交 URL 作为需求资源 |
| RES-004 | 文件列表查询 | 高 | 按项目、资源类型筛选，分页查询 |
| RES-005 | 文件删除 | 高 | 删除指定文件 |
| RES-006 | 文件内容提取 | 高 | 上传后自动提取文本内容（用于 AI 生成） |
| RES-007 | 需求链接管理 | 中 | CRUD 需求链接，支持多种认证方式 |
| RES-008 | 链接内容获取 | 中 | 获取链接内容，支持缓存和强制刷新 |
| RES-009 | UI 原型项目管理 | 高 | 创建/查询/删除 UI 原型项目 |
| RES-010 | UI 页面截图上传 | 高 | 上传 UI 页面截图 |
| RES-011 | UI 页面 AI 解析 | 高 | AI 解析 UI 页面结构和元素 |
| RES-012 | 页面流程图编辑 | 高 | 可视化编辑页面间导航流程 |
| RES-013 | AI 生成页面流程 | 中 | AI 自动推断页面间导航关系 |

#### 2.3.3 用户操作流程

**资源上传流程**:
1. 进入资源中心，选择项目
2. 点击"上传资源"，选择文件类型(requirement/ui_mockup/api_doc/test_data/other)
3. 上传文件或提交 URL
4. 系统自动提取文件内容，更新 `extract_status`

**UI 原型解析流程**:
1. 创建 UI 原型项目，上传页面截图
2. 触发 AI 解析，系统识别页面元素和结构
3. 查看解析结果，编辑页面流程图
4. 保存流程数据

#### 2.3.4 输入输出规范

**文件上传请求**:
- 输入: `file`(Binary, 必填), `project_id`(Integer, 必填), `resource_type`(Enum, 必填), `description`(String, 可选)
- 输出: 文件信息（含 id, file_name, file_url, extract_status）

**需求链接请求**:
- 输入: `link_name`(String, 必填), `link_type`(Enum: requirement/ui_mockup/api_doc/other), `link_url`(String, 必填), `auth_type`(Enum: none/basic/bearer/api_key/cookie, 默认 none), `auth_config`(Object, 可选, 加密存储), `cache_expire_minutes`(Integer, 默认 60)

**UI 页面解析响应**:
- `ui_spec`(JSON): 页面元素列表，含元素类型、位置、文本等
- `parse_status`: pending/running/completed/failed
- `element_count`, `button_count`, `input_count`

#### 2.3.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| RES-R01 | 文件资源类型: requirement/ui_mockup/api_doc/test_data/other |
| RES-R02 | 文件内容提取状态: pending → processing → completed/failed |
| RES-R03 | 需求链接认证配置加密存储 |
| RES-R04 | 链接内容缓存，默认 60 分钟过期，支持 `force_refresh` 强制刷新 |
| RES-R05 | UI 原型解析状态: pending → running → completed/failed |
| RES-R06 | 流程图数据与项目一对一关联 |
| RES-R07 | 流程图编辑器 2 秒防抖自动保存，5xx 错误自动重试 |

#### 2.3.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 文件格式不支持 | 400 | Unsupported file format |
| 文件过大 | 413 | File size exceeds limit |
| 链接不可访问 | 400 | Link is not accessible |
| 认证配置无效 | 400 | Invalid auth configuration |
| UI 解析失败 | 500 | UI parsing failed |

---

### 模块 4: 测试点管理

#### 2.4.1 功能概述

管理测试关注点，支持 AI 从需求文档自动提取测试点、手动创建/编辑测试点、Xmind 导入、测试点与用例关联。

#### 2.4.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| TP-001 | 测试点列表查询 | 高 | 按项目、模块、优先级、状态筛选 |
| TP-002 | 创建测试点 | 高 | 手动创建测试点 |
| TP-003 | 更新测试点 | 高 | 编辑测试点信息 |
| TP-004 | 删除测试点 | 高 | 单条/批量删除 |
| TP-005 | AI 提取测试点 | 高 | 从需求文档 AI 提取测试点（SSE 流式） |
| TP-006 | Xmind 导入测试点 | 中 | 上传 Xmind 文件导入测试点 |
| TP-007 | 测试点关联用例查询 | 高 | 查看测试点关联的测试用例 |
| TP-008 | 批量保存测试点 | 高 | AI 提取后批量保存 |
| TP-009 | 测试点与业务能力关联 | 中 | 关联 TestCapability |

#### 2.4.3 用户操作流程

**AI 提取测试点流程**:
1. 进入测试点提取向导
2. 步骤 1: 选择项目
3. 步骤 2: 选择需求资源文件
4. 步骤 3: AI 提取（SSE 流式推送进度）
5. 步骤 4: 验证确认，编辑/删除/补充测试点
6. 批量保存

**Xmind 导入流程**:
1. 上传 Xmind 文件
2. 预览解析结果
3. 确认导入

#### 2.4.4 输入输出规范

**创建测试点请求**:
- 输入: `project_id`(Integer, 必填), `module`(String, 必填, ≤100字符), `point`(String, 必填, ≤500字符), `priority`(Enum: 1高/2中/3低, 必填), `capability_id`(Integer, 可选), `requirement_id`(Integer, 可选)
- 输出: 测试点完整信息

**AI 提取请求**:
- 输入: `project_id`(Integer, 必填), `file_ids`(Array<Integer>, 必填), `requirement_text`(String, 可选)
- 输出: SSE 流式推送，每条消息含 `type`(progress/result/error) 和 `data`

#### 2.4.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| TP-R01 | 测试点生命周期: draft → active → deprecated → archived |
| TP-R02 | 测试点优先级: 1=高, 2=中, 3=低 |
| TP-R03 | 测试点按模块分组，一级分类为模块 |
| TP-R04 | AI 提取使用 SSE 流式通信 |
| TP-R05 | 测试点可关联业务能力(`capability_id`) |
| TP-R06 | 测试点可关联需求(`requirement_id`) |

#### 2.4.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 项目不存在 | 404 | Project not found |
| 文件未选择 | 400 | No files selected |
| AI 提取失败 | 500 | AI extraction failed |
| Xmind 解析失败 | 400 | Xmind parsing failed |
| 测试点不存在 | 404 | Test point not found |

---

### 模块 5: 测试用例管理

#### 2.5.1 功能概述

测试用例全生命周期管理，包括 AI 生成、手动创建、编辑、审核、版本管理、血缘追踪、软删除/恢复、导出等。

#### 2.5.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| TC-001 | 用例列表查询 | 高 | 分页、多维度筛选（关键词/模块/优先级/类型/状态/创建人/设备） |
| TC-002 | 创建用例 | 高 | 手动创建测试用例 |
| TC-003 | 更新用例 | 高 | 编辑用例信息 |
| TC-004 | 删除用例（软删除） | 高 | 标记 `is_deleted=True`，支持恢复 |
| TC-005 | 批量删除 | 高 | 批量软删除 |
| TC-006 | 批量恢复 | 高 | 批量恢复软删除用例 |
| TC-007 | AI 基础生成 | 高 | 基于需求/测试点 AI 生成用例 |
| TC-008 | AI 增强生成 | 高 | 增强模式（含 UI 原型上下文） |
| TC-009 | AI 流式生成 | 高 | SSE 流式生成用例 |
| TC-010 | AI 单点生成 | 中 | 基于单个测试点生成 |
| TC-011 | AI 批量生成 | 高 | 批量 AI 生成 |
| TC-012 | 生成上下文分析 | 高 | 分析资料完整度，返回警告和建议 |
| TC-013 | 用例详情 | 高 | 查看用例完整信息 |
| TC-014 | 版本管理 | 高 | 版本历史、版本对比、版本回滚 |
| TC-015 | 血缘追踪 | 中 | 查看用例衍生关系（父用例） |
| TC-016 | 用例导出 | 高 | Excel/Markdown/HTML/Python/JSON |
| TC-017 | 用例导入 | 中 | Excel 导入用例 |
| TC-018 | 前置条件管理 | 高 | 前置条件步骤 CRUD |
| TC-019 | AI 解析前置条件 | 中 | AI 自动解析前置条件 |
| TC-020 | 用例编号自动生成 | 高 | 格式 `TC-{project_id}-{seq}` |
| TC-021 | 生命周期状态流转 | 高 | 通过 LifecycleService 受控流转 |
| TC-022 | 用例工作流 | 中 | 纠正状态管理 |
| TC-023 | 技术视图 | 高 | 查看定位器信息、测试数据 |
| TC-024 | 业务视图 | 高 | 查看业务步骤描述 |
| TC-025 | 用例补充 | 中 | AI 补充用例细节 |

#### 2.5.3 用户操作流程

**AI 生成用例流程**:
1. 进入 AI 生成页面
2. 步骤 1: 选择项目
3. 步骤 2: 选择资源（需求文件、UI 文件、测试点）
4. 步骤 3: 配置生成参数（用例类型、执行模式、优先级、增强模式），点击生成
5. 步骤 4: 查看生成结果，编辑/重新生成/删除/保存

**用例编辑流程**:
1. 从用例列表点击进入详情
2. 编辑标题、模块、优先级、步骤等
3. 保存时自动创建版本快照
4. 生命周期状态自动流转

**版本管理流程**:
1. 查看版本历史列表
2. 选择两个版本进行对比
3. 可回滚到指定版本

#### 2.5.4 输入输出规范

**创建用例请求**:
- 输入: `project_id`(Integer, 必填), `module`(String, 必填), `title`(String, 必填, ≤255字符), `precondition`(String, 必填), `steps_json`(JSON, 必填), `expected_result`(String, 必填), `priority`(Enum: 1/2/3), `case_type`(Enum: ui_automation/manual/api_automation/performance/security), `test_point_id`(Integer, 可选), `target_device`(Enum: tablet/phone/desktop/web, 可选)
- 输出: 用例完整信息（含 `case_no`, `lifecycle_status`="draft"）

**AI 生成请求**:
- 输入: `project_id`(Integer, 必填), `requirement_file_ids`(Array<Integer>), `test_point_ids`(Array<Integer>), `ui_screen_ids`(Array<Integer>), `case_type`(Enum), `execution_mode`(Enum), `priority`(Enum), `enhanced_mode`(Boolean)
- 输出: 生成结果列表，每条含 `title`, `steps_json`, `expected_result`, `priority`, `generate_status`

**用例列表查询参数**:
- `project_id`(Integer, 必填), `keyword`(String, 可选), `module`(String, 可选), `priority`(Integer, 可选), `case_type`(String, 可选), `lifecycle_status`(String, 可选), `is_deleted`(Boolean, 默认 False), `page`(Integer, 默认 1), `page_size`(Integer, 默认 20, 最大 100)

#### 2.5.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| TC-R01 | 用例编号格式: `TC-{project_id}-{seq}`，通过 `case_number_seqs` 行锁保证并发安全 |
| TC-R02 | 生命周期状态机（必须通过 `LifecycleService.transition()` 变更）: draft → active → pending_review → needs_modify → active; active → locator_broken → active(修复); active → deprecated → archived |
| TC-R03 | `lifecycle_status` 禁止直接 SQL UPDATE，由 `before_flush` event hook 拦截 |
| TC-R04 | 追踪字段变更时自动创建版本快照（`CaseVersionService`） |
| TC-R05 | 软删除: `is_deleted=True` + `deleted_at`，支持批量恢复 |
| TC-R06 | 用例类型: ui_automation/manual/api_automation/performance/security |
| TC-R07 | 优先级: 1=高, 2=中, 3=低 |
| TC-R08 | 审核状态: pending/approved/rejected/needs_optimization |
| TC-R09 | 纠正状态: failed_correction/correcting/verifying/verified |
| TC-R10 | 生成状态: 0=生成中, 1=成功, 2=失败 |
| TC-R11 | 步骤支持业务视图和技术视图双重视角 |
| TC-R12 | 步骤操作类型: click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress |
| TC-R13 | 用例支持血缘关系（`parent_case_id`） |
| TC-R14 | AI 降级用例类型为 manual |

#### 2.5.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 用例不存在 | 404 | Test case not found |
| 非法生命周期流转 | 400 | Invalid lifecycle transition |
| 直接修改 lifecycle_status | 500 | Direct lifecycle_status modification blocked |
| AI 生成失败 | 500 | AI generation failed |
| 用例编号冲突 | 409 | Case number conflict |
| 版本回滚目标不存在 | 404 | Version not found |

---

### 模块 6: 智能生成用例

#### 2.6.1 功能概述

提供端到端的智能用例生成能力，支持新功能生成、历史用例更新、资产导入三种任务类型，含上下文分析、策略选择、质量控制、批次管理。

#### 2.6.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| SG-001 | 任务类型选择 | 高 | 新功能生成/历史用例更新/资产导入 |
| SG-002 | 素材选择 | 高 | 选择项目、需求文件、测试点、UI 页面 |
| SG-003 | 上下文分析 | 高 | 自动分析资料完整度(L0-L3)，展示警告和建议 |
| SG-004 | 策略选择 | 高 | 根据资料自动选择生成策略 |
| SG-005 | AI 流式生成 | 高 | 流式生成测试用例，实时展示 |
| SG-006 | 质量控制 | 高 | 每条用例标记质量状态(passed/warning/pending_review/rejected) |
| SG-007 | 保存确认 | 高 | 选择保存模式(draft/formal/passed_only) |
| SG-008 | 历史资产上传 | 中 | 上传 Excel/XMind 历史资产 |
| SG-009 | 系统用例导入 | 中 | 导入系统已有用例作为历史资产 |
| SG-010 | AI 对齐分析 | 高 | 将历史用例与当前需求匹配，分类处理 |
| SG-011 | 生成批次管理 | 高 | 创建/查询/更新/保存生成批次 |
| SG-012 | 成本查看 | 中 | 保存后查看 AI 调用成本 |

#### 2.6.3 用户操作流程

**新功能生成流程**:
1. 选择任务类型: "新功能生成"
2. 选择素材: 项目、需求文件、测试点、UI 页面
3. 上下文分析: 自动分析资料完整度，展示 L0-L3 级别
4. 策略选择: 系统根据资料自动选择（标准需求生成/完整资料生成）
5. AI 生成: 流式生成用例
6. 预览与质量控制: 查看质量状态，单条重新生成
7. 保存确认: 选择保存模式，批量保存
8. 查看成本

**历史用例更新流程**:
1. 选择任务类型: "历史用例更新"
2. 上传历史资产或导入系统用例
3. AI 对齐分析: 分类为 REUSE/UPDATE/NEW/DEPRECATED/CONFIRM_REQUIRED
4. 用户选择操作，批量保存

#### 2.6.4 输入输出规范

**创建生成批次请求**:
- 输入: `project_id`(Integer, 必填), `entry_type`(Enum: NEW_FEATURE_GENERATION/HISTORY_UPDATE/ASSET_IMPORT), `scenario_type`(String, 必填), `generation_strategy`(String, 必填), `requirement_file_ids_json`(Array), `test_point_ids_json`(Array), `ui_screen_ids_json`(Array), `history_asset_ids_json`(Array)
- 输出: 批次信息（含 `batch_no`, `status`="created"）

**保存批次请求**:
- 输入: `save_mode`(Enum: draft/formal/passed_only), `idempotency_key`(String, 必填), `cases`(Array<CaseData>)
- 输出: 保存结果（含成功/失败数量）

**AI 对齐分析响应**:
- 分类: REUSE_CASE(完全匹配)/UPDATE_CASE(标题匹配内容差异)/NEW_CASE(无匹配)/DEPRECATED_CASE(系统用例无匹配)/CONFIRM_REQUIRED(需人工确认)

#### 2.6.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| SG-R01 | 生成批次状态机: created → context_ready → generating → preview_ready → saving → saved/partial_saved/failed |
| SG-R02 | 幂等保存: `idempotency_key` + `request_hash` 防止重复保存 |
| SG-R03 | 保存模式: draft(草稿)/formal(正式)/passed_only(仅通过) |
| SG-R04 | 用例操作: update_existing(更新已有)/deprecate(标记废弃)/新增 |
| SG-R05 | 保存时自动创建版本快照 |
| SG-R06 | 历史资产类型: excel/xmind/system_cases |
| SG-R07 | 对齐分类基于标题相似度(Jaccard+前缀匹配) |
| SG-R08 | 批次号格式: `GB{YYYYMMDD}{seq}` |

#### 2.6.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 批次不存在 | 404 | Generation batch not found |
| 批次状态不允许操作 | 400 | Invalid batch status for operation |
| 重复保存请求 | 409 | Duplicate save request |
| AI 生成超时 | 504 | AI generation timeout |
| 历史资产解析失败 | 400 | History asset parsing failed |

---

### 模块 7: 测试任务与执行

#### 2.7.1 功能概述

创建测试任务，执行自动化测试，支持多种执行模式、实时进度推送、视频录制回放、失败分析、快速验证。

#### 2.7.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| EXEC-001 | 创建测试任务 | 高 | 选择用例、填写任务名称 |
| EXEC-002 | 任务列表查询 | 高 | 按项目、状态筛选 |
| EXEC-003 | 任务详情 | 高 | 查看任务信息和执行结果 |
| EXEC-004 | 启动执行 | 高 | 配置执行模式，开始执行 |
| EXEC-005 | 暂停执行 | 高 | 暂停正在执行的任务 |
| EXEC-006 | 恢复执行 | 高 | 恢复暂停的任务 |
| EXEC-007 | 停止执行 | 高 | 停止正在执行的任务 |
| EXEC-008 | 实时进度推送 | 高 | WebSocket 实时推送执行进度 |
| EXEC-009 | 步骤截图查看 | 高 | 查看执行前后截图 |
| EXEC-010 | 视频录制与回放 | 中 | 录制执行过程，支持回放 |
| EXEC-011 | AI 失败分析 | 高 | AI 自动分析失败原因 |
| EXEC-012 | 快速验证 | 中 | 快速验证单个用例 |
| EXEC-013 | ADB 设备管理 | 中 | 查询已连接的 ADB 设备 |
| EXEC-014 | 可见性配置 | 中 | 配置 headless/录制视频/截图/执行速度等 |
| EXEC-015 | 自愈定位 | 中 | 元素定位失败时自动尝试替代策略 |
| EXEC-016 | 删除任务 | 高 | 删除测试任务 |

#### 2.7.3 用户操作流程

**测试执行流程**:
1. 创建任务: 选择项目，填写任务名称，选择测试用例
2. 配置执行参数: 执行模式、目标环境、是否 MCP 模式
3. 启动执行 → WebSocket 实时推送进度
4. 执行过程中可暂停/恢复/停止
5. 查看步骤截图、执行日志
6. 视频录制与回放
7. 失败分析: AI 分析失败原因
8. 自测项目自动创建 Bug

#### 2.7.4 输入输出规范

**创建任务请求**:
- 输入: `task_name`(String, 必填), `project_id`(Integer, 必填), `case_ids`(Array<Integer>, 必填), `visibility_config`(Object, 可选)
- 输出: 任务信息（含 `id`, `status`=0）

**启动执行请求**:
- 输入: `execution_mode`(Enum: preprocess/realtime/smart/mobile_realtime/mobile_smart), `target_env`(Enum: test/staging/prod), `mcp_mode`(Boolean, 默认 False)
- 输出: 执行状态

**执行结果**:
- `exec_status`: 0=未执行, 1=成功, 2=失败, 3=阻塞
- `exec_log`(Text): 执行日志
- `error_msg`(Text): 失败错误信息
- `ai_analysis`(Text): AI 分析结果

#### 2.7.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| EXEC-R01 | 任务状态: 0=等待, 1=执行中, 2=完成, 3=失败, 4=已停止 |
| EXEC-R02 | 执行模式: preprocess/realtime/smart/mobile_realtime/mobile_smart |
| EXEC-R03 | 可见性配置三级: global/task/case |
| EXEC-R04 | 可见性配置项: headless, record_video, video_resolution, video_fps, take_screenshot, execution_speed, action_delay_ms, highlight_elements, show_ai_analysis |
| EXEC-R05 | 自测项目执行失败自动创建 Bug |
| EXEC-R06 | 批量插入优化: 任务创建使用 `bulk_insert_mappings` |
| EXEC-R07 | 元素定位优先级: css_selector > xpath > element_id > element_name > ai_coordinate |
| EXEC-R08 | 定位器来源: ai/manual/auto |
| EXEC-R09 | 定位器乐观锁: `version` 字段 + atomic 更新 |

#### 2.7.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 任务不存在 | 404 | Task not found |
| 任务状态不允许操作 | 400 | Invalid task status |
| 执行引擎启动失败 | 500 | Execution engine failed to start |
| 设备未连接 | 400 | No connected devices |
| 元素定位失败 | 500 | Element locator failed |
| AI 失败分析超时 | 504 | AI failure analysis timeout |

---

### 模块 8: 迭代管理

#### 2.8.1 功能概述

管理测试迭代，支持迭代创建、输入管理、基线对比、定稿、Pipeline 触发。

#### 2.8.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| ITER-001 | 创建迭代 | 高 | 填写名称、版本、描述 |
| ITER-002 | 迭代列表查询 | 高 | 按项目查询迭代列表 |
| ITER-003 | 迭代详情 | 高 | 查看迭代信息和关联数据 |
| ITER-004 | 更新迭代 | 高 | 修改迭代信息 |
| ITER-005 | 删除迭代 | 高 | 删除迭代 |
| ITER-006 | 添加迭代输入 | 高 | 添加 PRD/原型/Xmind/测试点/补充表单/变更说明 |
| ITER-007 | 定稿迭代 | 高 | 标记迭代为已定稿 |
| ITER-008 | 基线迭代对比 | 中 | 基于基线迭代对比差异 |
| ITER-009 | 触发 Pipeline | 高 | 启动迭代 Pipeline 运行 |

#### 2.8.3 用户操作流程

**迭代管理流程**:
1. 创建迭代，填写名称、版本号、描述
2. 添加迭代输入（文件或表单数据）
3. 触发 Pipeline 运行
4. Pipeline 完成后进入评审
5. 评审通过后定稿

#### 2.8.4 输入输出规范

**创建迭代请求**:
- 输入: `project_id`(Integer, 必填), `name`(String, 必填, ≤200字符), `version`(String, 默认 "v1.0"), `description`(String, 可选), `base_iteration_id`(Integer, 可选), `target_device`(Enum, 可选)
- 输出: 迭代信息（含 `status`="draft"）

**添加迭代输入请求**:
- 输入: `kind`(Enum: prd/prototype/xmind/testpoint/supplement_form/change_notes), `file_id`(Integer, 可选), `payload`(JSON, 可选)
- 输出: 输入信息（含 `content_hash`）

#### 2.8.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| ITER-R01 | 迭代状态机: draft → in_pipeline → in_review → finalized → archived（系统自动驱动） |
| ITER-R02 | 同项目迭代名称唯一 |
| ITER-R03 | 迭代输入幂等校验: `content_hash` 防止重复添加 |
| ITER-R04 | 输入类型: prd/prototype/xmind/testpoint/supplement_form/change_notes |
| ITER-R05 | 定稿设置 `finalized_at` 时间戳 |
| ITER-R06 | 基线迭代支持跨迭代对比 |

#### 2.8.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 迭代不存在 | 404 | Iteration not found |
| 迭代名称重复 | 400 | Iteration name already exists |
| 重复输入 | 409 | Duplicate iteration input |
| 状态不允许操作 | 400 | Invalid iteration status |

---

### 模块 9: Pipeline 流水线

#### 2.9.1 功能概述

可编排的 Step 执行引擎，支持缓存命中、重试、降级、暂停等待用户确认、WebSocket 实时推送。

#### 2.9.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| PIPE-001 | 触发 Pipeline 运行 | 高 | 基于迭代触发 |
| PIPE-002 | 查询运行状态 | 高 | 实时查询 Pipeline 运行状态 |
| PIPE-003 | 恢复暂停的 Pipeline | 高 | 用户确认后恢复 |
| PIPE-004 | 取消运行 | 高 | 协作式取消 |
| PIPE-005 | 获取 Pipeline 摘要 | 高 | 运行结果摘要 |
| PIPE-006 | 获取反推摘要 | 中 | AI 推断摘要 |
| PIPE-007 | 补充信号 | 高 | 用户补全信号后恢复 |
| PIPE-008 | 场景 4 预检 | 中 | 检查历史用例/测试点/UI 可用性 |
| PIPE-009 | WebSocket 进度推送 | 高 | 实时推送 Step 进度 |
| PIPE-010 | Pipeline 仪表盘 | 中 | 总览/Token 消耗/运行时长/Step 耗时/缓存命中率 |
| PIPE-011 | FMEA 指标 | 中 | 失效模式与影响分析指标 |

#### 2.9.3 用户操作流程

**Pipeline 运行流程**:
1. 用户触发 Pipeline（通过迭代或回归变更分析）
2. 系统按注册顺序执行 Step
3. 每步检查缓存命中 → 执行 → 校验输出 → 降级/重试
4. 置信度 < 0.7 或 Token 预算超限时暂停等待用户确认
5. 用户确认后恢复运行
6. 完成后推送摘要

**Pipeline 5 步流程**:
1. 信号采集 (SignalGatherer)
2. 测试点对齐 (TestpointAlignment)
3. 用例生成 (CaseGeneration)
4. 质量门禁 (QualityGate)
5. 用例持久化 (Persist)

#### 2.9.4 输入输出规范

**触发 Pipeline 请求**:
- 输入: `iteration_id`(Integer, 必填)
- 输出: 运行信息（含 `run_id`, `status`="pending"）

**运行状态响应**:
- `status`: pending/running/waiting_for_user/completed/failed/cancelled
- `steps`: Array<{step_name, status, cache_key, retried_count, degraded}>
- `pause_payload`: JSON（暂停原因和确认表单）

#### 2.9.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| PIPE-R01 | Pipeline 运行状态机: pending → running → completed/failed/cancelled; running → waiting_for_user → running |
| PIPE-R02 | Step 状态: pending/running/done/failed/skipped/degraded |
| PIPE-R03 | 缓存命中: 同 `cache_key` 已有 done 状态的 step 可跳过 |
| PIPE-R04 | 重试: 最多 2 次(`MAX_RETRIES=2`) |
| PIPE-R05 | 降级: 重试耗尽后调用 `fallback` 方法 |
| PIPE-R06 | 暂停条件: 置信度 < 0.7 或 Token 预算超限 |
| PIPE-R07 | 幂等性: `input_hash` 防止重复创建运行 |
| PIPE-R08 | 产物唯一: `content_hash` 防止重复落库 |
| PIPE-R09 | 协作式取消: Step 间检测 cancelled 状态 |
| PIPE-R10 | FMEA 指标: F1低置信度暂停/F2JSON校验失败/F3双向扫描冲突/F5零编辑确认/F9中断恢复/F11Token超限/F12Fallback模型/F13评审撤销/F14版本重跑/F15审计写入失败/F16后验质量分/F17评审拒绝率过高 |

#### 2.9.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| Pipeline 运行不存在 | 404 | Pipeline run not found |
| 运行状态不允许操作 | 400 | Invalid run status |
| 重复触发 | 409 | Duplicate pipeline run |
| Step 执行失败 | 500 | Step execution failed |
| Token 预算超限 | 400 | Token budget exceeded |
| 缓存键冲突 | 409 | Cache key conflict |

---

### 模块 10: 评审管理

#### 2.10.1 功能概述

管理 Pipeline 产出的评审决策，支持 AI 判定 + 人工确认、批量操作、最终化、撤销。

#### 2.10.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| REV-001 | 决策列表查询 | 高 | 查看评审决策列表 |
| REV-002 | 单条人工判定 | 高 | keep/modify/deprecate |
| REV-003 | 批量人工判定 | 高 | 批量采纳高置信度决策 |
| REV-004 | 最终化评审 | 高 | 不可逆操作，1 小时撤销窗口 |
| REV-005 | 撤销决策 | 中 | 撤销单条决策 |
| REV-006 | 回滚决策 | 中 | 重置决策到初始状态 |
| REV-007 | 撤销最终化 | 中 | 1 小时内可撤销 |
| REV-008 | 应用决策 | 高 | 将评审结果应用到用例 |

#### 2.10.3 用户操作流程

**评审流程**:
1. Pipeline 完成后进入评审
2. 查看决策列表，按 AI 判定分类
3. 对每条决策进行人工判定
4. 批量采纳高置信度决策
5. 最终化评审
6. 应用决策到用例

#### 2.10.4 输入输出规范

**人工判定请求**:
- 输入: `human_verdict`(Enum: keep/modify/deprecate), `human_reason`(String, 可选)
- 输出: 更新后的决策信息

**最终化请求**:
- 输出: 评审信息（含 `finalized_at`, `finalized_by`）

#### 2.10.5 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| REV-R01 | 评审类型: forward/backward/merged |
| REV-R02 | 评审状态: draft/in_progress/finalized/cancelled |
| REV-R03 | AI 判定: keep/modify/deprecate，含置信度(0-100) |
| REV-R04 | 评审锁定: `acquire_lock` 防止并发修改 |
| REV-R05 | 锁定过期: 默认 24 小时 |
| REV-R06 | 零编辑确认: 检测 AI 与人工判定一致但无修改 |
| REV-R07 | 撤销窗口: 最终化后 1 小时内可撤销 |
| REV-R08 | 决策应用: 新增/修改/废弃用例 |

#### 2.10.6 异常处理

| 异常场景 | HTTP 状态码 | 错误信息 |
|----------|-------------|----------|
| 评审不存在 | 404 | Review not found |
| 决策不存在 | 404 | Decision not found |
| 评审锁定冲突 | 409 | Review lock conflict |
| 撤销窗口已过期 | 400 | Undo window expired |
| 评审已最终化 | 400 | Review already finalized |
| 零编辑确认警告 | 400 | Zero-edit confirmation required |

---

### 模块 11: 用例质量分析

#### 2.11.1 功能概述

评估测试用例质量，支持项目级和用例级质量分析、批量分析、定位器优化、质量趋势追踪。

#### 2.11.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| QA-001 | 项目质量分析 | 高 | 项目级质量评分和维度分析 |
| QA-002 | 用例质量分析 | 高 | 单条用例质量评分 |
| QA-003 | 质量趋势 | 中 | 用例质量趋势追踪 |
| QA-004 | 成本统计 | 中 | 用例/项目成本统计 |
| QA-005 | 批量质量分析 | 高 | 批量分析用例质量 |
| QA-006 | 优化定位器 | 中 | AI 优化用例元素定位器 |
| QA-007 | 先验质量分 | 高 | 生成时由 QualityGate 计算 |
| QA-008 | 后验质量分 | 高 | 评审+执行后回填 |

#### 2.11.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| QA-R01 | 先验质量分: 0-100，生成时计算 |
| QA-R02 | 后验质量分: 0-100，评审+执行后回填 |
| QA-R03 | 质量规则: 项目级 `QualityRuleConfig` 配置 |
| QA-R04 | 质量维度: 覆盖度/复杂度/冗余度/建议 |

---

### 模块 12: 用例迁移

#### 2.12.1 功能概述

支持跨设备类型用例迁移、Excel 导入、AI 改写、批次管理和回滚。

#### 2.12.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| MIG-001 | Excel 导入 | 中 | 导入 Excel 格式用例 |
| MIG-002 | 跨设备迁移预览 | 高 | 预览迁移结果和类型 |
| MIG-003 | 确认批量迁移 | 高 | 提交迁移 |
| MIG-004 | 迁移批次查询 | 中 | 查询迁移批次信息 |
| MIG-005 | 回滚迁移 | 高 | 回滚指定批次迁移 |

#### 2.12.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| MIG-R01 | 设备类型: tablet/phone/desktop/web |
| MIG-R02 | 迁移类型: cloned(直接克隆)/adapted(AI改写)/split(拆分)/new(新增)/deprecated(废弃) |
| MIG-R03 | 批次管理: `migration_batch_id` 标识同一次迁移 |
| MIG-R04 | AI 改写: 调用 AI 客户端改写用例步骤 |

---

### 模块 13: 用例刷新（保鲜建议）

#### 2.13.1 功能概述

检测陈旧用例，提供保鲜建议，支持 AI 自动刷新和人工评审。

#### 2.13.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| REF-001 | 扫描陈旧用例 | 高 | 检测需要更新的用例 |
| REF-002 | 保鲜建议列表 | 高 | 查看保鲜建议 |
| REF-003 | 评审保鲜建议 | 高 | accept/reject 保鲜建议 |
| REF-004 | 自动刷新 | 中 | AI 自动刷新陈旧用例 |
| REF-005 | 保鲜统计 | 中 | 保鲜建议统计 |

#### 2.13.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| REF-R01 | 触发原因: stale/requirement_changed/ui_changed/manual |
| REF-R02 | 建议状态: pending/accepted/rejected/applied/expired |
| REF-R03 | 评审状态: pending/approved/rejected |
| REF-R04 | 快照版本: 关联 `test_case_versions.id` |

---

### 模块 14: 批量定位器

#### 2.14.1 功能概述

批量识别用例步骤中的页面元素并生成定位器，支持异步执行和进度查询。

#### 2.14.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| BL-001 | 启动批量定位 | 高 | 选择用例，配置参数，启动 |
| BL-002 | 查询任务状态 | 高 | 轮询批量定位任务进度 |
| BL-003 | 获取定位报告 | 高 | 查看定位结果 |
| BL-004 | 取消任务 | 中 | 取消正在执行的定位任务 |
| BL-005 | 任务列表 | 中 | 查看历史批量定位任务 |

#### 2.14.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| BL-R01 | 一次最多 100 个用例 |
| BL-R02 | 定位器类型: css/xpath |
| BL-R03 | 异步执行，通过状态接口轮询进度 |

---

### 模块 15: 报告管理

#### 2.15.1 功能概述

生成和管理测试报告，支持统计展示和多格式导出。

#### 2.15.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| RPT-001 | 生成测试报告 | 高 | 基于任务生成报告 |
| RPT-002 | 报告列表查询 | 高 | 按项目筛选，分页查询 |
| RPT-003 | 报告详情 | 高 | 统计数据和用例结果 |
| RPT-004 | 导出报告 | 高 | PDF/HTML 格式导出 |
| RPT-005 | 删除报告 | 高 | 删除指定报告 |

#### 2.15.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| RPT-R01 | 报告状态: pending/running/completed/failed |
| RPT-R02 | 统计项: 总用例数、通过/失败/阻塞数、通过率 |
| RPT-R03 | 支持执行时间统计 |

---

### 模块 16: AI 成本仪表盘

#### 2.16.1 功能概述

展示 AI 调用成本和统计信息，支持项目维度和时间范围筛选。

#### 2.16.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| AICOST-001 | 成本概览 | 高 | 总 Token 消耗、总成本、调用次数、成功率 |
| AICOST-002 | 成本趋势图 | 高 | 按日期的成本趋势 |
| AICOST-003 | Token 消耗图 | 中 | 每日 Token 消耗堆叠柱状图 |
| AICOST-004 | 模型成本饼图 | 中 | 按模型的成本分布 |
| AICOST-005 | 策略成本柱状图 | 中 | 按策略的成本分布 |
| AICOST-006 | 调用记录列表 | 高 | 分页查询 AI 调用记录 |

#### 2.16.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| AICOST-R01 | 默认时间范围: 近 30 天 |
| AICOST-R02 | 支持时间范围: 7/14/30 天 |
| AICOST-R03 | 成本聚合维度: model/strategy/date |
| AICOST-R04 | 通过 GenerationBatch 间接关联 project_id |

---

### 模块 17: 系统管理

#### 2.17.1 功能概述

提供用户管理、角色管理、审计日志、特性开关、质量规则、测试能力等系统级配置。

#### 2.17.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| SYS-001 | 用户管理 | 高 | 用户 CRUD、角色分配 |
| SYS-002 | 角色管理 | 高 | 角色 CRUD、权限分配 |
| SYS-003 | 审计日志查询 | 中 | 多维度过滤查询 |
| SYS-004 | FeatureFlag 管理 | 中 | 特性开关 CRUD、灰度配置 |
| SYS-005 | 质量规则配置 | 中 | 项目级质量规则编辑 |
| SYS-006 | 测试能力管理 | 中 | 测试能力 CRUD |
| SYS-007 | 提示词模板管理 | 中 | Prompt 版本管理、默认版本设置、回滚 |

#### 2.17.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| SYS-R01 | 审计日志不可变: 禁止 UPDATE 和 DELETE（before_flush hook 拦截） |
| SYS-R02 | 审计日志 action 枚举: lifecycle_transition/review_decide/review_rollback/review_undo/review_finalize/pipeline_start/pipeline_step_complete/pipeline_pause/pipeline_resume/pipeline_cancel/permission_change/config_change/case_version_create/locator_version_create/force_cancel_review |
| SYS-R03 | FeatureFlag 灰度: `rollout_percentage` 0-100 |
| SYS-R04 | FeatureFlag 目标类型: all/specific |
| SYS-R05 | 测试能力唯一约束: (project_id, key) |
| SYS-R06 | 测试能力软删除: status → archived |
| SYS-R07 | Prompt 模板版本管理: 每个 prompt_key 只有一个默认版本 |
| SYS-R08 | Prompt 回滚: 禁用高于目标版本的版本 |

---

### 模块 18: 测试数据管理

#### 2.18.1 功能概述

管理测试步骤的测试数据，支持多种数据类型和生成规则。

#### 2.18.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| TD-001 | 创建测试数据 | 高 | 为步骤创建测试数据 |
| TD-002 | 查询测试数据 | 高 | 查询步骤的测试数据 |
| TD-003 | 更新测试数据 | 高 | 编辑测试数据 |
| TD-004 | 删除测试数据 | 高 | 删除测试数据 |
| TD-005 | 生成测试数据 | 中 | 基于规则生成测试数据 |
| TD-006 | AI 自动推断生成 | 中 | AI 自动推断并生成测试数据 |

#### 2.18.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| TD-R01 | 数据类型: text/number/date/datetime/email/phone/enum/boolean/url/id_card/bank_card |
| TD-R02 | 生成规则: random/boundary_min/boundary_max/boundary_over/special_chars/empty/custom |
| TD-R03 | 测试数据与步骤一对多关联 |
| TD-R04 | 用例与测试数据多对多关联（通过 `test_case_data`） |

---

### 模块 19: AB 测试

#### 2.19.1 功能概述

记录和汇总 A/B 测试实验指标数据。

#### 2.19.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| AB-001 | 记录实验指标 | 中 | 记录一条 A/B 测试指标 |
| AB-002 | 获取实验汇总 | 中 | 获取实验汇总数据 |
| AB-003 | 列出所有实验 | 低 | 列出所有 A/B 测试实验 |

#### 2.19.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| AB-R01 | 变体标识: control/treatment |
| AB-R02 | 项目隔离: 只查询用户所属项目的实验数据 |

---

### 模块 20: 历史资产管理

#### 2.20.1 功能概述

上传和管理历史测试资产，支持 AI 智能对齐分析。

#### 2.20.2 功能点列表

| 编号 | 功能点 | 优先级 | 说明 |
|------|--------|--------|------|
| HA-001 | 上传历史资产 | 高 | 上传 Excel/XMind 文件 |
| HA-002 | 资产列表查询 | 高 | 按项目查询资产列表 |
| HA-003 | AI 对齐分析 | 高 | 将历史用例与当前需求匹配 |
| HA-004 | 导入系统用例 | 中 | 从系统导入已有用例作为历史资产 |
| HA-005 | 资产详情 | 高 | 查看资产详情和解析结果 |

#### 2.20.3 业务规则

| 规则编号 | 规则描述 |
|----------|----------|
| HA-R01 | 资产类型: excel/xmind/system_cases |
| HA-R02 | 解析状态: pending/parsing/completed/failed |
| HA-R03 | 对齐分类: REUSE_CASE/UPDATE_CASE/NEW_CASE/DEPRECATED_CASE/CONFIRM_REQUIRED |

---

## 三、核心业务状态机汇总

### 3.1 测试用例生命周期

```
draft ──→ active ──→ pending_review ──→ needs_modify ──→ active
  │          │              │
  │          ├──→ locator_broken ──→ active(修复后)
  │          │
  │          └──→ deprecated ──→ archived
```

**保护机制**: 禁止直接 SQL UPDATE `lifecycle_status`，必须通过 `LifecycleService.transition()`，由 `before_flush` event hook 拦截。

### 3.2 迭代流水线状态

```
draft ──→ in_pipeline ──→ in_review ──→ finalized ──→ archived
```

**驱动方式**: 系统自动驱动，不由用户手动设置。

### 3.3 Pipeline 运行状态

```
pending ──→ running ──→ completed
  │           │
  │           ├──→ waiting_for_user ──→ running(用户确认后)
  │           ├──→ failed
  │           └──→ cancelled
```

### 3.4 评审状态

```
draft ──→ in_progress ──→ finalized
  │           │
  └──→ cancelled   └──→ cancelled
```

### 3.5 测试任务状态

```
PENDING(0) ──→ RUNNING(1) ──→ COMPLETED(2)
                    │
                    ├──→ FAILED(3)
                    └──→ STOPPED(4)
```

### 3.6 测试点生命周期

```
draft ──→ active ──→ deprecated ──→ archived
```

### 3.7 生成批次状态

```
created ──→ context_ready ──→ generating ──→ preview_ready ──→ saving ──→ saved/partial_saved/failed
```

---

## 四、数据完整性约束

### 4.1 唯一性约束

| 表 | 字段/组合 | 说明 |
|----|-----------|------|
| users | username, email | 用户名和邮箱全局唯一 |
| test_cases | case_no | 用例编号全局唯一 |
| requirements | req_no | 需求编号全局唯一 |
| bugs | bug_no | Bug 编号全局唯一 |
| test_capabilities | (project_id, key) | 同项目能力 key 唯一 |
| iterations | (project_id, name) | 同项目迭代名唯一 |
| artifacts | content_hash | 产物内容哈希唯一 |
| pipeline_config | key | 配置项键名唯一 |
| prompt_templates | (prompt_key, prompt_version) | Prompt 版本唯一 |
| generation_batches | batch_no | 批次号唯一 |
| element_locators | step_id | 步骤定位器一对一 |
| quality_rule_configs | (project_id, rule_key) | 项目+规则键唯一 |

### 4.2 应用级约束

| 约束 | 位置 | 说明 |
|------|------|------|
| lifecycle_status 保护 | test_case before_flush hook | 禁止直接修改 |
| AuditLog 不可变 | audit_log before_flush hook | 禁止 UPDATE 和 DELETE |
| 版本自动快照 | test_case before_flush hook | 追踪字段变更时自动创建 |
| 乐观锁 | element_locators.version | 并发安全 |
| 编号序列行锁 | case_number_seqs | SELECT ... FOR UPDATE |
| 密码加密 | projects.test_object_password | property 自动加解密 |
| 认证配置加密 | requirement_links.auth_config | property 自动加解密 |
| ReviewLock 过期 | review_lock.expires_at | 默认 24 小时 |
| Token 预算控制 | ai_call_log | check_budget() 检查 |

---

## 五、权限体系

### 5.1 RBAC 权限模型

```
User ←→ Role ←→ Permission (树形)
  │        ↑
  └──→ Group ←→ Role
```

### 5.2 Pipeline 独立权限体系

```
PipelineRole (admin/qa_lead/qa_engineer/viewer)
    └──→ PipelinePermission (resource × action × scope)
            └──→ User (通过 pipeline_user_role, 含 project_id)
```

**Pipeline 资源类型**: iteration/pipeline/review/test_case/report/config

**Pipeline 操作类型**: create/read/update/delete/start/approve/reject/finalize/cancel

**Pipeline 范围**: own/project/all

### 5.3 前端权限控制

- 路由 meta.permission: 控制页面访问
- 自定义指令 `v-permission`: 控制按钮级权限

---

## 六、通信机制

### 6.1 REST API

- 基础路径: `/api/v1/`
- 认证: Bearer Token (Authorization header)
- 统一响应格式: `{code, message, data}`

### 6.2 SSE (Server-Sent Events)

- 用途: 测试点分析、用例生成、Xmind 导入
- 消息格式: `{type: progress/result/error, data: ...}`

### 6.3 WebSocket

- 用途: 测试执行进度、Pipeline 进度
- 路径: `/api/v1/ws/pipeline/{run_id}`, `/api/v1/ws/execution/{task_id}`

---

## 七、安全机制

### 7.1 认证安全

| 机制 | 说明 |
|------|------|
| JWT 令牌 | 480 分钟有效期 |
| 密码哈希 | bcrypt |
| 账户锁定 | 5 次失败后锁定 30 分钟 |
| 验证码 | IP 级别限流 |

### 7.2 数据安全

| 机制 | 说明 |
|------|------|
| 密码加密存储 | 项目环境密码、需求链接认证配置 |
| 脱敏返回 | API 返回时密码字段脱敏 |
| SQL 注入防护 | 参数化查询 |
| CORS | 根据环境动态配置 |

### 7.3 限流

| 环境 | 限流策略 |
|------|----------|
| 生产 | 1000 次/分钟 |
| 开发 | 5000 次/分钟 |

---

## 八、边界情况与异常场景

### 8.1 并发场景

| 场景 | 处理机制 |
|------|----------|
| 用例编号并发分配 | `case_number_seqs` 行级锁 |
| 定位器并发更新 | 乐观锁 version 字段 |
| 评审并发修改 | ReviewLock 锁定机制 |
| Pipeline 重复触发 | `input_hash` 幂等校验 |
| 生成批次重复保存 | `idempotency_key` + `request_hash` |

### 8.2 数据一致性

| 场景 | 处理机制 |
|------|----------|
| 项目删除级联 | CASCADE 删除所有子表 |
| 用例软删除 | `is_deleted` 标记，不影响关联数据 |
| 版本快照一致性 | before_flush hook 自动创建 |
| 审计日志不可变 | before_flush hook 拦截修改 |

### 8.3 AI 服务异常

| 场景 | 处理机制 |
|------|----------|
| AI 调用超时 | 180 秒超时配置 |
| AI 返回格式错误 | JSON 修复器 + 降级 |
| Token 预算超限 | Pipeline 暂停等待确认 |
| AI 模型不可用 | Fallback 客户端降级 |
| AI 生成质量低 | QualityGate 拦截 + 后验评分 |

### 8.4 执行异常

| 场景 | 处理机制 |
|------|----------|
| 元素定位失败 | 自愈策略（多优先级定位器） |
| 页面加载超时 | 可配置超时时间 |
| 设备断连 | ADB 重连机制 |
| 执行中断 | 协作式取消 + 中断恢复(F9) |

---

## 九、接口鉴权规则汇总

| 接口类别 | 鉴权要求 |
|----------|----------|
| 登录/注册/验证码 | 无需认证 |
| 公开查询接口 | Bearer 令牌 |
| 项目级操作 | 项目所有者 |
| 用户管理 | 自己或管理员 |
| 角色/权限管理 | 超级管理员 |
| 审计日志 | Pipeline 管理员 |
| 撤销最终化 | 管理员 |
| 超级管理员操作 | `is_superuser=True` |

---

## 十、测试用例生成指引

本文档作为生成全面测试用例的依据，建议按以下维度覆盖：

### 10.1 功能测试

- 每个功能点的正常流程（正向用例）
- 每个功能点的异常流程（逆向用例）
- 边界值测试（空值、最大长度、最小值等）
- 必填/选填字段校验

### 10.2 状态机测试

- 每个状态机的合法流转路径
- 非法状态流转（应被拒绝）
- 状态机的并发安全

### 10.3 权限测试

- 未认证访问
- 无权限访问
- 越权访问（跨项目、跨角色）
- 超级管理员特权

### 10.4 并发测试

- 用例编号并发分配
- 定位器并发更新
- 评审并发修改
- Pipeline 重复触发
- 生成批次重复保存

### 10.5 数据一致性测试

- 项目删除级联
- 用例软删除/恢复
- 版本快照一致性
- 审计日志不可变性

### 10.6 AI 服务测试

- AI 生成正常流程
- AI 超时/失败处理
- Token 预算控制
- 降级/Fallback 机制
- SSE 流式通信中断

### 10.7 执行引擎测试

- 多种执行模式
- 元素定位失败自愈
- 执行暂停/恢复/停止
- 视频录制与回放
- ADB 设备管理

### 10.8 安全测试

- SQL 注入
- XSS
- CSRF
- 敏感数据泄露
- 限流验证

### 10.9 性能测试

- 大量用例批量操作
- 并发 AI 生成
- Pipeline 大规模运行
- WebSocket 连接稳定性
