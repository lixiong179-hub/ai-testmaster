import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

/**
 * Task A-03：401 未授权响应提示优化测试
 *
 * 通过 mock 捕获 axios 响应拦截器的 rejected 回调，手动触发 401 错误，
 * 验证 handleUnauthorized 的副作用（ElMessage.warning + 延迟 router.push）。
 *
 * 使用 vi.hoisted 保证 mock 工厂引用的对象在 vi.mock 提升后仍稳定。
 */
const mocks = vi.hoisted(() => {
  const ElMessage = {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }
  const routerPush = vi.fn()
  const routerCurrentRoute: { value: { path: string; fullPath: string } } = {
    value: { path: '/home/workbench', fullPath: '/home/workbench' },
  }
  type InterceptorFn = ((arg: unknown) => unknown) | null
  const interceptorStore: { fulfilled: InterceptorFn; rejected: InterceptorFn } = {
    fulfilled: null,
    rejected: null,
  }
  return { ElMessage, routerPush, routerCurrentRoute, interceptorStore }
})

vi.mock('element-plus', () => ({ ElMessage: mocks.ElMessage }))

vi.mock('@/router', () => ({
  default: {
    currentRoute: mocks.routerCurrentRoute,
    push: mocks.routerPush,
  },
}))

vi.mock('axios', () => {
  const mockService = {
    interceptors: {
      request: { use: vi.fn() },
      response: {
        // 捕获 request.ts 注册的响应拦截器，便于测试手动触发
        use: (
          fulfilled: (arg: unknown) => unknown,
          rejected: (arg: unknown) => unknown
        ) => {
          mocks.interceptorStore.fulfilled = fulfilled
          mocks.interceptorStore.rejected = rejected
        },
      },
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  }
  return {
    default: {
      create: () => mockService,
      // 刷新接口返回空数据 → newToken 为 null → 触发 handleUnauthorized
      post: vi.fn().mockResolvedValue({ data: {} }),
    },
  }
})

// 在 mock 注册后导入被测模块，触发拦截器注册
import '../request'

/** 构造 401 错误对象（非 auth 端点，进入刷新失败分支） */
function build401Error(url: string): unknown {
  return { response: { status: 401 }, config: { url } }
}

/** 调用捕获到的 rejected 拦截器，等待刷新失败后触发 handleUnauthorized */
async function trigger401(url: string): Promise<void> {
  const rejected = mocks.interceptorStore.rejected
  if (!rejected) {
    throw new Error('响应拦截器 rejected 回调未捕获')
  }
  try {
    await rejected(build401Error(url))
  } catch {
    // 拦截器在 401 后会 reject buildError，属预期行为，这里仅触发副作用
  }
}

describe('Task A-03: 401 未授权响应提示优化', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
    localStorage.setItem('token', 'fake-token')
    localStorage.setItem('refresh_token', 'fake-refresh')
    mocks.ElMessage.warning.mockClear()
    mocks.routerPush.mockClear()
    mocks.routerPush.mockResolvedValue(undefined)
    mocks.routerCurrentRoute.value = {
      path: '/home/workbench',
      fullPath: '/home/workbench',
    }
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('非登录页 401：弹出 ElMessage.warning 且文本为"登录已过期，请重新登录"', async () => {
    await trigger401('/api/v1/projects')

    expect(mocks.ElMessage.warning).toHaveBeenCalledWith('登录已过期，请重新登录')
    expect(mocks.ElMessage.warning).toHaveBeenCalledTimes(1)
  })

  it('提示显示 1500ms 后才调用 router.push 跳转登录页', async () => {
    await trigger401('/api/v1/projects')

    // 1500ms 前不应跳转（用户需看到提示）
    vi.advanceTimersByTime(1499)
    expect(mocks.routerPush).not.toHaveBeenCalled()

    // 推进到 1500ms 触发跳转
    vi.advanceTimersByTime(1)
    expect(mocks.routerPush).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/home/workbench' },
    })
    expect(mocks.routerPush).toHaveBeenCalledTimes(1)
  })

  it('登录页自身 401 不弹提示也不跳转（避免干扰用户输入）', async () => {
    mocks.routerCurrentRoute.value = { path: '/login', fullPath: '/login' }
    await trigger401('/api/v1/projects')

    vi.advanceTimersByTime(1500)
    expect(mocks.ElMessage.warning).not.toHaveBeenCalled()
    expect(mocks.routerPush).not.toHaveBeenCalled()
  })

  it('当前路径为根路径 "/" 时，跳转不带 redirect 参数', async () => {
    mocks.routerCurrentRoute.value = { path: '/', fullPath: '/' }
    await trigger401('/api/v1/projects')

    vi.advanceTimersByTime(1500)
    expect(mocks.routerPush).toHaveBeenCalledWith({
      path: '/login',
      query: undefined,
    })
  })

  it('触发 401 后清理本地凭据（token/refresh_token/userInfo）', async () => {
    await trigger401('/api/v1/projects')

    expect(localStorage.getItem('token')).toBeNull()
    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem('userInfo')).toBeNull()
  })
})
