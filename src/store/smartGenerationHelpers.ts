/**
 * 智能生成 store 的纯函数工具集。
 * 抽取自 smartGeneration.ts，便于单测并控制单文件行数（项目规则：单文件≤350行）。
 * 所有函数均无副作用依赖 store 实例，IO 仅限 localStorage / 解析逻辑。
 */

/** localStorage 偏好 key 前缀，按用户隔离 */
const PREF_PREFIX = 'smart-gen'

/** 智能生成可持久化的用户偏好（仅非敏感字段） */
export interface SmartGenPreference {
  selectedProjectId: number | ''
  selectedTask: 'new_feature' | 'history_update' | 'import_asset'
  advancedConfig: {
    case_type: string
    exec_mode: string
    enhanced_mode: boolean
    mode: string
  }
}

/** Base64URL 解码（兼容浏览器与 happy-dom），失败返回空串 */
function decodeBase64Url(input: string): string {
  if (typeof atob !== 'function') return ''
  const padded = input.replace(/-/g, '+').replace(/_/g, '/')
  const pad = padded.length % 4
  const b64 = pad ? padded + '='.repeat(4 - pad) : padded
  try {
    return atob(b64)
  } catch {
    return ''
  }
}

/**
 * 从 localStorage 的 JWT token 解析当前用户 ID。
 * 无法识别（未登录/解析失败）时回退 'default'，保证偏好按用户隔离。
 */
export function readUserId(): string {
  const token = localStorage.getItem('token')
  if (!token) return 'default'
  try {
    const parts = token.split('.')
    if (parts.length < 2) return 'default'
    const payload = JSON.parse(decodeBase64Url(parts[1])) as Record<string, unknown>
    const id = payload.sub ?? payload.user_id ?? payload.userId ?? payload.id
    return id != null && id !== '' ? String(id) : 'default'
  } catch {
    return 'default'
  }
}

/** 构造偏好存储 key：smart-gen:{userId}:{field} */
export function buildPrefKey(userId: string, field: string): string {
  return `${PREF_PREFIX}:${userId}:${field}`
}

/** 读取并恢复用户偏好；无记录或解析失败时返回 null（边界兼容） */
export function restorePreferenceData(userId: string): SmartGenPreference | null {
  try {
    const raw = localStorage.getItem(buildPrefKey(userId, 'pref'))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<SmartGenPreference>
    if (!parsed || typeof parsed !== 'object') return null
    const adv = parsed.advancedConfig
    return {
      selectedProjectId:
        typeof parsed.selectedProjectId === 'number' ? parsed.selectedProjectId : '',
      selectedTask:
        parsed.selectedTask === 'history_update' || parsed.selectedTask === 'import_asset'
          ? parsed.selectedTask
          : 'new_feature',
      advancedConfig: {
        case_type: typeof adv?.case_type === 'string' ? adv.case_type : 'manual',
        exec_mode: typeof adv?.exec_mode === 'string' ? adv.exec_mode : 'manual',
        enhanced_mode: typeof adv?.enhanced_mode === 'boolean' ? adv.enhanced_mode : true,
        mode: typeof adv?.mode === 'string' ? adv.mode : 'linear',
      },
    }
  } catch {
    return null
  }
}

/** 持久化用户偏好（仅非敏感字段；localStorage 不可用时静默忽略） */
export function persistPreferenceData(userId: string, pref: SmartGenPreference): void {
  try {
    localStorage.setItem(buildPrefKey(userId, 'pref'), JSON.stringify(pref))
  } catch {
    // 配额超限或隐私模式：忽略，不影响主流程
  }
}

/**
 * 优先透出后端真实原因：error.response.data.detail → error.message → 兜底文案。
 * detail 为字符串直接用；为数组（FastAPI 422）拼接每项 msg；兜底才用通用文案。
 */
export function extractErrorDetail(e: unknown, fallback: string): string {
  if (!e) return fallback
  const err = e as {
    response?: { data?: { detail?: unknown; message?: string } }
    message?: string
  }
  const detail = err.response?.data?.detail
  if (typeof detail === 'string' && detail.trim() !== '') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((d) => {
        if (typeof d === 'string') return d
        if (d != null && typeof d === 'object' && 'msg' in d) {
          const msg = (d as { msg?: unknown }).msg
          return typeof msg === 'string' ? msg : String(d)
        }
        return String(d)
      })
      .filter((s) => s.length > 0)
    if (parts.length > 0) return parts.join('; ')
  }
  const respMsg = err.response?.data?.message
  if (typeof respMsg === 'string' && respMsg.trim() !== '') return respMsg
  if (typeof err.message === 'string' && err.message.trim() !== '') return err.message
  return fallback
}

/** 判断是否为用户主动中断（AbortController.abort 触发） */
export function isAbortError(e: unknown): boolean {
  if (!e) return false
  const err = e as { name?: string; code?: number | string }
  return err.name === 'AbortError' || err.code === 20 || err.code === 'ERR_ABORTED'
}

/**
 * 计算生成进度百分比。
 * 总数未知（<=0 或非有限数）返回 null，由调用方降级为 indeterminate。
 * 流式中上限 99，仅完成时返回 100，避免提前显示满格。
 */
export function computeProgressPercent(done: number, total: number): number | null {
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(done) || done < 0) return null
  if (done >= total) return 100
  return Math.min(99, Math.round((done / total) * 100))
}
