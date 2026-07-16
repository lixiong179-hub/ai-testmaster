import type { Ref } from 'vue'
import type { Edge } from '@vue-flow/core'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { useFlowSortStore } from '@/store/flowSort'
import type { FlowSortSubmitData } from '@/api/case'
import type {
  FlowEditorNode,
  FlowGraphEdge,
  EditorNodeData,
  FlowEdgeInput,
  FlowValidationResult,
} from '@/composables/useFlowEditor'
import {
  validateFlowData,
  normalizeMainNodeOrders,
  getOrderedNodesForSubmit,
} from '@/composables/useFlowEditor'

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
export default function useFlowSortData(options: UseFlowSortDataOptions): UseFlowSortDataReturn {
  const { vueFlowNodes, vueFlowEdges, emit, flowSortStore, getNodeData, moduleInfo } = options

  /** 将 FlowGraphEdge 序列化为 FlowEdgeData */
  function serializeEdge(edge: FlowGraphEdge): FlowEdgeData | null {
    const sourceNode = vueFlowNodes.value.find((n) => n.id === edge.source)
    const targetNode = vueFlowNodes.value.find((n) => n.id === edge.target)
    const sourceScreenId = sourceNode ? getNodeData(sourceNode).screen_id : undefined
    const targetScreenId = targetNode ? getNodeData(targetNode).screen_id : undefined
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
        existing.data = { ...existing.data, main_order: getNodeData(normalized).main_order }
      }
    })
    const flowNodes: FlowNodeData[] = normalizedNodes.map((node) => ({
      id: node.id,
      screen_id: getNodeData(node).screen_id,
      screen_name: getNodeData(node).screen_name,
      summary: getNodeData(node).summary,
      ui_spec_elements: getNodeData(node).ui_spec_elements,
      flow_type: getNodeData(node).flow_type,
      main_order: getNodeData(node).main_order,
      image_url: getNodeData(node).image_url,
      position: node.position,
      flow_meta: getNodeData(node).flow_meta,
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
          screen_id: getNodeData(node).screen_id,
          screen_order: index + 1,
          flow_type: getNodeData(node).flow_type,
          main_order: getNodeData(node).main_order,
          screen_name: getNodeData(node).screen_name,
          ui_spec_elements: getNodeData(node).ui_spec_elements || [],
          summary: getNodeData(node).summary || '',
          flow_meta: getNodeData(node).flow_meta || undefined,
          image_url: getNodeData(node).image_url || undefined,
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
