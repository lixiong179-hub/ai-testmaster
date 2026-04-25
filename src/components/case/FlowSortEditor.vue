<template>
  <div class="flow-sort-editor" @keydown="handleKeyDown" tabindex="0" ref="editorRef">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <div class="editor-heading">
          <span class="editor-title">页面流程编辑</span>
          <span class="editor-subtitle">拖拽节点调整布局，主干顺序使用前移/后移显式控制</span>
        </div>
      </div>
      <div class="toolbar-actions">
        <el-button-group class="action-group">
          <el-tooltip content="自动布局 (Ctrl+L)" placement="bottom">
            <el-button size="default" @click="handleAutoLayout">
              <el-icon><Grid /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="预览 Prompt (Ctrl+P)" placement="bottom">
            <el-button size="default" @click="handlePreviewPrompt">
              <el-icon><View /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tooltip content="撤销 (Ctrl+Z)" placement="bottom">
            <el-button size="default" @click="handleUndo" :disabled="!canUndo">
              <el-icon><RefreshLeft /></el-icon>
            </el-button>
          </el-tooltip>
        </el-button-group>
        <el-divider direction="vertical" />
        <div v-if="selectedNodes.length > 0" class="selection-info">
          <el-tag type="primary" size="small" effect="plain">
            已选 {{ selectedNodes.length }} 个节点
          </el-tag>
          <el-button size="small" type="danger" @click="handleDeleteSelected">
            <el-icon><Delete /></el-icon>
            删除
          </el-button>
        </div>
        <div v-if="getSelectedMainNodeId(vueFlowNodes)" class="main-order-actions">
          <el-tag type="success" size="small" effect="plain">
            主干第 {{ getSelectedMainOrder(vueFlowNodes) }} 步
          </el-tag>
          <el-button size="small" @click="moveSelectedMainNode(-1)" :disabled="!canMoveMainBackward()">
            主干前移
          </el-button>
          <el-button size="small" @click="moveSelectedMainNode(1)" :disabled="!canMoveMainForward()">
            主干后移
          </el-button>
        </div>
        <div class="zoom-controls">
          <el-button size="small" circle @click="zoomOut" :disabled="currentZoom <= 0.2">
            <el-icon><ZoomOut /></el-icon>
          </el-button>
          <span class="zoom-level">{{ Math.round(currentZoom * 100) }}%</span>
          <el-button size="small" circle @click="zoomIn" :disabled="currentZoom >= 4">
            <el-icon><ZoomIn /></el-icon>
          </el-button>
        </div>
      </div>
    </div>

    <div class="editor-container">
      <div class="graph-mode">
        <VueFlow
          v-model:nodes="vueFlowNodes"
          v-model:edges="vueFlowEdges"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          :default-edge-options="defaultEdgeOptions"
          :min-zoom="0.2"
          :max-zoom="4"
          :nodes-draggable="true"
          :nodes-connectable="true"
          :elements-selectable="true"
          fit-view-on-init
          @connect="onConnect"
          @node-drag-stop="onNodeDragStop"
          @edge-update="onEdgeUpdate"
          @pane-click="handlePaneClick"
          @node-click="handleNodeClick"
          @selection-change="handleSelectionChange"
        >
          <Background pattern-color="#e4e7ed" :gap="20" />
          <Controls />
          <MiniMap :node-color="minimapNodeColor" :node-stroke-color="minimapNodeStroke" />
          <template #node-custom="nodeProps">
            <FlowNodeCard
              :data="nodeProps.data"
              :is-selected="selectedNodes.includes(nodeProps.id)"
              :is-dragging="draggingNodeId === nodeProps.id"
              @update:flow-type="(type: string) => handleFlowTypeChange(nodeProps.id, type)"
              @preview="handleNodePreview(nodeProps.data)"
            />
          </template>
        </VueFlow>
      </div>
    </div>

    <EdgeConditionDialog
      v-model:visible="conditionDialogVisible"
      :edge-data="currentEdgeForm"
      @confirm="onEdgeConditionConfirm"
    />

    <FlowTypeConfigDialog
      v-model:visible="flowTypeConfigVisible"
      :flow-type="(pendingFlowTypeChange?.type as Exclude<FlowNodeData['flow_type'], 'main'>) || 'branch'"
      :main-node-options="mainNodeOptions"
      :initial-data="pendingFlowMeta"
      @confirm="handleFlowTypeConfigConfirm"
    />

    <transition name="tip-fade">
      <div v-if="showShortcutsTip" class="shortcuts-tip">
        <kbd>Delete</kbd> 删除选中 | <kbd>Ctrl+Z</kbd> 撤销 | <kbd>Space</kbd> 预览图片 |
        <kbd>Esc</kbd> 取消选择
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import {
  VueFlow,
  useVueFlow,
  type Connection as FlowConnection,
  type Edge,
  type Node,
} from '@vue-flow/core'
import { Background, Controls, MiniMap } from '@vue-flow/additional-components'
import { ElMessage } from 'element-plus'
import {
  Grid,
  View,
  RefreshLeft,
  Delete,
  ZoomIn,
  ZoomOut,
} from '@element-plus/icons-vue'
import FlowNodeCard from './FlowNodeCard.vue'
import EdgeConditionDialog from './EdgeConditionDialog.vue'
import FlowTypeConfigDialog from './FlowTypeConfigDialog.vue'
import type { FlowNodeData, FlowEdgeData, FlowMetaData } from '@/store/flowSort'
import type { UIScreen } from '@/api/uiPrototype'
import {
  type EditorNodeData,
  type FlowEditorNode,
  EDGE_STYLES,
  getNodeData,
  getMainNodesInOrder,
  getOrderedNodesForSubmit,
  normalizeMainNodeOrders,
  layoutMainNodesByOrder,
  getMainNodeCount,
  createEdgeMarker,
  normalizeEdges,
  validateFlowData,
  useFlowHistory,
  useFlowSelection,
} from '@/composables/useFlowEditor'

const props = defineProps<{
  screens: UIScreen[]
  screenImageUrls?: Record<number, string>
  moduleInfo?: { name: string; description: string }
}>()

const emit = defineEmits<{
  'update:sort-data': [data: { mode: string; nodes: FlowNodeData[]; edges: FlowEdgeData[] }]
  'preview-prompt': []
  'preview-screen': [screen: { screen_id: number; screen_name: string; image_url?: string }]
}>()

const editorRef = ref<HTMLElement | null>(null)
const conditionDialogVisible = ref(false)
const currentConnection = ref<{ source: string; target: string } | null>(null)
const currentEdgeForm = ref<{
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
} | null>(null)
const currentZoom = ref(1)
const showShortcutsTip = ref(true)

const flowTypeConfigVisible = ref(false)
const pendingFlowTypeChange = ref<{ nodeId: string; type: string } | null>(null)
const pendingFlowMeta = ref<FlowMetaData | null>(null)

const { zoomIn: flowZoomIn, zoomOut: flowZoomOut, viewport } = useVueFlow()

const vueFlowNodes = ref<FlowEditorNode[]>([])
const vueFlowEdges = ref<Edge[]>([])

const { historyStack, canUndo, saveToHistory, undo } = useFlowHistory()
const { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder } = useFlowSelection()

const getScreenImageUrl = (screen: UIScreen) => {
  if (!screen.id) return ''
  return props.screenImageUrls?.[screen.id] || ''
}

const defaultEdgeOptions = {
  type: 'default',
  markerEnd: createEdgeMarker(EDGE_STYLES.normal.stroke),
  style: EDGE_STYLES.normal,
}

const hydrateNodesWithImages = (nodes: FlowEditorNode[]) =>
  nodes.map((node) => ({
    ...node,
    data: {
      ...getNodeData(node),
      image_url:
        props.screenImageUrls?.[getNodeData(node).screen_id] || getNodeData(node).image_url || '',
    },
  }))

const syncHistoryImages = () => {
  historyStack.value = historyStack.value.map((snapshot) => ({
    nodes: hydrateNodesWithImages(snapshot.nodes),
    edges: normalizeEdges(snapshot.edges),
  }))
}

const minimapNodeColor = (node: Node) => {
  const flowType = node.data?.flow_type as string
  const colors: Record<string, string> = {
    main: '#409eff',
    branch: '#67c23a',
    exception: '#f56c6c',
    bypass: '#e6a23c',
  }
  return colors[flowType] || '#409eff'
}

const minimapNodeStroke = () => '#fff'

const emitSortData = () => {
  const flowNodes: FlowNodeData[] = vueFlowNodes.value.map((node) => ({
    id: node.id,
    screen_id: getNodeData(node).screen_id,
    screen_name: getNodeData(node).screen_name,
    summary: getNodeData(node).summary,
    ui_spec_elements: getNodeData(node).ui_spec_elements,
    flow_type: getNodeData(node).flow_type,
    main_order: getNodeData(node).main_order,
    image_url: getNodeData(node).image_url,
    position: node.position,
    flow_meta: getNodeData(node).flow_meta,
  }))
  const flowEdges: FlowEdgeData[] = vueFlowEdges.value.map((edge) => {
    const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
    const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
    const sourceScreenId = sourceNode ? getNodeData(sourceNode).screen_id : undefined
    const targetScreenId = targetNode ? getNodeData(targetNode).screen_id : undefined
    return {
      id: edge.id,
      source: String(sourceScreenId || edge.source),
      target: String(targetScreenId || edge.target),
      edge_type: edge.data?.edge_type || 'normal',
      condition: edge.data?.condition,
      label: typeof edge.label === 'string' ? edge.label : String(edge.label || ''),
      pre_action: edge.data?.pre_action,
      note: edge.data?.note,
    }
  })
  emit('update:sort-data', { mode: 'graph', nodes: flowNodes, edges: flowEdges })
}

watch(
  () => props.screens,
  (newScreens) => {
    vueFlowNodes.value = normalizeMainNodeOrders(
      newScreens.map((screen, index) => ({
        id: `node_${screen.id}`,
        type: 'custom',
        position: { x: index * 280, y: 0 },
        data: {
          screen_id: screen.id,
          screen_name: screen.screen_name,
          summary: screen.summary,
          ui_spec_elements: (screen.ui_spec?.elements || []).map((el) => ({
            type: el.type,
            label: el.label,
            semantic: el.semantic_hint || el.description,
            position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
            interactive: el.interactive,
          })),
          flow_type: 'main' as const,
          main_order: index + 1,
          image_url: getScreenImageUrl(screen),
          element_count: screen.element_count,
        },
      }))
    )
    vueFlowEdges.value = []
    saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
    emitSortData()
  },
  { immediate: true }
)

watch(
  () => props.screenImageUrls,
  (newImageUrls) => {
    if (!newImageUrls || vueFlowNodes.value.length === 0) return
    vueFlowNodes.value = hydrateNodesWithImages(vueFlowNodes.value)
    syncHistoryImages()
  },
  { deep: true }
)

watch(
  () => props.moduleInfo,
  () => emitSortData()
)

watch(
  viewport,
  (nextViewport) => {
    currentZoom.value = nextViewport?.zoom ?? 1
  },
  { deep: true, immediate: true }
)

const onConnect = (connection: FlowConnection) => {
  currentConnection.value = { source: connection.source, target: connection.target }
  currentEdgeForm.value = null
  conditionDialogVisible.value = true
}

const onEdgeConditionConfirm = (edgeData: {
  edge_type: string
  condition: string | null
  label: string
}) => {
  if (!currentConnection.value) return
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  const style = EDGE_STYLES[edgeData.edge_type] || EDGE_STYLES.normal
  const newEdge: Edge = {
    id: `edge_${Date.now()}`,
    source: currentConnection.value.source,
    target: currentConnection.value.target,
    type: 'default',
    animated: edgeData.edge_type !== 'normal',
    style,
    label: edgeData.label,
    data: { edge_type: edgeData.edge_type, condition: edgeData.condition },
  }
  vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, newEdge])
  conditionDialogVisible.value = false
  currentConnection.value = null
  emitSortData()
}

const onEdgeUpdate = () => {
  vueFlowEdges.value = normalizeEdges(vueFlowEdges.value)
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  emitSortData()
}

const onNodeDragStop = () => {
  draggingNodeId.value = null
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  emitSortData()
}

const handleFlowTypeChange = (nodeId: string, type: string) => {
  if (type === 'main') {
    saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
    const nextMainOrder = getMainNodesInOrder(vueFlowNodes.value).length + 1
    vueFlowNodes.value = normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (node.id !== nodeId) return node
        const nodeData = getNodeData(node)
        return {
          ...node,
          data: {
            ...nodeData,
            flow_type: type as EditorNodeData['flow_type'],
            main_order: nodeData.main_order ?? nextMainOrder,
            flow_meta: undefined,
          },
        }
      })
    )
    emitSortData()
    return
  }

  const node = vueFlowNodes.value.find((n) => n.id === nodeId)
  if (!node) return

  pendingFlowTypeChange.value = { nodeId, type }
  pendingFlowMeta.value = getNodeData(node).flow_meta || null
  flowTypeConfigVisible.value = true
}

/**
 * 主干节点选项列表，供弹窗选择挂靠主干节点。
 * 仅包含 flow_type 为 main 的节点，按 main_order 排序。
 */
const mainNodeOptions = computed(() =>
  getMainNodesInOrder(vueFlowNodes.value).map((node) => ({
    id: node.id,
    screen_id: getNodeData(node).screen_id,
    screen_name: getNodeData(node).screen_name,
    main_order: getNodeData(node).main_order,
  }))
)

/**
 * 处理流程类型配置弹窗确认事件。
 * 更新节点类型和元数据，并自动创建/更新从挂靠主干节点指向当前节点的语义边。
 *
 * @param meta - 用户填写的流程类型配置数据
 * @remarks
 * - 若当前节点已存在同类型边，则替换旧边以保留 edge id
 * - 主干节点切换为分支/异常/旁路时，清除 main_order
 * - 变更后自动保存到历史栈并触发数据输出
 */
const handleFlowTypeConfigConfirm = (meta: FlowMetaData) => {
  if (!pendingFlowTypeChange.value) return

  const { nodeId, type } = pendingFlowTypeChange.value
  const parentNodeId = meta.parent_main_node_id

  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)

  vueFlowNodes.value = normalizeMainNodeOrders(
    vueFlowNodes.value.map((node) => {
      if (node.id !== nodeId) return node
      const nodeData = getNodeData(node)
      return {
        ...node,
        data: {
          ...nodeData,
          flow_type: type as EditorNodeData['flow_type'],
          main_order: undefined,
          flow_meta: meta,
        },
      }
    })
  )

  if (parentNodeId) {
    const existingEdgeIndex = vueFlowEdges.value.findIndex(
      (e) => e.target === nodeId && e.data?.edge_type === type
    )
    const newEdge: Edge = {
      id: existingEdgeIndex >= 0 ? vueFlowEdges.value[existingEdgeIndex].id : `edge_${Date.now()}`,
      source: parentNodeId,
      target: nodeId,
      type: 'default',
      animated: true,
      style: EDGE_STYLES[type] || EDGE_STYLES.normal,
      label: `${type === 'branch' ? '分支' : type === 'exception' ? '异常' : '旁路'}：${meta.trigger_condition || ''}`,
      data: {
        edge_type: type,
        condition: meta.trigger_condition,
        pre_action: meta.pre_action,
        note: meta.note,
      },
      markerEnd: createEdgeMarker((EDGE_STYLES[type] || EDGE_STYLES.normal).stroke),
    }

    if (existingEdgeIndex >= 0) {
      vueFlowEdges.value = normalizeEdges([
        ...vueFlowEdges.value.slice(0, existingEdgeIndex),
        newEdge,
        ...vueFlowEdges.value.slice(existingEdgeIndex + 1),
      ])
    } else {
      vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, newEdge])
    }
  }

  pendingFlowTypeChange.value = null
  pendingFlowMeta.value = null
  flowTypeConfigVisible.value = false
  emitSortData()
}

const handleNodePreview = (data: {
  screen_id: number
  screen_name: string
  image_url?: string
}) => {
  emit('preview-screen', data)
}

const handleAutoLayout = () => {
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  const mainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const otherNodes = vueFlowNodes.value.filter((n) => getNodeData(n).flow_type !== 'main')
  mainNodes.forEach((node, index) => {
    node.position = { x: index * 280, y: 0 }
  })
  const branchYOffsets: Record<string, number> = {}
  otherNodes.forEach((node) => {
    const sourceEdge = vueFlowEdges.value.find((e) => e.target === node.id)
    const sourceNode = sourceEdge
      ? vueFlowNodes.value.find((n) => n.id === sourceEdge.source)
      : null
    const sourceX = sourceNode?.position.x ?? 0
    const sourceId = sourceNode?.id ?? ''
    branchYOffsets[sourceId] = branchYOffsets[sourceId] ? branchYOffsets[sourceId] + 200 : 200
    node.position = { x: sourceX, y: branchYOffsets[sourceId] }
  })
  vueFlowNodes.value = [...vueFlowNodes.value]
  emitSortData()
  ElMessage.success('自动布局完成')
}

const handlePreviewPrompt = () => emit('preview-prompt')

const handleUndo = () => {
  const prev = undo()
  if (prev) {
    vueFlowNodes.value = hydrateNodesWithImages(prev.nodes)
    vueFlowEdges.value = normalizeEdges(prev.edges)
    emitSortData()
    ElMessage.info('已撤销')
  }
}

const handlePaneClick = () => {
  selectedNodes.value = []
}

const handleNodeClick = (event: { node: Node }) => {
  selectedNodes.value = [event.node.id]
}

const handleSelectionChange = (selected: { nodes: Node[] }) => {
  selectedNodes.value = selected.nodes.map((n) => n.id)
}

const handleDeleteSelected = () => {
  if (selectedNodes.value.length === 0) return
  const deletedCount = selectedNodes.value.length
  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  vueFlowEdges.value = vueFlowEdges.value.filter(
    (e) => !selectedNodes.value.includes(e.source) && !selectedNodes.value.includes(e.target)
  )
  vueFlowNodes.value = normalizeMainNodeOrders(
    vueFlowNodes.value.filter((n) => !selectedNodes.value.includes(n.id))
  )
  selectedNodes.value = []
  emitSortData()
  ElMessage.success(`已删除 ${deletedCount} 个节点`)
}

const canMoveMainBackward = () => (getSelectedMainOrder(vueFlowNodes.value) ?? 0) > 1

const canMoveMainForward = () => {
  const selectedMainNodeId = getSelectedMainNodeId(vueFlowNodes.value)
  const selectedMainOrder = getSelectedMainOrder(vueFlowNodes.value)
  if (!selectedMainNodeId || selectedMainOrder == null) return false
  return selectedMainOrder < getMainNodeCount(vueFlowNodes.value)
}

const moveSelectedMainNode = (direction: -1 | 1) => {
  const selectedNodeId = getSelectedMainNodeId(vueFlowNodes.value)
  if (!selectedNodeId) return
  const selectedNode = vueFlowNodes.value.find((n) => n.id === selectedNodeId)
  if (!selectedNode) return

  const orderedMainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const currentIndex = orderedMainNodes.findIndex((node) => node.id === selectedNode.id)
  const targetIndex = currentIndex + direction
  if (currentIndex < 0 || targetIndex < 0 || targetIndex >= orderedMainNodes.length) return

  saveToHistory(vueFlowNodes.value, vueFlowEdges.value)
  const reorderedMainNodes = [...orderedMainNodes]
  ;[reorderedMainNodes[currentIndex], reorderedMainNodes[targetIndex]] = [
    reorderedMainNodes[targetIndex],
    reorderedMainNodes[currentIndex],
  ]
  const mainOrderMap = new Map(reorderedMainNodes.map((node, index) => [node.id, index + 1]))
  vueFlowNodes.value = layoutMainNodesByOrder(
    normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (!mainOrderMap.has(node.id)) return node
        return {
          ...node,
          data: {
            ...getNodeData(node),
            main_order: mainOrderMap.get(node.id),
          },
        }
      })
    )
  )
  emitSortData()
}

const zoomIn = () => {
  if (currentZoom.value < 4) {
    void flowZoomIn({ duration: 180 })
  }
}
const zoomOut = () => {
  if (currentZoom.value > 0.2) {
    void flowZoomOut({ duration: 180 })
  }
}

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedNodes.value.length > 0) handleDeleteSelected()
  }
  if (e.ctrlKey && e.key === 'z') {
    e.preventDefault()
    handleUndo()
  }
  if (e.ctrlKey && e.key === 'l') {
    e.preventDefault()
    handleAutoLayout()
  }
  if (e.key === 'Escape') {
    selectedNodes.value = []
  }
}

onMounted(() => {
  if (editorRef.value) editorRef.value.focus()
  setTimeout(() => {
    showShortcutsTip.value = false
  }, 5000)
})

const getFlowSortSubmitData = () => {
  const sortedNodes = getOrderedNodesForSubmit(vueFlowNodes.value)
  return {
    mode: 'graph' as const,
    flow_sort_data: {
      nodes: sortedNodes.map((node, index) => ({
        screen_id: getNodeData(node).screen_id,
        screen_order: index + 1,
        flow_type: getNodeData(node).flow_type,
        main_order: getNodeData(node).main_order,
        screen_name: getNodeData(node).screen_name,
        ui_spec_elements: getNodeData(node).ui_spec_elements || [],
        summary: getNodeData(node).summary || '',
        flow_meta: getNodeData(node).flow_meta || undefined,
      })),
      edges: vueFlowEdges.value
        .map((edge) => {
          const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
          const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
          const sourceScreenId = sourceNode ? getNodeData(sourceNode).screen_id : undefined
          const targetScreenId = targetNode ? getNodeData(targetNode).screen_id : undefined
          if (!sourceScreenId || !targetScreenId) return null
          return {
            source: String(sourceScreenId),
            target: String(targetScreenId),
            edge_type: edge.data?.edge_type || 'normal',
            condition: edge.data?.condition || '',
            label: typeof edge.label === 'string' ? edge.label : String(edge.label || ''),
            pre_action: edge.data?.pre_action || '',
            note: edge.data?.note || '',
          }
        })
        .filter((e): e is NonNullable<typeof e> => e !== null),
      module_info: props.moduleInfo || { name: '', description: '' },
    },
  }
}

const getFlowValidationIssues = (): { errors: string[]; warnings: string[] } => {
  const flowData = getFlowSortSubmitData().flow_sort_data
  const edges = flowData.edges.map((edge) => ({
    source: edge.source,
    target: edge.target,
    edge_type: edge.edge_type,
    condition: edge.condition || '',
    label: edge.label,
  }))
  return validateFlowData(flowData.nodes, edges)
}

defineExpose({ getFlowSortSubmitData, getFlowValidationIssues })
</script>

<style scoped lang="scss">
.flow-sort-editor {
  width: 100%;
  flex: 1;
  min-height: 0;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #fafbfc 0%, #f5f7fa 100%);
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
  outline: none;

  &:focus {
    outline: 2px solid rgba(64, 158, 255, 0.3);
    outline-offset: 2px;
  }

  .editor-toolbar {
    flex-shrink: 0;
    padding: 14px 16px;
    background: linear-gradient(135deg, #ffffff 0%, #fafbfc 100%);
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;

    .toolbar-left {
      display: flex;
      align-items: center;
      min-width: 0;

      .editor-heading {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .editor-title {
          font-size: 14px;
          font-weight: 600;
          color: #303133;
        }

        .editor-subtitle {
          font-size: 12px;
          color: #909399;
        }
      }
    }

    .toolbar-actions {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
      margin-left: auto;

      .action-group {
        :deep(.el-button) {
          border-radius: 8px;
          transition: all 0.2s ease;

          &:hover {
            transform: translateY(-1px);
          }
        }
      }

      .selection-info {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .main-order-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .zoom-controls {
        display: flex;
        align-items: center;
        gap: 6px;

        :deep(.el-button.is-circle) {
          padding: 0;
        }

        .zoom-level {
          font-size: 12px;
          color: #606266;
          min-width: 40px;
          text-align: center;
        }
      }
    }
  }

  .editor-container {
    flex: 1;
    position: relative;
    overflow: hidden;
    min-height: 0;
  }

  .graph-mode {
    position: absolute;
    inset: 0;
    overflow: hidden;
  }

  .shortcuts-tip {
    position: absolute;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.75);
    color: #fff;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    pointer-events: none;
    backdrop-filter: blur(4px);

    kbd {
      background: rgba(255, 255, 255, 0.15);
      padding: 2px 6px;
      border-radius: 4px;
      margin: 0 2px;
    }
  }
}

.graph-mode :deep(.vue-flow__controls) {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  overflow: hidden;
}

.graph-mode :deep(.vue-flow__minimap) {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}

.graph-mode :deep(.vue-flow__edge) {
  z-index: 1;
}

.graph-mode :deep(.vue-flow__edge-path) {
  stroke-width: 2;
}

.graph-mode :deep(.vue-flow__edge-marker) {
  stroke-width: 2;
}

.tip-fade-enter-active,
.tip-fade-leave-active {
  transition: opacity 0.5s ease;
}
.tip-fade-enter-from,
.tip-fade-leave-to {
  opacity: 0;
}

@media (max-width: 960px) {
  .flow-sort-editor {
    .editor-toolbar {
      align-items: flex-start;
      padding: 12px;

      .toolbar-actions {
        width: 100%;
        margin-left: 0;
        justify-content: flex-start;
      }
    }
  }
}

@media (max-width: 640px) {
  .flow-sort-editor {
    .editor-toolbar {
      .toolbar-left,
      .toolbar-actions,
      .selection-info,
      .zoom-controls {
        width: 100%;
      }

      .toolbar-actions {
        gap: 10px;
      }

      .selection-info {
        justify-content: space-between;
      }

      .zoom-controls {
        justify-content: flex-start;
      }
    }
  }
}
</style>
