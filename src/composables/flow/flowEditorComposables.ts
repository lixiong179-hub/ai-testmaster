import { ref, computed } from 'vue'
import type { FlowEditorNode, FlowGraphEdge } from './flowEditorTypes'

export const useFlowHistory = () => {
  const historyStack = ref<{ nodes: FlowEditorNode[]; edges: FlowGraphEdge[] }[]>([])
  const canUndo = computed(() => historyStack.value.length > 0)

  const saveToHistory = (nodes: FlowEditorNode[], edges: FlowGraphEdge[]) => {
    historyStack.value.push({
      nodes: JSON.parse(JSON.stringify(nodes)),
      edges: JSON.parse(JSON.stringify(edges)),
    })
    if (historyStack.value.length > 50) historyStack.value.shift()
  }

  const undo = () => {
    if (historyStack.value.length === 0) return null
    return historyStack.value.pop() ?? null
  }

  return { historyStack, canUndo, saveToHistory, undo }
}

export const useFlowSelection = () => {
  const selectedNodes = ref<string[]>([])
  const draggingNodeId = ref<string | null>(null)

  const getSelectedMainNodeId = (allNodes: FlowEditorNode[]): string | null => {
    if (selectedNodes.value.length !== 1) return null
    const node = allNodes.find((n) => n.id === selectedNodes.value[0])
    return node && (node.data as { flow_type: string }).flow_type === 'main' ? node.id : null
  }

  const getSelectedMainOrder = (allNodes: FlowEditorNode[]): number | null => {
    const nodeId = getSelectedMainNodeId(allNodes)
    if (!nodeId) return null
    const node = allNodes.find((n) => n.id === nodeId)
    return node ? ((node.data as { main_order?: number }).main_order ?? null) : null
  }

  return { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder }
}
