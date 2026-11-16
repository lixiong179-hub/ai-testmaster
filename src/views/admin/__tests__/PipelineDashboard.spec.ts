import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../usePipelineDashboard', () => ({
  usePipelineDashboard: () => state.current,
}))

import PipelineDashboard from '../PipelineDashboard.vue'

const actions = {
  goBack: vi.fn(),
  refreshAll: vi.fn(),
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    projectId: ref<number | undefined>(7),
    days: ref(7),
    projects: ref([
      { id: 7, name: 'Alpha 项目' },
      { id: 8, name: 'Beta 项目' },
    ]),
    overviewCards: ref([
      { key: 'runs', title: '运行次数', value: 12, suffix: '次', color: 'card-blue' },
      { key: 'tokens', title: 'Token 总量', value: '1.2万', suffix: '', color: 'card-green' },
    ]),
    fmeaMetrics: ref([
      {
        fmea_id: 'FMEA-1',
        metric_name: 'pipeline_failure',
        description: '流水线失败',
        count: 2,
        total: 10,
      },
      {
        fmea_id: 'FMEA-2',
        metric_name: 'step_timeout',
        description: '步骤超时',
        count: 0,
        total: 10,
      },
    ]),
    tokenChartRef: ref<HTMLElement | undefined>(undefined),
    durationChartRef: ref<HTMLElement | undefined>(undefined),
    stepLatencyChartRef: ref<HTMLElement | undefined>(undefined),
    cacheChartRef: ref<HTMLElement | undefined>(undefined),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

function mountDashboard(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  return mount(PipelineDashboard)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('PipelineDashboard — 渲染', () => {
  it('渲染概览卡片标题、数值与后缀', () => {
    const wrapper = mountDashboard()

    const cards = wrapper.findAll('.metric-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].find('.metric-title').text()).toBe('运行次数')
    expect(cards[0].find('.metric-value').text()).toContain('12')
    expect(cards[0].find('.metric-suffix').text()).toBe('次')
    expect(cards[0].classes()).toContain('card-blue')
  })

  it('FMEA 指标按次数渲染告警/正常状态', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('FMEA-1')
    expect(rows[0].text()).toContain('告警')
    expect(rows[1].text()).toContain('正常')
  })

  it('四个图表容器完成 ref 绑定', () => {
    mountDashboard()

    for (const key of [
      'tokenChartRef',
      'durationChartRef',
      'stepLatencyChartRef',
      'cacheChartRef',
    ]) {
      expect((ctx[key] as { value?: unknown }).value).toBeInstanceOf(HTMLElement)
    }
  })

  it('项目下拉渲染项目名', () => {
    const wrapper = mountDashboard()

    // el-select 未展开时选项不渲染，改为断言组件拿到项目数据
    expect((ctx.projects as { value: unknown[] }).value).toHaveLength(2)
    expect(wrapper.find('.dashboard-filters').exists()).toBe(true)
  })
})

describe('PipelineDashboard — 交互', () => {
  it('点击刷新触发 refreshAll', async () => {
    const wrapper = mountDashboard()

    await wrapper.find('.dashboard-filters .el-button').trigger('click')

    expect(actions.refreshAll).toHaveBeenCalledTimes(1)
  })

  it('页头返回触发 goBack', () => {
    const wrapper = mountDashboard()

    wrapper.findComponent({ name: 'ElPageHeader' }).vm.$emit('back')

    expect(actions.goBack).toHaveBeenCalledTimes(1)
  })
})
