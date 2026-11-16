import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { App } from 'vue'

const mocks = vi.hoisted(() => ({
  elMessageError: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: mocks.elMessageError },
}))

import { setupGlobalErrorHandler } from '../globalErrorHandler'

function createApp() {
  return { config: {} } as unknown as App
}

/** 等待动态 import('element-plus') 的微任务链完成 */
function flushDynamicImport() {
  return new Promise((resolve) => setTimeout(resolve, 0))
}

/** 统计某条消息被提示的次数 */
function countFor(message: string) {
  return mocks.elMessageError.mock.calls.filter((call) => call[0] === message).length
}

/**
 * 挂载处理并取回 window 监听器
 *
 * happy-dom 的 dispatchEvent 在 window 上不保证 event.target === window，
 * 因此直接取出注册的回调进行调用，专注验证处理逻辑本身。
 */
function mountWithListeners() {
  const app = createApp()
  const addEventListener = vi.spyOn(window, 'addEventListener')
  setupGlobalErrorHandler(app)
  const listenerFor = (type: string) => {
    const call = addEventListener.mock.calls.find((item) => item[0] === type)
    return call?.[1] as (event: unknown) => void
  }
  return {
    app,
    errorListener: () => listenerFor('error'),
    rejectionListener: () => listenerFor('unhandledrejection'),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('setupGlobalErrorHandler — 注册', () => {
  it('挂载 Vue 错误处理器与 window 监听', () => {
    const app = createApp()
    const addEventListener = vi.spyOn(window, 'addEventListener')

    setupGlobalErrorHandler(app)

    expect(typeof app.config.errorHandler).toBe('function')
    expect(addEventListener).toHaveBeenCalledWith('error', expect.any(Function))
    expect(addEventListener).toHaveBeenCalledWith('unhandledrejection', expect.any(Function))
    addEventListener.mockRestore()
  })
})

describe('setupGlobalErrorHandler — Vue 错误', () => {
  it('提示错误消息并输出开发日志', async () => {
    const app = createApp()
    setupGlobalErrorHandler(app)

    app.config.errorHandler!(new Error('组件崩溃'), null, 'render function')

    await flushDynamicImport()

    expect(countFor('组件崩溃')).toBe(1)
    expect(console.error).toHaveBeenCalled()
  })

  it('缺少 message 时使用默认文案', async () => {
    const app = createApp()
    setupGlobalErrorHandler(app)

    app.config.errorHandler!({} as Error, null, 'setup')

    await flushDynamicImport()

    expect(countFor('页面渲染异常，请刷新页面重试')).toBe(1)
  })

  it('同一消息在去重窗口内只提示一次', async () => {
    const app = createApp()
    setupGlobalErrorHandler(app)
    const message = '重复错误-dedup'

    app.config.errorHandler!(new Error(message), null, 'render')
    app.config.errorHandler!(new Error(message), null, 'render')

    await flushDynamicImport()

    expect(countFor(message)).toBe(1)
  })
})

describe('setupGlobalErrorHandler — window error', () => {
  it('脚本级错误会被提示', async () => {
    const { errorListener } = mountWithListeners()

    errorListener()({ target: window, message: '脚本崩了' })

    await flushDynamicImport()

    expect(countFor('脚本崩了')).toBe(1)
  })

  it('缺少 message 时使用默认文案', async () => {
    const { errorListener } = mountWithListeners()

    errorListener()({ target: window })

    await flushDynamicImport()

    expect(countFor('未知脚本错误')).toBe(1)
  })

  it('资源加载错误被忽略', async () => {
    const { errorListener } = mountWithListeners()

    errorListener()({ target: document.createElement('img'), message: '' })

    await flushDynamicImport()

    expect(mocks.elMessageError).not.toHaveBeenCalled()
  })
})

describe('setupGlobalErrorHandler — unhandledrejection', () => {
  it('Error 类型 reason 使用其 message', async () => {
    const { rejectionListener } = mountWithListeners()

    rejectionListener()({ reason: new Error('异步挂了') })

    await flushDynamicImport()

    expect(countFor('异步挂了')).toBe(1)
  })

  it('字符串 reason 直接作为消息', async () => {
    const { rejectionListener } = mountWithListeners()

    rejectionListener()({ reason: '字符串原因' })

    await flushDynamicImport()

    expect(countFor('字符串原因')).toBe(1)
  })

  it('其他类型 reason 使用默认文案', async () => {
    const { rejectionListener } = mountWithListeners()

    rejectionListener()({ reason: { code: 500 } })

    await flushDynamicImport()

    expect(countFor('异步操作异常')).toBe(1)
  })
})
