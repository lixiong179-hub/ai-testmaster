import { ref, computed, type Ref, type ComputedRef } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  type EdgeStyleConfig,
  computeUpstreamNodeIds,
  computeDownstreamNodeIds,
  computeRelatedEdgeIds,
  createEdgeMarker,
  normalizeEdges,
  EDGE_STYLES,
  OVERVIEW_EDGE_STYLES,
} from '@/composables/useFlowEditor'

/** 节点选择与路径高亮 composable 的配置项 */
export interface UseFlowPathHighlightOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  isOverviewMode: Ref<boolean>
  collapsedParentNodeIds: Ref<string[]>
}

/** 节点选择与路径高亮 composable 的返回值 */
export interface UseFlowPathHighlightReturn {
  selectedNodes: Ref<string[]>
  focusedNodeId: Ref<string | null>
  upstreamNodeIds: ComputedRef<Set<string>>
  downstreamNodeIds: ComputedRef<Set<string>>
  allPathNodeIds: ComputedRef<Set<string>>
  pathHighlightedEdgeIds: ComputedRef<Set<string>>
  currentEdgeStyles: Ref<Record<string, EdgeStyleConfig>>
  applyAllEdgeStyles: (edges: FlowGraphEdge[]) => FlowGraphEdge[]
  getEdgeStyle: (type: string) => EdgeStyleConfig
  defaultEdgeOptions: ComputedRef<{
    markerEnd: ReturnType<typeof createEdgeMarker>
    style: EdgeStyleConfig
  }>
  handleNodeClick: (event: { node: Node }) => void
  handlePaneClick: () => void
}

/**
 * 从 FlowSortEditor 抽取的节点选择与路径高亮逻辑。
 * 管理：选中节点、焦点节点、上下游路径计算、边样式应用与路径高亮。
 */
export function useFlowPathHighlight(
  options: UseFlowPathHighlightOptions
): UseFlowPathHighlightReturn {
  const { vueFlowEdges, isOverviewMode, collapsedParentNodeIds } = options

  // ---------- 选中的节点 ID 列表 ----------
  const selectedNodes = ref<string[]>([])

  // ---------- 焦点节点 ID（用于路径高亮） ----------
  const focusedNodeId = ref<string | null>(null)

  // ---------- 内部 Set 版本（保持与原始逻辑一致的 O(1) 查找性能） ----------
  const _upstreamNodeIds = computed<Set<string>>(() => {
    if (!focusedNodeId.value) return new Set<string>()
    return computeUpstreamNodeIds(vueFlowEdges.value as Edge[], focusedNodeId.value)
  })

  const _downstreamNodeIds = computed<Set<string>>(() => {
    if (!focusedNodeId.value) return new Set<string>()
    return computeDownstreamNodeIds(vueFlowEdges.value as Edge[], focusedNodeId.value)
  })

  const _allPathNodeIds = computed<Set<string>>(() => {
    if (!focusedNodeId.value) return new Set<string>()
    const all = new Set<string>([focusedNodeId.value])
    _upstreamNodeIds.value.forEach((id) => all.add(id))
    _downstreamNodeIds.value.forEach((id) => all.add(id))
    return all
  })

  const _pathHighlightedEdgeIds = computed<Set<string>>(() => {
    if (!focusedNodeId.value) return new Set<string>()
    return computeRelatedEdgeIds(vueFlowEdges.value as Edge[], _allPathNodeIds.value)
  })

  // ---------- 公开接口：直接返回 Set 版本（模板使用 .has() 方法） ----------
  const upstreamNodeIds = _upstreamNodeIds
  const downstreamNodeIds = _downstreamNodeIds
  const allPathNodeIds = _allPathNodeIds
  const pathHighlightedEdgeIds = _pathHighlightedEdgeIds

  // ---------- 边样式配置 ----------
  const currentEdgeStyles = computed<Record<string, EdgeStyleConfig>>(() =>
    isOverviewMode.value ? OVERVIEW_EDGE_STYLES : EDGE_STYLES
  )

  /** 获取指定类型的边样式，未知类型回退到 normal */
  function getEdgeStyle(edgeType: string): EdgeStyleConfig {
    return currentEdgeStyles.value[edgeType] || currentEdgeStyles.value.normal
  }

  /** 应用基础边样式（不含路径高亮） */
  function applyEdgeStyles(edges: FlowGraphEdge[]): FlowGraphEdge[] {
    return normalizeEdges(
      edges as Edge[],
      currentEdgeStyles.value,
      isOverviewMode.value
    ) as FlowGraphEdge[]
  }

  /** 应用所有边样式（含路径高亮） */
  function applyAllEdgeStyles(edges: FlowGraphEdge[]): FlowGraphEdge[] {
    const styled = applyEdgeStyles(edges)
    if (!focusedNodeId.value) return styled
    return styled.map((edge) => {
      const isHighlighted = _pathHighlightedEdgeIds.value.has(edge.id)
      return {
        ...edge,
        class: isHighlighted ? 'edge-path-highlighted' : 'edge-path-dimmed',
        style: {
          ...(edge.style || {}),
          strokeWidth: isHighlighted ? 3 : 1,
        },
      }
    })
  }

  /** 默认边选项，用于 VueFlow 的 default-edge-options 属性 */
  const defaultEdgeOptions = computed(() => ({
    markerEnd: createEdgeMarker(getEdgeStyle('normal').stroke),
    style: getEdgeStyle('normal'),
  }))

  // ---------- 交互处理 ----------

  /** 节点点击：选中节点 + 切换焦点（路径高亮） */
  function handleNodeClick(event: { node: Node }): void {
    selectedNodes.value = [event.node.id]
    if (focusedNodeId.value === event.node.id) {
      focusedNodeId.value = null
    } else {
      focusedNodeId.value = event.node.id
    }
    collapsedParentNodeIds.value = collapsedParentNodeIds.value.filter(
      (id) => !selectedNodes.value.includes(id)
    )
  }

  /** 画布点击：清除选中和焦点 */
  function handlePaneClick(): void {
    selectedNodes.value = []
    focusedNodeId.value = null
  }

  return {
    selectedNodes,
    focusedNodeId,
    upstreamNodeIds,
    downstreamNodeIds,
    allPathNodeIds,
    pathHighlightedEdgeIds,
    currentEdgeStyles,
    applyAllEdgeStyles,
    getEdgeStyle,
    defaultEdgeOptions,
    handleNodeClick,
    handlePaneClick,
  }
}
