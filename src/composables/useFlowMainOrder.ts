import { type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Edge } from '@vue-flow/core'
import type { EditorNodeData, FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'
import { getMainNodeCount, layoutMainNodesByOrder } from '@/composables/useFlowEditor'

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
    getNodeData,
    getMainNodesInOrder,
    normalizeMainNodeOrders,
    applyAllEdgeStyles,
    isProgrammaticEdgeChange,
  } = options

  // ---- 辅助方法 ----

  /** 获取当前选中的主干节点 ID（仅当选中恰好 1 个主干节点时返回） */
  const getSelectedMainNodeId = (_nodes?: FlowEditorNode[]): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = vueFlowNodes.value.find((n) => n.id === selectedNodes.value[0])
    return node && getNodeData(node).flow_type === 'main' ? node.id : null
  }

  /** 获取当前选中的主干节点的 main_order */
  const getSelectedMainOrder = (_nodes?: FlowEditorNode[]): number | null => {
    const nodeId = getSelectedMainNodeId()
    if (!nodeId) return null
    const node = vueFlowNodes.value.find((n) => n.id === nodeId)
    return node ? (getNodeData(node).main_order ?? null) : null
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
      (e: any) => !deletedSet.has(e.source) && !deletedSet.has(e.target)
    )
    vueFlowNodes.value = normalizeMainNodeOrders(
      vueFlowNodes.value.filter((n) => !deletedSet.has(n.id)),
      vueFlowEdges.value as any
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

    const orderedMainNodes = getMainNodesInOrder(vueFlowNodes.value, vueFlowEdges.value as any)
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
      normalizeMainNodeOrders(
        vueFlowNodes.value.map((node) => {
          if (!mainOrderMap.has(node.id)) return node
          return {
            ...node,
            data: {
              ...getNodeData(node),
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
