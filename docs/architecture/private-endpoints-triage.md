# endpoints 私有文件清点与下沉台账（R2-3）

- **生成时间**：2026-11-10（批次 1 完成后复核）
- **统计命令**：
  ```powershell
  (Get-ChildItem app/api/v1/endpoints -Recurse -File -Filter '_*.py' -Exclude '__init__.py').Count
  ```
- **当前数量**：**37**（基线 40 + R4-7 新增 `_deps.py` = 41；批次 1 已处理 4 个）
- **目标**：≤10，且保留项仅限「纯 schema / 常量 / 依赖聚合」
- **判定规则**（清单 R2-3）：仅含 Pydantic schema / 常量 / 纯类型别名的文件可保留；含 DB 访问、跨域编排、业务分支的必须下沉

## 一、处置类型定义

| 类型 | 含义 | 结果 |
| --- | --- | --- |
| **A 保留** | 纯 schema / 常量 / 依赖聚合，无业务语义 | 文件保留，不计入下沉目标 |
| **B 抽离** | FastAPI 路由文件（必须留在 endpoints），把 DB 查询与业务分支抽到 service | 文件保留但**瘦身**，业务进 `app/services/` |
| **C 下沉** | 纯函数 / helper / 解析器，可整文件移走并删除 | 文件消失 |

> B 类最终仍需在阶段末「合并回父端点模块」，才能达成 ≤10；本台账先按「业务归位」推进。

## 二、批次 1 已完成（2026-11-10，4 个）

| 原文件 | 行数 | 处置 | 去向 |
| --- | --- | --- | --- |
| `_history_asset_parsers.py` | 86 | C 下沉 | `app/services/history_asset_parsing.py` |
| `_history_asset_classification.py` | 143 | C 下沉 | `app/services/history_asset_classification.py` |
| `ui_prototype/_project_endpoints_helpers.py` | 87 | C 下沉 | `app/services/ui_prototype_flow.py` |
| `_project_config_helpers.py` | 115 | **删除（死代码）** | 逻辑与 `endpoints/project_config.py` 内同名函数三份重复，全仓 0 处导入 |

**验证**：`python -c "import app.main"` 成功；相关端点测试 **145 passed**；私有文件 **41 → 37**。

## 三、剩余 37 个文件台账

`db` 列为该文件中 `db.` / `session.` / `select(` 的出现次数（近似 DB 耦合度）。

### 3.1 顶层（15 个）

| # | 文件 | 行数 | db | 类型 | 下沉目标 / 说明 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `_case_quality_schemas.py` | 83 | 0 | A 保留 | 纯 Pydantic schema | — |
| 2 | `_deps.py` | 20 | 0 | A 保留 | 共享依赖（R4-7 产物，非业务） | — |
| 3 | `_case_quality_cost_routes.py` | 108 | 1 | B 抽离 | 成本统计编排 → `services/case_quality/cost_routes.py`（已有 `cost_statistics` 域可复用） | 3 |
| 4 | `_generation_batch_helpers.py` | 89 | 2 | C 下沉 | → `services/generation_batch_helpers.py` | 2 |
| 5 | `_generation_batch_routes.py` | 109 | 12 | B 抽离 | 批次 CRUD 编排 → `services/generation_batch_service.py` | 2 |
| 6 | `_generation_batch_save.py` | 284 | 24 | B 抽离 | 批量落库主逻辑 → `services/generation_batch_save.py`（最高耦合，最后做） | 2 |
| 7 | `_history_asset_helpers.py` | 41 | 1 | C 下沉 | ORM→响应转换 → `services/history_asset_helpers.py` | 3 |
| 8 | `_pipeline_artifacts_helpers.py` | 142 | 9 | C 下沉 | 制品查询助手 → `services/pipeline_artifacts_helpers.py` | 3 |
| 9 | `_pipeline_artifacts_mutations.py` | 163 | 6 | C 下沉 | 制品写操作 → `services/pipeline_artifacts_mutations.py` | 3 |
| 10 | `_pipeline_artifacts_routes.py` | 153 | 1 | B 抽离 | 制品路由编排 → 复用 8/9 下沉后的 service | 3 |
| 11 | `_test_case_crud_helpers.py` | 62 | 3 | C 下沉 | 用例串行化助手 → `services/test_case_crud_helpers.py` | 2 |
| 12 | `_test_case_crud_mutations.py` | 118 | 13 | C 下沉 | 用例写操作 → `services/test_case_crud_mutations.py`（注意与现有 `test_case` 域合并） | 2 |
| 13 | `_test_case_crud_routes.py` | 242 | 23 | B 抽离 | 用例路由编排 → 复用 11/12 下沉后的 service | 2 |
| 14 | `_user_perm_routes.py` | 86 | 1 | B 抽离 | 权限路由 → 业务已在 `user_service.PermissionService`，仅需合并回 `user.py` | 5 |
| 15 | `_user_role_routes.py` | 114 | 1 | B 抽离 | 角色路由 → 同上（`user_service.RoleService`） | 5 |

### 3.2 子目录（22 个）

| # | 文件 | 行数 | db | 类型 | 下沉目标 / 说明 | 批次 |
| --- | --- | --- | --- | --- | --- | --- |
| 16 | `execution_core/_analysis.py` | 326 | 22 | B 抽离 | 失败分析编排 → `services/execution_core/analysis.py` | 4 |
| 17 | `execution_core/_execution.py` | 246 | 21 | B 抽离 | 执行主流程 → `services/execution_core/execution.py` | 4 |
| 18 | `execution_core/_helpers.py` | 87 | 6 | C 下沉 | 执行助手 → `services/execution_core/helpers.py` | 4 |
| 19 | `iteration/_helpers.py` | 130 | 18 | C 下沉 | 迭代查询助手 → `services/iteration_service/`（与现有迭代域合并） | 5 |
| 20 | `iteration/_routes.py` | 234 | 16 | B 抽离 | 迭代路由 → 复用 19 + `iteration_service` | 5 |
| 21 | `pipeline_dashboard/_overview.py` | 113 | 11 | C 下沉 | 看板总览查询 → `services/pipeline_service/overview.py` | 5 |
| 22 | `pipeline_dashboard/_trends.py` | 187 | 9 | C 下沉 | 看板趋势查询 → `services/pipeline_service/trends.py` | 5 |
| 23 | `pipeline_dashboard/_utils.py` | 30 | 4 | C 下沉 | 看板工具 → `services/pipeline_service/utils.py` | 5 |
| 24 | `review_inbox/_queries.py` | 64 | 1 | C 下沉 | 评审收件箱查询 → `services/review_service/` | 5 |
| 25 | `review_inbox/_mutations.py` | 290 | 1 | C 下沉 | 评审决策写入 → `services/review_service/`（文件大，独立提交） | 5 |
| 26 | `review_inbox/_schemas.py` | 117 | 5 | B 抽离 | **名为 schemas 实含 router + DB**，schema 部分留、路由逻辑合并回 `review_inbox/__init__` | 5 |
| 27 | `test_case_ai_generate/_context.py` | 294 | 7 | B 抽离 | 上下文构建 → `services/test_case_generation/context.py` | 4 |
| 28 | `test_case_ai_generate/_generate.py` | 178 | 11 | B 抽离 | 生成编排 → `services/test_case_generation/generate.py` | 4 |
| 29 | `test_case_ai_generate/_precondition.py` | 138 | 19 | B 抽离 | 前置条件生成 → `services/test_case_generation/precondition.py` | 4 |
| 30 | `test_point/_helpers.py` | 29 | 3 | C 下沉 | 测试点助手 → `services/test_point/`（需新建包） | 4 |
| 31 | `test_point/_queries.py` | 168 | 6 | C 下沉 | 测试点查询 → 同上 | 4 |
| 32 | `test_point/_mutations.py` | 220 | 15 | C 下沉 | 测试点写入 → 同上 | 4 |
| 33 | `test_point/_management.py` | 160 | 13 | C 下沉 | 测试点管理 → 同上 | 4 |
| 34 | `ui_prototype/_parse_helpers.py` | 146 | 4 | C 下沉 | 解析助手 → `services/ui_spec_parser/` | 5 |
| 35 | `ui_prototype/_upload_helpers.py` | 110 | 2 | C 下沉 | 上传助手 → `services/ui_spec_parser/` | 5 |
| 36 | `ui_prototype/_project_endpoints_flow.py` | 118 | 16 | B 抽离 | 流程数据路由 → 业务进 `services/ui_prototype_flow.py`（已存在） | 5 |
| 37 | `ui_prototype/_project_endpoints_routes.py` | 218 | 25 | B 抽离 | 项目 CRUD 路由 → 复用 `ui_prototype_flow` + crud 层 | 5 |

## 四、统计与批次计划

| 类型 | 数量 | 说明 |
| --- | --- | --- |
| A 保留 | **2** | `_case_quality_schemas.py`、`_deps.py` |
| B 抽离 | **15** | 路由文件瘦身，业务进 service；阶段末再合并回父端点为 ≤10 收口 |
| C 下沉 | **20** | 整文件移走并删除 |
| 合计 | **37** | — |

| 批次 | 文件数 | 内容 | 风险 |
| --- | --- | --- | --- |
| 1 ✅ | 4 | 纯函数/死代码（已完成） | 低 |
| 2 | 6 | `_test_case_crud_*`（3）+ `_generation_batch_*`（3） | 中（用例主链路） |
| 3 | 6 | `_history_asset_*`（1）+ `_pipeline_artifacts_*`（3）+ `_case_quality_cost_routes`（1）+ 已完成的 2 | 中 |
| 4 | 9 | `execution_core/`（3）+ `test_point/`（4）+ `test_case_ai_generate/`（3） | 高（执行链路） |
| 5 | 12 | `ui_prototype/`（5）+ `review_inbox/`（3）+ `iteration/`（2）+ `pipeline_dashboard/`（3）+ `_user_*_routes`（2） | 高（面最广，注意 `_user_*` 已受 R4-7 依赖下沉影响） |

**每批完成后的验收**：`python -c "import app.main"` 成功 + 该域端点测试全绿 + `_*.py` 计数下降。

## 五、当前验收状态

- [x] 批次 1 完成，私有文件 **41 → 37**
- [x] `import app.main` 成功；批次 1 相关测试 **145 passed**
- [ ] 批次 2~5（剩余 35 个待办，其中 2 个 A 类永久保留）
