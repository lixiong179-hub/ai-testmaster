import type { ProjectFlowData } from '@/api/uiPrototype'

const STORAGE_KEY = 'flow-sort-data'

export { STORAGE_KEY }

export interface FlowMetaData {
  parent_node_id?: string
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
    state?: string
    description?: string
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
  module_info?: { name: string; description: string }
}

export function extractStatusFromError(error: unknown): number | null {
  const e = error as Record<string, unknown> | null
  if (!e) return null
  const response = e.response as Record<string, unknown> | undefined
  if (response && typeof response.status === 'number') return response.status
  if (typeof e.status === 'number') return e.status
  return null
}

export function computeHash(data: FlowSortData): string {
  try {
    const payload = JSON.stringify(data)
    let h1 = 0xdeadbeef
    let h2 = 0x41c6ce57
    for (let i = 0; i < payload.length; i++) {
      const ch = payload.charCodeAt(i)
      h1 = Math.imul(h1 ^ ch, 2654435761)
      h2 = Math.imul(h2 ^ ch, 1597334677)
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)
  } catch { return '' }
}

export function mapNodesToFlowData(nodes: FlowNodeData[]): ProjectFlowData['nodes'] {
  return nodes.map((n) => ({
    id: n.id, screen_id: n.screen_id, screen_name: n.screen_name, summary: n.summary,
    ui_spec_elements: n.ui_spec_elements as ProjectFlowData['nodes'][0]['ui_spec_elements'],
    flow_type: n.flow_type, main_order: n.main_order, image_url: n.image_url,
    position: n.position, flow_meta: n.flow_meta as ProjectFlowData['nodes'][0]['flow_meta'],
  }))
}

export function mapEdgesToFlowData(edges: FlowEdgeData[]): ProjectFlowData['edges'] {
  return edges.map((e) => ({
    id: e.id, source: e.source, target: e.target, edge_type: e.edge_type,
    condition: e.condition, label: e.label, trigger_action: e.trigger_action,
    pre_action: e.pre_action, note: e.note,
  }))
}
