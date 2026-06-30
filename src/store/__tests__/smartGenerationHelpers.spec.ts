import { describe, it, expect, beforeEach } from 'vitest'
import {
  buildPrefKey,
  computeProgressPercent,
  extractErrorDetail,
  isAbortError,
  persistPreferenceData,
  readUserId,
  restorePreferenceData,
} from '../smartGenerationHelpers'

/** 构造一个简易 JWT（header.payload.signature），payload 由 JSON 指定 */
function makeJwt(payload: Record<string, unknown>): string {
  const b64 = (obj: unknown) =>
    btoa(JSON.stringify(obj)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
  return `${b64({ alg: 'HS256' })}.${b64(payload)}.sig`
}

describe('readUserId', () => {
  beforeEach(() => localStorage.clear())

  it('无 token 时回退 default', () => {
    expect(readUserId()).toBe('default')
  })

  it('从 JWT sub 解析用户 ID', () => {
    localStorage.setItem('token', makeJwt({ sub: 42 }))
    expect(readUserId()).toBe('42')
  })

  it('sub 缺失时回退 user_id / userId / id', () => {
    localStorage.setItem('token', makeJwt({ user_id: 7 }))
    expect(readUserId()).toBe('7')
    localStorage.setItem('token', makeJwt({ userId: 'u9' }))
    expect(readUserId()).toBe('u9')
    localStorage.setItem('token', makeJwt({ id: 100 }))
    expect(readUserId()).toBe('100')
  })

  it('非法 token 回退 default（异常边界）', () => {
    localStorage.setItem('token', 'not.a.valid')
    expect(readUserId()).toBe('default')
    localStorage.setItem('token', 'singlepart')
    expect(readUserId()).toBe('default')
  })
})

describe('buildPrefKey', () => {
  it('生成 smart-gen:{userId}:{field} 形式 key', () => {
    expect(buildPrefKey('42', 'pref')).toBe('smart-gen:42:pref')
  })
})

describe('restorePreferenceData / persistPreferenceData', () => {
  beforeEach(() => localStorage.clear())

  it('无记录返回 null（空值边界）', () => {
    expect(restorePreferenceData('42')).toBeNull()
  })

  it('持久化后可恢复全部非敏感字段', () => {
    persistPreferenceData('42', {
      selectedProjectId: 5,
      selectedTask: 'history_update',
      advancedConfig: {
        case_type: 'api',
        exec_mode: 'auto',
        enhanced_mode: false,
        mode: 'graph',
      },
    })
    const restored = restorePreferenceData('42')
    expect(restored).not.toBeNull()
    expect(restored?.selectedProjectId).toBe(5)
    expect(restored?.selectedTask).toBe('history_update')
    expect(restored?.advancedConfig).toEqual({
      case_type: 'api',
      exec_mode: 'auto',
      enhanced_mode: false,
      mode: 'graph',
    })
  })

  it('按 userId 隔离：不同用户互不干扰', () => {
    persistPreferenceData('1', {
      selectedProjectId: 10,
      selectedTask: 'new_feature',
      advancedConfig: {
        case_type: 'manual',
        exec_mode: 'manual',
        enhanced_mode: true,
        mode: 'linear',
      },
    })
    persistPreferenceData('2', {
      selectedProjectId: 20,
      selectedTask: 'import_asset',
      advancedConfig: { case_type: 'api', exec_mode: 'auto', enhanced_mode: false, mode: 'graph' },
    })
    expect(restorePreferenceData('1')?.selectedProjectId).toBe(10)
    expect(restorePreferenceData('2')?.selectedProjectId).toBe(20)
    expect(restorePreferenceData('3')).toBeNull()
  })

  it('损坏 JSON 返回 null（异常边界）', () => {
    localStorage.setItem('smart-gen:42:pref', '{not json')
    expect(restorePreferenceData('42')).toBeNull()
  })

  it('字段缺失时使用安全默认值（边界兼容）', () => {
    localStorage.setItem('smart-gen:42:pref', JSON.stringify({ selectedProjectId: 5 }))
    const restored = restorePreferenceData('42')
    expect(restored?.selectedTask).toBe('new_feature')
    expect(restored?.advancedConfig.mode).toBe('linear')
    expect(restored?.advancedConfig.enhanced_mode).toBe(true)
  })

  it('不持久化敏感字段：存储内容不含 token', () => {
    persistPreferenceData('42', {
      selectedProjectId: 5,
      selectedTask: 'new_feature',
      advancedConfig: {
        case_type: 'manual',
        exec_mode: 'manual',
        enhanced_mode: true,
        mode: 'linear',
      },
    })
    const raw = localStorage.getItem('smart-gen:42:pref') || ''
    expect(raw).not.toContain('token')
    expect(raw).not.toContain('password')
  })
})

describe('extractErrorDetail', () => {
  it('优先返回 response.data.detail 字符串', () => {
    const e = { response: { data: { detail: 'test_points 字段不能为空' } } }
    expect(extractErrorDetail(e, '资料识别失败')).toBe('test_points 字段不能为空')
  })

  it('detail 为数组（FastAPI 422）拼接每项 msg', () => {
    const e = { response: { data: { detail: [{ msg: '字段必填' }, { msg: '类型错误' }] } } }
    expect(extractErrorDetail(e, '失败')).toBe('字段必填; 类型错误')
  })

  it('无 detail 时回退 response.data.message', () => {
    const e = { response: { data: { message: '服务异常' } } }
    expect(extractErrorDetail(e, '失败')).toBe('服务异常')
  })

  it('无 response 时回退 error.message', () => {
    expect(extractErrorDetail(new Error('网络错误'), '失败')).toBe('网络错误')
  })

  it('空字符串 detail 不采用，继续回退', () => {
    const e = { response: { data: { detail: '  ' } }, message: '真实原因' }
    expect(extractErrorDetail(e, '失败')).toBe('真实原因')
  })

  it('全部缺失时使用兜底文案', () => {
    expect(extractErrorDetail(null, '资料识别失败')).toBe('资料识别失败')
    expect(extractErrorDetail({}, '生成失败')).toBe('生成失败')
  })
})

describe('isAbortError', () => {
  it('识别 name=AbortError', () => {
    expect(isAbortError(Object.assign(new Error('x'), { name: 'AbortError' }))).toBe(true)
  })

  it('识别 code=20 / ERR_ABORTED', () => {
    expect(isAbortError({ code: 20 })).toBe(true)
    expect(isAbortError({ code: 'ERR_ABORTED' })).toBe(true)
  })

  it('普通错误返回 false', () => {
    expect(isAbortError(new Error('生成失败'))).toBe(false)
    expect(isAbortError(null)).toBe(false)
  })
})

describe('computeProgressPercent', () => {
  it('正常计算并向下取整', () => {
    expect(computeProgressPercent(5, 10)).toBe(50)
    expect(computeProgressPercent(1, 3)).toBe(33)
  })

  it('完成时返回 100', () => {
    expect(computeProgressPercent(10, 10)).toBe(100)
    expect(computeProgressPercent(11, 10)).toBe(100)
  })

  it('流式中上限 99（避免提前满格）', () => {
    expect(computeProgressPercent(9, 10)).toBe(90)
    expect(computeProgressPercent(99, 100)).toBe(99)
  })

  it('总数未知返回 null（indeterminate 边界）', () => {
    expect(computeProgressPercent(5, 0)).toBeNull()
    expect(computeProgressPercent(5, -1)).toBeNull()
    expect(computeProgressPercent(5, NaN)).toBeNull()
  })

  it('负已完成数返回 null', () => {
    expect(computeProgressPercent(-1, 10)).toBeNull()
  })
})
