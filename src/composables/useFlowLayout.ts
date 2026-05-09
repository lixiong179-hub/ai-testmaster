import type { Edge } from '@vue-flow/core'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import { getNodeData, getMainNodesInOrder } from '@/composables/useFlowEditor'

export interface LayoutOptions {
  /** 主干节点水平间距 */
  mainGapX: number
  /** 分支/异常/旁路节点垂直间距 */
  branchGapY: number
  /** 主干起始 Y 坐标 */
  mainStartY: number
  /** 分支起始 Y 偏移 */
  branchStartY: number
  /** 同一源节点下不同类型子节点的额外 Y 间距 */
  typeGapY: number
  /** 嵌套分支水平偏移（每层缩进） */
  nestedIndentX: number
}

const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  mainGapX: 280,
  branchGapY: 200,
  mainStartY: 0,
  branchStartY: 200,
  typeGapY: 60,
  nestedIndentX: 60,
}

/**
 * 分层自动布局：主干水平排列，分支/旁路挂在源节点下方，异常节点挂在源节点上方。
 * 支持递归嵌套：分支节点也可以有自己的子分支/异常/旁路。
 *
 * 布局规则：
 * - 主干节点：按 main_order 从左到右水平排列
 * - 异常节点：挂在源节点正上方，Y 递减
 * - 分支节点：挂在源节点正下方，Y 递增
 * - 旁路节点：挂在源节点下方，Y 起始 = 分支结束 + typeGap
 * - 嵌套分支：X 方向每层缩进 nestedIndentX，Y 方向在父分支下方继续排列
 * - 同类型多个子节点按垂直间距递增
 */
export const layeredAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes)
  const nonMainNodes = nodes.filter((n) => getNodeData(n).flow_type !== 'main')

  // 1. Position main nodes horizontally
  const positionMap = new Map<string, { x: number; y: number }>()
  mainNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.mainStartY })
  })

  // 2. Build target→source lookup (prefer branch/exception/bypass edges over normal)
  const targetToSourceMap = new Map<string, string>()
  edges.forEach((e) => {
    const edgeType = (e.data as { edge_type?: string })?.edge_type
    const isSemantic = edgeType && ['branch', 'exception', 'bypass'].includes(edgeType)
    // 语义边优先：如果已有语义边则不覆盖；如果当前是语义边则覆盖普通边
    if (isSemantic || !targetToSourceMap.has(e.target)) {
      targetToSourceMap.set(e.target, e.source)
    }
  })

  // 3. Group non-main nodes by sourceId (using parent_node_id or edge)
  const childrenBySource = new Map<string, FlowEditorNode[]>()

  nonMainNodes.forEach((node) => {
    const d = getNodeData(node)
    const sourceId =
      d.flow_meta?.parent_node_id ||
      d.flow_meta?.parent_main_node_id ||
      targetToSourceMap.get(node.id)
    if (!sourceId) return

    if (!childrenBySource.has(sourceId)) {
      childrenBySource.set(sourceId, [])
    }
    childrenBySource.get(sourceId)!.push(node)
  })

  // 4. Compute depth for each non-main node
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

  // 5. Recursive layout: process children of a source node, then recurse into each child
  const layoutChildren = (
    sourceId: string,
    sourcePos: { x: number; y: number },
    depth: number
  ) => {
    const children = childrenBySource.get(sourceId)
    if (!children || children.length === 0) return

    // Separate by type
    const exceptionChildren = children.filter((n) => getNodeData(n).flow_type === 'exception')
    const belowChildren = children.filter((n) => getNodeData(n).flow_type !== 'exception')

    // Exception nodes: above the source node
    exceptionChildren.forEach((child, idx) => {
      const childPos = {
        x: sourcePos.x + depth * opts.nestedIndentX,
        y: sourcePos.y - (idx + 1) * opts.branchGapY,
      }
      positionMap.set(child.id, childPos)
      layoutChildren(child.id, childPos, depth + 1)
    })

    // Branch and bypass: below the source node
    let currentY = sourcePos.y + opts.branchStartY
    const belowTypes = ['branch', 'bypass'] as const

    belowTypes.forEach((flowType) => {
      const typedChildren = belowChildren.filter((n) => getNodeData(n).flow_type === flowType)
      if (typedChildren.length === 0) return

      typedChildren.forEach((child, idx) => {
        const childPos = {
          x: sourcePos.x + depth * opts.nestedIndentX,
          y: currentY + idx * opts.branchGapY,
        }
        positionMap.set(child.id, childPos)
        layoutChildren(child.id, childPos, depth + 1)
      })

      currentY += typedChildren.length * opts.branchGapY + opts.typeGapY
    })
  }

  // 6. Start recursive layout from each main node
  mainNodes.forEach((mainNode) => {
    const mainPos = positionMap.get(mainNode.id)
    if (!mainPos) return
    layoutChildren(mainNode.id, mainPos, 0)
  })

  // 7. Handle non-main nodes whose parent wasn't processed yet
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

  // 8. Handle orphan nodes — move to bottom-right independent area
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  let orphanY = 0
  const orphanGapY = 200

  nonMainNodes.forEach((node) => {
    if (!positionMap.has(node.id)) {
      positionMap.set(node.id, {
        x: orphanStartX,
        y: orphanY,
      })
      orphanY += orphanGapY
    }
  })

  return nodes.map((node) => {
    const pos = positionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

export type LayoutMode = 'standard' | 'compact' | 'type-layered' | 'focused-path'

const COMPACT_OPTIONS: Partial<LayoutOptions> = {
  mainGapX: 200,
  branchGapY: 140,
  branchStartY: 140,
  typeGapY: 40,
  nestedIndentX: 40,
}

/**
 * 紧凑布局：缩小间距，适合节点较多时快速总览
 */
export const compactAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  return layeredAutoLayout(nodes, edges, { ...COMPACT_OPTIONS, ...options })
}

/**
 * 按类型分层布局：主干在中间水平带，分支在下方带，异常在上方带，旁路在最下方带。
 * 同类型节点按水平排列，不同类型占据不同 Y 层级。
 */
export const typeLayeredAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes)
  const branchNodes = nodes.filter((n) => getNodeData(n).flow_type === 'branch')
  const exceptionNodes = nodes.filter((n) => getNodeData(n).flow_type === 'exception')
  const bypassNodes = nodes.filter((n) => getNodeData(n).flow_type === 'bypass')
  const orphanNodes = nodes.filter(
    (n) => getNodeData(n).flow_type !== 'main' &&
      !edges.some((e) => e.target === n.id || e.source === n.id)
  )

  const positionMap = new Map<string, { x: number; y: number }>()

  // 主干：中间水平带 Y=0
  mainNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: 0 })
  })

  // 分支：下方带 Y=branchStartY
  branchNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.branchStartY })
  })

  // 异常：上方带 Y=-branchStartY
  exceptionNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: -opts.branchStartY })
  })

  // 旁路：最下方带 Y=branchStartY*2
  bypassNodes.forEach((node, index) => {
    positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.branchStartY * 2 })
  })

  // 孤立节点
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  orphanNodes.forEach((node, index) => {
    if (!positionMap.has(node.id)) {
      positionMap.set(node.id, { x: orphanStartX, y: index * 200 })
    }
  })

  return nodes.map((node) => {
    const pos = positionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

/**
 * 仅整理当前聚焦路径：只重新排列与 focusedNodeId 路径相关的节点，
 * 其余节点保持原位不动。
 */
export const focusedPathAutoLayout = (
  nodes: FlowEditorNode[],
  edges: Edge[],
  focusedNodeId: string | null,
  options: Partial<LayoutOptions> = {}
): FlowEditorNode[] => {
  if (!focusedNodeId) return layeredAutoLayout(nodes, edges, options)

  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }

  // 收集路径节点（上游 + 自身 + 下游）
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

  // 对路径节点执行标准布局
  const pathNodes = nodes.filter((n) => pathNodeIds.has(n.id))
  const pathEdges = edges.filter(
    (e) => pathNodeIds.has(e.source) && pathNodeIds.has(e.target)
  )
  const laidOutPathNodes = layeredAutoLayout(pathNodes, pathEdges, opts)
  const pathPositionMap = new Map(laidOutPathNodes.map((n) => [n.id, n.position]))

  // 路径节点使用新位置，其余节点保持不变
  return nodes.map((node) => {
    const pos = pathPositionMap.get(node.id)
    if (!pos) return node
    return { ...node, position: pos }
  })
}

/**
 * 根据布局模式选择对应的布局函数
 */
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
    case 'standard':
    default:
      return layeredAutoLayout(nodes, edges, options)
  }
}

export const LAYOUT_MODE_LABELS: Record<LayoutMode, string> = {
  standard: '标准布局',
  compact: '紧凑布局',
  'type-layered': '按类型分层',
  'focused-path': '仅整理当前路径',
}

export const useFlowLayout = () => ({
  layeredAutoLayout,
  compactAutoLayout,
  typeLayeredAutoLayout,
  focusedPathAutoLayout,
  autoLayoutByMode,
})
