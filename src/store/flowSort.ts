import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface FlowMetaData {
  parent_main_node_id?: string
  trigger_condition?: string
  pre_action?: string
  expected_result?: string
  bypass_reason?: string
  note?: string
}

export interface FlowNodeData {
  id: string
  screen_id: number
  screen_name: string
  summary?: string
  ui_spec_elements?: Array<{
    type: string
    label: string
    semantic?: string
    position?: string
    interactive?: boolean
  }>
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  main_order?: number
  image_url?: string
  position: { x: number; y: number }
  flow_meta?: FlowMetaData
}

export interface FlowEdgeData {
  id: string
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
  trigger_action?: string
  pre_action?: string
  note?: string
}

export interface FlowSortData {
  mode: 'linear' | 'graph'
  nodes: FlowNodeData[]
  edges: FlowEdgeData[]
  module_info?: {
    name: string
    description: string
  }
}

export const useFlowSortStore = defineStore('flowSort', () => {
  const mode = ref<'linear' | 'graph'>('graph')
  const nodes = ref<FlowNodeData[]>([])
  const edges = ref<FlowEdgeData[]>([])
  const moduleInfo = ref<{ name: string; description: string } | null>(null)

  const sortData = computed<FlowSortData>(() => ({
    mode: mode.value,
    nodes: nodes.value,
    edges: edges.value,
    module_info: moduleInfo.value || undefined,
  }))

  function setMode(newMode: 'linear' | 'graph') {
    mode.value = newMode
  }

  function updateNodes(newNodes: FlowNodeData[]) {
    nodes.value = newNodes
  }

  function updateEdges(newEdges: FlowEdgeData[]) {
    edges.value = newEdges
  }

  function setModuleInfo(info: { name: string; description: string } | null) {
    moduleInfo.value = info
  }

  function reset() {
    mode.value = 'graph'
    nodes.value = []
    edges.value = []
    moduleInfo.value = null
  }

  function toJson(): string {
    return JSON.stringify(sortData.value)
  }

  function fromJson(json: string) {
    try {
      const data = JSON.parse(json) as FlowSortData
      mode.value = data.mode || 'graph'
      nodes.value = data.nodes || []
      edges.value = data.edges || []
      moduleInfo.value = data.module_info || null
    } catch {
      reset()
    }
  }

  return {
    mode,
    nodes,
    edges,
    moduleInfo,
    sortData,
    setMode,
    updateNodes,
    updateEdges,
    setModuleInfo,
    reset,
    toJson,
    fromJson,
  }
})
