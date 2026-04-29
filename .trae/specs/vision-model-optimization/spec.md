# 视觉模型使用优化 Spec

## Why

当前项目中视觉模型（VLM）调用成本高、部分场景非必要、且缺乏按需降级策略。UI原型解析强制使用视觉模型，而大部分场景只需提取文字内容即可；AI自愈机制默认开启导致执行成本不可控；视觉模型配置未做性价比优化。需要引入分层降级策略，按需选择视觉模型或OCR+文本结构化方案，降低整体AI调用成本。

## What Changes

- **UI原型解析双模式** — UISpecParser支持 `vision`（视觉模型直接解析）和 `text`（OCR提取文字+LLM结构化）两种模式，默认使用 `text` 模式
- **新增OCR文本提取器** — 集成PaddleOCR作为本地OCR引擎，从UI截图中提取纯文本
- **新增文本结构化Prompt** — 针对OCR提取的纯文本，设计专用Prompt让DeepSeek等纯文本LLM进行页面元素拆解
- **AI自愈默认关闭** — `AI_SELF_HEALING_ENABLED` 默认值改为 `False`，提供明确开关让用户按需启用
- **视觉模型配置优化** — 默认模型降级为 `qwen-vl-plus`（性价比更高），新增 `UI_PARSER_MODE` 配置项
- **清理case_quality_analyzer的视觉调用估算** — 移除无实际作用的 `ai_vision_calls` 估算逻辑
- **前端UI原型解析界面增加模式切换** — 用户可在界面上选择解析模式

## Impact

- Affected specs: ui-prototype-integration, ui-automation-enhancement, batch-locator-optimization
- Affected code:
  - `app/services/ui_spec_parser.py` — 核心改造：支持双模式解析
  - `app/services/ui_spec_parse_pipeline.py` — 传递解析模式配置
  - `app/utils/unified_vision_model.py` — 新增 `analyze_text` 方法（纯文本LLM调用）
  - `app/core/config.py` — 新增 `UI_PARSER_MODE` 配置，修改 `AI_SELF_HEALING_ENABLED` 默认值
  - `app/services/case_quality_analyzer.py` — 清理视觉调用估算
  - `app/services/test_execution_engine_v2.py` — AI自愈默认关闭后的兼容处理
  - `src/views/requirement/ui-prototype.vue` — 前端解析模式切换

## ADDED Requirements

### Requirement: UI原型解析双模式

系统 SHALL 支持两种UI原型解析模式：视觉模型模式（vision）和文本结构化模式（text），默认使用text模式。

#### Scenario: 使用text模式解析UI图
- **GIVEN** 系统配置 `UI_PARSER_MODE=text`
- **WHEN** 用户上传UI原型图进行解析
- **THEN** 系统使用PaddleOCR提取图片中的文字内容
- **AND** 将OCR文本发送给DeepSeek等纯文本LLM进行结构化拆解
- **AND** 返回页面元素列表（type、label、semantic等文字信息）
- **AND** 不包含元素坐标信息（x、y、width、height为0或null）

#### Scenario: 使用vision模式解析UI图
- **GIVEN** 系统配置 `UI_PARSER_MODE=vision`
- **WHEN** 用户上传UI原型图进行解析
- **THEN** 系统使用视觉模型（如qwen-vl-plus）直接解析截图
- **AND** 返回完整的页面元素信息（包含坐标、布局等）
- **AND** 解析精度高于text模式

#### Scenario: 前端切换解析模式
- **GIVEN** 用户在UI原型解析界面
- **WHEN** 用户选择解析模式为"视觉模型解析"
- **THEN** 系统使用vision模式解析
- **AND** 界面提示"视觉模型解析将消耗更多API调用费用"

#### Scenario: text模式解析失败降级
- **GIVEN** 系统使用text模式解析UI图
- **WHEN** OCR提取的文字为空或LLM结构化返回无效结果
- **THEN** 自动降级到vision模式重新解析
- **AND** 记录降级事件日志

### Requirement: OCR文本提取器

系统 SHALL 提供本地OCR文本提取能力，从UI截图中提取文字内容。

#### Scenario: 从UI截图中提取文字
- **GIVEN** 一张包含"用户名"、"密码"、"登录"等文字的登录页截图
- **WHEN** 调用OCR文本提取器
- **THEN** 返回提取的文字列表，包含每行文字及其大致位置信息
- **AND** 文字识别准确率 >= 90%

#### Scenario: OCR引擎不可用时的处理
- **GIVEN** PaddleOCR未安装或初始化失败
- **WHEN** 尝试使用OCR提取文字
- **THEN** 记录错误日志
- **AND** 自动降级到vision模式

### Requirement: 文本结构化Prompt

系统 SHALL 提供专用的文本结构化Prompt，将OCR提取的纯文本转换为结构化页面元素信息。

#### Scenario: 文本结构化解析登录页
- **GIVEN** OCR提取的文字为"用户名\n密码\n登录\n忘记密码\n注册"
- **WHEN** 调用文本结构化LLM
- **THEN** 返回结构化JSON，包含：
  - `elements`: [{"type": "input", "label": "用户名", "semantic": "用户名输入框"}, {"type": "input", "label": "密码", "semantic": "密码输入框"}, {"type": "button", "label": "登录", "semantic": "登录提交按钮"}, ...]
  - `screen_name`: "登录页面"
  - `purpose`: "用户登录系统"

#### Scenario: 文本结构化解析表单页
- **GIVEN** OCR提取的文字为"产品名称\n产品编号\n产品类型\n提交\n重置"
- **WHEN** 调用文本结构化LLM
- **THEN** 返回结构化JSON，正确区分输入框和按钮

### Requirement: AI自愈默认关闭

系统 SHALL 将AI自愈功能默认设为关闭状态，用户可按需启用。

#### Scenario: 默认不启用AI自愈
- **GIVEN** 用户未修改任何配置
- **WHEN** 测试执行引擎初始化
- **THEN** `AI_SELF_HEALING_ENABLED` 为 `False`
- **AND** 元素定位失败时不触发AI自愈流程
- **AND** 直接标记步骤失败

#### Scenario: 用户启用AI自愈
- **GIVEN** 用户在配置中设置 `AI_SELF_HEALING_ENABLED=True`
- **WHEN** 测试执行引擎初始化
- **THEN** 启用AI自愈功能
- **AND** 元素定位失败时触发AI视觉识别兜底

### Requirement: 视觉模型配置优化

系统 SHALL 优化视觉模型默认配置，降低使用成本。

#### Scenario: 默认使用性价比更高的模型
- **GIVEN** 用户未配置视觉模型
- **WHEN** 系统初始化默认视觉模型
- **THEN** 使用 `qwen-vl-plus` 而非 `qwen3-vl-flash`
- **AND** `qwen-vl-plus` 单次调用成本约为 `qwen3-vl-flash` 的50%

#### Scenario: UI解析模式可配置
- **GIVEN** 管理员在 `.env` 中设置 `UI_PARSER_MODE=text`
- **WHEN** 系统启动
- **THEN** UI原型解析默认使用text模式
- **AND** 可通过 `UI_PARSER_MODE=vision` 切换为视觉模型模式

## MODIFIED Requirements

### Requirement: UISpecParser解析流程

**原实现**: 仅支持视觉模型解析，所有UI截图必须通过VLM处理

**修改后**:
- 支持双模式解析（vision/text）
- 默认使用text模式（OCR+LLM结构化）
- text模式解析失败时自动降级到vision模式
- 构造函数新增 `parse_mode` 参数
- 新增 `_extract_text_with_ocr` 方法
- 新增 `_structure_text_with_llm` 方法
- 新增 `TEXT_STRUCTURE_PROMPT` 类常量

### Requirement: UnifiedVisionModel纯文本调用

**原实现**: 仅支持图片+文字的多模态调用（`analyze_image`）

**修改后**:
- 新增 `analyze_text` 方法，支持纯文本LLM调用（不传图片，仅传文字prompt）
- 用于text模式的LLM结构化解析
- 复用已有的API请求基础设施（重试、错误处理等）

### Requirement: case_quality_analyzer成本估算

**原实现**: 包含 `ai_vision_calls` 估算字段，计算需要视觉模型调用的步骤数，但无实际作用

**修改后**:
- 移除 `ai_vision_calls` 字段
- 移除 `need_vision_steps` 计算逻辑
- 移除基于 `ai_vision_calls` 的成本估算
- 保留其他有效的质量分析维度

## REMOVED Requirements

### Requirement: UI原型解析强制使用视觉模型

**Reason**: 视觉模型成本高且大部分场景只需文字信息，OCR+LLM结构化方案可覆盖80%场景

**Migration**: 默认切换为text模式，需要精确布局信息的用户可手动切换为vision模式
