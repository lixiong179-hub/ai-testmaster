import { describe, it, expect, vi } from 'vitest'
import { emitAuthEvent, onAuthEvent } from '../authEventBus'

describe('authEventBus — 订阅与触发', () => {
  it('触发事件时通知所有订阅者', () => {
    const first = vi.fn()
    const second = vi.fn()
    onAuthEvent('auth:unauthorized', first)
    onAuthEvent('auth:unauthorized', second)

    emitAuthEvent('auth:unauthorized')

    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('返回的取消订阅函数生效', () => {
    const handler = vi.fn()
    const off = onAuthEvent('auth:unauthorized', handler)

    off()
    emitAuthEvent('auth:unauthorized')

    expect(handler).not.toHaveBeenCalled()
  })

  it('重复取消订阅不抛错', () => {
    const handler = vi.fn()
    const off = onAuthEvent('auth:unauthorized', handler)

    off()
    expect(() => off()).not.toThrow()
  })

  it('同一处理器只注册一次', () => {
    const handler = vi.fn()
    onAuthEvent('auth:unauthorized', handler)
    onAuthEvent('auth:unauthorized', handler)

    emitAuthEvent('auth:unauthorized')

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('无订阅者时触发是空操作', () => {
    expect(() => emitAuthEvent('auth:unauthorized')).not.toThrow()
  })

  it('单个处理器抛错不影响其他订阅者', () => {
    const broken = vi.fn(() => {
      throw new Error('boom')
    })
    const normal = vi.fn()
    onAuthEvent('auth:unauthorized', broken)
    onAuthEvent('auth:unauthorized', normal)

    emitAuthEvent('auth:unauthorized')

    expect(broken).toHaveBeenCalled()
    expect(normal).toHaveBeenCalledTimes(1)
  })
})
