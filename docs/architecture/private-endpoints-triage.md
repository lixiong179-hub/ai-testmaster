# endpoints 私有文件清点与下沉台账（R2-3）

- **生成时间**：2026-11-10（批次 1 ~ 批次 5 完成后复核，R2-3 收官）
- **统计命令**：
  ```powershell
  (Get-ChildItem app/api/v1/endpoints -Recurse -File -Filter '_*.py' -Exclude '__init__.py').Count
  ```
- **当前数量**：**2**（基线 40 + R4-7 新增 `_deps.py` = 41；累计处理 39 个，仅剩 2 个 A 类永久保留）
- **目标**：≤10，且保留项仅限「纯 schema / 常量 / 依赖聚合」
- **判定规则**（清单 R2-3）：仅含 Pydantic schema / 常量 / 纯类型别名的文件可保留；含 DB 访问、跨域编排、业务分支的必须下沉

## 一、处置类型定义

| 类型 | 含义 | 结果 |
| --- | --- | --- |
| **A 保留** | 纯 schema / 常量 / 依赖聚合，无业务语义 | 文件保留，不计入下沉目标 |
| **B 抽离** | FastAPI 路由文件（必须留在 endpoints），把 DB 查询与业务分支抽到 service | 文件保留但**瘦身**，业务进 `app/services/` |
| **C 下沉** | 纯函数 / helper / 解析器，可整文件移走并删除 | 文件消失 |

> B 类最终仍需在阶段末「合并回父端点模块」，才能达成 ≤10；本台账先按「业务归位」推进。

## 二、批次 1 ~ 批次 5 已完成（2026-11-10，共 39 个，R2-3 收官）

### 批次 2（6 / 6 完成）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `_generation_batch_helpers.py` | 89 | C 下沉 | `app/services/generation_batch_helpers.py`（状态迁移校验 / 批次号 / 响应转换 / 版本快照 / 用例废弃） |
| `_test_case_crud_helpers.py` | 62 | C 下沉 | `app/services/test_case_crud_helpers.py`（`TestStep`/`TestData` 构造与批量持久化） |
| `_generation_batch_routes.py` | 109 | B 合并 | 处理函数内联回 `generation_batch.py`（create / get / update） |
| `_generation_batch_save.py` | 284 | B 合并 | 处理函数内联回 `generation_batch.py`（save） |
| `_test_case_crud_routes.py` | 242 | B 合并 | 处理函数内联回 `test_case_crud.py`（create / list / detail） |
| `_test_case_crud_mutations.py` | 118 | B 合并 | 处理函数内联回 `test_case_crud.py`（update / delete） |

> 合并方式：路由处理函数逐字迁移至父端点模块，`router.add_api_route` 注册顺序与路径不变；已做 AST 级一致性校验（9 个处理函数体与合并前完全相同）。
> 兼容性：`test_case_crud.merge_test_data_to_steps` / `create_steps_and_test_data`、`generation_batch.VALID_TRANSITIONS` / `_validate_status_transition` 等符号仍由父端点导出，导入路径未变。
> **批次 2 验证**：`import app.main` 成功；`test_test_case_crud_api` + `test_test_case_crud_batch_async` + `test_generation_batch_async` 共 **40 passed**；私有文件 **35 → 31**；运行时导入环 **0**。

### 批次 3（5 / 5 完成）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `_history_asset_helpers.py` | 48 | C 下沉 | `app/services/history_asset_helpers.py`（ORM→响应转换 / 项目权限校验） |
| `_pipeline_artifacts_helpers.py` | 166 | C 下沉 | `app/services/pipeline_artifacts_helpers.py`（payload 截断 / 取消权限校验 / 重跑指标 / async 查询助手） |
| `_pipeline_artifacts_routes.py` | 179 | B 合并 | 处理函数内联回 `pipeline_artifacts.py`（summary / inferred-summary / artifact 详情） |
| `_pipeline_artifacts_mutations.py` | 185 | B 合并 | 处理函数内联回 `pipeline_artifacts.py`（supplement-signals / cancel） |
| `_case_quality_cost_routes.py` | 108 | B 合并 | 3 个成本统计端点并入 `case_quality_report.py`，取消 `include_router(cost_router)` 二级挂载 |

> 兼容性：`pipeline_artifacts` 仍导出 `record_version_rerun_metric`（`pipeline.py:38` 直接引用）、`CANCELLABLE_STATUSES`、`_truncate_payload`、`_check_cancel_permission`；`history_asset.py` 的调用点仅改 import 源。
> **批次 3 验证**：`import app.main` 成功；路由复核 `/api/v1/quality/projects/{project_id}/cost-statistics`、`/cost-report`、`/cases/{case_id}/cost-statistics`、`/api/v1/pipeline/{run_id}/artifacts/{artifact_id}` 均在位；`test_history_asset_api` + `test_pipeline_artifact_detail` + `test_case_quality_report_api` + `test_cost_statistics_service` + `test_models_api_cost_log` 共 **63 passed**；私有文件 **31 → 26**；运行时导入环 **0**。

### 批次 5（14 / 14 完成）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `iteration/_helpers.py` | 154 | C 下沉 | `app/services/iteration_helpers.py`（归属校验 / 序列化 / 资源清理，sync+async 双版本） |
| `iteration/_routes.py` | 252 | B 合并 | 8 个迭代路由内联回 `iteration/__init__.py` |
| `pipeline_dashboard/_utils.py` | 37 | C 下沉 | `app/services/pipeline_service/dashboard_utils.py`（方言适配 / 子查询构建） |
| `pipeline_dashboard/_overview.py` | 128 | B 合并 | 总览路由内联回 `pipeline_dashboard/__init__.py` |
| `pipeline_dashboard/_trends.py` | 199 | B 合并 | 4 个趋势路由内联为独立 `trends_router`，再 `include_router` 回主 router；`pipeline.py` 继续以无 `/dashboard` 前缀二次注册，前端旧路径不变 |
| `review_inbox/_queries.py` | 74 | B 合并 | 决策列表路由内联回 `review_inbox/__init__.py` |
| `review_inbox/_mutations.py` | 339 | B 合并 | 7 个决策写入路由 + `_run_review_mutation` 内联回 `review_inbox/__init__.py` |
| `review_inbox/_schemas.py` | 142 | 拆分 | 6 个 Pydantic 模型 → `review_inbox/schemas.py`；3 个 helper → `services/review_service/inbox_helpers.py`；`require_admin` 留端点层 |
| `ui_prototype/_parse_helpers.py` | 164 | 死代码删除 | 零引用（`parse_endpoints.py` 已内联自身版本） |
| `ui_prototype/_upload_helpers.py` | 124 | 死代码删除 | 零引用（`screen_endpoints.py` 已内联自身版本） |
| `ui_prototype/_project_endpoints_routes.py` | 238 | B 合并 | 3 个项目 CRUD 路由内联回 `ui_prototype/project_endpoints.py` |
| `ui_prototype/_project_endpoints_flow.py` | 130 | B 合并 | 2 个流程数据路由内联回 `ui_prototype/project_endpoints.py` |
| `_user_perm_routes.py` | 86 | B 合并 | 5 个权限路由内联回 `user.py`（位置保持在 `/{user_id}` 之前） |
| `_user_role_routes.py` | 131 | B 合并 | 7 个角色路由内联回 `user.py`，`_require_superuser` 继续取自 `_deps.py` |

> 台账订正：`pipeline_dashboard/_overview.py`、`_trends.py`、`review_inbox/_queries.py`、`_mutations.py` 原判 C 类，实测均含 `APIRouter`，按 **B 类合并** 处置；`ui_prototype/_parse_helpers.py`、`_upload_helpers.py` 经全仓引用扫描确认为死代码，直接删除。
> **批次 5 验证**：`import app.main` 成功；`tests/api` 全量 **998 passed / 44 skipped / 0 failed**；评审/迭代/用户/UI 相关非 API 测试 **555 passed**；私有文件 **16 → 2**；运行时导入环 **0**；六域映射表未归类 **0**（836 模块 / 2363 边 / 674 行）。

### 批次 4（10 / 10 完成）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `execution_core/_helpers.py` | 107 | C 下沉 | `app/services/execution_core/helpers.py`（权限校验 / 可见字段过滤） |
| `execution_core/_execution.py` | 279 | B 合并 | 5 个执行路由内联回 `execution_core/__init__.py` |
| `execution_core/_analysis.py` | 374 | C+B 拆分 | 纯计算与 Agent 编排 → `services/execution_core/failure_analysis.py`；4 个路由内联回 `execution_core/__init__.py`；`SpeedReplayRequest` 留在 `execution_core/schemas.py` |
| `test_point/_helpers.py` | 34 | C 下沉 | `app/services/test_point/helpers.py` |
| `test_point/_queries.py` | 181 | B 合并 | 3 个查询路由内联回 `test_point/__init__.py` |
| `test_point/_mutations.py` | 235 | B 合并 | 4 个写入路由内联回 `test_point/__init__.py` |
| `test_point/_management.py` | 181 | B 合并 | 4 个管理路由内联回 `test_point/__init__.py` |
| `test_case_ai_generate/_context.py` | 326 | C+B 拆分 | 6 个纯函数（`_assess_history_trust` 等）→ `services/test_case_generation/history_context.py`；4 个路由内联回 `test_case_ai_generate/__init__.py` |
| `test_case_ai_generate/_generate.py` | 193 | B 合并 | 2 个生成路由 + `_raise_ai_error` 内联回 `test_case_ai_generate/__init__.py` |
| `test_case_ai_generate/_precondition.py` | 146 | B 合并 | 3 个前置条件路由内联回 `test_case_ai_generate/__init__.py` |

> 台账订正：`test_point/_queries.py`、`_mutations.py`、`_management.py` 原判 C 类，实测均含 `APIRouter`，按 **B 类合并** 处置（仅权限校验下沉）。
> 连带变更：`app/services/test_case_generation/_history_scoring_mixin.py` 改为从 `history_context` 导入；测试 patch 路径同步（`tests/test_context_precision_features.py`、`tests/test_scenario_integration.py`、`tests/test_ai_generation_full_coverage.py`）；`execution_management.py`、`agents.py` 改从 `services.execution_core.helpers` 导入。
> 六域规则同步：`DIR_RULES` 补充 `services/execution_core`（execution）与 `services/test_point`（test_point）。
> **批次 4 验证**：`import app.main` 成功；路由复核 `/api/v1/test-point` 15 条、`/api/v1/execution` 8 条执行路由、AI 生成 8 条（`ai-generate`/`ai-enhanced-generate`/`generate-context`/`generate-single`/`ai-batch-generate`/`precondition-steps`/`parse-precondition`）全部在位；执行链路 **36 passed**、测试点与上下文 **87 passed**、AI 生成全量 **182 passed**；私有文件 **26 → 16**；运行时导入环 **0**；六域映射表未归类 **0**。

### 批次 1（4 个）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `_history_asset_parsers.py` | 86 | C 下沉 | `app/services/history_asset_parsing.py` |
| `_history_asset_classification.py` | 143 | C 下沉 | `app/services/history_asset_classification.py` |
| `ui_prototype/_project_endpoints_helpers.py` | 87 | C 下沉 | `app/services/ui_prototype_flow.py` |
| `_project_config_helpers.py` | 115 | **删除（死代码）** | 逻辑与 `endpoints/project_config.py` 内同名函数三份重复，全仓 0 处导入 |

**验证**：`python -c "import app.main"` 成功；相关端点测试 **145 passed**；私有文件 **41 → 37**。

## 三、原 37 项台账（已全部处置，删除线保留供追溯）

`db` 列为该文件中 `db.` / `session.` / `select(` 的出现次数（近似 DB 耦合度）。

### 3.1 顶层（清单 15 项：13 项已处置，2 项 A 类永久保留）

| # | 文件 | 行数 | db | 类型 | 下沉目标 / 说明 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `_case_quality_schemas.py` | 83 | 0 | A 保留 | 纯 Pydantic schema | — |
| 2 | `_deps.py` | 20 | 0 | A 保留 | 共享依赖（R4-7 产物，非业务） | — |
| 3 | ~~`_case_quality_cost_routes.py`~~ | 108 | 1 | ✅ B 合并完成 | → 内联回 `case_quality_report.py` | 3 ✅ |
| 4 | ~~`_generation_batch_helpers.py`~~ | 89 | 2 | ✅ C 下沉完成 | → `app/services/generation_batch_helpers.py` | 2 ✅ |
| 5 | ~~`_generation_batch_routes.py`~~ | 109 | 12 | ✅ B 合并完成 | → 内联回 `generation_batch.py` | 2 ✅ |
| 6 | ~~`_generation_batch_save.py`~~ | 284 | 24 | ✅ B 合并完成 | → 内联回 `generation_batch.py` | 2 ✅ |
| 7 | ~~`_history_asset_helpers.py`~~ | 48 | 1 | ✅ C 下沉完成 | → `app/services/history_asset_helpers.py` | 3 ✅ |
| 8 | ~~`_pipeline_artifacts_helpers.py`~~ | 166 | 9 | ✅ C 下沉完成 | → `app/services/pipeline_artifacts_helpers.py` | 3 ✅ |
| 9 | ~~`_pipeline_artifacts_mutations.py`~~ | 185 | 6 | ✅ B 合并完成 | → 内联回 `pipeline_artifacts.py` | 3 ✅ |
| 10 | ~~`_pipeline_artifacts_routes.py`~~ | 179 | 1 | ✅ B 合并完成 | → 内联回 `pipeline_artifacts.py` | 3 ✅ |
| 11 | ~~`_test_case_crud_helpers.py`~~ | 62 | 3 | ✅ C 下沉完成 | → `app/services/test_case_crud_helpers.py` | 2 ✅ |
| 12 | ~~`_test_case_crud_mutations.py`~~ | 118 | 13 | ✅ B 合并完成 | → 内联回 `test_case_crud.py` | 2 ✅ |
| 13 | ~~`_test_case_crud_routes.py`~~ | 242 | 23 | ✅ B 合并完成 | → 内联回 `test_case_crud.py` | 2 ✅ |
| 14 | ~~`_user_perm_routes.py`~~ | 86 | 1 | ✅ B 合并完成 | → 内联回 `user.py`（`/{user_id}` 之前） | 5 ✅ |
| 15 | ~~`_user_role_routes.py`~~ | 131 | 1 | ✅ B 合并完成 | → 内联回 `user.py` | 5 ✅ |

### 3.2 子目录（清单 22 项，全部处置完成）

| # | 文件 | 行数 | db | 类型 | 下沉目标 / 说明 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| 16 | ~~`execution_core/_analysis.py`~~ | 374 | 22 | ✅ C+B 完成 | 纯计算 → `services/execution_core/failure_analysis.py`；路由内联回包入口 | 4 ✅ |
| 17 | ~~`execution_core/_execution.py`~~ | 279 | 21 | ✅ B 合并完成 | → 内联回 `execution_core/__init__.py` | 4 ✅ |
| 18 | ~~`execution_core/_helpers.py`~~ | 107 | 6 | ✅ C 下沉完成 | → `app/services/execution_core/helpers.py` | 4 ✅ |
| 19 | ~~`iteration/_helpers.py`~~ | 154 | 18 | ✅ C 下沉完成 | → `app/services/iteration_helpers.py` | 5 ✅ |
| 20 | ~~`iteration/_routes.py`~~ | 252 | 16 | ✅ B 合并完成 | → 内联回 `iteration/__init__.py` | 5 ✅ |
| 21 | ~~`pipeline_dashboard/_overview.py`~~ | 128 | 11 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `pipeline_dashboard/__init__.py` | 5 ✅ |
| 22 | ~~`pipeline_dashboard/_trends.py`~~ | 199 | 9 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联为 `trends_router`，兼容无 `/dashboard` 前缀的旧路径 | 5 ✅ |
| 23 | ~~`pipeline_dashboard/_utils.py`~~ | 37 | 4 | ✅ C 下沉完成 | → `app/services/pipeline_service/dashboard_utils.py` | 5 ✅ |
| 24 | ~~`review_inbox/_queries.py`~~ | 74 | 1 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `review_inbox/__init__.py` | 5 ✅ |
| 25 | ~~`review_inbox/_mutations.py`~~ | 339 | 1 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `review_inbox/__init__.py` | 5 ✅ |
| 26 | ~~`review_inbox/_schemas.py`~~ | 142 | 5 | ✅ 拆分完成 | schema → `review_inbox/schemas.py`；helper → `services/review_service/inbox_helpers.py` | 5 ✅ |
| 27 | ~~`test_case_ai_generate/_context.py`~~ | 326 | 7 | ✅ C+B 完成 | 纯函数 → `services/test_case_generation/history_context.py`；路由内联回包入口 | 4 ✅ |
| 28 | ~~`test_case_ai_generate/_generate.py`~~ | 193 | 11 | ✅ B 合并完成 | → 内联回 `test_case_ai_generate/__init__.py` | 4 ✅ |
| 29 | ~~`test_case_ai_generate/_precondition.py`~~ | 146 | 19 | ✅ B 合并完成 | → 内联回 `test_case_ai_generate/__init__.py` | 4 ✅ |
| 30 | ~~`test_point/_helpers.py`~~ | 34 | 3 | ✅ C 下沉完成 | → `app/services/test_point/helpers.py` | 4 ✅ |
| 31 | ~~`test_point/_queries.py`~~ | 181 | 6 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `test_point/__init__.py` | 4 ✅ |
| 32 | ~~`test_point/_mutations.py`~~ | 235 | 15 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `test_point/__init__.py` | 4 ✅ |
| 33 | ~~`test_point/_management.py`~~ | 181 | 13 | ✅ B 合并完成（原判 C 类，实测含 router） | → 内联回 `test_point/__init__.py` | 4 ✅ |
| 34 | ~~`ui_prototype/_parse_helpers.py`~~ | 164 | 4 | ✅ 死代码删除 | 全仓零引用（`parse_endpoints.py` 已内联自身版本） | 5 ✅ |
| 35 | ~~`ui_prototype/_upload_helpers.py`~~ | 124 | 2 | ✅ 死代码删除 | 全仓零引用（`screen_endpoints.py` 已内联自身版本） | 5 ✅ |
| 36 | ~~`ui_prototype/_project_endpoints_flow.py`~~ | 130 | 16 | ✅ B 合并完成 | → 内联回 `ui_prototype/project_endpoints.py` | 5 ✅ |
| 37 | ~~`ui_prototype/_project_endpoints_routes.py`~~ | 238 | 25 | ✅ B 合并完成 | → 内联回 `ui_prototype/project_endpoints.py` | 5 ✅ |

## 四、统计与批次计划

| 类型 | 数量 | 说明 |
| --- | --- | --- |
| A 保留 | **2** | `_case_quality_schemas.py`、`_deps.py` |
| B 抽离 | **0** | 全部已合并回父端点；41 → 2 收口达成 |
| C 下沉 | **0** | 已处理 14 个，另 3 个为死代码已删 |
| 合计 | **2** | 均为 A 类永久保留 |

| 批次 | 文件数 | 内容 | 风险 |
| --- | --- | --- | --- |
| 1 ✅ | 4 | 纯函数/死代码（已完成） | 低 |
| 2 ✅ | 6 | `_test_case_crud_*`（3）+ `_generation_batch_*`（3）—— 2 个 C 类下沉 + 4 个 B 类合并回父端点（已完成） | 中（用例主链路） |
| 3 ✅ | 5 | `_history_asset_helpers`（1）+ `_pipeline_artifacts_*`（3）+ `_case_quality_cost_routes`（1）（已完成） | 中 |
| 4 ✅ | 10 | `execution_core/`（3）+ `test_point/`（4）+ `test_case_ai_generate/`（3）（已完成） | 高（执行链路） |
| 5 ✅ | 14 | `ui_prototype/`（4）+ `review_inbox/`（3）+ `iteration/`（2）+ `pipeline_dashboard/`（3）+ `_user_*_routes`（2）（已完成） | 高（面最广） |

**每批完成后的验收**：`python -c "import app.main"` 成功 + 该域端点测试全绿 + `_*.py` 计数下降。

## 五、当前验收状态

- [x] 批次 1 **41 → 37**、批次 2 **37 → 31**、批次 3 **31 → 26**、批次 4 **26 → 16**、批次 5 **16 → 2**
- [x] `import app.main` 成功；批次 1 **145 passed**、批次 2 **40 passed**、批次 3 **63 passed**、批次 4 **305 passed**、批次 5 `tests/api` **998 passed / 44 skipped** + 非 API **555 passed**
- [x] 结构调整后运行时导入环 **0**（`scripts/check_import_cycles.py`）；六域映射表未归类 **0**
- [x] **R2-3 收官**：私有文件 **41 → 2**（`_case_quality_schemas.py`、`_deps.py`），判据 41 → ≤10 达成
