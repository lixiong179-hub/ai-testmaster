/**
 * UI 原型相关的通用辅助方法。
 *
 * 这个模块只负责：
 * 1. UI 原型接口响应体判断
 * 2. 路由 query 参数取值
 *
 * `UIScreen.parse_status` 的展示逻辑统一放在 `uiScreenStatus.ts`。
 */
import type { UIScreenListResponse } from '@/api/uiPrototype'

export function isUIScreenListResponse(data: unknown): data is UIScreenListResponse {
  if (typeof data !== 'object' || data === null) return false
  const obj = data as Record<string, unknown>
  if ('data' in obj && typeof obj.data === 'object' && obj.data !== null) {
    const inner = obj.data as Record<string, unknown>
    return 'items' in inner && Array.isArray(inner.items)
  }
  return 'items' in obj && Array.isArray(obj.items)
}

export function getRouteQueryParam(
  value: string | null | undefined | Array<string | null>
): string {
  if (Array.isArray(value)) return value[0] || ''
  return value || ''
}
