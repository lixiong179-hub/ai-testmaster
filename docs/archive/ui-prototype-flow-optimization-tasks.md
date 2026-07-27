# UI 原型图流程编排优化实施任务项

## 1. 背景

当前 `AI生成测试用例` 页面已接入 UI 原型图流程编辑能力，核心实现位于：

- `src/views/case/ai-generate.vue`
- `src/views/case/ContextSelectPanel.vue`
- `src/components/case/FlowSortEditor.vue`
- `src/components/case/FlowNodeCard.vue`
- `src/components/case/FlowTypeConfigDialog.vue`
- `src/store/useGenerateStore.ts`

现有实现基于 `@vue-flow/core`，已经具备节点拖拽、画布缩放、连线、流程类型配置、分支/异常/旁路标注、生成接口传参等基础能力。

但与参考图所展示的“原型页面流总览图”相比，当前交互仍偏向流程编辑器，存在总览感不足、缩略图比例偏小、节点视觉偏重、复杂流程浏览不够便捷、分支布局不够清晰等问题。

本文档用于拆解后续优化实施任务，目标是让 UI 原型图流程编排更接近产品原型流图体验，同时保留 AI 生成测试用例所需的结构化编辑能力。

## 2. 优化目标

### 2.1 体验目标

- 支持用户像查看产品原型流程图一样浏览全部页面。
- 支持用户快速识别主干、分支、异常、旁路流程。
- 支持大量 UI 页面下的搜索、定位、缩放和路径追踪。
- 支持在总览模式和编辑模式之间切换。
- 降低首次使用成本，减少隐藏操作。

### 2.2 业务目标

- 提升 AI 生成测试用例前的 UI 流程整理效率。
- 让页面跳转关系、分支条件、异常场景能更稳定地传递给后端生成接口。
- 为后续按页面路径、按分支路径、按异常路径生成测试用例打基础。

### 2.3 技术目标

- 继续复用 `@vue-flow/core`，避免重写画布能力。
- 保持现有 `flow_sort_data` 数据结构兼容。
- 优化仅影响 UI 原型图流程编辑区域，不破坏现有生成链路。
- 支持后续扩展节点分组、路径播放、自动识别跳转关系等能力。

## 3. 当前能力梳理

### 3.1 已具备能力

- UI 原型图版本选择。
- 根据版本加载屏幕列表。
- 屏幕节点画布展示。
- 节点拖拽。
- 画布缩放。
- 小地图。
- 节点连线。
- 连线条件配置。
- 节点流程类型切换：
  - 主干
  - 分支
  - 异常
  - 旁路
- 主干顺序前移/后移。
- 自动布局。
- 撤销。
- 删除选中节点。
- Prompt 数据预览。
- 生成时提交 `flow_sort_data`。

### 3.2 当前不足

- 节点卡片视觉偏重，一屏可见节点较少。
- 缺少专门的“总览模式”。
- 缩略图不是视觉主体，不像参考图中的原型流图。
- 自动布局仅做基础横向主干和下方分支，复杂分支容易堆叠。
- 缺少节点搜索与快速定位。
- 缺少点击节点后上下游路径高亮。
- 缺少连线悬浮信息展示。
- 缺少模块分组背景。
- 缺少分支折叠/展开。
- 缺少流程完整度统计与提示。
- 新用户不容易发现“拖动 Handle 可连线”。

## 4. 目标交互形态

### 4.1 总览模式

总览模式用于快速浏览完整 UI 页面流。

特点：

- 节点更小。
- 页面截图占主要面积。
- 只保留页面名称、流程类型色条或小标签。
- 连线更浅、更细。
- 默认适配全图。
- 适合查看参考图那样的大范围页面关系。

### 4.2 编辑模式

编辑模式用于精确配置流程数据。

特点：

- 节点展示更多信息。
- 可切换主干、分支、异常、旁路。
- 可编辑挂靠主干、触发条件、前置操作、预期现象等。
- 可删除节点、调整主干顺序、编辑连线条件。
- 适合生成测试用例前的结构化整理。

### 4.3 路径聚焦模式

路径聚焦模式用于理解某个页面的上下游关系。

特点：

- 点击节点后高亮当前节点。
- 高亮上游节点、下游节点、相关连线。
- 弱化无关节点。
- 可显示从入口页到当前节点的路径。

## 5. 数据结构与兼容性要求

### 5.1 现有提交结构

当前生成接口依赖 `flow_sort_data`，格式包括：

```json
{
  "nodes": [
    {
      "screen_id": 1,
      "screen_order": 1,
      "flow_type": "main",
      "main_order": 1,
      "screen_name": "首页",
      "ui_spec_elements": [],
      "summary": "",
      "flow_meta": {}
    }
  ],
  "edges": [
    {
      "source": "1",
      "target": "2",
      "edge_type": "branch",
      "condition": "点击高级筛选",
      "label": "分支：点击高级筛选",
      "pre_action": "",
      "note": ""
    }
  ],
  "module_info": {
    "name": "",
    "description": ""
  }
}
```

### 5.2 兼容性要求

- 不删除现有字段。
- 不修改字段语义。
- 新增 UI 状态字段仅在前端内部使用，不传或可选传。
- 如果新增布局信息，应放在可选字段中，例如：

```ts
view_meta?: {
  group_name?: string
  manual_position?: boolean
  last_layout_strategy?: string
}
```

说明：

- `displayMode`、搜索关键词、高亮状态、折叠状态属于临时 UI 状态，不应进入 `flow_sort_data`。
- 如后续需要保存布局，应通过独立布局字段或独立接口保存，不应污染 AI 生成所需的流程语义字段。

### 5.3 建议新增前端状态

建议在 `FlowSortEditor.vue` 内维护以下状态：

```ts
const displayMode = ref<'overview' | 'edit'>('overview')
const focusedNodeId = ref<string | null>(null)
const searchKeyword = ref('')
const collapsedParentNodeIds = ref<string[]>([])
const highlightedNodeIds = computed(() => new Set<string>())
const highlightedEdgeIds = computed(() => new Set<string>())
```

## 6. 分阶段实施计划

## 阶段一：总览模式与基础观感优化

### 任务 1.1 增加总览/编辑模式切换

#### 目标

在流程编辑器顶部工具栏增加模式切换，让用户可以在轻量总览和详细编辑之间切换。

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`
- `src/components/case/FlowNodeCard.vue`

#### 实施内容

- 在 `FlowSortEditor.vue` 中新增 `displayMode` 状态。
- 工具栏增加 `el-segmented` 或 `el-radio-group`：
  - 总览
  - 编辑
- 将 `displayMode` 作为 prop 传给 `FlowNodeCard`。
- 根据模式切换节点样式和显示内容。

#### 交互细节

- 默认进入总览模式。
- 用户点击任意节点或选择编辑操作后，可自动切换到编辑模式，也可以保持手动切换。
- 总览模式下仍允许拖拽和点击预览。
- 编辑模式下展示完整操作入口。

#### 验收标准

- 页面加载后默认显示总览模式。
- 用户可切换到编辑模式。
- 切换模式不会丢失节点位置、连线和流程类型。
- 切换模式不会影响最终 `flow_sort_data`。

### 任务 1.2 优化总览模式节点样式

#### 目标

让节点更接近参考图中的原型缩略图节点。

#### 涉及文件

- `src/components/case/FlowNodeCard.vue`

#### 实施内容

- 新增 `displayMode` prop。
- 总览模式下：
  - 节点宽度建议 `160px` 到 `190px`。
  - 图片高度建议 `100px` 到 `130px`。
  - 隐藏摘要。
  - 隐藏元素数量徽标。
  - 流程类型用顶部细色条或角标展示。
- 编辑模式下保留当前卡片信息。

#### 样式建议

- 总览节点减少阴影。
- 背景使用白色或极浅灰。
- 选中节点增加蓝色描边。
- 分支/异常/旁路使用不同色条。

#### 验收标准

- 总览模式一屏能显示更多节点。
- 节点视觉主体是截图。
- 节点标题可读。
- 不同流程类型可快速识别。

### 任务 1.3 优化连线视觉

#### 目标

让连线在总览模式下更轻、更像原型页面关系线。

#### 涉及文件

- `src/composables/useFlowEditor.ts`
- `src/components/case/FlowSortEditor.vue`

#### 实施内容

- 根据 `displayMode` 设置不同连线样式。
- 总览模式：
  - 主干线浅灰或浅蓝。
  - 分支线浅绿。
  - 异常线浅红虚线。
  - 旁路线浅黄点线。
  - 默认不动画。
- 编辑模式：保留现有较明显的流程编辑线条。

#### 验收标准

- 总览模式连线不抢占截图视觉。
- 编辑模式连线仍易于点击和识别。
- 不同类型连线仍可区分。

### 任务 1.4 默认适配全图

#### 目标

用户选择 UI 原型版本后，自动看到完整流程图。

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`

#### 实施内容

- 屏幕列表加载并生成节点后调用 `fitView`。
- 切换版本后重新适配视图。
- 自动布局后适配视图。

#### 注意事项

- 避免在用户手动拖动画布后频繁自动 `fitView`。
- 只在初始化、版本切换、自动布局后执行。

#### 验收标准

- 首次打开流程图能看到完整节点范围。
- 自动布局后能看到完整流程。
- 用户手动缩放时不会被频繁打断。

## 阶段二：布局能力优化

### 任务 2.1 优化自动布局算法

#### 目标

让流程布局更像参考图中的页面流，而不是简单横排。

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`
- 可选新增：`src/composables/useFlowLayout.ts`

#### 布局规则

- 主干节点：水平排列，位于 `y = 0`。
- 分支节点：放在挂靠主干下方。
- 异常节点：放在挂靠主干上方。
- 旁路节点：放在挂靠主干右下方。
- 同一主干下多个分支，按层级错开。
- 未挂靠节点放在画布左下角或单独区域。

#### 建议参数

```ts
const NODE_WIDTH = 190
const NODE_HEIGHT = 150
const MAIN_X_GAP = 260
const BRANCH_Y_GAP = 220
const BRANCH_X_GAP = 210
```

#### 验收标准

- 主干流程从左到右清晰排列。
- 分支不会全部堆在同一个 x/y。
- 异常流程和普通分支视觉上分层。
- 自动布局后不出现明显节点重叠。

### 任务 2.2 增加按类型布局

#### 目标

提供更快捷的布局选择。

#### 实施内容

工具栏自动布局按钮扩展为下拉菜单：

- 标准布局
- 紧凑布局
- 按类型分层
- 只整理当前路径

#### 验收标准

- 用户可选择不同布局方式。
- 每种布局执行后节点位置符合预期。
- 执行布局前保存历史，支持撤销。

### 任务 2.3 支持模块分组背景

#### 目标

在大量页面场景下，帮助用户按业务模块理解流程。

#### 实施内容

- 根据页面名称、模块信息或 `ui_spec` 推断模块。
- 在画布中渲染分组背景区域。
- 分组背景显示模块名称和节点数量。

#### 可选实现方式

- 使用 VueFlow 的 group node。
- 或自定义背景层，根据节点位置计算矩形区域。

#### 验收标准

- 同一模块节点有视觉分组。
- 分组背景不影响节点拖拽和连线。
- 分组显示可开关。

## 阶段三：查找、定位与路径高亮

### 任务 3.1 增加页面搜索定位

#### 目标

用户可以通过页面名称快速定位节点。

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`

#### 实施内容

- 工具栏增加搜索框。
- 支持按 `screen_name` 模糊搜索。
- 搜索结果以下拉列表展示。
- 点击结果后：
  - 选中节点
  - 居中节点
  - 临时高亮节点

#### 交互细节

- 输入关键词实时筛选。
- 按 Enter 定位第一个结果。
- 无结果时显示“未找到页面”。

#### 验收标准

- 可通过页面名定位节点。
- 定位后画布自动居中到目标节点。
- 节点高亮明显。

### 任务 3.2 点击节点高亮上下游路径

#### 目标

用户点击一个页面后，能看清它的来源和去向。

#### 实施内容

- 维护 `focusedNodeId`。
- 根据 edges 计算：
  - upstream node ids
  - downstream node ids
  - related edge ids
- 对相关节点和连线增加高亮样式。
- 非相关节点降低透明度。

#### 高亮规则

- 当前节点：蓝色高亮。
- 上游节点：紫色或浅蓝高亮。
- 下游节点：绿色高亮。
- 相关边：加粗。
- 无关节点：透明度 `0.35`。

#### 验收标准

- 点击节点后能看出上下游。
- 再次点击空白区域清除高亮。
- 高亮不影响拖拽和连线。

### 任务 3.3 连线悬浮显示条件

#### 目标

用户不用打开弹窗，也能快速知道跳转条件。

#### 实施内容

- 给边增加 label 或 tooltip。
- 鼠标悬浮连线时显示：
  - 流程类型
  - 触发条件
  - 前置操作
  - 备注

#### 验收标准

- 悬浮连线时可读到条件。
- 无条件连线显示“普通跳转”。
- tooltip 不遮挡主要节点。

## 阶段四：分支与流程编辑效率优化

### 任务 4.1 节点悬浮快捷操作

#### 目标

减少切换流程类型和预览图片的操作成本。

#### 涉及文件

- `src/components/case/FlowNodeCard.vue`

#### 实施内容

节点 hover 时显示快捷操作：

- 预览
- 设为主干
- 设为分支
- 设为异常
- 设为旁路

#### 交互要求

- 总览模式下只显示轻量按钮。
- 编辑模式下显示完整按钮。
- 点击分支/异常/旁路仍弹配置弹窗。

#### 验收标准

- 用户不必点开下拉菜单即可设置流程类型。
- hover 操作不影响节点拖拽。
- 快捷按钮有 tooltip。

### 任务 4.2 快速创建分支

#### 目标

提高从主干节点派生分支的效率。

#### 实施内容

- 选中主干节点后，工具栏显示“添加分支”。
- 点击后弹出页面选择器，选择目标页面。
- 自动创建分支边。
- 可选填写触发条件。

#### 验收标准

- 可从主干快速创建分支。
- 创建后目标节点自动切换为分支类型。
- 自动布局可将新分支放到合理位置。

### 任务 4.3 分支折叠/展开

#### 目标

复杂流程下减少视觉噪音。

#### 实施内容

- 主干节点显示分支数量。
- 点击折叠按钮隐藏该主干下的分支/异常/旁路节点。
- 再次点击展开。

#### 验收标准

- 折叠后节点和相关边隐藏。
- 展开后恢复原位置。
- 折叠状态不影响最终提交数据。

### 任务 4.4 批量设置流程类型

#### 目标

提升多页面整理效率。

#### 实施内容

- 多选节点后支持批量设为：
  - 主干
  - 分支
  - 异常
  - 旁路
- 非主干批量设置时，允许选择统一挂靠主干；未选择时系统应根据现有连线或最近主干自动推断。

#### 验收标准

- 多选节点可批量设置类型。
- 设置后边和元数据正确生成。
- 支持撤销。

## 阶段五：流程质量检查与生成前校验

### 任务 5.1 增加流程完整度面板

#### 目标

帮助用户在生成前发现流程问题。

#### 实施内容

在工具栏或右侧小面板显示：

- 总节点数
- 主干节点数
- 分支节点数
- 异常节点数
- 旁路节点数
- 未连线节点数
- 未填写条件且无法自动推断条件的分支数
- 是否存在主干断链

#### 验收标准

- 数据实时更新。
- 点击问题项可定位对应节点或连线。
- 与现有 `getFlowValidationIssues` 校验逻辑一致。

### 任务 5.2 生成前问题列表

#### 目标

把校验错误和警告以更友好的形式展示。

#### 实施内容

- 将当前 `ElMessageBox.confirm` 升级为问题列表弹窗。
- 结构性错误阻止生成；触发条件缺失只作为警告或自动推断项，不阻止生成。
- 警告允许继续生成。
- 每个问题支持“定位”。

#### 验收标准

- 缺少主干节点时阻止生成。
- 分支缺少条件时不阻止生成，系统应尝试根据页面名称、按钮文案、连线 label 或 UI 元素自动推断条件，并给出警告。
- 主干无连线时给出警告。
- 点击定位可跳转到相关节点或边。

### 任务 5.3 Prompt 预览可视化

#### 目标

让用户知道当前流程会如何影响 AI 生成。

#### 实施内容

- 替换当前控制台输出。
- 弹出 Prompt 数据预览窗口。
- 分区展示：
  - 主干流程
  - 分支流程
  - 异常流程
  - UI 元素摘要
  - 模块信息

#### 验收标准

- 用户无需打开浏览器控制台。
- 预览内容和实际提交内容一致。
- 支持复制 JSON。

## 阶段六：高级能力预留

### 任务 6.1 路径播放

#### 目标

用户可以从入口页开始逐步查看页面流程。

#### 实施内容

- 识别入口节点。
- 提供“开始播放”按钮。
- 每一步高亮当前节点和下一条连线。
- 支持上一页、下一页、退出播放。

#### 验收标准

- 可沿主干播放。
- 遇到分支时可选择分支路径。
- 播放过程中画布自动跟随。

### 任务 6.2 自动识别页面跳转关系

#### 目标

减少用户手动连线工作量。

#### 实施内容

- 根据 `ui_spec.elements` 中按钮、链接、文案推断跳转关系。
- 根据页面名称相似度推断目标页面。
- 生成建议连线。
- 用户确认后应用。

#### 验收标准

- 能生成候选连线。
- 用户可逐条接受或忽略。
- 不自动覆盖用户已有连线。

### 任务 6.3 与测试点联动

#### 目标

让流程图和测试点选择互相辅助。

#### 实施内容

- 选择测试点后高亮相关 UI 页面。
- 选择页面路径后推荐相关测试点。
- 生成用例时可按路径过滤 UI 上下文。

#### 验收标准

- 测试点和页面之间有关联提示。
- 不影响当前测试点选择逻辑。
- 生成接口仍兼容。

## 7. 推荐实施顺序

建议按以下顺序推进：

1. 总览/编辑模式切换。
2. 总览模式节点轻量化。
3. 连线视觉优化。
4. 自动布局优化。
5. 页面搜索定位。
6. 点击节点高亮上下游。
7. 连线悬浮条件展示。
8. 节点悬浮快捷操作。
9. 流程完整度面板。
10. 生成前问题列表。
11. 分支折叠/展开。
12. 模块分组背景。
13. 路径播放。
14. 自动识别页面跳转关系。
15. 测试点联动。

## 8. 里程碑拆分

### M1：接近参考图的视觉总览

包含任务：

- 1.1 总览/编辑模式切换
- 1.2 总览模式节点样式
- 1.3 连线视觉优化
- 1.4 默认适配全图
- 2.1 自动布局算法优化

完成后效果：

- 一屏可看到更多原型页面。
- 页面缩略图成为视觉主体。
- 主干和分支布局更清晰。

### M2：提升大流程浏览效率

包含任务：

- 3.1 页面搜索定位
- 3.2 点击节点高亮上下游路径
- 3.3 连线悬浮显示条件
- 4.3 分支折叠/展开

完成后效果：

- 大量页面也能快速查找。
- 能快速理解某页面的前后关系。
- 复杂分支可折叠。

### M3：提升编辑效率和生成前质量

包含任务：

- 4.1 节点悬浮快捷操作
- 4.2 快速创建分支
- 4.4 批量设置流程类型
- 5.1 流程完整度面板
- 5.2 生成前问题列表
- 5.3 Prompt 预览可视化

完成后效果：

- 整理流程更快。
- 生成前问题更清晰。
- AI 输入数据更可控。

### M4：高级智能化能力

包含任务：

- 6.1 路径播放
- 6.2 自动识别页面跳转关系
- 6.3 与测试点联动

完成后效果：

- 用户可以按路径浏览原型。
- 系统能辅助生成跳转关系。
- 测试点和页面流程形成闭环。

## 9. 测试清单

### 9.1 功能测试

- 切换 UI 原型版本后，节点正确刷新。
- 切换总览/编辑模式后，节点和连线不丢失。
- 节点拖拽后位置保持。
- 自动布局后节点不明显重叠。
- 搜索页面后能定位节点。
- 点击节点后上下游高亮正确。
- 空白区域点击后高亮清除。
- 分支配置后自动生成连线。
- 删除节点后相关边同步删除。
- 撤销能恢复节点和边。
- 生成时提交的 `flow_sort_data` 正确。

### 9.2 UI 测试

- 总览模式节点缩略图清晰。
- 编辑模式节点信息完整。
- 图例颜色与节点/连线颜色一致。
- 小屏幕下工具栏可换行。
- 大量节点下画布不卡顿。
- tooltip 不遮挡核心操作。

### 9.3 回归测试

- 不选择 UI 原型图时仍可生成测试用例。
- 只选择需求文档时生成逻辑不受影响。
- 只选择测试点时生成逻辑不受影响。
- 原有分支/异常/旁路提交结构不变。
- 现有测试点选择器不受影响。

### 9.4 性能测试

建议覆盖节点数量：

- 10 个节点
- 30 个节点
- 50 个节点
- 100 个节点

关注指标：

- 首次渲染耗时。
- 拖拽流畅度。
- 搜索响应速度。
- 自动布局耗时。
- 高亮路径响应速度。

## 10. 风险与注意事项

### 10.1 VueFlow 事件兼容风险

不同版本的 `@vue-flow/core` 对事件参数可能存在差异。

处理建议：

- 所有事件参数做空值保护。
- 使用当前项目锁定版本进行验证。
- 避免依赖非公开 API。

### 10.2 节点过多导致性能下降

大量缩略图会带来渲染压力。

处理建议：

- 总览模式降低图片尺寸。
- 图片使用懒加载。
- 非可视区域可考虑虚拟化或降低渲染复杂度。
- 节点 hover 动效不要过重。

### 10.3 自动布局覆盖用户手动调整

用户手动排版后可能不希望自动布局覆盖。

处理建议：

- 自动布局必须由用户主动触发。
- 执行前保存历史，支持撤销。
- 可提示“将重新排列当前节点”。

### 10.4 新状态污染提交数据

总览模式、折叠状态、搜索高亮不应影响 AI 生成。

处理建议：

- UI 状态默认不进入 `flow_sort_data`。
- 如需保存，放到独立可选字段。
- 生成前只读取业务字段。

## 11. 建议验收口径

最终优化完成后，应达到以下效果：

- 从视觉上，流程图接近参考图中的产品原型流图。
- 从操作上，用户可以快速浏览、定位、拖拽、连线、配置分支。
- 从业务上，生成接口可以拿到清晰的主干、分支、异常、旁路结构。
- 从稳定性上，不影响现有 AI 测试用例生成主流程。

## 12. 建议优先落地版本

如果只做第一版，建议拆成 M1A 和 M1B 两个小闭环，避免一次性范围过大。

### 12.1 M1A：前端可见体验闭环

优先完成：

1. 总览/编辑模式切换。
2. 总览模式节点轻量化。
3. 连线视觉优化。
4. 默认适配全图。
5. 搜索定位页面。

完成后用户能明显感知界面接近参考图中的原型流总览效果。

### 12.2 M1B：流程语义增强闭环

在 M1A 稳定后继续完成：

1. 自动布局优化。
2. 后端 graph prompt 嵌套结构增强。
3. `flow_meta` 利用增强。
4. graph prompt 单元测试。
5. 基础后端流程结构校验。

完成后 AI 接收到的流程结构更接近思维导图语义。

### 12.3 M2：浏览和质量增强

后续再完成：

1. 点击节点高亮上下游路径。
2. 连线悬浮条件展示。
3. 分支折叠/展开。
4. 流程完整度面板。
5. 生成前问题列表。

不建议将 M2 内容并入 M1，避免第一版范围失控。

## 13. 用户角色与核心场景

### 13.1 用户角色

#### 测试人员

主要目标：

- 快速理解 UI 原型页面之间的跳转关系。
- 将主干、分支、异常、旁路流程整理成结构化数据。
- 基于整理后的流程生成更准确的测试用例。

关注点：

- 操作是否简单。
- 页面是否容易查找。
- 分支条件是否容易维护。
- 生成前是否能发现流程缺失。

#### 测试负责人

主要目标：

- 评估流程图是否覆盖核心业务路径。
- 检查是否存在未连线页面、断链主干、无法推断触发条件的分支。
- 确认 AI 生成测试用例的上下文输入是否完整。

关注点：

- 流程完整度。
- 异常路径覆盖。
- 生成前质量检查。
- 结果可追溯性。

#### 产品或业务人员

主要目标：

- 以原型流图方式查看页面结构。
- 快速理解页面之间的业务流转。
- 辅助测试人员确认流程是否符合业务预期。

关注点：

- 总览是否清晰。
- 页面缩略图是否直观。
- 路径关系是否容易理解。

### 13.2 核心使用场景

#### 场景一：上传 UI 原型后快速浏览整体流程

用户选择 UI 原型图版本后，希望立即看到类似参考图的页面流程总览。

期望行为：

- 默认进入总览模式。
- 自动适配全图。
- 节点以缩略图为主体展示。
- 主干和分支关系可直观看到。

#### 场景二：整理主干流程和分支流程

用户需要把多个 UI 页面整理成主干路径，并把部分页面标记为分支、异常或旁路。

期望行为：

- 可通过节点快捷操作切换流程类型。
- 切换为分支/异常/旁路时建议选择挂靠主干；未选择时系统应根据连线或节点位置自动推断。
- 自动生成对应语义连线。
- 分支条件可编辑。

#### 场景三：大量页面中快速定位某个页面

用户面对几十个 UI 页面，需要快速找到某个页面并查看上下游。

期望行为：

- 可通过页面名称搜索。
- 搜索结果可点击定位。
- 定位后节点居中并高亮。
- 可继续查看上游和下游路径。

#### 场景四：生成测试用例前检查流程完整性

用户准备生成测试用例前，需要确认流程图没有明显缺失。

期望行为：

- 显示未连线节点数量。
- 显示未填写且无法自动推断条件的分支数量。
- 显示主干是否断链。
- 问题项可点击定位。
- 结构性错误阻止生成；缺少人工触发条件只提示，不阻止生成，系统优先自动推断或降级为通用条件。

#### 场景五：只按某条路径生成测试用例

用户只关注某条主干或某个分支路径，希望后续能按路径过滤 UI 上下文。

期望行为：

- 可点击节点查看相关路径。
- 可选择一条路径作为上下文。
- 后续生成接口可扩展支持路径级上下文。

## 14. 非目标范围

为避免第一版范围失控，需明确以下内容不在 M1 范围内。

### 14.1 M1 不做的内容

- 不做后端布局持久化。
- 不新增或修改生成接口字段。
- 不改变现有 `flow_sort_data` 字段语义。
- 不做自动识别页面跳转关系。
- 不做路径播放。
- 不做测试点与 UI 页面自动联动。
- 不做跨用户共享流程布局。
- 不做复杂模块分组编辑。
- 不做多版本流程差异对比。

### 14.2 M1 必须保证的内容

- 不破坏现有 AI 生成测试用例链路。
- 不破坏现有 UI 原型图版本选择逻辑。
- 不破坏现有测试点选择逻辑。
- 不影响不选择 UI 原型图时的生成流程。
- 所有新增 UI 状态默认不提交给生成接口。

### 14.3 后续版本再考虑的内容

- 布局保存到后端。
- 自动推断页面跳转关系。
- 路径播放。
- 模块分组背景。
- 分支折叠状态持久化。
- 按路径生成测试用例。
- 页面流程与测试点双向推荐。

## 15. 数据状态与保存策略

### 15.1 状态分层原则

流程编辑器需要区分三类状态：

#### 业务提交状态

会进入 `flow_sort_data`，用于 AI 生成测试用例。

包括：

- 节点对应的 `screen_id`
- 节点流程类型 `flow_type`
- 主干顺序 `main_order`
- 分支/异常/旁路元数据 `flow_meta`，其中触发条件类字段为可选增强信息
- 连线 source/target
- 连线类型 `edge_type`
- 连线条件 `condition`，可为空；为空时后端应尝试自动推断或使用安全默认描述

#### 画布布局状态

用于展示和编辑体验。

包括：

- 节点坐标 `position`
- 节点是否手动拖拽过
- 自动布局策略
- 当前缩放和平移状态

#### 临时 UI 状态

只影响当前交互，不应提交给生成接口。

包括：

- 当前显示模式 `displayMode`
- 当前搜索关键词 `searchKeyword`
- 当前聚焦节点 `focusedNodeId`
- 当前高亮节点集合
- 当前高亮边集合
- 当前折叠节点集合

### 15.2 推荐类型定义

```ts
type FlowEditorDisplayMode = 'overview' | 'edit'

type FlowEditorViewState = {
  displayMode: FlowEditorDisplayMode
  focusedNodeId?: string
  searchKeyword: string
  collapsedParentNodeIds: string[]
}

type FlowNodeViewMeta = {
  groupName?: string
  manualPosition?: boolean
  lastLayoutStrategy?: string
}
```

### 15.3 提交边界

短期规则：

- `FlowEditorViewState` 不提交给生成接口。
- `FlowNodeViewMeta` 不提交给生成接口。
- `position` 可继续作为前端编辑状态存在，但不作为 AI 生成判断依据。
- AI 生成只读取节点、边和流程语义字段。

后续如果需要保存布局，应新增独立接口或独立字段，不应混入 AI 生成所需语义字段。

### 15.4 布局保存策略

#### M1 策略：仅前端内存保存

规则：

- 用户在当前页面调整的节点位置仅当前会话有效。
- 切换步骤时尽量保持组件状态。
- 切换 UI 原型版本时重置布局。
- 刷新页面后不保证恢复布局。

优点：

- 不需要后端改造。
- 风险低。
- 适合快速验证交互价值。

#### M2/M3 策略：考虑后端保存

如果用户对布局保存有强需求，再考虑：

- 新增流程布局保存接口。
- 按 `prototype_project_id` 保存布局。
- 按用户维度保存个人布局。
- 保存节点 position、layout strategy、group 信息。

## 16. 任务优先级、复杂度与依赖关系

### 16.1 优先级定义

- P0：第一版必须完成，直接影响核心体验。
- P1：重要增强，建议在第二阶段完成。
- P2：高级能力，可后置。

### 16.2 复杂度定义

- S：半天到 1 天。
- M：1 到 2 天。
- L：3 到 5 天。
- XL：超过 1 周或涉及较大不确定性。

### 16.3 任务评估表

| 任务 | 优先级 | 复杂度 | 风险 | 是否需后端 | 是否影响生成链路 | 主要依赖 |
|---|---|---:|---|---|---|---|
| 1.1 总览/编辑模式切换 | P0 | M | 中 | 否 | 否 | 无 |
| 1.2 总览模式节点样式 | P0 | M | 低 | 否 | 否 | 1.1 |
| 1.3 连线视觉优化 | P0 | M | 中 | 否 | 否 | 1.1 |
| 1.4 默认适配全图 | P0 | S | 低 | 否 | 否 | 1.1 |
| 2.1 自动布局算法优化 | P0 | L | 中 | 否 | 间接 | 1.1、1.2 |
| 2.2 增加按类型布局 | P1 | M | 中 | 否 | 否 | 2.1 |
| 2.3 模块分组背景 | P2 | L | 中 | 否 | 否 | 2.1 |
| 3.1 页面搜索定位 | P0 | M | 低 | 否 | 否 | 1.1 |
| 3.2 点击节点高亮上下游 | P1 | M | 中 | 否 | 否 | edges 数据稳定 |
| 3.3 连线悬浮显示条件 | P1 | S | 低 | 否 | 否 | 1.3 |
| 4.1 节点悬浮快捷操作 | P1 | M | 中 | 否 | 间接 | 1.2 |
| 4.2 快速创建分支 | P1 | L | 中 | 否 | 是 | 4.1、边生成逻辑 |
| 4.3 分支折叠/展开 | P1 | L | 中 | 否 | 否 | 3.2 |
| 4.4 批量设置流程类型 | P2 | L | 高 | 否 | 是 | 多选稳定 |
| 5.1 流程完整度面板 | P1 | M | 中 | 否 | 是 | 校验逻辑抽取 |
| 5.2 生成前问题列表 | P1 | M | 中 | 否 | 是 | 5.1 |
| 5.3 Prompt 预览可视化 | P1 | M | 低 | 否 | 否 | 提交数据稳定 |
| 6.1 路径播放 | P2 | L | 中 | 否 | 否 | 3.2 |
| 6.2 自动识别页面跳转关系 | P2 | XL | 高 | 可能 | 是 | UI 解析质量 |
| 6.3 与测试点联动 | P2 | XL | 高 | 可能 | 是 | 测试点与页面关联 |

### 16.4 推荐 M1A/M1B 最小闭环

M1A 建议只包含前端可见体验：

1. 总览/编辑模式切换。
2. 总览模式节点轻量化。
3. 连线视觉优化。
4. 默认适配全图。
5. 页面搜索定位。

M1B 建议只包含流程语义增强：

1. 自动布局算法优化。
2. 后端 graph prompt 嵌套结构增强。
3. `flow_meta` 利用增强。
4. graph prompt 单元测试。
5. 基础后端流程结构校验。

不建议 M1A/M1B 纳入：

- 模块分组背景。
- 分支折叠。
- 批量设置流程类型。
- 路径播放。
- 自动识别跳转。
- 测试点联动。
- Prompt 预览接口。

## 17. 量化验收标准

### 17.1 总览模式验收标准

- 节点宽度控制在 `160px` 到 `190px`。
- 截图区域高度占节点整体高度的 `70%` 以上。
- 总览模式默认隐藏摘要和元素统计。
- 1920x1080 分辨率下，30 个以内节点经过适配视图后应能看到主流程全貌。
- 节点标题超长时必须省略展示，并支持 tooltip 查看完整名称。

### 17.2 编辑模式验收标准

- 编辑模式保留流程类型切换入口。
- 编辑模式保留图片预览入口。
- 编辑模式保留摘要、元素数量等辅助信息。
- 切换模式后节点类型、连线、位置不丢失。

### 17.3 连线验收标准

- 总览模式连线宽度建议 `1px` 到 `1.5px`。
- 编辑模式连线宽度建议 `2px`。
- 分支、异常、旁路至少通过颜色或线型之一与主干区分。
- 连线 label 不应大面积遮挡缩略图。

### 17.4 自动布局验收标准

- 主干节点必须按 `main_order` 从左到右排列。
- 分支节点必须优先挂靠到 `flow_meta.parent_main_node_id` 对应主干下方。
- 异常节点必须优先放置在挂靠主干上方。
- 旁路节点必须优先放置在挂靠主干右下方。
- 30 个节点以内自动布局耗时建议小于 `500ms`。
- 100 个节点以内自动布局耗时建议小于 `1500ms`。
- 任意两个可见节点的重叠面积不应超过较小节点面积的 `10%`。

### 17.5 搜索定位验收标准

- 支持按 `screen_name` 模糊搜索。
- 输入关键词后 `300ms` 内展示搜索结果。
- 点击搜索结果后，目标节点应进入当前视口中心 `±20%` 区域。
- 搜索无结果时展示明确空状态。

### 17.6 高亮路径验收标准

- 点击节点后，当前节点、上游节点、下游节点视觉区分明确。
- 相关边加粗或高亮。
- 无关节点透明度降低到 `0.3` 到 `0.5`。
- 点击画布空白区域后恢复默认状态。

### 17.7 生成链路验收标准

- 不选择 UI 原型图时仍可正常生成测试用例。
- 仅选择需求文档时仍可正常生成测试用例。
- 仅选择测试点时仍可正常生成测试用例。
- 选择 UI 原型图并编辑流程后，`flow_sort_data` 包含正确 nodes 和 edges。
- 总览模式、搜索关键词、高亮状态、折叠状态不进入生成接口。

## 18. 交互边界与异常状态

### 18.1 空状态

#### 未选择项目

展示提示：

- 请先选择项目。
- 选择项目后可加载需求文档和 UI 原型图。

#### 未选择 UI 原型图版本

展示提示：

- 请选择 UI 原型图版本。
- 如无版本，请前往资源管理上传 UI 原型图。

#### 当前版本无屏幕

展示提示：

- 当前 UI 原型图版本暂无屏幕。
- 可刷新或重新上传原型图。

### 18.2 加载状态

需要覆盖：

- UI 原型版本加载中。
- 屏幕列表加载中。
- 缩略图加载中。
- 自动布局执行中。
- 搜索定位执行中。

要求：

- 长耗时操作需有 loading。
- 不允许用户在关键状态未加载完成时误触生成。

### 18.3 错误状态

#### 图片加载失败

处理方式：

- 节点展示默认占位图。
- 保留页面名称和流程类型。
- 不影响节点拖拽、连线和生成。

#### 页面名称为空

处理方式：

- 显示 `未命名页面#screen_id`。
- 生成前给出警告。

#### 连线目标节点已删除

处理方式：

- 删除节点时同步删除相关边。
- 校验时忽略孤立边或提示数据异常。

#### 自动布局失败

处理方式：

- 保持原有节点位置。
- 给出错误提示。
- 不清空用户已有编辑。

#### 搜索无结果

处理方式：

- 展示“未找到匹配页面”。
- 不改变当前节点选择。

### 18.4 操作冲突状态

#### 拖拽节点时点击按钮

处理要求：

- 节点内按钮应阻止事件冒泡。
- 避免触发画布拖拽。

#### 总览模式下编辑流程类型

处理建议：

- 可以允许轻量编辑。
- 如果操作需要填写复杂信息，可自动切换到编辑模式。

#### 折叠状态下搜索隐藏节点

处理建议：

- 搜索结果应包含隐藏节点。
- 点击隐藏节点时自动展开其父节点并定位。

## 19. 技术拆分建议

### 19.1 当前风险

`FlowSortEditor.vue` 已经承担较多职责：

- 工具栏展示。
- VueFlow 画布渲染。
- 节点和边状态管理。
- 历史栈。
- 自动布局。
- 校验。
- Prompt 数据导出。
- 快捷键。

继续直接堆功能会导致组件复杂度过高，后续维护困难。

### 19.2 建议组件拆分

#### FlowToolbar.vue

职责：

- 总览/编辑模式切换。
- 自动布局按钮。
- 搜索入口。
- 缩放和适配视图入口。
- Prompt 预览入口。

#### FlowSearchBox.vue

职责：

- 页面名称搜索。
- 搜索结果列表。
- Enter 定位。
- 无结果展示。

#### FlowStatsPanel.vue

职责：

- 节点数量统计。
- 分支数量统计。
- 未连线数量统计。
- 主干断链提示。
- 问题点击定位。

#### FlowPromptPreviewDialog.vue

职责：

- 展示实际提交给 AI 的流程数据。
- 支持复制 JSON。
- 按主干、分支、异常、旁路分区展示。

#### FlowIssueDialog.vue

职责：

- 生成前错误和警告列表。
- 支持继续生成或返回修改。
- 支持定位问题节点或连线。

### 19.3 建议 composable 拆分

#### useFlowLayout.ts

职责：

- 标准布局。
- 紧凑布局。
- 按类型分层布局。
- 节点重叠检测。

#### useFlowHighlight.ts

职责：

- 计算上游节点。
- 计算下游节点。
- 计算相关边。
- 输出高亮和弱化样式状态。

#### useFlowSearch.ts

职责：

- 搜索关键词状态。
- 搜索结果计算。
- 节点定位。

#### useFlowValidation.ts

职责：

- 校验主干节点。
- 校验主干连线。
- 校验分支条件。
- 输出错误和警告。

#### useFlowSubmitData.ts

职责：

- 从 VueFlow nodes/edges 生成 `flow_sort_data`。
- 保证提交数据不包含临时 UI 状态。

### 19.4 Store 边界建议

`useGenerateStore.ts` 继续负责：

- 项目选择。
- UI 原型图版本列表。
- 屏幕列表。
- 测试点列表。
- 生成请求。

不建议放入 `useGenerateStore.ts` 的内容：

- 当前画布缩放。
- 搜索关键词。
- 当前高亮节点。
- 当前折叠节点。
- 节点 hover 状态。

这些状态应留在 `FlowSortEditor.vue` 或对应 composable 中。

## 20. 详细完成定义 DoD

### 20.1 M1A 完成定义

M1A 完成必须满足：

- 支持总览/编辑模式切换。
- 总览模式节点轻量化完成。
- 总览模式连线视觉完成。
- 选择 UI 原型版本后默认适配全图。
- 支持按页面名称搜索定位。
- 生成接口提交数据不受模式、搜索、高亮状态影响。
- 不选择 UI 原型图时生成流程不受影响。

### 20.1.1 M1B 完成定义

M1B 完成必须满足：

- 自动布局按主干、分支、异常、旁路分层。
- 后端 graph prompt 支持嵌套流程结构。
- 后端 graph prompt 能利用 `flow_meta` 可选增强信息。
- 缺少人工触发条件时能自动推断或使用默认描述。
- graph prompt 单元测试覆盖主干、分支、异常、旁路和无效边容错。
- 不改变现有生成接口结构。

### 20.2 代码质量要求

- 新增逻辑优先拆入 composable 或子组件。
- 避免继续让 `FlowSortEditor.vue` 无限制膨胀。
- 新增类型必须显式定义。
- 关键事件参数必须做空值保护。
- 避免在模板中写复杂计算逻辑。

### 20.3 测试要求

M1A 至少覆盖：

- 手工测试：10 个节点、30 个节点、50 个节点。
- 总览/编辑模式切换测试。
- 搜索定位测试。
- 生成前提交数据检查。
- 不选择 UI 原型图的回归测试。

M1B 至少覆盖：

- 自动布局测试。
- graph prompt 构建单元测试。
- 分支/异常/旁路条件缺失时的自动推断测试。
- 无效 edge 容错测试。

建议补充组件测试：

- `useFlowLayout`
- `useFlowSearch`
- `useFlowValidation`
- `FlowNodeCard` 双模式展示

### 20.4 验收要求

- 产品验收：M1A 视觉接近参考图的页面流总览效果。
- 测试验收：核心流程和回归场景通过。
- 技术验收：不破坏现有生成接口和数据结构。
- 性能验收：50 个节点内操作流畅，无明显卡顿。

## 21. M1A/M1B 详细执行清单

### 21.1 开发前准备

- 确认参考图中的目标视觉风格。
- 确认 M1 不做后端布局保存。
- 确认不修改生成接口结构。
- 准备至少 3 组测试数据：
  - 10 个页面以内。
  - 30 个页面左右。
  - 50 个页面以上。

### 21.2 M1A 开发任务顺序

1. 抽取或整理节点显示模式类型。
2. 实现总览/编辑模式切换。
3. 改造 `FlowNodeCard` 支持双模式。
4. 改造连线样式以适配总览模式。
5. 实现初始化和自动布局后的 `fitView`。
6. 实现页面搜索定位。
7. 检查 `flow_sort_data` 提交边界。
8. 完成手工回归测试。

### 21.3 M1B 开发任务顺序

1. 抽取 `useFlowLayout`。
2. 实现主干、分支、异常、旁路分层布局。
3. 增强后端 graph prompt 嵌套结构。
4. 增强 `flow_meta` 利用与触发条件自动推断。
5. 增加 graph prompt 单元测试。
6. 增加基础后端流程结构校验。
7. 完成前后端联调。

### 21.4 M1A/M1B 交付物

- 代码改动。
- 简短交互说明。
- 回归测试结果。
- 如有必要，补充截图或录屏。

## 22. 文档维护要求

本实施文档后续应随开发进展更新：

- 任务完成后标记状态。
- 需求范围变化时更新非目标范围。
- 数据结构变化时更新第 5 节和第 15 节。
- 发现新风险时补充第 10 节。
- M1 完成后复盘实际耗时和遗留问题。

## 23. 后端流程图 Prompt 支持现状

### 23.1 当前链路

当前后端已经具备流程图模式的 Prompt 构建能力。

链路如下：

```text
前端 FlowSortEditor
  ↓
flow_sort_data: nodes + edges + module_info
  ↓
增强生成接口 mode=graph
  ↓
_build_graph_prompt_data()
  ↓
PromptBuilder.build_graph_prompt()
  ↓
graph_prompt
  ↓
generate_test_case_enhanced()
  ↓
AI
```

关键文件：

- `app/api/v1/endpoints/test_case_ai_generate.py`
- `app/api/v1/endpoints/test_case_ai.py`
- `app/services/case_generation_prompt_builder.py`
- `app/services/prompt_builder/case_prompt.py`
- `app/utils/ai_client_enhanced.py`
- `app/schemas/test_case.py`

### 23.2 当前支持能力

后端在请求满足以下条件时进入流程图模式：

```json
{
  "mode": "graph",
  "flow_sort_data": {
    "nodes": [],
    "edges": [],
    "module_info": {}
  }
}
```

后端会将 `flow_sort_data` 转换为 `graph_prompt`，并在 AI 调用时优先使用：

```python
graph_prompt = context.get('graph_prompt')
if graph_prompt:
    prompt = graph_prompt
```

Prompt 当前已经分区表达：

- 主干流程
- 分支流程
- 异常流程
- 旁路流程
- 生成要求
- 正反用例对比
- 输出 JSON 格式

### 23.3 当前不足

当前能力已经可用，但还不是最强的“思维导图式嵌套结构”。

不足包括：

- Prompt 是分区文本，不是严格嵌套树结构。
- 分支、异常、旁路主要基于 edges 渲染，未形成完整路径树。
- `flow_meta.expected_result`、`bypass_reason`、`note` 等信息利用不充分。
- 没有专门的后端单元测试校验 graph prompt 的结构完整性。
- 没有独立的 Prompt 预览接口，前端只能通过控制台或生成过程间接验证。
- 没有对断链、孤立节点、无效边进行完整后端校验。

### 23.4 后端增强目标

后端增强的目标不是替代前端流程编辑，而是确保 AI 接收到的信息真正具备“流程图/思维导图语义”。

增强后应达到：

- AI 能清楚理解主干路径。
- AI 能清楚理解每个主干步骤下挂载的分支、异常、旁路。
- AI 能区分主流程用例、分支用例、异常用例、旁路用例。
- AI 能利用 UI 元素、需求文档、测试点、流程条件共同生成测试用例。
- 后端能校验前端提交的流程结构是否可用。

## 24. M1A/M1B 可直接执行实施方案

本节为开发落地方案，按任务顺序描述具体文件、实现步骤和验收方式。

### 24.1 M1A/M1B 范围

M1A 目标：

- 前端体验接近参考图中的原型流总览。
- 保持现有生成接口兼容。

M1A 包含：

1. 总览/编辑模式切换。
2. 总览模式节点轻量化。
3. 连线视觉优化。
4. 默认适配全图。
5. 页面搜索定位。

M1B 目标：

- 前端自动布局更符合主干/分支/异常/旁路分层关系。
- 后端 Prompt 明确按主干/分支/异常/旁路结构传给 AI。
- 保持现有生成接口兼容。

M1B 包含：

1. 自动布局算法优化。
2. 后端 graph prompt 增强。
3. `flow_meta` 利用增强。
4. graph prompt 单元测试。
5. 基础后端流程结构校验。

M1A/M1B 不包含：

- 后端布局持久化。
- 自动识别跳转关系。
- 路径播放。
- 测试点与页面自动联动。
- 多用户协同。
- Prompt 预览接口。

## 25. 前端实施方案

### 25.1 任务 FE-01：总览/编辑模式切换

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`
- `src/components/case/FlowNodeCard.vue`

#### 实施步骤

1. 在 `FlowSortEditor.vue` 中新增状态：

```ts
const displayMode = ref<'overview' | 'edit'>('overview')
```

2. 工具栏增加模式切换控件：

```vue
<el-radio-group v-model=\"displayMode\" size=\"small\">
  <el-radio-button label=\"overview\">总览</el-radio-button>
  <el-radio-button label=\"edit\">编辑</el-radio-button>
</el-radio-group>
```

3. 将 `displayMode` 传给节点组件：

```vue
<FlowNodeCard
  :data=\"nodeProps.data\"
  :display-mode=\"displayMode\"
/>
```

4. `FlowNodeCard.vue` 新增 prop：

```ts
displayMode?: 'overview' | 'edit'
```

5. 根据模式切换 class：

```vue
<div :class=\"['flow-node-card', `mode-${displayMode}`]\">
```

#### 验收标准

- 默认进入总览模式。
- 可以手动切换编辑模式。
- 切换模式后节点、连线、位置不丢失。
- 切换模式不影响 `flow_sort_data`。

### 25.2 任务 FE-02：总览模式节点轻量化

#### 涉及文件

- `src/components/case/FlowNodeCard.vue`

#### 实施步骤

1. 总览模式隐藏以下内容：

- 摘要。
- 元素数量徽标。
- 大面积 header 操作区。

2. 总览模式保留：

- 页面截图。
- 页面名称。
- 流程类型色条。
- 选中态。
- hover 预览提示。

3. 样式建议：

```scss
.flow-node-card.mode-overview {
  width: 180px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);

  .node-header {
    height: 4px;
    padding: 0;
  }

  .node-image {
    height: 112px;
  }

  .node-footer {
    padding: 6px 8px;
  }

  .screen-summary,
  .element-badges {
    display: none;
  }
}
```

4. 根据流程类型设置顶部色条：

- 主干：蓝色。
- 分支：绿色。
- 异常：红色。
- 旁路：黄色。

#### 验收标准

- 截图区域占节点高度 70% 以上。
- 1920x1080 下 30 个节点以内可看到主流程全貌。
- 节点标题超长省略展示。

### 25.3 任务 FE-03：连线视觉优化

#### 涉及文件

- `src/composables/useFlowEditor.ts`
- `src/components/case/FlowSortEditor.vue`

#### 实施步骤

1. 保留现有 `EDGE_STYLES`，新增总览模式样式：

```ts
export const OVERVIEW_EDGE_STYLES = {
  normal: { stroke: '#b8c2cc', strokeWidth: 1.2 },
  branch: { stroke: '#95d475', strokeWidth: 1.2 },
  exception: { stroke: '#f3a6a6', strokeWidth: 1.2, strokeDasharray: '5 5' },
  bypass: { stroke: '#eebe77', strokeWidth: 1.2, strokeDasharray: '3 3' },
}
```

2. 在 `FlowSortEditor.vue` 中根据 `displayMode` 归一化边样式。

3. 总览模式默认关闭动画。

4. 编辑模式保留当前更明显的连线。

#### 验收标准

- 总览模式连线不抢视觉。
- 编辑模式连线仍可点击和识别。
- 分支、异常、旁路可区分。

### 25.4 任务 FE-04：默认适配全图

#### 涉及文件

- `src/components/case/FlowSortEditor.vue`

#### 实施步骤

1. 从 `useVueFlow()` 获取 `fitView`：

```ts
const { fitView } = useVueFlow()
```

2. 在节点初始化后调用：

```ts
setTimeout(() => {
  void fitView({ duration: 220, padding: 0.15 })
}, 0)
```

3. 在自动布局完成后调用 `fitView`。

4. 避免每次 props 更新都触发 `fitView`，只在以下情况触发：

- 首次加载。
- UI 原型版本切换。
- 用户点击自动布局。
- 用户点击适配视图按钮。

#### 验收标准

- 首次选择 UI 原型版本后能看到完整流程范围。
- 自动布局后自动适配。
- 用户手动缩放后不会被频繁重置。

### 25.5 任务 FE-05：自动布局算法优化

#### 建议新增文件

- `src/composables/useFlowLayout.ts`

#### 输入输出

输入：

```ts
type LayoutInput = {
  nodes: FlowEditorNode[]
  edges: Edge[]
  mode: 'standard' | 'compact'
}
```

输出：

```ts
type LayoutOutput = FlowEditorNode[]
```

#### 布局规则

1. 主干节点：

- 按 `main_order` 排序。
- 水平排列。
- 坐标从 `(0, 0)` 开始。

2. 分支节点：

- 优先读取 `flow_meta.parent_main_node_id`。
- 找不到时通过入边 `source` 判断父节点。
- 放到父节点下方。

3. 异常节点：

- 放到父节点上方。

4. 旁路节点：

- 放到父节点右下方。

5. 未归类节点：

- 放到主流程下方单独区域。

#### 参考实现伪代码

```ts
export function layoutFlowNodes(nodes: FlowEditorNode[], edges: Edge[]) {
  const mainNodes = getMainNodesInOrder(nodes)
  const nextNodes = [...nodes]
  const positionMap = new Map<string, { x: number; y: number }>()

  mainNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * 260, y: 0 })
  })

  const childrenByParent = groupChildrenByParent(nodes, edges)

  for (const [parentId, children] of childrenByParent.entries()) {
    const parentPosition = positionMap.get(parentId)
    if (!parentPosition) continue

    const branches = children.filter(isBranch)
    const exceptions = children.filter(isException)
    const bypasses = children.filter(isBypass)

    branches.forEach((node, index) => {
      positionMap.set(node.id, {
        x: parentPosition.x + index * 210,
        y: parentPosition.y + 220,
      })
    })

    exceptions.forEach((node, index) => {
      positionMap.set(node.id, {
        x: parentPosition.x + index * 210,
        y: parentPosition.y - 220,
      })
    })

    bypasses.forEach((node, index) => {
      positionMap.set(node.id, {
        x: parentPosition.x + 180 + index * 210,
        y: parentPosition.y + 180,
      })
    })
  }

  return nextNodes.map((node) => ({
    ...node,
    position: positionMap.get(node.id) || node.position,
  }))
}
```

#### 验收标准

- 主干从左到右排列。
- 分支、异常、旁路分层展示。
- 30 个节点内无明显重叠。
- 执行前保存历史，可撤销。

### 25.6 任务 FE-06：页面搜索定位

#### 建议新增文件

- `src/components/case/FlowSearchBox.vue`
- 或 `src/composables/useFlowSearch.ts`

#### 实施步骤

1. 工具栏增加搜索框。

2. 搜索字段：

```ts
const searchKeyword = ref('')
```

3. 搜索目标：

- `screen_name`
- 可选：`summary`

4. 搜索结果点击后：

- 设置选中节点。
- 调用 `setCenter` 或 `fitView` 定位节点。
- 临时高亮目标节点。

5. 无结果显示：

```text
未找到匹配页面
```

#### 验收标准

- 输入关键词 300ms 内展示结果。
- 点击结果后节点进入视口中心。
- 搜索无结果有明确提示。

## 26. 后端实施方案

### 26.1 任务 BE-01：增强 graph prompt 为嵌套流程结构

#### 涉及文件

- `app/services/prompt_builder/case_prompt.py`
- `app/services/case_generation_prompt_builder.py`

#### 目标

将现有分区式 Prompt 增强为更接近思维导图的嵌套结构。

#### 兼容策略

M1B 不直接删除现有分区式 Prompt。推荐采用“新增嵌套视图 + 保留流程类型摘要”的兼容方式。

增强后 Prompt 建议包含：

1. `UI 原型图流程结构（嵌套视图）`
2. `流程类型摘要`
3. `生成要求`
4. `正反用例对比`
5. `输出 JSON 格式`

这样既能让 AI 理解每个主干步骤下挂载的分支、异常、旁路，也能保留现有按类型汇总的稳定表达，降低 Prompt 改造对生成质量的影响。

当前结构：

```text
主干流程
分支流程
异常流程
旁路流程
```

目标结构：

```text
主干步骤 1：页面A
  ├─ 分支：页面B，条件：xxx
  ├─ 异常：页面C，场景：xxx
  └─ 旁路：页面D，出现时机：xxx
主干步骤 2：页面E
  ├─ 分支：页面F，条件：xxx
```

#### 实施步骤

1. 新增流程树构建函数：

```python
def _build_nested_flow_structure(nodes, edges):
    ...
```

2. 构建 `node_map`：

```python
node_map = {n.get('screen_id'): n for n in nodes}
```

3. 获取主干节点：

```python
main_nodes = sorted(
    [n for n in nodes if n.get('flow_type') == 'main'],
    key=lambda n: (
        n.get('main_order') or n.get('screen_order', 0),
        n.get('screen_order', 0),
    )
)
```

4. 将 edges 按 source 分组：

```python
edges_by_source = {}
for edge in edges:
    edges_by_source.setdefault(str(edge.get('source')), []).append(edge)
```

5. 每个主干节点下挂载相关边：

```python
for main_node in main_nodes:
    source_key = str(main_node.get('screen_id'))
    child_edges = edges_by_source.get(source_key, [])
```

6. 按 edge_type 分组输出：

- `branch`
- `exception`
- `bypass`
- `normal`

#### 推荐输出文本

```text
## UI 原型图流程结构（嵌套视图）

### 主干路径
步骤 1：登录页
- 页面元素：账号输入框、密码输入框、登录按钮
- 分支：
  - 目标页面：忘记密码页
  - 触发条件：点击忘记密码
  - 预期现象：进入密码找回流程
- 异常：
  - 目标页面：登录失败提示
  - 异常场景：密码错误
  - 预期提示：账号或密码错误

步骤 2：首页
- 页面元素：首页导航、消息入口
```

#### 验收标准

- 主干节点按 `main_order` 输出。
- 分支挂在对应 source 主干节点下。
- 异常挂在对应 source 主干节点下。
- 旁路挂在对应 source 主干节点下。
- 无效 edge 不导致接口报错。

### 26.2 任务 BE-02：充分利用 flow_meta

#### 涉及文件

- `app/services/prompt_builder/case_prompt.py`
- `app/services/case_generation_prompt_builder.py`

#### 目标

前端节点传递的 `flow_meta` 应进入 Prompt，增强 AI 对流程语义的理解。

#### flow_meta 字段

```json
{
  "parent_main_node_id": "node_1",
  "trigger_condition": "点击高级筛选",
  "pre_action": "已输入搜索条件",
  "expected_result": "展示高级筛选面板",
  "bypass_reason": "首次进入自动弹出",
  "note": "需要校验弹窗关闭"
}
```

#### 使用优先级与自动推断

触发条件、异常场景、旁路出现时机都不应作为人工必填项。用户填写时优先使用；用户未填写时，系统应根据已有结构自动推断或降级为安全默认描述。

边上的字段优先：

- `edge.condition`
- `edge.pre_action`
- `edge.note`

节点上的 `flow_meta` 作为补充：

- `flow_meta.trigger_condition`
- `flow_meta.expected_result`
- `flow_meta.bypass_reason`
- `flow_meta.note`

自动推断来源按优先级：

1. `edge.label`
2. 目标节点 `screen_name`
3. 源节点和目标节点名称组合
4. 目标节点 UI 元素中的按钮、链接、弹窗标题
5. 默认描述：
   - 分支：`进入{target_screen_name}相关分支`
   - 异常：`触发{target_screen_name}相关异常场景`
   - 旁路：`出现{target_screen_name}相关旁路流程`

#### 自动推断模板

当用户未填写触发条件时，系统应按以下模板生成描述。

##### 分支条件模板

```text
如果 edge.label 存在：
  使用 edge.label
如果目标页面名称包含“详情/设置/筛选/确认/编辑/新建/支付/授权”：
  推断为「进入{目标页面名}相关分支」
如果目标节点存在按钮或链接元素：
  推断为「点击{按钮或链接文案}后进入{目标页面名}」
否则：
  使用「进入{目标页面名}相关分支」
```

##### 异常场景模板

```text
如果 edge.label 存在：
  使用 edge.label
如果目标页面名称包含“失败/错误/异常/无权限/超时/为空”：
  推断为「触发{目标页面名}相关异常场景」
如果目标节点存在弹窗、提示、错误文案：
  推断为「出现{提示文案}异常提示」
否则：
  使用「触发{目标页面名}相关异常场景」
```

##### 旁路流程模板

```text
如果 edge.label 存在：
  使用 edge.label
如果目标页面名称包含“弹窗/引导/广告/提示/授权”：
  推断为「进入主流程时出现{目标页面名}」
否则：
  使用「出现{目标页面名}相关旁路流程」
```

##### 不确定性标注

系统推断得到的条件应在 Prompt 中标注来源，避免 AI 将其误认为用户明确输入。

推荐格式：

```text
触发条件（系统推断）：进入高级筛选页相关分支，请结合 UI 元素校验。
```

用户明确填写时使用：

```text
触发条件（用户填写）：点击高级筛选按钮。
```

#### 推荐合并逻辑

```python
def _get_flow_meta_text(edge, target_node):
    flow_meta = target_node.get('flow_meta') or {}
    condition = (
        edge.get('condition')
        or flow_meta.get('trigger_condition')
        or edge.get('label')
        or f"进入{target_node.get('screen_name', '目标页面')}相关流程"
    )
    pre_action = edge.get('pre_action') or flow_meta.get('pre_action') or ''
    expected_result = flow_meta.get('expected_result') or ''
    bypass_reason = flow_meta.get('bypass_reason') or ''
    note = edge.get('note') or flow_meta.get('note') or ''
    return condition, pre_action, expected_result, bypass_reason, note
```

#### 验收标准

- 分支 Prompt 优先包含用户填写的触发条件；未填写时包含系统推断或默认条件。
- 异常 Prompt 优先包含用户填写的异常场景；未填写时包含系统推断或默认异常描述。
- 旁路 Prompt 优先包含用户填写的出现时机；未填写时包含系统推断或默认旁路描述。
- `flow_meta` 缺失时不报错。

### 26.3 任务 BE-03：新增 graph prompt 后端单元测试

#### 建议新增文件

- `tests/services/test_graph_prompt_builder.py`

#### 执行命令

```bash
pytest tests/services/test_graph_prompt_builder.py
```

#### 建议测试函数

```python
def test_graph_prompt_orders_main_nodes_by_main_order():
    ...

def test_graph_prompt_attaches_branch_to_source_main_node():
    ...

def test_graph_prompt_attaches_exception_to_source_main_node():
    ...

def test_graph_prompt_attaches_bypass_to_source_main_node():
    ...

def test_graph_prompt_uses_user_condition_when_present():
    ...

def test_graph_prompt_infers_default_branch_condition_when_missing():
    ...

def test_graph_prompt_infers_default_exception_condition_when_missing():
    ...

def test_graph_prompt_ignores_invalid_edge_without_crash():
    ...
```

#### 测试用例 1：主干流程排序

输入：

- 3 个 main 节点。
- `main_order` 为 2、1、3。

断言：

- Prompt 中步骤顺序为 1、2、3。
- 页面名称顺序与 `main_order` 一致。

#### 测试用例 2：分支挂载

输入：

- 主干节点 A。
- 分支节点 B。
- branch edge：A -> B。

断言：

- Prompt 中 B 出现在 A 的分支下。
- Prompt 包含触发条件。

#### 测试用例 3：异常挂载

输入：

- 主干节点 A。
- 异常节点 C。
- exception edge：A -> C。

断言：

- Prompt 中 C 出现在 A 的异常下。
- Prompt 包含异常条件。

#### 测试用例 4：旁路挂载

输入：

- 主干节点 A。
- 旁路节点 D。
- bypass edge：A -> D。

断言：

- Prompt 中 D 出现在 A 的旁路下。
- Prompt 包含出现时机。

#### 测试用例 5：无效边容错

输入：

- edge source 或 target 不存在。

断言：

- 构建 Prompt 不抛异常。
- 日志可记录 warning。
- 有效节点仍正常输出。

### 26.4 任务 BE-04：后端流程结构校验

#### 涉及文件

- `app/api/v1/endpoints/test_case_ai_generate.py`
- `app/api/v1/endpoints/test_case_ai.py`
- 可选新增：`app/services/flow_validation.py`

#### 校验规则

错误级别：

- graph 模式下 nodes 为空。
- 不存在主干节点。
- 分支/异常/旁路边缺少 target。
- edge 指向不存在的节点。

警告级别：

- 多个主干节点但没有 normal 连线。
- 分支缺少 condition 且无法自动推断。
- 异常缺少 condition 且无法自动推断。
- 存在孤立节点。

#### 返回策略

M1B 可先只记录 warning，不阻断生成。

M2 再考虑将错误返回前端展示。

#### 验收标准

- 无效 edge 不导致 500。
- 后端日志能定位问题。
- 有效流程仍可生成测试用例。

### 26.5 任务 BE-05：Prompt 预览接口

#### 是否纳入 M1A/M1B

不纳入 M1A/M1B，建议作为 M2 或 P1 增强项。

#### 新增接口建议

```http
POST /api/v1/test-case/preview-graph-prompt
```

#### 请求参数

复用增强生成请求中的关键字段：

```json
{
  "project_id": 1,
  "description": "生成登录流程测试用例",
  "context": {},
  "mode": "graph",
  "flow_sort_data": {}
}
```

#### 返回数据

```json
{
  "graph_prompt": "...",
  "stats": {
    "node_count": 10,
    "edge_count": 12,
    "main_count": 4,
    "branch_count": 3,
    "exception_count": 2,
    "bypass_count": 1
  },
  "warnings": []
}
```

#### 前端用途

- 替代当前控制台输出。
- 支持 Prompt 预览弹窗。
- 支持复制 Prompt。

## 27. 前后端联调方案

### 27.1 联调前置条件

- 前端能传 `mode=graph`。
- 前端能传完整 `flow_sort_data`。
- 后端增强生成接口可访问。
- 项目下至少有一个测试点。
- 至少准备 5 个 UI 页面节点。

### 27.2 联调用例一：主干流程

#### 前端操作

1. 选择 UI 原型图版本。
2. 保留 3 个主干节点。
3. 调整主干顺序。
4. 点击生成。

#### 后端验证

- 请求体包含 `mode=graph`。
- `flow_sort_data.nodes` 中主干节点有 `main_order`。
- 后端 Prompt 中主干顺序正确。

#### AI 输出验证

- 生成用例步骤顺序符合主干流程。

### 27.3 联调用例二：分支流程

#### 前端操作

1. 将一个节点设置为分支。
2. 选择挂靠主干。
3. 可选填写触发条件；不填写时系统自动推断或使用默认条件。
4. 点击生成。

#### 后端验证

- `edges` 中存在 `edge_type=branch`。
- `condition` 可为空，但后端 Prompt 中必须出现用户填写、系统推断或默认生成的分支条件。
- Prompt 中出现“分支流程”或嵌套分支。

#### AI 输出验证

- 用例中包含分支触发条件。
- 分支作为独立场景或补充场景体现。

### 27.4 联调用例三：异常流程

#### 前端操作

1. 将一个节点设置为异常。
2. 填写异常场景。
3. 点击生成。

#### 后端验证

- `edges` 中存在 `edge_type=exception`。
- Prompt 中出现异常场景。

#### AI 输出验证

- 用例包含异常输入或异常触发条件。
- 预期结果包含错误提示或异常处理。

### 27.5 联调用例四：旁路流程

#### 前端操作

1. 将一个节点设置为旁路。
2. 填写出现时机或跳过原因。
3. 点击生成。

#### 后端验证

- `edges` 中存在 `edge_type=bypass`。
- Prompt 中出现旁路说明。

#### AI 输出验证

- 用例前置或步骤体现旁路出现和关闭方式。

## 28. 推荐开发执行顺序

### 28.1 第一批：前端视觉闭环

1. FE-01 总览/编辑模式切换。
2. FE-02 总览模式节点轻量化。
3. FE-03 连线视觉优化。
4. FE-04 默认适配全图。

目标：

- 用户能明显感受到界面接近参考图。

### 28.2 第二批：前端操作效率

1. FE-05 自动布局算法优化。
2. FE-06 页面搜索定位。

目标：

- 多页面场景下可快速整理和查找。

### 28.3 第三批：后端 Prompt 语义增强

1. BE-01 嵌套流程结构。
2. BE-02 flow_meta 利用。
3. BE-03 单元测试。
4. BE-04 后端校验。

目标：

- AI 接收到的流程结构更接近思维导图。

### 28.4 第四批：联调与验收

1. 主干流程联调。
2. 分支流程联调。
3. 异常流程联调。
4. 旁路流程联调。
5. 不选择 UI 原型图的回归测试。
6. 只选择需求文档的回归测试。
7. 只选择测试点的回归测试。

## 29. 可执行开发任务清单

### 29.1 前端任务清单

| 编号 | 任务 | 文件 | 优先级 | 完成标准 |
|---|---|---|---|---|
| FE-01 | 总览/编辑模式切换 | `FlowSortEditor.vue`, `FlowNodeCard.vue` | P0 | 可切换模式且不影响提交数据 |
| FE-02 | 总览节点轻量化 | `FlowNodeCard.vue` | P0 | 节点以截图为主体 |
| FE-03 | 连线视觉优化 | `useFlowEditor.ts`, `FlowSortEditor.vue` | P0 | 总览模式连线更轻 |
| FE-04 | 默认适配全图 | `FlowSortEditor.vue` | P0 | 初始化和自动布局后 fitView |
| FE-05 | 自动布局优化 | `useFlowLayout.ts` | P0 | 主干/分支/异常/旁路分层 |
| FE-06 | 页面搜索定位 | `FlowSearchBox.vue` 或 `useFlowSearch.ts` | P0 | 可按页面名定位节点 |

### 29.2 后端任务清单

| 编号 | 任务 | 文件 | 优先级 | 完成标准 |
|---|---|---|---|---|
| BE-01 | 嵌套流程 Prompt | `case_prompt.py` | P0 | Prompt 按主干节点嵌套分支/异常/旁路 |
| BE-02 | flow_meta 利用 | `case_prompt.py` | P0 | expected_result/bypass_reason/note 进入 Prompt |
| BE-03 | Prompt 单元测试 | `tests/services/test_graph_prompt_builder.py` | P0 | 覆盖主干、分支、异常、旁路 |
| BE-04 | 流程结构校验 | `flow_validation.py` 或 endpoint | P1 | 无效边不导致 500 |
| BE-05 | Prompt 预览接口 | endpoint | P1 | 前端可预览 graph_prompt |

## 30. M1 最终验收清单

### 30.1 前端验收

- 可在总览/编辑模式间切换。
- 总览模式下节点轻量、截图突出。
- 连线视觉接近原型流图。
- 自动布局后主干、分支、异常、旁路层次清晰。
- 搜索页面可定位节点。
- 生成接口请求仍包含正确 `flow_sort_data`。

### 30.2 后端验收

- `mode=graph` 时后端使用 `graph_prompt`。
- Prompt 中有主干流程。
- Prompt 中有按主干挂载的分支。
- Prompt 中有按主干挂载的异常。
- Prompt 中有按主干挂载的旁路。
- `flow_meta` 关键字段能进入 Prompt。
- 无效边不会导致接口 500。

### 30.3 AI 结果验收

- 主干流程生成的步骤顺序正确。
- 分支条件能体现在测试步骤或场景标题中。
- 异常流程能生成异常测试用例。
- 旁路流程能作为前置或步骤处理。
- 生成结果仍为合法 JSON。

### 30.4 回归验收

- 不选择 UI 原型图仍可生成。
- 只选择需求文档仍可生成。
- 只选择测试点仍可生成。
- 原有普通增强模式不受影响。
- 现有测试点选择和分页不受影响。

## 31. M1A 开发进度与自测记录

### 31.1 开发进度

| 任务 | 状态 | 改动文件 | 说明 |
|------|------|----------|------|
| M1A-1: 抽取节点显示模式类型 | ✅ 完成 | `FlowSortEditor.vue` | 新增 `displayMode` ref，类型 `'overview' \| 'edit'`，纯 UI 状态不入 store/提交数据 |
| M1A-2: 实现总览/编辑模式切换 | ✅ 完成 | `FlowSortEditor.vue` | 工具栏新增总览/编辑按钮组；切换时自动 fitView；总览模式禁用拖拽/连线/选择 |
| M1A-3: 改造 FlowNodeCard 双模式 | ✅ 完成 | `FlowNodeCard.vue` | 新增 `displayMode`/`isSearchMatch` prop；总览模式显示紧凑卡片（仅类型标签+名称+摘要），编辑模式保持完整卡片 |
| M1A-4: 连线样式适配总览模式 | ✅ 完成 | `FlowSortEditor.vue` | 总览模式连线 stroke-width 1.5、opacity 0.7、label 字号 10px |
| M1A-5: 初始化和自动布局后 fitView | ✅ 完成 | `FlowSortEditor.vue` | `displayMode` 切换时自动 fitView；`handleAutoLayout` 完成后自动 fitView |
| M1A-6: 页面搜索定位 | ✅ 完成 | `FlowSortEditor.vue` | 工具栏新增搜索输入框；按名称/摘要模糊匹配；匹配节点高亮（橙色边框）；自动居中到首个匹配 |
| M1A-7: flow_sort_data 提交边界 | ✅ 完成 | `useFlowEditor.ts` | 触发条件缺失从 error 降级为 warning + "系统将自动推断"提示；`getFlowSortSubmitData` 不受 displayMode/searchKeyword 影响 |

### 31.2 自测记录

#### TypeScript 编译检查

```bash
npx vue-tsc --noEmit 2>&1 | Select-String "FlowSortEditor|FlowNodeCard|useFlowEditor"
# 结果：无错误输出，三个改动文件零 TS 错误
```

#### 单元测试

```bash
npx vitest run src/composables/__tests__/useFlowEditor.spec.ts
# 17 passed — validateFlowData / normalizeEdges / getMainNodesInOrder 等核心逻辑

npx vitest run src/components/case/__tests__/FlowNodeCard.spec.ts
# 15 passed — 双模式渲染 / 搜索高亮 / dropdown 禁用 / 流程类型 class
```

| 测试文件 | 用例数 | 结果 |
|----------|--------|------|
| `useFlowEditor.spec.ts` | 17 | ✅ 全部通过 |
| `FlowNodeCard.spec.ts` | 15 | ✅ 全部通过 |

#### 功能自测清单

| 测试项 | 预期结果 | 实际结果 |
|--------|----------|----------|
| 默认进入编辑模式 | 节点可拖拽、连线、选择 | 待手工验证 |
| 切换到总览模式 | 节点紧凑显示，不可拖拽/连线，自动 fitView | 待手工验证 |
| 总览模式连线 | 连线更细更淡，label 字号更小 | 待手工验证 |
| 总览模式 dropdown 禁用 | 类型标签不可点击切换 | ✅ 单元测试验证 |
| 切回编辑模式 | 恢复完整卡片和交互 | 待手工验证 |
| 搜索输入 | 输入关键词后匹配节点高亮，画布居中到首个匹配 | 待手工验证 |
| 清空搜索 | 高亮消失 | 待手工验证 |
| 搜索框获焦时快捷键 | Backspace 不误删节点 | ✅ 代码审查确认 |
| 切换模式时搜索清空 | 残留高亮消失 | ✅ 代码审查确认 |
| 自动布局后 fitView | 布局完成后画布自动适配 | 待手工验证 |
| 提交数据不含 UI 状态 | `getFlowSortSubmitData()` 不含 displayMode/searchKeyword | ✅ 代码审查确认 |
| 触发条件缺失不阻止生成 | `validateFlowData` 返回 warning 而非 error | ✅ 单元测试验证 |

#### 回归风险点

- `displayMode` 是组件本地 ref，不影响 store 和提交数据 → 低风险
- `searchKeyword`/`searchMatchIds` 同为本地 ref → 低风险
- `validateFlowData` 触发条件从 error 改为 warning → 需确认调用方不依赖 errors 数组阻断生成

### 31.3 遗留与后续

- 搜索定位的 `setViewport` 坐标计算为简化公式，M1B 可考虑使用 VueFlow 的 `fitView({ nodes })` 精确居中
- 触发条件自动推断逻辑目前仅在前端 warning 提示，后端推断模板实现属于 M1B
- `warnings` 数组当前无展示渠道，用户看不到"系统将自动推断"提示，M1B/M2 需增加警告展示
- 搜索框在小屏下可能被挤压，M2 增加响应式处理

### 31.4 代码评审修复记录

| 问题 | 优先级 | 修复 |
|------|--------|------|
| `handleSearchLocate` 重复调用 `useVueFlow()` | P1 | 将 `setViewport` 移至顶层解构，删除函数内重复调用 |
| 总览模式下 `el-dropdown` 仍可操作 | P3 | 添加 `:disabled="displayMode === 'overview'"` 禁用下拉 |
| 搜索框获焦时 Backspace 误删节点 | Bug | `handleKeyDown` 增加 `isInputFocused` 判断，输入框获焦时跳过快捷键 |
| 切换模式时搜索高亮残留 | Bug | `watch(displayMode)` 中清空 `searchKeyword`/`searchMatchIds` |
| 搜索定位硬编码坐标 | P2 | 记录为 M1B 优化项，使用 `fitView({ nodes })` 替换 |

## 32. M1B 开发进度与自测记录

### 32.1 M1B 任务完成状态

| 编号 | 任务 | 涉及文件 | 状态 |
|------|------|----------|------|
| FE-05 | 自动布局优化（useFlowLayout） | `src/composables/useFlowLayout.ts`, `FlowSortEditor.vue` | ✅ 完成 |
| BE-01 | 嵌套流程 Prompt | `app/services/prompt_builder/case_prompt.py`, `app/services/case_generation_prompt_builder.py` | ✅ 完成 |
| BE-02 | flow_meta 利用 | `app/services/prompt_builder/helpers.py`, `case_prompt.py` | ✅ 完成 |
| BE-03 | Prompt 单元测试 | `tests/test_m1b_prompt.py`, `tests/test_case_generation_prompt_builder.py` | ✅ 完成 |
| BE-04 | 流程结构校验 | `app/services/flow_validation.py`, 两个 API endpoint | ✅ 完成 |

### 32.2 代码变更摘要

**前端 (FE-05)**:
- 新增 `src/composables/useFlowLayout.ts`：`layeredAutoLayout` 函数，主干节点水平排列，分支/异常/旁路节点垂直分层在源节点下方
- 修改 `FlowSortEditor.vue`：`handleAutoLayout` 改用 `layeredAutoLayout` composable

**后端 (BE-01/BE-02)**:
- 修改 `app/services/prompt_builder/case_prompt.py`：`_append_main_flow` + 3 个独立 append 函数 → `_append_nested_flow` 单函数，分支/异常/旁路嵌套在对应主干步骤下（├─/└─ 树形符号）
- 新增 `app/services/prompt_builder/helpers.py` 辅助函数：`_infer_condition`（触发条件自动推断）、`_render_flow_meta_hint`（flow_meta 补充信息渲染）、`_group_edges_by_source`（按源节点分组连线）
- 同步修改 `app/services/case_generation_prompt_builder.py`（被 `test_case_ai_generate.py` 使用的独立入口）

**后端 (BE-04)**:
- 新增 `app/services/flow_validation.py`：`validate_flow_structure` 函数，错误级别（空节点/无主干/缺 target/指向不存在节点）+ 警告级别（多主干无 normal 连线/缺 condition/孤立节点），M1B 阶段仅记录不阻断
- 修改 `app/api/v1/endpoints/test_case_ai.py` 和 `test_case_ai_generate.py`：在 `_build_graph_prompt_data` 中调用校验

### 32.3 自动化测试结果

```bash
# M1B 新增测试
python -m pytest tests/test_m1b_prompt.py tests/test_m1b_flow_validation.py -v --no-cov
# 26 passed

# M1B + 原有 prompt 测试
python -m pytest tests/test_m1b_prompt.py tests/test_m1b_flow_validation.py tests/test_case_generation_prompt_builder.py -v --no-cov
# 46 passed, 0 failed
```

| 测试文件 | 用例数 | 覆盖范围 | 结果 |
|----------|--------|----------|------|
| `test_m1b_prompt.py` | 15 | _infer_condition / _render_flow_meta_hint / _group_edges_by_source / 嵌套 Prompt / flow_meta 集成 | ✅ 全部通过 |
| `test_m1b_flow_validation.py` | 11 | 空 nodes / 无主干 / 缺 target / 不存在节点 / 多主干无连线 / 缺 condition / 孤立节点 / 正常流程 | ✅ 全部通过 |
| `test_case_generation_prompt_builder.py` | 20 | 原有主干/分支/异常/旁路/边界场景（已适配嵌套格式） | ✅ 全部通过 |

### 32.4 关键设计决策

1. **嵌套 Prompt 结构**：分支/异常/旁路嵌套在对应主干步骤下，使用 ├─/│/└─ 树形符号，替代原来的独立 `### 分支流程`/`### 异常流程`/`### 旁路流程` 扁平段落
2. **触发条件自动推断**：优先使用用户填写的 condition，缺失时按模板推断（branch: `用户在{source_name}选择{target_name}相关操作`，exception: `{target_name}操作失败或系统异常`，bypass: `进入{source_name}时自动弹出{target_name}`）
3. **flow_meta 渲染**：pre_action/expected_result/bypass_reason/note 字段渲染为 `[前置操作: ...; 预期结果: ...]` 格式附加在分支/异常/旁路行末
4. **校验不阻断**：M1B 阶段 `validate_flow_structure` 仅记录日志，不阻断生成流程；M2 再将错误返回前端
5. **双入口同步**：`prompt_builder` 包（`case_prompt.py`）和独立 `case_generation_prompt_builder.py` 保持逻辑一致

### 32.5 回归风险点

- 嵌套 Prompt 格式变更可能影响 AI 模型对 Prompt 的理解质量，需观察生成效果
- ~~`case_generation_prompt_builder.py` 中的辅助函数与 `prompt_builder/helpers.py` 存在重复~~ → 已统一为从 `prompt_builder.helpers` 导入
- 前端 `useFlowLayout` 的分层布局算法基于简单规则（水平间距/垂直偏移），复杂拓扑下可能重叠，M2 可优化
