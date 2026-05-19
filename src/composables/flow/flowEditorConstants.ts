import type { EdgeStyleConfig } from './flowEditorTypes'

export const EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#409eff', strokeWidth: 2 },
  branch: { stroke: '#67c23a', strokeWidth: 2 },
  exception: { stroke: '#f56c6c', strokeWidth: 2, strokeDasharray: '5 5' },
  bypass: { stroke: '#e6a23c', strokeWidth: 2, strokeDasharray: '3 3' },
}

export const OVERVIEW_EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  normal: { stroke: '#b8c2cc', strokeWidth: 1.2 },
  branch: { stroke: '#95d475', strokeWidth: 1.2 },
  exception: { stroke: '#f3a6a6', strokeWidth: 1.2, strokeDasharray: '5 5' },
  bypass: { stroke: '#eebe77', strokeWidth: 1.2, strokeDasharray: '3 3' },
}

export const FLOW_TYPE_TAG_MAP: Record<string, string> = {
  main: 'primary',
  branch: 'success',
  exception: 'danger',
  bypass: 'warning',
}

export const FLOW_TYPE_LABEL_MAP: Record<string, string> = {
  main: '主干',
  branch: '分支',
  exception: '异常',
  bypass: '旁路',
}

export const AUTO_CONNECT_DISTANCE = 350
