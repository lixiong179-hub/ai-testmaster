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
        <div v-if="getSelectedMainNodeId()" class="main-order-actions">
          <el-tag type="success" size="small" effect="plain">
            主干第 {{ getSelectedMainOrder() }} 步
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
  MarkerType,
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
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { UIScreen } from '@/api/uiPrototype'

type EditorNodeData = {
  screen_id: number
  screen_name: string
  summary?: string
  ui_spec_elements?: FlowNodeData['ui_spec_elements']
  flow_type: FlowNodeData['flow_type']
  main_order?: number
  image_url?: string
  element_count?: number
}
type FlowValidationResult = { errors: string[]; warnings: string[] }
type FlowEditorNode = {
  id: string
  type?: string
  position: { x: number; y: number }
  data: EditorNodeData
}

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
const selectedNodes = ref<string[]>([])
const draggingNodeId = ref<string | null>(null)
const currentZoom = ref(1)
const showShortcutsTip = ref(true)

const { zoomIn: flowZoomIn, zoomOut: flowZoomOut, viewport } = useVueFlow()

const vueFlowNodes = ref<FlowEditorNode[]>([])
const vueFlowEdges = ref<Edge[]>([])

const historyStack = ref<{ nodes: FlowEditorNode[]; edges: Edge[] }[]>([])
const canUndo = computed(() => historyStack.value.length > 0)

const getNodeData = (node: FlowEditorNode | Node) => node.data as EditorNodeData

const getMainNodesInOrder = (nodes: FlowEditorNode[]) =>
  [...nodes]
    .filter((node) => getNodeData(node).flow_type === 'main')
    .sort((a, b) => {
      const aOrder = getNodeData(a).main_order ?? Number.MAX_SAFE_INTEGER
      const bOrder = getNodeData(b).main_order ?? Number.MAX_SAFE_INTEGER
      if (aOrder !== bOrder) return aOrder - bOrder
      return a.position.x - b.position.x
    })

const normalizeMainNodeOrders = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const mainOrderMap = new Map(mainNodes.map((node, index) => [node.id, index + 1]))

  return nodes.map((node) => {
    const nodeData = getNodeData(node)
    if (nodeData.flow_type === 'main') {
      return {
        ...node,
        data: {
          ...nodeData,
          main_order: mainOrderMap.get(node.id),
        },
      }
    }

    const { main_order: _mainOrder, ...restData } = nodeData
    return {
      ...node,
      data: restData,
    }
  })
}

const layoutMainNodesByOrder = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const positionMap = new Map(
    mainNodes.map((node, index) => [
      node.id,
      {
        x: index * 280,
        y: node.position.y,
      },
    ])
  )

  return nodes.map((node) => {
    if (!positionMap.has(node.id)) return node
    return {
      ...node,
      position: positionMap.get(node.id) || node.position,
    }
  })
}

const getOrderedNodesForSubmit = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const otherNodes = [...nodes]
    .filter((node) => getNodeData(node).flow_type !== 'main')
    .sort((a, b) => {
      if (a.position.x !== b.position.x) return a.position.x - b.position.x
      return a.position.y - b.position.y
    })
  return [...mainNodes, ...otherNodes]
}

const getMainNodeCount = (nodes: FlowEditorNode[]) => {
  let count = 0
  for (const node of nodes) {
    if ((node.data as { flow_type?: string }).flow_type === 'main') count++
  }
  return count
}

const getNodeById = (nodeId: string | null): FlowEditorNode | null => {
  if (!nodeId) return null
  for (const item of vueFlowNodes.value) {
    if (item.id === nodeId) return item
  }
  return null
}

const getSelectedMainNodeId = (): string | null => {
  if (selectedNodes.value.length !== 1) return null
  const node = getNodeById(selectedNodes.value[0])
  return node && (node.data as { flow_type?: string }).flow_type === 'main' ? node.id : null
}

const getSelectedMainOrder = (): number | null => {
  const node = getNodeById(getSelectedMainNodeId())
  return node ? ((node.data as { main_order?: number }).main_order ?? null) : null
}

const canMoveMainBackward = () => (getSelectedMainOrder() ?? 0) > 1

const canMoveMainForward = () => {
  const selectedMainNodeId = getSelectedMainNodeId()
  const selectedMainOrder = getSelectedMainOrder()
  if (!selectedMainNodeId || selectedMainOrder == null) return false
  return selectedMainOrder < getMainNodeCount(vueFlowNodes.value)
}

const getScreenImageUrl = (screen: UIScreen) => {
  if (!screen.id) return ''
  return props.screenImageUrls?.[screen.id] || ''
}

const EDGE_STYLES: Record<string, { stroke: string; strokeDasharray?: string }> = {
  normal: { stroke: '#409eff' },
  branch: { stroke: '#67c23a' },
  exception: { stroke: '#f56c6c', strokeDasharray: '5 5' },
  bypass: { stroke: '#e6a23c', strokeDasharray: '3 3' },
}

const createEdgeMarker = (color: string) => ({
  type: MarkerType.ArrowClosed,
  width: 20,
  height: 20,
  color,
})

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

const normalizeEdge = (edge: Edge): Edge => {
  const edgeType = edge.data?.edge_type || 'normal'
  const baseStyle = EDGE_STYLES[edgeType] || EDGE_STYLES.normal
  const edgeStyle = typeof edge.style === 'function' ? {} : (edge.style ?? {})
  const stroke = typeof edgeStyle.stroke === 'string' ? edgeStyle.stroke : baseStyle.stroke

  return {
    ...edge,
    type: edge.type || 'default',
    animated: edgeType !== 'normal',
    style: {
      ...baseStyle,
      ...edgeStyle,
      stroke,
    },
    markerEnd: createEdgeMarker(stroke),
  }
}

const normalizeEdges = (edges: Edge[]) => edges.map(normalizeEdge)

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

const saveToHistory = () => {
  historyStack.value.push({
    nodes: JSON.parse(
      JSON.stringify(hydrateNodesWithImages(normalizeMainNodeOrders(vueFlowNodes.value)))
    ),
    edges: JSON.parse(JSON.stringify(normalizeEdges(vueFlowEdges.value))),
  })
  if (historyStack.value.length > 50) historyStack.value.shift()
}

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
          ui_spec_elements: screen.ui_spec?.elements || [],
          flow_type: 'main' as const,
          main_order: index + 1,
          image_url: getScreenImageUrl(screen),
          element_count: screen.element_count,
        },
      }))
    )
    vueFlowEdges.value = []
    saveToHistory()
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
  saveToHistory()
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
  saveToHistory()
  emitSortData()
}

const onNodeDragStop = () => {
  draggingNodeId.value = null
  saveToHistory()
  emitSortData()
}

const handleFlowTypeChange = (nodeId: string, type: string) => {
  saveToHistory()
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
          main_order: type === 'main' ? nodeData.main_order ?? nextMainOrder : undefined,
        },
      }
    })
  )
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
  saveToHistory()
  const mainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const otherNodes = vueFlowNodes.value.filter((n) => n.data.flow_type !== 'main')
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
  if (historyStack.value.length > 0) {
    const prev = historyStack.value.pop()!
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
  saveToHistory()
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

const moveSelectedMainNode = (direction: -1 | 1) => {
  const selectedNode = getNodeById(getSelectedMainNodeId())
  if (!selectedNode) return

  const orderedMainNodes = getMainNodesInOrder(vueFlowNodes.value)
  const currentIndex = orderedMainNodes.findIndex((node) => node.id === selectedNode.id)
  const targetIndex = currentIndex + direction
  if (currentIndex < 0 || targetIndex < 0 || targetIndex >= orderedMainNodes.length) return

  saveToHistory()
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
          }
        })
        .filter((e): e is NonNullable<typeof e> => e !== null),
      module_info: props.moduleInfo || { name: '', description: '' },
    },
  }
}

const getFlowValidationIssues = (): FlowValidationResult => {
  const errors: string[] = []
  const warnings: string[] = []
  const flowData = getFlowSortSubmitData().flow_sort_data
  const mainNodes = flowData.nodes.filter((node) => node.flow_type === 'main')
  const mainNodeIds = new Set(mainNodes.map((node) => String(node.screen_id)))
  const mainEdges = flowData.edges.filter(
    (edge) => mainNodeIds.has(edge.source) && mainNodeIds.has(edge.target) && edge.edge_type === 'normal'
  )

  if (mainNodes.length === 0) {
    errors.push('至少需要保留一个主干节点')
  }

  flowData.nodes.forEach((node) => {
    if (!node.screen_name.trim()) {
      errors.push(`存在未命名页面（screen_id=${node.screen_id}）`)
    }
  })

  flowData.edges.forEach((edge) => {
    if (edge.edge_type !== 'normal' && !edge.condition.trim()) {
      const labelMap: Record<string, string> = {
        branch: '分支触发条件',
        exception: '异常场景',
        bypass: '旁路出现时机',
      }
      errors.push(`${edge.label} 缺少${labelMap[edge.edge_type] || '说明'}`)
    }
  })

  if (mainNodes.length > 1 && mainEdges.length === 0) {
    warnings.push('当前主干节点之间没有正常连线，AI 可能无法稳定理解主流程')
  }

  return { errors, warnings }
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
