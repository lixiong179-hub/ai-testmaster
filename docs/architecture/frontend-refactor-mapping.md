# 前端分批重构映射表（P3 阶段一）

> 生成方式：`python scripts/gen_frontend_refactor_mapping.py`（请勿手工编辑，改脚本后重跑）
> 数据源：`docs/遗留文件处置清单.md` §1.4「类别 = 前端」逐文件清单
> 任务归属：**[分支] B-04**（P3 前端分批重构阶段一）——术语定义见《架构优化执行计划清单》§0：分支任务不计入主线进度
> 闸门：`npx vitest run` 全绿（历史基线 555 passed）；每批改动后必须复跑

## 1. 覆盖与统计

| 指标 | 数值 |
| --- | --- |
| 待处置前端文件总数 | **172** |
| 未归类（须为 0） | **0** |
| 工作区缺失文件 | 0 |
| 无生产代码引用 | 17 |
| 其中测试文件（护栏） | 4 |
| 其中应用入口文件 | 1 |
| 死代码候选（路由改 redirect） | 2 |
| 无 spec 直接覆盖 | 13 |

### 1.1 层分布

| 层 | 文件数 |
| --- | --- |
| 视图层 | 82 |
| Composable 层 | 31 |
| Store 层 | 20 |
| 组件层 | 19 |
| API 层 | 10 |
| 工具层 | 2 |
| 布局层 | 2 |
| 应用入口层 | 2 |
| 常量层 | 1 |
| 样式层 | 1 |
| 类型层 | 1 |
| 路由层 | 1 |

### 1.2 领域分布

| 领域 | 文件数 |
| --- | --- |
| 用例域 | 79 |
| 执行域 | 22 |
| 评审域 | 13 |
| 基础设施契约 | 12 |
| 测试点域 | 11 |
| 流水线域 | 8 |
| 项目域 | 6 |
| 报告域 | 5 |
| 成本看板与管理 | 4 |
| 认证与用户 | 4 |
| 应用入口 | 3 |
| AI 分析 | 2 |
| 公共组件与能力 | 2 |
| 系统管理 | 1 |

### 1.3 批次分布

| 批次 | 说明 | 文件数 |
| --- | --- | --- |
| B1 | B1 基础设施契约（api/store/utils/types/router/constants） | 15 |
| B2 | B2 用例域（含测试点、原型、思维导图、流程编排） | 90 |
| B3 | B3 执行域（执行页、任务、快速验证、移动端） | 22 |
| B4 | B4 报告与评审域（报告、缺陷、质量、流水线迭代） | 28 |
| B5 | B5 项目与系统域（项目、认证、系统管理、公共组件） | 17 |

## 2. 逐文件映射

| # | 现有路径 | 层 | 领域 | 关联路由 | 生产引用 | spec | 批次 | 建议动作 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `src/App.vue` | 应用入口层 | 应用入口 | — | 1 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 2 | `src/api/aiInvocation.ts` | API 层 | 基础设施契约 | — | 7 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 3 | `src/api/auth.ts` | API 层 | 认证与用户 | — | 2 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 4 | `src/api/case/ai.ts` | API 层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 5 | `src/api/case/types.ts` | API 层 | 用例域 | — | 8 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 6 | `src/api/caseQuality.ts` | API 层 | 评审域 | — | 2 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 7 | `src/api/file.ts` | API 层 | 基础设施契约 | — | 16 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 8 | `src/api/iteration.ts` | API 层 | 流水线域 | — | 9 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 9 | `src/api/report.ts` | API 层 | 报告域 | — | 8 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 10 | `src/api/review.ts` | API 层 | 评审域 | — | 5 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 11 | `src/api/testTask.ts` | API 层 | 基础设施契约 | — | 8 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 12 | `src/components/QuickTestGlobalEntry.vue` | 组件层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 13 | `src/components/RequirementUploader.vue` | 组件层 | 用例域 | — | 4 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 14 | `src/components/analysis/ProgressBar.vue` | 组件层 | AI 分析 | — | 2 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 15 | `src/components/case/EdgeSuggestionDialog.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 16 | `src/components/case/FlowCompletenessPanel.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 17 | `src/components/case/FlowPromptPreviewDialog.vue` | 组件层 | 评审域 | — | 2 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 18 | `src/components/case/FlowSortEditor.scss` | 组件层 | 用例域 | — | 1 | — | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 19 | `src/components/case/FlowSortEditor.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 20 | `src/components/case/LineageTree.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 21 | `src/components/case/SupplementForm.vue` | 组件层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 22 | `src/components/case/components/FlowSortEdgeTooltip.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 23 | `src/components/case/components/FlowSortToolbar.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 24 | `src/components/case/components/MainStepList.vue` | 组件层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 25 | `src/components/case/components/NodeDetailPanel.vue` | 组件层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 26 | `src/components/loading/AIParseLoading.scss` | 组件层 | 公共组件与能力 | — | 1 | — | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 27 | `src/components/report/ReportStat.vue` | 组件层 | 报告域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 28 | `src/components/xmind/XmindImportDialog.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 29 | `src/components/xmind/components/XmindPreviewStep.vue` | 组件层 | 评审域 | — | 2 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 30 | `src/components/xmind/components/XmindUploadStep.vue` | 组件层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 31 | `src/composables/__tests__/useFlowEditor.spec.ts` | Composable 层 | 用例域 | — | 0 | — | B2 | 测试护栏：随被测模块重构同步更新，禁止删除 |
| 32 | `src/composables/execution/useTestExecution.ts` | Composable 层 | 执行域 | — | 3 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 33 | `src/composables/flow/flowEditorComposables.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 34 | `src/composables/flow/flowEditorConstants.ts` | Composable 层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 35 | `src/composables/flow/flowEditorTypes.ts` | Composable 层 | 用例域 | — | 4 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 36 | `src/composables/flow/flowEditorUtils.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 37 | `src/composables/flow/flowLayoutTypes.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 38 | `src/composables/flowSort/useFlowSortEditor.ts` | Composable 层 | 用例域 | — | 6 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 39 | `src/composables/flowSort/useFlowSortEditorSync.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 40 | `src/composables/requirement/useResourceManage.ts` | Composable 层 | 用例域 | — | 3 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 41 | `src/composables/task/useTaskDetail.ts` | Composable 层 | 执行域 | — | 3 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 42 | `src/composables/testPointExtract/useExtractCore.ts` | Composable 层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 43 | `src/composables/useCaseFilter.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 44 | `src/composables/useCaseSelection.ts` | Composable 层 | 用例域 | — | 0 | ✅ | B2 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 45 | `src/composables/useEdgeSuggestion.ts` | Composable 层 | 用例域 | — | 3 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 46 | `src/composables/useFlowEdgeOps.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 47 | `src/composables/useFlowEdgeTooltip.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 48 | `src/composables/useFlowEditor.ts` | Composable 层 | 用例域 | — | 19 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 49 | `src/composables/useFlowGroupBackground.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 50 | `src/composables/useFlowLayout.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 51 | `src/composables/useFlowMainOrder.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 52 | `src/composables/useFlowPathHighlight.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 53 | `src/composables/useFlowSearch.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 54 | `src/composables/useFlowSortData.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 55 | `src/composables/useFlowStats.ts` | Composable 层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 56 | `src/composables/useFlowTypeOps.ts` | Composable 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 57 | `src/composables/useIterationManager.ts` | Composable 层 | 流水线域 | — | 5 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 58 | `src/composables/usePathPlayback.ts` | Composable 层 | 执行域 | — | 2 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 59 | `src/composables/useResourceList.ts` | Composable 层 | 用例域 | — | 3 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 60 | `src/composables/useTestPointLink.ts` | Composable 层 | 测试点域 | — | 3 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 61 | `src/composables/useWebSocket.ts` | Composable 层 | 公共组件与能力 | — | 0 | ✅ | B5 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 62 | `src/constants/resource.ts` | 常量层 | 用例域 | — | 5 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 63 | `src/layouts/MainLayout.vue` | 布局层 | 基础设施契约 | `/home` | 1 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 64 | `src/layouts/useMainLayout.ts` | 布局层 | 基础设施契约 | — | 1 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 65 | `src/main.ts` | 应用入口层 | 应用入口 | — | 0 | — | B1 | 应用入口：由 index.html / 框架加载，无引用属正常 |
| 66 | `src/router/index.ts` | 路由层 | 基础设施契约 | — | 2 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 67 | `src/store/__tests__/smartGeneration.spec.ts` | Store 层 | 用例域 | — | 0 | — | B2 | 测试护栏：随被测模块重构同步更新，禁止删除 |
| 68 | `src/store/analysis.ts` | Store 层 | 基础设施契约 | — | 1 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 69 | `src/store/case.ts` | Store 层 | 用例域 | — | 4 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 70 | `src/store/generate/__tests__/generateHelpers.spec.ts` | Store 层 | 用例域 | — | 0 | — | B2 | 测试护栏：随被测模块重构同步更新，禁止删除 |
| 71 | `src/store/generate/caseActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 72 | `src/store/generate/computed.ts` | Store 层 | 用例域 | — | 6 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 73 | `src/store/generate/editActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 74 | `src/store/generate/generateActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 75 | `src/store/generate/generateHelpers.ts` | Store 层 | 用例域 | — | 2 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 76 | `src/store/generate/projectActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 77 | `src/store/generate/saveActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 78 | `src/store/generate/state.ts` | Store 层 | 用例域 | — | 12 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 79 | `src/store/generate/testPointActions.ts` | Store 层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 80 | `src/store/generate/types.ts` | Store 层 | 用例域 | — | 13 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 81 | `src/store/generate/uiPrototypeActions.ts` | Store 层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 82 | `src/store/project.ts` | Store 层 | 项目域 | — | 8 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 83 | `src/store/report.ts` | Store 层 | 报告域 | — | 3 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 84 | `src/store/smartGeneration.ts` | Store 层 | 用例域 | — | 5 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 85 | `src/store/task.ts` | Store 层 | 基础设施契约 | — | 4 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 86 | `src/store/useGenerateStore.ts` | Store 层 | 用例域 | — | 9 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 87 | `src/styles/select-unified.css` | 样式层 | 基础设施契约 | — | 0 | — | B1 | 零引用候选：本轮仅登记，不删除（需运行时依赖分析后处理） |
| 88 | `src/types/element-plus.ts` | 类型层 | 基础设施契约 | — | 38 | — | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 89 | `src/utils/request.ts` | 工具层 | 基础设施契约 | — | 44 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 90 | `src/utils/websocket.ts` | 工具层 | 基础设施契约 | — | 3 | ✅ | B1 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 91 | `src/views/admin/AICostDashboard.vue` | 视图层 | 成本看板与管理 | `ai-cost-dashboard` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 92 | `src/views/admin/PipelineDashboard.vue` | 视图层 | 成本看板与管理 | `pipeline-dashboard` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 93 | `src/views/admin/useAICostDashboard.ts` | 视图层 | 成本看板与管理 | — | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 94 | `src/views/admin/usePipelineDashboard.ts` | 视图层 | 成本看板与管理 | — | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 95 | `src/views/analysis/AnalysisPage.vue` | 视图层 | AI 分析 | — | 0 | ✅ | B4 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 96 | `src/views/case/BatchLocatorDialog.vue` | 视图层 | 执行域 | — | 3 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 97 | `src/views/case/CaseMigration.vue` | 视图层 | 用例域 | `migration` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 98 | `src/views/case/CaseQualityAnalysis.vue` | 视图层 | 评审域 | `quality/:caseId` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 99 | `src/views/case/CaseRefresh.vue` | 视图层 | 用例域 | `case-refresh` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 100 | `src/views/case/TestCaseList.vue` | 视图层 | 用例域 | `` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 101 | `src/views/case/components/CaseDialogs.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 102 | `src/views/case/components/CaseTechnicalView.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 103 | `src/views/case/components/CaseVersionDiff.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 104 | `src/views/case/components/ContextHealthPanel.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 105 | `src/views/case/components/ContextHistoryCases.vue` | 视图层 | 用例域 | — | 0 | ✅ | B2 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 106 | `src/views/case/components/ContextScreenPreview.vue` | 视图层 | 评审域 | — | 0 | ✅ | B4 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 107 | `src/views/case/components/ContextTestPointSelector.vue` | 视图层 | 测试点域 | — | 0 | ✅ | B2 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 108 | `src/views/case/components/ErrorState.vue` | 视图层 | 用例域 | — | 3 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 109 | `src/views/case/components/EvidenceRefsPanel.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 110 | `src/views/case/components/GenerateCaseConfigForm.vue` | 视图层 | 用例域 | — | 0 | ✅ | B2 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 111 | `src/views/case/components/GenerateCaseNavBar.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 112 | `src/views/case/components/GenerateCaseResultCard.vue` | 视图层 | 用例域 | — | 0 | ✅ | B2 | 仅被 spec 引用：先确认是否为死代码，再决定重构或归档 |
| 113 | `src/views/case/components/GenerateCaseStepSection.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 114 | `src/views/case/components/QualityDonutChart.vue` | 视图层 | 评审域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 115 | `src/views/case/components/RightPreviewPanel.vue` | 视图层 | 评审域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 116 | `src/views/case/components/SmartGenerateDialogs.vue` | 视图层 | 流水线域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 117 | `src/views/case/components/Step1ProjectSelect.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 118 | `src/views/case/components/Step3AIExtract.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 119 | `src/views/case/components/Step4Validate.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 120 | `src/views/case/smart-generate.vue` | 视图层 | 流水线域 | `smart-generate` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 121 | `src/views/case/test-point-management/TestPointCasesDialog.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 122 | `src/views/case/test-point-management/TestPointExtractDialog.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 123 | `src/views/case/test-point-management/TestPointFormDialog.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 124 | `src/views/case/test-point-management/components/FilterSection.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 125 | `src/views/case/test-point-management/components/StatsCards.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 126 | `src/views/case/test-point-management/components/TestPointTable.vue` | 视图层 | 测试点域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 127 | `src/views/case/test-point-management/index.vue` | 视图层 | 测试点域 | `test-point-management` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 128 | `src/views/case/useCaseQualityAnalysis.ts` | 视图层 | 评审域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 129 | `src/views/case/useTestCaseList.ts` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 130 | `src/views/execution/components/ExecutionSidePanel.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 131 | `src/views/execution/components/ExecutionStepsPanel.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 132 | `src/views/iteration/PipelineProgress.scss` | 视图层 | 流水线域 | — | 1 | — | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 133 | `src/views/iteration/PipelineProgress.vue` | 视图层 | 流水线域 | `pipeline/:runId` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 134 | `src/views/iteration/ReviewInbox.scss` | 视图层 | 评审域 | — | 1 | — | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 135 | `src/views/iteration/ReviewInbox.vue` | 视图层 | 评审域 | `review/:reviewId` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 136 | `src/views/iteration/usePipelineProgress.ts` | 视图层 | 流水线域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 137 | `src/views/iteration/useReviewInbox.ts` | 视图层 | 评审域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 138 | `src/views/login/index.vue` | 视图层 | 认证与用户 | `/login` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 139 | `src/views/login/useLogin.ts` | 视图层 | 认证与用户 | — | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 140 | `src/views/profile/index.vue` | 视图层 | 认证与用户 | `profile` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 141 | `src/views/project/ProjectList.scss` | 视图层 | 项目域 | — | 1 | — | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 142 | `src/views/project/ProjectList.vue` | 视图层 | 项目域 | `` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 143 | `src/views/project/detail.vue` | 视图层 | 项目域 | `detail` | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 144 | `src/views/project/useProjectDetail.ts` | 视图层 | 项目域 | — | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 145 | `src/views/project/useProjectList.ts` | 视图层 | 项目域 | — | 1 | ✅ | B5 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 146 | `src/views/quick-test/__tests__/useQuickTestFlow.spec.ts` | 视图层 | 执行域 | — | 0 | — | B3 | 测试护栏：随被测模块重构同步更新，禁止删除 |
| 147 | `src/views/quick-test/components/CaseCard.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 148 | `src/views/quick-test/components/QuickAssetsCard.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 149 | `src/views/quick-test/components/QuickDefectList.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 150 | `src/views/quick-test/components/QuickHistoryList.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 151 | `src/views/quick-test/components/QuickInputCard.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 152 | `src/views/quick-test/components/QuickProgressView.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 153 | `src/views/quick-test/components/QuickResultView.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 154 | `src/views/quick-test/components/QuickSummaryCard.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 155 | `src/views/report/ReportDetail.vue` | 视图层 | 报告域 | `report/detail` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 156 | `src/views/report/ReportList.vue` | 视图层 | 报告域 | `report` | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 157 | `src/views/requirement/components/ElementDetailPanel.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 158 | `src/views/requirement/components/FlowLayoutPanel.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 159 | `src/views/requirement/components/IterationPanel.vue` | 视图层 | 流水线域 | — | 1 | ✅ | B4 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 160 | `src/views/requirement/components/ResourceTable.vue` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 161 | `src/views/requirement/resource-manage.vue` | 视图层 | 用例域 | `` / `analysis` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 162 | `src/views/requirement/ui-prototype.vue` | 视图层 | 用例域 | `ui-prototype` | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 163 | `src/views/requirement/useUIPrototype.ts` | 视图层 | 用例域 | — | 1 | ✅ | B2 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 164 | `src/views/system/quality-rule/index.vue` | 视图层 | 评审域 | — | 0 | ✅ | B4 | 路由已改为 redirect（旧 URL 指向新页面），死代码候选：本轮仅登记 |
| 165 | `src/views/system/test-capability/index.vue` | 视图层 | 系统管理 | — | 0 | ✅ | B5 | 路由已改为 redirect（旧 URL 指向新页面），死代码候选：本轮仅登记 |
| 166 | `src/views/task/TaskCreate.vue` | 视图层 | 执行域 | `create/:projectId` | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 167 | `src/views/task/TaskDetail.vue` | 视图层 | 执行域 | `detail/:taskId` | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 168 | `src/views/task/TaskList.vue` | 视图层 | 执行域 | `` / `list/:projectId` | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 169 | `src/views/task/components/TaskResultsPanel.vue` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 170 | `src/views/task/useTaskCreate.ts` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 171 | `src/views/task/useTaskList.ts` | 视图层 | 执行域 | — | 1 | ✅ | B3 | 按域重构：保持对外导出契约，改前先补/加厚 spec |
| 172 | `src/views/test/index.vue` | 视图层 | 应用入口 | — | 0 | — | B1 | 零引用候选：本轮仅登记，不删除（需运行时依赖分析后处理） |

## 3. 批次执行约定

1. 每批独立 commit；提交前 `npx vitest run` 必须全绿（0 failed，总数不下降）。
2. 批次内先补 spec 再改实现；「无 spec 覆盖」文件在改动前必须先有护栏。
3. 对外导出（`src/api`、`src/store`、`src/composables`）改签名须同步调用方，禁止留死路径。
4. 零引用候选本轮只登记不删除；删除需先做路由全量枚举与 `depcheck` 依赖分析。

## 4. 未归类清单

无（172/172 全部归类）
