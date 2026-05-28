# 下一迭代遗留项推进规划

> 基于代码审查验证后的真实遗留项清单，剔除已完成但文档未同步的项。
> 审查日期：2026-05-25 | 关联文档：`iteration-pipeline-tasks.md`

***

## 文档信息

| 项 | 内容 |
|----|------|
| 文档版本 | v1.2 |
| 创建日期 | 2026-05-25 |
| 关联文档 | `iteration-pipeline-tasks.md`、`ui-prototype-flow-optimization-tasks.md` |
| 审查基线 | 逐项对照代码验证，剔除已完成项，仅保留真实遗留 |

***

## 状态图例

| 标记 | 含义 |
|------|------|
| ⬜ pending | 未开始 |
| 🔄 in_progress | 进行中 |
| ✅ done | 已完成 |
| ⏸️ blocked | 被阻塞 |

***

## ⚠️ 项目开发规则（实施时必须遵守）

> 以下规则摘自 `.trae/rules/project_rules.md`，每个任务实施前必须回顾，实施后必须自检。

### 核心原则

**真实环境测试、禁止 Mock、覆盖率≥95%；最小改动、外科手术式修改、杜绝冗余。**

> ⚠️ 特别说明：TD-02 中使用 MockAIClient 是因为场景 3/5 依赖外部 AI API 不可控，属于"外部依赖隔离"而非"业务逻辑 Mock"，不违反禁止 Mock 原则。

### 规则速查表

| # | 规则 | 实施自检项 |
|---|------|-----------|
| R1 | 变量函数 lowerCamelCase，类 UpperCamelCase，常量 UPPER_SNAKE_CASE | 命名扫描 |
| R2 | 4 空格缩进，行宽 ≤ 120 | lint 检查 |
| R3 | 公开方法必须加类型注解与文档注释 | 代码审查 |
| R4 | 只注释业务原因与边界场景，**禁止无效注释** | 代码审查 |
| R5 | Python 强制类型注解，IO 统一 with 管理，字符串只用 f-string | mypy + 代码审查 |
| R6 | TS 禁用 any，强制空值处理，异步统一 async/await | vue-tsc + 代码审查 |
| R7 | 单文件 ≤ 350 行（代码粘性高可放宽，但需考虑拆分模块） | 文件行数检查 |
| R8 | 依赖构造函数注入，**禁止直接 new 实例** | 代码审查 |
| R9 | SQL/命令注入零容忍，仅用参数化/列表传参 | SQL 审查 |
| R10 | 密钥禁用硬编码，统一环境变量读取 | grep 硬编码检查 |
| R11 | 日志脱敏敏感字段 | 代码审查 |
| R12 | 所有外部输入必须经过模型校验才可进入业务 | Schema 校验 |
| R13 | **禁止循环内执行 SQL**，杜绝 N+1 | SQL 审查 |
| R14 | 批量写入使用 batch | 代码审查 |
| R15 | 核心分支覆盖率 ≥ 95% | pytest --cov |
| R16 | 代码同步配套正常、空值、异常、边界用例 | 测试审查 |
| R17 | 使用真实测试库，用例执行后自动清理测试数据 | 测试审查 |
| R18 | **禁止 TODO 与空占位**，未实现逻辑抛 NotImplementedError | grep TODO 检查 |
| R19 | IO/网络/解析强制异常捕获 | 代码审查 |
| R20 | 深层属性必须空安全兜底 | 代码审查 |
| R21 | 重复逻辑自动抽工具方法 | 代码审查 |
| R22 | 删除废弃注释代码 | 代码审查 |
| R23 | Bug 修复定位根因，只改必要代码并补充验证用例 | 代码审查 |
| R24 | 合并需全量测试、类型检查无错、CR 通过 | CI 检查 |
| R25 | 依赖锁定版本，库表变更附带迁移与回滚 | 迁移脚本 |

### 每个任务完成前的自检清单

- [ ] 无 TODO/空占位/FIXME（R18）
- [ ] 公开方法有类型注解 + 文档注释（R3）
- [ ] 无循环内 SQL（R13）
- [ ] 无硬编码密钥（R10）
- [ ] 异常捕获覆盖 IO/网络/解析（R19）
- [ ] 深层属性空安全兜底（R20）
- [ ] 单文件 ≤ 350 行（R7）
- [ ] 核心分支覆盖率 ≥ 95%（R15）
- [ ] 测试配套正常 + 空值 + 异常 + 边界用例（R16）
- [ ] `pytest` 全量通过 + `mypy`/`vue-tsc` 类型检查无错（R24）

***

## 总览

| 优先级 | 数量 | 说明 |
|--------|------|------|
| 🔴 P0 | 1 | 文档状态同步（阻塞后续跟踪） |
| 🔴 P1 | 2 | 技术债 + 测试缺口（影响数据安全/质量保障） |
| 🟡 P2 | 4 | 功能补全（影响用户体验/运维能力） |
| 🟢 P3 | 3 | 体验优化（非阻塞） |
| ⚪ 远期 | 6 | 长期规划，本迭代不排期 |

***

## 🔴 P0：文档状态同步

### DOC-01：iteration-pipeline-tasks.md 状态同步

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: —
- **Description**: 代码审查发现以下 5 个任务代码已完成，但文档详细页仍标 `⬜ pending`，与总览表 `✅ done` 不一致。需统一更新。M3-T08（集成测试）因 test_m3_e2e.py 仍被 skip，归入 TD-02 一并处理，不在本任务范围内。

| ID | 标题 | 代码证据 |
|----|------|----------|
| M3-T05 | 场景 3 流水线 | `app/pipelines/scenarios/scenario_3.py` 完整 7 步 Pipeline |
| M3-T06 | 场景 5 流水线 | `app/pipelines/scenarios/scenario_5.py` 完整 11 步 Pipeline |
| M3-T07 | 测试数据准备与标注集 | `tests/data/` 下 3 个项目数据集 + expected_verdicts.json |
| M4-T01 | 先验质量分服务 | `app/pipelines/steps/_signal_scoring.py` _compute_prior_score + persist.py D级标 pending_review |
| M4-T02 | 后验质量分回填 | `app/services/posterior_score_service.py` 完整实现 |

- **Deliverables**:
  - 更新 `iteration-pipeline-tasks.md` 中上述 5 个任务的详细页状态为 ✅ done
  - 补充自测记录（代码文件清单 + 关键函数）
  - 更新总进度计数：53/54（当前文档写 51/54；M3-T08 因测试被 skip 不计入完成）
- **Acceptance**:
  - [ ] 总览表与详细页状态一致
  - [ ] 总进度更新为 53/54
  - [ ] 每个任务补充代码证据说明

***

## 🔴 P1：技术债 + 测试缺口

### TD-01：delete_capability 硬删除改软删除

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: `app/services/test_capability_service.py:delete_capability` 当前执行 `db.delete()` 硬删除，注释标注"M1 阶段临时方案"。TestCapability 模型已有 `status` 字段（active/deprecated/archived）和 `CapabilityStatus` 枚举，但删除操作未走 LifecycleService 状态流转。

- **现状分析**:
  - `TestCapability.status` 支持 `active`/`deprecated`/`archived` 三态
  - `CapabilityStatus` 枚举已定义
  - `test_points` 关联使用 `SET NULL`，硬删除后测试点变孤儿
  - 无 LifecycleService 统一管控 Capability 状态变更

- **Deliverables**:
  - `app/services/test_capability_service.py`：`delete_capability` 改为调用 LifecycleService 将 status 置为 `archived`
  - `app/services/lifecycle_service/`：**新建** `_capability_rules.py`（Capability 状态流转规则：active → deprecated → archived）+ `_capability_service.py`（Capability 生命周期服务，含审计日志）。现有 LifecycleService 仅服务 TestCase，对 Capability 需从零新建
  - 查询方法 `get_capabilities_by_project` 默认过滤 `archived` 状态
  - 迁移脚本：无（status 字段已存在）
  - 数据修复脚本：扫描 `test_points` 表中 `capability_id IS NULL` 但对应 `test_capabilities` 记录仍存在的行，恢复关联（硬删除时期遗留的孤儿数据）
  - 单测覆盖软删除 + 状态流转 + 查询过滤

- **Acceptance**:
  - [ ] `delete_capability` 不再执行 `db.delete()`，改为 status='archived'
  - [ ] Capability 状态变更经 LifecycleService，记录审计日志
  - [ ] 默认查询排除 archived 能力
  - [ ] 已归档能力的 test_points 不变孤儿（保留 capability_id）
  - [ ] 单测覆盖率 ≥ 95%

- **Self-Test**:
  ```powershell
  pytest tests/services/test_test_capability_service.py -v
  pytest tests/services/test_lifecycle_service.py -v
  ```

***

### TD-02：场景 3/5 集成测试解除 skip

- **Status**: ⬜ pending
- **Estimate**: 1.5d
- **Depends on**: —
- **Description**: `tests/pipelines/test_scenario_3.py`、`test_scenario_5.py` 和 `tests/integration/test_m3_e2e.py` 整体标记 `pytest.mark.skip`，导致场景 3/5 的端到端流程和 M3 集成测试无自动化验证。M3-T08（集成测试与文档收口）的完成依赖此任务。

- **现状分析**:
  - 场景 3/5 代码已完成（scenario_3.py / scenario_5.py）
  - 测试文件已编写完整，但因依赖真实 AI API 而 skip
  - 项目已有 `MockAIClient`（`app/ai/mock_client.py`），场景 1/2/4 的测试已使用
  - 场景 3/5 测试未切换到 MockAIClient

- **Deliverables**:
  - 修改 `test_scenario_3.py`：移除 `pytest.mark.skip`，注入 `MockAIClient`
  - 修改 `test_scenario_5.py`：移除 `pytest.mark.skip`，注入 `MockAIClient`
  - 修改 `test_m3_e2e.py`：移除 `pytest.mark.skip`，注入 `MockAIClient`
  - MockAIClient 补充场景 3/5 所需的 mock 返回值（reverse_infer / scenario_candidates / backward_scan / forward_scan）
  - 确保测试可脱离 AI_API_KEY 独立运行

- **Acceptance**:
  - [ ] `pytest tests/pipelines/test_scenario_3.py -v` 全部通过（无 skip）
  - [ ] `pytest tests/pipelines/test_scenario_5.py -v` 全部通过（无 skip）
  - [ ] `pytest tests/integration/test_m3_e2e.py -v` 全部通过（无 skip）
  - [ ] 无 AI_API_KEY 环境变量依赖
  - [ ] 覆盖场景 3 的关键路径：UI反推 → 候选提取 → 对齐 → 生成
  - [ ] 覆盖场景 5 的关键路径：历史指纹 → 反推 → 双向扫描 → 合并 → 生成

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_scenario_3.py tests/pipelines/test_scenario_5.py tests/integration/test_m3_e2e.py -v
  ```

***

## 🟡 P2：功能补全

### FN-01：Pipeline 暂停超时自动取消

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: `PIPELINE_PAUSE_TIMEOUT_DAYS=7` 配置已存在（`app/core/config.py:89`、`app/services/config_service.py:44`），但无后台任务消费此配置。Pipeline 暂停后若用户未在 7 天内确认，运行将永远停留在 `waiting_for_user` 状态。

- **Deliverables**:
  - `app/services/pipeline_timeout_service.py`：定时扫描 `pipeline_run` 表中 `status='waiting_for_user'` 且 `paused_at < now() - timeout_days` 的记录，自动取消
  - 取消时：status → `cancelled`，记录审计日志，通知前端
  - 集成到运维定时任务框架。技术选型：**APScheduler**（轻量，Python 原生，无需额外消息队列），注册为 FastAPI startup 事件。备选：外部 cron 调用 CLI 脚本（适用于容器化部署）
  - 单测覆盖：正常超时取消、未超时不触发、边界值（恰好 7 天）

- **Acceptance**:
  - [ ] 超时 Pipeline 自动取消，status 变为 `cancelled`
  - [ ] 审计日志记录取消原因 `pause_timeout`
  - [ ] 未超时的 Pipeline 不受影响
  - [ ] 超时天数从 config_service 动态读取
  - [ ] 单测覆盖率 ≥ 95%

- **Self-Test**:
  ```powershell
  pytest tests/services/test_pipeline_timeout_service.py -v
  ```

***

### FN-02：Pipeline 取消运行 API

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: Pipeline 权限服务已定义 `cancel` 动作（`pipeline_permission_service.py:52`），审计服务已定义 `pipeline_cancel` 事件（`audit_service.py:33`），但缺少实际的取消 API 端点和 Runner 取消逻辑。

- **Deliverables**:
  - `app/api/v1/endpoints/pipeline_artifacts.py`：补充 `POST /{run_id}/cancel` 端点（与现有 summary/inferred-summary 同一 router，路径 `/api/v1/pipeline/{run_id}/cancel`）
  - 权限校验：admin / qa_lead 可取消任意运行，普通用户仅可取消自己发起的
  - Runner 取消逻辑：在 `PipelineRunner.run()` 的 Step 循环中，每次 Step 执行前检查 `PipelineRun.status == 'cancelled'`（由 API 端点写入 DB），若已取消则跳过剩余 Step 并将 run 状态设为 `cancelled`
  - 审计日志记录取消操作
  - 前端 `PipelineProgress.vue`：添加取消按钮（仅 running/waiting_for_user 状态可取消）
  - 单测覆盖权限校验 + 状态校验 + 取消流程

- **Acceptance**:
  - [ ] `POST /pipeline/{run_id}/cancel` 返回 200
  - [ ] running/waiting_for_user 状态可取消，其他状态返回 409
  - [ ] 权限校验通过 pipeline_permission_service
  - [ ] 取消后审计日志写入 pipeline_cancel 事件
  - [ ] 前端取消按钮仅在可取消状态显示
  - [ ] 单测覆盖率 ≥ 95%

- **Self-Test**:
  ```powershell
  pytest tests/api/test_pipeline_cancel.py -v
  ```

***

### FN-03：Pipeline 产物详情展开

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: Pipeline 进度页当前仅展示 Step 状态和耗时，产物（artifact）payload 仅显示摘要，无法展开查看详细内容。ADR-3 标注"暂不展开，M2 阶段加 artifact 详情 API 后再实现"。现有 `pipeline_artifacts.py` 已有 `GET /{run_id}/summary` 和 `GET /{run_id}/inferred-summary`，覆盖了部分场景，但缺少通用的按 artifact_id 查询端点。

- **Deliverables**:
  - `app/api/v1/endpoints/pipeline_artifacts.py`：补充 `GET /{run_id}/artifacts/{artifact_id}` 通用查询端点（现有 summary/inferred-summary 已覆盖部分场景）
  - 返回 artifact 完整 payload（JSON），大 payload 分页支持
  - 前端 `PipelineProgress.vue`：Step 行点击展开 artifact 详情面板
  - 大 payload 截断提示（超过 10KB 显示前 N 条 + 折叠）
  - 单测覆盖正常查询 / 不存在 / 大 payload 截断

- **Acceptance**:
  - [ ] API 返回 artifact 完整 payload
  - [ ] 前端可展开查看每个 Step 的输出详情
  - [ ] 大 payload 有截断提示
  - [ ] 单测覆盖率 ≥ 95%

- **Self-Test**:
  ```powershell
  pytest tests/api/test_pipeline_artifacts.py -v
  ```

***

### FN-04：testpoint_alignment 覆盖率重测与补全

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: —
- **Description**: 文档记录 `testpoint_alignment.py` 覆盖率仅 8% 行 / 0% 分支，但该模块已重构拆分为 `_step.py` + `_helpers.py` 子包，`test_testpoint_alignment.py` 已测试纯函数。需重新测量实际覆盖率并补全缺失测试。

- **Deliverables**:
  - 运行覆盖率报告确认当前实际数据
  - 补全 `_step.py` 中 TestPointAlignment 类的集成测试
  - 目标：行覆盖率 ≥ 90%，分支覆盖率 ≥ 85%

- **Acceptance**:
  - [ ] 覆盖率报告确认行 ≥ 90%，分支 ≥ 85%
  - [ ] 无 skip 测试
  - [ ] 覆盖 should_run / cache_key / validate_output / fallback

- **Self-Test**:
  ```powershell
  pytest tests/pipelines/test_testpoint_alignment.py -v --cov=app/pipelines/steps/testpoint_alignment --cov-branch
  ```

***

## 🟢 P3：体验优化

### UX-01：Pipeline 进度页 WebSocket 升级

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: Pipeline 进度页当前使用轮询获取运行状态。项目已有完整 WebSocket 基础设施（`app/utils/websocket.py` ConnectionManager + `src/utils/websocket.ts` WebSocketClient + `app/services/push_service.py` PushService），但 Pipeline 进度页未接入。

- **Deliverables**:
  - 后端：Pipeline Runner 在 Step 完成时通过 PushService 推送进度消息
  - 前端：`PipelineProgress.vue` 接入 WebSocket 替代轮询
  - 降级策略：WebSocket 连接失败时回退到轮询
  - 单测覆盖推送逻辑

- **Acceptance**:
  - [ ] Step 完成时前端实时收到进度更新（延迟 < 1s）
  - [ ] WebSocket 断连后自动降级为轮询
  - [ ] 不影响现有轮询逻辑（降级兼容）

***

### UX-02：流程完整度面板

- **Status**: ⬜ pending
- **Estimate**: 1d
- **Depends on**: —
- **Description**: UI 原型图流程编排 M2 浏览增强中唯一未实现的功能。用户需要在生成前直观了解主干/分支/异常/旁路流程的覆盖完整度。

- **Deliverables**:
  - `src/components/case/FlowCompletenessPanel.vue`：展示流程覆盖统计
  - 统计维度：主干节点数、分支数、异常路径数、旁路数、未连线节点数、缺条件连线数
  - 数据来源：与 `FlowIssueDialog.vue`（消费 `validate_flow_structure` 的 errors/warnings）不同，完整度面板需要**节点计数统计**，需新增 `compute_flow_stats()` 工具函数从 flow_sort_data 中计算各类型节点/连线数量
  - 集成到 FlowSortEditor 工具栏或侧边面板

- **Acceptance**:
  - [ ] 面板展示各类型流程节点计数
  - [ ] 未连线/缺条件等异常高亮提示
  - [ ] 不影响现有 flow_sort_data 提交逻辑

***

### UX-03：搜索框小屏响应式

- **Status**: ⬜ pending
- **Estimate**: 0.5d
- **Depends on**: —
- **Description**: FlowSortToolbar 搜索框在小屏下可能被挤压，需增加响应式处理。

- **Deliverables**:
  - `FlowSortToolbar.vue`：小屏下搜索框收缩为图标按钮，点击展开
  - 断点：≤768px 触发响应式布局

- **Acceptance**:
  - [ ] 768px 以下搜索框不挤压工具栏
  - [ ] 点击图标可展开搜索输入框

***

## ⚪ 远期规划（本迭代不排期）

以下项经验证仍适用，但优先级低或依赖未就绪，留待后续迭代评估：

| # | 功能 | 说明 | 保留原因 |
|---|------|------|----------|
| LT-01 | 布局保存到后端 | 画布坐标/布局策略持久化 | 需独立接口设计，避免污染 flow_sort_data |
| LT-02 | 自动推断页面跳转关系 | AI 分析 UI 原型自动生成连线 | 依赖 AI 能力增强，当前手动连线可满足 |
| LT-03 | 模块分组背景 | 画布中按模块分组显示背景色 | 视觉增强，非功能需求 |
| LT-04 | 分支折叠状态持久化 | collapsedParentNodeIds 保存到后端 | 当前为组件本地状态，刷新丢失可接受 |
| LT-05 | 按路径生成测试用例 | 选择某条路径单独生成 | 需生成接口支持路径级上下文，架构改动大 |
| LT-06 | 页面流程与测试点双向推荐 | 流程节点推荐关联测试点 | 需推荐算法，当前手动选择可满足 |

***

## 已关闭项（审查确认已完成）

以下项在原盘点中列为遗留，经代码验证已实际完成，从下个迭代中移除：

| # | 原遗留项 | 关闭原因 | 代码证据 |
|---|----------|----------|----------|
| ✅ | M3-T05/T06/T07 场景 3/5 流水线 + 测试数据 | 代码已完成 | scenario_3.py / scenario_5.py / tests/data/ |
| ✅ | M4-T01/T02 先验/后验质量分 | 代码已完成 | _signal_scoring.py / posterior_score_service.py |
| ✅ | draft 自动转 active ADR | 已通过 draft + D级 pending_review 解决 | persist.py:112-114 |
| ✅ | 搜索定位坐标优化 | 已用 fitView 替代简化公式 | useFlowSearch.ts:68 |
| ✅ | 触发条件推断后端模板 | _infer_condition 已实现 | helpers.py |
| ✅ | warnings 展示 | FlowIssueDialog.vue 已实现 | FlowIssueDialog.vue |
| ✅ | 点击节点高亮上下游 | useFlowPathHighlight.ts 已实现 | useFlowPathHighlight.ts |
| ✅ | 连线悬浮条件展示 | FlowSortEdgeTooltip.vue 已实现 | FlowSortEdgeTooltip.vue |
| ✅ | 分支折叠/展开 | collapsedParentNodeIds 已实现 | useFlowSortEditor.ts |
| ✅ | 生成前问题列表 | FlowIssueDialog.vue 已实现 | FlowIssueDialog.vue |
| ✅ | 路径播放 | 播放控件已实现 | FlowSortEdgeTooltip.vue:40-69 |
| ⚠️ | reverse_infer 集成覆盖率 8% | 单元测试已达 89%，但集成覆盖率仍低（test_m3_e2e.py 被 skip），归入 TD-02 一并解决 | test_reverse_infer.py 48/48 pass；test_m3_e2e.py skip |

***

## 任务依赖关系

```
DOC-01 (文档同步) ─── 无依赖，优先完成
  │
TD-01 (硬删除改软删除) ─── 无依赖
TD-02 (场景3/5测试解除skip) ─── 无依赖
  │
FN-01 (暂停超时自动取消) ─── 无依赖
FN-02 (取消运行API) ─── 无依赖，可与 FN-01 并行
FN-03 (产物详情展开) ─── 无依赖
FN-04 (覆盖率重测) ─── 无依赖
  │
UX-01 (WebSocket升级) ─── 无依赖
UX-02 (完整度面板) ─── 无依赖
UX-03 (搜索框响应式) ─── 无依赖
```

***

## 建议排期

| 阶段 | 任务 | 估时 |
|------|------|------|
| 第 1 批 | DOC-01 → TD-01 → TD-02 | 3d |
| 第 2 批 | FN-01 → FN-02 → FN-03 → FN-04 | 3.5d |
| 第 3 批 | UX-01 → UX-02 → UX-03 | 2.5d |
| **合计** | **13 个任务** | **9d** |

***

## 变更日志

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-25 | v1.0 | 初始版本，基于代码审查验证后的真实遗留项 |
| 2026-05-25 | v1.1 | 审查修正：C1 总进度 54→53（M3-T08 归入 TD-02）；C2 TD-01 LifecycleService 描述改为"新建"；C3 TD-01 补充数据修复脚本；C4 FN-03 改为"补充"现有 API；M5 TD-02 补充 test_m3_e2e.py；M6 FN-01 明确 APScheduler 选型；M7 FN-02 明确端点注册位置；M8 FN-02 补充 Runner 取消技术方案；M9 reverse_infer 集成覆盖率从已关闭移回待做；M10 M3-T08 归入 TD-02；UX-02 区分统计与校验数据源 |
| 2026-05-25 | v1.2 | 新增"项目开发规则"章节（25 条规则速查表 + 10 项自检清单），TD-02 MockAIClient 特别说明 |
