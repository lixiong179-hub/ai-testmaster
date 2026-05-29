<template>
  <transition name="panel-slide-left">
    <div v-if="visible" class="main-step-list">
      <div class="step-list-header">
        <span class="step-list-title">主干步骤</span>
        <el-tag size="small" type="primary" effect="plain">{{ mainSteps.length }} 步</el-tag>
        <el-button size="small" text @click="handleClose"
          ><el-icon :size="14"><Close /></el-icon
        ></el-button>
      </div>
      <div class="step-list-body">
        <div
          v-for="(step, index) in mainSteps"
          :key="step.id"
          class="step-item"
          :class="{
            'is-active': activeNodeId === step.id,
            'is-drag-over': dragOverIndex === index,
            'is-dragging': dragIndex === index,
            'has-issue': step.hasIssue,
          }"
          :draggable="true"
          @click="handleStepClick(step.id)"
          @dragstart="handleDragStart(index, $event)"
          @dragover.prevent="handleDragOver(index)"
          @dragleave="handleDragLeave"
          @drop="handleDrop(index)"
          @dragend="handleDragEnd"
        >
          <div class="step-order">{{ step.mainOrder }}</div>
          <div class="step-info">
            <div class="step-name" :title="step.screenName">{{ step.screenName }}</div>
            <div v-if="step.hasIssue" class="step-issue">
              <el-icon :size="12"><Warning /></el-icon>
              {{ step.issueText }}
            </div>
          </div>
          <el-icon class="step-drag-handle" :size="14"><Rank /></el-icon>
        </div>
        <div v-if="mainSteps.length === 0" class="step-list-empty">暂无主干节点</div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElIcon } from 'element-plus'
import { Close, Rank, Warning } from '@element-plus/icons-vue'
import { useFlowSortEditor } from '@/composables/flowSort/useFlowSortEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'
import { getNodeData } from '@/composables/useFlowEditor'

interface MainStepItem {
  id: string
  screenName: string
  mainOrder: number
  hasIssue: boolean
  issueText: string
}

defineProps<{
  visible: boolean
  activeNodeId: string | null
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  'locate-node': [nodeId: string]
  reorder: [orderedIds: string[]]
}>()

const ctx = useFlowSortEditor()

const mainSteps = computed<MainStepItem[]>(() => {
  const nodes = ctx.vueFlowNodes.value as FlowEditorNode[]
  const edges = ctx.vueFlowEdges.value as FlowGraphEdge[]
  const mainNodes = nodes
    .filter((n) => getNodeData(n).flow_type === 'main')
    .sort((a, b) => (getNodeData(a).main_order ?? 0) - (getNodeData(b).main_order ?? 0))

  const orders = mainNodes.map((n) => getNodeData(n).main_order ?? 0)
  const seenOrders = new Map<number, number>()
  orders.forEach((o) => seenOrders.set(o, (seenOrders.get(o) ?? 0) + 1))

  const maxOrder = orders.length > 0 ? Math.max(...orders) : 0
  const orderSet = new Set(orders.filter((o) => o > 0))
  const hasGap = maxOrder > 0 && orders.length > 1 && orderSet.size < maxOrder

  const mainNodeIds = new Set(mainNodes.map((n) => n.id))
  const connectedMainIds = new Set<string>()
  edges.forEach((e) => {
    if (mainNodeIds.has(e.source) || mainNodeIds.has(e.target)) {
      if (mainNodeIds.has(e.source)) connectedMainIds.add(e.source)
      if (mainNodeIds.has(e.target)) connectedMainIds.add(e.target)
    }
  })

  return mainNodes.map((n) => {
    const d = getNodeData(n)
    const order = d.main_order ?? 0
    const isDuplicate = (seenOrders.get(order) ?? 0) > 1
    const isOrphan = mainNodes.length > 1 && !connectedMainIds.has(n.id)
    const hasIssue =
      isDuplicate ||
      order <= 0 ||
      isOrphan ||
      (hasGap && order > 0 && !orderSet.has(order - 1) && order > 1)
    let issueText = ''
    if (order <= 0) issueText = '缺少顺序号'
    else if (isDuplicate) issueText = '顺序号重复'
    else if (isOrphan) issueText = '孤立节点'
    else if (hasGap && order > 1 && !orderSet.has(order - 1)) issueText = '顺序断档'

    return {
      id: n.id,
      screenName: d.screen_name || '',
      mainOrder: order,
      hasIssue,
      issueText,
    }
  })
})

const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

const handleStepClick = (nodeId: string) => {
  emit('locate-node', nodeId)
}

const handleDragStart = (index: number, event: DragEvent) => {
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

const handleDragOver = (index: number) => {
  dragOverIndex.value = index
}

const handleDragLeave = () => {
  dragOverIndex.value = null
}

const handleDrop = (targetIndex: number) => {
  const fromIndex = dragIndex.value
  if (fromIndex === null || fromIndex === targetIndex) {
    dragIndex.value = null
    dragOverIndex.value = null
    return
  }
  const steps = [...mainSteps.value]
  const [moved] = steps.splice(fromIndex, 1)
  steps.splice(targetIndex, 0, moved)
  emit(
    'reorder',
    steps.map((s) => s.id)
  )
  dragIndex.value = null
  dragOverIndex.value = null
}

const handleDragEnd = () => {
  dragIndex.value = null
  dragOverIndex.value = null
}

const handleClose = () => {
  emit('update:visible', false)
}
</script>

<style scoped lang="scss">
.main-step-list {
  width: 220px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.04);
}

.step-list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);

  .step-list-title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
    flex: 1;
  }
}

.step-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.15s ease;
  border-left: 3px solid transparent;

  &:hover {
    background: #f5f7fa;
  }

  &.is-active {
    background: #ecf5ff;
    border-left-color: #409eff;
  }

  &.is-drag-over {
    border-top: 2px solid #409eff;
  }

  &.is-dragging {
    opacity: 0.4;
  }

  &.has-issue {
    background: #fef0f0;
    border-left-color: #f56c6c;
  }
}

.step-order {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: #ecf5ff;
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-info {
  flex: 1;
  min-width: 0;
}

.step-name {
  font-size: 12px;
  color: #303133;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-issue {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: #f56c6c;
  margin-top: 2px;
}

.step-drag-handle {
  color: #c0c4cc;
  cursor: grab;
  flex-shrink: 0;

  &:hover {
    color: #909399;
  }
}

.step-list-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: #909399;
}

.panel-slide-left-enter-active {
  transition: all 0.25s ease;
}
.panel-slide-left-leave-active {
  transition: all 0.2s ease;
}
.panel-slide-left-enter-from {
  transform: translateX(-100%);
  opacity: 0;
}
.panel-slide-left-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}
</style>
