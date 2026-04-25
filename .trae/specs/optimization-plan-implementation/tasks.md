# Tasks

## M1 · 急救包（P0）

- [ ] Task 1: 重定义 coverage 指标（T1）— 多维覆盖率算法替代单一 locator 覆盖率
  - [ ] SubTask 1.1: 修改 `coverage_mixin.py`，新增 `requirement_coverage` 计算（基于 test_point_id 命中）
  - [ ] SubTask 1.2: 新增 `ui_element_coverage` 计算（基于 target_element 命中 UI Spec elements）
  - [ ] SubTask 1.3: 修改 `analyzer_mixin.py`，传入 project 上下文以获取需求/UI 数据
  - [ ] SubTask 1.4: 实现加权公式 `requirement_coverage × 0.5 + ui_element_coverage × 0.3 + locator_coverage × 0.2`
  - [ ] SubTask 1.5: 实现向后兼容退化逻辑（缺 requirement/ui_spec 时退化为 locator-only）
  - [ ] SubTask 1.6: 修改 `suggestion_mixin._generate_optimization_suggestions`，根据新维度重写建议文案
  - [ ] SubTask 1.7: 修改 `GET /cases/{id}/quality` 返回三维度分解数据
  - [ ] SubTask 1.8: 编写测试用例（正常/空值/异常/边界），覆盖率 ≥ 95%

- [ ] Task 2: 打通 UI 原型 → 测试点提取链路（T2）— 新增服务方法与端点
  - [ ] SubTask 2.1: 在 `ai_analysis_service.py` 新增 `extract_test_points_from_ui_specs(screen_ids)` 方法
  - [ ] SubTask 2.2: 新增端点 `POST /test-point/extract-from-ui`，请求体 `{ project_id, ui_screen_ids[], iteration_id? }`
  - [ ] SubTask 2.3: 新增 UI 提取 Prompt 模板（参考 T7 合流）
  - [ ] SubTask 2.4: 前端 `TestPointExtractDialog.vue` 增加"从 UI 原型提取"Tab
  - [ ] SubTask 2.5: 复用现有测试点预览/保存组件
  - [ ] SubTask 2.6: 编写测试用例，验证"只上传 UI 原型图"场景走通

- [ ] Task 3: 修复批量解析越权风险（T3）— 全量校验 screen_ids 项目归属
  - [ ] SubTask 3.1: 修改 `parse_endpoints.py`，一次性 `SELECT screen_id, project_id FROM ui_prototype_screen WHERE screen_id IN (:ids)`
  - [ ] SubTask 3.2: 断言所有返回行的 `project_id` 等于当前用户项目 ID，不匹配返回 403
  - [ ] SubTask 3.3: 编写安全测试用例（含他人 screen_id 请求返回 403）

- [ ] Task 4: 修复 Windows 下路径白名单（T4）— 配置化路径替代硬编码
  - [ ] SubTask 4.1: 在 `config.py` 新增 `UI_PROTOTYPE_DIR` 配置项（默认 `<project_root>/uploads/ui_prototypes`）
  - [ ] SubTask 4.2: 修改 `core_mixin._read_image_file`，使用 `pathlib.Path.resolve()` 做前缀校验
  - [ ] SubTask 4.3: 编写测试用例（Windows/Linux 路径校验 + 路径穿越防护）

- [ ] Task 5: 合并需求上传入口 + 多文件批量（T5）— 统一上传组件与端点
  - [ ] SubTask 5.1: 后端新增 `POST /file/batch-upload`，服务端按扩展名/MIME 预判 resource_type
  - [ ] SubTask 5.2: 新增 `src/components/RequirementUploader.vue`（支持拖拽 + 批量 + 预览 + resource_type 下拉）
  - [ ] SubTask 5.3: 改造 `project/detail.vue` 引用 RequirementUploader
  - [ ] SubTask 5.4: 改造 `requirement/upload.vue` 引用 RequirementUploader
  - [ ] SubTask 5.5: 改造 `requirement/resource-manage.vue` 引用 RequirementUploader
  - [ ] SubTask 5.6: 编写测试用例（混合类型文件批量上传 + magic 校验不降级）

## M2 · 架构瘦身（P1）

- [ ] Task 6: 合并 endpoints 文件（T6）— 内部组织调整，URL path 不变
  - [ ] SubTask 6.1: `test_point_{core,import,mutate,query}` → `test_point.py` + `test_point_extract.py`
  - [ ] SubTask 6.2: `test_case_ai_{core,context,enhanced,stream,basic}` → `test_case_ai.py` + `test_case_ai_stream.py`
  - [ ] SubTask 6.3: 更新 `main.py` 中 `include_router` 顺序
  - [ ] SubTask 6.4: 验证所有 URL path 不变，回归测试通过

- [ ] Task 7: 统一 PromptBuilder（T7）— 合并 3 处 Prompt 构建逻辑
  - [ ] SubTask 7.1: 新建 `app/services/prompt_builder.py`，定义 `PromptBuilder` 类
  - [ ] SubTask 7.2: 实现 `for_test_case(mode='graph'|'linear')` 入口
  - [ ] SubTask 7.3: 实现 `for_test_point_extraction()` 入口
  - [ ] SubTask 7.4: 实现 `for_ui_extraction()` 入口
  - [ ] SubTask 7.5: 统一 UI Spec 格式化函数（合并 `ai_prompt_builder.py` 和 `case_generation_prompt_builder.py` 中的重复逻辑）
  - [ ] SubTask 7.6: 迁移所有调用方到新 PromptBuilder
  - [ ] SubTask 7.7: 删除旧 Prompt 构建文件（`ai_prompt_builder.py`、`case_generation_prompt_builder.py`、`test_data/prompt_builder.py`）
  - [ ] SubTask 7.8: 编写测试用例，验证各模式 Prompt 输出一致

- [ ] Task 8: 拆分 ai-generate.vue（T8）— 3177 行拆为子组件 + Store
  - [ ] SubTask 8.1: 先写 2 个 E2E 冒烟测试（创建项目→生成→保存）作为回归基线
  - [ ] SubTask 8.2: 新建 `stores/useGenerateStore.ts`（formData / contextPreview / generatedCases 集中管理）
  - [ ] SubTask 8.3: 抽取 `ContextSelectPanel.vue`（需求/UI/测试点选择 + generate-context 调用）
  - [ ] SubTask 8.4: 修改 `FlowSortEditor.vue` 接入 Pinia Store
  - [ ] SubTask 8.5: 抽取 `GeneratePreviewPanel.vue`（流式进度 + 用例编辑保存）
  - [ ] SubTask 8.6: 重构主视图 `ai-generate.vue` ≤ 500 行（仅负责 step 切换和 store 装配）
  - [ ] SubTask 8.7: 运行 E2E 回归测试，确保功能不变

- [ ] Task 9: 删除旧向导页（T9）— 下线冗余页面
  - [ ] SubTask 9.1: 下线 `test-point-extract.vue` 路由与文件
  - [ ] SubTask 9.2: 入口统一为 `test-point-management/ExtractDialog`
  - [ ] SubTask 9.3: 在两个 release 之间加过渡提示

- [ ] Task 10: iteration_id 去哨兵值（T10）— `-1` 归一到 `NULL`
  - [ ] SubTask 10.1: 后端模型改为 `Optional[int]`，None 即"未关联迭代"
  - [ ] SubTask 10.2: 前端发送 `undefined` / 省略字段，不再做 `0→-1` 转换
  - [ ] SubTask 10.3: 数据库迁移：`UPDATE project_file SET iteration_id=NULL WHERE iteration_id=-1`（事务中完成，带唯一迁移版本号）
  - [ ] SubTask 10.4: 编写迁移回滚脚本
  - [ ] SubTask 10.5: 编写测试用例（正常/空值/迁移前后）

## M3 · 体验升级（P2）

- [ ] Task 11: 项目工作台页（T11）— 新增工作台端点与前端页面
  - [ ] SubTask 11.1: 后端新增 `GET /projects/{id}/workspace-summary`（缓存 TTL 30s）
  - [ ] SubTask 11.2: 前端新增工作台页面（需求数、UI 解析进度条、测试点数、用例数、质量分、"下一步建议"按钮）
  - [ ] SubTask 11.3: 编写测试用例

- [ ] Task 12: few-shot 强化 Prompt（T12）— test_data 各类型给示例
  - [ ] SubTask 12.1: 在 PromptBuilder 中为 test_data 的 normal/boundary/abnormal 各给 1 个示例
  - [ ] SubTask 12.2: 验证目标空值率 < 20%

- [ ] Task 13: 冗余度算法升级（T13）— SequenceMatcher → TF-IDF
  - [ ] SubTask 13.1: 实现 TF-IDF 向量化（scikit-learn 已在依赖中则用；否则自写轻量版）
  - [ ] SubTask 13.2: 实现余弦相似度计算
  - [ ] SubTask 13.3: 阈值按项目规模动态调整
  - [ ] SubTask 13.4: 编写测试用例

- [ ] Task 14: 测试点聚类后生成（T14）— 合并相近测试点
  - [ ] SubTask 14.1: 实现 K-means 或层次聚类（共享 T13 向量化）
  - [ ] SubTask 14.2: 相近测试点合并为一条数据驱动用例
  - [ ] SubTask 14.3: 减少 AI 调用数和冗余扣分
  - [ ] SubTask 14.4: 编写测试用例

- [ ] Task 15: N² 查询修复（T15）— 预取 + 缓存
  - [ ] SubTask 15.1: 修改 `analyze_project_quality`，预取 `all_cases` 传给每次 analyzer
  - [ ] SubTask 15.2: 项目级缓存一次嵌入向量
  - [ ] SubTask 15.3: 编写性能测试用例

- [ ] Task 16: 清理调试产物（T16）— 删除 debug 文件
  - [ ] SubTask 16.1: 删除 `captcha_debug_*.png`、`ai_response_debug.txt`、`ocr_debug.log`
  - [ ] SubTask 16.2: 扩展 `.gitignore`
  - [ ] SubTask 16.3: 可选：用 `git filter-repo` 清历史

- [ ] Task 17: UI 解析进度真 SSE（T17）— 替代前端轮询
  - [ ] SubTask 17.1: `parse_endpoints` 增加 `/stream` 版本
  - [ ] SubTask 17.2: 单屏/批量都推送 progress
  - [ ] SubTask 17.3: 前端换掉 `setInterval` 模拟
  - [ ] SubTask 17.4: 编写测试用例

- [ ] Task 18: action_type 中英文/同义词（T18）— 关键词表扩展
  - [ ] SubTask 18.1: 扩展 `infer_action_type` + `steps_mixin` 的关键词表（中英文 + 同义词）
  - [ ] SubTask 18.2: 示例：open/打开/跳转 → navigate
  - [ ] SubTask 18.3: 编写单测覆盖

- [ ] Task 19: flow_sort token 保护（T19）— nodes 超阈值概要化
  - [ ] SubTask 19.1: PromptBuilder 在 `nodes > 阈值（如 15）` 时做概要化
  - [ ] SubTask 19.2: 保留主流程完整，分支/异常只保留名称
  - [ ] SubTask 19.3: 编写测试用例

- [ ] Task 20: precondition 语义放宽（T20）— 识别"登录是被测功能"场景
  - [ ] SubTask 20.1: 识别需求文档含"注册"/"登录"等关键词的场景
  - [ ] SubTask 20.2: 此时 AI 允许把登录写成可测步骤
  - [ ] SubTask 20.3: 输出校验层兼容两种模式
  - [ ] SubTask 20.4: 编写测试用例

# Task Dependencies

## M1 内部依赖
- T1、T2、T3、T4、T5 可并行（无前置依赖）
- T5 建议先做 T10（消除 iteration_id 哨兵值），但非强制

## M2 依赖 M1
- T6、T7、T8、T9、T10 依赖 M1 完成
- T5 前置于 T8（上传组件拆分需要统一入口）
- T6、T7、T8 可并行

## M3 依赖 M2
- T11 依赖 T5（上传组件）和 T1（质量分）
- T12 依赖 T7（PromptBuilder）
- T14 依赖 T13（共享向量化）
- T15 依赖 T1（新算法要查项目级数据）
- T19 依赖 T7（PromptBuilder）
- T20 依赖 T7（PromptBuilder）
- T13、T16、T17、T18 无前置依赖，可提前

## 关键路径
1. 质量闭环：T1 → T15
2. 链路补齐：T2 → T14
3. 前端收敛：T5 → T8 → T11
4. Prompt 统一：T7 → T12/T19/T20
