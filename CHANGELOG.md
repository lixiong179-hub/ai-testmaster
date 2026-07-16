# Changelog

所有项目的显著变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added - 新增功能

#### 前端
- **FlowSortEditor.vue** - 流程图排序编辑器组件
  - 集成 `@vue-flow/core`，支持节点拖拽、连线、条件编辑
  - 支持线性/流程图模式切换（回滚开关）
  - 自动布局算法（主干横向、分支纵向）
  - Prompt 预览功能（输出到控制台）
- **FlowNodeCard.vue** - 流程图节点卡片组件
  - 显示截图缩略图、屏幕名称、OCR摘要
  - 流程类型标签（主干/分支/异常/旁路）可切换
  - 图片加载错误回退处理
- **EdgeConditionDialog.vue** - 连线条件弹窗组件
  - 支持4种连线类型（正常/分支/异常/旁路）
  - 动态条件输入框（根据类型显示不同标签）
  - 支持编辑已有连线（edgeData 回显）
- **flowSort.ts** - Pinia Store
  - 管理流程图排序状态（nodes/edges/mode）
  - 提供序列化/反序列化方法（toJson/fromJson）
- **@vue-flow 依赖** - `@vue-flow/core@1.48.2` + `@vue-flow/additional-components@1.3.3`
- **@vue/test-utils 依赖** - `@vue/test-utils@2.4.6`（组件测试）

#### 后端
- **FlowSortDataSchema** - 流程图排序数据Schema
  - `FlowNodeSchema`: screen_id/screen_order/flow_type/screen_name/ocr_text/ui_spec_elements/summary
  - `FlowEdgeSchema`: source/target/edge_type/condition/label
  - `FlowSortDataSchema`: nodes/edges/module_info
  - 字段校验：gt=0/min_length/max_length/Literal枚举
- **PromptBuilder** - Prompt构建服务
  - `build_graph_prompt`: 流程图模式Prompt构建（主干/分支/异常/旁路分层）
  - `build_linear_prompt`: 线性模式Prompt构建（复用现有逻辑）
- **FlowTreeMixin** - 流程树构建Mixin
  - `_build_flow_tree`: 通用流程树构建方法
  - `_build_branch_tree`/`_build_exception_tree`/`_build_bypass_tree`: 特定类型流程树
- **API端点改造** - `test_case_ai_enhanced.py`
  - `AIGenerateEnhancedRequest` 新增 `mode`/`flow_sort_data` 参数
  - 非流式端点支持 graph 模式（mode='graph'）
  - 流式端点（SSE）支持 graph 模式
  - 请求体大小限制：nodes≤100, edges≤200

### Changed - 变更

- **ai-generate.vue** - 集成 FlowSortEditor 组件
  - 替换原生拖拽排序为 FlowSortEditor（保留线性模式兼容）
  - 提交数据包含 mode/flow_sort_data
- **case.ts** - API类型定义更新
  - 新增 `FlowNodeSubmitData`/`FlowEdgeSubmitData`/`FlowSortSubmitData`
  - `TestCaseAIEnhancedRequest` 新增 mode/flow_sort_data
- **context_mixin.py** - 上下文构建支持 flow_sort_data
  - `get_context_for_generation` 新增 flow_sort_data 参数
  - 构建 flow_structure/ocr_texts 上下文
  - ui_descriptions 去重处理
- **ai_client_enhanced.py** - 支持 graph_prompt 参数
  - 存在 graph_prompt 时直接使用，否则构建原有 prompt
- **main.ts** - 全局导入 @vue-flow CSS
  - 避免 FlowSortEditor.vue scoped style 中重复导入

### Fixed - 修复

- **线性模式兼容性** - `generate_test_case_enhanced` 不再强制要求 graph_prompt
- **重复方法定义** - 删除 context_mixin.py 中 `_get_file_content` 重复定义
- **重复导入** - 删除 test_case_ai_enhanced.py 中重复 typing 导入
- **代码冗余** - 删除 PromptBuilder 中 `condition` 重复赋值
- **DRY原则** - flow_tree_mixin.py 提取通用 `_build_flow_tree` 方法

### Tests - 测试

- **test_flow_tree_mixin.py** - 13个测试用例
  - 分支/异常/旁路流程树构建
  - 空数据/缺失节点/无效source/target/默认条件
- **test_flow_sort_schema.py** - 26个测试用例
  - FlowNodeSchema/FlowEdgeSchema/FlowSortDataSchema 字段校验
  - 边界值/空值/长度限制/类型限制/数量上限
- **test_prompt_builder.py** - 24个测试用例
  - build_graph_prompt（空数据/主干/全类型/无效source/超长分支）
  - build_linear_prompt/辅助函数
- **test_api_ai_enhanced_graph.py** - 16个测试用例
  - AIGenerateEnhancedRequest Schema校验
  - _build_graph_prompt_data/_build_linear_prompt_data/_format_case_response
- **test_stream_endpoint_stress.py** - 10个测试用例
  - SSE事件流格式验证（graph/linear模式）
  - 并发请求处理（3个同时请求）
  - 大数据量流式请求（50节点/49连线）
  - 异常处理与JSON编码
- **test_scenario_validation.py** - 11个测试用例
  - 10个真实业务场景Prompt质量验证
  - Prompt结构完整性/UI元素描述/生成要求数量
- **EdgeConditionDialog.spec.ts** - 9个测试用例（前端组件）
  - 渲染/条件输入/确认/取消/重置/编辑回显

**测试总计：109个用例全部通过**

### 全系统审计整改 (2026-07-16)

基于全系统审计报告（23 项问题：1 P0 / 7 P1 / 9 P2 / 6 P3），分四批完成整改。

#### Security - 安全加固
- **P0-1 路径遍历修复** - `ui_prototype/helpers.py` 新增 `_sanitize_filename_component()` 白名单清洗 + `screen_endpoints.py` 路径边界校验
- **P2-8 安全响应头中间件** - `app/main.py` 新增 `SecurityHeadersMiddleware`，统一注入 `X-Content-Type-Options`/`X-Frame-Options`/`X-XSS-Protection`/`Referrer-Policy`
- **P1-7 跨项目迭代归属校验** - `app/models/project.py` 添加 `before_flush` 事件守卫，拒绝跨项目的 iteration_id 赋值

#### Performance - 性能优化
- **P1-2/3/4 N+1 查询修复** - `file_content_extractor.py`、`self_test/_pipeline_steps_setup.py`、`case_quality_check.py` 三处循环内查询改为批量 `in_()` 查询
- **P2-2 Dashboard 查询合并** - `pipeline_dashboard/_overview.py` 8 次独立 COUNT/SUM/AVG 查询合并为 4 次（FILTER 子句条件聚合）
- **P2-3 review_inbox 过滤排序下推** - `review_service/_lock.py` `get_decisions()` 新增 verdict/sort_by/order 参数，过滤与排序下推 SQL
- **P1-1/P2-4 分页补齐** - 8 个列表端点统一添加 `page`/`page_size` Query 参数（file_management × 2、history_asset、test_capability、ab_test、review_inbox、prompt_template、feature_flag）

#### API Consistency - API 一致性
- **P1-5 response_model 标准化** - 84 处 `response_model=dict` 替换为 `response_model=ApiResponse`
- **P3-1 路由前缀冲突修复** - `execution_visualization.py` 前缀 `/execution` → `/execution-vis`；前端 `testExecution.ts` 5 个回放控制端点同步更新
- **P1-6 文档路径更新** - 5 个文档文件 19 处过时 API 路径修正

#### Code Quality - 代码规范
- **P3-3 动态导入消除** - `self_test/_pipeline_steps_setup.py` `__import__` 替换为静态 import
- **P3-2 测试类误识别修复** - `app/db/database/_engine.py` Base 类添加 `__test__ = False`
- **P2-6 测试包名冲突修复** - 删除 `tests/scripts/__init__.py` 解决与根 `scripts/` 包的命名冲突

#### Tests - 测试修复
- **P2-9 health 端点测试恢复** - 移除 `test_main.py` 中过时的 skip 标记，10 个测试恢复执行
- **新增 `test_batch1_security_fixes.py`** - 12 个安全修复验证用例（路径遍历 + 跨项目迭代守卫）

#### Deferred - 延后处理
- P2-1 db.run_sync 系统性迁移（100+ 处，按模块逐步迁移）
- P2-5 大文件拆分（execution.py/pipeline.py，架构级重构）
- P2-7 30+ skip 测试清理（需逐个排查重构遗留）
- P3-6 浏览器 eval 低风险项（JavaScript 上下文，非 Python）

### Phase 5 - Defect Discovery & Self-Test Automation (2026-06-03)

#### Database (commit 2ab7dad)
- **alembic 4 步迁移链** - snapshot_nullable → add_defect_evidence → add_ux_category_to_bugs + merge_phase4_heads
- **defect_evidence 表** - 缺陷证据（截图/PDF/日志）
- **bugs.ux_category** - UX 缺陷分类（loading_experience/error_feedback/response_performance/visual_consistency/empty_state/security）
- **test_case_versions.snapshot_data → nullable** - 归档后可置空以省存储
- **设计要点**：ux_category 在应用层用 VALID_UX_CATEGORIES 常量校验（不用 SQL Enum）；add_ux_category 检 information_schema 实现幂等

#### Service & Endpoint (commit 81c8c4d)
- **/api/v1/bugs 端点** - bug 生命周期 + ux_category 感知
- **/api/v1/feature-flag 端点 + 运行时开关服务** - 用于灰度/紧急回滚
- **/api/v1/prompt-template 端点** - 提示词模板管理
- **defect discovery pipeline** - 从浏览器交互到缺陷创建的完整链路
- **self_test_service 增强** - 53 → 1194 行；含 requirement 自动导入、严重度评估、证据打包
- **self_test_prompt + self_test_scheduler** - APScheduler 定时自测
- **structured_assertion_mixin + task_batch_executor_mixin** - 测试执行引擎结构化断言与批量执行
- **browser_controller_base 增强** - 177 行；增加 defect 证据收集/clear 钩子
- **step_executor_mixin** - 每步前后清空/收集 defect 证据
- **report_service 增强** - 290 行；缺陷指标、UX 分布
- **feature_flag_service 修复** - `hash()` → `hashlib.md5()`（修 Python hash 随机化，重启后缓存 key 失效问题）

#### Frontend (commit 8aed1fa)
- **src/views/report/ReportDetail.vue** - 缺陷分布 + ux_category 过滤 + 严重度图表
- **src/api/report.ts** - 缺陷指标 + UX 分布类型
- **src/views/case/smart-generate.vue** - 4 个 API 路径修正（`/api/v1/project/list`、`/api/v1/file/list`、`/api/v1/test-point/list/{id}`、`/api/v1/testCase/`）；`.stop` 事件冒泡修复；币种符号 ¥/$ 互换

#### Docs
- **docs/requirement_specification.md** - 1369 行需求规格说明书（20 模块、状态机、完整性约束、RBAC）。被 self_test_service._auto_import_requirement_doc() 自动消费

#### Tests
- **test_self_test_service.py** - 19 用例（自测项目创建/幂等导入）
- **test_self_test_prompt.py** - 93 用例
- **test_defect_discovery_pipeline.py** - 152 用例
- **test_defect_metrics.py** - 67 用例
- **test_defect_severity_assessment.py** - 38 用例
- **test_browser_defect_capture.py** - 23 用例
- **test_structured_assertion.py** - 45 用例
- **test_feature_flag_api.py** - 33 用例
- **test_video_extended.py** - 39 用例
- **test_remote_pull_risk_fixes.py** - 21 用例
- **test_step_helpers.py + test_models.py** - 32 用例
- **总计：562 个新增/修改用例通过，0 失败**

#### Commits
- `2ab7dad` feat(db): defect discovery + ux_category + snapshot nullable for archive
- `81c8c4d` feat(service): defect discovery pipeline + self-test automation + bug endpoint
- `8aed1fa` feat(frontend): defect metrics UI + smart-generate API path fix + requirement spec

## [1.0.0] - 2026-04-21

### Added
- 项目初始版本
- AI测试用例生成功能
- 需求文档解析
- UI原型图解析
