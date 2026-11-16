import { describe, it, expect, beforeEach, vi } from 'vitest'
import { defineComponent, h, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'

vi.mock('@/utils/websocket', () => ({
  connectWebSocket: vi.fn(),
  disconnectWebSocket: vi.fn(),
}))

import { connectWebSocket, disconnectWebSocket, type WebSocketConnection } from '@/utils/websocket'
import { useExecutionWebSocket } from '../useExecutionWebSocket'

const connectMock = vi.mocked(connectWebSocket)
const disconnectMock = vi.mocked(disconnectWebSocket)

type Handlers = {
  onMessage: (data: unknown) => void
  onError: (error: unknown) => void
}

function setup(taskId = 42) {
  const executionSteps = ref<Record<string, unknown>[]>([{ id: 's1' }])
  const currentStepIndex = ref(0)
  const executionLogs = ref<Record<string, unknown>[]>([])
  const executionStatus = ref<Record<string, unknown> | null>({ status: 'running' })
  const loadStepScreenshot = vi.fn().mockResolvedValue(undefined)
  const scrollToBottom = vi.fn()

  let api!: ReturnType<typeof useExecutionWebSocket>
  const Comp = defineComponent({
    setup() {
      api = useExecutionWebSocket({
        taskId: () => taskId,
        executionSteps,
        currentStepIndex,
        executionLogs,
        executionStatus,
        loadStepScreenshot,
        scrollToBottom,
      })
      return () => h('div')
    },
  })
  const wrapper = mount(Comp)

  return {
    api,
    wrapper,
    executionSteps,
    currentStepIndex,
    executionLogs,
    executionStatus,
    loadStepScreenshot,
    scrollToBottom,
  }
}

function firstHandlers(): Handlers {
  return connectMock.mock.calls[0][1] as unknown as Handlers
}

describe('useExecutionWebSocket — 连接管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    connectMock.mockReturnValue({
      ws: {} as WebSocket,
      close: vi.fn(),
    } as WebSocketConnection)
  })

  it('按任务ID连接 /ws/execution/{taskId}', () => {
    const ctx = setup(77)

    ctx.api.connectWebSocketForRealtimeUpdate()

    expect(connectMock).toHaveBeenCalledTimes(1)
    expect(connectMock.mock.calls[0][0]).toBe('/ws/execution/77')
    expect(typeof firstHandlers().onMessage).toBe('function')
    expect(typeof firstHandlers().onError).toBe('function')
  })

  it('disconnect 关闭连接并置空，重复调用不再关闭', () => {
    const ctx = setup()
    const connection = { ws: {} as WebSocket, close: vi.fn() } as WebSocketConnection
    connectMock.mockReturnValue(connection)

    ctx.api.connectWebSocketForRealtimeUpdate()
    ctx.api.disconnect()
    ctx.api.disconnect()

    expect(disconnectMock).toHaveBeenCalledTimes(1)
    expect(disconnectMock).toHaveBeenCalledWith(connection)
  })

  it('组件卸载时自动断开连接', () => {
    const ctx = setup()
    const connection = { ws: {} as WebSocket, close: vi.fn() } as WebSocketConnection
    connectMock.mockReturnValue(connection)

    ctx.api.connectWebSocketForRealtimeUpdate()
    ctx.wrapper.unmount()

    expect(disconnectMock).toHaveBeenCalledWith(connection)
  })
})

describe('useExecutionWebSocket — 消息处理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    connectMock.mockReturnValue({
      ws: {} as WebSocket,
      close: vi.fn(),
    } as WebSocketConnection)
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  it('step_update 写入步骤并按 current_step-1 切索引、加载截图', () => {
    const ctx = setup()
    ctx.api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onMessage({
      type: 'step_update',
      steps: [{ id: 's2' }, { id: 's3' }],
      current_step: 2,
    })

    expect(ctx.executionSteps.value).toEqual([{ id: 's2' }, { id: 's3' }])
    expect(ctx.currentStepIndex.value).toBe(1)
    expect(ctx.loadStepScreenshot).toHaveBeenCalledTimes(1)
  })

  it('step_update 无 current_step 时不切索引', () => {
    const ctx = setup()
    ctx.api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onMessage({ type: 'step_update', steps: [{ id: 's9' }] })

    expect(ctx.executionSteps.value).toEqual([{ id: 's9' }])
    expect(ctx.currentStepIndex.value).toBe(0)
    expect(ctx.loadStepScreenshot).not.toHaveBeenCalled()
  })

  it('log 追加日志并在 nextTick 后滚动到底部', async () => {
    const ctx = setup()
    ctx.api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onMessage({ type: 'log', log: { level: 'info', text: 'hi' } })

    expect(ctx.executionLogs.value).toEqual([{ level: 'info', text: 'hi' }])
    expect(ctx.scrollToBottom).not.toHaveBeenCalled()

    await nextTick()
    expect(ctx.scrollToBottom).toHaveBeenCalledTimes(1)
  })

  it('status_update 覆盖执行状态', () => {
    const ctx = setup()
    ctx.api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onMessage({ type: 'status_update', status: { status: 'completed' } })

    expect(ctx.executionStatus.value).toEqual({ status: 'completed' })
  })

  it('未知消息类型不影响状态', () => {
    const ctx = setup()
    ctx.api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onMessage({ type: 'unknown', payload: 1 })

    expect(ctx.executionSteps.value).toEqual([{ id: 's1' }])
    expect(ctx.executionLogs.value).toEqual([])
  })

  it('onError 仅记录日志', () => {
    setup().api.connectWebSocketForRealtimeUpdate()

    firstHandlers().onError(new Error('ws down'))

    expect(console.error).toHaveBeenCalledWith('WebSocket错误:', expect.any(Error))
  })
})
