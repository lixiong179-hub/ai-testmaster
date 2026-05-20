import type { Edge } from '@vue-flow/core'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import { getNodeData, getMainNodesInOrder } from '@/composables/useFlowEditor'
import { DEFAULT_LAYOUT_OPTIONS, COMPACT_OPTIONS, type LayoutOptions, type LayoutMode, LAYOUT_MODE_LABELS } from './flow/flowLayoutTypes'

export type { LayoutOptions, LayoutMode } from './flow/flowLayoutTypes'
export { DEFAULT_LAYOUT_OPTIONS, COMPACT_OPTIONS, LAYOUT_MODE_LABELS } from './flow/flowLayoutTypes'

export const layeredAutoLayout = (nodes: FlowEditorNode[], edges: Edge[], options: Partial<LayoutOptions> = {}): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const nonMainNodes = nodes.filter((n) => getNodeData(n).flow_type !== 'main')
  const positionMap = new Map<string, { x: number; y: number }>()
  mainNodes.forEach((node, index) => { positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.mainStartY }) })
  const targetToSourceMap = new Map<string, string>()
  edges.forEach((e) => {
    const edgeType = (e.data as { edge_type?: string })?.edge_type
    const isSemantic = edgeType && ['branch', 'exception', 'bypass'].includes(edgeType)
    if (!targetToSourceMap.has(e.target)) targetToSourceMap.set(e.target, e.source)
    else if (isSemantic) {
      const existingEdgeType = edges.find((pe) => pe.target === e.target && pe.source === targetToSourceMap.get(e.target))?.data?.edge_type
      if (!existingEdgeType || !['branch', 'exception', 'bypass'].includes(existingEdgeType as string)) targetToSourceMap.set(e.target, e.source)
    }
  })
  const childrenBySource = new Map<string, FlowEditorNode[]>()
  nonMainNodes.forEach((node) => {
    const d = getNodeData(node)
    const sourceId = d.flow_meta?.parent_node_id || d.flow_meta?.parent_main_node_id || targetToSourceMap.get(node.id)
    if (!sourceId) return
    if (!childrenBySource.has(sourceId)) childrenBySource.set(sourceId, [])
    childrenBySource.get(sourceId)!.push(node)
  })
  const computeDepth = (nodeId: string, visited: Set<string>): number => {
    if (visited.has(nodeId)) return 0; visited.add(nodeId)
    const node = nodes.find((n) => n.id === nodeId); if (!node) return 0
    const d = getNodeData(node); if (d.flow_type === 'main') return 0
    const parentId = d.flow_meta?.parent_node_id || d.flow_meta?.parent_main_node_id || targetToSourceMap.get(nodeId)
    if (!parentId) return 1; return computeDepth(parentId, visited) + 1
  }
  const layoutChildren = (sourceId: string, sourcePos: { x: number; y: number }, depth: number, visited: Set<string> = new Set()) => {
    if (visited.has(sourceId)) return; visited.add(sourceId)
    const children = childrenBySource.get(sourceId); if (!children || children.length === 0) return
    const exceptionChildren = children.filter((n) => getNodeData(n).flow_type === 'exception' || getNodeData(n).flow_type === 'bypass')
    const belowChildren = children.filter((n) => getNodeData(n).flow_type !== 'exception' && getNodeData(n).flow_type !== 'bypass')
    const calcRequiredColumns = (count: number) => Math.max(1, Math.ceil(count / opts.maxChildrenPerColumn))
    const layoutInGrid = (typedChildren: FlowEditorNode[], startX: number, startY: number, cols: number) => {
      typedChildren.forEach((child, idx) => {
        const col = idx % cols; const row = Math.floor(idx / cols)
        const childPos = { x: startX + col * opts.childrenHorizontalGap, y: startY + row * opts.branchGapY }
        positionMap.set(child.id, childPos); layoutChildren(child.id, childPos, depth + 1, visited)
      }); return Math.ceil(typedChildren.length / cols) * opts.branchGapY
    }
    if (exceptionChildren.length > 0) {
      const cols = calcRequiredColumns(exceptionChildren.length)
      const totalHeight = Math.ceil(exceptionChildren.length / cols) * opts.branchGapY
      layoutInGrid(exceptionChildren, sourcePos.x + depth * opts.nestedIndentX, sourcePos.y - totalHeight, cols)
    }
    let currentY = sourcePos.y + opts.branchStartY
    const belowTypes = ['branch'] as const
    belowTypes.forEach((flowType) => {
      const typedChildren = belowChildren.filter((n) => getNodeData(n).flow_type === flowType)
      if (typedChildren.length === 0) return
      const cols = calcRequiredColumns(typedChildren.length)
      const usedHeight = layoutInGrid(typedChildren, sourcePos.x + depth * opts.nestedIndentX, currentY, cols)
      currentY += usedHeight + opts.typeGapY
    })
  }
  mainNodes.forEach((mainNode) => { const mainPos = positionMap.get(mainNode.id); if (mainPos) layoutChildren(mainNode.id, mainPos, 0) })
  nonMainNodes.forEach((node) => {
    if (positionMap.has(node.id)) return
    const d = getNodeData(node)
    const sourceId = d.flow_meta?.parent_node_id || d.flow_meta?.parent_main_node_id || targetToSourceMap.get(node.id)
    if (sourceId && positionMap.has(sourceId)) {
      const sourcePos = positionMap.get(sourceId)!; const depth = computeDepth(node.id, new Set())
      const childPos = { x: sourcePos.x + depth * opts.nestedIndentX, y: sourcePos.y + opts.branchStartY }
      positionMap.set(node.id, childPos); layoutChildren(node.id, childPos, depth + 1)
    }
  })
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2; let orphanY = 0
  nonMainNodes.forEach((node) => { if (!positionMap.has(node.id)) { positionMap.set(node.id, { x: orphanStartX, y: orphanY }); orphanY += 200 } })
  return nodes.map((node) => { const pos = positionMap.get(node.id); if (!pos) return node; return { ...node, position: pos } })
}

export const compactAutoLayout = (nodes: FlowEditorNode[], edges: Edge[], options: Partial<LayoutOptions> = {}): FlowEditorNode[] => layeredAutoLayout(nodes, edges, { ...COMPACT_OPTIONS, ...options })

export const typeLayeredAutoLayout = (nodes: FlowEditorNode[], edges: Edge[], options: Partial<LayoutOptions> = {}): FlowEditorNode[] => {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options }
  const mainNodes = getMainNodesInOrder(nodes, edges)
  const branchNodes = nodes.filter((n) => getNodeData(n).flow_type === 'branch')
  const exceptionNodes = nodes.filter((n) => getNodeData(n).flow_type === 'exception')
  const bypassNodes = nodes.filter((n) => getNodeData(n).flow_type === 'bypass')
  const orphanNodes = nodes.filter((n) => { if (getNodeData(n).flow_type === 'main') return false; return !edges.some((e) => e.target === n.id || e.source === n.id) })
  const positionMap = new Map<string, { x: number; y: number }>()
  mainNodes.forEach((node, index) => { positionMap.set(node.id, { x: index * opts.mainGapX, y: 0 }) })
  branchNodes.forEach((node, index) => { positionMap.set(node.id, { x: index * opts.mainGapX, y: opts.branchStartY }) })
  const aboveNodes = [...exceptionNodes, ...bypassNodes]
  aboveNodes.forEach((node, index) => { positionMap.set(node.id, { x: index * opts.mainGapX, y: -opts.branchStartY }) })
  const maxMainX = mainNodes.length > 0 ? (mainNodes.length - 1) * opts.mainGapX : 0
  const orphanStartX = maxMainX + opts.mainGapX * 2
  orphanNodes.forEach((node, index) => { if (!positionMap.has(node.id)) positionMap.set(node.id, { x: orphanStartX, y: index * 200 }) })
  return nodes.map((node) => { const pos = positionMap.get(node.id); if (!pos) return node; return { ...node, position: pos } })
}

export const focusedPathAutoLayout = (nodes: FlowEditorNode[], edges: Edge[], focusedNodeId: string | null, options: Partial<LayoutOptions> = {}): FlowEditorNode[] => {
  if (!focusedNodeId) return layeredAutoLayout(nodes, edges, options)
  const pathNodeIds = new Set<string>([focusedNodeId])
  const collectUpstream = (id: string) => { edges.forEach((e) => { if (e.target === id && !pathNodeIds.has(e.source)) { pathNodeIds.add(e.source); collectUpstream(e.source) } }) }
  const collectDownstream = (id: string) => { edges.forEach((e) => { if (e.source === id && !pathNodeIds.has(e.target)) { pathNodeIds.add(e.target); collectDownstream(e.target) } }) }
  collectUpstream(focusedNodeId); collectDownstream(focusedNodeId)
  const pathNodes = nodes.filter((n) => pathNodeIds.has(n.id))
  const pathEdges = edges.filter((e) => pathNodeIds.has(e.source) && pathNodeIds.has(e.target))
  const laidOutPathNodes = layeredAutoLayout(pathNodes, pathEdges, { ...DEFAULT_LAYOUT_OPTIONS, ...options })
  const pathPositionMap = new Map(laidOutPathNodes.map((n) => [n.id, n.position]))
  return nodes.map((node) => { const pos = pathPositionMap.get(node.id); if (!pos) return node; return { ...node, position: pos } })
}

export const autoLayoutByMode = (mode: LayoutMode, nodes: FlowEditorNode[], edges: Edge[], focusedNodeId?: string | null, options?: Partial<LayoutOptions>): FlowEditorNode[] => {
  switch (mode) {
    case 'compact': return compactAutoLayout(nodes, edges, options)
    case 'type-layered': return typeLayeredAutoLayout(nodes, edges, options)
    case 'focused-path': return focusedPathAutoLayout(nodes, edges, focusedNodeId ?? null, options)
    case 'standard': default: return layeredAutoLayout(nodes, edges, options)
  }
}

export const useFlowLayout = () => ({ layeredAutoLayout, compactAutoLayout, typeLayeredAutoLayout, focusedPathAutoLayout, autoLayoutByMode })
