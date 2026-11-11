import { describe, it, expect, beforeEach, vi } from 'vitest'

const { mockHasPermission, mockCreateRouter } = vi.hoisted(() => ({
  mockHasPermission: vi.fn(),
  mockCreateRouter: vi.fn(),
}))

vi.mock('vue-router', () => ({
  createRouter: mockCreateRouter,
  createWebHistory: vi.fn(() => ({})),
}))
vi.mock('@/directives/permission', () => ({ hasPermission: mockHasPermission }))
vi.mock('../routes', () => ({ routes: [] }))

type Next = (to?: string) => void
type Guard = (to: unknown, from: unknown, next: Next) => void

let guard: Guard

function makeTo(meta: Record<string, unknown>) {
  return { meta, path: '/home/project' }
}

/** 构造三段式 JWT；expOffsetSec 为负表示已过期 */
function makeToken(expOffsetSec: number): string {
  const encode = (value: Record<string, unknown>) => btoa(JSON.stringify(value)).replace(/=+$/, '')
  return [
    encode({ alg: 'HS256', typ: 'JWT' }),
    encode({ exp: Math.floor(Date.now() / 1000) + expOffsetSec }),
    'signature',
  ].join('.')
}

async function loadGuard(): Promise<void> {
  vi.resetModules()
  mockCreateRouter.mockImplementation(() => ({
    beforeEach: (fn: Guard) => {
      guard = fn
    },
  }))
  await import('../index')
}

describe('router 全局前置守卫', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    localStorage.clear()
    mockHasPermission.mockReturnValue(true)
    await loadGuard()
  })

  it('注册守卫并写入「页面标题 - 平台名」', () => {
    expect(typeof guard).toBe('function')

    const next = vi.fn()
    guard(makeTo({ title: '任务详情' }), {}, next)

    expect(document.title).toBe('任务详情 - AI自动化测试平台')
    expect(next).toHaveBeenCalledWith()
  })

  it('标题缺省时回退平台名', () => {
    guard(makeTo({}), {}, vi.fn())

    expect(document.title).toBe('AI TestMaster - AI自动化测试平台')
  })

  it('公开路由直接放行，不校验 token', () => {
    const next = vi.fn()
    guard(makeTo({ requireAuth: false }), {}, next)

    expect(next).toHaveBeenCalledWith()
    expect(mockHasPermission).not.toHaveBeenCalled()
  })

  it('需要登录但无 token：清理残留登录态并跳转 /login', () => {
    localStorage.setItem('token', '')
    localStorage.setItem('userInfo', '{"id":1}')
    const next = vi.fn()

    guard(makeTo({ requireAuth: true }), {}, next)

    expect(next).toHaveBeenCalledWith('/login')
    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('userInfo')).toBeNull()
  })

  it('token 已过期：视为未登录并跳转 /login', () => {
    localStorage.setItem('token', makeToken(-60))
    const next = vi.fn()

    guard(makeTo({ requireAuth: true }), {}, next)

    expect(next).toHaveBeenCalledWith('/login')
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('token 格式非法（非三段）：按过期处理', () => {
    localStorage.setItem('token', 'not-a-jwt')
    const next = vi.fn()

    guard(makeTo({ requireAuth: true }), {}, next)

    expect(next).toHaveBeenCalledWith('/login')
  })

  it('token 有效且无权限要求：放行', () => {
    localStorage.setItem('token', makeToken(3600))
    const next = vi.fn()

    guard(makeTo({ requireAuth: true }), {}, next)

    expect(next).toHaveBeenCalledWith()
    expect(localStorage.getItem('token')).not.toBeNull()
  })

  it('token 有效但权限不足：跳转 /home/project', () => {
    localStorage.setItem('token', makeToken(3600))
    mockHasPermission.mockReturnValue(false)
    const next = vi.fn()

    guard(makeTo({ requireAuth: true, permission: 'task:delete' }), {}, next)

    expect(mockHasPermission).toHaveBeenCalledWith('task:delete')
    expect(next).toHaveBeenCalledWith('/home/project')
  })

  it('token 有效且权限通过：放行', () => {
    localStorage.setItem('token', makeToken(3600))
    mockHasPermission.mockReturnValue(true)
    const next = vi.fn()

    guard(makeTo({ requireAuth: true, permission: 'task:view' }), {}, next)

    expect(next).toHaveBeenCalledWith()
  })
})
