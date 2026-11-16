import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useAICostDashboard', () => ({
  useAICostDashboard: () => state.current,
}))

import AICostDashboard from '../AICostDashboard.vue'

const actions = {
  goBack: vi.fn(),
  refreshAll: vi.fn(),
  handlePageChange: vi.fn(),
}

function makeInvocation(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    model: 'gpt-4o-mini',
    step_name: 'generate_cases',
    prompt_tokens: 100,
    completion_tokens: 50,
    cost_usd: 0.4,
    latency_ms: 1200,
    status: 'success',
    generation_strategy: 'strict',
    created_at: '2026-11-16T08:30:00',
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    projectId: ref<number | undefined>(undefined),
    days: ref(7),
    loading: ref(false),
    projects: ref([{ id: 7, name: 'Alpha 项目' }]),
    overviewCards: ref([
      { key: 'cost', title: '总成本', value: '¥12.90', suffix: '元', color: 'card-blue' },
      { key: 'calls', title: '调用次数', value: 32, suffix: '次', color: 'card-green' },
    ]),
    invocationList: ref([
      makeInvocation(1),
      makeInvocation(2, { status: 'failed', created_at: '', cost_usd: 0 }),
    ]),
    invocationTotal: ref(32),
    invocationPage: ref(1),
    invocationPageSize: ref(10),
    costTrendChartRef: ref<HTMLElement | undefined>(undefined),
    tokenDailyChartRef: ref<HTMLElement | undefined>(undefined),
    modelPieChartRef: ref<HTMLElement | undefined>(undefined),
    strategyBarChartRef: ref<HTMLElement | undefined>(undefined),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

function mountDashboard(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  return mount(AICostDashboard)
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AICostDashboard — 渲染', () => {
  it('渲染概览卡片', () => {
    const wrapper = mountDashboard()

    const cards = wrapper.findAll('.metric-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('总成本')
    expect(cards[0].text()).toContain('¥12.90')
  })

  it('调用明细按美元汇率格式化为人民币四位小数', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    // 0.4 USD × 7.25 = 2.9
    expect(rows[0].text()).toContain('2.9000')
    expect(rows[1].text()).toContain('0.0000')
  })

  it('状态标签区分成功与失败', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows[0].text()).toContain('成功')
    expect(rows[1].text()).toContain('失败')
  })

  it('时间格式化：合法时间转本地时间，空值回退占位符', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows[0].text()).toMatch(/2026/)
    expect(rows[1].text()).toContain('-')
  })

  it('非法时间字符串原样展示', async () => {
    const wrapper = mountDashboard({
      invocationList: ref([makeInvocation(3, { created_at: 'not-a-date' })]),
    })
    await flushPromises()

    expect(wrapper.find('.el-table__row').text()).toContain('not-a-date')
  })

  it('四个图表容器完成 ref 绑定', () => {
    mountDashboard()

    for (const key of [
      'costTrendChartRef',
      'tokenDailyChartRef',
      'modelPieChartRef',
      'strategyBarChartRef',
    ]) {
      expect((ctx[key] as { value?: unknown }).value).toBeInstanceOf(HTMLElement)
    }
  })

  it('总数大于 0 时渲染分页，否则隐藏', () => {
    const withPager = mountDashboard()
    expect(withPager.find('.el-pagination').exists()).toBe(true)

    const withoutPager = mountDashboard({ invocationTotal: ref(0) })
    expect(withoutPager.find('.el-pagination').exists()).toBe(false)
  })

  it('加载中时刷新按钮展示 loading 态', () => {
    const wrapper = mountDashboard({ loading: ref(true) })

    expect(wrapper.find('.dashboard-filters .el-button').classes()).toContain('is-loading')
  })
})

describe('AICostDashboard — 交互', () => {
  it('刷新按钮触发 refreshAll', async () => {
    const wrapper = mountDashboard()

    await wrapper.find('.dashboard-filters .el-button').trigger('click')

    expect(actions.refreshAll).toHaveBeenCalledTimes(1)
  })

  it('翻页透传页码', () => {
    const wrapper = mountDashboard()

    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 3)

    expect(actions.handlePageChange).toHaveBeenCalledWith(3)
  })

  it('页头返回触发 goBack', () => {
    const wrapper = mountDashboard()

    wrapper.findComponent({ name: 'ElPageHeader' }).vm.$emit('back')

    expect(actions.goBack).toHaveBeenCalledTimes(1)
  })
})
