import { type InjectionKey, inject, provide, ref, computed, type Ref } from 'vue'
import { useVueFlow, type Node } from '@vue-flow/core'
import { ElMessage } from 'element-plus'
import { useFlowSortStore } from '@/store/flowSort'
import { useGenerateStore } from '@/store/useGenerateStore'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { UIScreen } from '@/api/uiPrototype'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  normalizeEdges,
  useFlowHistory,
  FLOW_TYPE_TAG_MAP as _FLOW_TYPE_TAG_MAP,
  FLOW_TYPE_LABEL_MAP as _FLOW_TYPE_LABEL_MAP,
  inferEdgeType,
  AUTO_CONNECT_DISTANCE,
} from '@/composables/useFlowEditor'

export { _FLOW_TYPE_TAG_MAP as FLOW_TYPE_TAG_MAP, _FLOW_TYPE_LABEL_MAP as FLOW_TYPE_LABEL_MAP }
import useFlowSortData, { type EmitSortDataPayload } from '@/composables/useFlowSortData'
import {
  type LayoutMode,
  autoLayoutByMode,
  LAYOUT_MODE_LABELS as _LAYOUT_MODE_LABELS,
} from '@/composables/useFlowLayout'

export { _LAYOUT_MODE_LABELS as LAYOUT_MODE_LABELS }
import { usePathPlayback } from '@/composables/usePathPlayback'
import { useTestPointLink } from '@/composables/useTestPointLink'
import { useFlowSearch } from '@/composables/useFlowSearch'
import { useFlowPathHighlight } from '@/composables/useFlowPathHighlight'
import { useFlowEdgeOps } from '@/composables/useFlowEdgeOps'
import { useFlowTypeOps } from '@/composables/useFlowTypeOps'
import { useFlowMainOrder } from '@/composables/useFlowMainOrder'
import { useFlowEdgeTooltip } from '@/composables/useFlowEdgeTooltip'
import { useFlowGroupBackground, groupPadding } from '@/composables/useFlowGroupBackground'

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
  const vueFlowEdges = ref<any[]>([])
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
  const saveSnapshot = () => saveToHistory(vueFlowNodes.value, vueFlowEdges.value as any)

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

  const handleEditEdge = (edge: any) => {
    _handleEditEdge(edge, () => {
      edgeTooltipVisible.value = false
      edgeTooltipData.value = null
    })
  }
  const handleDeleteEdge = (edge: any) => {
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

  const hydrateNodesWithImages = (nodes: any[]): any[] =>
    nodes.map((node: any) => ({
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
      edges: normalizeEdges(snapshot.edges as any) as any,
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
        (e: any) => e.hidden !== (hiddenNodeIds.has(e.source) || hiddenNodeIds.has(e.target))
      )
    if (!hasChange) return
    vueFlowNodes.value = vueFlowNodes.value.map((node) => ({
      ...node,
      hidden: hiddenNodeIds.has(node.id),
    }))
    vueFlowEdges.value = vueFlowEdges.value.map((edge: any) => ({
      ...edge,
      hidden: hiddenNodeIds.has(edge.source) || hiddenNodeIds.has(edge.target),
    }))
  }

  const mainNodeOptions = computed(() => {
    const mainNodes = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as any)
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
        (e: any) =>
          e.target === node.id && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)
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
      vueFlowEdges.value as any,
      focusedNodeId.value
    )
    emitSortData()
    ElMessage.success(`${_LAYOUT_MODE_LABELS[layoutMode.value]}完成`)
  }
  const handleUndo = () => {
    const prev = undo()
    if (!prev) return
    vueFlowNodes.value = prev.nodes
    vueFlowEdges.value = applyAllEdgeStyles(prev.edges as any)
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
      vueFlowEdges.value = vueFlowEdges.value.map((edge: any) => ({ ...edge, hidden: false }))
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
    vueFlowEdges.value = vueFlowEdges.value.map((edge: any) => ({
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
      vueFlowEdges.value.filter((e: any) => !e.hidden).map((e: any) => `${e.source}->${e.target}`)
    )
    const newEdges: any[] = []
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
    FLOW_TYPE_TAG_MAP: _FLOW_TYPE_TAG_MAP,
    FLOW_TYPE_LABEL_MAP: _FLOW_TYPE_LABEL_MAP,
    LAYOUT_MODE_LABELS: _LAYOUT_MODE_LABELS,
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
