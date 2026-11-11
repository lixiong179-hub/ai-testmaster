import { describe, it, expect, beforeEach, vi } from 'vitest'

const { mockRequest } = vi.hoisted(() => ({
  mockRequest: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/request', () => ({
  default: mockRequest,
}))

import aiInvocationApi, { usdToCny } from '@/api/aiInvocation'
import type { AIInvocationListItem } from '@/api/aiInvocation'

function makeItem(overrides: Partial<AIInvocationListItem> = {}): AIInvocationListItem {
  return {
    id: 1,
    run_id: 1,
    step_name: 'generate',
    model: 'deepseek',
    prompt_tokens: 100,
    completion_tokens: 50,
    cost_usd: 0.2,
    latency_ms: 1200,
    status: 'success',
    error_message: null,
    created_at: '2026-01-01T00:00:00',
    generation_batch_id: 1,
    scenario_type: 'case',
    generation_strategy: 'smart',
    prompt_key: 'p',
    prompt_version: 1,
    prompt_hash: 'h',
    error_code: null,
    ...overrides,
  }
}

function pageOf(count: number): {
  code: number
  data: { items: AIInvocationListItem[]; total: number; page: number; page_size: number }
} {
  const items = Array.from({ length: count }, (_, i) => makeItem({ id: i + 1 }))
  return {
    code: 200,
    data: { items, total: count, page: 1, page_size: 100 },
  }
}

describe('usdToCny', () => {
  it('按固定汇率 7.25 换算并保留 4 位小数', () => {
    expect(usdToCny(0)).toBe(0)
    expect(usdToCny(1)).toBe(7.25)
    expect(usdToCny(1.23456)).toBe(8.9506)
  })
})

describe('aiInvocationApi.getBatchCost', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('汇总批次内 Token 与成本，totalTokens 为输入+输出之和', async () => {
    mockRequest.get.mockResolvedValueOnce({
      code: 200,
      data: {
        items: [
          makeItem({ prompt_tokens: 100, completion_tokens: 50, cost_usd: 0.2 }),
          makeItem({ prompt_tokens: 300, completion_tokens: 150, cost_usd: 0.5 }),
        ],
      },
    })

    const cost = await aiInvocationApi.getBatchCost(7)

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/ai-invocation/list', {
      params: { batch_id: 7, page: 1, page_size: 100 },
    })
    expect(cost).toEqual({
      totalCalls: 2,
      totalPromptTokens: 400,
      totalCompletionTokens: 200,
      totalTokens: 600,
      totalCostUsd: 0.7,
    })
  })

  it('字段缺失按 0 处理，空列表返回全 0', async () => {
    mockRequest.get.mockResolvedValueOnce({
      code: 200,
      data: {
        items: [
          {
            ...makeItem(),
            prompt_tokens: undefined,
            completion_tokens: undefined,
            cost_usd: undefined,
          },
        ],
      },
    })
    const one = await aiInvocationApi.getBatchCost(1)
    expect(one.totalTokens).toBe(0)
    expect(one.totalCostUsd).toBe(0)

    mockRequest.get.mockResolvedValueOnce({ code: 200, data: { items: [] } })
    const empty = await aiInvocationApi.getBatchCost(2)
    expect(empty).toEqual({
      totalCalls: 0,
      totalPromptTokens: 0,
      totalCompletionTokens: 0,
      totalTokens: 0,
      totalCostUsd: 0,
    })
  })
})

describe('aiInvocationApi.getRunCost', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('按页拉全后本地汇总，末页不足 100 条即停止', async () => {
    mockRequest.get.mockResolvedValueOnce(pageOf(100)).mockResolvedValueOnce(pageOf(30))

    const cost = await aiInvocationApi.getRunCost(9)

    expect(mockRequest.get).toHaveBeenCalledTimes(2)
    expect(mockRequest.get).toHaveBeenNthCalledWith(1, '/api/v1/ai-invocation/list', {
      params: { run_id: 9, page: 1, page_size: 100 },
    })
    expect(mockRequest.get).toHaveBeenNthCalledWith(2, '/api/v1/ai-invocation/list', {
      params: { run_id: 9, page: 2, page_size: 100 },
    })
    expect(cost.totalCalls).toBe(130)
    expect(cost.totalPromptTokens).toBe(130 * 100)
    expect(cost.totalCompletionTokens).toBe(130 * 50)
  })

  it('首页不足一页时只请求一次', async () => {
    mockRequest.get.mockResolvedValueOnce(pageOf(5))

    const cost = await aiInvocationApi.getRunCost(9)

    expect(mockRequest.get).toHaveBeenCalledTimes(1)
    expect(cost.totalCalls).toBe(5)
  })

  it('异常数据（页页满 100）最多翻 20 页，防死循环', async () => {
    mockRequest.get.mockResolvedValue(pageOf(100))

    const cost = await aiInvocationApi.getRunCost(9)

    expect(mockRequest.get).toHaveBeenCalledTimes(20)
    expect(cost.totalCalls).toBe(2000)
  })
})

describe('aiInvocationApi.getStats / getList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('getStats: 参数原样透传到 /stats', async () => {
    mockRequest.get.mockResolvedValueOnce({ code: 200, data: { items: [] } })

    await aiInvocationApi.getStats({
      project_id: 10,
      start_date: '2026-01-01',
      end_date: '2026-01-31',
      group_by: 'model',
    })

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/ai-invocation/stats', {
      params: {
        project_id: 10,
        start_date: '2026-01-01',
        end_date: '2026-01-31',
        group_by: 'model',
      },
    })
  })

  it('getList: 分页参数原样透传', async () => {
    mockRequest.get.mockResolvedValueOnce({ code: 200, data: { items: [], total: 0 } })

    await aiInvocationApi.getList({ project_id: 10, page: 2, page_size: 50 })

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/ai-invocation/list', {
      params: { project_id: 10, page: 2, page_size: 50 },
    })
  })
})
