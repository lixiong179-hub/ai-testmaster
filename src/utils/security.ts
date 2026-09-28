/**
 * 前端安全工具函数
 * 集中管理输入校验、重定向净化等安全相关逻辑，便于单元测试与复用
 */

/** 单文件大小上限（50MB），防止超大文件上传造成 DoS */
export const MAX_UPLOAD_FILE_SIZE = 50 * 1024 * 1024

/** 允许上传的文件扩展名白名单（小写，不含点号） */
export const ALLOWED_UPLOAD_EXTENSIONS = new Set([
  'txt',
  'doc',
  'docx',
  'pdf',
  'md',
  'xlsx',
  'xls',
  'csv',
  'json',
  'yaml',
  'yml',
  'png',
  'jpg',
  'jpeg',
  'gif',
  'webp',
  'bmp',
  'zip',
  'rar',
])

/** 默认安全重定向首页 */
const DEFAULT_REDIRECT = '/home/workbench'

/** 允许在 :href 中使用的 URL 协议白名单 */
const SAFE_URL_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:'])

/**
 * 安全化用户提交的 URL，防止 javascript:/data: 等协议导致的 XSS 或钓鱼。
 * 仅允许 http/https/mailto/tel 协议；不合规时返回空串（绑定到 :href 不跳转）。
 *
 * @param url 待校验的 URL（通常来自后端存储的用户提交数据）
 * @returns 安全的 URL；不合规返回空串
 */
export function sanitizeUrl(url: unknown): string {
  if (typeof url !== 'string' || url.length === 0) return ''
  const trimmed = url.trim()
  // 相对路径（以 / 或 # 开头）直接放行
  if (trimmed.startsWith('/') || trimmed.startsWith('#')) return trimmed
  try {
    const parsed = new URL(trimmed)
    if (SAFE_URL_PROTOCOLS.has(parsed.protocol)) return trimmed
  } catch {
    // 非 URL 格式，拒绝
  }
  return ''
}

/**
 * 安全处理登录后重定向地址，防止开放重定向攻击：
 * 仅允许以单个 "/" 开头的站内相对路径，拒绝 "//" 协议相对 URL 和反斜杠变体。
 *
 * @param redirect 待校验的重定向地址（通常来自 URL query 参数）
 * @returns 安全的站内路径，不合规时回退到默认首页
 */
export function sanitizeRedirect(redirect: unknown): string {
  if (typeof redirect !== 'string' || redirect.length === 0) return DEFAULT_REDIRECT
  // 拒绝协议相对 URL（//evil.com）和反斜杠变体（/\evil.com）
  if (redirect.startsWith('//') || redirect.startsWith('/\\')) return DEFAULT_REDIRECT
  // 仅允许以 / 开头的站内路径
  if (!redirect.startsWith('/')) return DEFAULT_REDIRECT
  return redirect
}

/**
 * 校验单个上传文件是否满足安全要求：
 * 1. 扩展名必须在白名单内（防止上传可执行文件/脚本）
 * 2. 文件大小不得超过 MAX_UPLOAD_FILE_SIZE（防止超大文件 DoS）
 * 3. 文件大小不得为 0（防止空文件上传）
 *
 * @param file 待校验的文件对象
 * @returns 错误原因字符串，校验通过返回 null
 */
export function validateUploadFile(file: File): string | null {
  const ext = file.name.includes('.') ? file.name.split('.').pop()!.toLowerCase() : ''
  if (!ext || !ALLOWED_UPLOAD_EXTENSIONS.has(ext)) {
    return `不支持的文件类型: .${ext || '未知'}`
  }
  if (file.size > MAX_UPLOAD_FILE_SIZE) {
    return `文件 ${file.name} 超过 50MB 大小限制`
  }
  if (file.size === 0) {
    return `文件 ${file.name} 为空`
  }
  return null
}
