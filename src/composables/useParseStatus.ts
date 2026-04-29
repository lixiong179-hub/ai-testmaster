import type { UIScreenListResponse } from '@/api/uiPrototype'

const PARSE_STATUS_TYPE_MAP: Record<string, string> = {
  pending: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'danger'
}

const PARSE_STATUS_TEXT_MAP: Record<string, string> = {
  pending: '待解析',
  running: '解析中',
  completed: '已完成',
  failed: '解析失败'
}

export const getParseStatusType = (status: string): string => {
  return PARSE_STATUS_TYPE_MAP[status] || 'info'
}

export const getParseStatusText = (status: string): string => {
  return PARSE_STATUS_TEXT_MAP[status] || status
}

export function isScreenListResponse(data: unknown): data is UIScreenListResponse {
  if (typeof data !== 'object' || data === null) return false
  const obj = data as Record<string, unknown>
  if ('data' in obj && typeof obj.data === 'object' && obj.data !== null) {
    const inner = obj.data as Record<string, unknown>
    return 'items' in inner && Array.isArray(inner.items)
  }
  return 'items' in obj && Array.isArray(obj.items)
}

export function getQueryParam(value: string | null | undefined | Array<string | null>): string {
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}
