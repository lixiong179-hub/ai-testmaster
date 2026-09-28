/**
 * 日期格式化工具
 *
 * 统一项目中的 formatTime / formatDate 实现，消除 6+ 处重复定义。
 */

const INVALID_PLACEHOLDER = '—'

/**
 * 格式化 ISO 时间字符串为本地日期时间（zh-CN，24 小时制）
 * @param iso ISO 8601 字符串或 null/undefined
 * @param placeholder 无效值时的占位符，默认 '—'
 * @returns 如 "2026/07/28 14:30:00"
 */
export function formatTime(iso: string | null | undefined, placeholder = INVALID_PLACEHOLDER): string {
  if (!iso) return placeholder
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

/**
 * 格式化 ISO 时间字符串为仅日期部分
 * @param iso ISO 8601 字符串或 null/undefined
 * @param placeholder 无效值时的占位符，默认 '—'
 * @returns 如 "2026/07/28"
 */
export function formatDate(iso: string | null | undefined, placeholder = INVALID_PLACEHOLDER): string {
  if (!iso) return placeholder
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return d.toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}
