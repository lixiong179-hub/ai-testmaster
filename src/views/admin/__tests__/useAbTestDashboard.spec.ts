import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  listExperiments: vi.fn(),
  getExperimentSummary: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back }),
}))

vi.mock('@/api/abTest', () => ({
  abTestApi: {
    listExperiments: mocks.listExperiments,
    getExperimentSummary: mocks.getExperimentSummary,
  },
  AB_TEST_METRIC_LABELS: {
    pass_rate: '通过率',
    duration: '平均耗时',
    cost: '平均成本',
  },
  AB_TEST_METRIC_DIRECTION: {
    pass_rate: 'higher',
    duration: 'lower',
    cost: 'lower',
  },
}))

import { useAbTestDashboard } from '../useAbTestDashboard'

type Ctx = ReturnType<typeof useAbTestDashboard>

const host = createComposableHost<Ctx>(() => useAbTestDashboard())
let ctx: Ctx

function makeSummary(overrides: Record<string, unknown> = {}) {
  return {
    experiment_id: 'exp-1',
    variants: {
      control: {
        pass_rate: { mean: 0.8, sample_count: 100 },
        duration: { mean: 2, sample_count: 100 },
      },
      treatment: {
        pass_rate: { mean: 0.9, sample_count: 120 },
        duration: { mean: 1, sample_count: 120 },
      },
    },
    ...overrides,
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function rowOf(name: string) {
  return ctx.comparisonRows.value.find((row) => row.metricName === name)!
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.listExperiments.mockResolvedValue({
    data: {
      items: [
        { experiment_id: 'exp-1', case_count: 10 },
        { experiment_id: 'exp-2', case_count: 20 },
      ],
    },
  })
  mocks.getExperimentSummary.mockResolvedValue({ data: makeSummary() })
})

describe('useAbTestDashboard — 加载', () => {
  it('挂载后拉取实验列表并默认选中首个实验的汇总', async () => {
    await mountHost()

    expect(mocks.listExperiments).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.experiments.value).toHaveLength(2)
    expect(ctx.experimentId.value).toBe('exp-1')
    expect(mocks.getExperimentSummary).toHaveBeenCalledWith('exp-1')
    expect(ctx.summary.value).not.toBeNull()
    expect(ctx.loading.value).toBe(false)
    expect(ctx.errorMessage.value).toBe('')
  })

  it('没有实验时不请求汇总', async () => {
    mocks.listExperiments.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(ctx.experimentId.value).toBe('')
    expect(mocks.getExperimentSummary).not.toHaveBeenCalled()
    expect(ctx.summary.value).toBeNull()
    expect(ctx.hasData.value).toBe(false)
  })

  it('实验列表失败时写入错误并提示', async () => {
    mocks.listExperiments.mockRejectedValue(new Error('实验服务异常'))

    await mountHost()

    expect(ctx.errorMessage.value).toBe('实验服务异常')
    expect(ElMessage.warning).toHaveBeenCalledWith('实验服务异常')
    expect(ctx.loading.value).toBe(false)
  })

  it('实验列表失败且非 Error 时使用兜底文案', async () => {
    mocks.listExperiments.mockRejectedValue(undefined)

    await mountHost()

    expect(ctx.errorMessage.value).toBe('获取实验列表失败')
  })

  it('汇总失败时清空汇总并提示', async () => {
    mocks.getExperimentSummary.mockRejectedValue(new Error('汇总服务异常'))

    await mountHost()

    expect(ctx.summary.value).toBeNull()
    expect(ElMessage.warning).toHaveBeenCalledWith('汇总服务异常')
  })

  it('汇总失败且非 Error 时使用兜底文案', async () => {
    mocks.getExperimentSummary.mockRejectedValue(undefined)

    await mountHost()

    expect(ctx.errorMessage.value).toBe('获取实验汇总失败')
  })

  it('切换实验时重新拉取汇总', async () => {
    await mountHost()
    mocks.getExperimentSummary.mockClear()

    ctx.experimentId.value = 'exp-2'
    await flushPromises()

    expect(mocks.getExperimentSummary).toHaveBeenCalledWith('exp-2')
  })

  it('实验 ID 为空时汇总置空且不请求', async () => {
    await mountHost()
    mocks.getExperimentSummary.mockClear()

    ctx.experimentId.value = ''
    await flushPromises()

    expect(mocks.getExperimentSummary).not.toHaveBeenCalled()
    expect(ctx.summary.value).toBeNull()
  })

  it('refreshAll 重新拉取实验与汇总', async () => {
    await mountHost()
    mocks.listExperiments.mockClear()
    mocks.getExperimentSummary.mockClear()

    await ctx.refreshAll()

    expect(mocks.listExperiments).toHaveBeenCalledTimes(1)
    expect(mocks.getExperimentSummary).toHaveBeenCalledTimes(1)
  })

  it('goBack 返回上一页', async () => {
    await mountHost()

    ctx.goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
  })
})

describe('useAbTestDashboard — 指标对比', () => {
  it('按全部指标生成对比行，包含均值与样本数', async () => {
    await mountHost()

    expect(ctx.comparisonRows.value.map((row) => row.metricName)).toEqual([
      'pass_rate',
      'duration',
      'cost',
    ])
    expect(rowOf('pass_rate')).toMatchObject({
      label: '通过率',
      direction: 'higher',
      controlMean: 0.8,
      treatmentMean: 0.9,
      controlSample: 100,
      treatmentSample: 120,
      diffPercent: 12.5,
      improved: true,
    })
  })

  it('方向为 lower 时下降才算改善', async () => {
    await mountHost()

    expect(rowOf('duration')).toMatchObject({ diffPercent: -50, improved: true })
  })

  it('与 control 持平时不算改善', async () => {
    mocks.getExperimentSummary.mockResolvedValue({
      data: makeSummary({
        variants: {
          control: { pass_rate: { mean: 0.8, sample_count: 10 } },
          treatment: { pass_rate: { mean: 0.8, sample_count: 10 } },
        },
      }),
    })

    await mountHost()

    expect(rowOf('pass_rate').diffPercent).toBe(0)
    expect(rowOf('pass_rate').improved).toBe(false)
  })

  it('control 为 0 时差异与改善判定为空', async () => {
    mocks.getExperimentSummary.mockResolvedValue({
      data: makeSummary({
        variants: {
          control: { pass_rate: { mean: 0, sample_count: 10 } },
          treatment: { pass_rate: { mean: 0.5, sample_count: 10 } },
        },
      }),
    })

    await mountHost()

    expect(rowOf('pass_rate').diffPercent).toBeNull()
    expect(rowOf('pass_rate').improved).toBeNull()
  })

  it('指标缺失时均值与样本数为空', async () => {
    await mountHost()

    expect(rowOf('cost')).toMatchObject({
      controlMean: null,
      treatmentMean: null,
      controlSample: 0,
      treatmentSample: 0,
      diffPercent: null,
      improved: null,
    })
  })

  it('只有一侧变体有数据时差异为空', async () => {
    mocks.getExperimentSummary.mockResolvedValue({
      data: makeSummary({
        variants: { control: { pass_rate: { mean: 0.8, sample_count: 10 } } },
      }),
    })

    await mountHost()

    expect(rowOf('pass_rate').treatmentMean).toBeNull()
    expect(rowOf('pass_rate').diffPercent).toBeNull()
  })

  it('无汇总数据时全部对比行为空', async () => {
    mocks.listExperiments.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(ctx.comparisonRows.value).toHaveLength(3)
    expect(ctx.comparisonRows.value.every((row) => row.controlMean === null)).toBe(true)
  })

  it('hasData 依据汇总的变体数量判定', async () => {
    await mountHost()
    expect(ctx.hasData.value).toBe(true)

    ctx.summary.value = makeSummary({ variants: {} }) as never
    expect(ctx.hasData.value).toBe(false)

    ctx.summary.value = null
    expect(ctx.hasData.value).toBe(false)
  })
})
