# AI 测试用例生成上下文精准化与历史用例保鲜优化方案

## 1. 背景

当前 `ai-testmaster` 的测试用例生成链路会在最长路径中组合需求文档、原型图片描述、UI 原型解析数据、UI 流程、测试点、历史用例以及 prompt 规则。该设计有利于生成专属项目用例，但当上下文过长、来源过多且缺少优先级控制时，会降低 AI 对当前测试点的聚焦度。

典型问题包括：

- 步骤中出现目标页面不存在的按钮、输入框或跳转。
- 旧版本需求或历史用例逻辑混入新用例。
- 格式满足要求，但业务覆盖不足。
- 历史用例被改写复用，缺少针对当前需求和 UI 的设计。
- 需求、UI 解析、UI 流程和历史用例冲突时，AI 自由裁量导致幻觉。
- 历史用例随需求和 UI 持续迭代逐渐腐化，旧用例未同步维护时会反向误导新用例生成。
- 按需加载命中范围不足时，若仍按“完整上下文”处理，会产生低置信但看似完整的测试用例。

本方案目标是将生成链路从“全量资料填充”优化为“按测试点精准取数”，减少人工二次修订，提高生成用例对当前项目、当前需求、当前 UI 流程的贴合度。

## 2. 优化目标

- 上下文按需加载：避免默认加载全部需求、全部 UI 屏幕和全部历史用例。
- 生成质量提升：减少不存在元素、旧逻辑混入、历史用例仿写等问题。
- 人工投入降低：减少测试人员手动删除、重写、补步骤的比例。
- 可审计：生成结果可追溯到实际注入的需求、UI 页面和历史用例摘要。
- 可降级：精准匹配失败时显式告警，不静默回退到全量上下文。
- 可判定：上下文完整性和历史用例可信度可量化，低可信资料不进入 prompt 或仅作为 warning 暴露。
- 可理解：前端页面能让测试人员看懂本次生成用了哪些资料、缺了哪些资料、为什么降级。

## 3. 当前项目基础

当前项目已经具备第一阶段落地基础：

- `TestPoint.requirement_id` 可用于优先定位测试点关联需求。
- `Requirement.description` 可作为精准需求正文来源。
- `UIPrototypeScreen.ui_spec`、`summary`、`navigation_flow`、`related_screens` 可作为 UI 精准上下文来源。
- 历史用例已有 `title`、`summary`、`expected_result`、`steps_json`，可摘要化用于避重。
- 项目已有 `QualityGate` 和 `CaseQualityAnalyzer`，可复用为生成后质量门禁。

需要注意：

- 当前没有独立需求版本表，“最新版本需求”第一阶段以 `Requirement.update_time/status/source_file_id` 作为近似依据。
- `TestCase` 当前没有 `requirement_id/is_archived/refresh_status` 字段，第一阶段通过 `TestCase.test_point_id -> TestPoint.requirement_id` 追溯需求，并使用 `lifecycle_status != 'archived'` 与 `is_deleted=False` 表示可用历史用例。
- `TestCase.lifecycle_status` 有受控变更机制，废弃或归档不得直接改字段，后续保鲜归档必须走生命周期服务。
- 项目已有 `HistoryFingerprint`，但当前能力是 summary 过期重算，不等同于根据最新需求刷新历史用例内容。
- 不强制新增必填参数，避免破坏现有页面、批量生成、流式生成等链路。
- 审计信息不交给 AI 生成，避免模型编造来源；由服务层根据实际注入内容后置生成。

## 4. 总体架构

```text
测试点 + 项目ID
  -> 上下文规划
  -> 需求/UI/历史用例按需检索
  -> 上下文完整性评分与历史可信度过滤
  -> 按优先级和预算组装 prompt
  -> AI 生成测试用例
  -> 服务层附加 evidence_refs
  -> 质量门禁与可执行性检查
```

上下文优先级如下：

1. 当前测试点描述。
2. 关联需求 `Requirement.description`。
3. 当前目标 UI 页面 `UIPrototypeScreen.ui_spec`。
4. 当前 UI 流程与相邻页面摘要。
5. 历史相似用例摘要。
6. 项目背景和固定生成规则。

冲突仲裁规则：

- 测试点和需求冲突时，以测试点明确描述为准。
- 需求和 UI 冲突时，以需求为准，并在相关步骤标记 `待确认UI`。
- UI 元素存在性以 `ui_spec` 为准，跳转关系以 `navigation_flow` 为准。
- `ui_spec` 缺失或解析失败时，UI 数据标记为低置信度，涉及交互的步骤必须标记 `待确认UI`。
- 历史用例只用于避重和识别覆盖缺口，不得照搬或改写历史步骤。
- 历史用例必须先通过可信度判断，低可信或疑似过时用例不得作为业务事实来源。
- 缺失信息不得臆造页面、按钮、字段或业务规则。
- 权重规则只作为可信上下文内的二级提示策略，不能替代上述来源优先级。

## 5. 核心改造

### 5.1 上下文按需加载

优化 `context_loader.py` 和 `TestCaseGenerationService.get_context_for_generation`：

- 指定 `test_point_ids` 时，优先读取对应 `TestPoint`。
- 若 `TestPoint.requirement_id` 存在，仅加载该需求描述和必要来源信息。
- 若无关联需求，则根据 `module/point/ai_prompt` 对需求库做关键词 Top-N 兜底。
- 若显式传入 `ui_screen_ids`，以显式选择为准。
- 若未传入 `ui_screen_ids`，根据测试点文本匹配 UI 页面，最多返回 Top 3 个目标页。
- 匹配失败时返回空 UI 上下文和 warning，不回退到全量 UI。
- 如果测试点包含“进入、跳转、提交、返回、下一步”等流程词，可额外带入目标页的相邻跳转页面摘要。
- 当 `Requirement.description` 超过 800 字时，先按测试点关键词做需求段落裁剪，优先保留命中的连续段落和前后上下文；检索不到命中段落时再使用裁剪后的全文前段。
- 需求文本被裁剪时，必须在 `warnings` 中记录 `REQUIREMENT_TRIMMED_BY_KEYWORDS`，便于测试人员判断是否需要补充资料。

UI 匹配策略：

- 从测试点 `module/point/ai_prompt` 提取关键词。
- 匹配 `screen_name`、`summary`、`ui_spec` 文本。
- 精确命中页面名优先，其次按关键词命中数排序。
- 多页面流程场景可补充 `navigation_flow` 指向页面。
- 结果去重后限制数量，避免“错误的精准”扩大影响。

### 5.1.1 无 UI 原型图项目处理

没有 UI 原型图是合法场景，不应阻断生成，但必须切换生成策略，避免 AI 编造页面元素。

处理规则：

- 若项目本身是 API、后端、数据处理、批任务等非 UI 项目，`ui_spec` 缺失不视为核心上下文缺失，完整性评分不扣 UI 分。
- 若项目是 Web/App 但未上传 UI 原型图，可生成手工用例、需求验证用例或 API 用例，但不得生成确定性的 UI 自动化步骤。
- 若用户指定 `case_type=ui_automation`，但没有任何 UI 上下文，应降级为低置信草稿，步骤中涉及页面元素的位置必须标记 `待确认UI`。
- 历史用例不能替代 UI 原型图。历史步骤中出现的按钮、页面、输入框只能作为参考，不得作为当前 UI 元素存在的证据。
- 质量门禁在无 UI 时跳过 UI 元素命中率检查，但增加“禁止编造具体元素”校验。

Prompt 约束：

```text
当前项目未提供 UI 原型图或 UI 解析数据。
不得编造按钮、输入框、页面区域、弹窗或跳转入口。
如测试点必须涉及 UI 操作，请使用【待确认UI】标记。
优先生成基于需求、业务规则、接口或人工验证视角的测试用例。
```

建议 warning code：

- `UI_CONTEXT_ABSENT`
- `UI_AUTOMATION_DEGRADED`

### 5.2 历史用例摘要化

优化 `test_case_ai_generate/_context.py`：

- `history_case_ids is None` 时不再查询全部未归档用例。
- 默认按当前测试点文本相似度返回 Top 3-10 条，但只注入高可信历史用例摘要。
- 查询基础条件使用当前项目字段：`is_deleted=False` 且 `lifecycle_status != 'archived'`，不使用当前模型不存在的 `is_archived` 字段。
- 如果测试点文本为空，返回空历史列表并给出 warning。
- 每条历史用例仅返回摘要字段：
  - `id`
  - `case_no`
  - `module`
  - `title`
  - `summary`
  - `covered_scene`
  - `design_tag`
  - `similarity`
  - `trust_level`
  - `staleness_reason`

`design_tag` 由规则提取：

- 标题或步骤包含“空、为空、必填、超长、最大、最小、边界”等，标记为 `边界值`。
- 包含“失败、错误、异常、无权限、断网、超时”等，标记为 `异常流程`。
- 步骤数较多或包含多个页面动作，标记为 `组合场景`。
- 默认标记为 `常规流程`。

Prompt 中明确约束：

> 历史用例仅用于避免设计重复，你必须基于当前需求和 UI 设计全新用例，不得改写、合并或照搬历史用例步骤。

同时增加约束：

> 历史用例的覆盖场景仅说明已有用例，不代表当前测试点必须包含同类场景。请严格围绕当前测试点设计用例，不要为了避重而额外扩展测试范围。

历史摘要建议附带相似度：

```text
【异常流程】登录-连续失败锁定（相似度: 0.78，仅供避重参考，非必须覆盖）
```

### 5.2.1 历史用例可信度治理

历史用例腐化是长期风险：需求、UI 和业务流程持续变化后，历史用例可能仍保持 `active`，但内容已经不再适配当前需求。第一阶段不直接让 AI 覆盖正式用例，而是先做可信度识别、过滤和告警。

> **已实现**：`_assess_history_trust()` 函数（`app/api/v1/endpoints/test_case_ai_generate/_context.py`），在历史用例注入 prompt 前自动评估可信度。`trust_level` 和 `staleness_reason` 字段已加入 `_summarize_history_case()` 返回值和 `evidence_refs.history_cases`。

可信度判断优先使用现有字段和链路：

- 需求追溯：`TestCase.test_point_id -> TestPoint.requirement_id -> Requirement`。
- 新鲜度：比较历史用例 `update_time` 与关联需求 `update_time`。
- 生命周期：`lifecycle_status in ('deprecated', 'archived')` 的用例不进入历史参考。
- 摘要状态：`summary` 缺失或 `summary_model_version` 过旧时，先走摘要重算或降权。
- UI 一致性：历史用例关联 UI 不在当前目标 UI 上下文时降权。

过滤规则：

- 与当前测试点关联需求不一致的历史用例，标记 `HISTORY_REQUIREMENT_MISMATCH`，默认不注入 prompt。
- 历史用例更新时间早于当前需求更新时间，标记 `HISTORY_POTENTIALLY_STALE`，只作为 warning 或低可信参考。
- 疑似 stale 或低可信历史用例不得作为业务规则来源，不得提升 prompt 权重。
- 高可信历史用例也只用于避重和覆盖缺口识别，不传完整步骤。

`evidence_refs.history_cases` 建议结构：

```json
{
  "id": 31,
  "case_no": "TC-LOGIN-003",
  "design_tag": "异常流程",
  "similarity": 0.78,
  "trust_level": "high|medium|low",
  "staleness_reason": ""
}
```

新增 warning code：

- `HISTORY_POTENTIALLY_STALE`
- `HISTORY_LOW_TRUST_FILTERED`
- `HISTORY_REQUIREMENT_MISMATCH`

### 5.2.2 历史用例保鲜实施方式

历史用例保鲜分阶段落地，避免 AI 直接污染正式测试资产。

第一阶段：

- 只生成“保鲜建议”，不直接覆盖正式用例。
- 保鲜建议包含建议状态、建议标题、建议步骤、建议预期结果、差异说明、废弃原因。
- 低可信历史用例从生成上下文中剔除，并通过 warning 暴露给前端或审计日志。

第二阶段：

- 新增保鲜任务表或任务记录，保存 AI 刷新结果、diff、状态、失败原因和操作人。
- 更新正式用例前必须保留快照，可通过 `TestCaseVersion` 或等价审计表支持回滚。
- 废弃或归档必须走生命周期服务，不能直接修改 `lifecycle_status`。
- 默认需要人工确认；自动应用仅作为项目级配置开启。

建议保鲜 Prompt 只作为维护建议生成，不直接写库：

```text
[角色] 你是测试用例维护专家。请依据最新需求评估以下历史用例。

[最新需求]
{{ requirement.description }}

[历史用例摘要与步骤]
{{ case.title }}
{{ case.steps_json }}
{{ case.expected_result }}

[任务]
1. 判断该用例在当前需求下是否仍然有效。
2. 若有效，输出建议更新内容和差异说明。
3. 若无效，输出建议废弃原因。
4. 不要引入需求中未提及的规则或 UI 元素。
```

### 5.3 Prompt 模板重构

将 prompt 调整为模块化结构：

```text
[角色]
你是一名测试用例设计专家。

[优先级与冲突规则]
测试点 > 关联需求 > 当前 UI 元素 > UI 流程 > 历史用例。
UI 元素存在性仅依据 ui_spec；若 ui_spec 缺失，交互步骤必须标记【待确认UI】。

[核心上下文]
测试点：
关联需求：
目标 UI：
当前流程：

[辅助上下文]
相邻页面：
项目类型：
默认测试账号：

[历史参考]
相似用例摘要：

[任务]
为当前测试点生成测试用例。

[格式要求]
步骤原子化，预期结果可断言，禁止使用核心上下文不存在的 UI 元素。
历史用例仅用于避重，不得复写。
```

审计信息不要求 AI 输出，由服务层基于实际注入资料生成 `evidence_refs`。

### 5.3.1 权重规则兼容策略

当前项目仍存在按权重规则生成 prompt 的链路。按需加载与权重规则不冲突，但职责必须拆开：

- 按需加载决定"给 AI 什么资料"。
- 上下文完整性评分决定"这些资料是否足够可信"。
- 权重规则只决定"在可信资料内部如何表达侧重点"。

调整原则：

- 权重规则降级为二级策略，不能覆盖"测试点 > 关联需求 > 当前 UI > UI 流程 > 历史用例"的来源优先级。
- 当需求缺失时，不允许 UI 或历史用例升级为业务事实来源。
- 当 UI 缺失时，不允许生成确定性 UI 交互步骤，只能生成 `待确认UI` 或草稿。
- 历史用例权重固定最低，仅用于避重和覆盖缺口识别。
- 旧增强链路可继续保留 `build_weight_model`，但精准上下文链路应优先使用简化优先级与硬约束。

> **已实现**：`_enhanced.py` 旧链路已统一降级改造，移除 `build_weight_model` 百分比权重调用，改用 `_build_priority_rules()` 函数生成来源优先级 + 硬约束策略，与 `linear_prompt` 和 `graph_prompt` 保持一致。`build_weight_model` 函数仍保留但不再被生产代码调用。

推荐将复杂百分比权重压缩为：

```text
[信息优先级]
1. 当前测试点限定生成范围。
2. 关联需求是最高业务依据。
3. 当前 UI 元素用于保证步骤可执行。
4. 历史用例仅用于避重，不得作为业务规则来源。

[硬约束]
- 禁止使用需求中未提及的规则或 UI 中不存在的元素。
- 缺失信息必须标记【待补充】或【待确认UI】。
```

### 5.3.2 上下文完整性评分

按需加载会降低噪声，但也可能带来"命中不足"的风险。因此需要在组装 prompt 前计算 `context_completeness_score`。

> **已实现**：`TestCaseGenerationBaseMixin._compute_completeness_score()` 方法（`app/services/test_case_generation/base_mixin.py`），在 `_get_context_for_generation_precision` 末尾自动计算并写入 `context_stats`。

建议计分：


| 维度     | 权重  | 判定                                                                |
| ------ | --- | ----------------------------------------------------------------- |
| 当前测试点  | 20  | 存在明确 `test_point`、`module`、`priority`                             |
| 关联需求   | 35  | 命中 `TestPoint.requirement_id -> Requirement.description` 或高置信需求片段 |
| 目标 UI  | 25  | 命中显式 UI 或关键词 Top-N 页面且存在 `ui_spec`                                |
| 流程上下文  | 10  | 多页面测试点命中 `navigation_flow` 或相邻页面摘要                                |
| 可信历史参考 | 10  | 存在高可信历史摘要，仅作避重                                                    |


无 UI 原型图时需要动态调整计分：

- 非 UI 项目：将 `目标 UI` 的 25 分按比例分配给需求和测试点，不因缺 UI 降低总分。
- Web/App 项目但未上传 UI：保留 UI 缺失扣分，生成策略降级为手工/API/草稿。
- 用户明确要求 `ui_automation` 且无 UI：无论总分如何，必须返回 `UI_AUTOMATION_DEGRADED` warning。

生成策略：

- `score >= 80`：正常生成。
- `50 <= score < 80`：低置信生成，返回 warning，步骤中允许 `待确认UI` / `待补充`。
- `score < 50`：不建议自动生成正式用例，只生成草稿或强制人工复核。

`context_stats` 建议增加：

```json
{
  "completeness_score": 75,
  "missing_core_context": ["requirement", "ui"],
  "low_confidence_reasons": ["UI_NO_MATCH", "HISTORY_LOW_TRUST_FILTERED"]
}
```

### 5.4 Token 预算控制

新增 `ContextBudgetController`：

- 默认总预算控制在 4000-5000 tokens。
- 核心层优先保留。
- 辅助层可摘要化。
- 历史参考层优先裁剪。
- 规则模板压缩为短规则，减少长示例占比。
- 设定核心上下文最小保留长度，例如需求原文至少保留 500 字符，避免复杂测试点被过度裁剪。
- 当核心需求超预算时，优先按段落拆分和关键词裁剪，其次才考虑摘要化；避免摘要丢失“3次”“30分钟”等精确约束。

建议预算：

- 核心上下文：50%。
- UI 与流程：25%。
- 历史参考：10%。
- 项目背景：5%。
- 格式与质量规则：10%。

若核心需求本身超预算，先对需求正文做段落裁剪，再考虑摘要化，最后进入生成。

### 5.5 可执行性质量门禁

在现有 `QualityGate` / `CaseQualityAnalyzer` 基础上补充 UI 可执行性检查：

- 将目标页 `ui_spec` 解析为元素集合，包括按钮文本、输入框标签、字段名、可交互控件名。
- 检查步骤中的“点击【XXX】”“在【YYY】输入”等目标元素是否命中集合。
- 命中率低于 80% 时标记为低置信度。
- 输出未命中的元素名称，方便测试人员定位。
- 从测试点中提取可能需要的关键交互元素，例如“忘记密码”“提交”“下一步”“验证码”；若目标页 `ui_spec` 未包含对应入口，返回 `UI_REQUIRED_ELEMENT_MISSING` warning。
- Prompt 中补充说明：“目标 UI 中未发现相关入口，若需要设计相关步骤，请标记为【待确认UI】。”

其他校验：

- 是否覆盖当前测试点。
- 是否引用历史用例中的旧页面或旧流程。
- 是否包含“正常显示”“功能正常”等不可断言描述。
- 是否超过 8 步并混合多个测试场景。
- 是否缺少异常、边界或正向覆盖。

## 6. evidence_refs 设计

`evidence_refs` 由服务层生成，不进入模型推理，也不依赖 AI 返回。

建议结构：

```json
{
  "requirements": [
    {"id": 12, "req_no": "REQ-001", "title": "登录锁定规则"}
  ],
  "ui_screens": [
    {"id": 8, "screen_name": "登录页", "confidence": "high"}
  ],
  "history_cases": [
    {
      "id": 31,
      "case_no": "TC-LOGIN-003",
      "design_tag": "异常流程",
      "similarity": 0.78,
      "trust_level": "high",
      "staleness_reason": ""
    }
  ],
  "warnings": [
    {
      "code": "UI_PARTIAL_MATCH",
      "message": "UI 匹配仅找到 1 个页面，可能缺少前置页",
      "detail": {"matched_screen_ids": [8], "test_point_id": 12}
    }
  ]
}
```

返回位置：

- `generate-context` 返回 `evidence_refs`、`context_stats` 和结构化 `warnings`。
- `generate-single` 可在响应中带出 `evidence_refs`。
- 保存用例时可作为扩展元数据或审计日志记录，避免污染用例主体字段。
- `context_stats` 同步返回 `completeness_score`，用于前端判断本次生成是否需要人工复核。

## 7. 分阶段实施

### 第一阶段：止血优化

- [x] 历史用例默认返回 Top-N 摘要，不再全量返回。
- [x] 历史用例先做可信度判断，疑似 stale、需求不匹配、低可信用例只返回 warning，不进入 prompt。
- [x] 需求优先走 `TestPoint.requirement_id -> Requirement.description`。
- [x] UI 优先使用显式 `ui_screen_ids`，否则按测试点关键词匹配 Top-N。
- [x] UI 匹配失败只告警，不静默回退全量 UI。
- [x] Prompt 增加上下文优先级、冲突规则、禁止臆造规则。
- [x] 返回 `context_stats`、`warnings`、`evidence_refs`，其中 `context_stats` 增加 `completeness_score`。
- [x] 仅生成历史用例保鲜建议，不自动覆盖正式用例。

### 第二阶段：精准检索

- [x] 增加需求分段和关键词检索能力。
- [x] 增加 UI 页面按 `screen_name/summary/ui_spec` 的检索能力。
- [x] 增加历史用例相似度排序。
- [x] 实现 `ContextBudgetController`。
- [x] 建立保鲜任务记录，保存 AI 建议结果、diff、失败原因和人工确认状态。（`CaseRefreshSuggestion` 模型 + `CaseRefreshService`）
- [x] 增加用例版本快照或等价审计表，支持保鲜前后对比和回滚。（`TestCaseVersion` + 保鲜服务自动快照）
- [x] 建立旧方案和新方案 A/B 测试指标。（`ABTestMetric` 模型 + `ABTestService` + API 端点 + 生成链路自动埋点）

### 第三阶段：智能编排

- [ ] 引入上下文规划器，根据测试点生成信息需求清单。
- [ ] 支持缺失信息补充查询。
- [ ] 将人工修改结果反向沉淀为检索权重和质量规则。
- [ ] 支持按项目配置不同上下文策略。
- [ ] 支持项目级保鲜策略配置，例如是否自动应用、是否强制人工确认、是否允许批量保鲜。

## 8. A/B 测试与验收

选取 30 个典型测试点，覆盖：

- 单页面场景。
- 多页面跳转场景。
- 有历史用例场景。
- 无历史用例场景。
- UI 解析缺失或低置信度场景。
- 历史用例疑似过期场景。
- 需求缺失但 UI/历史用例存在的低完整性场景。

对比旧方案和新方案：


| 指标                | 旧方案基线  | 新方案目标               | 测量方式         |
| ----------------- | ------ | ------------------- | ------------ |
| 步骤可执行率            | 约 70%  | 第一阶段 > 85%，最终 > 95% | 人工或自动逐步执行    |
| 需求对齐率             | 约 80%  | > 90%               | 对照关联需求检查     |
| 无关元素引入率           | 约 15%  | < 3%                | 审查步骤元素       |
| 上下文 token 数       | 15000+ | 4000-5000           | 统计 prompt 长度 |
| 人工二次修改率           | 约 30%  | < 10%-15%           | 统计修改比例       |
| evidence_refs 准确率 | 无      | > 95%               | 核对引用来源       |
| 历史低可信过滤准确率        | 无      | > 90%               | 抽检 stale/不匹配历史用例 |
| 上下文完整性评分有效性       | 无      | 分层结果与人工判断一致       | 对比高/中/低置信样本 |


验收要求：

- 历史用例默认注入数量不超过 10 条。
- 单条用例步骤中不存在目标 UI 之外的页面元素。
- 每次生成结果可追溯到具体 `requirement_id`、`ui_screen_id`、`history_case_id`。
- warnings 能明确说明降级原因。
- `context_stats.completeness_score` 能反映需求、UI、流程、历史参考的缺失情况。
- 默认历史用例注入不包含 `deprecated/archived` 或低可信用例。
- 指标拆分为 `UI 可执行率` 和 `真实可执行率`：前者验证步骤元素是否存在于已提供 UI 数据，目标 > 95%；后者验证在真实界面手工执行的通过率，单独受 UI 数据时效性影响。

## 9. 风险与缓解


| 风险                           | 缓解措施                                                     |
| ---------------------------- | -------------------------------------------------------- |
| `requirement_id` 为空，无法精准加载需求 | 根据测试点 `module/point` 关键词检索需求库，并添加 warning；仍无匹配时只注入项目通用摘要 |
| UI 匹配错误，形成“错误的精准”            | 采用多级匹配和置信度；低置信度时标记 warning，不回退全量 UI                      |
| UI 解析数据陈旧或缺失                 | 标记 `待确认UI`，质量门禁降低置信度                                     |
| 历史摘要过像，AI 仍模仿                | prompt 强调仅用于避重，并在质量门禁中做文本相似度检查                           |
| 历史用例腐化，旧逻辑误导新用例             | 生成前做历史可信度判断；低可信或疑似 stale 用例只进入 warning，不进入 prompt          |
| AI 保鲜误改正式用例                   | 第一阶段只生成保鲜建议；正式更新前必须有人审、快照和回滚能力                           |
| 按需加载导致上下文不完整                 | 使用 `completeness_score` 分层；低分生成草稿或强制人工复核                     |
| 权重规则放大缺失上下文影响                | 权重规则降级为二级策略，必须服从上下文完整性和来源优先级                              |
| Token 预算导致关键上下文丢失            | 核心层优先保留；核心层超限时先做需求段落裁剪                                   |
| 审计来源被 AI 编造                  | `evidence_refs` 由服务层后置注入，不由 AI 生成                        |


## 10. 工程防御性设计

### 10.1 结构化 warnings

`warnings` 使用结构化数组，避免只有自然语言字符串。推荐 warning code：

- `REQUIREMENT_NOT_FOUND`
- `REQUIREMENT_TRIMMED_BY_KEYWORDS`
- `UI_NO_MATCH`
- `UI_PARTIAL_MATCH`
- `UI_CONTEXT_ABSENT`
- `UI_AUTOMATION_DEGRADED`
- `UI_SPEC_MISSING`
- `UI_REQUIRED_ELEMENT_MISSING`
- `HISTORY_NO_QUERY_TEXT`
- `HISTORY_POTENTIALLY_STALE`
- `HISTORY_LOW_TRUST_FILTERED`
- `HISTORY_REQUIREMENT_MISMATCH`
- `CONTEXT_COMPLETENESS_LOW`
- `CONTEXT_BUDGET_TRIMMED`

### 10.2 evidence_refs 序列化

`evidence_refs` 必须在服务层预组装为普通字典列表，不返回 ORM 对象，避免懒加载、N+1 查询或无法 JSON 序列化。

### 10.3 流式生成兼容

若接口使用 SSE 流式输出：

- 可在首帧推送 `context_stats` 和 `warnings`。
- 可在尾帧推送最终 `evidence_refs`。
- 不将审计信息混入 AI 正文流，避免破坏前端解析。

> **已实现**：SSE 单条和批量流式端点首帧已推送 `context_stats` 和 `warnings`，批量端点 warnings 改为结构化推送（含 `warning_detail` 字段）。

### 10.4 批量生成缓存

批量生成多个测试点时，相同需求、相同 UI 页面可在一次请求生命周期内做简单缓存，减少重复查询。缓存仅限当前请求，不做长期缓存，避免需求或 UI 数据时效性问题。

### 10.5 离线验证与灰度发布

第一阶段上线前，选取 30 个测试点离线验证：

- UI 匹配是否命中正确页面。
- 需求裁剪是否保留关键业务约束。
- 历史摘要是否只用于避重，没有引导 AI 扩展范围。
- 历史用例可信度判断是否能识别 stale、需求不匹配和低可信样本。
- 上下文完整性评分是否能区分完整、缺需求、缺 UI、缺流程等不同场景。
- UI 元素命中检查是否存在高误报。

上线时先对 1-2 个项目开启精准模式，收集 `context_stats`、`evidence_refs` 和 warning 分布，调优后再全量放开。

### 10.6 人工修改闭环

记录测试人员人工删除、添加、修改的步骤，作为第三阶段检索权重和规则优化的输入。该埋点不影响第一阶段生成链路，但应提前预留数据结构或审计日志位置。

> **已实现**：`TestCaseVersion.change_type` 新增 `human_edit` 类型，版本恢复时自动记录 `changed_fields`（含每个字段的旧值和新值）。保鲜建议应用时创建 `change_type="refresh_apply"` 快照。

### 10.7 保鲜建议队列

历史用例保鲜建议需要独立于正式用例保存，避免 AI 直接覆盖测试资产。建议记录：

- 关联 `case_id`、`requirement_id`、触发原因和触发时间。
- AI 建议状态：`active` / `deprecated` / `needs_review`。
- 建议标题、步骤、预期结果和差异说明。
- 人工确认状态、确认人、确认时间和驳回原因。
- 失败原因、重试次数和模型版本。

正式用例更新前必须有快照；废弃或归档必须走生命周期服务。

> **已实现**：`CaseRefreshSuggestion` 模型（`app/models/case_refresh_suggestion.py`）+ `CaseRefreshService`（`app/services/case_refresh_service.py`）+ API 端点（`app/api/v1/endpoints/case_refresh.py`）。
>
> - `suggestion_status`: pending/accepted/rejected/applied/expired
> - `review_status`: pending/approved/rejected
> - 审核通过后自动应用建议，应用前自动创建 `TestCaseVersion` 快照
> - 废弃用例走 `lifecycle_transition` 生命周期服务
> - `scan_stale_cases` 接口扫描需求变更后未更新的用例

### 10.8 前端用户体验设计

上下文精准化不能只在后端静默发生，前端需要让测试人员清楚知道“本次生成是否可信、缺什么、引用了什么、下一步怎么处理”。

#### 10.8.1 生成前上下文健康检查

在点击生成前展示上下文健康状态：

- `完整`：需求、测试点、目标 UI 或适用上下文均已命中，可正常生成。
- `部分缺失`：缺少 UI、流程或可信历史参考，可继续生成但会带 warning。
- `低置信`：缺少核心需求或用户要求 UI 自动化但无 UI 上下文，默认生成草稿或要求人工确认。

展示字段：

- 当前测试点数量。
- 命中的需求标题和 `requirement_id`。
- 命中的 UI 页面和 `ui_screen_id`。
- 历史参考数量及可信度分布。
- `completeness_score` 和主要缺失原因。

#### 10.8.2 warnings 可读化

后端返回结构化 warning，前端不应直接展示原始 JSON。建议按严重程度分组：

- 阻断类：缺少核心需求、UI 自动化但无 UI 上下文。
- 风险类：历史用例疑似过期、UI 页面低置信匹配、需求文本被裁剪。
- 提示类：无历史参考、无流程信息、仅生成手工用例。

每条 warning 展示：

- 用户可读标题。
- 简短影响说明。
- 建议操作，例如“补充 UI 原型图”“绑定需求”“查看被过滤历史用例”“以草稿生成”。

#### 10.8.3 无 UI 原型图体验

项目未上传 UI 原型图时，页面需要明确提示：

- 非 UI 项目：展示“当前项目无需 UI 原型图，可按需求/API 视角生成”。
- Web/App 项目：展示“未检测到 UI 原型图，UI 自动化步骤将标记为待确认”。
- 当用户选择 `ui_automation` 时，弹出确认提示：继续后会生成低置信草稿，不会生成可直接执行的定位步骤。

前端应提供快捷入口：

- 上传 UI 原型图。
- 切换为手工用例。
- 切换为 API/需求验证用例。
- 继续生成草稿。

#### 10.8.4 evidence_refs 审计展示

生成结果页增加“生成依据”区域：

- 需求依据：展示需求标题、编号、状态，可点击查看原文。
- UI 依据：展示页面名称、匹配置信度、元素数量。
- 历史参考：展示标题、相似度、可信度、是否被过滤。
- 警告记录：展示本次生成过程中触发的 warning。

审计信息应来自服务层 `evidence_refs`，不从 AI 输出正文解析。

#### 10.8.5 历史用例保鲜体验

历史用例列表或生成弹窗中增加保鲜状态：

- `高可信`：可作为避重参考。
- `疑似过期`：不进入 prompt，可查看原因。
- `待保鲜`：存在 AI 建议版本，等待人工确认。
- `已废弃`：不参与生成。

保鲜建议页面提供：

- 原用例与建议用例 diff。
- AI 废弃原因或更新说明。
- 确认应用、驳回、重新生成建议。
- 回滚入口。

#### 10.8.6 批量生成与流式体验

批量生成时，前端应在任务开始前展示聚合风险：

- 多少测试点缺需求。
- 多少测试点缺 UI。
- 多少测试点历史参考被过滤。
- 预计会生成多少低置信草稿。

流式生成时：

- 首帧推送上下文健康状态和 warnings。
- 中间帧持续展示生成进度。
- 尾帧展示 `evidence_refs`、质量门禁结果和可执行性检查结果。

这样测试人员不需要等生成结束才发现上下文不足。

## 11. 结论

本方案适用于当前项目现状，第一阶段无需引入向量数据库或完整 Agent 框架，即可明显降低全量上下文带来的质量波动。

优先落地点是：

- 上下文按测试点按需加载。
- UI 匹配失败显式告警。
- 历史用例 Top-N 摘要化、打设计标签并做可信度过滤。
- 通过上下文完整性评分决定正常生成、低置信生成或人工复核。
- 将权重规则降级为可信上下文内的二级策略。
- 服务层生成 `evidence_refs`。
- 增加 UI 元素可执行性检查。

该方案的核心不是简单压缩上下文，而是让 AI 只看到与当前测试点最相关、优先级明确、来源可追溯的项目信息，从而减少人工投入并提高专属项目测试用例质量。
