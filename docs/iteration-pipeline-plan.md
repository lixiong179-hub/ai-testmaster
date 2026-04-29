# 迭代用例生成与维护流水线 — 规划文档

> 解决跨迭代的用例生成、去重、维护问题。配套任务追踪：`iteration-pipeline-tasks.md`。

---

## 文档信息

| 项 | 内容 |
|----|------|
| 项目名称 | 迭代用例生成与维护流水线 |
| 文档版本 | v1.0 |
| 编制日期 | 2026-04-29 |
| 关联文档 | `iteration-pipeline-tasks.md` |

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

## 2. 核心场景（5 类）

| 场景 | 业务信号 | 结构信号 | 视觉信号 | 历史信号 | 关键矛盾 |
|:-:|:-:|:-:|:-:|:-:|---|
| 1 | ✅PRD | ✅测试点 | ✅UI | ❌ | 测试点-UI 对齐 |
| 2 | ✅PRD | ✅测试点 | ❌ | ❌ | 操作步骤具象化 |
| 3 | ❌ | ❌ | ✅UI | ❌ | 缺业务上下文，AI 在猜 |
| 4 | ✅PRD | ✅旧测试点 | ✅UI | ✅旧用例 | 去重 + 旧用例维护 |
| 5 | ⚠️弱 | ✅旧测试点 | ✅原型 | ✅旧用例 | PRD 反推 + 维护 |

**5 个场景共用一条流水线**，区别只是哪些 Step 开启 / 跳过。

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
| `Iteration` | 关联 0..N 个 PRD/Prototype 输入 |
| `IterationReview` | 不可变（决策一旦记录不能改） |
| `PipelineRun` | 幂等 key = (iteration_id, input_hash) |
| `Artifact` | 含 `confidence`、`provenance`、`schema_version` |

---

## 4. 用例生命周期状态机

```
   ┌──────┐    ┌───────────┐    ┌─────────────┐
   │draft │──>│   active   │<──│ needs_modify│
   └──────┘    └─────┬─────┘    └──────┬──────┘
                     │                 │
                     │                 v
                     │           ┌──────────┐
                     │           │ modified │ (创建新版本，
                     │           │ (终态)    │  新版本进 active)
                     │           └──────────┘
                     v
              ┌──────────────┐
              │locator_broken│──> 重录后回 active
              └──────────────┘
                     │
                     v
              ┌──────────────┐    ┌──────────┐
              │ deprecated   │──> │ archived │ (终态)
              └──────────────┘    └──────────┘
```

**迁移规则**：
1. 只能由 `LifecycleService` 驱动迁移，禁止直接 SQL update。
2. `active → needs_modify` 必须附带 `last_review_id`。
3. `needs_modify → modified`：必须创建新 case 版本（`parent_case_id` 指向原 case）。
4. `deprecated → archived` 至少冷却 24h（防误删）。
5. `archived` 是终态，不可恢复（要恢复则复制为新用例）。

---

## 5. 流水线（Pipeline）

```
[S1] SignalGatherer       — 输入信号收集 + 缺失检测
[S2] HistoryFingerprint   — 历史指纹提炼/复用（旧项目）
[S3] ReverseInfer         — 业务摘要反推（场景 3、5）
[S4] HumanConfirmation    — 强制人工确认门槛
[S5] TestPointAlignment   — 测试点对齐
[S6] BackwardScan         — 旧用例反向扫描（旧项目）
[S7] CandidateExtractor   — 新场景候选提取
[S8] ForwardScan          — 候选场景前向扫描（旧项目）
[S9] Reconciliation       — 双向合并（合并矩阵）
[S10] ScenarioPreview     — 候选场景人工勾选
[S11] CaseGeneration      — 完整用例生成
[S12] QualityGate         — 质量自检红线
[S13] PersistAndReview    — 落库 + 评审入口
```

**幂等保证**：每 Step 输出落 `artifact` 表，`cache_key = sha256(step_name + step_version + sorted(input_artifact_hashes))`。重复输入直接复用产物，不重跑 AI。

**失败处理**：每 Step 重试 3 次（指数退避 1s/4s/16s）→ 调 `fallback()` → 标 `degraded=true`，后续 Step 看到 degraded 强制人工确认。

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

---

## 10. 落地里程碑

| 里程碑 | 主题 | 预计 | 任务数 |
|:-:|---|:-:|:-:|
| M1 | 基础骨架（数据模型、状态机、Pipeline 抽象） | 2-3 周 | 13 |
| M2 | 双向扫描（旧项目场景 4） | 3-4 周 | 12 |
| M3 | 反推 + 信号补全（场景 3、5） | 2-3 周 | 8 |
| M4 | 质量与运营（评分、血缘、监控） | 2 周 | 7 |

详见 `iteration-pipeline-tasks.md`。

---

## 11. 设计原则（不可妥协）

1. **不破坏可追溯性**：任何修改都建新版本，不覆盖。
2. **不绕过状态机**：所有 lifecycle_status 变更必须经 `LifecycleService`。
3. **不允许低质量自动落库**：先验质量分 D 必须人工评审通过。
4. **不允许敷衍确认**：用户跳过/未编辑直接通过的人工卡点要打标记。
5. **不假装搞定**：开放问题（§9）必须在文档中显式列出。
6. **不重复跑 AI**：所有 Step 输出可缓存，相同输入零成本重放。
