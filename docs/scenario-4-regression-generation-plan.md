# 场景 4：旧项目变更生成开发任务计划

## 1. 背景

当前“AI生成测试用例”页面主要走普通增强生成链路：

```text
src/views/case/ai-generate.vue
-> src/store/useGenerateStore.ts
-> POST /api/v1/test-case/ai-enhanced-generate
```

该链路适合基于需求、UI、测试点快速生成新测试用例草稿，但不执行场景 4 Pipeline，因此不会完整维护旧项目变更场景下的历史用例关系。

场景 4 的目标是处理：

```text
旧项目历史用例 + 新 UI 原型变更 + 新功能迭代 + 旧页面重构
```

应走 Pipeline 场景 4：

```text
POST /api/v1/pipeline/iteration/{iteration_id}/run
Body: { "scenario": 4 }
```

场景 4 会执行：

```text
SignalGatherer
-> HistoryFingerprint
-> TestPointAlignment
-> BackwardScan
-> ScenarioCandidateExtractor
-> ForwardScan
-> Reconciliation
-> CaseGeneration
-> QualityGate
-> Persist
```

## 2. 总体目标

新增一个面向旧项目变更的正式生成入口，使用户在上传并解析新 UI 原型后，可以基于当前项目历史用例自动执行场景 4 回归分析与用例生成。

核心目标：

- 新增“旧项目变更生成 / 场景 4”入口。
- 前端不要求用户逐条选择旧用例，历史用例由后端自动扫描。
- 页面展示本次参与扫描的数据范围。
- 启动后调用 Pipeline 场景 4，而不是普通 AI 增强生成接口。
- Pipeline 运行后跳转进度页。
- 支持 `waiting_for_user` 人工确认流程。
- 最终能看到新增、修改、废弃、冲突等分析结果。

## 3. 非目标

本阶段不做以下内容：

- 不重构普通 AI 生成链路。
- 不要求用户手动逐条选择旧用例。
- 不做复杂的历史用例多维筛选器。
- 不实现完整可视化 Reconciliation 矩阵大屏。
- 不替换现有 `ai-enhanced-generate` 接口。

## 4. 推荐产品形态

建议新增独立入口：

```text
旧项目变更分析 / 回归生成
```

入口位置可选：

- UI 原型管理页面：解析完成后提供“基于此原型做旧项目变更分析”。
- AI 生成测试用例页面：增加“生成模式：普通生成 / 旧项目变更生成”。
- 迭代详情页：增加“启动场景 4 Pipeline”。

推荐优先入口：

```text
src/views/requirement/ui-prototype.vue
```

原因：用户刚上传并解析新 UI，最自然的下一步就是基于新 UI 做旧项目变更分析。

## 5. 数据流设计

### 5.1 普通生成现有链路

```text
选择资源和测试点
-> generate-context
-> ai-enhanced-generate
-> 前端预览
-> 手动保存
```

该链路不维护旧用例变更关系。

### 5.2 新增场景 4 链路

```text
选择项目
-> 选择已解析 UI 原型 / 屏幕
-> 选择或创建 Iteration
-> 写入 IterationInput(kind="prototype")
-> 可选写入 IterationInput(kind="prd")
-> 可选写入 IterationInput(kind="testpoint")
-> 展示扫描范围
-> POST /api/v1/pipeline/iteration/{iteration_id}/run { scenario: 4 }
-> 跳转 PipelineProgress
-> completed 或 waiting_for_user
```

## 6. 前端任务

### FE-01 新增旧项目变更入口

优先级：P0

涉及文件：

```text
src/views/requirement/ui-prototype.vue
src/router/index.ts
```

任务说明：

- 在 UI 原型解析完成状态下增加按钮：

```text
旧项目变更分析
```

- 按钮可出现在：
  - 原型项目卡片操作区。
  - 已解析屏幕列表操作区。
  - 页面顶部批量操作区。

点击后进入新页面或弹窗。

建议路由：

```text
/home/iteration/regression-generate
```

查询参数示例：

```text
project_id=1&ui_project_id=10
```

验收标准：

- 已解析 UI 原型显示入口。
- 未解析或解析失败 UI 原型不允许启动，提示用户先解析。
- 能携带 `project_id` 和 UI 原型上下文进入下一步。

### FE-02 新增旧项目变更生成页面

优先级：P0

建议新文件：

```text
src/views/iteration/RegressionGenerate.vue
```

页面模块：

1. 项目信息区。
2. 新 UI 原型信息区。
3. 历史扫描范围区。
4. 迭代选择/创建区。
5. 可选变更说明/PRD 区。
6. 可选测试点区。
7. 启动 Pipeline 按钮。

页面主按钮：

```text
开始旧项目变更分析
```

验收标准：

- 页面能展示当前项目。
- 页面能展示已选择的新 UI 原型或屏幕数量。
- 页面能展示历史用例统计。
- 用户能选择已有迭代或创建新迭代。
- 点击启动后调用场景 4 Pipeline。

### FE-03 展示历史扫描范围

优先级：P0

需要后端统计接口支持，见 BE-01。

展示内容：

```text
历史用例总数
参与扫描用例数
active 用例数
draft 用例数
pending_review 用例数
archived 排除数
已删除排除数
历史测试点数量
新 UI 已解析页面数
新 UI 未解析页面数
```

提示文案：

```text
场景 4 会自动扫描当前项目下非 archived、未删除的历史用例，不需要手动逐条选择旧用例。
```

验收标准：

- 用户能清楚知道历史用例会自动参与扫描。
- 如果参与扫描用例数为 0，禁止启动场景 4，并提示改用新项目场景。
- 如果已解析 UI 页面数为 0，禁止启动。

### FE-04 迭代输入写入

优先级：P0

目标：启动 Pipeline 前确保 Iteration 已挂载输入。

需要支持写入：

```json
{
  "kind": "prototype",
  "payload": {
    "screen_ids": [1, 2, 3]
  }
}
```

可选写入：

```json
{
  "kind": "prd",
  "file_id": 100
}
```

可选写入：

```json
{
  "kind": "testpoint",
  "payload": {
    "test_point_ids": [11, 12, 13]
  }
}
```

验收标准：

- 用户启动前，系统能创建或选择一个 `Iteration`。
- 新 UI 屏幕 ID 被写入 `IterationInput(kind="prototype")`。
- 如选择测试点，测试点 ID 被写入 `IterationInput(kind="testpoint")`。
- 如选择 PRD，文件 ID 被写入 `IterationInput(kind="prd")`。

### FE-05 调用 Pipeline 场景 4

优先级：P0

调用接口：

```text
POST /api/v1/pipeline/iteration/{iteration_id}/run
```

请求体：

```json
{
  "scenario": 4
}
```

成功后跳转：

```text
/home/case/pipeline/{pipeline_run_id}
```

验收标准：

- 不再调用 `/api/v1/test-case/ai-enhanced-generate`。
- 返回 `pipeline_run_id` 后跳转进度页。
- Pipeline 状态为 `completed` 或 `waiting_for_user` 时页面能正确展示。

### FE-06 支持 waiting_for_user 人工确认

优先级：P1

现有页面：

```text
src/views/iteration/PipelineProgress.vue
src/components/ConfirmationDialog.vue
```

任务说明：

- 检查 `PipelineProgress.vue` 是否能展示 `pause_payload`。
- 如果 `status = waiting_for_user`，展示确认弹窗。
- 用户确认后调用：

```text
POST /api/v1/pipeline/{run_id}/resume
```

请求体：

```json
{
  "confirmation_payload": {
    "confirmed": true,
    "notes": "确认继续生成新增和变更用例"
  }
}
```

验收标准：

- 测试点与 UI 对齐冲突时，页面能展示人工确认。
- 用户确认后 Pipeline 能继续执行。

### FE-07 结果摘要展示

优先级：P1

在 Pipeline 完成后，展示：

```text
新增用例 ADD_NEW 数量
需修改 NEEDS_MODIFY 数量
定位失效 LOCATOR_BROKEN 数量
废弃 DEPRECATE 数量
冲突 CONFLICT 数量
待人工确认 PENDING_REVIEW 数量
最终落库用例数量
```

数据来源：

- `merged_verdicts` artifact。
- `persisted_case_ids` artifact。
- `quality_scores` artifact。

验收标准：

- 用户能看懂本次变更影响范围。
- 用户能跳转查看生成/变更后的用例。

### FE-00 API 封装与类型定义

优先级：P0

涉及文件：

```text
src/api/pipeline.ts
src/api/iteration.ts
```

任务说明：

- 在页面开发前，先补齐前端 API 封装，避免在 Vue 页面中直接散落 `request.get/post`。
- `pipeline.ts` 需要新增或确认：

```ts
precheckScenario4(data)
runPipeline(iterationId, { scenario: 4 })
getPipelineRun(runId)
resumePipeline(runId, payload)
getPipelineSummary(runId)
```

- `iteration.ts` 需要新增或确认：

```ts
createIteration(data)
getIteration(iterationId)
listIterations(projectId)
addIterationInput(iterationId, data)
```

建议类型：

```ts
export interface Scenario4PrecheckRequest {
  project_id: number
  ui_project_id?: number
  screen_ids?: number[]
  iteration_id?: number
  test_point_ids?: number[]
}

export interface Scenario4PrecheckResponse {
  project_id: number
  history_cases: {
    total: number
    included: number
    active: number
    draft: number
    pending_review: number
    archived: number
    deleted: number
  }
  test_points: {
    total: number
    selected: number
  }
  ui: {
    selected_screen_count: number
    parsed_screen_count: number
    unparsed_screen_count: number
    parse_failed_count: number
    usable_screen_ids: number[]
  }
  can_run: boolean
  blocking_reasons: string[]
  warnings: string[]
}
```

验收标准：

- 场景 4 页面只调用统一 API 封装。
- TypeScript 类型覆盖预检、启动、摘要、迭代输入写入。
- 点击启动时调用 Pipeline API，而不是 `/api/v1/test-case/ai-enhanced-generate`。

### FE-08 UI 原型项目到 screen_ids 的转换规则

优先级：P0

任务说明：

- 如果用户选择的是 UI 原型项目，则需要转换为该原型项目下可参与分析的 `screen_ids`。
- 默认规则：

```text
prototype_project_id == 当前选择的 UI 原型项目
parse_status == "completed"
ui_spec is not null
按 screen_order 升序
```

- 如果用户手动选择具体屏幕，则只使用用户选择的屏幕，但仍需过滤：

```text
parse_status == "completed"
ui_spec is not null
```

- 过滤结果写入：

```json
{
  "kind": "prototype",
  "payload": {
    "screen_ids": [1, 2, 3]
  }
}
```

验收标准：

- 选择整个 UI 原型项目时，能自动得到可用 `screen_ids`。
- 未解析、解析失败、`ui_spec` 为空的屏幕不会写入 IterationInput。
- 页面展示过滤结果和 warning，例如“2 个页面未解析，已排除”。

### FE-09 重复输入与重复运行确认

优先级：P1

任务说明：

- 启动前检查当前 `Iteration` 是否已有相同 `prototype` 输入。
- 如果已有相同 `screen_ids`：
  - 默认不重复添加。
  - 提示“该迭代已关联当前 UI 原型输入”。
- 如果已有不同 `prototype` 输入：
  - 询问用户是追加、替换还是取消。
- 如果当前迭代已有 PipelineRun：
  - 询问用户是否重新运行。

提示文案：

```text
该迭代已运行过 Pipeline，重新运行会生成新的 PipelineRun，并可能产生新的用例结果。是否继续？
```

验收标准：

- 不会重复写入完全相同的 IterationInput。
- 重新运行前有明确确认。
- 用户能区分追加 UI 输入和替换 UI 输入。

## 7. 后端任务

### BE-01 新增场景 4 预检统计接口

优先级：P0

建议接口：

```text
POST /api/v1/pipeline/scenario-4/precheck
```

请求体：

```json
{
  "project_id": 1,
  "ui_project_id": 10,
  "screen_ids": [1, 2, 3],
  "iteration_id": 20,
  "test_point_ids": [11, 12]
}
```

返回示例：

```json
{
  "project_id": 1,
  "history_cases": {
    "total": 128,
    "included": 120,
    "active": 110,
    "draft": 5,
    "pending_review": 5,
    "archived": 8,
    "deleted": 0
  },
  "test_points": {
    "total": 35,
    "selected": 2
  },
  "ui": {
    "selected_screen_count": 12,
    "parsed_screen_count": 12,
    "unparsed_screen_count": 0,
    "parse_failed_count": 0,
    "usable_screen_ids": [1, 2, 3]
  },
  "can_run": true,
  "blocking_reasons": [],
  "warnings": []
}
```

校验规则：

- `included == 0` 时 `can_run = false`。
- `parsed_screen_count == 0` 时 `can_run = false`。
- 存在未解析 UI 时给 `warnings`。
- 未选择测试点时不阻断，但返回 warning。
- 跨项目资源访问返回 403 或 404。
- `ui_project_id` 和 `screen_ids` 同时存在时，以 `screen_ids` 为准，但必须校验这些 screen 属于同一项目。

验收标准：

- 前端能展示历史用例扫描范围。
- 前端能在启动前判断是否允许运行场景 4。
- 前端能得到最终可用的 `usable_screen_ids`。
- 接口不会泄露其他项目的历史用例、测试点、UI 原型数据。

### BE-02 确认 IterationInput 创建/更新接口

优先级：P0

现有接口已存在：

```text
POST /api/v1/iteration/{iteration_id}/inputs
```

本任务不是新建接口，而是确认并补充该接口对场景 4 输入的测试覆盖。

需要支持：

```json
{
  "kind": "prototype",
  "file_id": null,
  "payload": {
    "screen_ids": [1, 2, 3]
  }
}
```

验收标准：

- 前端能把 UI 屏幕写入迭代输入。
- `SignalGatherer` 能读取到 `ui_specs`。
- 相同输入重复提交时，返回明确结果：创建、跳过或 409。
- 跨项目的 `file_id`、`screen_ids`、`test_point_ids` 不允许写入。

### BE-03 场景 4 启动接口兼容性确认

优先级：P0

现有接口：

```text
POST /api/v1/pipeline/iteration/{iteration_id}/run
POST /api/v1/iteration/{iteration_id}/pipeline/run
```

确认返回包含：

```json
{
  "run_id": 1,
  "pipeline_run_id": 1,
  "iteration_id": 10,
  "status": "completed",
  "scenario": 4
}
```

验收标准：

- 场景 4 能通过 API 启动。
- 前端能拿到 `pipeline_run_id` 跳转。
- 当 `iteration.status` 不在 `draft` / `in_pipeline` 时，返回 400。
- 当迭代无有效输入时，返回清晰错误。

### BE-04 结果摘要接口增强

优先级：P1

建议新增接口：

```text
GET /api/v1/pipeline/{run_id}/summary
```

返回示例：

```json
{
  "run_id": 1,
  "status": "completed",
  "scenario": 4,
  "actions": {
    "keep": 30,
    "needs_modify": 12,
    "locator_broken": 8,
    "locator_and_modify": 3,
    "deprecate": 5,
    "add_new": 10,
    "conflict": 2,
    "pending_review": 1
  },
  "persisted_case_ids": [101, 102, 103],
  "artifact_kinds": [
    "raw_signals",
    "history_fingerprints",
    "backward_verdicts",
    "scenario_candidates",
    "forward_verdicts",
    "merged_verdicts",
    "generated_cases",
    "quality_scores",
    "persisted_case_ids"
  ]
}
```

验收标准：

- 前端可以展示场景 4 结果摘要。
- 不需要前端直接解析复杂 artifact。
- 只允许当前项目有权限的用户查看。
- 缺少某类 artifact 时返回空统计，而不是 500。

### BE-05 历史用例扫描策略文档化

优先级：P1

当前 `HistoryFingerprint` 规则：

```text
TestCase.project_id == project_id
TestCase.lifecycle_status != "archived"
TestCase.is_deleted == False
```

任务说明：

- 在接口返回和用户提示中明确说明。
- 如果后续要支持模块筛选，可以扩展 `HistoryFingerprint` 支持 `ctx.config.history_case_filter`。

验收标准：

- 用户知道旧用例无需手动选择。
- 用户知道 archived / deleted 不参与扫描。

### BE-06 场景 4 旧用例关系维护

优先级：P0

背景：

用户关心的核心问题是：旧项目变更生成不能只生成新用例，还必须维护旧用例影响关系。否则即使调用了场景 4，也可能只是“生成了一批新用例”，没有完成历史用例资产维护。

任务说明：

- 检查并补齐 `Persist` 或相关后处理逻辑，确保根据 `merged_verdicts` 维护旧用例关系。
- 推荐动作规则：

```text
ADD_NEW:
  新增用例，parent_case_id 可为空。

NEEDS_MODIFY:
  生成变更用例，parent_case_id = matched_case_id / case_id。

LOCATOR_BROKEN:
  不一定生成新用例；应标记旧用例步骤 locator_status，或生成定位修复待办。

LOCATOR_AND_MODIFY:
  生成变更用例，parent_case_id = matched_case_id / case_id，并标记定位风险。

DEPRECATE:
  不静默删除旧用例；建议生成待评审动作，或将旧用例标记为待废弃状态。

CONFLICT:
  不自动落库为最终结果；进入人工确认或 pending_review。

PENDING_REVIEW:
  生成待评审记录，不直接覆盖旧用例。
```

需要确认字段：

```text
TestCase.parent_case_id
TestCase.lifecycle_status
TestCase.last_review_id
TestStep.locator_status
Artifact.kind = merged_verdicts
```

验收标准：

- `NEEDS_MODIFY` / `LOCATOR_AND_MODIFY` 生成的新用例能关联旧用例 `parent_case_id`。
- `DEPRECATE` 不会直接物理删除旧用例。
- `CONFLICT` 不会被静默当作普通新增用例保存。
- 测试覆盖 `ADD_NEW`、`NEEDS_MODIFY`、`DEPRECATE`、`CONFLICT` 至少四种动作。

### BE-07 重复运行与输入去重策略

优先级：P1

任务说明：

- 明确同一迭代多次运行场景 4 的行为。
- 推荐规则：

```text
每次启动都创建新的 PipelineRun。
Artifact cache 可复用，但不能覆盖历史 PipelineRun。
相同 IterationInput 不重复写入。
新生成用例如来源相同旧用例，需避免重复创建完全相同标题/步骤的用例，或标记为重复候选。
```

验收标准：

- 同一迭代可重复运行，并保留多次 PipelineRun 记录。
- 重复输入不会导致 SignalGatherer 读取重复 UI。
- 重复运行不会静默覆盖旧的 PipelineRun 结果。

### BE-08 权限与资源归属校验

优先级：P0

所有新增或复用接口必须校验：

```text
project_id 属于当前用户
iteration_id 属于 project_id
ui_project_id 属于 project_id
screen_ids 全部属于 project_id
test_point_ids 全部属于 project_id
prd file_id 属于 project_id
pipeline run 属于当前用户可访问项目
```

验收标准：

- 跨项目读取预检数据返回 403/404。
- 跨项目写入 IterationInput 返回 403/404。
- 跨项目查看 Pipeline summary 返回 403/404。
- 测试覆盖至少一个跨项目 screen_id 或 test_point_id 的拒绝场景。

## 8. 数据库与模型影响

本阶段优先不新增数据库表。

现有关键字段：

```text
TestCase.test_point_id
TestCase.parent_case_id
TestCase.lifecycle_status
TestCase.summary
TestCase.summary_version
TestCase.summary_model_version
PipelineRun.status
Artifact.kind
IterationInput.kind
IterationInput.payload
```

注意事项：

- 场景 4 必须明确旧用例变更关系维护策略，详见 BE-06。
- 如果当前 `Persist` 只新增用例，不更新旧用例状态，则 BE-06 必须补齐。
- 如现有 `lifecycle_status` 缺少 `deprecated` / `pending_deprecate` 等状态，不建议直接新增枚举；优先通过评审记录或 `pending_review` 方式承载。

## 9. 测试计划

### 9.1 后端单元测试

新增或扩展：

```text
tests/api/test_pipeline_api.py
tests/pipelines/test_scenario_4.py
```

测试项：

- `scenario-4/precheck` 有历史用例、有已解析 UI 时 `can_run = true`。
- 无历史用例时 `can_run = false`。
- 无已解析 UI 时 `can_run = false`。
- `IterationInput(kind="prototype")` 能被 `SignalGatherer` 读取。
- 场景 4 API 返回 `pipeline_run_id`。
- 预检接口拒绝跨项目 screen_id。
- `NEEDS_MODIFY` 生成用例能写入 `parent_case_id`。
- `CONFLICT` 不被静默持久化为普通新增用例。

### 9.2 前端单元/组件测试

建议覆盖：

- 有历史用例和已解析 UI 时，按钮可点击。
- 无历史用例时，按钮禁用。
- 未解析 UI 时，按钮禁用。
- 点击启动调用 Pipeline API，而不是普通 AI 生成 API。
- 选择 UI 原型项目时能展示过滤后的可用屏幕数。
- 重复运行时弹出确认。

### 9.3 Cypress E2E

建议新增：

```text
cypress/e2e/scenario-4-regression-generation.cy.ts
```

主流程：

1. 登录。
2. 进入 UI 原型页面。
3. 选择已解析 UI 原型。
4. 点击“旧项目变更分析”。
5. 查看历史用例统计。
6. 创建或选择迭代。
7. 启动场景 4。
8. 跳转 Pipeline 进度页。
9. 验证状态为 `completed` 或 `waiting_for_user`。

## 10. 验收标准

### P0 验收

- 用户能从 UI 原型页面进入“旧项目变更生成”。
- 页面能展示历史用例扫描数量。
- 页面能展示新 UI 已解析页面数量。
- 无历史用例时禁止启动。
- 无已解析 UI 时禁止启动。
- 启动后调用 Pipeline 场景 4。
- 成功后跳转 Pipeline 进度页。
- 后端场景 4 测试通过。
- 前端使用统一 API 封装。
- 预检接口具备权限校验。
- 新 UI 输入能写入 `IterationInput(kind="prototype")`。
- 场景 4 不再走 `/api/v1/test-case/ai-enhanced-generate`。

### P1 验收

- 支持 `waiting_for_user` 人工确认。
- Pipeline 完成后展示 ADD_NEW / NEEDS_MODIFY / DEPRECATE / CONFLICT 摘要。
- 用户能跳转查看生成用例。
- `NEEDS_MODIFY` / `LOCATOR_AND_MODIFY` 能维护 `parent_case_id`。
- 重复运行有确认提示。

### P2 验收

- 支持按模块筛选历史用例。
- 支持选择是否包含 draft / pending_review。
- 支持展示旧用例到新用例的血缘关系。

## 11. 风险与注意事项

### 风险 1：用户以为要手动选旧用例

处理：页面提示“历史用例会自动扫描”。

### 风险 2：没有测试点导致对齐不足

处理：允许运行，但提示建议选择测试点或上传变更说明。

### 风险 3：UI 原型解析不完整

处理：预检接口返回 warning，前端提示未解析页面不会参与。

### 风险 4：Pipeline 进入 waiting_for_user

处理：必须支持进度页人工确认。

### 风险 5：普通生成和场景 4 混淆

处理：明确区分两个模式：

```text
普通生成：生成新用例草稿
旧项目变更生成：分析历史用例影响并生成变更用例
```

### 风险 6：只生成新用例但没有维护旧用例关系

处理：BE-06 作为必做任务，明确 `merged_verdicts` 到 `TestCase.parent_case_id`、旧用例生命周期、冲突评审的映射规则。

### 风险 7：UI 原型项目包含未解析屏幕

处理：预检接口返回 `usable_screen_ids`，前端只写入可用屏幕，并展示排除原因。

### 风险 8：跨项目资源被错误写入迭代

处理：BE-08 统一权限与资源归属校验，前后端测试覆盖跨项目拒绝。

## 12. 建议实施顺序

### 阶段 1：P0 打通链路

1. FE-00 补齐 API 封装与类型定义。
2. BE-01 新增预检统计接口。
3. BE-08 补权限与资源归属校验。
4. FE-01 新增入口。
5. FE-02 新增旧项目变更生成页面。
6. FE-03 展示扫描范围。
7. FE-08 实现 UI 原型项目到 `screen_ids` 转换。
8. FE-04 写入 IterationInput。
9. BE-03 确认场景 4 启动接口。
10. FE-05 调用 Pipeline 场景 4 并跳转 `/home/case/pipeline/{runId}`。
11. 补后端和前端最小测试。

### 阶段 2：P1 完善体验

1. FE-06 完善人工确认。
2. BE-04 新增 Pipeline summary 接口。
3. BE-06 补齐旧用例关系维护。
4. FE-07 展示结果摘要。
5. FE-09 支持重复运行确认。
6. BE-07 明确重复运行与输入去重策略。
7. 补 E2E 测试。

### 阶段 3：P2 增强能力

1. 历史用例模块筛选。
2. 旧用例血缘展示。
3. 变更矩阵可视化。

## 13. 开发检查清单

- [ ] 补齐 `pipelineApi.precheckScenario4`。
- [ ] 补齐 `pipelineApi.getPipelineSummary`。
- [ ] 补齐 `iterationApi.addIterationInput`。
- [ ] 新增预检接口。
- [ ] 预检接口使用 POST 请求体。
- [ ] 预检接口返回 `usable_screen_ids`。
- [ ] 预检接口校验项目权限。
- [ ] 新增前端路由。
- [ ] 新增旧项目变更生成页面。
- [ ] UI 原型页面增加入口按钮。
- [ ] 页面展示历史用例统计。
- [ ] 页面展示 UI 解析统计。
- [ ] UI 原型项目能转换为可用 `screen_ids`。
- [ ] 支持创建/选择 Iteration。
- [ ] 写入 `IterationInput(kind="prototype")`。
- [ ] 可选写入 `IterationInput(kind="testpoint")`。
- [ ] 调用 Pipeline 场景 4。
- [ ] 跳转 `/home/case/pipeline/{runId}`。
- [ ] 支持 `waiting_for_user` 确认。
- [ ] 展示 Pipeline 结果摘要。
- [ ] 维护 `NEEDS_MODIFY` 等动作的旧用例 `parent_case_id`。
- [ ] `CONFLICT` 不静默保存为普通新增用例。
- [ ] `DEPRECATE` 不物理删除旧用例。
- [ ] 重复运行前弹出确认。
- [ ] 补 API 测试。
- [ ] 补场景 4 Pipeline 测试。
- [ ] 补 Cypress E2E。

## 14. 最终推荐

正式采用：

```text
方案 B + 方案 C
```

即：

```text
增加场景 4 专用入口 + 展示历史扫描范围
```

不要继续用普通 AI 生成链路处理“旧测试用例 + 新 UI 变更”场景，否则会跳过历史用例扫描、双向扫描、合并判断、旧用例变更关系维护等核心能力。
