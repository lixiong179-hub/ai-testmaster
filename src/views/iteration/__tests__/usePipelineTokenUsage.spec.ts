import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createComposableHost, deferred } from '@/test-utils'
import type { BatchCostInfo } from '@/api/aiInvocation'

const mocks = vi.hoisted(() => ({ getRunCost: vi.fn() }))

vi.mock('@/api/aiInvocation', () => ({
  aiInvocationApi: { getRunCost: mocks.getRunCost },
  // 与真实实现同口径（7.25 汇率），断言不依赖 mock 汇率
  usdToCny: (usd: number) => Number((usd * 7.25).toFixed(4)),
}))

import { usePipelineTokenUsage, type PipelineProgressMessage } from '../usePipelineTokenUsage'

type Ctx = ReturnType<typeof usePipelineTokenUsage>

const runId = ref(1)
const host = createComposableHost<Ctx>(() => usePipelineTokenUsage(runId))
let ctx: Ctx

async function mountHost(id = 1) {
  runId.value = id
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

/** 构造成本快照；默认 150 Token / 0.4 美元（≈ ¥2.90） */
function makeCost(over: Partial<BatchCostInfo> = {}): BatchCostInfo {
  return {
    totalCalls: 2,
    totalPromptTokens: 100,
    totalCompletionTokens: 50,
    totalTokens: 150,
    totalCostUsd: 0.4,
    ...over,
  }
}

function makeMessage(over: Partial<PipelineProgressMessage> = {}): PipelineProgressMessage {
  return {
    type: 'pipeline_progress',
    run_id: 1,
    step_name: 'generate_cases',
    status: 'running',
    progress: 30,
    pipeline_status: 'in_pipeline',
    ...over,
  }
}

const EMPTY = { totalTokens: 0, totalCostCny: 0, loaded: false }

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getRunCost.mockResolvedValue(makeCost())
})

afterEach(() => {
  vi.useRealTimers()
})

describe('usePipelineTokenUsage — 展示文案', () => {
  it('未加载时展示占位符而不是 0', async () => {
    await mountHost()

    expect(ctx.tokenUsage.value).toEqual(EMPTY)
    expect(ctx.tokenDisplay.value).toBe('Token: — | 成本: —')
  })

  it('加载后按千分位 Token 与两位小数成本展示', async () => {
    mocks.getRunCost.mockResolvedValue(makeCost({ totalTokens: 12345, totalCostUsd: 0.4 }))
    await mountHost()

    await ctx.fetchTokenUsage()

    expect(ctx.tokenUsage.value).toEqual({
      totalTokens: 12345,
      totalCostCny: 2.9,
      loaded: true,
    })
    expect(ctx.tokenDisplay.value).toBe('Token: 12,345 | 成本: ¥2.90')
  })
})

describe('usePipelineTokenUsage — 轮询拉取', () => {
  it('runId 为 0 时不发请求', async () => {
    await mountHost(0)

    await ctx.fetchTokenUsage()

    expect(mocks.getRunCost).not.toHaveBeenCalled()
    expect(ctx.tokenUsage.value).toEqual(EMPTY)
  })

  it('按当前 runId 请求累计成本', async () => {
    await mountHost(23)

    await ctx.fetchTokenUsage()

    expect(mocks.getRunCost).toHaveBeenCalledWith(23)
  })

  it('请求失败时静默复位为空快照', async () => {
    mocks.getRunCost.mockRejectedValue(new Error('成本服务不可用'))
    await mountHost()

    await ctx.fetchTokenUsage()

    expect(ctx.tokenUsage.value).toEqual(EMPTY)
    expect(ctx.tokenDisplay.value).toBe('Token: — | 成本: —')
  })

  it('runId 切换后旧请求的响应被丢弃', async () => {
    await mountHost(1)
    const pendingCost = deferred<BatchCostInfo>()
    mocks.getRunCost.mockReturnValueOnce(pendingCost.promise)

    const pending = ctx.fetchTokenUsage()
    runId.value = 2
    pendingCost.resolve(makeCost({ totalTokens: 999, totalCostUsd: 1 }))
    await pending

    expect(ctx.tokenUsage.value).toEqual(EMPTY)
  })

  it('并发请求中较晚发起的响应生效、较早的被丢弃', async () => {
    await mountHost()
    const first = deferred<BatchCostInfo>()
    const second = deferred<BatchCostInfo>()
    mocks.getRunCost.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)

    const p1 = ctx.fetchTokenUsage()
    const p2 = ctx.fetchTokenUsage()

    first.resolve(makeCost({ totalTokens: 111, totalCostUsd: 1 }))
    await p1
    expect(ctx.tokenUsage.value.loaded).toBe(false)

    second.resolve(makeCost({ totalTokens: 222, totalCostUsd: 2 }))
    await p2
    expect(ctx.tokenUsage.value.totalTokens).toBe(222)
  })
})

describe('usePipelineTokenUsage — WebSocket 推送', () => {
  it('非 pipeline_progress 消息忽略', async () => {
    await mountHost()

    ctx.applyWsMessage({ type: 'heartbeat' } as unknown as PipelineProgressMessage)
    await flushPromises()

    expect(mocks.getRunCost).not.toHaveBeenCalled()
    expect(ctx.tokenUsage.value).toEqual(EMPTY)
  })

  it('run_id 不匹配的消息忽略', async () => {
    await mountHost(1)

    ctx.applyWsMessage(makeMessage({ run_id: 2, token_usage: 10, cost_usd: 0.1 }))
    await flushPromises()

    expect(mocks.getRunCost).not.toHaveBeenCalled()
    expect(ctx.tokenUsage.value).toEqual(EMPTY)
  })

  it('后端推送累计字段时直接采用且不再轮询', async () => {
    await mountHost(1)

    ctx.applyWsMessage(makeMessage({ token_usage: 2048, cost_usd: 0.2 }))
    await flushPromises()

    expect(ctx.tokenUsage.value).toEqual({
      totalTokens: 2048,
      totalCostCny: 1.45,
      loaded: true,
    })
    expect(mocks.getRunCost).not.toHaveBeenCalled()
  })

  it('未携带累计字段时触发一次兜底拉取', async () => {
    await mountHost(1)

    ctx.applyWsMessage(makeMessage())
    await flushPromises()

    expect(mocks.getRunCost).toHaveBeenCalledTimes(1)
    expect(mocks.getRunCost).toHaveBeenCalledWith(1)
  })

  it('只推送其中一个累计字段时仍走兜底拉取', async () => {
    await mountHost(1)

    ctx.applyWsMessage(makeMessage({ token_usage: 100 }))
    await flushPromises()

    expect(mocks.getRunCost).toHaveBeenCalledTimes(1)
  })
})

describe('usePipelineTokenUsage — 轮询定时器', () => {
  it('startPolling 每 5 秒拉取一次，stopPolling 后停止', async () => {
    await mountHost()
    vi.useFakeTimers()

    ctx.startPolling()
    await vi.advanceTimersByTimeAsync(4999)
    expect(mocks.getRunCost).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(1)
    expect(mocks.getRunCost).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(5000)
    expect(mocks.getRunCost).toHaveBeenCalledTimes(2)

    ctx.stopPolling()
    await vi.advanceTimersByTimeAsync(15000)
    expect(mocks.getRunCost).toHaveBeenCalledTimes(2)
  })

  it('重复 startPolling 不叠加定时器', async () => {
    await mountHost()
    vi.useFakeTimers()

    ctx.startPolling()
    ctx.startPolling()
    await vi.advanceTimersByTimeAsync(5000)

    expect(mocks.getRunCost).toHaveBeenCalledTimes(1)
  })

  it('stopPolling 可重复调用', async () => {
    await mountHost()

    ctx.stopPolling()
    ctx.stopPolling()

    expect(ctx.tokenUsage.value).toEqual(EMPTY)
  })

  it('组件卸载后停止轮询', async () => {
    const wrapper = await mountHost()
    vi.useFakeTimers()
    ctx.startPolling()

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(15000)

    expect(mocks.getRunCost).not.toHaveBeenCalled()
  })
})
