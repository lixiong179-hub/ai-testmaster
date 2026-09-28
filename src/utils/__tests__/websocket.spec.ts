/**
 * WebSocket 断线重连提示单元测试
 *
 * 覆盖范围：
 * 1. WebSocketClient（单例）：断线 warning、重连成功 success、3 次失败 error、手动 disconnect 静默
 * 2. connectWebSocket（函数式 API）：断线 warning、重连成功 success、3 次失败 error、手动 close 静默
 *
 * 说明：单元测试无真实 WS 服务，按任务要求 mock WebSocket 构造函数与 ElMessage。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ElMessage } from 'element-plus'
import { wsClient, connectWebSocket } from '../websocket'

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}))

const messageSpy = vi.mocked(ElMessage)

// WebSocket readyState 常量
const WS_CONNECTING = 0
const WS_OPEN = 1
const WS_CLOSING = 2
const WS_CLOSED = 3

interface MockWebSocketInstance {
  url: string
  onopen: (() => void) | null
  onclose: (() => void) | null
  onmessage: ((event: { data: unknown }) => void) | null
  onerror: ((event: unknown) => void) | null
  readyState: number
  close: () => void
  send: (data: string) => void
}

interface MockWebSocketCtor {
  new (url: string): MockWebSocketInstance
  OPEN: number
  CONNECTING: number
  CLOSING: number
  CLOSED: number
}

/**
 * 创建 mock WebSocket 构造函数，将所有创建的实例推入传入的 instances 数组。
 * 实例的 close() 仅切换 readyState，不自动触发 onclose（由测试显式触发）。
 */
function createMockWebSocket(instances: MockWebSocketInstance[]): MockWebSocketCtor {
  const ctor = function (url: string): MockWebSocketInstance {
    const instance: MockWebSocketInstance = {
      url,
      onopen: null,
      onclose: null,
      onmessage: null,
      onerror: null,
      readyState: WS_OPEN,
      close: () => {
        instance.readyState = WS_CLOSED
      },
      send: () => {},
    }
    instances.push(instance)
    return instance
  } as unknown as MockWebSocketCtor
  ctor.OPEN = WS_OPEN
  ctor.CONNECTING = WS_CONNECTING
  ctor.CLOSING = WS_CLOSING
  ctor.CLOSED = WS_CLOSED
  return ctor
}

describe('WebSocket 断线重连提示', () => {
  let instances: MockWebSocketInstance[]

  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    localStorage.setItem('token', 'test-token')
    instances = []
    const mockCtor = createMockWebSocket(instances)
    vi.stubGlobal('WebSocket', mockCtor)
  })

  afterEach(() => {
    wsClient.disconnect(true)
    vi.unstubAllGlobals()
    localStorage.clear()
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  /** 获取最新创建的 mock 实例 */
  function latestWs(): MockWebSocketInstance {
    const ws = instances[instances.length - 1]
    if (!ws) throw new Error('未创建 WebSocket 实例')
    return ws
  }

  describe('WebSocketClient（单例）', () => {
    it('连接断开时弹出 warning 提示正在重连', () => {
      wsClient.connect(1, 1, 'test-token')
      latestWs().onclose?.()

      expect(messageSpy.warning).toHaveBeenCalledWith('连接已断开，正在重连...')
    })

    it('首次连接成功不弹出 success 提示', () => {
      wsClient.connect(1, 1, 'test-token')
      latestWs().onopen?.()

      expect(messageSpy.success).not.toHaveBeenCalled()
    })

    it('重连成功后弹出 success 提示已恢复', () => {
      wsClient.connect(1, 1, 'test-token')
      latestWs().onclose?.() // 断线 → warning，重连计数 0→1

      vi.advanceTimersByTime(1000) // 触发第 1 次重连 → 新 ws
      latestWs().onopen?.() // 重连成功

      expect(messageSpy.success).toHaveBeenCalledWith('连接已恢复')
    })

    it('重连 3 次仍失败后弹出 error 提示刷新页面', () => {
      wsClient.connect(1, 1, 'test-token')

      // 初始断开：warning，计数 0→1，定时器 1s
      latestWs().onclose?.()
      expect(messageSpy.warning).toHaveBeenCalledTimes(1)

      // 第 1 次重连失败：计数 1→2，定时器 2s
      vi.advanceTimersByTime(1000)
      latestWs().onclose?.()

      // 第 2 次重连失败：计数 2→3，定时器 4s
      vi.advanceTimersByTime(2000)
      latestWs().onclose?.()

      // 第 3 次重连失败：计数 3→4 > 3 → error
      vi.advanceTimersByTime(4000)
      latestWs().onclose?.()

      expect(messageSpy.error).toHaveBeenCalledWith('连接失败，请刷新页面重试')
      // 全程仅首次断线提示一次 warning
      expect(messageSpy.warning).toHaveBeenCalledTimes(1)
    })

    it('重连 3 次失败后不再继续重连', () => {
      wsClient.connect(1, 1, 'test-token')
      latestWs().onclose?.()
      vi.advanceTimersByTime(1000)
      latestWs().onclose?.()
      vi.advanceTimersByTime(2000)
      latestWs().onclose?.()
      vi.advanceTimersByTime(4000)
      latestWs().onclose?.() // 触发 error，计数复位

      const countBefore = instances.length
      vi.advanceTimersByTime(30000)
      // 不应再创建新连接
      expect(instances.length).toBe(countBefore)
    })

    it('手动 disconnect 不触发 ElMessage 提示与重连', () => {
      wsClient.connect(1, 1, 'test-token')
      const ws = latestWs()
      wsClient.disconnect(true)
      // 模拟 close() 引发的 onclose 回调
      ws.onclose?.()

      expect(messageSpy.warning).not.toHaveBeenCalled()
      expect(messageSpy.error).not.toHaveBeenCalled()

      vi.advanceTimersByTime(30000)
      expect(messageSpy.warning).not.toHaveBeenCalled()
      expect(messageSpy.error).not.toHaveBeenCalled()
    })
  })

  describe('connectWebSocket（函数式 API）', () => {
    it('连接断开时弹出 warning 提示正在重连', () => {
      const conn = connectWebSocket('/test')
      latestWs().onclose?.()

      expect(messageSpy.warning).toHaveBeenCalledWith('连接已断开，正在重连...')
      conn.close()
    })

    it('重连成功后弹出 success 提示已恢复', () => {
      const conn = connectWebSocket('/test')
      latestWs().onclose?.() // 断线 → warning，计数 0→1

      vi.advanceTimersByTime(1000) // 触发重连 → 新 ws
      latestWs().onopen?.() // 重连成功

      expect(messageSpy.success).toHaveBeenCalledWith('连接已恢复')
      conn.close()
    })

    it('重连 3 次仍失败后弹出 error 提示刷新页面', () => {
      const conn = connectWebSocket('/test')

      latestWs().onclose?.() // 计数 0→1
      vi.advanceTimersByTime(1000)
      latestWs().onclose?.() // 计数 1→2
      vi.advanceTimersByTime(2000)
      latestWs().onclose?.() // 计数 2→3
      vi.advanceTimersByTime(4000)
      latestWs().onclose?.() // 计数 3→4 > 3 → error

      expect(messageSpy.error).toHaveBeenCalledWith('连接失败，请刷新页面重试')
      expect(messageSpy.warning).toHaveBeenCalledTimes(1)
      conn.close()
    })

    it('手动 close 不触发 ElMessage 提示与重连', () => {
      const conn = connectWebSocket('/test')
      const ws = latestWs()
      conn.close()
      // 模拟 close() 引发的 onclose 回调
      ws.onclose?.()

      expect(messageSpy.warning).not.toHaveBeenCalled()
      expect(messageSpy.error).not.toHaveBeenCalled()
    })
  })
})
