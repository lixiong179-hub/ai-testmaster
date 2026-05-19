import { ref, nextTick, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Edge } from '@vue-flow/core'
import type { FlowMetaData } from '@/store/flowSort'
import type { EditorNodeData, EdgeStyleConfig, FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'
import { FLOW_TYPE_LABEL_MAP, inferEdgeType } from '@/composables/useFlowEditor'

const VIRTUAL_SCREEN_ID_OFFSET = 1000
const NODE_SPACING_Y = 280

export interface UseFlowTypeOpsOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  selectedNodes: Ref<string[]>
  emitSortData: () => void
  saveSnapshot: () => void
  applyAllEdgeStyles: (edges: FlowGraphEdge[]) => FlowGraphEdge[]
  currentEdgeStyles: Ref<Record<string, EdgeStyleConfig>>
  isOverviewMode: Ref<boolean>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  getMainNodesInOrder: (nodes: FlowEditorNode[], edges?: Edge[]) => FlowEditorNode[]
  normalizeMainNodeOrders: (nodes: FlowEditorNode[], edges?: Edge[]) => FlowEditorNode[]
  normalizeEdges: (edges: any[], styleMap?: any, isOverview?: boolean) => any[]
  autoLayoutByMode: (mode: string, nodes: FlowEditorNode[], edges: FlowGraphEdge[], focusedNodeId?: string | null) => FlowEditorNode[]
  layoutMode: Ref<string>
  focusedNodeId: Ref<string | null>
  getEdgeStyle: (type: string) => EdgeStyleConfig
  isProgrammaticEdgeChange: Ref<boolean>
  fitView?: (options: { duration: number; padding: number }) => Promise<void>
}

export function useFlowTypeOps(options: UseFlowTypeOpsOptions) {
  const { vueFlowNodes, vueFlowEdges, selectedNodes, emitSortData, saveSnapshot, applyAllEdgeStyles, currentEdgeStyles, isOverviewMode, getNodeData, getMainNodesInOrder, normalizeMainNodeOrders, normalizeEdges, autoLayoutByMode: autoLayout, getEdgeStyle, isProgrammaticEdgeChange, fitView } = options

  const pendingFlowTypeChange = ref<{ nodeId: string; type: string } | null>(null)
  const pendingFlowMeta = ref<FlowMetaData | null>(null)
  const flowTypeConfigVisible = ref(false)
  const branchCounter = ref(1)

  const getSelectedMainNodeId = (): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeData(node).flow_type === 'main' ? node.id : null
  }

  const handleFlowTypeChange = (nodeId: string, type: string): void => {
    if (type === 'main') {
      saveSnapshot()
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter((e: any) => !(e.target === nodeId && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)))
      const nextMainOrder = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as any).length + 1
      vueFlowNodes.value = normalizeMainNodeOrders(vueFlowNodes.value.map((node) => {
        if (node.id !== nodeId) return node
        const nodeData = getNodeData(node)
        return { ...node, data: { ...nodeData, flow_type: type as EditorNodeData['flow_type'], main_order: nodeData.main_order ?? nextMainOrder, flow_meta: undefined } }
      }), vueFlowEdges.value as any)
      emitSortData()
      vueFlowNodes.value = autoLayout('focused-path', vueFlowNodes.value, vueFlowEdges.value as any, nodeId)
      return
    }
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (!node) return
    pendingFlowTypeChange.value = { nodeId, type }
    pendingFlowMeta.value = getNodeData(node).flow_meta || null
    flowTypeConfigVisible.value = true
  }

  const handleFlowTypeConfigConfirm = (meta: FlowMetaData): void => {
    if (!pendingFlowTypeChange.value) return
    const { nodeId, type } = pendingFlowTypeChange.value
    const parentNodeId = meta.parent_main_node_id
    saveSnapshot()
    const currentMainNodesBefore = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as any)
    const nodeIndexBefore = currentMainNodesBefore.findIndex((n) => n.id === nodeId)
    const wasMainNode = nodeIndexBefore >= 0 && type !== 'main'
    let predecessorMainId: string | null = null; let successorMainId: string | null = null
    if (wasMainNode) {
      if (nodeIndexBefore > 0) predecessorMainId = currentMainNodesBefore[nodeIndexBefore - 1].id
      if (nodeIndexBefore < currentMainNodesBefore.length - 1) successorMainId = currentMainNodesBefore[nodeIndexBefore + 1].id
    }
    vueFlowNodes.value = normalizeMainNodeOrders(vueFlowNodes.value.map((node) => {
      if (node.id !== nodeId) return node
      const nodeData = getNodeData(node)
      return { ...node, data: { ...nodeData, flow_type: type as EditorNodeData['flow_type'], main_order: undefined, flow_meta: meta } }
    }), vueFlowEdges.value as any)
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = vueFlowEdges.value.filter((e: any) => {
      if (e.target === nodeId && e.source === parentNodeId && e.data?.edge_type !== 'normal') return false
      if (e.source === nodeId || e.target === nodeId) {
        if (predecessorMainId && successorMainId) { if ((e.source === predecessorMainId && e.target === nodeId) || (e.source === nodeId && e.target === successorMainId)) return false }
        else if (e.source === nodeId || e.target === nodeId) return false
      }
      return true
    })
    if (parentNodeId) {
      const existingEdgeIndex = vueFlowEdges.value.findIndex((e: any) => e.target === nodeId && e.source === parentNodeId)
      const style = getEdgeStyle(type)
      const handles = inferEdgeType('main', type)
      const newEdge: FlowGraphEdge = {
        id: existingEdgeIndex >= 0 ? vueFlowEdges.value[existingEdgeIndex].id : `edge_${Date.now()}`,
        source: parentNodeId, target: nodeId, sourceHandle: handles.sourceHandle, targetHandle: handles.targetHandle,
        type: 'default', animated: true, style,
        label: `${type === 'branch' ? '分支' : type === 'exception' ? '异常' : '旁路'}：${meta.trigger_condition || ''}`,
        data: { edge_type: type, condition: meta.trigger_condition, pre_action: meta.pre_action, note: meta.note },
      }
      if (existingEdgeIndex >= 0) vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value.slice(0, existingEdgeIndex), newEdge, ...vueFlowEdges.value.slice(existingEdgeIndex + 1)] as any, currentEdgeStyles.value, isOverviewMode.value) as any
      else vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, newEdge] as any, currentEdgeStyles.value, isOverviewMode.value) as any
    }
    if (predecessorMainId && successorMainId) {
      const existingDirectEdge = vueFlowEdges.value.find((e: any) => e.source === predecessorMainId && e.target === successorMainId)
      const mainChainEdge: FlowGraphEdge = {
        id: existingDirectEdge?.id || `edge_${predecessorMainId}_${successorMainId}_${Date.now()}`,
        source: predecessorMainId, target: successorMainId, sourceHandle: 'source-right', targetHandle: 'target-left',
        type: 'default', label: existingDirectEdge?.label || '连线', data: existingDirectEdge?.data || { edge_type: 'normal' },
      }
      if (existingDirectEdge) vueFlowEdges.value = vueFlowEdges.value.map((e: any) => e.id === existingDirectEdge.id ? mainChainEdge : e)
      else vueFlowEdges.value = [...vueFlowEdges.value, mainChainEdge]
    }
    flowTypeConfigVisible.value = false; pendingFlowTypeChange.value = null; pendingFlowMeta.value = null
    vueFlowNodes.value = autoLayout('focused-path', vueFlowNodes.value, vueFlowEdges.value as any, nodeId)
    emitSortData()
    nextTick(() => { fitView?.({ duration: 300, padding: 0.15 }) })
  }

  const handleQuickCreateBranch = async (): Promise<void> => {
    const mainNodeId = getSelectedMainNodeId()
    if (!mainNodeId) return
    try {
      const { value: branchName } = await ElMessageBox.prompt('请输入分支页面名称', '快速创建分支', { confirmButtonText: '创建', cancelButtonText: '取消', inputValue: `新分支页面${branchCounter.value}`, inputValidator: (val: string) => { if (!val || !val.trim()) return '页面名称不能为空'; return true } })
      saveSnapshot()
      const mainNode = vueFlowNodes.value.find((n) => n.id === mainNodeId)!
      const branchId = `node_branch_${Date.now()}`
      const branchScreenId = -(VIRTUAL_SCREEN_ID_OFFSET + branchCounter.value)
      const branchNode: FlowEditorNode = { id: branchId, type: 'custom', position: { x: mainNode.position.x, y: mainNode.position.y + NODE_SPACING_Y }, data: { screen_id: branchScreenId, screen_name: branchName.trim(), summary: '', ui_spec_elements: [], flow_type: 'branch', image_url: '' } }
      const branchHandles = inferEdgeType('main', 'branch')
      const branchEdge: FlowGraphEdge = { id: `edge_${mainNodeId}_${branchId}`, source: mainNodeId, target: branchId, sourceHandle: branchHandles.sourceHandle, targetHandle: branchHandles.targetHandle, type: 'default', data: { edge_type: 'branch', condition: '', pre_action: '', note: '' }, label: branchName.trim() }
      vueFlowNodes.value = [...vueFlowNodes.value, branchNode]
      vueFlowEdges.value = normalizeEdges([...vueFlowEdges.value, branchEdge] as any, currentEdgeStyles.value, isOverviewMode.value) as any
      selectedNodes.value = [branchId]; branchCounter.value++
      vueFlowNodes.value = autoLayout('focused-path', vueFlowNodes.value, vueFlowEdges.value as any, branchId)
      emitSortData()
      ElMessage.success(`已创建分支节点：${branchName.trim()}`)
    } catch { /* user cancelled */ }
  }

  const handleBatchFlowTypeChange = (type: string): void => {
    if (selectedNodes.value.length < 2) return
    saveSnapshot()
    const selectedSet = new Set(selectedNodes.value)
    vueFlowNodes.value = normalizeMainNodeOrders(vueFlowNodes.value.map((node) => {
      if (!selectedSet.has(node.id)) return node
      const nodeData = getNodeData(node)
      if (nodeData.flow_type === type) return node
      return { ...node, data: { ...nodeData, flow_type: type as EditorNodeData['flow_type'], main_order: type === 'main' ? (nodeData.main_order ?? 0) : undefined, flow_meta: undefined } }
    }), vueFlowEdges.value as any)
    if (type === 'main') {
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter((e: any) => !(selectedSet.has(e.target) && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)))
    }
    vueFlowEdges.value = applyAllEdgeStyles(vueFlowEdges.value.map((edge: any) => {
      const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
      if (!targetNode) return edge
      const targetType = getNodeData(targetNode).flow_type
      const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
      const sourceType = sourceNode ? getNodeData(sourceNode).flow_type : 'main'
      const newEdgeType = targetType === 'main' ? 'normal' : targetType
      const handles = inferEdgeType(sourceType, targetType)
      return { ...edge, sourceHandle: handles.sourceHandle, targetHandle: handles.targetHandle, data: { ...edge.data, edge_type: newEdgeType } }
    }))
    emitSortData()
    ElMessage.success(`已将 ${selectedNodes.value.length} 个节点设为${FLOW_TYPE_LABEL_MAP[type] || type}`)
  }

  return { pendingFlowTypeChange, pendingFlowMeta, flowTypeConfigVisible, branchCounter, handleFlowTypeChange, handleFlowTypeConfigConfirm, handleQuickCreateBranch, handleBatchFlowTypeChange }
}
