import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useWebSocket } from '../useWebSocket'

class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  url: string
  protocols?: string | string[]
  readyState = FakeWebSocket.OPEN
  sent: unknown[] = []
  closedWith: { code?: number; reason?: string } | null = null
  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  onclose: (() => void) | null = null

  constructor(url: string, protocols?: string | string[]) {
    this.url = url
    this.protocols = protocols
    FakeWebSocket.instances.push(this)
  }

  send(data: unknown) {
    this.sent.push(data)
  }

  close(code?: number, reason?: string) {
    this.closedWith = { code, reason }
    this.readyState = FakeWebSocket.CLOSED
  }
}

function mountApi() {
  let api!: ReturnType<typeof useWebSocket>
  const Comp = defineComponent({
    setup() {
      api = useWebSocket()
      return () => h('div')
    },
  })
  const wrapper = mount(Comp)
  return { api, wrapper }
}

describe('useWebSocket — 连接生命周期', () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  it('connect 建立连接并在 onopen/onclose 间同步 isConnected', () => {
    const { api } = mountApi()

    api.connect('ws://test/echo')
    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].url).toBe('ws://test/echo')
    expect(FakeWebSocket.instances[0].protocols).toBeUndefined()
    expect(api.isConnected.value).toBe(false)

    FakeWebSocket.instances[0].onopen?.()
    expect(api.isConnected.value).toBe(true)

    FakeWebSocket.instances[0].onclose?.()
    expect(api.isConnected.value).toBe(false)
  })

  it('connect 支持子协议参数', () => {
    const { api } = mountApi()

    api.connect('ws://test/echo', ['a', 'b'])

    expect(FakeWebSocket.instances[0].protocols).toEqual(['a', 'b'])
  })

  it('重复 connect 会先关闭旧连接', () => {
    const { api } = mountApi()

    api.connect('ws://test/one')
    api.connect('ws://test/two')

    expect(FakeWebSocket.instances).toHaveLength(2)
    expect(FakeWebSocket.instances[0].closedWith).not.toBeNull()
    expect(FakeWebSocket.instances[1].closedWith).toBeNull()
  })

  it('disconnect 透传 code/reason 并复位连接状态', () => {
    const { api } = mountApi()
    api.connect('ws://test/echo')
    FakeWebSocket.instances[0].onopen?.()

    api.disconnect(1000, 'bye')

    expect(FakeWebSocket.instances[0].closedWith).toEqual({ code: 1000, reason: 'bye' })
    expect(api.isConnected.value).toBe(false)
  })

  it('未连接时 disconnect 不报错', () => {
    const { api } = mountApi()

    expect(() => api.disconnect()).not.toThrow()
    expect(api.isConnected.value).toBe(false)
  })

  it('组件卸载时自动断开', () => {
    const { api, wrapper } = mountApi()
    api.connect('ws://test/echo')

    wrapper.unmount()

    expect(FakeWebSocket.instances[0].closedWith).not.toBeNull()
  })
})

describe('useWebSocket — 收发与订阅', () => {
  beforeEach(() => {
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  it('连接打开时 send 透传数据', () => {
    const { api } = mountApi()
    api.connect('ws://test/echo')

    api.send('payload')

    expect(FakeWebSocket.instances[0].sent).toEqual(['payload'])
  })

  it('连接未打开时 send 丢弃数据', () => {
    const { api } = mountApi()
    api.connect('ws://test/echo')
    FakeWebSocket.instances[0].readyState = FakeWebSocket.CONNECTING

    api.send('payload')

    expect(FakeWebSocket.instances[0].sent).toEqual([])
  })

  it('onMessage 分发消息，返回函数取消订阅', () => {
    const { api } = mountApi()
    const handler = vi.fn()
    const off = api.onMessage(handler)
    api.connect('ws://test/echo')

    const event = { data: 'hi' } as MessageEvent
    FakeWebSocket.instances[0].onmessage?.(event)
    expect(handler).toHaveBeenCalledWith(event)

    off()
    FakeWebSocket.instances[0].onmessage?.(event)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('单个处理器抛错不影响其他处理器', () => {
    const { api } = mountApi()
    const bad = vi.fn(() => {
      throw new Error('boom')
    })
    const good = vi.fn()
    api.onMessage(bad)
    api.onMessage(good)
    api.connect('ws://test/echo')

    FakeWebSocket.instances[0].onmessage?.({ data: 'x' } as MessageEvent)

    expect(good).toHaveBeenCalledTimes(1)
    expect(console.error).toHaveBeenCalled()
  })

  it('onError 分发错误事件，返回函数取消订阅', () => {
    const { api } = mountApi()
    const handler = vi.fn()
    const off = api.onError(handler)
    api.connect('ws://test/echo')

    const event = new Event('error')
    FakeWebSocket.instances[0].onerror?.(event)
    expect(handler).toHaveBeenCalledWith(event)

    off()
    FakeWebSocket.instances[0].onerror?.(event)
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('错误处理器抛错被吞并记录日志', () => {
    const { api } = mountApi()
    api.onError(() => {
      throw new Error('boom')
    })
    api.connect('ws://test/echo')

    expect(() => FakeWebSocket.instances[0].onerror?.(new Event('error'))).not.toThrow()
    expect(console.error).toHaveBeenCalled()
  })
})
