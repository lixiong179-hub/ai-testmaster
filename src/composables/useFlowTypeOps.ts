import { ref, nextTick, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FlowMetaData } from '@/store/flowSort'
import type {
  EditorNodeData,
  EdgeStyleConfig,
  FlowEditorNode,
  FlowGraphEdge,
} from '@/composables/useFlowEditor'
import { FLOW_TYPE_LABEL_MAP } from '@/composables/useFlowEditor'

/** 快速创建分支时的虚拟 screen_id 偏移量 */
const VIRTUAL_SCREEN_ID_OFFSET = 1000
/** 分支节点与主干节点的垂直间距 */
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
  getMainNodesInOrder: (nodes: FlowEditorNode[]) => FlowEditorNode[]
  normalizeMainNodeOrders: (nodes: FlowEditorNode[]) => FlowEditorNode[]
  normalizeEdges: (edges: any[], styleMap?: any, isOverview?: boolean) => any[]
  autoLayoutByMode: (
    mode: string,
    nodes: FlowEditorNode[],
    edges: FlowGraphEdge[],
    focusedNodeId?: string | null,
  ) => FlowEditorNode[]
  layoutMode: Ref<string>
  focusedNodeId: Ref<string | null>
  getEdgeStyle: (type: string) => EdgeStyleConfig
  /** 共享的程序化边变更标志（与 useFlowEdgeOps/useFlowMainOrder 共用） */
  isProgrammaticEdgeChange: Ref<boolean>
  /** 可选：布局完成后自动适配视图（来自 useVueFlow 的 fitView） */
  fitView?: (options: { duration: number; padding: number }) => Promise<void>
}

/**
 * 流程类型操作 composable
 * 封装单个/批量节点流程类型变更、流程类型配置确认、快速创建分支等逻辑
 */
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
    getNodeData,
    getMainNodesInOrder,
    normalizeMainNodeOrders,
    normalizeEdges,
    autoLayoutByMode: autoLayout,
    layoutMode,
    focusedNodeId,
    getEdgeStyle,
    isProgrammaticEdgeChange,
    fitView,
  } = options

  // ---- 内部状态 ----
  const pendingFlowTypeChange = ref<{ nodeId: string; type: string } | null>(null)
  const pendingFlowMeta = ref<FlowMetaData | null>(null)
  const flowTypeConfigVisible = ref(false)
  const branchCounter = ref(1)

  // ---- 辅助方法 ----

  /** 获取当前选中的主干节点 ID（仅当选中恰好 1 个主干节点时返回） */
  const getSelectedMainNodeId = (): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeData(node).flow_type === 'main' ? node.id : null
  }

  // ---- 核心操作 ----

  /** 单个节点流程类型变更 */
  const handleFlowTypeChange = (nodeId: string, type: string): void => {
    if (type === 'main') {
      saveSnapshot()
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: any) =>
          !(e.target === nodeId && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)),
      )
      const nextMainOrder = getMainNodesInOrder(vueFlowNodes.value).length + 1
      vueFlowNodes.value = normalizeMainNodeOrders(
        vueFlowNodes.value.map((node) => {
          if (node.id !== nodeId) return node
          const nodeData = getNodeData(node)
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
      )
      emitSortData()
      vueFlowNodes.value = autoLayout(
        layoutMode.value,
        vueFlowNodes.value,
        vueFlowEdges.value as any,
        focusedNodeId.value,
      )
      return
    }

    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    if (!node) return

    pendingFlowTypeChange.value = { nodeId, type }
    pendingFlowMeta.value = getNodeData(node).flow_meta || null
    flowTypeConfigVisible.value = true
  }

  /** 流程类型配置弹窗确认回调 */
  const handleFlowTypeConfigConfirm = (meta: FlowMetaData): void => {
    if (!pendingFlowTypeChange.value) return
    const { nodeId, type } = pendingFlowTypeChange.value
    const parentNodeId = meta.parent_main_node_id

    saveSnapshot()

    vueFlowNodes.value = normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (node.id !== nodeId) return node
        const nodeData = getNodeData(node)
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
    )

    if (parentNodeId) {
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: any) =>
          !(e.target === nodeId && e.source === parentNodeId && e.data?.edge_type !== 'normal'),
      )
      const existingEdgeIndex = vueFlowEdges.value.findIndex(
        (e: any) => e.target === nodeId && e.source === parentNodeId,
      )
      const style = getEdgeStyle(type)
      const newEdge: FlowGraphEdge = {
        id:
          existingEdgeIndex >= 0
            ? vueFlowEdges.value[existingEdgeIndex].id
            : `edge_${Date.now()}`,
        source: parentNodeId,
        target: nodeId,
        type: 'default',
        animated: true,
        style,
        label: `${type === 'branch' ? '分支' : type === 'exception' ? '异常' : '旁路'}：${meta.trigger_condition || ''}`,
        data: {
          edge_type: type,
          condition: meta.trigger_condition,
          pre_action: meta.pre_action,
          note: meta.note,
        },
      }

      if (existingEdgeIndex >= 0) {
        vueFlowEdges.value = normalizeEdges(
          [
            ...vueFlowEdges.value.slice(0, existingEdgeIndex),
            newEdge,
            ...vueFlowEdges.value.slice(existingEdgeIndex + 1),
          ] as any,
          currentEdgeStyles.value,
          isOverviewMode.value,
        ) as any
      } else {
        vueFlowEdges.value = normalizeEdges(
          [...vueFlowEdges.value, newEdge] as any,
          currentEdgeStyles.value,
          isOverviewMode.value,
        ) as any
      }
    } else {
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: any) =>
          !(e.target === nodeId && ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)),
      )
    }

    flowTypeConfigVisible.value = false
    pendingFlowTypeChange.value = null
    pendingFlowMeta.value = null
    vueFlowNodes.value = autoLayout(
      layoutMode.value,
      vueFlowNodes.value,
      vueFlowEdges.value as any,
      focusedNodeId.value,
    )
    emitSortData()
    nextTick(() => {
      fitView?.({ duration: 300, padding: 0.15 })
    })
  }

  /** 快速创建分支节点 */
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
        },
      )

      saveSnapshot()

      const mainNode = vueFlowNodes.value.find((n) => n.id === mainNodeId)!
      const branchId = `node_branch_${Date.now()}`
      const branchScreenId = -(VIRTUAL_SCREEN_ID_OFFSET + branchCounter.value)

      const branchNode: FlowEditorNode = {
        id: branchId,
        type: 'custom',
        position: {
          x: mainNode.position.x,
          y: mainNode.position.y + NODE_SPACING_Y,
        },
        data: {
          screen_id: branchScreenId,
          screen_name: branchName.trim(),
          summary: '',
          ui_spec_elements: [],
          flow_type: 'branch',
          image_url: '',
        },
      }

      const branchEdge: FlowGraphEdge = {
        id: `edge_${mainNodeId}_${branchId}`,
        source: mainNodeId,
        target: branchId,
        type: 'default',
        data: {
          edge_type: 'branch',
          condition: '',
          pre_action: '',
          note: '',
        },
        label: branchName.trim(),
      }

      vueFlowNodes.value = [...vueFlowNodes.value, branchNode]
      vueFlowEdges.value = normalizeEdges(
        [...vueFlowEdges.value, branchEdge] as any,
        currentEdgeStyles.value,
        isOverviewMode.value,
      ) as any

      selectedNodes.value = [branchId]
      branchCounter.value++
      vueFlowNodes.value = autoLayout(
        layoutMode.value,
        vueFlowNodes.value,
        vueFlowEdges.value as any,
        focusedNodeId.value,
      )
      emitSortData()
      ElMessage.success(`已创建分支节点：${branchName.trim()}`)
    } catch {
      // 用户取消
    }
  }

  /** 批量流程类型变更 */
  const handleBatchFlowTypeChange = (type: string): void => {
    if (selectedNodes.value.length < 2) return
    saveSnapshot()
    const selectedSet = new Set(selectedNodes.value)

    vueFlowNodes.value = normalizeMainNodeOrders(
      vueFlowNodes.value.map((node) => {
        if (!selectedSet.has(node.id)) return node
        const nodeData = getNodeData(node)
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
    )

    if (type === 'main') {
      isProgrammaticEdgeChange.value = true
      vueFlowEdges.value = vueFlowEdges.value.filter(
        (e: any) =>
          !(selectedSet.has(e.target) &&
            ['branch', 'exception', 'bypass'].includes(e.data?.edge_type)),
      )
    }

    vueFlowEdges.value = applyAllEdgeStyles(
      vueFlowEdges.value.map((edge: any) => {
        const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
        if (!targetNode) return edge
        const targetType = getNodeData(targetNode).flow_type
        return {
          ...edge,
          data: { ...edge.data, edge_type: targetType === 'main' ? 'normal' : targetType },
        }
      }),
    )

    emitSortData()
    ElMessage.success(
      `已将 ${selectedNodes.value.length} 个节点设为${FLOW_TYPE_LABEL_MAP[type] || type}`,
    )
  }

  return {
    // 状态
    pendingFlowTypeChange,
    pendingFlowMeta,
    flowTypeConfigVisible,
    branchCounter,
    // 方法
    handleFlowTypeChange,
    handleFlowTypeConfigConfirm,
    handleQuickCreateBranch,
    handleBatchFlowTypeChange,
  }
}
