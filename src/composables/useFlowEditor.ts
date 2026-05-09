import { ref, computed } from 'vue'
import { MarkerType } from '@vue-flow/core'
import type { Edge, Styles } from '@vue-flow/core'
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

export interface FlowGraphEdge {
  id: string
  source: string
  target: string
  type: string
  sourceHandle?: string
  targetHandle?: string
  label?: string | number
  style?: Record<string, unknown>
  animated?: boolean
  hidden?: boolean
  selected?: boolean
  markerEnd?: unknown
  data?: Record<string, unknown>
}

export type EdgeStyleConfig = Styles & {
  stroke: string
  strokeWidth: number
  strokeDasharray?: string
}

export const EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#409eff', strokeWidth: 2 },
  branch: { stroke: '#67c23a', strokeWidth: 2 },
  exception: { stroke: '#f56c6c', strokeWidth: 2, strokeDasharray: '5 5' },
  bypass: { stroke: '#e6a23c', strokeWidth: 2, strokeDasharray: '3 3' },
}

export const OVERVIEW_EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#b8c2cc', strokeWidth: 1.2 },
  branch: { stroke: '#95d475', strokeWidth: 1.2 },
  exception: { stroke: '#f3a6a6', strokeWidth: 1.2, strokeDasharray: '5 5' },
  bypass: { stroke: '#eebe77', strokeWidth: 1.2, strokeDasharray: '3 3' },
}

export const FLOW_TYPE_TAG_MAP: Record<string, string> = {
  main: 'primary',
  branch: 'success',
  exception: 'danger',
  bypass: 'warning',
}

export const FLOW_TYPE_LABEL_MAP: Record<string, string> = {
  main: '主干',
  branch: '分支',
  exception: '异常',
  bypass: '旁路',
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

    // main_order 仅主干节点持有，非主干节点显式剔除
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
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

export const normalizeEdge = (
  edge: Edge,
  styleMap?: Record<string, EdgeStyleConfig>,
  isOverview?: boolean
): Edge => {
  const edgeType = (edge.data?.edge_type as string) || 'normal'
  const styles = styleMap || EDGE_STYLES
  const baseStyle = styles[edgeType as string] || styles.normal
  const edgeStyle = typeof edge.style === 'function' ? {} : (edge.style ?? {})
  const stroke = typeof edgeStyle.stroke === 'string' ? edgeStyle.stroke : baseStyle.stroke
  const forcedStyle = isOverview ? { strokeWidth: baseStyle.strokeWidth } : {}

  return {
    ...edge,
    type: edge.type || 'default',
    animated: !isOverview && edgeType !== 'normal',
    style: { ...baseStyle, ...edgeStyle, stroke, ...forcedStyle },
    markerEnd: createEdgeMarker(stroke),
  }
}

export const normalizeEdges = (
  edges: Edge[],
  styleMap?: Record<string, EdgeStyleConfig>,
  isOverview?: boolean
): Edge[] => edges.map((e) => normalizeEdge(e, styleMap, isOverview))

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
  nodes: (Pick<FlowNodeData, 'screen_id' | 'screen_name' | 'flow_type'> & { position?: { x: number; y: number } })[],
  edges: FlowEdgeInput[]
): FlowValidationResult => {
  const errors: string[] = []
  const warnings: string[] = []
  const mainNodes = nodes.filter((node) => node.flow_type === 'main')
  const mainNodeIds = new Set(mainNodes.map((node) => String(node.screen_id)))
  const mainEdges = edges.filter(
    (edge) =>
      mainNodeIds.has(edge.source) && mainNodeIds.has(edge.target) && edge.edge_type === 'normal'
  )

  if (mainNodes.length === 0) {
    errors.push('至少需要保留一个主干节点')
  }

  nodes.forEach((node) => {
    if (!node.screen_name.trim()) {
      errors.push(`存在未命名页面（screen_id=${node.screen_id}）`)
    }
    if (node.position) {
      if (node.position.x < -2000 || node.position.x > 15000 || node.position.y < -2000 || node.position.y > 15000) {
        warnings.push(`${node.screen_name} 位置可能超出画布可视区域`)
      }
    }
  })

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const posA = nodes[i].position
      const posB = nodes[j].position
      if (posA && posB) {
        const dx = posA.x - posB.x
        const dy = posA.y - posB.y
        if (Math.sqrt(dx * dx + dy * dy) < 50) {
          warnings.push(`${nodes[i].screen_name} 与 ${nodes[j].screen_name} 位置重叠`)
        }
      }
    }
  }

  edges.forEach((edge) => {
    if (edge.edge_type !== 'normal' && !edge.condition.trim()) {
      const labelMap: Record<string, string> = {
        branch: '分支触发条件',
        exception: '异常场景',
        bypass: '旁路出现时机',
      }
      warnings.push(`${edge.label} 缺少${labelMap[edge.edge_type] || '说明'}，系统将自动推断`)
    }
  })

  if (mainNodes.length > 1 && mainEdges.length === 0) {
    warnings.push('当前主干节点之间没有正常连线，AI 可能无法稳定理解主流程')
  }

  return { errors, warnings }
}

/** 距离阈值（px），用于自动连线 */
export const AUTO_CONNECT_DISTANCE = 350

/**
 * 基于节点物理距离自动生成连线。
 * 距离小于阈值的节点对自动建立边，方向从左/上到右/下。
 * 边类型根据源和目标节点的 flow_type 推断：
 * - main → main → 'normal'
 * - * → branch → 'branch'
 * - * → exception → 'exception'
 * - * → bypass → 'bypass'
 */
export const generateAutoEdges = (
  nodes: FlowEditorNode[],
  distanceThreshold: number = AUTO_CONNECT_DISTANCE
): Edge[] => {
  const edges: Edge[] = []

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const nodeA = nodes[i]
      const nodeB = nodes[j]

      const dx = nodeA.position.x - nodeB.position.x
      const dy = nodeA.position.y - nodeB.position.y
      const distance = Math.sqrt(dx * dx + dy * dy)

      if (distance < distanceThreshold) {
        // 方向：从左/上 → 右/下
        const source =
          nodeA.position.x < nodeB.position.x ||
          (nodeA.position.x === nodeB.position.x && nodeA.position.y < nodeB.position.y)
            ? nodeA
            : nodeB
        const target = source === nodeA ? nodeB : nodeA

        if (source.id === target.id) continue

        // 根据目标节点 flow_type 推断边类型
        const sourceType = getNodeData(source).flow_type
        const targetType = getNodeData(target).flow_type

        let edgeType: 'normal' | 'branch' | 'exception' | 'bypass'
        if (sourceType === 'main' && targetType === 'main') {
          edgeType = 'normal'
        } else if (targetType === 'branch') {
          edgeType = 'branch'
        } else if (targetType === 'exception') {
          edgeType = 'exception'
        } else if (targetType === 'bypass') {
          edgeType = 'bypass'
        } else if (sourceType !== 'main' && targetType === 'main') {
          // 分支/异常/旁路 → 主干：视为回归主干，用 normal
          edgeType = 'normal'
        } else {
          edgeType = 'branch'
        }

        // 根据相对位置选择连接点：水平主导用左右，垂直主导用上下
        const absDx = Math.abs(dx)
        const absDy = Math.abs(dy)
        const isVertical = absDy > absDx
        const sourceHandle = isVertical ? 'source-bottom' : 'source-right'
        const targetHandle = isVertical ? 'target-top' : 'target-left'

        edges.push({
          id: `auto_${source.id}_${target.id}`,
          source: source.id,
          target: target.id,
          sourceHandle,
          targetHandle,
          type: 'default',
          data: { edge_type: edgeType },
        })
      }
    }
  }

  return edges
}

export const useFlowHistory = () => {
  const historyStack = ref<{ nodes: FlowEditorNode[]; edges: FlowGraphEdge[] }[]>([])
  const canUndo = computed(() => historyStack.value.length > 0)

  const saveToHistory = (nodes: FlowEditorNode[], edges: FlowGraphEdge[]) => {
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

export const computeUpstreamNodeIds = (edges: Edge[], nodeId: string): Set<string> => {
  const upstream = new Set<string>()
  const queue = [nodeId]
  let head = 0
  while (head < queue.length) {
    const currentId = queue[head]
    head += 1
    edges.forEach((edge) => {
      if (edge.source === edge.target) return
      if (edge.target === currentId && !upstream.has(edge.source)) {
        upstream.add(edge.source)
        queue.push(edge.source)
      }
    })
  }
  return upstream
}

export const computeDownstreamNodeIds = (edges: Edge[], nodeId: string): Set<string> => {
  const downstream = new Set<string>()
  const queue = [nodeId]
  let head = 0
  while (head < queue.length) {
    const currentId = queue[head]
    head += 1
    edges.forEach((edge) => {
      if (edge.source === edge.target) return
      if (edge.source === currentId && !downstream.has(edge.target)) {
        downstream.add(edge.target)
        queue.push(edge.target)
      }
    })
  }
  return downstream
}

export const computeRelatedEdgeIds = (edges: Edge[], nodeIds: Set<string>): Set<string> => {
  const related = new Set<string>()
  edges.forEach((edge) => {
    if (nodeIds.has(edge.source) || nodeIds.has(edge.target)) {
      related.add(edge.id)
    }
  })
  return related
}

export const computeBranchChildren = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  parentNodeId: string
): Array<{ node: FlowEditorNode; edge: Edge }> => {
  const results: Array<{ node: FlowEditorNode; edge: Edge }> = []
  const nodeMap = new Map(nodes.map((n) => [n.id, n]))
  edges.forEach((edge) => {
    if (
      edge.source === parentNodeId &&
      edge.data?.edge_type &&
      ['branch', 'exception', 'bypass'].includes(edge.data.edge_type as string)
    ) {
      const child = nodeMap.get(edge.target)
      if (child) {
        results.push({ node: child, edge })
      }
    }
  })
  return results
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
