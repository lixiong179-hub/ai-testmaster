import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createComposableHost } from '@/test-utils'

type Fn = ReturnType<typeof vi.fn>

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  getStats: vi.fn(),
  getList: vi.fn(),
  getProjects: vi.fn(),
  init: vi.fn(),
  use: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back }),
}))

vi.mock('@/api/aiInvocation', () => ({
  aiInvocationApi: { getStats: mocks.getStats, getList: mocks.getList },
  usdToCny: (usd: number) => usd * 7.25,
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('echarts/core', () => ({
  init: mocks.init,
  use: mocks.use,
  graphic: { LinearGradient: vi.fn() },
}))

vi.mock('echarts/charts', () => ({ BarChart: {}, LineChart: {}, PieChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
  TitleComponent: {},
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

import { useAICostDashboard } from '../useAICostDashboard'

type Ctx = ReturnType<typeof useAICostDashboard>

const host = createComposableHost<Ctx>(() => useAICostDashboard())
let ctx: Ctx
let charts: Array<{ setOption: Fn; resize: Fn; dispose: Fn }>

function isoDate(offsetDays: number): string {
  const date = new Date()
  date.setDate(date.getDate() + offsetDays)
  return date.toISOString().split('T')[0]
}

function statItem(overrides: Record<string, unknown> = {}) {
  return {
    group_key: '2026-06-01',
    total_prompt_tokens: 100,
    total_completion_tokens: 50,
    total_cost_usd: 1,
    total_calls: 2,
    ...overrides,
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function attachChartRefs() {
  ctx.costTrendChartRef.value = document.createElement('div')
  ctx.tokenDailyChartRef.value = document.createElement('div')
  ctx.modelPieChartRef.value = document.createElement('div')
  ctx.strategyBarChartRef.value = document.createElement('div')
}

beforeEach(() => {
  vi.clearAllMocks()
  charts = []
  mocks.init.mockImplementation(() => {
    const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    charts.push(chart)
    return chart
  })
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 5, name: '项目A' },
        { id: 6, name: '项目B' },
      ],
    },
  })
  mocks.getStats.mockImplementation((params: { group_by: string }) => {
    if (params.group_by === 'model') {
      return Promise.resolve({ data: { items: [statItem({ group_key: 'gpt-4' })] } })
    }
    if (params.group_by === 'strategy') {
      return Promise.resolve({ data: { items: [statItem({ group_key: '全量AI' })] } })
    }
    return Promise.resolve({
      data: {
        items: [
          statItem({ group_key: '2026-06-02', total_cost_usd: 2, total_calls: 3 }),
          statItem({ group_key: '2026-06-01' }),
        ],
      },
    })
  })
  mocks.getList.mockResolvedValue({
    data: { items: [{ status: 'success' }, { status: 'failed' }], total: 2 },
  })
})

describe('useAICostDashboard — 初始化与数据加载', () => {
  it('挂载后拉取项目、按三个维度拉统计并拉调用记录', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({})
    expect(ctx.projects.value).toHaveLength(2)
    expect(mocks.getStats).toHaveBeenCalledTimes(3)
    expect(mocks.getStats.mock.calls.map((c) => c[0].group_by)).toEqual([
      'model',
      'strategy',
      'date',
    ])
    expect(mocks.getList).toHaveBeenCalledWith({ project_id: 5, page: 1, page_size: 10 })
  })

  it('未选项目时默认使用第一个项目，并带上最近 7 天区间', async () => {
    await mountHost()

    const params = mocks.getStats.mock.calls[0][0]
    expect(params.project_id).toBe(5)
    expect(params.start_date).toBe(isoDate(-6))
    expect(params.end_date).toBe(isoDate(0))
  })

  it('没有项目时直接跳过统计请求', async () => {
    mocks.getProjects.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(mocks.getStats).not.toHaveBeenCalled()
    expect(mocks.getList).not.toHaveBeenCalled()
    expect(ctx.overviewCards.value[0].value).toBe('0')
  })

  it('统计失败时复位 loading 且不抛出', async () => {
    mocks.getStats.mockRejectedValue(new Error('统计异常'))

    await mountHost()

    expect(ctx.loading.value).toBe(false)
  })

  it('调用记录失败时不抛出', async () => {
    mocks.getList.mockRejectedValue(new Error('列表异常'))

    await mountHost()

    expect(ctx.invocationList.value).toEqual([])
  })
})

describe('useAICostDashboard — 概览卡片', () => {
  it('按日期维度汇总 Token、成本与调用次数', async () => {
    await mountHost()

    const [tokens, cost, calls] = ctx.overviewCards.value
    // (100+50) + (100+50) = 300
    expect(tokens.value).toBe('300')
    // (1 + 2) USD * 7.25
    expect(cost.value).toBe('21.75')
    expect(cost.suffix).toBe(' 元')
    expect(calls.value).toBe('5')
    expect(calls.suffix).toBe(' 次')
  })

  it('Token 与调用次数使用千分位', async () => {
    mocks.getStats.mockImplementation((params: { group_by: string }) =>
      Promise.resolve({
        data: {
          items: [
            statItem({
              total_prompt_tokens: params.group_by === 'date' ? 12345 : 0,
              total_completion_tokens: 0,
              total_calls: 1234,
            }),
          ],
        },
      })
    )

    await mountHost()

    expect(ctx.overviewCards.value[0].value).toBe((12345).toLocaleString('zh-CN'))
    expect(ctx.overviewCards.value[2].value).toBe((1234).toLocaleString('zh-CN'))
  })

  it('成本超过一万元时使用「万」为单位', async () => {
    mocks.getStats.mockImplementation(() =>
      Promise.resolve({ data: { items: [statItem({ total_cost_usd: 2000 })] } })
    )

    await mountHost()

    expect(ctx.overviewCards.value[1].value).toBe('1.45万')
  })

  it('成功率按调用记录中成功条数占比计算', async () => {
    mocks.getList.mockResolvedValue({
      data: {
        items: [
          { status: 'success' },
          { status: 'success' },
          { status: 'failed' },
          { status: 'failed' },
        ],
        total: 4,
      },
    })

    await mountHost()

    expect(ctx.overviewCards.value[3].value).toBe('50.0')
    expect(ctx.overviewCards.value[3].suffix).toBe('%')
  })

  it('调用记录为空时成功率保持统计结果', async () => {
    mocks.getList.mockResolvedValue({ data: { items: [], total: 0 } })

    await mountHost()

    expect(ctx.overviewCards.value[3].value).toBe('100.0')
  })
})

describe('useAICostDashboard — 交互与监听', () => {
  it('goBack 返回上一页', async () => {
    await mountHost()

    ctx.goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
  })

  it('切换页码后按新页码拉取记录', async () => {
    await mountHost()
    mocks.getList.mockClear()

    await ctx.handlePageChange(3)

    expect(ctx.invocationPage.value).toBe(3)
    expect(mocks.getList).toHaveBeenCalledWith({ project_id: 5, page: 3, page_size: 10 })
  })

  it('切换项目时重置页码并刷新', async () => {
    await mountHost()
    await ctx.handlePageChange(2)
    mocks.getStats.mockClear()
    mocks.getList.mockClear()

    ctx.projectId.value = 6
    await flushPromises()

    expect(ctx.invocationPage.value).toBe(1)
    expect(mocks.getStats).toHaveBeenCalledTimes(3)
    expect(mocks.getList).toHaveBeenCalledWith({ project_id: 6, page: 1, page_size: 10 })
  })

  it('切换天数后按新区间刷新', async () => {
    await mountHost()
    mocks.getStats.mockClear()

    ctx.days.value = 30
    await flushPromises()

    expect(ctx.days.value).toBe(30)
    expect(mocks.getStats.mock.calls[0][0].start_date).toBe(isoDate(-29))
  })
})

describe('useAICostDashboard — 图表', () => {
  it('四个图表容器各初始化一次并写入配置', async () => {
    await mountHost()
    attachChartRefs()

    await ctx.refreshAll()

    expect(charts).toHaveLength(4)
    charts.forEach((chart) => expect(chart.setOption).toHaveBeenCalledTimes(1))
  })

  it('重复刷新复用已有图表实例', async () => {
    await mountHost()
    attachChartRefs()

    await ctx.refreshAll()
    await ctx.refreshAll()

    expect(mocks.init).toHaveBeenCalledTimes(4)
    expect(charts[0].setOption).toHaveBeenCalledTimes(2)
  })

  it('容器不存在时不初始化图表', async () => {
    await mountHost()

    await ctx.refreshAll()

    expect(mocks.init).not.toHaveBeenCalled()
  })

  it('成本趋势图按日期升序并换算为人民币', async () => {
    await mountHost()
    attachChartRefs()
    mocks.init.mockClear()

    await ctx.refreshAll()

    const option = charts[0].setOption.mock.calls[0][0] as {
      xAxis: { data: string[] }
      series: Array<{ data: number[] }>
    }
    expect(option.xAxis.data).toEqual(['2026-06-01', '2026-06-02'])
    expect(option.series[0].data).toEqual([7.25, 14.5])
  })

  it('成本趋势图 tooltip 汇总各系列金额', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[0].setOption.mock.calls[0][0] as {
      tooltip: { formatter: (params: unknown) => string }
    }
    const html = option.tooltip.formatter([
      { axisValue: '2026-06-01', seriesName: '成本（元）', value: 1.23456, marker: '●' },
    ])

    expect(html).toContain('2026-06-01')
    expect(html).toContain('成本（元）: 1.2346 元')
  })

  it('每日 Token 图包含堆叠的 prompt/completion 两个系列', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[1].setOption.mock.calls[0][0] as {
      series: Array<{ name: string; data: number[] }>
    }
    expect(option.series.map((s) => s.name)).toEqual(['Prompt Tokens', 'Completion Tokens'])
    expect(option.series[0].data).toEqual([100, 100])
  })

  it('模型饼图按模型换算成本并保留四位小数', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[2].setOption.mock.calls[0][0] as {
      series: Array<{ data: Array<{ name: string; value: number }> }>
      tooltip: { formatter: (params: unknown) => string }
    }
    expect(option.series[0].data[0]).toEqual({ name: 'gpt-4', value: 7.25 })
    expect(option.tooltip.formatter({ name: 'gpt-4', value: 7.25, percent: 100 })).toBe(
      'gpt-4: 7.2500 元 (100%)'
    )
  })

  it('策略柱图使用渐变填充并支持 tooltip 汇总', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[3].setOption.mock.calls[0][0] as {
      xAxis: { data: string[] }
      tooltip: { formatter: (params: unknown) => string }
    }
    expect(option.xAxis.data).toEqual(['全量AI'])
    expect(option.tooltip.formatter([{ axisValue: '全量AI', value: 7.25 }])).toContain('7.2500 元')
  })

  it('窗口尺寸变化时重绘所有已创建图表', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    window.dispatchEvent(new Event('resize'))

    charts.forEach((chart) => expect(chart.resize).toHaveBeenCalledTimes(1))
  })

  it('卸载时移除监听并销毁图表', async () => {
    const wrapper = await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    wrapper.unmount()

    charts.forEach((chart) => expect(chart.dispose).toHaveBeenCalledTimes(1))
  })
})
