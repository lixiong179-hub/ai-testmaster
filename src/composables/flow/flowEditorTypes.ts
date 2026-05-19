import type { Styles } from '@vue-flow/core'
import type { FlowNodeData } from '@/store/flowSort'

export type EditorNodeData = {
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
  flow_type: FlowNodeData['flow_type']
  main_order?: number
  image_url?: string
  element_count?: number
  flow_meta?: FlowNodeData['flow_meta']
}

export interface FlowEditorNode {
  id: string
  type?: string
  position: { x: number; y: number }
  data: EditorNodeData
  [key: string]: unknown
}

export interface FlowGraphEdge {
  id: string
  source: string
  target: string
  type: string
  sourceHandle?: string
  targetHandle?: string
  label?: string | number
  style?: Record<string, unknown>
  animated?: boolean
  hidden?: boolean
  selected?: boolean
  markerEnd?: unknown
  data?: Record<string, unknown>
}

export type EdgeStyleConfig = Styles & {
  stroke: string
  strokeWidth: number
  strokeDasharray?: string
}

export interface FlowValidationResult {
  errors: string[]
  warnings: string[]
}

export type FlowEdgeInput = {
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition: string
  label: string
}

export interface EdgeHandles {
  sourceHandle: string
  targetHandle: string
  edgeType: 'normal' | 'branch' | 'exception' | 'bypass'
}
