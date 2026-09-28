/**
 * useFlowInteraction - 流程编辑交互模块
 *
 * 合并自：useFlowSearch.ts / useFlowEdgeOps.ts / useFlowTypeOps.ts /
 * useFlowEdgeTooltip.ts / useFlowPathHighlight.ts
 *
 * 提供搜索定位、边操作、类型操作、边 tooltip、路径高亮等交互能力。
 * 单向依赖 useFlowCore，不依赖 useFlowSort。
 */
import { ref, computed, watch, nextTick, onUnmounted, type Ref, type ComputedRef } from 'vue'
import {
  type Connection as FlowConnection,
  type EdgeChange,
  type Edge,
  type Node,
  type EdgeMouseEvent,
} from '@vue-flow/core'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FlowMetaData } from '@/store/flowSort'
import {
  type EditorNodeData,
  type FlowEditorNode,
  type FlowGraphEdge,
  type EdgeStyleConfig,
  getNodeData,
  normalizeEdges,
  computeUpstreamNodeIds,
  computeDownstreamNodeIds,
  computeRelatedEdgeIds,
  createEdgeMarker,
  inferEdgeType,
  EDGE_STYLES,
  OVERVIEW_EDGE_STYLES,
  FLOW_TYPE_LABEL_MAP,
} from '@/composables/useFlowCore'
import { type EdgeSuggestion } from '@/composables/useEdgeSuggestion'

// ============================================================================
// useFlowSearch - 搜索定位
// ============================================================================

/** 搜索结果项 */
export interface FlowSearchResultItem {
  id: string
  screen_name: string
  flow_type: string
}

/** useFlowSearch 入参 */
export interface UseFlowSearchOptions {
  vueFlowNodes: Ref<FlowEditorNode[]>
  getNodeData: (node: FlowEditorNode) => EditorNodeData
  fitView: (options?: Record<string, unknown>) => void
}

/** useFlowSearch 返回值 */
export interface UseFlowSearchReturn {
  searchKeyword: Ref<string>
  searchResults: ComputedRef<FlowSearchResultItem[]>
  searchMatchIds: Ref<string[]>
  showSearchDropdown: Ref<boolean>
  debouncedSearch: () => void
  clearSearch: () => void
  locateNode: (nodeId: string) => void
  locateFirstMatch: () => void
  handleSearchBlur: () => void
}

/**
 * 流程编辑器搜索定位 composable
 * 负责节点搜索、匹配高亮、视图定位等逻辑
 */
export function useFlowSearch(options: UseFlowSearchOptions): UseFlowSearchReturn {
  const { vueFlowNodes, getNodeData: getNodeDataFn, fitView } = options

  // ---------- 状态 ----------
  const searchKeyword = ref('')
  const searchMatchIds = ref<string[]>([])
  const showSearchDropdown = ref(false)
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  // ---------- 计算属性 ----------
  /** 根据关键词过滤节点，匹配 screen_name 或 summary */
  const searchResults = computed<FlowSearchResultItem[]>(() => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) return []
    return vueFlowNodes.value
      .filter((node) => {
        const name = getNodeDataFn(node).screen_name?.toLowerCase() || ''
        const summary = getNodeDataFn(node).summary?.toLowerCase() || ''
        return name.includes(keyword) || summary.includes(keyword)
      })
      .map((node) => ({
        id: node.id,
        screen_name: getNodeDataFn(node).screen_name,
        flow_type: getNodeDataFn(node).flow_type,
      }))
  })

  // ---------- 方法 ----------

  /** 定位到指定节点：高亮该节点并适配视图 */
  const locateNode = (nodeId: string): void => {
    searchMatchIds.value = [nodeId]
    showSearchDropdown.value = false
    void fitView({ nodes: [nodeId], duration: 300, padding: 0.3 })
  }

  /** 定位到第一个搜索结果 */
  const locateFirstMatch = (): void => {
    if (searchResults.value.length > 0) {
      locateNode(searchResults.value[0].id)
    }
  }

  /**
   * 处理搜索定位：更新匹配节点列表并定位到指定节点
   * @param nodeId - 需要定位的节点 ID
   */
  const handleSearchLocate = (nodeId: string): void => {
    const keyword = searchKeyword.value.trim().toLowerCase()
    if (!keyword) {
      searchMatchIds.value = []
      return
    }
    searchMatchIds.value = searchResults.value.map((r) => r.id)
    showSearchDropdown.value = true
    locateNode(nodeId)
  }

  /** 防抖搜索：300ms 后执行搜索定位 */
  const debouncedSearch = (): void => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      const keyword = searchKeyword.value.trim().toLowerCase()
      if (!keyword) {
        searchMatchIds.value = []
        return
      }
      searchMatchIds.value = searchResults.value.map((r) => r.id)
      showSearchDropdown.value = true
      if (searchResults.value.length > 0) {
        handleSearchLocate(searchResults.value[0].id)
      }
    }, 300)
  }

  /** 清除搜索状态 */
  const clearSearch = (): void => {
    searchMatchIds.value = []
    showSearchDropdown.value = false
    if (searchTimer) clearTimeout(searchTimer)
  }

  /** 搜索输入失焦处理：延迟关闭下拉列表 */
  const handleSearchBlur = (): void => {
    setTimeout(() => {
      showSearchDropdown.value = false
    }, 200)
  }

  // ---------- 生命周期 ----------
  onUnmounted(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })

  return {
    searchKeyword,
    searchResults,
    searchMatchIds,
    showSearchDropdown,
    debouncedSearch,
    clearSearch,
    locateNode,
    locateFirstMatch,
    handleSearchBlur,
  }
}

// ============================================================================
// useFlowEdgeOps - 边操作
// ============================================================================

/** 边操作 composable 的外部依赖选项 */
export interface UseFlowEdgeOpsOptions {
  /** VueFlow 节点列表 */
  vueFlowNodes: Ref<FlowEditorNode[]>
  /** VueFlow 边列表 */
  vueFlowEdges: Ref<FlowGraphEdge[]>
  /** 向父组件提交排序数据 */
  emitSortData: () => void
  /** 保存历史快照 */
  saveSnapshot: () => void
  /** 撤销历史栈 */
  historyStack: Ref<Array<{ nodes: FlowEditorNode[]; edges: FlowGraphEdge[] }>>
  /** 对边列表应用完整样式（含路径高亮） */
  applyAllEdgeStyles: (edges: FlowGraphEdge[]) => FlowGraphEdge[]
  /** 当前边样式映射 */
  currentEdgeStyles: Ref<Record<string, EdgeStyleConfig>>
  /** 是否为总览模式 */
  isOverviewMode: Ref<boolean>
  /** 标准化边列表（附加样式/标记） */
  normalizeEdges: (edges: Edge[], styleMap?: Record<string, EdgeStyleConfig>, isOverview?: boolean) => Edge[]
  /** 共享的程序化边变更标志（与 useFlowTypeOps/useFlowMainOrder 共用） */
  isProgrammaticEdgeChange: Ref<boolean>
}

/** 边条件弹窗表单数据 */
interface EdgeConditionForm {
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
  trigger_action: string
  pre_action: string
  note: string
}

/** onEdgeConditionConfirm 回调参数 */
export interface EdgeConditionConfirmData {
  edge_type: string
  condition: string | null
  trigger_action: string
  pre_action: string
  note: string
  label: string
}

/**
 * useFlowEdgeOps - 流程图边操作 composable
 *
 * 抽取自 FlowSortEditor.vue，负责所有边相关的交互逻辑：
 * 新建连线、编辑边、删除边、边条件确认、边变更处理（含撤销快照）、边建议确认。
 */
export function useFlowEdgeOps(options: UseFlowEdgeOpsOptions) {
  const {
    vueFlowNodes,
    vueFlowEdges,
    emitSortData,
    saveSnapshot,
    historyStack,
    applyAllEdgeStyles,
    currentEdgeStyles,
    isOverviewMode,
    normalizeEdges: normalizeEdgesFn,
    isProgrammaticEdgeChange,
  } = options

  // ---------- 状态 ----------

  /** 当前连接信息（新建连线时暂存 source/target 和 handle） */
  const currentConnection = ref<{
    source: string
    target: string
    sourceHandle?: string
    targetHandle?: string
  } | null>(null)

  /** 边条件弹窗可见性 */
  const conditionDialogVisible = ref(false)

  /** 边条件弹窗表单数据 */
  const currentEdgeForm = ref<EdgeConditionForm | null>(null)

  /** 正在编辑的边 ID（null 表示新建模式） */
  const editingEdgeId = ref<string | null>(null)

  /** 边删除前快照，用于 onEdgesChange 中恢复撤销 */
  const preChangeEdgesSnapshot = ref<{
    nodes: FlowEditorNode[]
    edges: FlowGraphEdge[]
  } | null>(null)

  // ---------- watch: 弹窗关闭时清理编辑状态 ----------

  watch(conditionDialogVisible, (val) => {
    if (!val) {
      editingEdgeId.value = null
      currentConnection.value = null
    }
  })

  // ---------- watch: 边列表变更时捕获删除前快照 ----------

  watch(
    vueFlowEdges,
    (newVal, oldVal) => {
      if (isProgrammaticEdgeChange.value) {
        isProgrammaticEdgeChange.value = false
        return
      }
      if (newVal.length < oldVal.length) {
        preChangeEdgesSnapshot.value = {
          nodes: JSON.parse(JSON.stringify(vueFlowNodes.value)),
          edges: JSON.parse(JSON.stringify(oldVal)),
        }
      }
    },
    { flush: 'sync' }
  )

  // ---------- 方法 ----------

  /** 新建连线处理 - 打开条件弹窗 */
  const onConnect = (connection: FlowConnection): void => {
    const {
      source,
      target,
      sourceHandle: rawSourceHandle,
      targetHandle: rawTargetHandle,
    } = connection
    const sourceHandle = rawSourceHandle ?? undefined
    const targetHandle = rawTargetHandle ?? undefined
    let finalSourceHandle = sourceHandle
    let finalTargetHandle = targetHandle

    if (!sourceHandle || !targetHandle) {
      const sourceNode = vueFlowNodes.value.find((n) => n.id === source)
      const targetNode = vueFlowNodes.value.find((n) => n.id === target)
      if (sourceNode && targetNode) {
        const handles = inferEdgeType(
          sourceNode.data?.flow_type as string,
          targetNode.data?.flow_type as string
        )
        finalSourceHandle = handles.sourceHandle
        finalTargetHandle = handles.targetHandle
      } else {
        finalSourceHandle = 'source-right'
        finalTargetHandle = 'target-left'
      }
    }

    currentConnection.value = {
      source,
      target,
      sourceHandle: finalSourceHandle,
      targetHandle: finalTargetHandle,
    }
    currentEdgeForm.value = null
    editingEdgeId.value = null
    conditionDialogVisible.value = true
  }

  /** 编辑边 - 打开条件弹窗并填充已有数据 */
  const handleEditEdge = (edge: FlowGraphEdge, closeTooltip?: () => void): void => {
    if (closeTooltip) closeTooltip()
    editingEdgeId.value = edge.id
    currentConnection.value = null
    currentEdgeForm.value = {
      edge_type: (edge.data?.edge_type as EdgeConditionForm['edge_type']) || 'normal',
      condition: (edge.data?.condition as string) || '',
      trigger_action: (edge.data?.trigger_action as string) || '',
      pre_action: (edge.data?.pre_action as string) || '',
      note: (edge.data?.note as string) || '',
    }
    conditionDialogVisible.value = true
  }

  /** 删除边 */
  const handleDeleteEdge = (edge: FlowGraphEdge, closeTooltip?: () => void): void => {
    if (closeTooltip) closeTooltip()
    saveSnapshot()
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = vueFlowEdges.value.filter((e: FlowGraphEdge) => e.id !== edge.id)
    emitSortData()
    ElMessage.success('已删除连线')
  }

  /** 边条件确认 - 新建或更新边 */
  const onEdgeConditionConfirm = (edgeData: EdgeConditionConfirmData): void => {
    saveSnapshot()

    if (editingEdgeId.value) {
      // 编辑已有边
      vueFlowEdges.value = applyAllEdgeStyles(
        vueFlowEdges.value.map((e: FlowGraphEdge) => {
          if (e.id !== editingEdgeId.value) return e
          return {
            ...e,
            label: edgeData.label,
            data: {
              edge_type: edgeData.edge_type,
              condition: edgeData.condition,
              trigger_action: edgeData.trigger_action,
              pre_action: edgeData.pre_action,
              note: edgeData.note,
            },
          }
        })
      )
      editingEdgeId.value = null
      ElMessage.success('连线属性已更新')
    } else if (currentConnection.value) {
      // 新建连线 - 连接验证
      if (currentConnection.value.source === currentConnection.value.target) {
        ElMessage.warning('不能连接到自身')
        conditionDialogVisible.value = false
        currentConnection.value = null
        return
      }
      const alreadyExists = vueFlowEdges.value.some(
        (e: FlowGraphEdge) =>
          e.source === currentConnection.value!.source &&
          e.target === currentConnection.value!.target
      )
      if (alreadyExists) {
        ElMessage.warning('已存在相同连线')
        conditionDialogVisible.value = false
        currentConnection.value = null
        return
      }

      const newEdge: FlowGraphEdge = {
        id: `edge_${Date.now()}`,
        source: currentConnection.value.source,
        target: currentConnection.value.target,
        sourceHandle: currentConnection.value.sourceHandle,
        targetHandle: currentConnection.value.targetHandle,
        type: 'default',
        animated: true,
        label: edgeData.label,
        data: {
          edge_type: edgeData.edge_type,
          condition: edgeData.condition,
          trigger_action: edgeData.trigger_action,
          pre_action: edgeData.pre_action,
          note: edgeData.note,
        },
      }

      vueFlowEdges.value = normalizeEdgesFn(
        [...vueFlowEdges.value, newEdge] as unknown as Edge[],
        currentEdgeStyles.value,
        isOverviewMode.value
      ) as unknown as FlowGraphEdge[]
    }

    conditionDialogVisible.value = false
    emitSortData()
  }

  /** 边变更处理 - 含撤销快照逻辑 */
  const onEdgesChange = (changes: EdgeChange[]): void => {
    const removedIds = new Set(changes.filter((c) => c.type === 'remove').map((c) => c.id))
    if (removedIds.size > 0) {
      if (preChangeEdgesSnapshot.value) {
        historyStack.value.push(preChangeEdgesSnapshot.value)
        if (historyStack.value.length > 50) historyStack.value.shift()
        preChangeEdgesSnapshot.value = null
      } else {
        saveSnapshot()
      }
      nextTick(() => emitSortData())
    }
    const otherChanges = changes.filter((c) => c.type !== 'remove')
    if (otherChanges.length > 0) {
      nextTick(() => emitSortData())
    }
  }

  /** 边建议确认 - 批量添加建议连线 */
  const handleEdgeSuggestionsConfirmed = (accepted: EdgeSuggestion[]): void => {
    if (accepted.length === 0) return
    saveSnapshot()
    const newEdges: FlowGraphEdge[] = accepted.map((s) => {
      const sourceNode = vueFlowNodes.value.find((n) => n.id === s.sourceNodeId)
      const targetNode = vueFlowNodes.value.find((n) => n.id === s.targetNodeId)
      const sourceType = sourceNode ? getNodeData(sourceNode).flow_type : 'main'
      const targetType = targetNode ? getNodeData(targetNode).flow_type : 'branch'
      const handles = inferEdgeType(sourceType, targetType)
      return {
        id: `edge_${s.sourceNodeId}_${s.targetNodeId}_${Date.now()}`,
        source: s.sourceNodeId,
        target: s.targetNodeId,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'default' as const,
        data: { edge_type: handles.edgeType, condition: '' },
      }
    })
    vueFlowEdges.value = applyAllEdgeStyles([...vueFlowEdges.value, ...newEdges])
    emitSortData()
    ElMessage.success(`已应用 ${accepted.length} 条建议连线`)
  }

  return {
    // 状态
    currentConnection,
    conditionDialogVisible,
    currentEdgeForm,
    editingEdgeId,

    // 方法
    onConnect,
    handleEditEdge,
    handleDeleteEdge,
    onEdgeConditionConfirm,
    onEdgesChange,
    handleEdgeSuggestionsConfirmed,
  }
}

// ============================================================================
// useFlowTypeOps - 类型操作
// ============================================================================

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
  normalizeEdges: (
    edges: Edge[],
    styleMap?: Record<string, EdgeStyleConfig>,
    isOverview?: boolean
  ) => Edge[]
  autoLayoutByMode: (
    mode: string,
    nodes: FlowEditorNode[],
    edges: FlowGraphEdge[],
    focusedNodeId?: string | null
  ) => FlowEditorNode[]
  layoutMode: Ref<string>
  focusedNodeId: Ref<string | null>
  getEdgeStyle: (type: string) => EdgeStyleConfig
  isProgrammaticEdgeChange: Ref<boolean>
  fitView?: (options: { duration: number; padding: number }) => Promise<void>
}

export function useFlowTypeOps(options: UseFlowTypeOpsOptions) {
  const {
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    emitSortData,
    saveSnapshot,
    applyAllEdgeStyles,
    currentEdgeStyles,
    isOverviewMode,
    getNodeData: getNodeDataFn,
    getMainNodesInOrder: getMainNodesInOrderFn,
    normalizeMainNodeOrders: normalizeMainNodeOrdersFn,
    normalizeEdges: normalizeEdgesFn,
    autoLayoutByMode: autoLayout,
    getEdgeStyle,
    isProgrammaticEdgeChange,
    fitView,
  } = options

  const pendingFlowTypeChange = ref<{ nodeId: string; type: string } | null>(null)
  const pendingFlowMeta = ref<FlowMetaData | null>(null)
  const flowTypeConfigVisible = ref(false)
  const branchCounter = ref(1)

  const getSelectedMainNodeId = (): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeDataFn(node).flow_type === 'main' ? node.id : null
  }

  const handleFlowTypeChange = (nodeId: string, type: string): void => {
    if (type === 'main') {
      saveSnapshot()
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: FlowGraphEdge) =>
          !(e.target === nodeId && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type as string))
      )
      const nextMainOrder =
        getMainNodesInOrderFn(vueFlowNodes.value, vueFlowEdges.value as unknown as Edge[]).length + 1
      vueFlowNodes.value = normalizeMainNodeOrdersFn(
        vueFlowNodes.value.map((node) => {
          if (node.id !== nodeId) return node
          const nodeData = getNodeDataFn(node)
          return {
            ...node,
            data: {
              ...nodeData,
              flow_type: type as EditorNodeData['flow_type'],
              main_order: nodeData.main_order ?? nextMainOrder,
              flow_meta: undefined,
            },
          }
        }),
        vueFlowEdges.value as unknown as Edge[]
      )
      emitSortData()
      vueFlowNodes.value = autoLayout(
        'focused-path',
        vueFlowNodes.value,
        vueFlowEdges.value,
        nodeId
      )
      return
    }
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (!node) return
    pendingFlowTypeChange.value = { nodeId, type }
    pendingFlowMeta.value = getNodeDataFn(node).flow_meta || null
    flowTypeConfigVisible.value = true
  }

  const handleFlowTypeConfigConfirm = (meta: FlowMetaData): void => {
    if (!pendingFlowTypeChange.value) return
    const { nodeId, type } = pendingFlowTypeChange.value
    const parentNodeId = meta.parent_main_node_id
    saveSnapshot()
    const currentMainNodesBefore = getMainNodesInOrderFn(
      vueFlowNodes.value,
      vueFlowEdges.value as unknown as Edge[]
    )
    const nodeIndexBefore = currentMainNodesBefore.findIndex((n) => n.id === nodeId)
    const wasMainNode = nodeIndexBefore >= 0 && type !== 'main'
    let predecessorMainId: string | null = null
    let successorMainId: string | null = null
    if (wasMainNode) {
      if (nodeIndexBefore > 0) predecessorMainId = currentMainNodesBefore[nodeIndexBefore - 1].id
      if (nodeIndexBefore < currentMainNodesBefore.length - 1)
        successorMainId = currentMainNodesBefore[nodeIndexBefore + 1].id
    }
    vueFlowNodes.value = normalizeMainNodeOrdersFn(
      vueFlowNodes.value.map((node) => {
        if (node.id !== nodeId) return node
        const nodeData = getNodeDataFn(node)
        return {
          ...node,
          data: {
            ...nodeData,
            flow_type: type as EditorNodeData['flow_type'],
            main_order: undefined,
            flow_meta: meta,
          },
        }
      }),
      vueFlowEdges.value as unknown as Edge[]
    )
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = vueFlowEdges.value.filter((e: FlowGraphEdge) => {
      if (e.target === nodeId && e.source === parentNodeId && e.data?.edge_type !== 'normal')
        return false
      if (e.source === nodeId || e.target === nodeId) {
        if (predecessorMainId && successorMainId) {
          if (
            (e.source === predecessorMainId && e.target === nodeId) ||
            (e.source === nodeId && e.target === successorMainId)
          )
            return false
        } else if (e.source === nodeId || e.target === nodeId) return false
      }
      return true
    })
    if (parentNodeId) {
      const existingEdgeIndex = vueFlowEdges.value.findIndex(
        (e: FlowGraphEdge) => e.target === nodeId && e.source === parentNodeId
      )
      const style = getEdgeStyle(type)
      const handles = inferEdgeType('main', type)
      const newEdge: FlowGraphEdge = {
        id:
          existingEdgeIndex >= 0 ? vueFlowEdges.value[existingEdgeIndex].id : `edge_${Date.now()}`,
        source: parentNodeId,
        target: nodeId,
        sourceHandle: handles.sourceHandle,
        targetHandle: handles.targetHandle,
        type: 'default',
        animated: true,
        style,
        label: `${type === 'branch' ? '分支' : type === 'exception' ? '异常' : '弹窗'}：${meta.trigger_condition || ''}`,
        data: {
          edge_type: type,
          condition: meta.trigger_condition,
          pre_action: meta.pre_action,
          note: meta.note,
        },
      }
      if (existingEdgeIndex >= 0)
        vueFlowEdges.value = normalizeEdgesFn(
          [
            ...vueFlowEdges.value.slice(0, existingEdgeIndex),
            newEdge,
            ...vueFlowEdges.value.slice(existingEdgeIndex + 1),
          ] as unknown as Edge[],
          currentEdgeStyles.value,
          isOverviewMode.value
        ) as unknown as FlowGraphEdge[]
      else
        vueFlowEdges.value = normalizeEdgesFn(
          [...vueFlowEdges.value, newEdge] as unknown as Edge[],
          currentEdgeStyles.value,
          isOverviewMode.value
        ) as unknown as FlowGraphEdge[]
    }
    if (predecessorMainId && successorMainId) {
      const existingDirectEdge = vueFlowEdges.value.find(
        (e: FlowGraphEdge) => e.source === predecessorMainId && e.target === successorMainId
      )
      const mainChainEdge: FlowGraphEdge = {
        id: existingDirectEdge?.id || `edge_${predecessorMainId}_${successorMainId}_${Date.now()}`,
        source: predecessorMainId,
        target: successorMainId,
        sourceHandle: 'source-right',
        targetHandle: 'target-left',
        type: 'default',
        label: existingDirectEdge?.label || '连线',
        data: existingDirectEdge?.data || { edge_type: 'normal' },
      }
      if (existingDirectEdge)
        vueFlowEdges.value = vueFlowEdges.value.map((e: FlowGraphEdge) =>
          e.id === existingDirectEdge.id ? mainChainEdge : e
        )
      else vueFlowEdges.value = [...vueFlowEdges.value, mainChainEdge]
    }
    flowTypeConfigVisible.value = false
    pendingFlowTypeChange.value = null
    pendingFlowMeta.value = null
    vueFlowNodes.value = autoLayout(
      'focused-path',
      vueFlowNodes.value,
      vueFlowEdges.value,
      nodeId
    )
    emitSortData()
    nextTick(() => {
      fitView?.({ duration: 300, padding: 0.15 })
    })
  }

  const handleQuickCreateBranch = async (): Promise<void> => {
    const mainNodeId = getSelectedMainNodeId()
    if (!mainNodeId) return
    try {
      const { value: branchName } = await ElMessageBox.prompt(
        '请输入分支页面名称',
        '快速创建分支',
        {
          confirmButtonText: '创建',
          cancelButtonText: '取消',
          inputValue: `新分支页面${branchCounter.value}`,
          inputValidator: (val: string) => {
            if (!val || !val.trim()) return '页面名称不能为空'
            return true
          },
        }
      )
      saveSnapshot()
      const mainNode = vueFlowNodes.value.find((n) => n.id === mainNodeId)!
      const branchId = `node_branch_${Date.now()}`
      const branchScreenId = -(VIRTUAL_SCREEN_ID_OFFSET + branchCounter.value)
      const branchNode: FlowEditorNode = {
        id: branchId,
        type: 'custom',
        position: { x: mainNode.position.x, y: mainNode.position.y + NODE_SPACING_Y },
        data: {
          screen_id: branchScreenId,
          screen_name: branchName.trim(),
          summary: '',
          ui_spec_elements: [],
          flow_type: 'branch',
          image_url: '',
        },
      }
      const branchHandles = inferEdgeType('main', 'branch')
      const branchEdge: FlowGraphEdge = {
        id: `edge_${mainNodeId}_${branchId}`,
        source: mainNodeId,
        target: branchId,
        sourceHandle: branchHandles.sourceHandle,
        targetHandle: branchHandles.targetHandle,
        type: 'default',
        data: { edge_type: 'branch', condition: '', pre_action: '', note: '' },
        label: branchName.trim(),
      }
      vueFlowNodes.value = [...vueFlowNodes.value, branchNode]
      vueFlowEdges.value = normalizeEdgesFn(
        [...vueFlowEdges.value, branchEdge] as unknown as Edge[],
        currentEdgeStyles.value,
        isOverviewMode.value
      ) as unknown as FlowGraphEdge[]
      selectedNodes.value = [branchId]
      branchCounter.value++
      vueFlowNodes.value = autoLayout(
        'focused-path',
        vueFlowNodes.value,
        vueFlowEdges.value,
        branchId
      )
      emitSortData()
      ElMessage.success(`已创建分支节点：${branchName.trim()}`)
    } catch {
      /* user cancelled */
    }
  }

  const handleBatchFlowTypeChange = (type: string): void => {
    if (selectedNodes.value.length < 2) return
    saveSnapshot()
    const selectedSet = new Set(selectedNodes.value)
    vueFlowNodes.value = normalizeMainNodeOrdersFn(
      vueFlowNodes.value.map((node) => {
        if (!selectedSet.has(node.id)) return node
        const nodeData = getNodeDataFn(node)
        if (nodeData.flow_type === type) return node
        return {
          ...node,
          data: {
            ...nodeData,
            flow_type: type as EditorNodeData['flow_type'],
            main_order: type === 'main' ? (nodeData.main_order ?? 0) : undefined,
            flow_meta: undefined,
          },
        }
      }),
      vueFlowEdges.value as unknown as Edge[]
    )
    if (type === 'main') {
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: FlowGraphEdge) =>
          !(
            selectedSet.has(e.target) &&
            ['branch', 'exception', 'bypass'].includes(e.data?.edge_type as string)
          )
      )
    }
    vueFlowEdges.value = applyAllEdgeStyles(
      vueFlowEdges.value.map((edge: FlowGraphEdge) => {
        const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
        if (!targetNode) return edge
        const targetType = getNodeDataFn(targetNode).flow_type
        const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
        const sourceType = sourceNode ? getNodeDataFn(sourceNode).flow_type : 'main'
        const newEdgeType = targetType === 'main' ? 'normal' : targetType
        const handles = inferEdgeType(sourceType, targetType)
        return {
          ...edge,
          sourceHandle: handles.sourceHandle,
          targetHandle: handles.targetHandle,
          data: { ...edge.data, edge_type: newEdgeType },
        }
      })
    )
    emitSortData()
    ElMessage.success(
      `已将 ${selectedNodes.value.length} 个节点设为${FLOW_TYPE_LABEL_MAP[type] || type}`
    )
  }

  return {
    pendingFlowTypeChange,
    pendingFlowMeta,
    flowTypeConfigVisible,
    branchCounter,
    handleFlowTypeChange,
    handleFlowTypeConfigConfirm,
    handleQuickCreateBranch,
    handleBatchFlowTypeChange,
  }
}

// ============================================================================
// useFlowEdgeTooltip - 边 Tooltip
// ============================================================================

/** useFlowEdgeTooltip 配置项 */
// eslint-disable-next-line @typescript-eslint/no-empty-interface
export interface UseFlowEdgeTooltipOptions {}

/** 边 tooltip 数据结构 */
export interface EdgeTooltipData {
  id: string
  source: string
  target: string
  label?: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

/** useFlowEdgeTooltip 返回值 */
export interface UseFlowEdgeTooltipReturn {
  edgeTooltipVisible: Ref<boolean>
  edgeTooltipData: Ref<EdgeTooltipData | null>
  edgeTooltipPosition: Ref<{ x: number; y: number }>
  onEdgeMouseEnter: (event: EdgeMouseEvent) => void
  onEdgeMouseLeave: () => void
  onEdgeMouseMove: (event: EdgeMouseEvent) => void
  onEdgeTooltipEnter: () => void
  onEdgeTooltipLeave: () => void
}

/**
 * 从 FlowSortEditor 抽取的边 tooltip 交互逻辑。
 * 管理鼠标悬停边时显示/隐藏 tooltip，以及 tooltip 自身的悬停保持。
 */
export function useFlowEdgeTooltip(_options: UseFlowEdgeTooltipOptions): UseFlowEdgeTooltipReturn {
  const edgeTooltipVisible = ref(false)
  const edgeTooltipData = ref<EdgeTooltipData | null>(null)
  const edgeTooltipPosition = ref({ x: 0, y: 0 })

  let edgeTooltipRafId: number | null = null
  let edgeTooltipHideTimer: ReturnType<typeof setTimeout> | null = null
  let edgeTooltipHovered = false

  const onEdgeMouseEnter = (event: EdgeMouseEvent) => {
    const mouseEvent = event.event as MouseEvent
    edgeTooltipData.value = event.edge as unknown as EdgeTooltipData
    edgeTooltipPosition.value = { x: mouseEvent.clientX + 12, y: mouseEvent.clientY + 12 }
    edgeTooltipVisible.value = true
  }

  const onEdgeMouseMove = (event: EdgeMouseEvent) => {
    // 只在 tooltip 未显示时更新位置，避免 tooltip 跟随鼠标移动导致无法点击
    if (edgeTooltipVisible.value) return
    if (edgeTooltipRafId !== null) return
    edgeTooltipRafId = requestAnimationFrame(() => {
      const mouseEvent = event.event as MouseEvent
      edgeTooltipPosition.value = { x: mouseEvent.clientX + 12, y: mouseEvent.clientY + 12 }
      edgeTooltipRafId = null
    })
  }

  const onEdgeMouseLeave = () => {
    if (edgeTooltipRafId !== null) {
      cancelAnimationFrame(edgeTooltipRafId)
      edgeTooltipRafId = null
    }
    // 延迟隐藏，给用户时间移入 tooltip 点击按钮
    edgeTooltipHideTimer = setTimeout(() => {
      if (!edgeTooltipHovered) {
        edgeTooltipVisible.value = false
        edgeTooltipData.value = null
      }
    }, 200)
  }

  const onEdgeTooltipEnter = () => {
    edgeTooltipHovered = true
    if (edgeTooltipHideTimer) {
      clearTimeout(edgeTooltipHideTimer)
      edgeTooltipHideTimer = null
    }
  }

  const onEdgeTooltipLeave = () => {
    edgeTooltipHovered = false
    edgeTooltipVisible.value = false
    edgeTooltipData.value = null
  }

  onUnmounted(() => {
    if (edgeTooltipRafId !== null) {
      cancelAnimationFrame(edgeTooltipRafId)
      edgeTooltipRafId = null
    }
    if (edgeTooltipHideTimer) {
      clearTimeout(edgeTooltipHideTimer)
      edgeTooltipHideTimer = null
    }
  })

  return {
    edgeTooltipVisible,
    edgeTooltipData,
    edgeTooltipPosition,
    onEdgeMouseEnter,
    onEdgeMouseLeave,
    onEdgeMouseMove,
    onEdgeTooltipEnter,
    onEdgeTooltipLeave,
  }
}

// ============================================================================
// useFlowPathHighlight - 节点选择与路径高亮
// ============================================================================

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
