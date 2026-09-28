/**
 * useFlowCore - 流程编辑核心模块
 *
 * 合并自：useFlowEditor.ts / useFlowLayout.ts / useFlowMainOrder.ts /
 * useFlowGroupBackground.ts / flow/{flowEditorTypes,flowLayoutTypes,
 * flowEditorConstants,flowEditorUtils,flowEditorComposables}.ts
 *
 * 提供流程编辑器的基础类型、常量、工具函数、布局算法、主干顺序操作与分组背景。
 */
import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import { useVueFlow, MarkerType, type Styles, type Edge } from '@vue-flow/core'
import { ElMessage } from 'element-plus'
import type { FlowNodeData } from '@/store/flowSort'
import type { TagType } from '@/types/element-plus'

// ============================================================================
// 类型定义（flowEditorTypes + flowLayoutTypes）
// ============================================================================

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
    state?: string
    description?: string
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
  type?: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
  style?: Edge['style']
  animated?: boolean
  hidden?: boolean
  selected?: boolean
  markerEnd?: Edge['markerEnd']
  data?: Record<string, unknown>
}

export type EdgeStyleConfig = Styles & {
  stroke: string
  strokeWidth: number
  strokeDasharray?: string
}

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

export interface EdgeHandles {
  sourceHandle: string
  targetHandle: string
  edgeType: 'normal' | 'branch' | 'exception' | 'bypass'
}

export interface LayoutOptions {
  mainGapX: number
  branchGapY: number
  mainStartY: number
  branchStartY: number
  typeGapY: number
  nestedIndentX: number
  childrenHorizontalGap: number
  maxChildrenPerColumn: number
  maxMainPerRow: number
}

export type LayoutMode = 'standard' | 'compact' | 'type-layered' | 'focused-path' | 'swimlane'

// ============================================================================
// 常量（flowEditorConstants + flowLayoutTypes 常量）
// ============================================================================

export const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  mainGapX: 280,
  branchGapY: 200,
  mainStartY: 0,
  branchStartY: 200,
  typeGapY: 60,
  nestedIndentX: 60,
  childrenHorizontalGap: 280,
  maxChildrenPerColumn: 4,
  maxMainPerRow: 8,
}

export const COMPACT_OPTIONS: Partial<LayoutOptions> = {
  mainGapX: 200,
  branchGapY: 140,
  branchStartY: 140,
  typeGapY: 40,
  nestedIndentX: 40,
  childrenHorizontalGap: 220,
  maxChildrenPerColumn: 5,
}

export const SWIMLANE_OPTIONS: Partial<LayoutOptions> = {
  mainGapX: 260,
  branchGapY: 180,
  branchStartY: 180,
  typeGapY: 40,
  nestedIndentX: 40,
  childrenHorizontalGap: 240,
  maxChildrenPerColumn: 4,
  maxMainPerRow: 6,
}

export const LAYOUT_MODE_LABELS: Record<LayoutMode, string> = {
  standard: '标准布局',
  compact: '紧凑布局',
  'type-layered': '按类型分层',
  'focused-path': '仅整理当前路径',
  swimlane: '泳道布局',
}

export const EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#409eff', strokeWidth: 2 },
  branch: { stroke: '#67c23a', strokeWidth: 2 },
  exception: { stroke: '#f56c6c', strokeWidth: 2, strokeDasharray: '5 5' },
  bypass: { stroke: '#e6a23c', strokeWidth: 2, strokeDasharray: '3 3' },
}

export const OVERVIEW_EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#c8cdd5', strokeWidth: 1 },
  branch: { stroke: '#a4d48d', strokeWidth: 1 },
  exception: { stroke: '#f0b8b8', strokeWidth: 1, strokeDasharray: '5 5' },
  bypass: { stroke: '#ebd3a0', strokeWidth: 1, strokeDasharray: '3 3' },
}

export const FLOW_TYPE_TAG_MAP: Record<string, TagType> = {
  main: 'primary',
  branch: 'success',
  exception: 'danger',
  bypass: 'warning',
}

export const FLOW_TYPE_LABEL_MAP: Record<string, string> = {
  main: '主干',
  branch: '分支',
  exception: '异常',
  bypass: '弹窗',
}

export const AUTO_CONNECT_DISTANCE = 350

// ============================================================================
// 工具函数（flowEditorUtils）
// ============================================================================

export const getNodeData = (node: FlowEditorNode) => node.data as EditorNodeData

const deriveMainOrderFromEdges = (mainNodeIds: Set<string>, edges: Edge[]): string[] | null => {
  const incoming = new Map<string, string>()
  for (const e of edges) {
    const edgeType = (e.data as { edge_type?: string })?.edge_type
    if (edgeType === 'normal' && mainNodeIds.has(e.source) && mainNodeIds.has(e.target)) {
      if (!incoming.has(e.target)) incoming.set(e.target, e.source)
    }
  }
  if (incoming.size === 0) return null
  const allSources = new Set(incoming.values())
  const headCandidates = [...mainNodeIds].filter((id) => !incoming.has(id) && allSources.has(id))
  let headId: string | undefined
  if (headCandidates.length === 1) headId = headCandidates[0]
  else if (headCandidates.length > 1) headId = headCandidates[0]
  else headId = [...mainNodeIds][0]
  const ordered: string[] = [headId]
  const visited = new Set<string>([headId])
  const outgoing = new Map<string, string>()
  for (const [target, source] of incoming) outgoing.set(source, target)
  let current = headId
  while (outgoing.has(current)) {
    const next = outgoing.get(current)!
    if (visited.has(next)) break
    visited.add(next)
    ordered.push(next)
    current = next
  }
  return ordered.length > 1 ? ordered : null
}

export const getMainNodesInOrder = (nodes: FlowEditorNode[], edges?: Edge[]): FlowEditorNode[] => {
  const mainNodes = nodes.filter((node) => getNodeData(node).flow_type === 'main')
  if (edges) {
    const mainNodeIds = new Set(mainNodes.map((n) => n.id))
    const edgeOrder = deriveMainOrderFromEdges(mainNodeIds, edges)
    if (edgeOrder) {
      const orderMap = new Map(edgeOrder.map((id, idx) => [id, idx]))
      return mainNodes.sort((a, b) => {
        const aOrder = orderMap.get(a.id) ?? Number.MAX_SAFE_INTEGER
        const bOrder = orderMap.get(b.id) ?? Number.MAX_SAFE_INTEGER
        if (aOrder !== bOrder) return aOrder - bOrder
        return a.position.x - b.position.x
      })
    }
  }
  return [...mainNodes].sort((a, b) => {
    const aOrder = getNodeData(a).main_order ?? Number.MAX_SAFE_INTEGER
    const bOrder = getNodeData(b).main_order ?? Number.MAX_SAFE_INTEGER
    if (aOrder !== bOrder) return aOrder - bOrder
    return a.position.x - b.position.x
  })
}

export const getOrderedNodesForSubmit = (nodes: FlowEditorNode[], edges?: Edge[]) => {
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const otherNodes = [...nodes]
    .filter((node) => getNodeData(node).flow_type !== 'main')
    .sort((a, b) => {
      if (a.position.x !== b.position.x) return a.position.x - b.position.x
      return a.position.y - b.position.y
    })
  return [...mainNodes, ...otherNodes]
}

export const normalizeMainNodeOrders = (nodes: FlowEditorNode[], edges?: Edge[]) => {
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const mainOrderMap = new Map(mainNodes.map((node, index) => [node.id, index + 1]))
  return nodes.map((node) => {
    const nodeData = getNodeData(node)
    if (nodeData.flow_type === 'main')
      return { ...node, data: { ...nodeData, main_order: mainOrderMap.get(node.id) } }
    const { main_order: _mainOrder, ...restData } = nodeData
    return { ...node, data: restData }
  })
}

export const layoutMainNodesByOrder = (nodes: FlowEditorNode[], edges?: Edge[]) => {
  const mainNodes = getMainNodesInOrder(nodes, edges)
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

export const validateFlowData = (
  nodes: (Pick<EditorNodeData, 'screen_id' | 'screen_name' | 'flow_type'> & {
    position?: { x: number; y: number }
  })[],
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
  if (mainNodes.length === 0) errors.push('至少需要保留一个主干节点')
  nodes.forEach((node) => {
    if (!node.screen_name.trim()) errors.push(`存在未命名页面（screen_id=${node.screen_id}）`)
    if (
      node.position &&
      (node.position.x < -2000 ||
        node.position.x > 15000 ||
        node.position.y < -2000 ||
        node.position.y > 15000)
    )
      warnings.push(`${node.screen_name} 位置可能超出画布可视区域`)
  })
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const posA = nodes[i].position
      const posB = nodes[j].position
      if (posA && posB) {
        const dx = posA.x - posB.x
        const dy = posA.y - posB.y
        if (Math.sqrt(dx * dx + dy * dy) < 50)
          warnings.push(`${nodes[i].screen_name} 与 ${nodes[j].screen_name} 位置重叠`)
      }
    }
  }
  edges.forEach((edge) => {
    if (edge.edge_type !== 'normal' && !edge.condition.trim()) {
      const labelMap: Record<string, string> = {
        branch: '分支触发条件',
        exception: '异常场景',
        bypass: '弹窗出现时机',
      }
      warnings.push(`${edge.label} 缺少${labelMap[edge.edge_type] || '说明'}，系统将自动推断`)
    }
  })
  if (mainNodes.length > 1 && mainEdges.length === 0)
    warnings.push('当前主干节点之间没有正常连线，AI 可能无法稳定理解主流程')
  return { errors, warnings }
}

export const inferEdgeType = (sourceType: string, targetType: string): EdgeHandles => {
  let edgeType: 'normal' | 'branch' | 'exception' | 'bypass'
  if (sourceType === 'main' && targetType === 'main') edgeType = 'normal'
  else if (targetType === 'branch') edgeType = 'branch'
  else if (targetType === 'exception') edgeType = 'exception'
  else if (targetType === 'bypass') edgeType = 'bypass'
  else if (sourceType !== 'main' && targetType === 'main') edgeType = 'normal'
  else edgeType = 'branch'
  let sourceHandle: string
  let targetHandle: string
  if (edgeType !== 'normal') {
    if (edgeType === 'exception' || edgeType === 'bypass') {
      sourceHandle = 'source-top'
      targetHandle = 'target-bottom'
    } else {
      sourceHandle = 'source-bottom'
      targetHandle = 'target-top'
    }
  } else {
    sourceHandle = 'source-right'
    targetHandle = 'target-left'
  }
  return { edgeType, sourceHandle, targetHandle }
}

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
        const source =
          nodeA.position.x < nodeB.position.x ||
          (nodeA.position.x === nodeB.position.x && nodeA.position.y < nodeB.position.y)
            ? nodeA
            : nodeB
        const target = source === nodeA ? nodeB : nodeA
        if (source.id === target.id) continue
        const { edgeType, sourceHandle, targetHandle } = inferEdgeType(
          getNodeData(source).flow_type,
          getNodeData(target).flow_type
        )
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
    if (nodeIds.has(edge.source) || nodeIds.has(edge.target)) related.add(edge.id)
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
      if (child) results.push({ node: child, edge })
    }
  })
  return results
}

// ============================================================================
// 内部 composables（flowEditorComposables）
// ============================================================================

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

export const useFlowSelection = () => {
  const selectedNodes = ref<string[]>([])
  const draggingNodeId = ref<string | null>(null)

  const getSelectedMainNodeId = (allNodes: FlowEditorNode[]): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = allNodes.find((n) => n.id === selectedNodes.value[0])
    return node && (node.data as { flow_type: string }).flow_type === 'main' ? node.id : null
  }

  const getSelectedMainOrder = (allNodes: FlowEditorNode[]): number | null => {
    const nodeId = getSelectedMainNodeId(allNodes)
    if (!nodeId) return null
    const node = allNodes.find((n) => n.id === nodeId)
    return node ? ((node.data as { main_order?: number }).main_order ?? null) : null
  }

  return { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder }
}

// ============================================================================
// 布局算法（useFlowLayout）
// ============================================================================

export const layeredAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const nonMainNodes = nodes.filter((n) => getNodeData(n).flow_type !== 'main')
  const positionMap = new Map<string, { x: number; y: number }>()
  mainNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.mainStartY })
  })
  const targetToSourceMap = new Map<string, string>()
  edges.forEach((e) => {
    const edgeType = (e.data as { edge_type?: string })?.edge_type
    const isSemantic = edgeType && ['branch', 'exception', 'bypass'].includes(edgeType)
    if (!targetToSourceMap.has(e.target)) targetToSourceMap.set(e.target, e.source)
    else if (isSemantic) {
      const existingEdgeType = edges.find(
        (pe) => pe.target === e.target && pe.source === targetToSourceMap.get(e.target)
      )?.data?.edge_type
      if (
        !existingEdgeType ||
        !['branch', 'exception', 'bypass'].includes(existingEdgeType as string)
      )
        targetToSourceMap.set(e.target, e.source)
    }
  })
  const childrenBySource = new Map<string, FlowEditorNode[]>()
  nonMainNodes.forEach((node) => {
    const d = getNodeData(node)
    const sourceId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(node.id)
    if (!sourceId) return
    if (!childrenBySource.has(sourceId)) childrenBySource.set(sourceId, [])
    childrenBySource.get(sourceId)!.push(node)
  })
  const computeDepth = (nodeId: string, visited: Set<string>): number => {
    if (visited.has(nodeId)) return 0
    visited.add(nodeId)
    const node = nodes.find((n) => n.id === nodeId)
    if (!node) return 0
    const d = getNodeData(node)
    if (d.flow_type === 'main') return 0
    const parentId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(nodeId)
    if (!parentId) return 1
    return computeDepth(parentId, visited) + 1
  }
  const layoutChildren = (
    sourceId: string,
    sourcePos: { x: number; y: number },
    depth: number,
    visited: Set<string> = new Set()
  ) => {
    if (visited.has(sourceId)) return
    visited.add(sourceId)
    const children = childrenBySource.get(sourceId)
    if (!children || children.length === 0) return
    const exceptionChildren = children.filter(
      (n) => getNodeData(n).flow_type === 'exception' || getNodeData(n).flow_type === 'bypass'
    )
    const belowChildren = children.filter(
      (n) => getNodeData(n).flow_type !== 'exception' && getNodeData(n).flow_type !== 'bypass'
    )
    const calcRequiredColumns = (count: number) =>
      Math.max(1, Math.ceil(count / opts.maxChildrenPerColumn))
    const layoutInGrid = (
      typedChildren: FlowEditorNode[],
      startX: number,
      startY: number,
      cols: number
    ) => {
      typedChildren.forEach((child, idx) => {
        const col = idx % cols
        const row = Math.floor(idx / cols)
        const childPos = {
          x: startX + col * opts.childrenHorizontalGap,
          y: startY + row * opts.branchGapY,
        }
        positionMap.set(child.id, childPos)
        layoutChildren(child.id, childPos, depth + 1, visited)
      })
      return Math.ceil(typedChildren.length / cols) * opts.branchGapY
    }
    if (exceptionChildren.length > 0) {
      const cols = calcRequiredColumns(exceptionChildren.length)
      const totalHeight = Math.ceil(exceptionChildren.length / cols) * opts.branchGapY
      layoutInGrid(
        exceptionChildren,
        sourcePos.x + depth * opts.nestedIndentX,
        sourcePos.y - totalHeight,
        cols
      )
    }
    let currentY = sourcePos.y + opts.branchStartY
    const belowTypes = ['branch'] as const
    belowTypes.forEach((flowType) => {
      const typedChildren = belowChildren.filter((n) => getNodeData(n).flow_type === flowType)
      if (typedChildren.length === 0) return
      const cols = calcRequiredColumns(typedChildren.length)
      const usedHeight = layoutInGrid(
        typedChildren,
        sourcePos.x + depth * opts.nestedIndentX,
        currentY,
        cols
      )
      currentY += usedHeight + opts.typeGapY
    })
  }
  mainNodes.forEach((mainNode) => {
    const mainPos = positionMap.get(mainNode.id)
    if (mainPos) layoutChildren(mainNode.id, mainPos, 0)
  })
  nonMainNodes.forEach((node) => {
    if (positionMap.has(node.id)) return
    const d = getNodeData(node)
    const sourceId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(node.id)
    if (sourceId && positionMap.has(sourceId)) {
      const sourcePos = positionMap.get(sourceId)!
      const depth = computeDepth(node.id, new Set())
      const childPos = {
        x: sourcePos.x + depth * opts.nestedIndentX,
        y: sourcePos.y + opts.branchStartY,
      }
      positionMap.set(node.id, childPos)
      layoutChildren(node.id, childPos, depth + 1)
    }
  })
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  let orphanY = 0
  nonMainNodes.forEach((node) => {
    if (!positionMap.has(node.id)) {
      positionMap.set(node.id, { x: orphanStartX, y: orphanY })
      orphanY += 200
    }
  })
  return nodes.map((node) => {
    const pos = positionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

export const compactAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => layeredAutoLayout(nodes, edges, { ...COMPACT_OPTIONS, ...options })

export const typeLayeredAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const branchNodes = nodes.filter((n) => getNodeData(n).flow_type === 'branch')
  const exceptionNodes = nodes.filter((n) => getNodeData(n).flow_type === 'exception')
  const bypassNodes = nodes.filter((n) => getNodeData(n).flow_type === 'bypass')
  const orphanNodes = nodes.filter((n) => {
    if (getNodeData(n).flow_type === 'main') return false
    return !edges.some((e) => e.target === n.id || e.source === n.id)
  })
  const positionMap = new Map<string, { x: number; y: number }>()
  mainNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: 0 })
  })
  branchNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.branchStartY })
  })
  const aboveNodes = [...exceptionNodes, ...bypassNodes]
  aboveNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: -opts.branchStartY })
  })
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  orphanNodes.forEach((node, index) => {
    if (!positionMap.has(node.id)) positionMap.set(node.id, { x: orphanStartX, y: index * 200 })
  })
  return nodes.map((node) => {
    const pos = positionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

export const focusedPathAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  focusedNodeId: string | null,
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  if (!focusedNodeId) return layeredAutoLayout(nodes, edges, options)
  const pathNodeIds = new Set<string>([focusedNodeId])
  const collectUpstream = (id: string) => {
    edges.forEach((e) => {
      if (e.target === id && !pathNodeIds.has(e.source)) {
        pathNodeIds.add(e.source)
        collectUpstream(e.source)
      }
    })
  }
  const collectDownstream = (id: string) => {
    edges.forEach((e) => {
      if (e.source === id && !pathNodeIds.has(e.target)) {
        pathNodeIds.add(e.target)
        collectDownstream(e.target)
      }
    })
  }
  collectUpstream(focusedNodeId)
  collectDownstream(focusedNodeId)
  const pathNodes = nodes.filter((n) => pathNodeIds.has(n.id))
  const pathEdges = edges.filter((e) => pathNodeIds.has(e.source) && pathNodeIds.has(e.target))
  const laidOutPathNodes = layeredAutoLayout(pathNodes, pathEdges, {
    ...DEFAULT_LAYOUT_OPTIONS,
    ...options,
  })
  const pathPositionMap = new Map(laidOutPathNodes.map((n) => [n.id, n.position]))
  return nodes.map((node) => {
    const pos = pathPositionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

export const swimlaneAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...SWIMLANE_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const nonMainNodes = nodes.filter((n) => getNodeData(n).flow_type !== 'main')
  const positionMap = new Map<string, { x: number; y: number }>()

  const targetToSourceMap = new Map<string, string>()
  edges.forEach((e) => {
    const edgeType = (e.data as { edge_type?: string })?.edge_type
    const isSemantic = edgeType && ['branch', 'exception', 'bypass'].includes(edgeType)
    if (!targetToSourceMap.has(e.target)) targetToSourceMap.set(e.target, e.source)
    else if (isSemantic) {
      const existingEdgeType = edges.find(
        (pe) => pe.target === e.target && pe.source === targetToSourceMap.get(e.target)
      )?.data?.edge_type
      if (
        !existingEdgeType ||
        !['branch', 'exception', 'bypass'].includes(existingEdgeType as string)
      )
        targetToSourceMap.set(e.target, e.source)
    }
  })

  const childrenBySource = new Map<string, FlowEditorNode[]>()
  nonMainNodes.forEach((node) => {
    const d = getNodeData(node)
    const sourceId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(node.id)
    if (!sourceId) return
    if (!childrenBySource.has(sourceId)) childrenBySource.set(sourceId, [])
    childrenBySource.get(sourceId)!.push(node)
  })

  const rowGapY = opts.branchStartY + opts.branchGapY * 2 + opts.typeGapY

  mainNodes.forEach((node, index) => {
    const row = Math.floor(index / opts.maxMainPerRow)
    const col = index % opts.maxMainPerRow
    positionMap.set(node.id, {
      x: col * opts.mainGapX,
      y: row * rowGapY + opts.mainStartY,
    })
  })

  const layoutChildren = (
    sourceId: string,
    sourcePos: { x: number; y: number },
    visited: Set<string> = new Set()
  ) => {
    if (visited.has(sourceId)) return
    visited.add(sourceId)
    const children = childrenBySource.get(sourceId)
    if (!children || children.length === 0) return

    const branchChildren = children.filter((n) => getNodeData(n).flow_type === 'branch')
    const exceptionChildren = children.filter(
      (n) => getNodeData(n).flow_type === 'exception' || getNodeData(n).flow_type === 'bypass'
    )

    let currentY = sourcePos.y + opts.branchStartY
    if (branchChildren.length > 0) {
      const cols = Math.max(1, Math.ceil(branchChildren.length / opts.maxChildrenPerColumn))
      branchChildren.forEach((child, idx) => {
        const col = idx % cols
        const row = Math.floor(idx / cols)
        const childPos = {
          x: sourcePos.x + col * opts.childrenHorizontalGap,
          y: currentY + row * opts.branchGapY,
        }
        positionMap.set(child.id, childPos)
        layoutChildren(child.id, childPos, visited)
      })
      currentY += Math.ceil(branchChildren.length / cols) * opts.branchGapY + opts.typeGapY
    }

    if (exceptionChildren.length > 0) {
      const cols = Math.max(1, Math.ceil(exceptionChildren.length / opts.maxChildrenPerColumn))
      const totalHeight = Math.ceil(exceptionChildren.length / cols) * opts.branchGapY
      exceptionChildren.forEach((child, idx) => {
        const col = idx % cols
        const row = Math.floor(idx / cols)
        const childPos = {
          x: sourcePos.x + col * opts.childrenHorizontalGap,
          y: sourcePos.y - totalHeight + row * opts.branchGapY,
        }
        positionMap.set(child.id, childPos)
        layoutChildren(child.id, childPos, visited)
      })
    }
  }

  mainNodes.forEach((mainNode) => {
    const mainPos = positionMap.get(mainNode.id)
    if (mainPos) layoutChildren(mainNode.id, mainPos)
  })

  nonMainNodes.forEach((node) => {
    if (positionMap.has(node.id)) return
    const d = getNodeData(node)
    const sourceId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(node.id)
    if (sourceId && positionMap.has(sourceId)) {
      const sourcePos = positionMap.get(sourceId)!
      positionMap.set(node.id, {
        x: sourcePos.x + opts.nestedIndentX,
        y: sourcePos.y + opts.branchStartY,
      })
    }
  })

  const maxMainX =
    mainNodes.length > 0 ? (Math.min(mainNodes.length, opts.maxMainPerRow) - 1) * opts.mainGapX : 0
  const maxRow = mainNodes.length > 0 ? Math.floor((mainNodes.length - 1) / opts.maxMainPerRow) : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  const orphanStartY = maxRow * rowGapY
  let orphanY = orphanStartY
  nonMainNodes.forEach((node) => {
    if (!positionMap.has(node.id)) {
      positionMap.set(node.id, { x: orphanStartX, y: orphanY })
      orphanY += 200
    }
  })

  return nodes.map((node) => {
    const pos = positionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

export const autoLayoutByMode = (
  mode: LayoutMode,
  nodes: FlowEditorNode[],
  edges: Edge[],
  focusedNodeId?: string | null,
  options?: Partial<LayoutOptions>
): FlowEditorNode[] => {
  switch (mode) {
    case 'compact':
      return compactAutoLayout(nodes, edges, options)
    case 'type-layered':
      return typeLayeredAutoLayout(nodes, edges, options)
    case 'focused-path':
      return focusedPathAutoLayout(nodes, edges, focusedNodeId ?? null, options)
    case 'swimlane':
      return swimlaneAutoLayout(nodes, edges, options)
    case 'standard':
    default:
      return layeredAutoLayout(nodes, edges, options)
  }
}

export const useFlowLayout = () => ({
  layeredAutoLayout,
  compactAutoLayout,
  typeLayeredAutoLayout,
  focusedPathAutoLayout,
  swimlaneAutoLayout,
  autoLayoutByMode,
})

// ============================================================================
// 主干顺序操作（useFlowMainOrder）
// ============================================================================

export interface UseFlowMainOrderOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  selectedNodes: Ref<string[]>
  focusedNodeId: Ref<string | null>
  collapsedParentNodeIds: Ref<string[]>
  emitSortData: () => void
  saveSnapshot: () => void
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  getMainNodesInOrder: (nodes: FlowEditorNode[], edges?: Edge[]) => FlowEditorNode[]
  normalizeMainNodeOrders: (nodes: FlowEditorNode[], edges?: Edge[]) => FlowEditorNode[]
  /** 对边列表应用完整样式（含路径高亮） */
  applyAllEdgeStyles: (edges: FlowGraphEdge[]) => FlowGraphEdge[]
  /** 共享的程序化边变更标志（与 useFlowEdgeOps/useFlowTypeOps 共用） */
  isProgrammaticEdgeChange: Ref<boolean>
}

/**
 * 主干顺序操作 composable
 * 封装删除选中节点、主干节点前移/后移等逻辑
 */
export function useFlowMainOrder(options: UseFlowMainOrderOptions) {
  const {
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    focusedNodeId,
    collapsedParentNodeIds,
    emitSortData,
    saveSnapshot,
    getNodeData: getNodeDataFn,
    getMainNodesInOrder: getMainNodesInOrderFn,
    normalizeMainNodeOrders: normalizeMainNodeOrdersFn,
    applyAllEdgeStyles,
    isProgrammaticEdgeChange,
  } = options

  // ---- 辅助方法 ----

  /** 获取当前选中的主干节点 ID（仅当选中恰好 1 个主干节点时返回） */
  const getSelectedMainNodeId = (_nodes?: FlowEditorNode[]): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeDataFn(node).flow_type === 'main' ? node.id : null
  }

  /** 获取当前选中的主干节点的 main_order */
  const getSelectedMainOrder = (_nodes?: FlowEditorNode[]): number | null => {
    const nodeId = getSelectedMainNodeId()
    if (!nodeId) return null
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    return node ? (getNodeDataFn(node).main_order ?? null) : null
  }

  // ---- 核心操作 ----

  /** 删除选中的节点及其关联边 */
  const handleDeleteSelected = (): void => {
    if (selectedNodes.value.length === 0) return
    const deletedCount = selectedNodes.value.length
    const deletedSet = new Set(selectedNodes.value)
    saveSnapshot()
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = vueFlowEdges.value.filter(
      (e: FlowGraphEdge) => !deletedSet.has(e.source) && !deletedSet.has(e.target)
    )
    vueFlowNodes.value = normalizeMainNodeOrdersFn(
      vueFlowNodes.value.filter((n) => !deletedSet.has(n.id)),
      vueFlowEdges.value as unknown as Edge[]
    )
    collapsedParentNodeIds.value = collapsedParentNodeIds.value.filter((id) => !deletedSet.has(id))
    if (focusedNodeId.value && deletedSet.has(focusedNodeId.value)) {
      focusedNodeId.value = null
    }
    selectedNodes.value = []
    emitSortData()
    ElMessage.success(`已删除 ${deletedCount} 个节点`)
  }

  /** 判断选中的主干节点是否可以向前（序号减小方向）移动 */
  const canMoveMainBackward = (): boolean => (getSelectedMainOrder() ?? 0) > 1

  /** 判断选中的主干节点是否可以向后（序号增大方向）移动 */
  const canMoveMainForward = (): boolean => {
    const selectedMainOrder = getSelectedMainOrder()
    if (selectedMainOrder == null) return false
    return selectedMainOrder < getMainNodeCount(vueFlowNodes.value)
  }

  /**
   * 移动选中的主干节点
   * @param direction -1 表示前移（序号减小），1 表示后移（序号增大）
   */
  const moveSelectedMainNode = (direction: -1 | 1): void => {
    const selectedNodeId = getSelectedMainNodeId()
    if (!selectedNodeId) return
    const selectedNode = vueFlowNodes.value.find((n) => n.id === selectedNodeId)
    if (!selectedNode) return

    const orderedMainNodes = getMainNodesInOrderFn(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[])
    const currentIndex = orderedMainNodes.findIndex((node) => node.id === selectedNode.id)
    const targetIndex = currentIndex + direction
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= orderedMainNodes.length) return

    saveSnapshot()
    isProgrammaticEdgeChange.value = true
    const reorderedMainNodes = [...orderedMainNodes]
    ;[reorderedMainNodes[currentIndex], reorderedMainNodes[targetIndex]] = [
      reorderedMainNodes[targetIndex],
      reorderedMainNodes[currentIndex],
    ]
    const mainOrderMap = new Map(reorderedMainNodes.map((node, index) => [node.id, index + 1]))
    // 不传 edges：此处的 main_order 已由显式交换指定，旧边尚未重建，传入 edges 会覆盖为错误顺序。
    // emitSortData 在边重建后会从新边推导并写回正确的 main_order。
    vueFlowNodes.value = layoutMainNodesByOrder(
      normalizeMainNodeOrdersFn(
        vueFlowNodes.value.map((node) => {
          if (!mainOrderMap.has(node.id)) return node
          return {
            ...node,
            data: {
              ...getNodeDataFn(node),
              main_order: mainOrderMap.get(node.id),
            },
          }
        })
      )
    )
    const mainNodeIdSet = new Set(reorderedMainNodes.map((n) => n.id))
    const newMainEdges: FlowGraphEdge[] = []
    for (let i = 0; i < reorderedMainNodes.length - 1; i++) {
      const sourceNode = reorderedMainNodes[i]
      const targetNode = reorderedMainNodes[i + 1]
      const existingEdge = vueFlowEdges.value.find(
        (e) => e.source === sourceNode.id && e.target === targetNode.id
      )
      newMainEdges.push({
        ...(existingEdge || { id: `edge_${sourceNode.id}_${targetNode.id}` }),
        source: sourceNode.id,
        target: targetNode.id,
        sourceHandle: 'source-right',
        targetHandle: 'target-left',
        type: 'default',
        label: existingEdge?.label || '连线',
        data: existingEdge?.data || { edge_type: 'normal' },
      })
    }
    const nonMainEdges = vueFlowEdges.value.filter(
      (e) => !mainNodeIdSet.has(e.source) || !mainNodeIdSet.has(e.target)
    )
    vueFlowEdges.value = applyAllEdgeStyles([...nonMainEdges, ...newMainEdges])
    emitSortData()
  }

  return {
    handleDeleteSelected,
    canMoveMainBackward,
    canMoveMainForward,
    moveSelectedMainNode,
    getSelectedMainNodeId,
    getSelectedMainOrder,
  }
}

// ============================================================================
// 分组背景（useFlowGroupBackground）
// ============================================================================

/** 节点分组项 */
export interface NodeGroup {
  id: string
  label: string
  color: string
  strokeColor: string
  bounds: { x: number; y: number; width: number; height: number }
}

/** useFlowGroupBackground 配置项 */
export interface UseFlowGroupBackgroundOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
}

/** useFlowGroupBackground 返回值 */
export interface UseFlowGroupBackgroundReturn {
  showGroupBackground: Ref<boolean>
  nodeGroups: ComputedRef<NodeGroup[]>
  svgViewBox: ComputedRef<{ x: number; y: number }>
  branchChildrenMap: ComputedRef<Map<string, Array<{ node: FlowEditorNode; edge: FlowGraphEdge }>>>
}

/** 节点卡片默认尺寸，用于计算分组边界 */
const NODE_CARD_WIDTH = 220
const NODE_CARD_HEIGHT = 200

/** 分组内边距 */
const GROUP_PADDING = 20

/** 分组颜色映射 */
const TYPE_COLORS: Record<string, { color: string; strokeColor: string }> = {
  main: { color: 'rgba(64, 158, 255, 0.08)', strokeColor: 'rgba(64, 158, 255, 0.4)' },
  branch: { color: 'rgba(103, 194, 58, 0.08)', strokeColor: 'rgba(103, 194, 58, 0.4)' },
  exception: { color: 'rgba(245, 108, 108, 0.08)', strokeColor: 'rgba(245, 108, 108, 0.4)' },
  bypass: { color: 'rgba(230, 162, 60, 0.08)', strokeColor: 'rgba(230, 162, 60, 0.4)' },
}

/**
 * 从 FlowSortEditor 抽取的模块分组背景逻辑。
 * 按主干节点分组，计算每组的边界矩形与颜色，供 SVG 背景渲染。
 */
export function useFlowGroupBackground(
  options: UseFlowGroupBackgroundOptions
): UseFlowGroupBackgroundReturn {
  const { vueFlowNodes, vueFlowEdges, getNodeData: getNodeDataFn } = options
  const { viewport } = useVueFlow()

  const showGroupBackground = ref(true)

  /** 分支子节点映射：主干节点 ID → 其分支/异常/弹窗子节点列表 */
  const branchChildrenMap = computed(() => {
    const map = new Map<string, Array<{ node: FlowEditorNode; edge: FlowGraphEdge }>>()
    const nodes = vueFlowNodes.value
    const nodeMap = new Map(nodes.map((n) => [n.id, n]))
    vueFlowEdges.value.forEach((edge) => {
      if (
        edge.data?.edge_type &&
        ['branch', 'exception', 'bypass'].includes(edge.data.edge_type as string) &&
        nodeMap.has(edge.target)
      ) {
        const child = nodeMap.get(edge.target)!
        if (!map.has(edge.source)) {
          map.set(edge.source, [])
        }
        map.get(edge.source)!.push({ node: child, edge })
      }
    })
    return map
  })

  /** 按模块分组的节点列表与边界 */
  const nodeGroups = computed<NodeGroup[]>(() => {
    if (!showGroupBackground.value) return []
    const visibleNodes = vueFlowNodes.value.filter((n) => !n.hidden)
    if (visibleNodes.length === 0) return []

    // Group by parent main node (for branch/exception/bypass children)
    const groups = new Map<string, FlowEditorNode[]>()
    const mainNodes = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[])

    mainNodes.forEach((mainNode) => {
      const children = branchChildrenMap.value.get(mainNode.id)
      if (children && children.length > 0) {
        groups.set(mainNode.id, [mainNode, ...children.map((c) => c.node)])
      }
    })

    // Also group standalone main nodes that have no children
    mainNodes.forEach((mainNode) => {
      if (!groups.has(mainNode.id)) {
        groups.set(mainNode.id, [mainNode])
      }
    })

    // Orphan non-main nodes
    const groupedNodeIds = new Set<string>()
    groups.forEach((nodes) => nodes.forEach((n) => groupedNodeIds.add(n.id)))
    const orphans = visibleNodes.filter((n) => !groupedNodeIds.has(n.id))
    if (orphans.length > 0) {
      groups.set('__orphans__', orphans)
    }

    const result: NodeGroup[] = []
    groups.forEach((nodes, groupId) => {
      if (nodes.length === 0) return
      const minX = Math.min(...nodes.map((n) => n.position.x))
      const minY = Math.min(...nodes.map((n) => n.position.y))
      const maxX = Math.max(...nodes.map((n) => n.position.x + NODE_CARD_WIDTH))
      const maxY = Math.max(...nodes.map((n) => n.position.y + NODE_CARD_HEIGHT))

      const mainNode = nodes.find((n) => getNodeDataFn(n).flow_type === 'main')
      const flowType = mainNode ? getNodeDataFn(mainNode).flow_type : 'branch'
      const colors = TYPE_COLORS[flowType] || TYPE_COLORS.main
      const label = mainNode
        ? `${getNodeDataFn(mainNode).screen_name} 模块`
        : groupId === '__orphans__'
          ? '未分组'
          : '模块'

      result.push({
        id: groupId,
        label,
        color: colors.color,
        strokeColor: colors.strokeColor,
        bounds: {
          x: minX,
          y: minY,
          width: maxX - minX,
          height: maxY - minY,
        },
      })
    })

    return result
  })

  /** SVG 定位偏移，跟随画布视口 */
  const svgViewBox = computed(() => ({
    x: viewport.value?.x ?? 0,
    y: viewport.value?.y ?? 0,
  }))

  return {
    showGroupBackground,
    nodeGroups,
    svgViewBox,
    branchChildrenMap,
  }
}

/** 分组内边距常量，供模板使用 */
export const groupPadding = GROUP_PADDING
