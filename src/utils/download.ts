/**
 * 文件下载与 Blob 错误解析工具。
 *
 * 用于配合 axios `responseType: 'blob'` 的接口：
 *  - 从 `Content-Disposition` 头解析中文文件名（RFC 5987）
 *  - 触发浏览器下载
 *  - 当请求失败但响应仍是 Blob 时，把 Blob 反解为后端的 JSON detail
 */

import type { AxiosResponse } from 'axios'

/** 解析 `Content-Disposition` 头里的文件名，优先 RFC 5987 UTF-8。 */
export function parseFilename(disposition: string | undefined | null): string | undefined {
  if (!disposition) return undefined
  const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(disposition)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(disposition)
  return plain?.[1]
}

/** 触发浏览器下载一段 Blob。 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 用 AxiosResponse 直接触发下载，自动从响应头读取文件名；读不到时用 fallback。
 * 返回最终使用的文件名，便于上层日志/提示。
 */
export function downloadFromResponse(resp: AxiosResponse<Blob>, fallbackName: string): string {
  const disposition =
    (resp.headers?.['content-disposition'] as string | undefined) ||
    (resp.headers as unknown as { get?: (name: string) => string | undefined })?.get?.(
      'content-disposition'
    )
  const filename = parseFilename(disposition) || fallbackName
  downloadBlob(resp.data, filename)
  return filename
}

/**
 * 当 axios 请求设置了 `responseType: 'blob'` 时，错误响应的 `data` 也是 Blob。
 * 这里把它反解为 JSON 中的 `detail` 字段，拿不到则返回兜底 message。
 */
export async function parseBlobError(err: unknown, fallbackMsg: string): Promise<string> {
  const e = err as { response?: { data?: unknown }; message?: string } | null
  const data = e?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      try {
        const json = JSON.parse(text)
        return json?.detail || json?.message || fallbackMsg
      } catch {
        return text || fallbackMsg
      }
    } catch {
      return fallbackMsg
    }
  }
  return e?.message || fallbackMsg
}
