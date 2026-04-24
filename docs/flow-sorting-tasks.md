# 截图流程图排序优化 - 详细任务项

> 版本：v1.0 | 日期：2026-04-21 | 关联文档：[flow-sorting-plan.md](./flow-sorting-plan.md)

---

## M1: 前端交互设计 + 原型验证（0.5 天）

### T1.1 安装 @vue-flow 依赖

**负责人：** 前端  
**预计耗时：** 10 分钟

```bash
npm install @vue-flow/core@1 @vue-flow/additional-components@1
```

**验收标准：**
- [ ] `npm install` 无报错
- [ ] `package.json` 中新增依赖版本锁定
- [ ] `npm run dev` 项目正常启动

---

### T1.2 创建流程图编辑器基础组件

**负责人：** 前端  
**预计耗时：** 2 小时  
**文件：** `src/components/case/FlowSortEditor.vue`

**任务内容：**

1. 创建基础 Vue 3 组件，使用 `<script setup lang="ts">` 语法
2. 集成 `@vue-flow/core` 的 `VueFlow` 组件
3. 实现基础画布渲染（Background、Controls、MiniMap）
4. 接收 `screens: UIScreen[]` props，渲染为初始节点

**核心代码框架：**

```vue
<template>
  <div class="flow-sort-editor">
    <div class="editor-toolbar">
      <el-radio-group v-model="sortMode" size="small">
        <el-radio-button value="linear">线性排序</el-radio-button>
        <el-radio-button value="graph">流程图排序</el-radio-button>
      </el-radio-group>
      <el-button @click="handleAutoLayout">自动布局</el-button>
      <el-button @click="handlePreviewPrompt">预览 Prompt</el-button>
    </div>

    <div v-if="sortMode === 'linear'" class="linear-mode">
      <!-- 原有线性排序逻辑（保留兼容） -->
      <slot name="linear" />
    </div>

    <div v-else class="graph-mode">
      <VueFlow
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="{ x: 0, y: 0, zoom: 1 }"
        :min-zoom="0.2"
        :max-zoom="4"
        fit-view-on-init
        @connect="onConnect"
        @node-drag-stop="onNodeDragStop"
      >
        <Background />
        <Controls />
        <MiniMap />
        <template #node-custom="nodeProps">
          <FlowNodeCard :node-data="nodeProps.data" />
        </template>
      </VueFlow>
    </div>

    <EdgeConditionDialog
      v-model:visible="conditionDialogVisible"
      :edge-data="currentEdge"
      @confirm="onEdgeConditionConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { VueFlow, useVueFlow, type Connection, type Edge, type Node } from '@vue-flow/core'
import { Background, Controls, MiniMap } from '@vue-flow/additional-components'
import FlowNodeCard from './FlowNodeCard.vue'
import EdgeConditionDialog from './EdgeConditionDialog.vue'

interface UIScreen {
  id: number
  screen_name: string
  summary?: string
  parse_status?: string
  element_count?: number
  original_file_path?: string
}

const props = defineProps<{
  screens: UIScreen[]
  initialMode?: 'linear' | 'graph'
}>()

const emit = defineEmits<{
  'update:sort-data': [data: FlowSortData]
  'preview-prompt': []
}>()

interface FlowSortData {
  mode: 'linear' | 'graph'
  nodes: FlowNode[]
  edges: FlowEdge[]
}

interface FlowNode {
  id: string
  screen_id: number
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  position: { x: number; y: number }
}

interface FlowEdge {
  id: string
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
}

const sortMode = ref<'linear' | 'graph'>(props.initialMode || 'graph')
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])
const conditionDialogVisible = ref(false)
const currentEdge = ref<Connection | null>(null)

const { onConnect, addEdges } = useVueFlow()

// 初始化节点
watch(() => props.screens, (newScreens) => {
  nodes.value = newScreens.map((screen, index) => ({
    id: `node_${index + 1}`,
    type: 'custom',
    position: { x: index * 280, y: 0 },
    data: {
      screen_id: screen.id,
      screen_name: screen.screen_name,
      summary: screen.summary,
      flow_type: 'main',
      image_url: screen.original_file_path ? `/api/v1/file/preview-screen/${screen.id}` : ''
    }
  }))
}, { immediate: true })

// 连线处理
const onConnect = (connection: Connection) => {
  currentEdge.value = connection
  conditionDialogVisible.value = true
}

const onEdgeConditionConfirm = (edgeData: Partial<FlowEdge>) => {
  if (!currentEdge.value) return
  
  const newEdge: Edge = {
    id: `edge_${Date.now()}`,
    source: currentEdge.value.source,
    target: currentEdge.value.target,
    type: 'default',
    animated: edgeData.edge_type !== 'normal',
    style: getEdgeStyle(edgeData.edge_type),
    label: edgeData.label,
    data: {
      edge_type: edgeData.edge_type,
      condition: edgeData.condition
    }
  }
  
  edges.value = [...edges.value, newEdge]
  conditionDialogVisible.value = false
  emitSortData()
}

const getEdgeStyle = (type: string) => {
  const styles: Record<string, { stroke: string }> = {
    normal: { stroke: '#409eff' },
    branch: { stroke: '#67c23a' },
    exception: { stroke: '#f56c6c' },
    bypass: { stroke: '#e6a23c' }
  }
  return styles[type] || styles.normal
}

// 节点拖拽结束
const onNodeDragStop = () => {
  emitSortData()
}

// 自动布局
const handleAutoLayout = () => {
  // TODO: 实现自动布局算法（Dagre 或简单网格）
}

// 预览 Prompt
const handlePreviewPrompt = () => {
  emit('preview-prompt')
}

// 输出排序数据
const emitSortData = () => {
  const flowNodes: FlowNode[] = nodes.value.map(node => ({
    id: node.id,
    screen_id: node.data.screen_id,
    flow_type: node.data.flow_type,
    position: node.position
  }))
  
  const flowEdges: FlowEdge[] = edges.value.map(edge => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    edge_type: edge.data?.edge_type || 'normal',
    condition: edge.data?.condition,
    label: edge.label || ''
  }))
  
  emit('update:sort-data', {
    mode: sortMode.value,
    nodes: flowNodes,
    edges: flowEdges
  })
}
</script>

<style scoped lang="scss">
.flow-sort-editor {
  height: 600px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  .editor-toolbar {
    padding: 12px;
    background: #fafafa;
    border-bottom: 1px solid #e4e7ed;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .graph-mode {
    flex: 1;
    height: calc(100% - 56px);
  }
}
</style>
```

**验收标准：**
- [ ] 组件可正常渲染画布
- [ ] 传入 screens 数据后，节点正确显示
- [ ] 节点可拖拽移动
- [ ] 模式切换正常

---

### T1.3 创建节点卡片组件

**负责人：** 前端  
**预计耗时：** 1.5 小时  
**文件：** `src/components/case/FlowNodeCard.vue`

**任务内容：**

1. 创建自定义节点组件，显示截图缩略图
2. 左上角显示流程类型标签（可点击切换）
3. 右侧显示连接点（用于拖拽连线）
4. 底部显示屏幕名称和 OCR 摘要

**核心代码框架：**

```vue
<template>
  <div class="flow-node-card" :class="`flow-type-${data.flow_type}`">
    <div class="node-header">
      <div class="connect-handle" />
      <el-dropdown trigger="click" @command="handleFlowTypeChange">
        <el-tag :type="flowTypeTagType" size="small" effect="dark">
          {{ flowTypeLabel }}
        </el-tag>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="main">主干流程</el-dropdown-item>
            <el-dropdown-item command="branch">分支流程</el-dropdown-item>
            <el-dropdown-item command="exception">异常流程</el-dropdown-item>
            <el-dropdown-item command="bypass">旁路流程</el-dropdown-item>
          </el-dropdown-menu>
        </el-dropdown>
      </el-dropdown>
    </div>

    <div class="node-image" @click="handlePreview">
      <img v-if="data.image_url" :src="data.image_url" :alt="data.screen_name" />
      <div v-else class="image-placeholder">
        <el-icon :size="32"><Picture /></el-icon>
      </div>
      <div class="image-overlay">
        <el-icon><View /></el-icon>
      </div>
    </div>

    <div class="node-footer">
      <div class="screen-name">{{ data.screen_name }}</div>
      <div v-if="data.summary" class="screen-summary">{{ data.summary }}</div>
    </div>

    <Handle type="source" :position="Position.Right" />
    <Handle type="target" :position="Position.Left" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { Picture, View } from '@element-plus/icons-vue'

const props = defineProps<{
  data: {
    screen_id: number
    screen_name: string
    summary?: string
    flow_type: 'main' | 'branch' | 'exception' | 'bypass'
    image_url?: string
  }
}>()

const emit = defineEmits<{
  'update:flow-type': [type: string]
  'preview': []
}>()

const flowTypeLabel = computed(() => {
  const labels = {
    main: '主干',
    branch: '分支',
    exception: '异常',
    bypass: '旁路'
  }
  return labels[props.data.flow_type] || '主干'
})

const flowTypeTagType = computed(() => {
  const types = {
    main: '' as const,
    branch: 'success' as const,
    exception: 'danger' as const,
    bypass: 'warning' as const
  }
  return types[props.data.flow_type] || ''
})

const handleFlowTypeChange = (type: string) => {
  emit('update:flow-type', type)
}

const handlePreview = () => {
  emit('preview')
}
</script>

<style scoped lang="scss">
.flow-node-card {
  width: 220px;
  background: #fff;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: box-shadow 0.2s;

  &:hover {
    box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
  }

  &.flow-type-main { border-color: #409eff; }
  &.flow-type-branch { border-color: #67c23a; }
  &.flow-type-exception { border-color: #f56c6c; }
  &.flow-type-bypass { border-color: #e6a23c; }

  .node-header {
    padding: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    background: #fafafa;

    .connect-handle {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #409eff;
      cursor: crosshair;
    }
  }

  .node-image {
    position: relative;
    height: 120px;
    background: #f5f7fa;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;

    img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }

    .image-placeholder {
      color: #c0c4cc;
    }

    .image-overlay {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.2s;
      color: #fff;
      font-size: 24px;
    }

    &:hover .image-overlay {
      opacity: 1;
    }
  }

  .node-footer {
    padding: 8px;

    .screen-name {
      font-size: 13px;
      font-weight: 500;
      color: #303133;
      margin-bottom: 4px;
    }

    .screen-summary {
      font-size: 11px;
      color: #909399;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  }
}
</style>
```

**验收标准：**
- [ ] 节点卡片样式正确
- [ ] 流程类型标签可切换
- [ ] 点击缩略图可触发预览事件
- [ ] 不同流程类型显示不同边框颜色

---

### T1.4 创建连线条件弹窗组件

**负责人：** 前端  
**预计耗时：** 1 小时  
**文件：** `src/components/case/EdgeConditionDialog.vue`

**任务内容：**

1. 创建 Element Plus Dialog 组件
2. 提供连线类型选择（正常流转/条件分支/异常跳转/旁路步骤）
3. 根据类型动态显示条件输入框
4. 提交时输出 `FlowEdge` 数据

**核心代码框架：**

```vue
<template>
  <el-dialog
    v-model="dialogVisible"
    title="设置连线类型"
    width="400px"
    @close="handleClose"
  >
    <el-form label-width="80px">
      <el-form-item label="连线类型">
        <el-select v-model="formData.edge_type" style="width: 100%">
          <el-option label="正常流转" value="normal" />
          <el-option label="条件分支" value="branch" />
          <el-option label="异常跳转" value="exception" />
          <el-option label="旁路步骤" value="bypass" />
        </el-select>
      </el-form-item>

      <el-form-item
        v-if="formData.edge_type !== 'normal'"
        :label="conditionLabel"
      >
        <el-input
          v-model="formData.condition"
          type="textarea"
          :rows="3"
          :placeholder="conditionPlaceholder"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  edgeData?: any
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'confirm': [data: any]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val)
})

const formData = ref({
  edge_type: 'normal',
  condition: ''
})

const conditionLabel = computed(() => {
  const labels = {
    branch: '触发条件',
    exception: '异常场景',
    bypass: '出现时机'
  }
  return labels[formData.value.edge_type] || '条件'
})

const conditionPlaceholder = computed(() => {
  const placeholders = {
    branch: '例如：用户点击高级筛选按钮',
    exception: '例如：输入非法字符或接口超时',
    bypass: '例如：进入页面自动弹出'
  }
  return placeholders[formData.value.edge_type] || ''
})

watch(() => props.visible, (val) => {
  if (val) {
    formData.value = { edge_type: 'normal', condition: '' }
  }
})

const handleClose = () => {
  formData.value = { edge_type: 'normal', condition: '' }
}

const handleConfirm = () => {
  const labelMap = {
    normal: '正常流转',
    branch: '条件分支',
    exception: '异常跳转',
    bypass: '旁路步骤'
  }

  emit('confirm', {
    edge_type: formData.value.edge_type,
    condition: formData.value.condition || null,
    label: labelMap[formData.value.edge_type]
  })
}
</script>
```

**验收标准：**
- [ ] 弹窗正常显示/隐藏
- [ ] 选择不同连线类型时，条件输入框动态显示/隐藏
- [ ] 点击确认时输出正确数据

---

### T1.5 创建状态管理 Store

**负责人：** 前端  
**预计耗时：** 30 分钟  
**文件：** `src/stores/flowSort.ts`

**任务内容：**

1. 使用 Pinia 创建流程图排序状态管理
2. 存储 nodes、edges、mode 数据
3. 提供数据序列化/反序列化方法

**核心代码：**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface FlowNodeData {
  id: string
  screen_id: number
  screen_name: string
  summary?: string
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  image_url?: string
  position: { x: number; y: number }
}

export interface FlowEdgeData {
  id: string
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
}

export const useFlowSortStore = defineStore('flowSort', () => {
  const mode = ref<'linear' | 'graph'>('graph')
  const nodes = ref<FlowNodeData[]>([])
  const edges = ref<FlowEdgeData[]>([])

  const sortData = computed(() => ({
    mode: mode.value,
    nodes: nodes.value,
    edges: edges.value
  }))

  function setMode(newMode: 'linear' | 'graph') {
    mode.value = newMode
  }

  function updateNodes(newNodes: FlowNodeData[]) {
    nodes.value = newNodes
  }

  function updateEdges(newEdges: FlowEdgeData[]) {
    edges.value = newEdges
  }

  function reset() {
    mode.value = 'graph'
    nodes.value = []
    edges.value = []
  }

  function toJson(): string {
    return JSON.stringify(sortData.value)
  }

  function fromJson(json: string) {
    const data = JSON.parse(json)
    mode.value = data.mode || 'graph'
    nodes.value = data.nodes || []
    edges.value = data.edges || []
  }

  return {
    mode,
    nodes,
    edges,
    sortData,
    setMode,
    updateNodes,
    updateEdges,
    reset,
    toJson,
    fromJson
  }
})
```

**验收标准：**
- [ ] Store 可正常创建
- [ ] 数据更新响应式生效
- [ ] toJson/fromJson 序列化正常

---

### T1.6 原型可用性测试

**负责人：** 前端 + 测试  
**预计耗时：** 1 小时

**测试流程：**

1. 找 2-3 名测试人员
2. 提供任务：完成"主干 3 步 + 分支 1 步 + 异常 1 步"的排序
3. 计时并记录操作问题
4. 收集反馈

**验收标准：**
- [ ] 30 秒内完成排序任务
- [ ] 无严重操作困惑
- [ ] 反馈评分 ≥ 7 分（10 分制）

---

## M2: 前端功能开发（0.5 天）

### T2.1 集成 FlowSortEditor 到 ai-generate.vue

**负责人：** 前端  
**预计耗时：** 2 小时  
**修改文件：** `src/views/case/ai-generate.vue`

**任务内容：**

1. 替换原有 `ui-screens-grid` 拖拽区域（L156-L207）
2. 引入 `FlowSortEditor` 组件
3. 传递 `uiScreens` 数据作为 props
4. 监听 `update:sort-data` 事件，更新 `formData.ui_screen_ids`
5. 构建 `flow_sort_data` 提交数据（包含 `screen_name`、`summary`、`screen_order`）

**修改位置：**

```vue
<!-- 原代码 L156-L207 替换为 -->
<FlowSortEditor
  v-if="selectedUiPrototypeProjectId"
  :screens="uiScreens"
  :initial-mode="sortMode"
  @update:sort-data="handleFlowSortUpdate"
  @preview-prompt="handlePreviewPrompt"
/>
```

**数据传递逻辑：**

```typescript
// ai-generate.vue 中新增
const flowSortNodes = ref<any[]>([])
const flowSortEdges = ref<any[]>([])

const handleFlowSortUpdate = (data: { mode: string; nodes: any[]; edges: any[] }) => {
  flowSortNodes.value = data.nodes
  flowSortEdges.value = data.edges
  // 同步更新 ui_screen_ids（保持向后兼容）
  formData.ui_screen_ids = data.nodes.map(n => n.screen_id)
}

// 提交给后端的数据（handleGenerate 方法中）
const buildSubmitData = () => {
  const baseData = {
    project_id: formData.project_id,
    test_point_ids: formData.test_point_ids,
    requirement_file_ids: formData.requirement_file_ids,
    ui_screen_ids: formData.ui_screen_ids
  }

  // 仅在 graph 模式下传递 flow_sort_data
  if (sortMode.value === 'graph' && flowSortNodes.value.length > 0) {
    return {
      ...baseData,
      mode: 'graph',
      flow_sort_data: {
        nodes: flowSortNodes.value.map((node, index) => {
          // 从 uiScreens 中查找对应的屏幕数据
          const screen = uiScreens.value.find(s => s.id === node.screen_id)
          return {
            screen_id: node.screen_id,
            screen_order: index + 1,                    // 前端排序序号（从 1 开始）
            flow_type: node.flow_type,                  // main | branch | exception | bypass
            screen_name: screen?.screen_name || node.screen_name || '',
            summary: screen?.summary || '',             // AI 解析摘要（已持久化到数据库）
            ocr_text: screen?.ui_spec?.ocr_text || ''   // OCR 原始文本（如果 ui_spec 中包含）
          }
        }),
        edges: flowSortEdges.value.map(edge => {
          // 将 edge.source/target 从 node_id 转换为 screen_id
          const sourceNode = flowSortNodes.value.find(n => n.id === edge.source)
          const targetNode = flowSortNodes.value.find(n => n.id === edge.target)
          return {
            source: String(sourceNode?.screen_id || edge.source),  // 使用 screen_id
            target: String(targetNode?.screen_id || edge.target),  // 使用 screen_id
            edge_type: edge.edge_type || 'normal',
            condition: edge.condition || '',
            label: edge.label || ''
          }
        }),
        module_info: {
          name: selectedUiPrototypeProject.value?.name || '',
          description: selectedUiPrototypeProject.value?.description || ''
        }
      }
    }
  }

  // linear 模式下不传递 flow_sort_data
  return { ...baseData, mode: 'linear' }
}
```

**注意事项：**
- `summary` 字段来自 `uiScreens` 数组，是 AI 解析后持久化到数据库的摘要文本
- `ocr_text` 字段优先从 `ui_spec.ocr_text` 获取，如果 `ui_spec` 中不包含 OCR 原始文本，则为空字符串
- 如果后端确认 `ui_spec` 中不包含 `ocr_text` 字段，则前端只需传递 `summary`，后端通过 `screen_id` 从数据库查询 `ui_spec` 自行提取 OCR 文本

**验收标准：**
- [ ] 原有功能不受影响
- [ ] 新模式下可正常显示截图节点
- [ ] 拖拽节点后 `flowSortNodes` 数据正确更新
- [ ] 连线后 `flowSortEdges` 数据正确更新
- [ ] 提交数据中 `flow_sort_data.nodes` 包含 `screen_order`、`flow_type`、`screen_name`、`summary`
- [ ] linear 模式下 `flow_sort_data` 为 null

---

### T2.2 实现自动布局算法

**负责人：** 前端  
**预计耗时：** 1.5 小时

**任务内容：**

1. 实现简单网格布局算法
2. 主干流程横向排列（y=0）
3. 分支/异常流程纵向排列在源节点下方

**核心逻辑：**

```typescript
function autoLayout(nodes: Node[], edges: Edge[]) {
  const mainNodes = nodes.filter(n => n.data.flow_type === 'main')
  const branchNodes = nodes.filter(n => n.data.flow_type !== 'main')
  
  // 主干横向排列
  mainNodes.forEach((node, index) => {
    node.position = { x: index * 280, y: 0 }
  })
  
  // 分支纵向排列
  branchNodes.forEach((node, index) => {
    const sourceEdge = edges.find(e => e.target === node.id)
    const sourceNode = sourceEdge ? nodes.find(n => n.id === sourceEdge.source) : null
    const sourceX = sourceNode?.position.x || 0
    
    node.position = { x: sourceX, y: (index + 1) * 200 }
  })
}
```

**验收标准：**
- [ ] 点击"自动布局"按钮后，节点按规则排列
- [ ] 主干流程横向排列
- [ ] 分支流程在源节点下方排列

---

### T2.3 实现 Prompt 预览功能

**负责人：** 前端  
**预计耗时：** 1 小时

**任务内容：**

1. 创建 `PromptPreviewDialog.vue` 组件
2. 将排序数据转换为 Prompt 文本
3. 使用 Dialog 展示预览结果

**验收标准：**
- [ ] 点击"预览 Prompt"按钮弹出预览
- [ ] Prompt 文本包含完整流程结构
- [ ] 格式清晰易读

---

## M3: 后端 Prompt 构建逻辑 + 数据传递修复（0.5 天）

### T3.0 数据传递链路修复（关键任务）

**负责人：** 后端 + 前端  
**预计耗时：** 2 小时  
**修改文件：** 
- `app/schemas/test_case.py`
- `app/services/case_generation_core.py`
- `src/views/case/ai-generate.vue`

**任务背景：**

当前系统存在严重的数据传递断层：前端拖拽排序后的数据未完整传递到后端，AI 拿到的只是"一堆页面"而非"有顺序有关系的流程"。

**根因：**
- 前端只传 `ui_screen_ids`（ID 列表），丢失排序顺序
- 后端根据 ID 从数据库重新查询，按数据库 `screen_order` 排序（覆盖前端排序）
- OCR 原始文本、流程类型、连线关系均未传递

**任务内容：**

#### 3.0.1 前端新增传递字段

修改 `ai-generate.vue` 中的提交逻辑，新增 `mode` 和 `flow_sort_data` 字段：

```typescript
// ai-generate.vue 中 handleGenerate 方法修改
const submitData = {
  project_id: formData.project_id,
  test_point_ids: formData.test_point_ids,
  requirement_file_ids: formData.requirement_file_ids,
  ui_screen_ids: formData.ui_screen_ids,
  
  // === 新增字段 ===
  mode: sortMode.value,                    // 排序模式：linear | graph
  flow_sort_data: sortMode.value === 'graph' ? {
    nodes: flowSortNodes.value.map((node, index) => ({
      screen_id: node.screen_id,
      screen_order: index + 1,             // 前端排序序号（从 1 开始）
      flow_type: node.flow_type,           // main | branch | exception | bypass
      screen_name: node.screen_name,
      ocr_text: node.ocr_text,             // OCR 原始文本
      summary: node.summary                // AI 解析摘要（可选）
    })),
    edges: flowSortEdges.value.map(edge => ({
      source: edge.source,
      target: edge.target,
      edge_type: edge.edge_type,           // normal | branch | exception | bypass
      condition: edge.condition,           // 触发条件
      label: edge.label                    // 连线标签
    })),
    module_info: {
      name: selectedUiPrototypeProject.value?.name || '',
      description: selectedUiPrototypeProject.value?.description || ''
    }
  } : null
}
```

#### 3.0.2 后端 Schema 定义

在 `app/schemas/test_case.py` 中新增：

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class FlowNodeSchema(BaseModel):
    screen_id: int
    screen_order: int                              # 前端排序序号
    flow_type: Literal['main', 'branch', 'exception', 'bypass']
    screen_name: str
    ocr_text: Optional[str]                        # OCR 原始文本
    summary: Optional[str]                         # AI 解析摘要

class FlowEdgeSchema(BaseModel):
    source: str
    target: str
    edge_type: Literal['normal', 'branch', 'exception', 'bypass']
    condition: Optional[str]
    label: str

class FlowSortDataSchema(BaseModel):
    nodes: List[FlowNodeSchema]
    edges: List[FlowEdgeSchema]
    module_info: Optional[dict]
```

修改 `AIGenerateEnhancedRequest`：

```python
class AIGenerateEnhancedRequest(BaseModel):
    # ... 现有字段 ...
    mode: Literal['linear', 'graph'] = Field(default='linear', description="排序模式")
    flow_sort_data: Optional[FlowSortDataSchema] = Field(None, description="流程图排序数据")
```

#### 3.0.3 后端上下文构建修改

在 `app/services/case_generation_core.py` 的 `get_context_for_generation` 方法中新增处理逻辑：

```python
async def get_context_for_generation(
    self,
    project_id: int,
    user_id: int,
    flow_sort_data: Optional[FlowSortDataSchema] = None,  # 新增参数
    # ... 其他参数保持不变 ...
) -> Dict[str, Any]:
    context = {
        "requirement_content": "",
        "ui_descriptions": [],
        "ui_specs": [],
        "test_points": [],
        "flow_structure": None,  # 新增：流程结构
        "ocr_texts": {},         # 新增：OCR 文本映射
        # ... 其他字段 ...
    }

    # === 新增：处理流程图排序数据 ===
    if flow_sort_data and flow_sort_data.mode == 'graph':
        # 1. 按前端 screen_order 排序（不覆盖）
        sorted_nodes = sorted(flow_sort_data.nodes, key=lambda n: n.screen_order)
        
        # 2. 构建流程结构
        context["flow_structure"] = {
            "main_flow": [n for n in sorted_nodes if n.flow_type == 'main'],
            "branch_flows": self._build_branch_tree(flow_sort_data.edges, sorted_nodes),
            "exception_flows": self._build_exception_tree(flow_sort_data.edges, sorted_nodes),
            "bypass_flows": self._build_bypass_tree(flow_sort_data.edges, sorted_nodes)
        }
        
        # 3. 注入 OCR 文本映射
        context["ocr_texts"] = {n.screen_id: n.ocr_text for n in sorted_nodes if n.ocr_text}
        
        # 4. 构建 UI 描述（使用前端排序顺序）
        for node in sorted_nodes:
            context["ui_descriptions"].append({
                "screen_id": node.screen_id,
                "screen_name": node.screen_name,
                "screen_order": node.screen_order,      # 新增：前端排序序号
                "flow_type": node.flow_type,            # 新增：流程类型
                "summary": node.summary or "",
                "ocr_text": node.ocr_text or ""         # 新增：OCR 原始文本
            })
        
        logger.info(f"流程图模式：接收到 {len(sorted_nodes)} 个节点，{len(flow_sort_data.edges)} 条连线")
    
    # ... 其余逻辑保持不变 ...
```

#### 3.0.4 流程树构建辅助方法

在 `CoreMixin` 类中新增三个辅助方法：

**设计说明：**

前端提交 `flow_sort_data` 时，`edge.source` 和 `edge.target` 直接使用 `screen_id`（数字转字符串），而非 `@vue-flow` 内部的 `node_id`（如 `node_1`）。这样后端无需反查，直接通过 `int(edge.source)` 即可得到 `screen_id`。

```python
def _build_branch_tree(self, edges: List[FlowEdgeSchema], nodes: List[FlowNodeSchema]) -> List[Dict]:
    """构建分支流程树
    
    Args:
        edges: 连线列表，source/target 为 screen_id 的字符串形式
        nodes: 节点列表，包含 screen_id 和 screen_order 等信息
    
    Returns:
        分支流程列表，每个元素包含 source_step、target_screen_id、target_name、condition
    """
    branch_edges = [e for e in edges if e.edge_type == 'branch']
    result = []
    
    # 构建 screen_id -> node 的映射，提升查找效率
    node_map = {node.screen_id: node for node in nodes}
    
    for edge in branch_edges:
        try:
            source_screen_id = int(edge.source)
            target_screen_id = int(edge.target)
        except (ValueError, TypeError):
            logger.warning(f"连线 source/target 格式错误: source={edge.source}, target={edge.target}")
            continue
        
        source_node = node_map.get(source_screen_id)
        target_node = node_map.get(target_screen_id)
        
        if source_node and target_node:
            result.append({
                'source_step': source_node.screen_order,
                'source_screen_id': source_screen_id,
                'target_screen_id': target_screen_id,
                'target_name': target_node.screen_name,
                'condition': edge.condition or '未指定'
            })
        else:
            missing = []
            if not source_node:
                missing.append(f'source={source_screen_id}')
            if not target_node:
                missing.append(f'target={target_screen_id}')
            logger.warning(f"分支连线节点不存在: {', '.join(missing)}")
    
    return result

def _build_exception_tree(self, edges: List[FlowEdgeSchema], nodes: List[FlowNodeSchema]) -> List[Dict]:
    """构建异常流程树
    
    Args:
        edges: 连线列表，source/target 为 screen_id 的字符串形式
        nodes: 节点列表
    
    Returns:
        异常流程列表，结构同 _build_branch_tree
    """
    exception_edges = [e for e in edges if e.edge_type == 'exception']
    result = []
    
    node_map = {node.screen_id: node for node in nodes}
    
    for edge in exception_edges:
        try:
            source_screen_id = int(edge.source)
            target_screen_id = int(edge.target)
        except (ValueError, TypeError):
            logger.warning(f"连线 source/target 格式错误: source={edge.source}, target={edge.target}")
            continue
        
        source_node = node_map.get(source_screen_id)
        target_node = node_map.get(target_screen_id)
        
        if source_node and target_node:
            result.append({
                'source_step': source_node.screen_order,
                'source_screen_id': source_screen_id,
                'target_screen_id': target_screen_id,
                'target_name': target_node.screen_name,
                'condition': edge.condition or '未指定'
            })
        else:
            missing = []
            if not source_node:
                missing.append(f'source={source_screen_id}')
            if not target_node:
                missing.append(f'target={target_screen_id}')
            logger.warning(f"异常连线节点不存在: {', '.join(missing)}")
    
    return result

def _build_bypass_tree(self, edges: List[FlowEdgeSchema], nodes: List[FlowNodeSchema]) -> List[Dict]:
    """构建旁路流程树
    
    Args:
        edges: 连线列表，source/target 为 screen_id 的字符串形式
        nodes: 节点列表
    
    Returns:
        旁路流程列表，结构同 _build_branch_tree
    """
    bypass_edges = [e for e in edges if e.edge_type == 'bypass']
    result = []
    
    node_map = {node.screen_id: node for node in nodes}
    
    for edge in bypass_edges:
        try:
            source_screen_id = int(edge.source)
            target_screen_id = int(edge.target)
        except (ValueError, TypeError):
            logger.warning(f"连线 source/target 格式错误: source={edge.source}, target={edge.target}")
            continue
        
        source_node = node_map.get(source_screen_id)
        target_node = node_map.get(target_screen_id)
        
        if source_node and target_node:
            result.append({
                'source_step': source_node.screen_order,
                'source_screen_id': source_screen_id,
                'target_screen_id': target_screen_id,
                'target_name': target_node.screen_name,
                'condition': edge.condition or '自动弹出'
            })
        else:
            missing = []
            if not source_node:
                missing.append(f'source={source_screen_id}')
            if not target_node:
                missing.append(f'target={target_screen_id}')
            logger.warning(f"旁路连线节点不存在: {', '.join(missing)}")
    
    return result
```

**关键设计决策：**

| 设计点 | 方案 | 原因 |
|--------|------|------|
| edge.source/target 类型 | 字符串（screen_id 的字符串形式） | 兼容 JSON 传输，后端 `int()` 转换即可 |
| 节点查找方式 | 预先构建 `node_map` 字典 | O(1) 查找，避免循环内 O(n) 遍历 |
| 异常处理 | `try-except` + 日志警告 | 数据异常时不中断流程，记录日志便于排查 |
| 返回值结构 | 统一包含 `source_step`、`source_screen_id`、`target_screen_id`、`target_name`、`condition` | 便于 Prompt 模板统一渲染 |
```

**验收标准：**
- [ ] 前端提交数据包含 `mode` 和 `flow_sort_data` 字段
- [ ] 后端正确接收并解析 `flow_sort_data`
- [ ] 日志输出：`流程图模式：接收到 X 个节点，Y 条连线`
- [ ] `context["flow_structure"]` 包含完整的流程树结构
- [ ] `context["ocr_texts"]` 包含所有节点的 OCR 文本
- [ ] 线性模式下 `flow_sort_data` 为 null，行为与优化前一致

---

### T3.1 新增 FlowSortData Schema

**负责人：** 后端  
**预计耗时：** 30 分钟  
**文件：** `app/schemas/test_case.py`

**任务说明：**

本任务的 Schema 定义已在 T3.0.2 中完整给出，此处仅做补充说明和校验规则增强。

**字段设计依据：**

| 字段 | 来源 | 用途 | 是否必填 |
|------|------|------|----------|
| `screen_id` | 前端节点 data | 关联数据库 UI 屏幕记录 | 必填 |
| `screen_order` | 前端排序序号（从 1 开始） | 保证 AI 理解页面先后顺序 | 必填 |
| `flow_type` | 前端节点 dropdown 选择 | 区分主干/分支/异常/旁路 | 必填 |
| `screen_name` | 前端节点 data | Prompt 中显示页面名称 | 必填 |
| `ocr_text` | 前端调用 OCR 接口获取 | Prompt 中注入页面文字内容 | 可选 |
| `summary` | AI 解析摘要（可选） | 补充页面功能描述 | 可选 |

**完整 Schema 定义（以 T3.0.2 为准，此处增加校验规则）：**

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal

class FlowNodeSchema(BaseModel):
    """流程图节点 Schema - 用于接收前端传递的排序数据"""
    screen_id: int = Field(..., gt=0, description="UI 屏幕 ID")
    screen_order: int = Field(..., gt=0, description="前端排序序号，从 1 开始")
    flow_type: Literal['main', 'branch', 'exception', 'bypass'] = Field(
        ..., description="流程类型"
    )
    screen_name: str = Field(..., min_length=1, max_length=200, description="屏幕名称")
    ocr_text: Optional[str] = Field(None, max_length=5000, description="OCR 识别的页面文本")
    summary: Optional[str] = Field(None, max_length=1000, description="AI 解析摘要")

    @validator('screen_name')
    def screen_name_not_blank(cls, v):
        if not v.strip():
            raise ValueError('screen_name 不能为纯空白字符')
        return v.strip()

class FlowEdgeSchema(BaseModel):
    """流程图连线 Schema - 用于接收前端传递的连线关系"""
    source: str = Field(..., min_length=1, description="源节点 ID")
    target: str = Field(..., min_length=1, description="目标节点 ID")
    edge_type: Literal['normal', 'branch', 'exception', 'bypass'] = Field(
        ..., description="连线类型"
    )
    condition: Optional[str] = Field(None, max_length=500, description="触发条件/异常场景")
    label: str = Field(..., min_length=1, max_length=100, description="连线显示标签")

    @validator('label')
    def label_not_blank(cls, v):
        if not v.strip():
            raise ValueError('label 不能为纯空白字符')
        return v.strip()

class FlowSortDataSchema(BaseModel):
    """流程图排序完整数据 Schema"""
    nodes: List[FlowNodeSchema] = Field(..., min_items=1, description="节点列表")
    edges: List[FlowEdgeSchema] = Field(default_factory=list, description="连线列表")
    module_info: Optional[dict] = Field(None, description="模块基础信息")
```

**注意事项：**
- `FlowSortDataSchema` 不包含 `mode` 字段，`mode` 在 `AIGenerateEnhancedRequest` 层级定义
- `FlowNodeSchema` 不包含 `id` 和 `position` 字段，这些是前端 `@vue-flow` 内部使用的渲染字段，后端不需要
- `FlowEdgeSchema` 不包含 `id` 字段，后端通过 `source` + `target` 组合即可唯一标识连线

**验收标准：**
- [ ] Schema 定义正确，字段与 T3.0.2 完全一致
- [ ] 类型校验生效（传入错误类型时 Pydantic 抛出 ValidationError）
- [ ] 必填字段校验生效（缺少必填字段时抛出 ValidationError）
- [ ] 字符串长度限制生效（超长文本被拒绝）

---

### T3.2 新增 PromptBuilder 服务

**负责人：** 后端  
**预计耗时：** 2.5 小时  
**文件：** `app/services/case_generation_prompt_builder.py`

**任务背景：**

当前系统采用**多源数据融合策略**，整合需求文档、UI 原型图解析数据、测试点三类信息。PromptBuilder 的职责是将这三类信息与新增的"流程结构"维度融合，构建完整的 AI Prompt。

**数据融合关系：**

| 数据源 | 提供信息 | 在 Prompt 中的位置 |
|--------|----------|-------------------|
| 测试点 | 测试维度、优先级、覆盖范围 | `## 测试点信息` |
| 需求文档 | 业务规则、功能描述、验收标准 | `## 需求文档内容` |
| UI 原型图（原有） | 页面结构、元素信息、交互关系 | `## UI 原型图解析结果` |
| UI 原型图（新增） | 流程结构、页面顺序、分支关系 | `## UI 原型图流程结构` |

**任务内容：**

1. 创建 `PromptBuilder` 类
2. 实现 `build_graph_prompt()` 方法（融合多源数据）
3. 实现 `build_linear_prompt()` 方法（复用现有逻辑）
4. 实现流程解析逻辑（从 nodes/edges 构建流程树）

**核心代码框架：**

```python
from typing import List, Dict, Any, Optional

class PromptBuilder:
    """测试用例生成 Prompt 构建器"""
    
    @staticmethod
    def build_graph_prompt(
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        module_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建流程图模式的 Prompt"""
        
        # 1. 解析主干流程
        main_nodes = [n for n in nodes if n['flow_type'] == 'main']
        main_nodes.sort(key=lambda n: n.get('position', {}).get('x', 0))
        
        # 2. 解析分支/异常/旁路流程
        branch_edges = [e for e in edges if e['edge_type'] == 'branch']
        exception_edges = [e for e in edges if e['edge_type'] == 'exception']
        bypass_edges = [e for e in edges if e['edge_type'] == 'bypass']
        
        # 3. 构建 Prompt 各部分
        parts = []
        parts.append("你是一名资深测试工程师，拥有10年以上的测试经验。")
        parts.append("请根据以下流程结构生成详细的、可执行的测试用例。\n")
        
        # 模块信息
        if module_info:
            parts.append(f"## 模块信息")
            parts.append(module_info.get('name', ''))
            parts.append(module_info.get('description', ''))
            parts.append("")
        
        # 主干流程
        parts.append("### 主干流程（按顺序执行，必须完整覆盖）")
        for i, node in enumerate(main_nodes, 1):
            parts.append(
                f"步骤 {i}: [截图{i} - {node.get('screen_name', '')}] "
                f"{node.get('ocr_text', '')}"
            )
        parts.append("")
        
        # 分支流程
        if branch_edges:
            parts.append("### 分支流程（满足条件时执行，每个分支作为独立测试场景）")
            # 构建 screen_id -> node 映射
            node_map = {n['screen_id']: n for n in nodes}
            for idx, edge in enumerate(branch_edges, ord('A')):
                try:
                    target_screen_id = int(edge['target'])
                    source_screen_id = int(edge['source'])
                except (ValueError, TypeError):
                    continue
                target_node = node_map.get(target_screen_id, {})
                source_step = next(
                    (i for i, n in enumerate(main_nodes, 1) if n['screen_id'] == source_screen_id),
                    '?'
                )
                parts.append(
                    f"分支 {chr(idx)}: 从步骤 {source_step} 分支，"
                    f"触发条件「{edge.get('condition', '未指定')}」"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] "
                    f"{target_node.get('ocr_text', '')}"
                )
            parts.append("")
        
        # 异常流程
        if exception_edges:
            parts.append("### 异常流程（异常场景下触发，需标注异常场景和预期错误提示）")
            node_map = {n['screen_id']: n for n in nodes}
            for idx, edge in enumerate(exception_edges, ord('A')):
                try:
                    target_screen_id = int(edge['target'])
                    source_screen_id = int(edge['source'])
                except (ValueError, TypeError):
                    continue
                target_node = node_map.get(target_screen_id, {})
                source_step = next(
                    (i for i, n in enumerate(main_nodes, 1) if n['screen_id'] == source_screen_id),
                    '?'
                )
                parts.append(
                    f"异常 {chr(idx)}: 从步骤 {source_step} 异常跳转，"
                    f"异常场景「{edge.get('condition', '未指定')}」"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] "
                    f"{target_node.get('ocr_text', '')}"
                )
            parts.append("")
        
        # 旁路流程
        if bypass_edges:
            parts.append("### 旁路流程（出现时机和关闭方式，不影响主流程）")
            node_map = {n['screen_id']: n for n in nodes}
            for idx, edge in enumerate(bypass_edges, ord('A')):
                try:
                    target_screen_id = int(edge['target'])
                    source_screen_id = int(edge['source'])
                except (ValueError, TypeError):
                    continue
                target_node = node_map.get(target_screen_id, {})
                source_step = next(
                    (i for i, n in enumerate(main_nodes, 1) if n['screen_id'] == source_screen_id),
                    '?'
                )
                parts.append(
                    f"旁路 {chr(idx)}: 进入步骤 {source_step} 时{edge.get('condition', '自动弹出')}，"
                    f"关闭后继续主流程"
                )
                parts.append(
                    f"  → [截图 - {target_node.get('screen_name', '')}] "
                    f"{target_node.get('ocr_text', '')}"
                )
            parts.append("")
        
        # 生成要求
        parts.append("## 生成要求")
        parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        parts.append("2. 每个分支流程需标注触发条件，作为独立测试场景生成用例")
        parts.append("3. 每个异常流程需标注异常场景和预期错误提示，生成异常测试用例")
        parts.append("4. 旁路流程需标注出现时机和关闭方式，作为前置步骤处理")
        parts.append("5. 输出格式：JSON，包含 title/module/precondition/steps/expected_result/case_type/priority/case_category")
        
        return "\n".join(parts)
    
    @staticmethod
    def build_linear_prompt(screens: List[Dict[str, Any]]) -> str:
        """构建线性模式的 Prompt（复用现有逻辑）"""
        # TODO: 复用 case_generation_ai.py 中的 _build_generation_prompt
        pass
```

**验收标准：**
- [ ] `build_graph_prompt` 输出符合 2.4.1 定义的模板
- [ ] 主干/分支/异常/旁路流程正确解析
- [ ] 单元测试覆盖率 ≥ 95%

---

### T3.3 修改 API 端点接收 mode 参数

**负责人：** 后端  
**预计耗时：** 1 小时  
**文件：** `app/api/v1/endpoints/test_case_ai_enhanced.py`

**任务内容：**

1. 在 `AIGenerateEnhancedRequest` 中增加 `mode` 字段
2. 根据 mode 调用不同的 Prompt 构建方法
3. 保持向后兼容（默认 mode='linear'）

**修改内容：**

```python
class AIGenerateEnhancedRequest(BaseModel):
    # ... 现有字段 ...
    mode: Literal['linear', 'graph'] = Field(default='linear', description="排序模式")
    flow_sort_data: Optional[FlowSortDataSchema] = Field(None, description="流程图排序数据")

# 在端点中处理
if request_data.mode == 'graph' and request_data.flow_sort_data:
    prompt = PromptBuilder.build_graph_prompt(
        nodes=request_data.flow_sort_data.nodes,
        edges=request_data.flow_sort_data.edges,
        module_info=request_data.flow_sort_data.module_info
    )
else:
    prompt = PromptBuilder.build_linear_prompt(screens_data)
```

**验收标准：**
- [ ] API 可接收 mode 参数
- [ ] graph 模式下正确调用新 Prompt 构建逻辑
- [ ] linear 模式下保持原有行为

---

## M4: AI Prompt 优化 + 回滚开关（0.25 天）

### T4.1 优化 Prompt 模板

**负责人：** 后端  
**预计耗时：** 1 小时

**任务内容：**

1. 基于 T3.2 的 Prompt 模板，增加输出格式约束
2. 增加示例用例，引导 AI 输出正确格式
3. 增加分支/异常用例的生成要求

**验收标准：**
- [ ] AI 输出 JSON 格式正确率 ≥ 95%
- [ ] 分支/异常用例完整生成

---

### T4.2 实现回滚开关

**负责人：** 前端 + 后端  
**预计耗时：** 1 小时

**任务内容：**

1. 前端：在 ai-generate.vue 顶部添加模式切换开关
2. 后端：确保 linear 模式完全兼容原有逻辑
3. 配置：支持通过环境变量默认模式

**验收标准：**
- [ ] 切换线性模式后，功能与优化前完全一致
- [ ] 切换流程图模式后，新功能正常

---

## M5: 10 个真实场景验证（0.25 天）

### T5.1 准备测试场景

**负责人：** 全员  
**预计耗时：** 30 分钟

**测试场景清单：**

| 编号 | 场景 | 覆盖流程类型 |
|------|------|--------------|
| 1 | 后台管理系统-查询功能 | 主干 + 分支（高级筛选）+ 异常（非法输入） |
| 2 | 电商系统-下单流程 | 主干 + 分支（优惠券）+ 异常（库存不足） |
| 3 | 用户注册流程 | 主干 + 异常（用户名重复）+ 旁路（协议弹窗） |
| 4 | 文件上传功能 | 主干 + 异常（格式错误/超大文件） |
| 5 | 权限管理-角色分配 | 主干 + 分支（批量操作）+ 异常（权限不足） |
| 6 | 数据导出功能 | 主干 + 分支（筛选导出）+ 异常（数据为空） |
| 7 | 审批流程 | 主干 + 分支（驳回重审）+ 旁路（催办提醒） |
| 8 | 支付流程 | 主干 + 分支（优惠券/积分）+ 异常（余额不足） |
| 9 | 消息通知设置 | 主干 + 旁路（订阅弹窗） |
| 10 | 系统登录 | 主干 + 异常（密码错误/账号锁定）+ 旁路（验证码） |

---

### T5.2 执行测试并统计指标

**负责人：** 测试  
**预计耗时：** 2 小时

**测试流程：**

1. 每个场景使用新模式生成用例
2. 记录生成结果：可用/需修改/不可用
3. 统计分支/异常覆盖率
4. 记录测试人员修改时间
5. 填写满意度问卷

**验收标准：**
- [ ] 10 个场景全部测试完成
- [ ] 可用率 ≥ 90%
- [ ] 分支/异常覆盖率 ≥ 90%
- [ ] 手动修改频次降低 ≥ 60%
- [ ] 满意度 ≥ 8 分

---

### T5.3 回滚决策

**负责人：** 全员  
**预计耗时：** 30 分钟

**决策标准：**

| 指标 | 达标 | 未达标 |
|------|------|--------|
| 可用率 ≥ 90% | 上线 | 回滚到线性模式 |
| 分支覆盖率 ≥ 90% | 上线 | 优化 Prompt 后重测 |
| 满意度 ≥ 8 分 | 上线 | 收集反馈后迭代 |

---

## M6: API 接口变更说明（参考）

### API 变更清单

| 接口路径 | 请求方法 | 修改类型 | 变更内容 | 影响范围 |
|----------|----------|----------|----------|----------|
| `/api/v1/testCase/ai-generate-enhanced` | POST | 新增参数 | 新增 `mode`（string, 默认 'linear'）、`flow_sort_data`（object, 可选） | 前端调用需适配 |
| `/api/v1/ui-prototype/projects/{project_id}/screens` | GET | 无需修改 | 返回数据已包含 `ui_spec`、`summary`，前端直接使用 | 无 |
| `/api/v1/file/preview-screen/{screen_id}` | GET | 无需修改 | 截图预览接口，流程图节点缩略图使用 | 无 |

### 新增参数详细说明

**接口：** `POST /api/v1/testCase/ai-generate-enhanced`

**新增字段：**

```json
{
  "mode": "graph",
  "flow_sort_data": {
    "nodes": [
      {
        "screen_id": 101,
        "screen_order": 1,
        "flow_type": "main",
        "screen_name": "查询页",
        "summary": "后台管理系统查询功能页面，包含筛选条件输入框和查询按钮",
        "ocr_text": "高级筛选 查询 重置"
      },
      {
        "screen_id": 102,
        "screen_order": 2,
        "flow_type": "branch",
        "screen_name": "高级筛选页",
        "summary": "高级筛选弹窗，支持多条件组合查询",
        "ocr_text": "时间范围 状态 关键词 确定 取消"
      }
    ],
    "edges": [
      {
        "source": "101",
        "target": "102",
        "edge_type": "branch",
        "condition": "用户点击高级筛选按钮",
        "label": "条件分支"
      }
    ],
    "module_info": {
      "name": "查询管理模块",
      "description": "支持多条件组合查询和数据展示"
    }
  }
}
```

**字段约束：**

| 字段 | 类型 | 必填 | 约束 | 示例 |
|------|------|------|------|------|
| `mode` | string | 是 | 枚举值：'linear' \| 'graph' | `'graph'` |
| `flow_sort_data` | object | graph 模式必填 | 包含 nodes、edges、module_info | 见上方 JSON |
| `flow_sort_data.nodes` | array | 是 | 至少 1 个节点 | 见上方 JSON |
| `flow_sort_data.nodes[].screen_id` | int | 是 | 必须 > 0 | `101` |
| `flow_sort_data.nodes[].screen_order` | int | 是 | 必须 > 0，从 1 开始 | `1` |
| `flow_sort_data.nodes[].flow_type` | string | 是 | 枚举值：'main' \| 'branch' \| 'exception' \| 'bypass' | `'main'` |
| `flow_sort_data.nodes[].screen_name` | string | 是 | 1-200 字符，不能为纯空白 | `'查询页'` |
| `flow_sort_data.nodes[].ocr_text` | string | 否 | 最大 5000 字符 | `'高级筛选 查询 重置'` |
| `flow_sort_data.nodes[].summary` | string | 否 | 最大 1000 字符 | `'后台管理系统查询功能页面...'` |
| `flow_sort_data.edges` | array | 否 | 可为空数组 | 见上方 JSON |
| `flow_sort_data.edges[].source` | string | 是 | screen_id 的字符串形式 | `'101'` |
| `flow_sort_data.edges[].target` | string | 是 | screen_id 的字符串形式 | `'102'` |
| `flow_sort_data.edges[].edge_type` | string | 是 | 枚举值：'normal' \| 'branch' \| 'exception' \| 'bypass' | `'branch'` |
| `flow_sort_data.edges[].condition` | string | 否 | 最大 500 字符 | `'用户点击高级筛选按钮'` |
| `flow_sort_data.edges[].label` | string | 是 | 1-100 字符，不能为纯空白 | `'条件分支'` |
| `flow_sort_data.module_info` | object | 否 | 包含 name、description | 见上方 JSON |

**向后兼容说明：**

- `mode` 默认值为 `'linear'`，不传此字段时按原有逻辑处理
- `flow_sort_data` 为可选字段，不传时按原有逻辑处理
- 原有字段（`project_id`、`description`、`ui_screen_ids` 等）行为不变

---

## M7: 测试用例设计矩阵

### 测试场景矩阵

| 场景编号 | 场景名称 | 数据源组合 | 覆盖流程类型 | 验证点 | 预期结果 |
|----------|----------|------------|--------------|--------|----------|
| S1 | 后台管理系统-查询功能 | 仅 UI | 主干 + 分支（高级筛选） | 步骤顺序正确、分支触发条件明确 | 可用率≥90% |
| S2 | 电商系统-下单流程 | UI + 需求 | 主干 + 分支（优惠券）+ 异常（库存不足） | 分支覆盖率≥90%、异常场景完整 | 可用率≥90% |
| S3 | 用户注册流程 | UI + 测试点 | 主干 + 异常（用户名重复）+ 旁路（协议弹窗） | 旁路流程标注出现时机 | 可用率≥90% |
| S4 | 文件上传功能 | 仅 UI | 主干 + 异常（格式错误/超大文件） | 异常场景覆盖完整 | 可用率≥90% |
| S5 | 权限管理-角色分配 | UI + 需求 + 测试点 | 主干 + 分支（批量操作）+ 异常（权限不足） | 多源数据融合效果最佳 | 可用率≥95% |
| S6 | 数据导出功能 | UI + 需求 | 主干 + 分支（筛选导出）+ 异常（数据为空） | 分支/异常均覆盖 | 可用率≥90% |
| S7 | 审批流程 | UI + 测试点 | 主干 + 分支（驳回重审）+ 旁路（催办提醒） | 复杂流程逻辑正确 | 可用率≥90% |
| S8 | 支付流程 | UI + 需求 + 测试点 | 主干 + 分支（优惠券/积分）+ 异常（余额不足） | 完整多源融合 | 可用率≥95% |
| S9 | 消息通知设置 | 仅 UI | 主干 + 旁路（订阅弹窗） | 旁路流程处理正确 | 可用率≥90% |
| S10 | 系统登录 | UI + 需求 | 主干 + 异常（密码错误/账号锁定）+ 旁路（验证码） | 异常/旁路均覆盖 | 可用率≥90% |

### 回归测试用例

| 用例编号 | 测试场景 | 验证点 | 预期结果 |
|----------|----------|--------|----------|
| R1 | linear 模式-仅 UI | 行为与优化前完全一致 | 用例生成结果与优化前相同 |
| R2 | linear 模式-UI + 需求 | 行为与优化前完全一致 | 用例生成结果与优化前相同 |
| R3 | linear 模式-UI + 需求 + 测试点 | 行为与优化前完全一致 | 用例生成结果与优化前相同 |
| R4 | graph 模式-无连线 | 仅主干流程，无分支/异常 | 用例仅覆盖主干流程 |
| R5 | graph 模式-仅分支 | 主干 + 分支，无异常 | 用例覆盖主干和分支 |
| R6 | graph 模式-仅异常 | 主干 + 异常，无分支 | 用例覆盖主干和异常 |
| R7 | graph 模式-完整流程 | 主干 + 分支 + 异常 + 旁路 | 用例覆盖所有流程类型 |
| R8 | 空 OCR 文本 | 节点无 OCR 文本 | 用例生成正常，不报错 |
| R9 | 超长 OCR 文本 | OCR 文本超过 5000 字符 | 后端校验拒绝，返回 422 |
| R10 | 节点顺序调整 | 前端拖拽调整节点顺序 | 后端接收的 screen_order 与前端一致 |

### 性能测试用例

| 用例编号 | 测试场景 | 验证点 | 预期结果 |
|----------|----------|--------|----------|
| P1 | 50 个节点 | 画布渲染性能 | 帧率 ≥ 30fps，无明显卡顿 |
| P2 | 100 条连线 | 画布渲染性能 | 帧率 ≥ 30fps，无明显卡顿 |
| P3 | Prompt 长度 | Prompt 总长度接近 AI 模型限制 | 有截断处理，不超出限制 |
| P4 | 并发请求 | 5 个用户同时生成用例 | 后端正常处理，无数据串扰 |

---

## 任务依赖关系

```
T1.1 安装依赖
   ↓
T1.2 创建 FlowSortEditor
   ↓
T1.3 创建 FlowNodeCard ──→ T1.4 创建 EdgeConditionDialog
   ↓
T1.5 创建 Store
   ↓
T1.6 原型测试
   ↓
T2.1 集成到 ai-generate.vue
   ↓
T2.2 自动布局 ──→ T2.3 Prompt 预览
   ↓
T3.0 数据传递链路修复（关键）
   ↓
T3.1 Schema 定义 ──→ T3.2 PromptBuilder ──→ T3.3 API 适配
   ↓
T4.1 Prompt 优化 ──→ T4.2 回滚开关
   ↓
T5.1 准备场景 ──→ T5.2 执行测试 ──→ T5.3 回滚决策
```

---

## 风险检查清单

- [ ] @vue-flow 与 Vue 3.4 版本兼容
- [ ] 画布节点超过 50 个时性能正常
- [ ] 移动端浏览器不兼容流程图模式（提示切换线性模式）
- [ ] OCR 文本为空时节点显示正常
- [ ] 网络异常时图片加载失败有兜底显示
- [ ] Prompt 长度超过 AI 模型限制时有截断处理
