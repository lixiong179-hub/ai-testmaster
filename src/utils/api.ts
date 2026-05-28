/** API 响应解包工具，兼容双层嵌套响应 */
export function unwrapApiResponse<T = unknown>(
  response: unknown
): {
  code?: number
  data?: T
  message?: string
} {
  if (response && typeof response === 'object') {
    const resp = response as Record<string, unknown>
    if (
      typeof resp.code !== 'undefined' ||
      typeof resp.message !== 'undefined' ||
      typeof resp.msg !== 'undefined'
    ) {
      return {
        code: resp.code as number | undefined,
        data: resp.data as T | undefined,
        message: (resp.message || resp.msg) as string | undefined,
      }
    }

    const inner = resp.data as Record<string, unknown> | undefined
    if (
      inner &&
      typeof inner === 'object' &&
      (typeof inner.code !== 'undefined' ||
        typeof inner.message !== 'undefined' ||
        typeof inner.msg !== 'undefined')
    ) {
      return {
        code: inner.code as number | undefined,
        data: inner.data as T | undefined,
        message: (inner.message || inner.msg) as string | undefined,
      }
    }
  }

  return { code: 200, data: response as T, message: '' }
}
