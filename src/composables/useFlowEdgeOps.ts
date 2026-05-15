import { ref, watch, nextTick, type Ref } from 'vue'
import { type Connection as FlowConnection, type EdgeChange } from '@vue-flow/core'
import { ElMessage } from 'element-plus'
import {
  type FlowEditorNode,
  type FlowGraphEdge,
  type EdgeStyleConfig,
  getNodeData,
  inferEdgeType,
} from '@/composables/useFlowEditor'
import { type EdgeSuggestion } from '@/composables/useEdgeSuggestion'

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
  normalizeEdges: (edges: any[], styleMap?: any, isOverview?: boolean) => any[]
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
  const handleEditEdge = (edge: any, closeTooltip?: () => void): void => {
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
  const handleDeleteEdge = (edge: any, closeTooltip?: () => void): void => {
    if (closeTooltip) closeTooltip()
    saveSnapshot()
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = vueFlowEdges.value.filter((e: any) => e.id !== edge.id)
    emitSortData()
    ElMessage.success('已删除连线')
  }

  /** 边条件确认 - 新建或更新边 */
  const onEdgeConditionConfirm = (edgeData: EdgeConditionConfirmData): void => {
    saveSnapshot()

    if (editingEdgeId.value) {
      // 编辑已有边
      vueFlowEdges.value = applyAllEdgeStyles(
        vueFlowEdges.value.map((e: any) => {
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
        (e: any) =>
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
        [...vueFlowEdges.value, newEdge] as any,
        currentEdgeStyles.value,
        isOverviewMode.value
      ) as any
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

  /** 设置程序化边变更标志（供外部调用，如流程类型变更时过滤边） - 已通过共享 ref 替代，保留兼容 */

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
