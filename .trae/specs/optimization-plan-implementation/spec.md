# ai-testmaster 优化计划实施 Spec

## Why

基于前次评估发现的 20 个问题，项目存在三大类缺陷：P0 级安全/兼容性/核心链路断裂、P1 级代码架构腐化（巨型组件/重复逻辑）、P2 级体验与质量评估不完善。当前 `ai-generate.vue` 达 3177 行严重超标、`coverage_mixin.py` 仅 48 行导致质量分永久偏低、Prompt 构建逻辑分散在 3 处、批量解析存在越权风险、Windows 路径白名单硬编码失效。需要按 M1→M2→M3 三阶段逐步修复。

## What Changes

### M1 · 急救包（P0）
- **T1** 重定义 coverage 指标 — 多维覆盖率算法替代单一 locator 覆盖率
- **T2** 打通 UI 原型 → 测试点提取链路 — 新增 `extract_test_points_from_ui_specs` 服务方法与新端点
- **T3** 修复批量解析越权风险 — 全量校验 screen_ids 项目归属
- **T4** 修复 Windows 下路径白名单 — 引入 `settings.UI_PROTOTYPE_DIR` 替代硬编码
- **T5** 合并需求上传入口 + 多文件批量 — 新增 `RequirementUploader.vue` 组件与批量上传端点

### M2 · 架构瘦身（P1）
- **T6** 合并 endpoints 文件 — test_point/test_case_ai 子模块内部合并
- **T7** 统一 PromptBuilder — 新建 `app/services/prompt_builder.py`，合并 3 处 Prompt 构建逻辑
- **T8** 拆分 ai-generate.vue — 拆为 ContextSelectPanel / FlowSortEditor / GeneratePreviewPanel + useGenerateStore
- **T9** 删除旧向导页 — 下线 `test-point-extract.vue` 路由与文件
- **T10** iteration_id 去哨兵值 — `-1` 归一到 `NULL`，前端发送 `undefined`

### M3 · 体验升级（P2）
- **T11** 项目工作台页 — 新增 `/projects/{id}/workspace-summary` 端点与前端工作台
- **T12** few-shot 强化 Prompt — test_data 各类型给示例，目标空值率 < 20%
- **T13** 冗余度算法升级 — SequenceMatcher → TF-IDF
- **T14** 测试点聚类后生成 — K-means/层次聚类合并相近测试点
- **T15** N² 查询修复 — 预取 all_cases + 项目级缓存嵌入向量
- **T16** 清理调试产物 — 删除 debug 文件，扩展 .gitignore
- **T17** UI 解析进度真 SSE — 新增 `/stream` 版本替代前端轮询
- **T18** action_type 中英文/同义词 — 关键词表扩展
- **T19** flow_sort token 保护 — nodes > 阈值时概要化
- **T20** precondition 语义放宽 — 识别"登录是被测功能"场景

## Impact

- Affected specs: 所有已有 spec（coverage_mixin、prompt_builder、ui_prototype 等均需修改）
- Affected code:
  - 后端: `app/services/case_quality/`、`app/services/ai_analysis_service.py`、`app/api/v1/endpoints/`、`app/services/ui_spec_parser/`、`app/core/config.py`、`app/services/case_generation_prompt_builder.py`、`app/services/test_case_generation/ai_prompt_builder.py`、`app/services/test_data/prompt_builder.py`、`app/models/`
  - 前端: `src/views/case/ai-generate.vue`、`src/views/case/test-point-management/`、`src/views/project/detail.vue`、`src/views/requirement/upload.vue`、`src/views/requirement/resource-manage.vue`

## ADDED Requirements

### Requirement: 多维覆盖率算法（T1）

系统 SHALL 使用多维覆盖率算法替代单一 locator 覆盖率计算。

#### Scenario: 计算多维覆盖率
- **GIVEN** 项目包含需求文档、UI 原型、测试用例
- **WHEN** 系统计算用例覆盖率
- **THEN** 覆盖率 = `requirement_coverage × 0.5 + ui_element_coverage × 0.3 + locator_coverage × 0.2`
- **AND** `requirement_coverage` 基于测试点（test_point_id）命中计算
- **AND** `ui_element_coverage` 基于用例步骤 `target_element` 命中 UI Spec elements 计算
- **AND** `locator_coverage` 保留原逻辑，权重下调到 0.2

#### Scenario: 向后兼容退化
- **GIVEN** 项目缺少需求文档或 UI Spec
- **WHEN** 系统计算覆盖率
- **THEN** 缺失维度权重归零，剩余维度按比例重新分配
- **AND** 旧用例重新跑分不崩溃

#### Scenario: 质量分不再永久偏低
- **GIVEN** AI 新生成、尚未做批量定位的用例
- **WHEN** 计算综合质量分
- **THEN** 综合分应 ≥ 70（旧逻辑下固定 ≤ 60）

### Requirement: UI 原型测试点提取（T2）

系统 SHALL 支持从 UI 原型图提取测试点。

#### Scenario: 仅上传 UI 原型图提取测试点
- **GIVEN** 项目只上传了 UI 原型图，未上传需求文档
- **WHEN** 用户在 ExtractDialog 选择"从 UI 原型提取"
- **THEN** 系统遍历 `UIPrototypeScreen.ui_spec`，按"页面 × 可交互元素 × 流程边"三维生成测试点建议
- **AND** 返回 ≥ 5 条测试点建议

#### Scenario: 新端点调用
- **GIVEN** 用户发起 `POST /test-point/extract-from-ui`
- **WHEN** 请求体包含 `{ project_id, ui_screen_ids[], iteration_id? }`
- **THEN** 系统复用现有流式响应（SSE）模板返回测试点

#### Scenario: 测试点保存后进入 batch 生成
- **GIVEN** UI 原型提取的测试点已保存
- **WHEN** 用户进入 ai-generate 的 batch 生成流程
- **THEN** 流程正常完成

### Requirement: 批量解析越权修复（T3）

系统 SHALL 对批量解析请求中的所有 screen_ids 进行项目归属校验。

#### Scenario: 夹带他人 screen_id
- **GIVEN** 用户发起批量解析请求，screen_ids 中包含他人项目的 screen_id
- **WHEN** 系统校验项目归属
- **THEN** 返回 403 Forbidden

#### Scenario: 正常批量解析
- **GIVEN** 用户发起批量解析请求，所有 screen_ids 属于当前用户项目
- **WHEN** 系统校验项目归属
- **THEN** 全部通过校验，正常执行解析

### Requirement: Windows 路径白名单修复（T4）

系统 SHALL 使用配置化路径替代硬编码路径白名单。

#### Scenario: Windows 下路径校验
- **GIVEN** 项目运行在 Windows 环境
- **WHEN** `_read_image_file` 校验文件路径
- **THEN** 使用 `settings.UI_PROTOTYPE_DIR`（默认 `<project_root>/uploads/ui_prototypes`）做前缀校验
- **AND** 使用 `pathlib.Path.resolve()` 替代字符串比对

#### Scenario: 路径穿越防护
- **GIVEN** 请求包含路径穿越尝试（如 `../../etc/passwd`）
- **WHEN** 系统校验文件路径
- **THEN** 请求被拦截

### Requirement: 合并需求上传入口（T5）

系统 SHALL 提供统一的多文件批量上传组件和端点。

#### Scenario: 混合类型文件批量上传
- **GIVEN** 用户拖入 10 个混合类型文件（doc/pdf/png）
- **WHEN** 用户提交上传
- **THEN** 一次请求上传完成，resource_type 自动识别正确
- **AND** magic 校验、路径隔离、size 限制等校验规则不降级

#### Scenario: 三个页面上传一致
- **GIVEN** 用户在 detail.vue / upload.vue / resource-manage.vue 上传文件
- **WHEN** 使用上传功能
- **THEN** UI 视觉一致、表现一致
- **AND** 均使用 `RequirementUploader.vue` 组件

### Requirement: 统一 PromptBuilder（T7）

系统 SHALL 提供统一的 PromptBuilder 替代分散的 3 处 Prompt 构建逻辑。

#### Scenario: 构建测试用例 Prompt
- **GIVEN** 调用方请求生成测试用例
- **WHEN** 使用 `builder.for_test_case(mode='graph'|'linear').with_requirement(req).with_ui_specs(specs).with_test_points(points).with_flow(nodes, edges).build()`
- **THEN** 返回 `{prompt, weight_hint}`
- **AND** UI Spec 格式化函数唯一

#### Scenario: 构建测试点提取 Prompt
- **GIVEN** 调用方请求提取测试点
- **WHEN** 使用 `builder.for_test_point_extraction()`
- **THEN** 返回测试点提取专用 Prompt

#### Scenario: 构建 UI 提取 Prompt
- **GIVEN** 调用方请求从 UI 原型提取
- **WHEN** 使用 `builder.for_ui_extraction()`
- **THEN** 返回 UI 提取专用 Prompt

### Requirement: 拆分 ai-generate.vue（T8）

系统 SHALL 将 ai-generate.vue（3177 行）拆分为多个子组件和 Store。

#### Scenario: 主视图行数达标
- **GIVEN** ai-generate.vue 拆分完成
- **WHEN** 统计主视图行数
- **THEN** 主视图 ≤ 500 行，仅负责 step 切换和 store 装配

#### Scenario: 子组件拆分
- **GIVEN** 拆分完成
- **WHEN** 查看组件结构
- **THEN** 包含 ContextSelectPanel.vue、FlowSortEditor.vue（已有）、GeneratePreviewPanel.vue
- **AND** stores/useGenerateStore.ts 管理 formData / contextPreview / generatedCases

### Requirement: iteration_id 去哨兵值（T10）

系统 SHALL 将 iteration_id 的哨兵值 `-1` 归一到 `NULL`。

#### Scenario: 后端处理
- **GIVEN** 前端发送 `iteration_id=undefined` 或省略字段
- **WHEN** 后端接收请求
- **THEN** 后端将 `iteration_id` 存储为 `NULL`（`Optional[int]`，None 即"未关联迭代"）

#### Scenario: 数据库迁移
- **GIVEN** 现有数据中存在 `iteration_id=-1`
- **WHEN** 执行数据库迁移
- **THEN** `UPDATE project_file SET iteration_id=NULL WHERE iteration_id=-1`
- **AND** 迁移在事务中完成，带唯一迁移版本号

### Requirement: 项目工作台页（T11）

系统 SHALL 提供项目工作台页面，展示项目概览和下一步建议。

#### Scenario: 工作台数据展示
- **GIVEN** 用户进入项目工作台
- **WHEN** 页面加载
- **THEN** 展示需求数、UI 解析进度条、测试点数、用例数、质量分、"下一步建议"按钮

#### Scenario: 工作台摘要端点
- **GIVEN** 前端请求 `GET /projects/{id}/workspace-summary`
- **WHEN** 后端返回数据
- **THEN** 数据包含项目统计摘要
- **AND** 端点有缓存（TTL 30s）

### Requirement: 冗余度算法升级（T13）

系统 SHALL 将冗余度算法从 SequenceMatcher 升级为 TF-IDF。

#### Scenario: TF-IDF 冗余检测
- **GIVEN** 项目存在多条测试用例
- **WHEN** 系统计算冗余度
- **THEN** 使用 TF-IDF 向量化 + 余弦相似度
- **AND** 阈值按项目规模动态调整

### Requirement: N² 查询修复（T15）

系统 SHALL 修复 `analyze_project_quality` 中的 N² 查询问题。

#### Scenario: 批量预取
- **GIVEN** 项目质量分析需要遍历所有用例
- **WHEN** 执行 `analyze_project_quality`
- **THEN** 预取 `all_cases` 传给每次 analyzer
- **AND** 项目级缓存一次嵌入向量

### Requirement: UI 解析进度真 SSE（T17）

系统 SHALL 提供 UI 解析进度的真实 SSE 推送。

#### Scenario: SSE 进度推送
- **GIVEN** 用户发起 UI 原型解析
- **WHEN** 解析进行中
- **THEN** 后端通过 SSE 推送 progress 事件
- **AND** 前端换掉 setInterval 模拟

## MODIFIED Requirements

### Requirement: 覆盖率计算

**原实现**: `coverage_mixin._analyze_coverage` 仅基于 `ElementLocator.step_id` 命中数计算覆盖率，权重占综合分 40%

**修改后**: 多维覆盖率 = `requirement_coverage × 0.5 + ui_element_coverage × 0.3 + locator_coverage × 0.2`，向后兼容退化

### Requirement: iteration_id 处理

**原实现**: 前端发送 `iteration_id=0` 表示"未分类"，后端转为 `-1` 存储

**修改后**: 前端发送 `undefined` 或省略字段，后端存储为 `NULL`（`Optional[int]`）

### Requirement: 文件上传

**原实现**: 单文件上传，三个独立入口（detail.vue / upload.vue / resource-manage.vue），不会自动识别 resource_type

**修改后**: 统一 `RequirementUploader.vue` 组件，支持多文件批量上传，服务端按扩展名/MIME 预判 resource_type

## REMOVED Requirements

### Requirement: 旧向导页 test-point-extract.vue

**Reason**: 入口已统一为 test-point-management/ExtractDialog，旧页面冗余
**Migration**: 在两个 release 之间加过渡提示，然后下线路由与文件

## 项目开发规范约束

本优化计划实施过程中必须遵守以下项目开发规范：

1. **代码风格**: 变量函数 lowerCamelCase，类 UpperCamelCase，常量 UPPER_SNAKE_CASE；4 空格缩进，行宽 ≤ 120
2. **语言规范**: Python 强制类型注解，IO 统一 with 管理，字符串只用 f-string；TS 禁用 any，强制空值处理
3. **架构设计**: 单文件 ≤ 300 行（T8 主视图放宽至 ≤ 500 行）；依赖构造函数注入；新增模块遵循项目现有结构
4. **安全红线**: SQL 仅用参数化/列表传参；密钥禁用硬编码；所有外部输入必须经过模型校验
5. **性能要求**: 禁止循环内执行 SQL；批量写入使用 batch；高频查询优先 Set/Map
6. **测试规范**: 核心分支覆盖率 ≥ 95%；配套正常、空值、异常、边界用例；真实测试库
7. **AI 生成约束**: 禁止 TODO 与空占位；IO/网络/解析强制异常捕获；深层属性空安全兜底
8. **修复与合并**: Bug 修复定位根因；合并需全量测试、类型检查无错；库表变更附带迁移与回滚

## 风险与回滚预案

| 风险项 | 影响 | 回滚预案 |
|--------|------|----------|
| T1 历史质量分变化 | 用户困惑 | 保留旧分段快照，UI 标注"评分算法已升级" |
| T10 数据库迁移 | 数据丢失风险 | 事务中完成，带唯一迁移版本号 |
| T5 批量上传绕过 magic 校验 | 安全风险 | 对接 CI 文件类型扫描 |
| T6 合并 endpoints 不改 URL path | router 顺序 | 注意 main.py 里 include_router 顺序 |
| T8 大改前端组件 | 回归风险 | 先写 E2E 冒烟测试作为回归基线 |
| T11 工作台 summary 端点 | DB 压力 | 缓存 TTL 30s |
