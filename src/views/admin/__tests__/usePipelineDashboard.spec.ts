import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createComposableHost } from '@/test-utils'

type Fn = ReturnType<typeof vi.fn>

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  getDashboardOverview: vi.fn(),
  getDashboardTokenUsage: vi.fn(),
  getDashboardRunDuration: vi.fn(),
  getDashboardStepLatency: vi.fn(),
  getDashboardCacheHitRate: vi.fn(),
  getMetricsSummary: vi.fn(),
  getProjects: vi.fn(),
  init: vi.fn(),
  use: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back }),
}))

vi.mock('@/api/pipeline', () => ({
  pipelineApi: {
    getDashboardOverview: mocks.getDashboardOverview,
    getDashboardTokenUsage: mocks.getDashboardTokenUsage,
    getDashboardRunDuration: mocks.getDashboardRunDuration,
    getDashboardStepLatency: mocks.getDashboardStepLatency,
    getDashboardCacheHitRate: mocks.getDashboardCacheHitRate,
    getMetricsSummary: mocks.getMetricsSummary,
  },
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('echarts/core', () => ({
  init: mocks.init,
  use: mocks.use,
  graphic: { LinearGradient: vi.fn() },
}))

vi.mock('echarts/charts', () => ({ BarChart: {}, LineChart: {} }))
vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

import { usePipelineDashboard } from '../usePipelineDashboard'

type Ctx = ReturnType<typeof usePipelineDashboard>

const host = createComposableHost<Ctx>(() => usePipelineDashboard())
let ctx: Ctx
let charts: Array<{ setOption: Fn; resize: Fn; dispose: Fn }>

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function attachChartRefs() {
  ctx.tokenChartRef.value = document.createElement('div')
  ctx.durationChartRef.value = document.createElement('div')
  ctx.stepLatencyChartRef.value = document.createElement('div')
  ctx.cacheChartRef.value = document.createElement('div')
}

function chartTitles(): string[] {
  return ctx.overviewCards.value.map((card) => card.title)
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
    data: { items: [{ id: 5, name: '项目A' }] },
  })
  mocks.getDashboardOverview.mockResolvedValue({
    data: {
      data: {
        total_runs: 12,
        success_rate: 91.7,
        total_tokens: 3456,
        total_cost_usd: 1.25,
        avg_duration_seconds: 88,
        cache_hit_rate: 42.5,
      },
    },
  })
  mocks.getDashboardTokenUsage.mockResolvedValue({
    data: {
      data: [
        { date: '2026-06-01', prompt_tokens: 100, completion_tokens: 40 },
        { date: '2026-06-02', prompt_tokens: 200, completion_tokens: 60 },
      ],
    },
  })
  mocks.getDashboardRunDuration.mockResolvedValue({
    data: { data: [{ date: '2026-06-01', avg_duration_seconds: 30 }] },
  })
  mocks.getDashboardStepLatency.mockResolvedValue({
    data: { data: [{ step_name: '解析需求', avg_duration_seconds: 12 }] },
  })
  mocks.getDashboardCacheHitRate.mockResolvedValue({
    data: { data: [{ date: '2026-06-01', cache_hit_rate: 40 }] },
  })
  mocks.getMetricsSummary.mockResolvedValue({
    data: { data: { metrics: [{ name: 'fmea', value: 1 }] } },
  })
})

describe('usePipelineDashboard — 数据加载', () => {
  it('挂载后拉取项目与六个看板接口', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({})
    expect(mocks.getDashboardOverview).toHaveBeenCalledWith({ days: 7 })
    expect(mocks.getDashboardTokenUsage).toHaveBeenCalledWith({ days: 7 })
    expect(mocks.getDashboardRunDuration).toHaveBeenCalledWith({ days: 7 })
    expect(mocks.getDashboardStepLatency).toHaveBeenCalledWith({ days: 7 })
    expect(mocks.getDashboardCacheHitRate).toHaveBeenCalledWith({ days: 7 })
    expect(mocks.getMetricsSummary).toHaveBeenCalledWith({ days: 7 })
  })

  it('写入各维度数据', async () => {
    await mountHost()

    expect(ctx.overviewCards.value[0].value).toBe(12)
    expect(ctx.fmeaMetrics.value).toEqual([{ name: 'fmea', value: 1 }])
    expect(mocks.getDashboardTokenUsage).toHaveBeenCalled()
  })

  it('选择项目后请求参数带上 project_id', async () => {
    await mountHost()
    mocks.getDashboardOverview.mockClear()

    ctx.projectId.value = 5
    await flushPromises()

    expect(mocks.getDashboardOverview).toHaveBeenCalledWith({ days: 7, project_id: 5 })
  })

  it('切换天数后刷新', async () => {
    await mountHost()
    mocks.getDashboardOverview.mockClear()

    ctx.days.value = 30
    await flushPromises()

    expect(mocks.getDashboardOverview).toHaveBeenCalledWith({ days: 30 })
  })

  it('任意接口失败都不影响其它数据', async () => {
    mocks.getDashboardOverview.mockRejectedValue(new Error('总览失败'))
    mocks.getDashboardTokenUsage.mockRejectedValue(new Error('token 失败'))
    mocks.getDashboardRunDuration.mockRejectedValue(new Error('时长失败'))
    mocks.getDashboardStepLatency.mockRejectedValue(new Error('步骤失败'))
    mocks.getDashboardCacheHitRate.mockRejectedValue(new Error('缓存失败'))
    mocks.getMetricsSummary.mockRejectedValue(new Error('FMEA 失败'))

    await mountHost()

    expect(ctx.overviewCards.value.every((card) => card.value === '-')).toBe(true)
    expect(ctx.fmeaMetrics.value).toEqual([])
  })

  it('接口返回缺字段时数组降级为空', async () => {
    mocks.getDashboardTokenUsage.mockResolvedValue({ data: {} })
    mocks.getMetricsSummary.mockResolvedValue({ data: { data: {} } })

    await mountHost()

    expect(ctx.fmeaMetrics.value).toEqual([])
    expect(mocks.getDashboardTokenUsage).toHaveBeenCalled()
  })
})

describe('usePipelineDashboard — 概览卡片', () => {
  it('六张卡片按总览字段映射，单位正确', async () => {
    await mountHost()

    expect(chartTitles()).toEqual([
      '总运行',
      '成功率',
      'Token 消耗',
      '总成本',
      '平均时长',
      '缓存命中率',
    ])
    expect(ctx.overviewCards.value.map((card) => card.suffix)).toEqual([
      '次',
      '%',
      '',
      ' USD',
      ' 秒',
      '%',
    ])
  })

  it('总览为空时全部展示占位符', async () => {
    mocks.getDashboardOverview.mockResolvedValue({ data: {} })

    await mountHost()

    expect(ctx.overviewCards.value.map((card) => card.value)).toEqual([
      '-',
      '-',
      '-',
      '-',
      '-',
      '-',
    ])
  })

  it('goBack 返回上一页', async () => {
    await mountHost()

    ctx.goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
  })
})

describe('usePipelineDashboard — 图表', () => {
  it('四个容器各初始化一次并绘制', async () => {
    await mountHost()
    attachChartRefs()

    await ctx.refreshAll()

    expect(charts).toHaveLength(4)
    charts.forEach((chart) => expect(chart.setOption).toHaveBeenCalledTimes(1))
  })

  it('重复刷新复用实例', async () => {
    await mountHost()
    attachChartRefs()

    await ctx.refreshAll()
    await ctx.refreshAll()

    expect(mocks.init).toHaveBeenCalledTimes(4)
  })

  it('容器不存在时不初始化', async () => {
    await mountHost()

    await ctx.refreshAll()

    expect(mocks.init).not.toHaveBeenCalled()
  })

  it('Token 图按日期堆叠两个系列', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[0].setOption.mock.calls[0][0] as {
      xAxis: { data: string[] }
      series: Array<{ name: string; data: number[] }>
    }
    expect(option.xAxis.data).toEqual(['2026-06-01', '2026-06-02'])
    expect(option.series[0].data).toEqual([100, 200])
    expect(option.series[1].data).toEqual([40, 60])
  })

  it('运行时长图使用折线', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[1].setOption.mock.calls[0][0] as {
      series: Array<{ type: string; data: number[] }>
    }
    expect(option.series[0].type).toBe('line')
    expect(option.series[0].data).toEqual([30])
  })

  it('步骤耗时图使用柱状并旋转标签', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[2].setOption.mock.calls[0][0] as {
      xAxis: { data: string[]; axisLabel: { rotate: number } }
      series: Array<{ type: string }>
    }
    expect(option.xAxis.data).toEqual(['解析需求'])
    expect(option.xAxis.axisLabel.rotate).toBe(30)
    expect(option.series[0].type).toBe('bar')
  })

  it('缓存命中率图上限固定为 100', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    const option = charts[3].setOption.mock.calls[0][0] as {
      yAxis: { max: number; name: string }
      series: Array<{ data: number[] }>
    }
    expect(option.yAxis.max).toBe(100)
    expect(option.series[0].data).toEqual([40])
  })

  it('窗口尺寸变化时重绘所有图表', async () => {
    await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    window.dispatchEvent(new Event('resize'))

    charts.forEach((chart) => expect(chart.resize).toHaveBeenCalledTimes(1))
  })

  it('卸载时销毁图表', async () => {
    const wrapper = await mountHost()
    attachChartRefs()
    await ctx.refreshAll()

    wrapper.unmount()

    charts.forEach((chart) => expect(chart.dispose).toHaveBeenCalledTimes(1))
  })
})
