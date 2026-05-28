import { MarkerType } from '@vue-flow/core'
import type { Edge } from '@vue-flow/core'
import type {
  FlowEditorNode,
  EditorNodeData,
  EdgeStyleConfig,
  FlowValidationResult,
  FlowEdgeInput,
  EdgeHandles,
} from './flowEditorTypes'
import { EDGE_STYLES, AUTO_CONNECT_DISTANCE } from './flowEditorConstants'

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
        bypass: '旁路出现时机',
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
