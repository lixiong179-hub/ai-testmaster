/**
 * useFlowSort - 流程排序与统计模块
 *
 * 合并自：useFlowSortData.ts / useFlowStats.ts /
 * flowSort/useFlowSortEditor.ts / flowSort/useFlowSortEditorSync.ts
 *
 * 提供流程排序数据序列化、提交、完整度统计、FlowSortEditor 上下文与同步逻辑。
 * 单向依赖 useFlowCore 与 useFlowInteraction，不形成循环。
 */
import { type InjectionKey, inject, provide, ref, computed, watch, onMounted, nextTick, type Ref } from 'vue'
import { useVueFlow, type Node, type Edge } from '@vue-flow/core'
import { ElMessage } from 'element-plus'
import { useFlowSortStore } from '@/store/flowSort'
import { useGenerateStore } from '@/store/useGenerateStore'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { UIScreen, UIElement } from '@/api/uiPrototype'
import type { FlowSortSubmitData } from '@/api/case'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  type FlowEdgeInput,
  type FlowValidationResult,
  type LayoutMode,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  normalizeEdges,
  generateAutoEdges,
  validateFlowData,
  getOrderedNodesForSubmit,
  useFlowHistory,
  FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP,
  inferEdgeType,
  AUTO_CONNECT_DISTANCE,
  autoLayoutByMode,
  LAYOUT_MODE_LABELS,
  useFlowGroupBackground,
  groupPadding,
  useFlowMainOrder,
} from '@/composables/useFlowCore'

// Re-export 常量，保持组件可从 useFlowSort 统一导入
export { FLOW_TYPE_TAG_MAP, FLOW_TYPE_LABEL_MAP, LAYOUT_MODE_LABELS }
import {
  useFlowSearch,
  useFlowPathHighlight,
  useFlowEdgeOps,
  useFlowTypeOps,
  useFlowEdgeTooltip,
} from '@/composables/useFlowInteraction'
import { usePathPlayback } from '@/composables/usePathPlayback'
import { useTestPointLink } from '@/composables/useTestPointLink'

// ============================================================================
// useFlowSortData - 排序数据序列化与提交
// ============================================================================

/** emit('update:sort-data') 的数据类型 */
export type EmitSortDataPayload = { mode: string; nodes: FlowNodeData[]; edges: FlowEdgeData[] }

export interface UseFlowSortDataOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  vueFlowEdges: Ref<FlowGraphEdge[]>
  emit: (event: 'update:sort-data', data: EmitSortDataPayload) => void
  flowSortStore: ReturnType<typeof useFlowSortStore>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  moduleInfo: Ref<{ name: string; description: string } | undefined>
}

export interface UseFlowSortDataReturn {
  serializeEdge: (edge: FlowGraphEdge) => FlowEdgeData | null
  emitSortData: () => void
  getFlowSortSubmitData: () => { flow_sort_data: FlowSortSubmitData }
  getFlowValidationIssues: () => FlowValidationResult
}

/** 流程排序数据序列化与提交 composable */
export function useFlowSortData(options: UseFlowSortDataOptions): UseFlowSortDataReturn {
  const { vueFlowNodes, vueFlowEdges, emit, flowSortStore, getNodeData: getNodeDataFn, moduleInfo } = options

  /** 将 FlowGraphEdge 序列化为 FlowEdgeData */
  function serializeEdge(edge: FlowGraphEdge): FlowEdgeData | null {
    const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
    const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
    const sourceScreenId = sourceNode ? getNodeDataFn(sourceNode).screen_id : undefined
    const targetScreenId = targetNode ? getNodeDataFn(targetNode).screen_id : undefined
    if (!sourceScreenId || !targetScreenId) return null
    return {
      id: edge.id,
      source: String(sourceScreenId),
      target: String(targetScreenId),
      edge_type: ((edge.data?.edge_type as string | undefined) ||
        'normal') as FlowEdgeData['edge_type'],
      condition: (edge.data?.condition as string | undefined) || undefined,
      trigger_action: (edge.data?.trigger_action as string | undefined) || undefined,
      label: typeof edge.label === 'string' && edge.label.trim() ? edge.label : '连线',
      pre_action: (edge.data?.pre_action as string | undefined) || undefined,
      note: (edge.data?.note as string | undefined) || undefined,
    }
  }

  /** 序列化所有节点和边数据，emit 事件并同步到 flowSort store */
  function emitSortData(): void {
    // 在序列化前从边推导主干顺序并同步 main_order，确保 store 中的 main_order 与画布连线一致
    const normalizedNodes = normalizeMainNodeOrders(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[])

    // 将边推导的 main_order 同步回 vueFlowNodes，避免后续代码路径读到旧值
    normalizedNodes.forEach((normalized) => {
      const existing = vueFlowNodes.value.find((n) => n.id === normalized.id)
      if (existing) {
        existing.data = { ...existing.data, main_order: getNodeDataFn(normalized).main_order }
      }
    })
    const flowNodes: FlowNodeData[] = normalizedNodes.map((node) => ({
      id: node.id,
      screen_id: getNodeDataFn(node).screen_id,
      screen_name: getNodeDataFn(node).screen_name,
      summary: getNodeDataFn(node).summary,
      ui_spec_elements: getNodeDataFn(node).ui_spec_elements,
      flow_type: getNodeDataFn(node).flow_type,
      main_order: getNodeDataFn(node).main_order,
      image_url: getNodeDataFn(node).image_url,
      position: node.position,
      flow_meta: getNodeDataFn(node).flow_meta,
    }))
    const flowEdges: FlowEdgeData[] = vueFlowEdges.value
      .map(serializeEdge)
      .filter((e): e is FlowEdgeData => e !== null)
    emit('update:sort-data', { mode: 'graph', nodes: flowNodes, edges: flowEdges })
    flowSortStore.updateNodes(flowNodes)
    flowSortStore.updateEdges(flowEdges)
    flowSortStore.triggerAutoSave()
  }

  /** 获取提交给后端的完整流程数据 */
  function getFlowSortSubmitData(): { flow_sort_data: FlowSortSubmitData } {
    const sortedNodes = getOrderedNodesForSubmit(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[])
    return {
      flow_sort_data: {
        nodes: sortedNodes.map((node, index) => ({
          screen_id: getNodeDataFn(node).screen_id,
          screen_order: index + 1,
          flow_type: getNodeDataFn(node).flow_type,
          main_order: getNodeDataFn(node).main_order,
          screen_name: getNodeDataFn(node).screen_name,
          ui_spec_elements: getNodeDataFn(node).ui_spec_elements || [],
          summary: getNodeDataFn(node).summary || '',
          flow_meta: getNodeDataFn(node).flow_meta || undefined,
          image_url: getNodeDataFn(node).image_url || undefined,
        })),
        edges: vueFlowEdges.value.map(serializeEdge).filter((e): e is FlowEdgeData => e !== null),
        module_info: moduleInfo.value || { name: '', description: '' },
      },
    }
  }

  /** 获取流程校验问题 */
  function getFlowValidationIssues(): FlowValidationResult {
    const flowData = getFlowSortSubmitData().flow_sort_data
    const edges: FlowEdgeInput[] = flowData.edges.map(
      (edge): FlowEdgeInput => ({
        source: edge.source,
        target: edge.target,
        edge_type: edge.edge_type as FlowEdgeInput['edge_type'],
        condition: edge.condition || '',
        label: edge.label,
      })
    )
    return validateFlowData(flowData.nodes, edges)
  }

  return {
    serializeEdge,
    emitSortData,
    getFlowSortSubmitData,
    getFlowValidationIssues,
  }
}

// ============================================================================
// useFlowStats - 流程完整度统计
// ============================================================================

/** 流程完整度统计数据 */
export interface FlowStats {
  /** 节点总数 */
  totalNodes: number
  /** 主干节点数 */
  mainNodes: number
  /** 分支节点数 */
  branchNodes: number
  /** 异常路径节点数 */
  exceptionNodes: number
  /** 弹窗/浮层节点数 */
  bypassNodes: number
  /** 连线总数 */
  totalEdges: number
  /** 正常连线数（主干间） */
  normalEdges: number
  /** 分支连线数 */
  branchEdges: number
  /** 异常连线数 */
  exceptionEdges: number
  /** 弹窗/浮层连线数 */
  bypassEdges: number
  /** 未连线节点数（孤立节点） */
  orphanNodes: number
  /** 缺条件连线数（分支/异常/弹窗连线缺少 condition） */
  missingConditionEdges: number
  /** 完整度评分 0-100 */
  completenessScore: number
}

/** 流程完整度问题项（用于面板高亮展示） */
export interface FlowStatsIssue {
  type: 'error' | 'warning'
  message: string
}

type FlowType = FlowNodeData['flow_type']
type EdgeType = FlowEdgeData['edge_type']

/** 从 VueFlow 编辑器节点/连线计算流程统计数据 */
export function computeFlowStats(nodes: FlowEditorNode[], edges: FlowGraphEdge[]): FlowStats {
  const nodeTypeCounts: Record<FlowType, number> = { main: 0, branch: 0, exception: 0, bypass: 0 }
  const edgeTypeCounts: Record<EdgeType, number> = { normal: 0, branch: 0, exception: 0, bypass: 0 }

  for (const node of nodes) {
    const ft = (node.data?.flow_type as FlowType) || 'main'
    if (ft in nodeTypeCounts) nodeTypeCounts[ft]++
  }

  for (const edge of edges) {
    const et = (edge.data?.edge_type as EdgeType) || 'normal'
    if (et in edgeTypeCounts) edgeTypeCounts[et]++
  }

  // 计算孤立节点：没有任何连线关联的节点
  const connectedNodeIds = new Set<string>()
  for (const edge of edges) {
    if (edge.source) connectedNodeIds.add(edge.source)
    if (edge.target) connectedNodeIds.add(edge.target)
  }
  const orphanCount = nodes.filter((n) => !connectedNodeIds.has(n.id)).length

  // 计算缺条件连线：分支/异常/弹窗连线缺少 condition
  let missingConditionCount = 0
  for (const edge of edges) {
    const et = (edge.data?.edge_type as EdgeType) || 'normal'
    if (et !== 'normal') {
      const cond = (edge.data?.condition as string | undefined) || ''
      if (!cond.trim()) missingConditionCount++
    }
  }

  const score = calcCompletenessScore(
    nodeTypeCounts,
    edgeTypeCounts,
    orphanCount,
    missingConditionCount
  )

  return {
    totalNodes: nodes.length,
    mainNodes: nodeTypeCounts.main,
    branchNodes: nodeTypeCounts.branch,
    exceptionNodes: nodeTypeCounts.exception,
    bypassNodes: nodeTypeCounts.bypass,
    totalEdges: edges.length,
    normalEdges: edgeTypeCounts.normal,
    branchEdges: edgeTypeCounts.branch,
    exceptionEdges: edgeTypeCounts.exception,
    bypassEdges: edgeTypeCounts.bypass,
    orphanNodes: orphanCount,
    missingConditionEdges: missingConditionCount,
    completenessScore: score,
  }
}

/** 从统计数据推导问题列表 */
export function deriveStatsIssues(stats: FlowStats): FlowStatsIssue[] {
  const issues: FlowStatsIssue[] = []

  if (stats.totalNodes === 0) {
    issues.push({ type: 'error', message: '流程图节点列表为空' })
    return issues
  }
  if (stats.mainNodes === 0) {
    issues.push({ type: 'error', message: '缺少主干节点，至少需要一个主干节点' })
  }
  if (stats.mainNodes > 1 && stats.normalEdges === 0) {
    issues.push({
      type: 'warning',
      message: '多个主干节点但没有正常连线，主干流程可能不完整',
    })
  }
  if (stats.orphanNodes > 0) {
    issues.push({
      type: 'warning',
      message: `${stats.orphanNodes} 个节点未连线（孤立节点）`,
    })
  }
  if (stats.missingConditionEdges > 0) {
    issues.push({
      type: 'warning',
      message: `${stats.missingConditionEdges} 条分支/异常/弹窗连线缺少触发条件`,
    })
  }

  return issues
}

/** 完整度评分算法 */
function calcCompletenessScore(
  nodeTypeCounts: Record<FlowType, number>,
  edgeTypeCounts: Record<EdgeType, number>,
  orphanCount: number,
  missingConditionCount: number
): number {
  if (
    nodeTypeCounts.main +
      nodeTypeCounts.branch +
      nodeTypeCounts.exception +
      nodeTypeCounts.bypass ===
    0
  ) {
    return 0
  }

  let score = 100

  // 无主干节点：严重扣分
  if (nodeTypeCounts.main === 0) score -= 35

  // 多个主干但无正常连线
  if (nodeTypeCounts.main > 1 && edgeTypeCounts.normal === 0) score -= 15

  // 孤立节点扣分（每节点扣5分，上限20分）
  score -= Math.min(orphanCount * 5, 20)

  // 缺条件连线扣分（每条扣3分，上限15分）
  score -= Math.min(missingConditionCount * 3, 15)

  // 有节点但无连线扣分
  const totalNodes =
    nodeTypeCounts.main + nodeTypeCounts.branch + nodeTypeCounts.exception + nodeTypeCounts.bypass
  if (
    totalNodes > 1 &&
    edgeTypeCounts.normal +
      edgeTypeCounts.branch +
      edgeTypeCounts.exception +
      edgeTypeCounts.bypass ===
      0
  ) {
    score -= 15
  }

  return Math.max(0, Math.min(100, score))
}

// ============================================================================
// FlowSortEditor 上下文（合并自 flowSort/useFlowSortEditor.ts）
// ============================================================================

export interface FlowSortEditorProps {
  screens: UIScreen[]
  screenImageUrls?: Record<number, string>
  moduleInfo?: { name: string; description: string }
  highlightedScreenIds?: number[]
}

export type FlowSortEditorEmit = {
  (
    e: 'update:sort-data',
    data: { mode: string; nodes: FlowNodeData[]; edges: FlowEdgeData[] }
  ): void
  (
    e: 'preview-screen',
    screen: { screen_id: number; screen_name: string; image_url?: string }
  ): void
}

export type FlowSortEditorContext = ReturnType<typeof createFlowSortEditorContext>
export const FLOW_SORT_EDITOR_KEY: InjectionKey<FlowSortEditorContext> = Symbol('flowSortEditor')

function createFlowSortEditorContext(props: FlowSortEditorProps, emit: FlowSortEditorEmit) {
  const flowSortStore = useFlowSortStore()
  const { fitView, viewport, setCenter } = useVueFlow()

  const displayMode = ref<'overview' | 'edit'>('overview')
  const vueFlowNodes = ref<FlowEditorNode[]>([])
  const vueFlowEdges = ref<FlowGraphEdge[]>([])
  const currentZoom = ref(1)
  const showShortcutsTip = ref(true)
  const editorRef = ref<HTMLElement | null>(null)
  const collapsedParentNodeIds = ref<string[]>([])
  const draggingNodeId = ref<string | null>(null)
  const isRestoredFromBackend = ref(false)
  const isProgrammaticEdgeChange = ref(false)
  const layoutMode = ref<LayoutMode>('standard')
  const showPromptPreview = ref(false)
  const showEdgeSuggestion = ref(false)
  const showCompletenessPanel = ref(false)
  const showDetailPanel = ref(false)
  const detailPanelNodeId = ref<string | null>(null)
  const showMainStepList = ref(false)
  const flowFilter = ref<'all' | 'main' | 'branch' | 'exception' | 'bypass'>('all')

  const { emitSortData, getFlowSortSubmitData, getFlowValidationIssues } = useFlowSortData({
    vueFlowNodes,
    vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
    emit: (event: 'update:sort-data', data: EmitSortDataPayload) => emit(event, data),
    flowSortStore,
    getNodeData,
    moduleInfo: computed(() => props.moduleInfo),
  })

  const isOverviewMode = computed(() => displayMode.value === 'overview')
  const { historyStack, canUndo, saveToHistory, undo } = useFlowHistory()
  const saveSnapshot = () => saveToHistory(vueFlowNodes.value, vueFlowEdges.value)

  const {
    searchKeyword,
    searchResults,
    searchMatchIds,
    showSearchDropdown,
    debouncedSearch,
    clearSearch,
    locateNode,
    locateFirstMatch,
    handleSearchBlur,
  } = useFlowSearch({
    vueFlowNodes,
    getNodeData,
    fitView: (o?: Record<string, unknown>) => {
      void fitView(o)
    },
  })

  const {
    selectedNodes,
    focusedNodeId,
    upstreamNodeIds,
    downstreamNodeIds,
    allPathNodeIds,
    currentEdgeStyles,
    applyAllEdgeStyles,
    getEdgeStyle,
    defaultEdgeOptions,
    handleNodeClick: _handleNodeClick,
    handlePaneClick: _handlePaneClick,
  } = useFlowPathHighlight({
    vueFlowNodes,
    vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
    getNodeData,
    isOverviewMode,
    collapsedParentNodeIds,
  })

  const handleNodeClick = (event: { node: Node }) => {
    _handleNodeClick(event)
    detailPanelNodeId.value = event.node.id
    showDetailPanel.value = true
  }

  const handlePaneClick = () => {
    _handlePaneClick()
    showDetailPanel.value = false
    detailPanelNodeId.value = null
  }

  const {
    edgeTooltipVisible,
    edgeTooltipData,
    edgeTooltipPosition,
    onEdgeMouseEnter,
    onEdgeMouseMove,
    onEdgeMouseLeave,
    onEdgeTooltipEnter,
    onEdgeTooltipLeave,
  } = useFlowEdgeTooltip({})

  const { showGroupBackground, nodeGroups, svgViewBox, branchChildrenMap } = useFlowGroupBackground(
    {
      vueFlowNodes,
      vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
      getNodeData,
    }
  )

  const {
    conditionDialogVisible,
    currentEdgeForm,
    onConnect,
    handleEditEdge: _handleEditEdge,
    handleDeleteEdge: _handleDeleteEdge,
    onEdgeConditionConfirm,
    onEdgesChange,
    handleEdgeSuggestionsConfirmed,
  } = useFlowEdgeOps({
    vueFlowNodes,
    vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
    emitSortData,
    saveSnapshot,
    historyStack,
    applyAllEdgeStyles,
    currentEdgeStyles,
    isOverviewMode,
    normalizeEdges,
    isProgrammaticEdgeChange,
  })

  const handleEditEdge = (edge: FlowGraphEdge) => {
    _handleEditEdge(edge, () => {
      edgeTooltipVisible.value = false
      edgeTooltipData.value = null
    })
  }
  const handleDeleteEdge = (edge: FlowGraphEdge) => {
    _handleDeleteEdge(edge, () => {
      edgeTooltipVisible.value = false
      edgeTooltipData.value = null
    })
  }

  const {
    pendingFlowTypeChange,
    pendingFlowMeta,
    flowTypeConfigVisible,
    handleFlowTypeChange,
    handleFlowTypeConfigConfirm,
    handleQuickCreateBranch,
    handleBatchFlowTypeChange,
  } = useFlowTypeOps({
    vueFlowNodes,
    vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
    selectedNodes,
    emitSortData,
    saveSnapshot,
    applyAllEdgeStyles,
    currentEdgeStyles,
    isOverviewMode,
    getNodeData,
    getMainNodesInOrder,
    normalizeMainNodeOrders,
    normalizeEdges,
    autoLayoutByMode: autoLayoutByMode as (
      mode: string,
      nodes: FlowEditorNode[],
      edges: FlowGraphEdge[],
      focusedNodeId?: string | null
    ) => FlowEditorNode[],
    layoutMode: layoutMode as Ref<string>,
    focusedNodeId,
    getEdgeStyle,
    isProgrammaticEdgeChange,
    fitView: async (opts: { duration: number; padding: number }) => {
      void (await fitView(opts))
    },
  })

  const {
    handleDeleteSelected,
    canMoveMainBackward,
    canMoveMainForward,
    moveSelectedMainNode,
    getSelectedMainNodeId,
    getSelectedMainOrder,
  } = useFlowMainOrder({
    vueFlowNodes,
    vueFlowEdges: vueFlowEdges as Ref<FlowGraphEdge[]>,
    selectedNodes,
    focusedNodeId,
    collapsedParentNodeIds,
    emitSortData,
    saveSnapshot,
    getNodeData,
    getMainNodesInOrder,
    normalizeMainNodeOrders,
    applyAllEdgeStyles,
    isProgrammaticEdgeChange,
  })

  const promptPreviewFlowData = computed(
    () => getFlowSortSubmitData().flow_sort_data as unknown as Record<string, unknown>
  )

  const {
    isPlaying,
    playPath,
    currentPlayIndex,
    currentPlayNodeId,
    showBranchChoice,
    hasPrevStep,
    hasNextStep,
    startPlayback,
    stopPlayback,
    nextStep,
    prevStep,
    followBranch,
    getStepInfo,
  } = usePathPlayback()

  const genStore = useGenerateStore()
  const { getRelatedScreenIds } = useTestPointLink()
  const highlightedScreenIds = computed(() => {
    if (props.highlightedScreenIds) return new Set(props.highlightedScreenIds)
    try {
      return getRelatedScreenIds(
        genStore.formData.test_point_ids,
        genStore.testPoints,
        vueFlowNodes.value
      )
    } catch (error) {
      console.warn('Failed to get related screen IDs from test points:', error)
      return new Set<number>()
    }
  })

  const hydrateNodesWithImages = (nodes: FlowEditorNode[]): FlowEditorNode[] =>
    nodes.map((node: FlowEditorNode) => ({
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
      edges: normalizeEdges(snapshot.edges as unknown as Edge[]) as unknown as FlowGraphEdge[],
    }))
  }
  const minimapNodeColor = (node: Node) => {
    const c: Record<string, string> = {
      main: '#409eff',
      branch: '#67c23a',
      exception: '#f56c6c',
      bypass: '#e6a23c',
    }
    return c[node.data?.flow_type as string] || '#409eff'
  }
  const minimapNodeStroke = () => '#fff'
  const getChildBranchCount = (nodeId: string): number =>
    branchChildrenMap.value.get(nodeId)?.length ?? 0
  const canQuickCreateBranch = computed(() => {
    if (selectedNodes.value.length !== 1) return false
    const n = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return n !== undefined && getNodeData(n).flow_type === 'main'
  })

  const detailPanelNodeData = computed(() => {
    if (!detailPanelNodeId.value) return null
    const node = vueFlowNodes.value.find((n) => n.id === detailPanelNodeId.value)
    if (!node) return null
    const d = getNodeData(node)
    return {
      id: node.id,
      screen_id: d.screen_id,
      screen_name: d.screen_name,
      summary: d.summary,
      flow_type: d.flow_type,
      main_order: d.main_order,
      image_url: d.image_url,
      element_count: d.element_count,
    }
  })

  function applyCollapsedHidden() {
    const hiddenNodeIds = new Set<string>()
    collapsedParentNodeIds.value.forEach((pid) => {
      ;(branchChildrenMap.value.get(pid) ?? []).forEach((c) => hiddenNodeIds.add(c.node.id))
    })
    const hasChange =
      vueFlowNodes.value.some((n) => n.hidden !== hiddenNodeIds.has(n.id)) ||
      vueFlowEdges.value.some(
        (e: FlowGraphEdge) => e.hidden !== (hiddenNodeIds.has(e.source) || hiddenNodeIds.has(e.target))
      )
    if (!hasChange) return
    vueFlowNodes.value = vueFlowNodes.value.map((node) => ({
      ...node,
      hidden: hiddenNodeIds.has(node.id),
    }))
    vueFlowEdges.value = vueFlowEdges.value.map((edge: FlowGraphEdge) => ({
      ...edge,
      hidden: hiddenNodeIds.has(edge.source) || hiddenNodeIds.has(edge.target),
    }))
  }

  const mainNodeOptions = computed(() => {
    const mainNodes = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[])
    const nonMainNodes = vueFlowNodes.value.filter((n) => getNodeData(n).flow_type !== 'main')
    const mainOpts = mainNodes.map((node) => ({
      id: node.id,
      screen_id: getNodeData(node).screen_id,
      screen_name: getNodeData(node).screen_name,
      main_order: getNodeData(node).main_order,
      flow_type: getNodeData(node).flow_type,
      depth: 0,
    }))
    const nonMainOpts = nonMainNodes.map((node) => {
      const d = getNodeData(node)
      const parentEdge = vueFlowEdges.value.find(
        (e: FlowGraphEdge) =>
          e.target === node.id && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type as string)
      )
      let depth = 1
      if (parentEdge) {
        const p = mainOpts.find((o) => o.id === parentEdge.source)
        if (p) depth = p.depth + 1
      }
      return {
        id: node.id,
        screen_id: d.screen_id,
        screen_name: d.screen_name,
        flow_type: d.flow_type,
        depth,
      }
    })
    return [...mainOpts, ...nonMainOpts]
  })

  const handleFitView = () => {
    void fitView({ duration: 220, padding: 0.15 })
  }
  const handleLayoutModeChange = (mode: string | number | boolean) => {
    layoutMode.value = mode as LayoutMode
    handleAutoLayout()
  }
  const handleAutoLayout = () => {
    saveSnapshot()
    vueFlowNodes.value = autoLayoutByMode(
      layoutMode.value,
      vueFlowNodes.value,
      vueFlowEdges.value as unknown as Edge[],
      focusedNodeId.value
    )
    emitSortData()
    ElMessage.success(`${LAYOUT_MODE_LABELS[layoutMode.value]}完成`)
  }
  const handleUndo = () => {
    const prev = undo()
    if (!prev) return
    vueFlowNodes.value = prev.nodes
    vueFlowEdges.value = applyAllEdgeStyles(prev.edges)
    emitSortData()
    ElMessage.success('已撤销')
  }
  const handleSelectionChange = (selected: { nodes: Node[] }) => {
    selectedNodes.value = selected.nodes.map((n) => n.id)
  }
  const handleToggleCollapse = (nodeId: string) => {
    const idx = collapsedParentNodeIds.value.indexOf(nodeId)
    if (idx >= 0) collapsedParentNodeIds.value.splice(idx, 1)
    else collapsedParentNodeIds.value.push(nodeId)
  }
  const handlePreviewPrompt = () => {
    showPromptPreview.value = true
  }
  const handleNodePreview = (data: EditorNodeData) => {
    if (data?.screen_id)
      emit('preview-screen', {
        screen_id: data.screen_id,
        screen_name: data.screen_name,
        image_url: data.image_url,
      })
  }

  const handleDetailFlowTypeChange = (type: string) => {
    if (detailPanelNodeId.value) {
      handleFlowTypeChange(detailPanelNodeId.value, type)
    }
  }

  const handleDetailLocateNode = (nodeId: string) => {
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (node) {
      focusedNodeId.value = nodeId
      selectedNodes.value = [nodeId]
      detailPanelNodeId.value = nodeId
      setCenter(node.position.x, node.position.y, { zoom: currentZoom.value, duration: 300 })
    }
  }

  const handleDetailPreview = () => {
    if (detailPanelNodeData.value) {
      handleNodePreview(detailPanelNodeData.value)
    }
  }

  const handleMainStepReorder = (orderedIds: string[]) => {
    saveSnapshot()
    const orderMap = new Map<string, number>()
    orderedIds.forEach((id, index) => orderMap.set(id, index + 1))
    vueFlowNodes.value = vueFlowNodes.value.map((node) => {
      const newOrder = orderMap.get(node.id)
      if (newOrder !== undefined) {
        return {
          ...node,
          data: { ...getNodeData(node), main_order: newOrder },
        }
      }
      return node
    })
    emitSortData()
  }

  const handleMainStepLocateNode = (nodeId: string) => {
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (node) {
      focusedNodeId.value = nodeId
      selectedNodes.value = [nodeId]
      detailPanelNodeId.value = nodeId
      showDetailPanel.value = true
      setCenter(node.position.x, node.position.y, { zoom: currentZoom.value, duration: 300 })
    }
  }

  const applyFlowFilter = () => {
    const filter = flowFilter.value
    if (filter === 'all') {
      vueFlowNodes.value = vueFlowNodes.value.map((node) => ({ ...node, hidden: false }))
      vueFlowEdges.value = vueFlowEdges.value.map((edge: FlowGraphEdge) => ({ ...edge, hidden: false }))
      applyCollapsedHidden()
      return
    }
    const visibleNodeIds = new Set<string>()
    vueFlowNodes.value.forEach((node) => {
      const d = getNodeData(node)
      const isVisible =
        filter === 'main'
          ? d.flow_type === 'main'
          : filter === 'branch'
            ? d.flow_type === 'branch' || d.flow_type === 'main'
            : filter === 'exception'
              ? d.flow_type === 'exception' || d.flow_type === 'main'
              : filter === 'bypass'
                ? d.flow_type === 'bypass' || d.flow_type === 'main'
                : true
      if (isVisible) visibleNodeIds.add(node.id)
    })
    vueFlowNodes.value = vueFlowNodes.value.map((node) => ({
      ...node,
      hidden: !visibleNodeIds.has(node.id),
    }))
    vueFlowEdges.value = vueFlowEdges.value.map((edge: FlowGraphEdge) => ({
      ...edge,
      hidden: !visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target),
    }))
  }

  const onNodeDragStart = (event: { node?: Node }) => {
    draggingNodeId.value = event.node?.id || null
    if (event.node?.id && !selectedNodes.value.includes(event.node.id))
      selectedNodes.value = [event.node.id]
  }
  const onNodeDragStop = () => {
    draggingNodeId.value = null
    tryAutoConnectOnDrag()
    saveSnapshot()
    emitSortData()
  }

  const tryAutoConnectOnDrag = () => {
    if (flowSortStore.quickMode === true) return
    const draggedId = selectedNodes.value.length === 1 ? selectedNodes.value[0] : null
    if (!draggedId) return
    const draggedNode = vueFlowNodes.value.find((n) => n.id === draggedId)
    if (!draggedNode) return
    const existingEdges = new Set(
      vueFlowEdges.value.filter((e: FlowGraphEdge) => !e.hidden).map((e: FlowGraphEdge) => `${e.source}->${e.target}`)
    )
    const newEdges: FlowGraphEdge[] = []
    vueFlowNodes.value.forEach((other) => {
      if (other.id === draggedId || other.hidden) return
      const distance = Math.sqrt(
        (draggedNode.position.x - other.position.x) ** 2 +
          (draggedNode.position.y - other.position.y) ** 2
      )
      if (distance >= AUTO_CONNECT_DISTANCE) return
      const source =
        other.position.x < draggedNode.position.x ||
        (other.position.x === draggedNode.position.x && other.position.y < draggedNode.position.y)
          ? other
          : draggedNode
      const target = source === other ? draggedNode : other
      const key = `${source.id}->${target.id}`
      const reverseKey = `${target.id}->${source.id}`
      if (existingEdges.has(key) || existingEdges.has(reverseKey)) return
      const { edgeType, sourceHandle, targetHandle } = inferEdgeType(
        getNodeData(source).flow_type,
        getNodeData(target).flow_type
      )
      newEdges.push({
        id: `edge_${source.id}_${target.id}_${Date.now()}`,
        source: source.id,
        target: target.id,
        sourceHandle,
        targetHandle,
        type: 'default',
        data: { edge_type: edgeType },
      })
    })
    if (newEdges.length > 0) {
      vueFlowEdges.value = applyAllEdgeStyles([...vueFlowEdges.value, ...newEdges])
      ElMessage.success(`已自动连接 ${newEdges.length} 条邻近连线`)
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
    const mod = e.ctrlKey || e.metaKey
    if (flowSortStore.quickMode === true) {
      if (mod && e.key === 's') {
        e.preventDefault()
        flowSortStore.manualSave()
      }
      return
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (selectedNodes.value.length > 0) {
        e.preventDefault()
        handleDeleteSelected()
      }
    }
    if (mod && e.key === 'z') {
      e.preventDefault()
      handleUndo()
    }
    if (mod && e.key === 'l') {
      e.preventDefault()
      handleAutoLayout()
    }
    if (mod && e.key === 'p') {
      e.preventDefault()
      handlePreviewPrompt()
    }
    if (e.key === 'Escape') {
      selectedNodes.value = []
    }
    if (mod && e.key === 's') {
      e.preventDefault()
      flowSortStore.manualSave()
    }
    if (mod && e.key === '0') {
      e.preventDefault()
      handleFitView()
    }
    if (e.code === 'Space' && selectedNodes.value.length === 1) {
      e.preventDefault()
      const n = vueFlowNodes.value.find((item) => item.id === selectedNodes.value[0])
      if (n) handleNodePreview(getNodeData(n))
    }
  }

  return {
    props,
    displayMode,
    vueFlowNodes,
    vueFlowEdges,
    currentZoom,
    showShortcutsTip,
    editorRef,
    collapsedParentNodeIds,
    draggingNodeId,
    isRestoredFromBackend,
    layoutMode,
    showPromptPreview,
    showEdgeSuggestion,
    showCompletenessPanel,
    showDetailPanel,
    detailPanelNodeId,
    detailPanelNodeData,
    showMainStepList,
    flowFilter,
    isOverviewMode,
    canUndo,
    saveSnapshot,
    searchKeyword,
    searchResults,
    searchMatchIds,
    showSearchDropdown,
    debouncedSearch,
    clearSearch,
    locateNode,
    locateFirstMatch,
    handleSearchBlur,
    selectedNodes,
    focusedNodeId,
    upstreamNodeIds,
    downstreamNodeIds,
    allPathNodeIds,
    defaultEdgeOptions,
    handleNodeClick,
    handlePaneClick,
    edgeTooltipVisible,
    edgeTooltipData,
    edgeTooltipPosition,
    onEdgeMouseEnter,
    onEdgeMouseMove,
    onEdgeMouseLeave,
    onEdgeTooltipEnter,
    onEdgeTooltipLeave,
    showGroupBackground,
    nodeGroups,
    svgViewBox,
    branchChildrenMap,
    conditionDialogVisible,
    currentEdgeForm,
    onConnect,
    handleEditEdge,
    handleDeleteEdge,
    onEdgeConditionConfirm,
    onEdgesChange,
    handleEdgeSuggestionsConfirmed,
    pendingFlowTypeChange,
    pendingFlowMeta,
    flowTypeConfigVisible,
    handleFlowTypeChange,
    handleFlowTypeConfigConfirm,
    handleQuickCreateBranch,
    handleBatchFlowTypeChange,
    handleDeleteSelected,
    canMoveMainBackward,
    canMoveMainForward,
    moveSelectedMainNode,
    getSelectedMainNodeId,
    getSelectedMainOrder,
    promptPreviewFlowData,
    isPlaying,
    playPath,
    currentPlayIndex,
    currentPlayNodeId,
    showBranchChoice,
    hasPrevStep,
    hasNextStep,
    startPlayback,
    stopPlayback,
    nextStep,
    prevStep,
    followBranch,
    getStepInfo,
    highlightedScreenIds,
    minimapNodeColor,
    minimapNodeStroke,
    getChildBranchCount,
    canQuickCreateBranch,
    applyCollapsedHidden,
    mainNodeOptions,
    handleFitView,
    handleLayoutModeChange,
    handleAutoLayout,
    handleUndo,
    handleSelectionChange,
    handleToggleCollapse,
    handlePreviewPrompt,
    handleNodePreview,
    handleDetailFlowTypeChange,
    handleDetailLocateNode,
    handleDetailPreview,
    handleMainStepReorder,
    handleMainStepLocateNode,
    applyFlowFilter,
    onNodeDragStart,
    onNodeDragStop,
    handleKeyDown,
    getFlowSortSubmitData,
    getFlowValidationIssues,
    emitSortData,
    applyAllEdgeStyles,
    flowSortStore,
    fitView,
    viewport,
    setCenter,
    hydrateNodesWithImages,
    syncHistoryImages,
    isProgrammaticEdgeChange,
    FLOW_TYPE_TAG_MAP,
    FLOW_TYPE_LABEL_MAP,
    LAYOUT_MODE_LABELS,
    groupPadding,
    inferEdgeType,
    getNodeData,
  }
}

export function provideFlowSortEditor(props: FlowSortEditorProps, emit: FlowSortEditorEmit) {
  const ctx = createFlowSortEditorContext(props, emit)
  provide(FLOW_SORT_EDITOR_KEY, ctx)
  return ctx
}

export function useFlowSortEditor() {
  const ctx = inject(FLOW_SORT_EDITOR_KEY)
  if (!ctx) throw new Error('FlowSortEditor context not provided')
  return ctx
}

// ============================================================================
// useFlowSortEditorSync - 同步逻辑（合并自 flowSort/useFlowSortEditorSync.ts）
// ============================================================================

const NODE_SPACING_X = 280
const SHORTCUTS_TIP_DURATION = 5000
const GRID_COLS = 4
const GRID_GAP_X = 280
const GRID_GAP_Y = 260

export function useFlowSortEditorSync(ctx: FlowSortEditorContext) {
  const {
    props,
    displayMode,
    vueFlowNodes,
    vueFlowEdges,
    showShortcutsTip,
    editorRef,
    collapsedParentNodeIds,
    isRestoredFromBackend,
    searchKeyword,
    searchMatchIds,
    emitSortData,
    applyAllEdgeStyles,
    saveSnapshot,
    fitView,
    hydrateNodesWithImages,
    syncHistoryImages,
    focusedNodeId,
    selectedNodes,
    currentPlayNodeId,
    isPlaying,
    currentZoom,
    flowSortStore,
  } = ctx

  function isScreensEqual(a: UIScreen[], b: UIScreen[]): boolean {
    if (a.length !== b.length) return false
    return a.every((screen: UIScreen, index: number) => {
      const other = b[index]
      return (
        screen.id === other.id &&
        screen.screen_name === other.screen_name &&
        screen.summary === other.summary &&
        screen.element_count === other.element_count
      )
    })
  }

  let lastScreens: UIScreen[] = []

  watch(
    () => props.screens,
    (newScreens) => {
      if (isScreensEqual(newScreens, lastScreens)) return
      lastScreens = newScreens
      isRestoredFromBackend.value = false
      const newNodes = normalizeMainNodeOrders(
        newScreens.map((screen: UIScreen, index: number) => ({
          id: `node_${screen.id}`,
          type: 'custom',
          position:
            flowSortStore.quickMode === true
              ? {
                  x: (index % GRID_COLS) * GRID_GAP_X,
                  y: Math.floor(index / GRID_COLS) * GRID_GAP_Y,
                }
              : { x: index * NODE_SPACING_X, y: 0 },
          data: {
            screen_id: screen.id,
            screen_name: screen.screen_name,
            summary: screen.summary,
            ui_spec_elements: (screen.ui_spec?.elements || []).map((el: UIElement) => ({
              type: el.type,
              label: el.label,
              semantic: el.semantic_hint || el.description,
              position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
              interactive: el.interactive,
              state: el.state,
              description: el.description,
            })),
            flow_type: 'main' as const,
            main_order: index + 1,
            image_url: !screen.id ? '' : props.screenImageUrls?.[screen.id] || '',
            element_count: screen.element_count,
          },
        }))
      )
      vueFlowNodes.value = newNodes
      if (flowSortStore.quickMode === true) {
        vueFlowEdges.value = []
      } else {
        const autoEdges = generateAutoEdges(newNodes)
        vueFlowEdges.value = applyAllEdgeStyles(autoEdges as unknown as FlowGraphEdge[])
      }
      saveSnapshot()
      emitSortData()
    },
    { immediate: true }
  )

  watch(displayMode, () => {
    searchKeyword.value = ''
    searchMatchIds.value = []
    vueFlowEdges.value = applyAllEdgeStyles(vueFlowEdges.value)
    nextTick(() => {
      void fitView({ duration: 300, padding: 0.15 })
    })
    emitSortData()
  })

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
    ctx.viewport,
    (nextViewport) => {
      currentZoom.value = nextViewport?.zoom ?? 1
    },
    { deep: true, immediate: true }
  )

  watch(currentPlayNodeId, (nodeId) => {
    if (nodeId) {
      focusedNodeId.value = nodeId
      const node = vueFlowNodes.value.find((n) => n.id === nodeId)
      if (node)
        ctx.setCenter(node.position.x, node.position.y, { zoom: currentZoom.value, duration: 300 })
    }
  })

  watch(isPlaying, (playing) => {
    if (!playing) {
      focusedNodeId.value = null
      selectedNodes.value = []
    }
  })

  watch(collapsedParentNodeIds, () => ctx.applyCollapsedHidden(), { deep: true })

  function syncStoreToEditor() {
    const currentScreenIds = new Set(props.screens.map((screen: UIScreen) => Number(screen.id)))
    const storeNodes = flowSortStore.nodes.filter((node: FlowNodeData) =>
      currentScreenIds.has(Number(node.screen_id))
    )
    if (storeNodes.length === 0) return
    const screenById = new Map(props.screens.map((s: UIScreen) => [s.id, s]))
    vueFlowNodes.value = storeNodes.map((node: FlowNodeData) => ({
      id: node.id,
      type: 'custom',
      position: node.position || { x: 0, y: 0 },
      data: {
        screen_id: node.screen_id,
        screen_name: node.screen_name,
        summary: node.summary,
        ui_spec_elements: node.ui_spec_elements || [],
        flow_type: node.flow_type,
        main_order: node.main_order,
        image_url: props.screenImageUrls?.[node.screen_id] || node.image_url || '',
        element_count: screenById.get(node.screen_id)?.element_count,
        flow_meta: node.flow_meta,
      },
    }))
    const { inferEdgeType, getNodeData } = ctx
    const validNodeIds = new Set(storeNodes.map((node: FlowNodeData) => node.id))
    const validScreenIds = new Set(storeNodes.map((node: FlowNodeData) => String(node.screen_id)))
    const rawEdges = flowSortStore.edges
      .filter((edge: FlowEdgeData) => {
        const source = String(edge.source)
        const target = String(edge.target)
        return (
          (validNodeIds.has(source) || validScreenIds.has(source)) &&
          (validNodeIds.has(target) || validScreenIds.has(target))
        )
      })
      .map((edge: FlowEdgeData) => {
        const sourceNode = vueFlowNodes.value.find(
          (n: FlowEditorNode) => getNodeData(n).screen_id === Number(edge.source)
        )
        const targetNode = vueFlowNodes.value.find(
          (n: FlowEditorNode) => getNodeData(n).screen_id === Number(edge.target)
        )
        const sourceType = sourceNode ? getNodeData(sourceNode).flow_type : 'main'
        const targetType = targetNode ? getNodeData(targetNode).flow_type : 'main'
        const handles =
          edge.edge_type !== 'normal'
            ? inferEdgeType(sourceType, targetType)
            : { sourceHandle: 'source-right', targetHandle: 'target-left' }
        return {
          id: edge.id,
          source: sourceNode?.id || edge.source,
          target: targetNode?.id || edge.target,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
          type: 'default',
          data: {
            edge_type: edge.edge_type,
            condition: edge.condition,
            trigger_action: edge.trigger_action,
            pre_action: edge.pre_action,
            note: edge.note,
          },
          label: edge.label || '连线',
        }
      })
    vueFlowEdges.value = applyAllEdgeStyles(rawEdges as unknown as FlowGraphEdge[])
    saveSnapshot()
    isRestoredFromBackend.value = true
    emitSortData()
  }

  watch(
    () => flowSortStore.isBackendLoaded,
    (isLoaded, wasLoaded) => {
      if (isLoaded && !wasLoaded && flowSortStore.nodes.length > 0) {
        nextTick(() => syncStoreToEditor())
      }
    }
  )

  onMounted(() => {
    if (editorRef.value) editorRef.value.focus()
    if (
      flowSortStore.isBackendLoaded &&
      flowSortStore.nodes.length > 0 &&
      !isRestoredFromBackend.value
    ) {
      nextTick(() => syncStoreToEditor())
    }
    setTimeout(() => {
      showShortcutsTip.value = false
    }, SHORTCUTS_TIP_DURATION)
  })
}
