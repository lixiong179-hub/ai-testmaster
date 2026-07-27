# AI辅助跨设备用例迁移规划

> **文档版本**：v2.1
> **最后更新**：2026-05-22
> **变更历史**：见文末附录B

---

## 一、场景定义

### 1.1 核心场景
一个功能从**平板App**迁移到**手机App**，业务逻辑基本不变，但交互形态因设备差异需要调整测试用例。

**重要前提**：平板端测试用例目前以**Excel文档**形式存在，尚未录入系统。因此迁移流程需要包含"Excel导入"前置步骤。

### 1.2 典型差异矩阵

| 差异维度 | 平板端 | 手机端 | 对用例的影响 |
|---------|--------|--------|-------------|
| 屏幕尺寸 | 10"+ 横屏/竖屏 | 5-6" 竖屏为主 | 同一页面可能拆分为多页 |
| 布局模式 | 多栏并排、侧边栏 | 单栏、底部Tab、抽屉菜单 | 导航步骤数量和路径变化 |
| 交互方式 | 大触控区、可能支持键盘/笔 | 小触控区、手势操作 | 操作描述和action_type变化 |
| 弹窗/对话框 | 居中大弹窗 | 底部Sheet/全屏页 | 元素定位策略变化 |
| 列表展示 | 表格/多列Grid | 单列列表/卡片 | 数据验证方式变化 |
| 分屏/多窗口 | 支持 | 不支持/受限 | 需删除分屏相关用例 |
| 输入方式 | 外接键盘、语音 | 软键盘、语音 | 前置条件和输入步骤变化 |
| 前置条件 | "在平板端已登录"、"已连接外接键盘" | "在手机端已登录"、"App已获取通知权限" | 前置条件需设备适配 |

### 1.3 可复用 vs 需调整的判断原则

> **v2.0 修订说明**：v1.0将"保存/提交/删除"等归为可直克隆，评审发现即使是纯逻辑操作，
> 只要涉及UI交互（如点击保存按钮），步骤描述就需调整。修订后仅 `api_automation` 类型
> 用例可直克隆，`ui_automation` 类型一律需AI审查。

```
可直克隆（仅限 api_automation 类型）：
  - API接口测试用例（不涉及UI交互）
  - 纯后端逻辑验证（如：接口参数校验、响应码校验）
  - 数据层测试（如：数据库状态断言）

需AI审查改写（ui_automation 类型，一律不可跳过）：
  - 所有涉及UI操作的用例，包括：
    · 导航路径（如：侧边栏→底部Tab）
    · 操作步骤描述（如：点击顶部保存按钮→点击底部浮动按钮）
    · 元素定位（如：id=sidebar_menu→id=bottom_tab_more）
    · 页面流转（如：一页完成→三步向导）
    · 前置条件（如：在平板端已登录→在手机端已登录）
    · 预期结果（如：右侧显示详情面板→跳转到详情页）
  - 即使业务逻辑不变，UI操作步骤也必须经AI审查确认

需拆分迁移（1:N，一条平板用例拆为多条手机用例）：
  - 平板端同屏多区域操作 → 手机端需分页跳转
  - 如：平板"同时对比两个方案" → 手机"查看方案A" + "查看方案B"

需新增（手机端独有）：
  - 手势操作（下拉刷新、左滑删除、长按菜单）
  - 软键盘交互（键盘弹出遮挡、返回键收起键盘）
  - 小屏适配（文字截断、按钮重叠、横竖屏切换）
  - 通知栏/状态栏交互

需废弃（平板端独有）：
  - 分屏操作用例
  - 外接键盘快捷键用例
  - 大屏专属布局校验
```

---

## 二、现有系统适配性分析

### 2.1 已有能力（可直接复用）

| 能力 | 对应模块 | 迁移场景中的作用 |
|------|---------|----------------|
| **Excel导入** | `ExcelImportMixin` + `ExcelValidateMixin` | 平板用例Excel文档导入系统 |
| 迭代管理 | `Iteration` + `base_iteration_id` | 新建手机端迭代，关联平板端基线迭代 |
| 用例血缘 | `TestCase.parent_case_id` | 新用例指向平板端原用例，保持追溯 |
| AI生成Prompt | `PromptBuilder.for_test_case()` | 扩展`extra_context`支持迁移模式 |
| 修改模式Prompt | `_append_extra_context_sections()` | 已有`task_type=modify`逻辑，可扩展 |
| 用例版本 | `TestCaseVersion` | 记录迁移操作的版本变更 |
| 生命周期 | `LifecycleService` + 状态机 | 管理迁移后用例的生命周期 |
| UI原型解析 | `UIPrototypeScreen` + AI解析 | 上传手机端需求原型截图作为新输入 |
| 测试点管理 | `TestPoint` | 测试点可跨设备复用 |

### 2.2 需要新增的能力

| 能力 | 说明 | 优先级 |
|------|------|--------|
| 设备类型标签 | 用例/迭代级别的设备维度标记 | P0 |
| 迁移Prompt模板 | 专门用于跨设备用例改写的AI Prompt | P0 |
| 批量迁移入口 | 选择源用例 → 指定目标设备 → AI批量改写 | P0 |
| Excel格式规范化预处理 | 合并单元格展开、单单元格多步骤拆分、多Sheet合并、列名智能映射 | P0 |
| 迁移后验证任务 | 迁移后一键创建手机端验证任务，支持试执行 | P0 |
| 迁移回退机制 | 批量迁移出错后一键撤销 | P1 |
| 迁移差异标注 | AI改写后标注哪些步骤被修改及原因 | P1 |
| 1:N拆分支持 | 一条平板用例拆为多条手机用例 | P1 |
| 设备差异知识库 | 平板vs手机的常见交互差异规则 | P1 |
| 迁移报告导出 | 迁移报告支持Excel/PDF导出 | P2 |

---

## 三、详细设计

### 3.1 数据模型扩展

#### 3.1.1 TestCase 增加设备类型字段

```python
target_device = Column(
    String(20),
    nullable=True,
    comment="目标设备类型：tablet/phone/desktop/web，为空表示通用"
)
```

**设计考量**：
- 使用 `nullable=True` 而非 `default="phone"`，因为已有用例没有设备概念，强制填值会导致数据迁移
- 查询时通过 `target_device IS NULL OR target_device = 'phone'` 兼容通用用例
- 不使用枚举类型，因为未来可能扩展到手表、车机等

#### 3.1.2 Iteration 增加设备类型字段

```python
target_device = Column(
    String(20),
    nullable=True,
    comment="迭代目标设备：tablet/phone/desktop/web"
)
```

**设计考量**：
- 迭代级别的设备标记，新建手机端迭代时设置
- 该迭代下生成的用例自动继承此设备类型
- 与 `base_iteration_id` 配合：手机迭代.base_iteration_id → 平板迭代.id

#### 3.1.3 TestCase 增加迁移来源字段

> **v2.0 修订说明**：v1.0中 `migration_type` 仅支持 cloned/adapted/new/deprecated，
> 评审指出1:N拆分场景未覆盖。新增 `split` 类型，`adapted_case` 改为数组支持多条产出。

```python
migration_source_id = Column(
    Integer,
    ForeignKey("test_cases.id", ondelete="SET NULL"),
    nullable=True,
    comment="迁移来源用例ID，跨设备迁移时指向原设备用例"
)
migration_type = Column(
    String(20),
    nullable=True,
    comment="迁移类型：cloned=直接克隆/adapted=AI改写/split=拆分迁移/new=新增/deprecated=废弃"
)
migration_batch_id = Column(
    String(50),
    nullable=True,
    comment="迁移批次ID，同一次批量迁移产出的用例共享此ID，用于回退"
)
```

**与 `parent_case_id` 的区别**：
- `parent_case_id`：用例衍生/拆分关系（同一设备内）
- `migration_source_id`：跨设备迁移关系（不同设备间）
- 两者独立，一条用例可以同时有 parent_case_id（从某用例拆分）和 migration_source_id（从平板用例迁移）

**1:N拆分的数据关系**：
- 一条平板用例（id=101）拆为3条手机用例（id=201/202/203）
- 3条手机用例的 `migration_source_id` 均指向 101
- 3条手机用例的 `migration_type` 均为 `split`
- 通过 `migration_source_id` 反向查询可获取所有拆分子用例

### 3.2 AI迁移Prompt设计

#### 3.2.1 迁移Prompt核心逻辑

> **v2.0 修订说明**：新增前置条件审查、预期结果改写、优先级重评估、1:N拆分输出。

```
输入：
  1. 源用例完整内容（标题、前置条件、步骤、预期结果、优先级、用例类型）
  2. 源设备类型（tablet）
  3. 目标设备类型（phone）
  4. 目标设备的UI原型截图（可选，有则更精准）
  5. 设备差异规则（内置知识）

输出：
  1. 迁移类型判定：cloned / adapted / split / new / deprecated
  2. 改写后的完整用例（支持1:N拆分，产出多条）
  3. 差异标注：每个步骤的变更类型和原因
  4. 前置条件变更标注
  5. 预期结果变更标注
  6. 优先级调整建议
  7. 手机端独有场景发现
```

#### 3.2.2 Prompt模板（核心部分）

```
你是一个专业的跨设备测试用例迁移专家。现在需要将一条平板端测试用例迁移到手机端。

## 源用例信息
- 标题：{source_case.title}
- 前置条件：{source_case.precondition}
- 步骤：{source_case.steps_json}
- 预期结果：{source_case.expected_result}
- 优先级：{source_case.priority}
- 用例类型：{source_case.case_type}

## 设备差异规则
平板→手机的典型差异：
1. 导航方式：侧边栏/多Tab → 底部Tab栏/抽屉菜单
2. 页面布局：多栏并排 → 单栏滚动，可能拆分为多页
3. 弹窗形式：居中对话框 → 底部Sheet/全屏页面
4. 操作方式：大触控区点击 → 手势操作（滑动/长按）
5. 输入方式：外接键盘 → 软键盘（注意键盘遮挡）
6. 列表展示：表格/Grid → 单列列表/卡片
7. 分屏功能：支持 → 不支持
8. 前置条件：设备相关描述需同步改写（如"在平板端已登录"→"在手机端已登录"）

## 目标设备UI信息（如有）
{target_ui_specs}

## 迁移要求
1. 首先判断迁移类型：
   - cloned：仅限API/接口测试用例，不涉及任何UI交互
   - adapted：业务逻辑不变，操作步骤/前置条件/预期结果需因设备差异调整
   - split：一条平板用例需拆为多条手机用例（如平板同屏多区域→手机分页跳转）
   - new：手机端独有的新场景（如手势操作、软键盘交互）
   - deprecated：平板端独有功能，手机端不存在

2. 对于adapted/split类型，必须审查并改写以下所有字段：
   a. 前置条件（precondition）：
      - 设备相关描述必须改写（如"在平板端"→"在手机端"）
      - 设备特有条件必须删除或替换（如"已连接外接键盘"→删除或替换为"已获取软键盘权限"）
   b. 操作步骤（steps）：
      - 逐步骤标注变更：unchanged/modified/added/removed
      - 每个modified步骤必须标注调整原因
   c. 预期结果（expected_result）：
      - 设备相关描述必须同步改写（如"右侧显示详情面板"→"跳转到详情页"）
      - 弹窗描述必须调整（如"居中弹窗"→"底部Sheet"）
   d. 优先级（priority）：
      - 评估手机端交互复杂度是否变化
      - 若手机端操作更复杂或风险更高，建议提升优先级

3. 对于split类型，输出多条目标用例：
   - 每条用例独立完整（标题、前置条件、步骤、预期结果）
   - 标注拆分原因和各子用例的覆盖范围

4. 同时输出手机端独有场景发现（new_scenarios）：
   - 基于该用例涉及的功能，推断手机端需要额外覆盖的场景
   - 如：涉及列表操作→手机端需覆盖左滑删除、下拉刷新
   - 如：涉及输入操作→手机端需覆盖软键盘遮挡、返回键收起键盘

5. 输出格式：
{
  "migration_type": "cloned|adapted|split|new|deprecated",
  "confidence": 0.0-1.0,
  "adapted_cases": [
    {
      "title": "...",
      "precondition": "...",
      "precondition_changes": [
        {"original": "原前置条件片段", "adapted": "改写后片段", "reason": "改写原因"}
      ],
      "steps": [...],
      "expected_result": "...",
      "expected_result_changes": [
        {"original": "原预期结果片段", "adapted": "改写后片段", "reason": "改写原因"}
      ],
      "priority": 1-3,
      "priority_change": {"original": 2, "adapted": 1, "reason": "手机端操作更复杂"} | null
    }
  ],
  "step_changes": [
    {
      "case_index": 0,
      "step_index": 0,
      "change_type": "unchanged|modified|added|removed",
      "reason": "变更原因",
      "original_step": "原步骤内容（modified/removed时）",
      "new_step": "新步骤内容（modified/added时）"
    }
  ],
  "split_reason": "拆分原因（仅split类型）",
  "new_scenarios": [
    "手机端需要额外覆盖的场景描述"
  ],
  "deprecated_scenarios": [
    "平板端独有、手机端不存在的场景描述"
  ]
}
```

### 3.3 迁移流程设计

#### 3.3.1 整体流程

> **v2.0 修订说明**：
> - Step 0 增加 Excel格式规范化预处理子步骤
> - Step 1 预分析规则修订：仅 api_automation 可直克隆
> - Step 2 AI改写时同步发现手机端独有场景（而非延迟到Step 4）
> - 新增 Step 3.5 迁移后验证环节
> - 新增 Step 5 迁移回退机制
> - Step 4 调整为聚合去重+补充生成

```
┌─────────────────────────────────────────────────────────┐
│         Step 0: Excel导入（前置步骤）                     │
│                                                         │
│  Step 0.1: 上传Excel + 格式检测                          │
│  - 上传平板端用例Excel文档                                │
│  - 自动检测格式类型（标准双Sheet / 功能用例单Sheet / 其他）│
│  - 若格式不匹配，进入Step 0.2                            │
│                                                         │
│  Step 0.2: Excel格式规范化预处理（新增）                  │
│  - 合并单元格展开填充                                    │
│  - 单单元格多步骤拆分（按【1】【2】编号或换行符）         │
│  - 多Sheet合并导入（每个Sheet作为一个模块）               │
│  - 列名智能映射（用户确认系统推断的列名对应关系）         │
│  - 嵌入截图/附件提取（如有）                             │
│                                                         │
│  Step 0.3: 解析导入                                     │
│  - 验证Excel格式（复用ExcelValidateMixin）               │
│  - 解析并导入为系统内TestCase（复用ExcelImportMixin）     │
│  - 导入的用例标记 target_device = "tablet"               │
│  - 归入指定的平板端迭代                                   │
│  - 导入完成后进入Step 1                                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    用户操作入口                           │
│  选择源迭代(平板) → 选择目标迭代(手机) → 发起批量迁移    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Step 1: 用例预分析（不调用AI）                    │
│                                                         │
│  分类规则（v2.0修订）：                                  │
│  - case_type == "api_automation" → 可直克隆              │
│  - case_type == "ui_automation" → 需AI审查               │
│  - 包含分屏/外接键盘等关键词 → 可能需废弃                │
│                                                         │
│  输出迁移预览报告：                                      │
│  - 可直克隆数量（仅API用例）                             │
│  - 需AI审查数量（所有UI用例）                            │
│  - 可能需废弃数量                                        │
│  - 预估AI调用量和Token消耗                               │
└──────────────────────┬──────────────────────────────────┘
                       │ 用户确认
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Step 2: AI批量迁移改写                            │
│                                                         │
│  - 对"需AI审查"的UI用例，逐条调用迁移Prompt              │
│  - AI改写时同步输出 new_scenarios（手机端独有场景）       │
│  - 对"可直克隆"的API用例，直接复制并标记migration_type   │
│  - 支持1:N拆分：一条平板用例产出多条手机用例              │
│  - 每条用例独立处理，单条失败不影响整体                   │
│  - 通过WebSocket实时推送进度                             │
│  - 所有产出用例标记 migration_batch_id                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Step 3: 结果入库 + 人工审核                      │
│                                                         │
│  - 迁移后的用例以draft状态入库                           │
│  - migration_source_id指向源用例                         │
│  - target_device标记为phone                              │
│  - 生成迁移差异报告（含前置条件/步骤/预期结果/优先级变更）│
│  - 用户在审核界面逐条确认/修改/废弃                      │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│    Step 3.5: 迁移后验证（新增）                          │
│                                                         │
│  - 一键创建手机端验证任务（关联迁移产出的用例）           │
│  - 对 ui_automation 类型用例，在手机端设备试执行         │
│  - 记录执行结果（通过/失败/步骤卡住位置）                │
│  - 失败的用例自动标记为 needs_modify                     │
│  - 验证结果回填到迁移报告                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Step 4: 手机端独有场景聚合去重 + 补充生成               │
│                                                         │
│  - 聚合Step 2中每条用例输出的 new_scenarios              │
│  - 去重合并（同一功能模块的手势/软键盘场景可能重复）     │
│  - 结合手机端UI原型补充遗漏场景                          │
│  - 批量生成手机端独有用例                                │
│  - migration_type = "new"                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│    Step 5: 迁移回退（新增，可选）                        │
│                                                         │
│  - 触发条件：批量迁移方向错误或质量不可接受               │
│  - 通过 migration_batch_id 批量删除该批次所有产出用例    │
│  - 源用例不受影响（仅删除目标端用例）                    │
│  - 回退操作记录审计日志                                  │
│  - 回退后可调整参数重新执行迁移                          │
└─────────────────────────────────────────────────────────┘
```

#### 3.3.2 用例预分析规则（不调用AI，基于规则引擎）

> **v2.0 修订说明**：v1.0的 `CAN_CLONE_KEYWORDS` 规则过于乐观，将"保存/提交/删除"
> 等UI操作归为可直克隆。修订后预分析以 `case_type` 为主要判断依据，
> 关键词仅作为辅助参考，不再作为直克隆依据。

```python
MIGRATION_CATEGORY_RULES = [
    {
        "category": "can_clone",
        "condition": "case_type == 'api_automation'",
        "description": "API/接口测试用例不涉及UI交互，可直接克隆",
    },
    {
        "category": "needs_ai_review",
        "condition": "case_type == 'ui_automation'",
        "description": "所有UI测试用例一律需AI审查改写",
    },
    {
        "category": "likely_deprecated",
        "condition": "any(kw in text for kw in DEPRECATED_KEYWORDS)",
        "description": "包含平板端独有功能关键词，可能需废弃",
    },
]

DEPRECATED_KEYWORDS = [
    "分屏", "多窗口", "外接键盘", "快捷键", "横屏模式",
    "侧边栏展开", "双栏对比", "并排显示",
]

UI_REVIEW_HINT_KEYWORDS = [
    "侧边栏", "导航栏", "Tab栏", "菜单栏", "抽屉",
    "拖拽", "右键", "悬浮", "悬停",
    "表格视图", "看板视图", "日历视图",
    "弹窗", "对话框", "面板",
]
```

**预分析输出增强**：
- 新增 `estimated_ai_calls` 字段：预估AI调用量（= 需AI审查的用例数）
- 新增 `estimated_tokens` 字段：预估Token消耗
- 新增 `clone_savings` 字段：直克隆节省的AI调用量

### 3.4 API设计

#### 3.4.0 Excel导入（前置步骤）

系统已有 `ExcelImportMixin` 和 `ExcelValidateMixin`，支持两种Excel格式：

**格式A：标准双Sheet格式**
- Sheet1 `用例信息`：用例编号、用例标题、所属模块、前置条件、预期结果、优先级
- Sheet2 `测试步骤`：步骤编号、操作步骤、预期结果、业务视图、技术视图、已定位、定位状态、CSS选择器、XPath、元素类型

**格式B：功能用例格式（单Sheet）**
- 列：用例序号、执行用例ID、用例描述/标题、所属模块/分组、初始条件/前置条件、操作步骤/步骤描述、期望结果/预期结果、优先级/用例等级、用例类型
- 支持模块分组标题行（操作步骤为空的行，第一列为模块名）

**Excel格式规范化预处理API（新增）**：

```
POST /api/v1/case-migration/normalize-excel
Request: multipart/form-data
  - file: Excel文件
Response:
{
  "detected_format": "functional|standard|unknown",
  "normalization_needed": true,
  "issues": [
    {
      "type": "merged_cells",
      "sheet": "Sheet1",
      "range": "A2:A5",
      "suggestion": "将合并单元格展开，向下填充模块名"
    },
    {
      "type": "multi_step_in_cell",
      "row": 12,
      "cell": "操作步骤",
      "value": "1.打开App 2.点击登录 3.输入账号",
      "suggestion": "拆分为3个独立步骤"
    },
    {
      "type": "multi_sheet",
      "sheet_count": 5,
      "suggestion": "5个Sheet将合并导入，每个Sheet作为一个模块"
    }
  ],
  "column_mapping": {
    "detected": {"用例描述": "title", "操作步骤": "action", ...},
    "confidence": 0.85
  },
  "preview": {
    "total_rows": 50,
    "module_distribution": {"登录模块": 8, "答题模块": 15, ...}
  }
}
```

**确认规范化并导入**：

```
POST /api/v1/case-migration/import-excel
Request: multipart/form-data
  - file: Excel文件
  - project_id: 项目ID
  - iteration_id: 平板端迭代ID
  - target_device: "tablet"
  - column_mapping: {"自定义列名1": "title", ...}  // 可选，覆盖自动推断
  - normalize_options: {                             // 可选
      "expand_merged_cells": true,
      "split_multi_step": true,
      "merge_sheets": true
    }
Response:
{
  "imported_count": 45,
  "failed_count": 2,
  "imported_case_ids": [101, 102, ...],
  "normalization_applied": {
    "merged_cells_expanded": 12,
    "multi_steps_split": 8,
    "sheets_merged": 5
  },
  "errors": [
    {"row": 12, "reason": "用例标题为空，跳过"}
  ]
}
```

#### 3.4.1 迁移预分析

```
POST /api/v1/case-migration/preview
Request:
{
  "source_iteration_id": 1,
  "target_device": "phone",
  "target_ui_prototype_project_id": 5
}
Response:
{
  "total_cases": 50,
  "can_clone": 5,                 // 仅API用例
  "needs_ai_review": 40,          // 所有UI用例
  "likely_deprecated": 5,
  "estimated_ai_calls": 40,
  "estimated_tokens": "~120000",
  "clone_savings": "5条API用例免AI调用",
  "details": [
    {
      "case_id": 101,
      "title": "平板分屏模式下同时查看两个模块",
      "category": "likely_deprecated",
      "reason": "包含分屏关键词，手机端不支持"
    },
    ...
  ]
}
```

#### 3.4.2 执行迁移

```
POST /api/v1/case-migration/execute
Request:
{
  "source_iteration_id": 1,
  "target_iteration_id": 2,
  "target_device": "phone",
  "case_ids": [101, 102, 103],
  "target_ui_prototype_project_id": 5,
  "options": {
    "include_new_scenarios": true,
    "auto_clone_api_cases": true
  }
}
Response:
{
  "task_id": "migration_abc123",
  "migration_batch_id": "batch_20260522_001",
  "status": "running"
}
```

#### 3.4.3 迁移进度查询

```
GET /api/v1/case-migration/status/{task_id}
Response:
{
  "task_id": "migration_abc123",
  "migration_batch_id": "batch_20260522_001",
  "status": "running|completed|failed",
  "progress": {
    "total": 50,
    "completed": 30,
    "cloned": 3,
    "adapted": 22,
    "split": 3,
    "new": 1,
    "deprecated": 1,
    "failed": 0
  }
}
```

#### 3.4.4 迁移报告

> **v2.0 修订说明**：报告内容扩展，增加前置条件变更、预期结果变更、优先级调整、
> 拆分详情、验证结果，并支持导出。

```
GET /api/v1/case-migration/report/{task_id}
Response:
{
  "migration_batch_id": "batch_20260522_001",
  "summary": {
    "total_source": 50,
    "cloned": 5,
    "adapted": 35,
    "split": 3,
    "split_target_count": 7,
    "new": 5,
    "deprecated": 2
  },
  "adapted_cases": [
    {
      "source_case_id": 101,
      "source_title": "通过侧边栏导航到设置页",
      "new_case_id": 201,
      "new_title": "通过底部Tab导航到设置页",
      "precondition_changes": [
        {"original": "在平板端已登录", "adapted": "在手机端已登录", "reason": "设备描述适配"}
      ],
      "step_changes": [
        {"step_index": 0, "change_type": "modified", "reason": "侧边栏→底部Tab"}
      ],
      "expected_result_changes": [
        {"original": "右侧显示设置面板", "adapted": "跳转到设置页面", "reason": "手机端无侧面板"}
      ],
      "priority_change": null
    }
  ],
  "split_cases": [
    {
      "source_case_id": 105,
      "source_title": "同时对比两个答题方案",
      "split_reason": "手机端无法同屏对比，需拆分为独立查看",
      "target_cases": [
        {"new_case_id": 211, "title": "查看答题方案A"},
        {"new_case_id": 212, "title": "查看答题方案B"}
      ]
    }
  ],
  "new_cases": [...],
  "deprecated_cases": [...],
  "verification_results": {
    "verified_count": 30,
    "passed": 25,
    "failed": 3,
    "needs_modify": 2
  }
}
```

**迁移报告导出（新增）**：

```
GET /api/v1/case-migration/report/{task_id}/export?format=xlsx|pdf
Response: 文件下载
```

#### 3.4.5 迁移回退（新增）

```
POST /api/v1/case-migration/rollback
Request:
{
  "migration_batch_id": "batch_20260522_001",
  "reason": "AI改写方向错误，需调整参数重新迁移"
}
Response:
{
  "rolled_back_count": 47,
  "rolled_back_case_ids": [201, 202, ...],
  "source_cases_affected": false
}
```

**安全约束**：
- 仅可回退 `draft` 状态的用例，已进入 `active` 状态的需先手动废弃
- 回退操作需二次确认
- 回退操作记录审计日志

#### 3.4.6 迁移后验证任务（新增）

```
POST /api/v1/case-migration/verify
Request:
{
  "migration_batch_id": "batch_20260522_001",
  "device_id": "phone_001",
  "case_ids": [201, 202, 203]    // 可选，不传则验证全部
}
Response:
{
  "task_id": "verify_abc123",
  "status": "running"
}
```

### 3.5 前端交互设计

#### 3.5.1 迁移入口

在迭代管理页面增加"跨设备迁移"按钮，进入迁移向导：

**向导Step 1：上传平板用例**
1. 上传平板端用例Excel文档
2. 系统自动检测格式，展示规范化建议（合并单元格、多步骤拆分等）
3. 用户确认列名映射和规范化选项
4. 选择/创建平板端迭代，将Excel用例导入系统
5. 导入完成后标记 `target_device = "tablet"`

**向导Step 2：配置迁移**
1. 选择源迭代（刚导入的平板端迭代）
2. 选择/创建目标迭代（手机端）
3. 上传手机端UI原型截图（可选，提高AI改写精度）
4. 预览迁移范围（区分API可克隆 / UI需审查 / 可能废弃）→ 确认执行

**向导Step 3：审核与验证**
1. 查看迁移差异报告
2. 逐条审核（左右对照 + 步骤级标注）
3. 一键创建验证任务（可选）
4. 确认全部通过或回退重做

#### 3.5.2 迁移审核界面

在用例列表中增加"迁移差异"视图：
- 左右对照：左侧平板原用例，右侧手机新用例
- 差异标注维度（v2.0扩展）：
  - 前置条件变更：黄色高亮
  - 步骤变更：unchanged(灰) / modified(黄) / added(绿) / removed(红)
  - 预期结果变更：黄色高亮
  - 优先级调整：蓝色标记
- 拆分用例展示：一条源用例 → 多条目标用例，折叠/展开
- 支持逐条确认/修改/废弃
- 批量操作：全部通过 / 批量废弃

#### 3.5.3 设备筛选

用例列表增加设备类型筛选器：
- 全部 / 平板 / 手机 / 桌面 / 通用
- 迭代详情页按设备分组展示

#### 3.5.4 迁移回退入口（新增）

迁移报告页面增加"撤销迁移"按钮：
- 显示将被删除的用例数量
- 二次确认弹窗
- 仅可回退draft状态用例

---

## 四、实施阶段

> **硬性约束**：所有实施工作必须严格遵守项目开发规范（`.trae/rules/project_rules.md`），
> 以下为规范要点与迁移模块的对应关系，每个Phase的验收标准中均包含合规检查项。

### 4.0 项目开发规范合规要求（硬性指标）

| 规范条目 | 规范要求 | 迁移模块合规落地 |
|---------|---------|----------------|
| **代码风格** | lowerCamelCase/UpperCamelCase/UPPER_SNAKE_CASE；4空格缩进；行宽≤120；公开方法加类型注解与文档注释 | `CaseMigrationService` 及所有新增方法必须加类型注解和文档注释；禁止无效注释 |
| **语言规范** | Python强制类型注解；IO统一with管理；字符串只用f-string；TS禁用any，强制空值处理 | Excel文件读取用`with`管理；AI响应解析强制异常捕获；前端TS禁用any |
| **架构设计** | 单文件≤350行；依赖构造函数注入；新增模块遵循项目现有结构 | `CaseMigrationService`若超350行必须拆分为mixin（参照`test_case_view/`的mixin模式）；迁移Prompt拆为独立模块 |
| **安全红线** | SQL参数化传参；密钥环境变量读取；日志脱敏；外部输入必须模型校验 | Excel上传文件路径必须校验（防路径穿越）；迁移API入参必须经Pydantic模型校验；AI返回的JSON必须校验后才入库 |
| **性能要求** | 禁止循环内SQL；批量写入用batch；高频查询优先Set/Map | 批量迁移入库用`session.bulk_save_objects`；预分析查询用Set去重；迁移进度查询走Redis缓存 |
| **测试规范** | 核心分支覆盖率≥95%；配套正常/空值/异常/边界用例；真实测试库；自动清理 | 每个Phase必须配套测试：正常迁移、空Excel、格式错误、AI超时、回退冲突等场景；测试数据自动清理 |
| **AI生成约束** | 禁止TODO与空占位；IO/网络/解析强制异常捕获；深层属性空安全兜底 | AI调用必须try/except；AI返回的`adapted_cases`数组必须做空安全兜底（`cases[0] if cases else None`） |
| **修复与合并** | Bug修复定位根因；合并需全量测试+类型检查+CR通过；库表变更附带迁移与回滚 | 新增字段必须配套Alembic迁移脚本；迁移脚本必须包含`downgrade`回滚；合并前必须跑全量测试 |

### Phase 1: 基础能力（最小可用）

**目标**：支持Excel导入 + 单条用例的跨设备AI改写

1. 数据库迁移：`test_cases` 增加 `target_device`、`migration_source_id`、`migration_type`、`migration_batch_id` 字段
2. `iterations` 增加 `target_device` 字段
3. **Excel导入增强**：扩展现有 `ExcelImportMixin`，支持指定迭代和设备类型
4. **Excel格式规范化预处理**：合并单元格展开、单单元格多步骤拆分、多Sheet合并、列名智能映射
5. 迁移Prompt模板实现（含前置条件/预期结果/优先级改写）
6. 单条用例迁移API
7. 用例列表增加设备筛选

**验收标准**：
- 可上传平板用例Excel文档（含合并单元格、多步骤单单元格等常见格式问题），系统自动规范化后导入
- 导入的用例标记为tablet设备
- 可选择一条平板用例，AI改写为手机端用例（含前置条件、步骤、预期结果、优先级的完整改写）
- 新用例通过 `migration_source_id` 关联原用例
- 用例列表可按设备类型筛选

**合规检查项**：
- [ ] Alembic迁移脚本含`upgrade`和`downgrade`
- [ ] 新增API入参均经Pydantic模型校验
- [ ] Excel文件读取使用`with`管理
- [ ] AI调用包裹try/except，AI返回JSON做空安全兜底
- [ ] `CaseMigrationService`单文件≤350行，超限则拆mixin
- [ ] 核心分支覆盖率≥95%（正常迁移、空Excel、格式错误、AI超时）
- [ ] 无TODO/空占位，无硬编码密钥

### Phase 2: 批量迁移

**目标**：支持迭代级别的批量迁移

1. 迁移预分析API（以 `case_type` 为主要分类依据）
2. 批量迁移执行（异步任务 + WebSocket进度推送）
3. 1:N拆分支持（一条平板用例产出多条手机用例）
4. 迁移报告生成（含前置条件/步骤/预期结果/优先级变更、拆分详情）
5. 迁移报告导出（Excel/PDF）
6. 前端迁移向导界面

**验收标准**：
- 可选择整个平板迭代，一键迁移到手机迭代
- API用例自动克隆，UI用例全部经AI审查
- 批量迁移过程中单条失败不影响整体
- 拆分用例正确关联源用例

**合规检查项**：
- [ ] 批量入库使用`session.bulk_save_objects`，禁止循环内单条INSERT
- [ ] 迁移进度查询走缓存，禁止高频查库
- [ ] 前端TS禁用any，空值强制处理
- [ ] WebSocket推送异常捕获，断线重连兜底
- [ ] 核心分支覆盖率≥95%（批量成功、单条失败、部分拆分、AI批量超时）
- [ ] 测试数据自动清理

### Phase 3: 验证 + 回退 + 补充生成

**目标**：完善迁移后的验证、回退和补充流程

1. 迁移差异对照界面（左右对比 + 前置条件/步骤/预期结果/优先级多维度标注）
2. 迁移后验证任务（一键创建手机端测试任务，试执行并回填结果）
3. 迁移回退机制（按 `migration_batch_id` 批量撤销）
4. 手机端独有场景聚合去重 + 补充生成
5. 迁移后用例的批量审核流程
6. 设备差异知识库（可配置的规则引擎）

**验收标准**：
- 差异对照界面可清晰展示前置条件/步骤/预期结果/优先级的每项变更
- 验证任务可自动执行并标记失败用例
- 回退操作可一键撤销整批迁移
- 手机端独有场景覆盖率 ≥ 90%（人工评估）
- 审核流程与现有评审流程无缝衔接

**合规检查项**：
- [ ] 回退操作使用参数化SQL删除，禁止字符串拼接
- [ ] 回退操作记录审计日志，日志脱敏敏感字段
- [ ] 验证任务执行异常捕获，超时自动终止
- [ ] 核心分支覆盖率≥95%（正常回退、回退已active用例拒绝、验证通过、验证失败标记）
- [ ] 合并前全量测试+类型检查无错

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **Excel格式不统一** | 导入失败或数据丢失 | 1. 新增格式规范化预处理（合并单元格展开、多步骤拆分、多Sheet合并）<br>2. 提供Excel模板下载，引导用户按模板整理<br>3. 列名智能映射 + 用户确认 |
| **Excel步骤描述不规范** | AI改写时无法准确理解操作意图 | 1. 导入后增加"步骤规范化"预处理<br>2. AI Prompt中要求先理解再改写 |
| **UI用例被错误跳过AI审查** | 产出不可用的步骤描述 | 1. 仅 `api_automation` 类型可直克隆<br>2. `ui_automation` 类型一律需AI审查<br>3. 预分析以 `case_type` 为准，不以关键词为准 |
| AI改写质量不稳定 | 迁移后用例需大量人工修正 | 1. 迁移后一律为draft状态，必须人工审核<br>2. 提供差异标注辅助快速定位问题<br>3. 迁移后验证任务可试执行确认 |
| 1:N拆分判断不准 | 该拆的没拆，不该拆的拆了 | 1. AI输出confidence字段，低置信度拆分需人工确认<br>2. 拆分用例在审核界面特殊标注 |
| 前置条件/预期结果遗漏改写 | 用例不可执行或验证失败 | 1. Prompt中明确要求审查并改写前置条件和预期结果<br>2. 迁移后验证任务可实际检验 |
| 批量迁移AI调用成本高 | Token消耗大 | 1. 仅API用例直接克隆不调AI<br>2. 支持指定用例范围，避免全量迁移<br>3. 预分析展示预估Token消耗 |
| 迁移后用例与原用例失去关联 | 无法追溯 | 1. `migration_source_id` 强制关联<br>2. 迁移报告持久化保存 |
| 批量迁移方向错误 | 大量无效用例需手动清理 | 1. `migration_batch_id` 支持一键回退<br>2. 回退仅删除draft状态用例，不影响源用例 |

---

## 六、与现有系统的集成点

```
 ┌──────────────┐
 │ Excel导入     │ ← 复用 ExcelImportMixin + ExcelValidateMixin
 │ +规范化预处理  │ ← 新增：合并单元格/多步骤拆分/多Sheet合并/列名映射
 └──────┬───────┘
        │ 导入平板用例到系统
        ▼
 ┌──────────────┐
 │  迭代管理     │ ← 新增 target_device 字段
 │  Iteration   │ ← base_iteration_id 关联基线
 └──────┬───────┘
        │
 ┌──────▼───────┐
 │  迁移服务     │ ← 新增 CaseMigrationService
 │  (新增模块)   │ ← 调用 PromptBuilder 扩展
 └──────┬───────┘
        │
        ├──────────┬──────────┬──────────┐
        │          │          │          │
 ┌──────▼──┐ ┌────▼────┐ ┌───▼─────┐ ┌──▼──────┐
 │Prompt   │ │生命周期  │ │UI原型   │ │测试任务  │
 │Builder  │ │服务     │ │解析     │ │执行引擎  │
 │扩展迁移 │ │draft→  │ │手机端   │ │迁移后   │
 │模式     │ │审核    │ │截图     │ │验证     │
 └─────────┘ └─────────┘ └─────────┘ └─────────┘
```

### 关键集成点说明：

1. **ExcelImportMixin**：复用现有双格式导入能力，扩展支持 `target_device` 和 `iteration_id` 参数；新增格式规范化预处理
2. **PromptBuilder**：在 `_append_extra_context_sections()` 中新增 `task_type="migrate"` 分支，注入源用例 + 设备差异规则 + 前置条件/预期结果改写要求
3. **LifecycleService**：迁移后的用例走 `draft → pending_review → active` 标准流程；验证失败的用例走 `needs_modify`
4. **UI原型解析**：手机端需求原型截图作为迁移的额外输入，提高改写精度
5. **TestCaseVersion**：迁移操作记录为 `change_type="migration"` 的版本记录
6. **WebSocket**：复用现有WebSocket通道推送批量迁移进度
7. **测试任务执行引擎**：迁移后验证任务复用现有执行能力，在手机端设备试执行

---

## 附录A：评审意见追踪表

> 以下为测试工程师评审过程中提出的所有意见及其处置结果。

| # | 评审意见 | 级别 | 采纳 | 文档体现位置 | 处置说明 |
|---|---------|------|------|-------------|---------|
| 1 | Excel真实格式复杂（合并单元格、单单元格多步骤、多Sheet分模块、嵌入截图） | P0 | ✅ 采纳 | 1.2差异矩阵、3.3.1 Step 0.2、3.4.0 normalize-excel API、5风险表 | 新增Step 0.2格式规范化预处理，含合并单元格展开、多步骤拆分、多Sheet合并、列名智能映射；同时提供Excel模板下载作为备选方案 |
| 2 | "可直克隆"判断过于乐观，"保存/提交/删除"等UI操作步骤描述在不同设备上完全不同 | P0 | ✅ 采纳 | 1.3判断原则、3.3.2预分析规则、5风险表 | 修订判断原则：仅 `api_automation` 类型可直克隆，`ui_automation` 一律需AI审查；`CAN_CLONE_KEYWORDS` 规则降级为辅助参考；预分析以 `case_type` 为主要依据 |
| 3 | 缺少迁移后验证环节，无法确认迁移结果是否正确 | P0 | ✅ 采纳 | 3.3.1 Step 3.5、3.4.6验证API、3.5.1向导Step 3、Phase 3验收标准 | 新增Step 3.5迁移后验证：一键创建手机端测试任务，试执行并回填结果，失败用例自动标记 `needs_modify` |
| 4 | 1:1迁移假设不成立，一条平板用例可能需拆为多条手机用例 | P1 | ✅ 采纳 | 1.3判断原则新增"需拆分迁移"、3.1.3新增split类型和migration_batch_id、3.2.2 Prompt输出adapted_cases数组、3.3.1 Step 2、3.4.3进度查询、3.4.4报告、3.5.2审核界面、Phase 2 | 新增 `migration_type=split`；Prompt输出 `adapted_cases` 改为数组支持1:N；数据模型新增 `migration_batch_id` 用于回退；审核界面支持拆分用例折叠/展开 |
| 5 | 前置条件的设备适配被忽略 | P1 | ✅ 采纳 | 1.2差异矩阵新增前置条件行、3.2.2 Prompt新增前置条件审查要求、3.4.4报告新增precondition_changes、3.5.2审核界面新增前置条件变更标注 | Prompt模板中明确要求AI审查并改写 `precondition` 字段；差异报告和审核界面增加前置条件变更维度 |
| 6 | 缺少回退/撤销机制 | P1 | ✅ 采纳 | 3.1.3新增migration_batch_id、3.3.1 Step 5、3.4.5回退API、3.5.4回退入口、5风险表 | 新增 `migration_batch_id` 字段；新增Step 5回退流程和rollback API；安全约束：仅可回退draft状态用例，需二次确认 |
| 7 | 预期结果需同步改写 | P2 | ✅ 采纳 | 3.2.2 Prompt新增预期结果改写要求、3.4.4报告新增expected_result_changes、3.5.2审核界面新增预期结果变更标注 | Prompt模板中明确要求同步改写 `expected_result`；差异报告和审核界面增加预期结果变更维度 |
| 8 | 优先级可能需要调整 | P2 | ✅ 采纳 | 3.2.2 Prompt新增优先级重评估、3.4.4报告新增priority_change、3.5.2审核界面新增优先级调整标记 | Prompt模板中要求AI评估手机端交互复杂度变化并建议优先级调整；差异报告增加优先级变更字段 |
| 9 | 迁移报告应可导出 | P2 | ✅ 采纳 | 3.4.4报告导出API、Phase 2实施项 | 新增报告导出API，支持xlsx和pdf格式 |
| 10 | 手机端独有场景发现不应只在Step 4，应在单条迁移时同步发现 | P2 | ✅ 采纳 | 3.3.1 Step 2说明、Step 4调整为聚合去重 | Step 2 AI改写时同步输出 `new_scenarios`；Step 4调整为"聚合去重+补充生成"而非从零发现 |

---

## 附录B：变更历史

| 版本 | 日期 | 变更内容 | 变更原因 |
|------|------|---------|---------|
| v1.0 | 2026-05-22 | 初始版本 | 项目规划 |
| v1.1 | 2026-05-22 | 补充Excel导入前置步骤 | 需求澄清：平板用例为Excel文档 |
| v2.0 | 2026-05-22 | 评审意见全面整合 | 测试工程师评审，10条意见全部采纳 |
| v2.1 | 2026-05-22 | 新增4.0项目开发规范合规要求（硬性指标） | 需求补充：实施必须符合项目开发规范 |

### v2.0 详细变更清单

| 变更位置 | v1.0 内容 | v2.0 内容 | 对应评审意见 |
|---------|----------|----------|-------------|
| 1.2 差异矩阵 | 7行，无前置条件行 | 8行，新增"前置条件"行 | #5 |
| 1.3 判断原则 | "可复用"含保存/提交/删除等UI操作 | 仅api_automation可直克隆，ui_automation一律需AI审查；新增"需拆分迁移"类别 | #2, #4 |
| 2.2 新增能力 | 6项 | 10项，新增Excel规范化预处理、迁移后验证、回退机制、1:N拆分、报告导出 | #1, #3, #4, #6, #9 |
| 3.1.3 迁移来源字段 | migration_type含4种 | 新增split类型；新增migration_batch_id字段 | #4, #6 |
| 3.2.1 Prompt输入输出 | 5输入3输出 | 6输入（含case_type）7输出（含前置条件/预期结果/优先级变更、1:N拆分） | #4, #5, #7, #8 |
| 3.2.2 Prompt模板 | 无前置条件/预期结果/优先级要求 | 新增前置条件审查、预期结果改写、优先级重评估、1:N拆分输出、独有场景同步发现 | #4, #5, #7, #8, #10 |
| 3.3.1 整体流程 | 5步（Step 0~4） | 7步（Step 0细化、新增Step 3.5验证、Step 5回退、Step 4调整） | #1, #3, #6, #10 |
| 3.3.2 预分析规则 | CAN_CLONE_KEYWORDS关键词匹配 | 以case_type为主要依据，关键词降级为辅助 | #2 |
| 3.4 API设计 | 5个API | 8个API（新增normalize-excel、rollback、verify、report/export） | #1, #3, #6, #9 |
| 3.5 前端设计 | 3个子节 | 4个子节（新增3.5.4回退入口）；3.5.1向导扩展为3步；3.5.2差异标注扩展4维度 | #3, #4, #5, #6, #7, #8 |
| 四、实施阶段 | 3个Phase | 3个Phase内容大幅调整：Phase 1新增规范化预处理；Phase 2新增1:N拆分和报告导出；Phase 3新增验证+回退 | 全部 |
| 五、风险 | 6项 | 9项，新增"UI用例被错误跳过"、"1:N拆分判断不准"、"前置条件/预期结果遗漏"、"批量迁移方向错误" | #2, #4, #5, #6 |
| 六、集成点 | 6个集成点 | 7个集成点，新增"测试任务执行引擎" | #3 |
