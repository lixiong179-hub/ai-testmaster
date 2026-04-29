# 迭代用例生成与维护流水线 — 规划文档

> 解决跨迭代的用例生成、去重、维护问题。配套任务追踪：`iteration-pipeline-tasks.md`。

---

## 文档信息

| 项 | 内容 |
|----|------|
| 项目名称 | 迭代用例生成与维护流水线 |
| 文档版本 | v2.0 |
| 编制日期 | 2026-04-29 |
| 更新日期 | 2026-05-01 |
| 关联文档 | `iteration-pipeline-tasks.md` |
| 变更摘要 | v2.0 — 补全状态机、AI Client 抽象、权限模型、配置管理、审计日志、Pipeline 重跑策略、场景 6-8、FMEA F11-F15、API 设计原则、Pipeline 版本升级路径、评审回滚机制、M0 基线阶段 |

---

## 1. 问题与目标

### 1.1 问题
- 历史用例已通过 XMind 导入并生成，新迭代有功能新增 + UI 重构。
- 旧用例不能全删重生（丢失历史、丢失人工修订、丢失 locator）。
- AI 看 UI 图直接生成会大量重复，且漏掉真正的"新增点"。
- 旧用例需要系统性维护：弃用 / 修改 / 仅 UI 重录。

### 1.2 目标
- 用例库当作**长期资产**，跨迭代可演进、可追溯、可回滚。
- AI 在每一步只是"建议者"，决策权在精心设计的人工门槛 + 质量红线。
- 所有变更可审计、所有产物可缓存、所有 Step 可重放。

---

## 2. 核心场景（8 类）

| 场景 | 业务信号 | 结构信号 | 视觉信号 | 历史信号 | 关键矛盾 |
|:-:|:-:|:-:|:-:|:-:|---|
| 1 | ✅PRD | ✅测试点 | ✅UI | ❌ | 测试点-UI 对齐 |
| 2 | ✅PRD | ✅测试点 | ❌ | ❌ | 操作步骤具象化 |
| 3 | ❌ | ❌ | ✅UI | ❌ | 缺业务上下文，AI 在猜 |
| 4 | ✅PRD | ✅旧测试点 | ✅UI | ✅旧用例 | 去重 + 旧用例维护 |
| 5 | ⚠️弱 | ✅旧测试点 | ✅原型 | ✅旧用例 | PRD 反推 + 维护 |
| 6 | ✅PRD | ✅测试点 | ❌ | ✅旧用例 | 无 UI 但有历史，旧用例业务逻辑复用 |
| 7 | ⚠️弱 | ❌ | ❌ | ✅旧用例 | 紧急修复：仅变更影响分析，最小化生成 |
| 8 | ✅PRD | ✅测试点 | ✅UI | ✅旧用例 | Capability 拆分/合并导致用例重组 |

**8 个场景共用一条流水线**，区别只是哪些 Step 开启 / 跳过。

**场景补充说明**：
- **场景 6**：后端接口变更但 UI 未改（如 API 字段增删、状态机变更），旧用例的业务逻辑步骤可复用，但断言需更新。Pipeline 走反向扫描 + 业务逻辑 diff，不触发 UI 相关 Step。
- **场景 7**：紧急 hotfix 场景，输入极简。Pipeline 仅执行 BackwardScan + 变更影响范围分析，不生成新用例，只标记受影响的旧用例为 `needs_modify`。
- **场景 8**：业务能力拆分（如"用户管理"拆为"账号管理"+"权限管理"）或合并。需要 `testpoint_migration` 映射表（见 O1），Pipeline 识别 Capability 变更后触发批量用例重组。

---

## 3. 概念模型

### 3.1 信号二维分类

```
              ┌──────────────┬──────────────┬──────────────┐
              │ Provided     │ Inferred     │ Inherited    │
              │ (人类输入)    │ (AI 推导)    │ (历史沉淀)    │
┌─────────────┼──────────────┼──────────────┼──────────────┤
│ Capability  │ PRD/补充表单  │ 从UI反推业务  │ 旧业务能力     │
│ TestPoint   │ XMind/手填   │ 从PRD/UI抽取  │ 旧测试点      │
│ TestCase    │ 用户手写      │ AI 生成/修改  │ 旧用例        │
│ Locator     │ 录制         │ 原型猜测(低)  │ 旧 locator   │
└─────────────┴──────────────┴──────────────┴──────────────┘
```

### 3.2 核心实体与不变式

| 实体 | 关键不变式 |
|---|---|
| `Capability` | 同项目内 `key` 唯一；UI 改不影响它 |
| `TestPoint` | 必关联 1 个 Capability；自身版本化 |
| `TestCase` | 必关联 1 个 TestPoint 版本；修改 → 创建新版本 |
| `Locator` | **独立版本化**：Locator 变更不创建新 TestCase 版本，但标记 `locator_status=stale`，需重录验证后更新 Locator 自身版本 |
| `Iteration` | 关联 0..N 个 PRD/Prototype 输入 |
| `IterationReview` | finalize 前可自由回滚单条决策（见 §4.3）；finalize 后 1h 内允许有限回滚（需 admin/qa_lead 权限）；超过 1h 后不可变 |
| `PipelineRun` | 幂等 key = (iteration_id, input_hash) |
| `Artifact` | 含 `confidence`、`provenance`、`schema_version` |
| `AuditLog` | 不可变、仅追加；记录所有状态变更、决策、权限操作 |

**Locator 与 TestCase 版本解耦规则**：
1. Locator 变更（UI 重构导致元素定位变化）→ 仅更新 Locator 版本，TestCase 版本号不变，但 `locator_status` 标记为 `stale`。
2. TestCase 业务逻辑变更 → 创建新 TestCase 版本，新版本继承旧版本的 Locator 引用（`locator_status=pending_review`，需验证是否仍有效）。
3. 两者同时变更 → 先创建新 TestCase 版本，再处理 Locator 更新，最终 `locator_status` 由重录结果决定。

### 3.3 权限模型

| 操作 | 项目管理员 | 迭代负责人 | 评审者 | 只读成员 |
|---|:-:|:-:|:-:|:-:|
| 创建迭代 | ✅ | ✅ | ❌ | ❌ |
| 上传迭代输入 | ✅ | ✅ | ❌ | ❌ |
| 触发 Pipeline | ✅ | ✅ | ❌ | ❌ |
| 评审决策（采纳/否决） | ✅ | ✅ | ✅ | ❌ |
| Finalize 评审 | ✅ | ✅ | ❌ | ❌ |
| 回滚评审决策 | ✅ | ✅ | ❌ | ❌ |
| 弃用/归档用例 | ✅ | ✅ | ❌ | ❌ |
| 查看用例/评审 | ✅ | ✅ | ✅ | ✅ |
| 导出用例 | ✅ | ✅ | ✅ | ✅ |
| 管理项目成员 | ✅ | ❌ | ❌ | ❌ |

**角色分配规则**：
- 迭代创建者自动成为"迭代负责人"。
- 项目管理员可转让迭代负责人。
- 评审者由迭代负责人指定，范围限定在本迭代。
- 只读成员可查看但不可变更任何实体状态。

**权限检查点**：
- Pipeline 触发前检查 `触发 Pipeline` 权限。
- 评审决策提交前检查 `评审决策` 权限 + 评审锁（见 M2-T01）。
- Finalize 前检查 `Finalize 评审` 权限。
- 所有权限拒绝返回 403 + 明确提示缺少哪个角色。

### 3.4 AI Client 抽象层

所有 AI 调用必须通过统一抽象层，禁止 Step 直接调用模型 API。

```python
class AIClient(Protocol):
    """统一 AI 调用接口"""
    async def complete(self, prompt: str, *, 
                       system: str | None = None,
                       schema: type[BaseModel] | None = None,
                       temperature: float = 0.3,
                       max_tokens: int = 4096,
                       metadata: dict | None = None) -> AIResponse: ...

class AIResponse:
    content: str
    parsed: BaseModel | None     # schema 不为 None 时自动解析
    usage: TokenUsage            # prompt_tokens, completion_tokens
    model_version: str           # 实际使用的模型版本
    latency_ms: int
    raw_response: dict           # 原始返回，用于调试

class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float        # 基于配置的单价计算
```

**关键约束**：
1. **模型版本可切换**：配置 `AI_MODEL_NAME` 即可切换底层模型，Step 代码无需修改。
2. **Token 预算**：每次 PipelineRun 启动时设定 `token_budget`，超出时 Pipeline 暂停等人工确认。
3. **重试与降级**：AIClient 内置重试（3 次），支持 fallback 模型（主模型失败时切备用模型，标 `degraded`）。
4. **可观测性**：每次调用记录 `ai_call_log(model, prompt_tokens, completion_tokens, cost, latency, step_name, run_id)`。
5. **Mock 友好**：测试环境可注入 `MockAIClient`，返回预设 JSON，零成本跑单测。

### 3.5 配置管理

所有可调参数集中管理，禁止硬编码。

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `LIFECYCLE_DEPRECATE_COOLDOWN_HOURS` | 24 | deprecated → archived 冷却时间 |
| `AI_MODEL_NAME` | `gpt-4o` | 主模型 |
| `AI_FALLBACK_MODEL_NAME` | `gpt-4o-mini` | 降级模型 |
| `AI_TOKEN_BUDGET_PER_RUN` | 500000 | 单次 PipelineRun token 上限 |
| `AI_TEMPERATURE` | 0.3 | 默认温度 |
| `AI_MAX_RETRIES` | 3 | 单次调用重试次数 |
| `AI_PRICE_PER_1K_INPUT` | 0.0025 | 主模型输入单价（USD/1K tokens） |
| `AI_PRICE_PER_1K_OUTPUT` | 0.01 | 主模型输出单价（USD/1K tokens） |
| `AI_FALLBACK_PRICE_PER_1K_INPUT` | 0.00015 | 降级模型输入单价 |
| `AI_FALLBACK_PRICE_PER_1K_OUTPUT` | 0.0006 | 降级模型输出单价 |
| `AI_RETRY_BACKOFF_BASE` | 1 | 指数退避基数（秒） |
| `CONFIDENCE_THRESHOLD` | 0.7 | 低于此值强制人工确认 |
| `REVIEW_LOCK_TTL_HOURS` | 24 | 评审锁过期时间 |
| `PIPELINE_PAUSE_TIMEOUT_DAYS` | 7 | Pipeline 暂停超时自动取消 |
| `SUMMARY_MAX_LENGTH` | 200 | summary 最大字数 |
| `LINEAGE_CHAIN_WARNING_LENGTH` | 3 | 血缘链长度警告阈值 |
| `PRIOR_QUALITY_D_THRESHOLD` | 45 | 先验质量 D 级阈值 |
| `POSTERIOR_MIN_EXECUTIONS` | 3 | 后验分最少执行次数 |
| `PIPELINE_VERSION` | `1.0` | Pipeline 逻辑版本，变更时强制重跑 |
| `REVIEW_UNDO_WINDOW_MINUTES` | 60 | finalize 后允许回滚的时间窗口（分钟） |
| `BATCH_SIZE_BACKWARD_SCAN` | 50 | 反向扫描每批用例数 |
| `BATCH_SIZE_SUMMARY_BACKFILL` | 20 | summary 回填每批用例数 |
| `AUTO_APPROVE_MIN_GRADE` | `A` | 自动通过最低先验等级（`A`/`B`/`C`/`NONE`，`NONE` 表示全部需人工） |

**配置来源优先级**：环境变量 > `.env` 文件 > 代码默认值。

### 3.6 审计日志（Audit Log）

所有关键操作写入不可变、仅追加的 `audit_log` 表。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT PK | 自增 |
| `created_at` | DATETIME | 操作时间（服务器时间） |
| `actor_id` | INT FK | 操作人 |
| `action` | VARCHAR(64) | 操作类型枚举 |
| `target_kind` | VARCHAR(32) | 目标实体类型 |
| `target_id` | INT | 目标实体 ID |
| `detail` | JSON | 变更详情（before/after 快照） |
| `run_id` | INT FK NULL | 关联 PipelineRun |
| `iteration_id` | INT FK NULL | 关联迭代 |

**action 枚举**：`lifecycle_transition`, `review_decide`, `review_rollback`, `review_undo`, `review_finalize`, `pipeline_start`, `pipeline_step_complete`, `pipeline_pause`, `pipeline_resume`, `pipeline_cancel`, `permission_change`, `config_change`, `case_version_create`, `locator_version_create`, `force_cancel_review`

**不可变性保证**：`audit_log` 表禁止 UPDATE 和 DELETE（数据库触发器强制）。

---

## 4. 用例生命周期状态机

### 4.1 状态与迁移图

```
   ┌──────┐     ┌──────────────┐     ┌───────────┐
   │draft │────>│pending_review│────>│   active   │
   └──────┘     └──────────────┘     └─────┬─────┘
                                       │      ^
                                       │      │
                                       v      │
                                ┌─────────────┐ │  重录后
                                │locator_broken│─┘
                                └──────┬──────┘
                                       │
                                       v
                                ┌──────────────┐
                                │ deprecated   │
                                └──────┬───────┘
                                       │ (≥24h)
                                       v
                                ┌──────────┐
                                │ archived │ (终态)
                                └──────────┘

   active ──(review 决定)──> needs_modify ──(创建新版本)──> 新版本进 pending_review
                                                                旧版本进 archived
```

### 4.2 完整迁移规则

| 从 → 到 | 前置条件 | 附加动作 |
|---|---|---|
| `draft` → `pending_review` | AI 生成完成 | 写入 `prior_quality_score` |
| `pending_review` → `active` | 人工评审通过；**M1 阶段允许先验分 ≥ A 自动通过**（配置 `AUTO_APPROVE_MIN_GRADE` = `A`，后续可调为 `B`） | 记录 `review_decision`（auto_approve=true 标记） |
| `pending_review` → `needs_modify` | 人工评审否决 | 记录 `modification_hint` |
| `pending_review` → `deprecated` | 人工判定无价值 | 需 `deprecate_reason` |
| `active` → `needs_modify` | 必须附带 `last_review_id` | 记录 `modification_hint` |
| `active` → `locator_broken` | UI 变更导致 locator 失效 | 加入重录队列 |
| `active` → `deprecated` | 需 `deprecate_reason` + `review_id` | — |
| `needs_modify` → (新版本 `pending_review`) | 创建新 case 版本，`parent_case_id` 指向原 case | 旧 case → `archived` |
| `locator_broken` → `active` | 重录验证通过 | 更新 Locator 版本 |
| `locator_broken` → `deprecated` | 需 `deprecate_reason` | — |
| `deprecated` → `archived` | 冷却 ≥ 24h | — |
| `archived` → (不可恢复) | — | 要恢复则复制为新用例（`draft`） |

**全局约束**：
1. 只能由 `LifecycleService` 驱动迁移，禁止直接 SQL update。
2. 所有迁移产生 `audit_log` 记录。
3. `archived` 是终态，不可恢复（要恢复则复制为新用例）。

### 4.3 评审决策回滚机制

**finalize 之前**：允许自由回滚单条决策。

- **回滚条件**：评审状态为 `in_progress`（未 finalize），且该决策未被其他决策依赖。
- **回滚操作**：将 `review_decision.human_verdict` 置 NULL，`final_verdict` 恢复为 `ai_verdict`，释放评审锁。
- **审计**：回滚操作写入 `audit_log`（action=`review_rollback`）。

**finalize 之后**：允许 1h 内有限回滚（配置 `REVIEW_UNDO_WINDOW_MINUTES` = 60）。

- **回滚条件**：finalize 后 ≤ 1h，且操作者具有 admin/qa_lead 权限。
- **回滚操作**：
  - 单条决策回滚：逆操作（如 deprecated → active）。**`archived` 是终态不可恢复**，若原用例已 archived，回滚时创建新 draft 副本（继承原用例内容），而非恢复 archived 记录。
  - 整体 finalize 回滚：撤销整个评审的 finalize，所有决策恢复为 `in_progress` 状态。已 archived 的用例不恢复，改为创建 draft 副本。
  - 新版本已存在时：回滚需同时标记新版本为 deprecated。
- **超时后不可回滚**：finalize 超过 1h 后，决策不可变（不可变保证）；若需修正，只能创建新评审。
- **审计**：回滚操作写入 `audit_log`（action=`review_undo`）。

---

## 5. 流水线（Pipeline）

### 5.1 Step 列表

```
[S1]  SignalGatherer       — 输入信号收集 + 缺失检测
[S2]  HistoryFingerprint   — 历史指纹提炼/复用（旧项目）
[S3]  ReverseInfer         — 业务摘要反推（场景 3、5、7）
[S4]  HumanConfirmation    — 强制人工确认门槛
[S5]  TestPointAlignment   — 测试点对齐
[S6]  BackwardScan         — 旧用例反向扫描（旧项目）
[S7]  CandidateExtractor   — 新场景候选提取
[S8]  ForwardScan          — 候选场景前向扫描（旧项目）
[S9]  Reconciliation       — 双向合并（合并矩阵）
[S10] ScenarioPreview       — 候选场景人工勾选
[S11] CaseGeneration       — 完整用例生成
[S12] QualityGate          — 质量自检红线
[S13] PersistAndReview     — 落库 + 评审入口
```

**幂等保证**：每 Step 输出落 `artifact` 表，`cache_key = sha256(step_name + step_version + sorted(input_artifact_hashes))`。重复输入直接复用产物，不重跑 AI。

**失败处理**：每 Step 重试 3 次（指数退避 1s/4s/16s）→ 调 `fallback()` → 标 `degraded=true`，后续 Step 看到 degraded 强制人工确认。

### 5.2 Pipeline 重跑策略

当用户对同一迭代重新触发 Pipeline 时，需处理与进行中评审的交互：

| 当前状态 | 重跑行为 | 理由 |
|---|---|---|
| 无历史 Run | 正常执行 | — |
| 有历史 Run（已完成），无进行中评审 | 增量执行：输入 hash 未变的 Step 命中缓存，仅重跑输入变化的 Step | 幂等保证 |
| 有历史 Run（已完成），有进行中评审 | **拒绝重跑**，返回 409 + 提示"请先 finalize 或 cancel 当前评审" | 防止评审结果与新 Run 产物冲突 |
| 有历史 Run（进行中） | **拒绝重跑**，返回 409 + 提示"Pipeline 正在运行" | 防止并发冲突 |
| 有历史 Run（waiting_for_user） | 允许取消后重跑；或直接 resume | 用户可能想改输入重跑 |

**增量重跑判定**：比较 `iteration_input` 的 hash 与上次 Run 的 `input_hash`，仅重跑受影响 Step 及其下游。

### 5.3 Pipeline 版本升级路径

当 `PIPELINE_VERSION` 配置变更时（如 Step 逻辑调整、Schema 变更）：

1. **自动检测**：PipelineRunner 启动时比较当前 `PIPELINE_VERSION` 与历史 Run 的 `pipeline_version`。
2. **版本不匹配**：强制清除该迭代所有缓存 artifact，从头重跑。
3. **迁移脚本**：若 artifact schema 变更，提供 `scripts/migrate_artifacts.py --from-version X --to-version Y`。
4. **灰度**：新版本 Pipeline 可先对单个迭代试跑，确认无误后全局切换。

---

## 6. 双向扫描合并矩阵

| 反向 \ 前向 | EXISTING | MODIFY | (前向未涉及) |
|---|---|---|---|
| **VALID** | ✅ keep | ⚠️ needs_modify | ✅ keep |
| **LOCATOR_ONLY** | ⚠️ locator_broken | ⚠️ locator + modify | ⚠️ locator_broken |
| **NEEDS_MODIFY** | ⚠️ needs_modify | ⚠️ needs_modify (合并 hint，**人工必看**) | ⚠️ needs_modify |
| **DEPRECATED** | 🔴 **冲突！强制人工** | 🔴 **冲突！强制人工** | ✅ deprecated |
| **UNCERTAIN** | ⚠️ pending_review | ⚠️ pending_review | ⚠️ pending_review |

前向新场景但反向未覆盖 → `new`。

---

## 7. 质量评估

### 7.1 先验质量分（生成时）

```
score = 0
score += 25 if has(PRD)              else inferred_capability_confidence * 15
score += 20 if has(testpoints)       else 0
score += 25 if has(UI/prototype)     else 0
score += 15 if has(history)          else 5
score += 15 if user_confirmed_inferred_artifacts
score -= min(15, conflicts * 3)  # 冲突惩罚
```

| 等级 | 分数 | 含义 |
|:-:|:-:|---|
| A | ≥85 | 信号完整 + 用户确认到位 |
| B | 65~84 | 缺一类信号或部分确认 |
| C | 45~64 | 多类信号缺失 |
| D | <45 | **强制不允许自动落库** |

### 7.2 后验质量分（评审/执行后回填）

```
posterior = 0.5*review_pass_rate + 0.3*execution_pass_rate + 0.2*(1-modification_rate)
```

按"信号组合"聚合，反向校准先验公式。

---

## 8. 失败模式（FMEA 摘要）

| ID | 失败模式 | 缓解 |
|:-:|---|---|
| F1 | AI 反推 PRD 严重偏差 | 强制用户填补充表单 + 标 degraded |
| F2 | JSON 校验失败 | 重试 → 切批 → 单条 → 标 UNCERTAIN |
| F3 | DEPRECATED 误判 | 红色冲突强制人工 |
| F4 | 用例血缘断裂 | DB 触发器禁止 update 关键字段 |
| F5 | 用户敷衍点过确认 | 记录 `confirmed_with_zero_edit`，警告 |
| F6 | 测试点候选爆炸 | 模块分页 + AI 自评分 top-K |
| F7 | 跨迭代并发评审 | 乐观锁 |
| F8 | LOCATOR_ONLY 误判 | 提测后回归二次校验 |
| F9 | Pipeline 中断 | artifact 持久化，重启从最近完成处继续 |
| F10 | summary 模型漂移 | summary 带 `model_version`，模型升级触发批量重算 |
| F11 | Pipeline 重跑覆盖进行中评审 | 重跑前检查评审状态，进行中评审拒绝重跑（§5.2） |
| F12 | 权限越权操作 | 所有写操作检查权限，拒绝返回 403 + 审计日志（§3.3） |
| F13 | 配置漂移（环境不一致） | 配置集中管理 + 启动时校验关键配置项（§3.5） |
| F14 | AI 模型版本升级中途换模型 | `model_version` 写入 artifact，版本不匹配时标 `stale` 并触发增量重算 |
| F15 | 审计日志存储溢出 | 日志表按月分区 + 超过 180 天归档到冷存储 |

---

## 9. 已知开放问题

| ID | 问题 | 当前妥协 |
|:-:|---|---|
| O1 | 测试点拆分/合并的迁移 | 引入 `testpoint_migration` 映射表，手工迁移优先 |
| O2 | 跨项目用例复用 | 暂不支持 |
| O3 | summary 模型漂移 | `summary_model_version` 字段 + 触发重算 |
| O4 | 万级用例反向扫描成本 | 增量化 + 模块切片 |
| O5 | AI 反推幻觉检测 | 强制确认 + 后验通过率反向监控 |
| O6 | 多人评审意见不一致 | M1 单评审者；后续支持多人 voting |
| O7 | 断言覆盖度量化 | 启发式（每用例至少 1 断言） |
| O8 | 流程图解析准确率 | 通用 vision，后续可专门模型 |
| O9 | Capability 拆分/合并的自动化 | 场景 8 暂需人工标记拆分/合并关系，Pipeline 仅执行批量重组 |
| O10 | 评审回滚的级联影响 | 回滚一条决策可能影响依赖它的其他决策，暂由人工判断 |

---

## 10. 落地里程碑

| 里程碑 | 主题 | 预计 | 任务数 |
|:-:|---|:-:|:-:|
| M0 | 基线测量（现有用例质量/成本数据采集） | 1 周 | 3 |
| M1 | 基础骨架（数据模型、状态机、Pipeline 抽象、AI Client、权限、配置、审计日志） | 3-4 周 | 18 |
| M2 | 双向扫描 + 评审交互（旧项目场景 4，含确认门槛） | 3-4 周 | 14 |
| M3 | 反推 + 信号补全（场景 3、5） | 2-3 周 | 8 |
| M4 | 质量与运营（评分、血缘、监控、用户手册、运维） | 2-3 周 | 11 |

详见 `iteration-pipeline-tasks.md`。

---

## 11. 设计原则（不可妥协）

1. **不破坏可追溯性**：任何修改都建新版本，不覆盖。
2. **不绕过状态机**：所有 lifecycle_status 变更必须经 `LifecycleService`。
3. **不允许低质量自动落库**：先验质量分 D 必须人工评审通过。
4. **不允许敷衍确认**：用户跳过/未编辑直接通过的人工卡点要打标记。
5. **不假装搞定**：开放问题（§9）必须在文档中显式列出。
6. **不重复跑 AI**：所有 Step 输出可缓存，相同输入零成本重放。
7. **不绕过权限**：所有写操作必须经过权限检查，拒绝返回 403。
8. **不硬编码配置**：所有可调参数走配置管理（§3.5）。
9. **不直接调用模型 API**：所有 AI 调用走抽象层（§3.4）。

---

## 12. API 设计原则

1. **RESTful 风格**：资源名用复数名词，动作用 HTTP 方法。
2. **版本化**：所有端点前缀 `/api/v1/`，破坏性变更升级为 `/api/v2/`。
3. **分页**：列表接口默认 `page=1, page_size=20`，最大 `page_size=100`。
4. **过滤与排序**：支持 `?lifecycle_status=active,needs_modify` 多值过滤，`?sort=-created_at` 降序。
5. **幂等**：创建接口对相同内容返回已有资源（不重复创建）。
6. **错误格式统一**：`{code: "ERROR_CODE", message: "人类可读", detail: {}}` 。
7. **异步操作**：长时间操作返回 `202 Accepted` + `Location` header 指向状态查询端点。
8. **审计**：所有写操作自动产生 `audit_log` 记录。
