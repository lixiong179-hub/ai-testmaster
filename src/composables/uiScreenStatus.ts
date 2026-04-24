/**
 * `UIScreen.parse_status` 的单一事实来源。
 *
 * 这个模块负责：
 * 1. 状态文案映射
 * 2. 标签类型映射
 * 3. 派生布尔状态（如是否可查看详情）
 *
 * 页面和组件只应依赖这里的结果，不再各自维护状态判断。
 */
type UIScreenStatusLike = {
  parse_status?: string | null
  parse_status_text?: string | null
}

const UI_SCREEN_STATUS_TYPE_MAP: Record<string, string> = {
  pending: 'info',
  running: 'warning',
  completed: 'success',
  failed: 'danger',
}

const UI_SCREEN_STATUS_TEXT_MAP: Record<string, string> = {
  pending: '待解析',
  running: '解析中',
  completed: '已解析',
  failed: '解析失败',
}

function normalizeStatusInput(input: UIScreenStatusLike | string | null | undefined) {
  if (typeof input === 'string') {
    return {
      status: input,
      customText: '',
    }
  }

  return {
    status: input?.parse_status || 'pending',
    customText: input?.parse_status_text || '',
  }
}

export interface UIScreenStatusMeta {
  status: string
  type: string
  text: string
  isPending: boolean
  isRunning: boolean
  isCompleted: boolean
  isFailed: boolean
  canShowDetails: boolean
}

export function getUIScreenStatusType(
  input: UIScreenStatusLike | string | null | undefined
): string {
  const { status } = normalizeStatusInput(input)
  return UI_SCREEN_STATUS_TYPE_MAP[status] || 'info'
}

export function getUIScreenStatusText(
  input: UIScreenStatusLike | string | null | undefined
): string {
  const { status, customText } = normalizeStatusInput(input)
  return customText || UI_SCREEN_STATUS_TEXT_MAP[status] || status
}

export function getUIScreenStatusMeta(
  input: UIScreenStatusLike | string | null | undefined
): UIScreenStatusMeta {
  const { status } = normalizeStatusInput(input)
  const type = getUIScreenStatusType(input)
  const text = getUIScreenStatusText(input)

  return {
    status,
    type,
    text,
    isPending: status === 'pending',
    isRunning: status === 'running',
    isCompleted: status === 'completed',
    isFailed: status === 'failed',
    canShowDetails: status === 'completed',
  }
}

export type { UIScreenStatusLike }
