import { ref, computed } from 'vue'
import { MarkerType } from '@vue-flow/core'
import type { Edge } from '@vue-flow/core'
import type { FlowNodeData } from '@/store/flowSort'

export type EditorNodeData = {
  screen_id: number
  screen_name: string
  summary?: string
  ui_spec_elements?: Array<{
    type: string
    label: string
    semantic?: string
    position?: string
    interactive?: boolean
  }>
  flow_type: FlowNodeData['flow_type']
  main_order?: number
  image_url?: string
  element_count?: number
  flow_meta?: FlowNodeData['flow_meta']
}

export interface FlowEditorNode {
  id: string
  type?: string
  position: { x: number; y: number }
  data: EditorNodeData
  [key: string]: unknown
}

export const EDGE_STYLES: Record<string, { stroke: string; strokeDasharray?: string }> = {
  normal: { stroke: '#409eff' },
  branch: { stroke: '#67c23a' },
  exception: { stroke: '#f56c6c', strokeDasharray: '5 5' },
  bypass: { stroke: '#e6a23c', strokeDasharray: '3 3' },
}

export const getNodeData = (node: FlowEditorNode) => node.data as EditorNodeData

export const getMainNodesInOrder = (nodes: FlowEditorNode[]) =>
  [...nodes]
    .filter((node) => getNodeData(node).flow_type === 'main')
    .sort((a, b) => {
      const aOrder = getNodeData(a).main_order ?? Number.MAX_SAFE_INTEGER
      const bOrder = getNodeData(b).main_order ?? Number.MAX_SAFE_INTEGER
      if (aOrder !== bOrder) return aOrder - bOrder
      return a.position.x - b.position.x
    })

export const getOrderedNodesForSubmit = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const otherNodes = [...nodes]
    .filter((node) => getNodeData(node).flow_type !== 'main')
    .sort((a, b) => {
      if (a.position.x !== b.position.x) return a.position.x - b.position.x
      return a.position.y - b.position.y
    })
  return [...mainNodes, ...otherNodes]
}

export const normalizeMainNodeOrders = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const mainOrderMap = new Map(mainNodes.map((node, index) => [node.id, index + 1]))

  return nodes.map((node) => {
    const nodeData = getNodeData(node)
    if (nodeData.flow_type === 'main') {
      return {
        ...node,
        data: { ...nodeData, main_order: mainOrderMap.get(node.id) },
      }
    }

    const { main_order: _mainOrder, ...restData } = nodeData
    return { ...node, data: restData }
  })
}

export const layoutMainNodesByOrder = (nodes: FlowEditorNode[]) => {
  const mainNodes = getMainNodesInOrder(nodes)
  const positionMap = new Map(
    mainNodes.map((node, index) => [node.id, { x: index * 280, y: node.position.y }])
  )

  return nodes.map((node) => {
    if (!positionMap.has(node.id)) return node
    return { ...node, position: positionMap.get(node.id) || node.position }
  })
}

export const getMainNodeCount = (nodes: FlowEditorNode[]) =>
  nodes.filter((node) => getNodeData(node).flow_type === 'main').length

export const createEdgeMarker = (color: string) => ({
  type: MarkerType.ArrowClosed,
  width: 20,
  height: 20,
  color,
})

export const normalizeEdge = (edge: Edge): Edge => {
  const edgeType = edge.data?.edge_type || 'normal'
  const baseStyle = EDGE_STYLES[edgeType] || EDGE_STYLES.normal
  const edgeStyle = typeof edge.style === 'function' ? {} : (edge.style ?? {})
  const stroke = typeof edgeStyle.stroke === 'string' ? edgeStyle.stroke : baseStyle.stroke

  return {
    ...edge,
    type: edge.type || 'default',
    animated: edgeType !== 'normal',
    style: { ...baseStyle, ...edgeStyle, stroke },
    markerEnd: createEdgeMarker(stroke),
  }
}

export const normalizeEdges = (edges: Edge[]) => edges.map(normalizeEdge)

export interface FlowValidationResult {
  errors: string[]
  warnings: string[]
}

export type FlowEdgeInput = {
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
  label: string
}

export const validateFlowData = (
  nodes: Pick<FlowNodeData, 'screen_id' | 'screen_name' | 'flow_type'>[],
  edges: FlowEdgeInput[]
): FlowValidationResult => {
  const errors: string[] = []
  const warnings: string[] = []
  const mainNodes = nodes.filter((node) => node.flow_type === 'main')
  const mainNodeIds = new Set(mainNodes.map((node) => String(node.screen_id)))
  const mainEdges = edges.filter(
    (edge) => mainNodeIds.has(edge.source) && mainNodeIds.has(edge.target) && edge.edge_type === 'normal'
  )

  if (mainNodes.length === 0) {
    errors.push('至少需要保留一个主干节点')
  }

  nodes.forEach((node) => {
    if (!node.screen_name.trim()) {
      errors.push(`存在未命名页面（screen_id=${node.screen_id}）`)
    }
  })

  edges.forEach((edge) => {
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

export const useFlowHistory = () => {
  const historyStack = ref<{ nodes: FlowEditorNode[]; edges: Edge[] }[]>([])
  const canUndo = computed(() => historyStack.value.length > 0)

  const saveToHistory = (nodes: FlowEditorNode[], edges: Edge[]) => {
    historyStack.value.push({
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    })
    if (historyStack.value.length > 50) historyStack.value.shift()
  }

  const undo = () => {
    if (historyStack.value.length === 0) return null
    return historyStack.value.pop() ?? null
  }

  return { historyStack, canUndo, saveToHistory, undo }
}

export const useFlowSelection = () => {
  const selectedNodes = ref<string[]>([])
  const draggingNodeId = ref<string | null>(null)

  const getSelectedMainNodeId = (allNodes: FlowEditorNode[]): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = allNodes.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeData(node).flow_type === 'main' ? node.id : null
  }

  const getSelectedMainOrder = (allNodes: FlowEditorNode[]): number | null => {
    const nodeId = getSelectedMainNodeId(allNodes)
    if (!nodeId) return null
    const node = allNodes.find((n) => n.id === nodeId)
    return node ? (getNodeData(node).main_order ?? null) : null
  }

  return { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder }
}
