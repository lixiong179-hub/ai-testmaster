import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import type { Report } from '@/api/report'

const chartInstance = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
}))

const chartModule = vi.hoisted(() => ({
  use: vi.fn(),
  init: vi.fn(() => chartInstance),
  graphic: {
    LinearGradient: class {
      constructor(
        public a: number,
        public b: number,
        public c: number,
        public d: number,
        public stops: unknown[]
      ) {}
    },
  },
}))

vi.mock('echarts/core', () => chartModule)
vi.mock('echarts/charts', () => ({ PieChart: {}, LineChart: {} }))
vi.mock('echarts/components', () => ({
  TooltipComponent: {},
  LegendComponent: {},
  TitleComponent: {},
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: {} }))

import ReportStat from '../ReportStat.vue'

/**
 * 组件共享同一份图表实例 mock，且 resize 监听挂在 window 上；
 * 每个用例结束必须卸载，否则后续 dispatchEvent 会累计到旧实例。
 */
const mountedWrappers: VueWrapper[] = []

function mountStat(report: Report | null) {
  const wrapper = mount(ReportStat, { props: { report } })
  mountedWrappers.push(wrapper)
  return wrapper
}

function makeReport(over: Partial<Report> = {}): Report {
  return {
    id: 1,
    project_id: 7,
    test_task_id: 3,
    name: '回归报告',
    status: 'completed',
    total_cases: 20,
    passed_cases: 15,
    failed_cases: 3,
    blocked_cases: 1,
    pass_rate: 75,
    create_time: '2026-11-16 08:00:00',
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  while (mountedWrappers.length > 0) {
    mountedWrappers.pop()!.unmount()
  }
})

describe('ReportStat — 统计卡片', () => {
  it('report 为空时全部展示 0', () => {
    const wrapper = mountStat(null)

    const values = wrapper.findAll('.stat-value').map((node) => node.text())
    expect(values).toEqual(['0', '0', '0', '0', '0.00%'])
  })

  it('展示用例统计与两位小数通过率', () => {
    const wrapper = mountStat(makeReport())

    const values = wrapper.findAll('.stat-value').map((node) => node.text())
    expect(values).toEqual(['20', '15', '3', '1', '75.00%'])
  })

  it('通过率小数位四舍五入到两位', () => {
    const wrapper = mountStat(makeReport({ pass_rate: 66.666 }))

    expect(wrapper.findAll('.stat-value')[4].text()).toBe('66.67%')
  })

  it('统计项使用语义色 class', () => {
    const wrapper = mountStat(makeReport())

    const values = wrapper.findAll('.stat-value')
    expect(values[1].classes()).toContain('success')
    expect(values[2].classes()).toContain('danger')
    expect(values[3].classes()).toContain('warning')
    expect(values[4].classes()).toContain('info')
  })
})

describe('ReportStat — 图表', () => {
  it('挂载后初始化两个图表并按报告数据填充饼图', () => {
    mountStat(makeReport())

    expect(chartModule.init).toHaveBeenCalledTimes(2)
    const option = chartInstance.setOption.mock.calls[0][0] as {
      series: { data: { name: string; value: number }[] }[]
    }
    expect(option.series[0].data.map((item) => [item.name, item.value])).toEqual([
      ['通过', 15],
      ['失败', 3],
      ['阻塞', 1],
      ['其他', 1],
    ])
  })

  it('折线图末点使用报告通过率', () => {
    mountStat(makeReport({ pass_rate: 88 }))

    const lineOption = chartInstance.setOption.mock.calls[1][0] as {
      xAxis: { data: string[] }
      series: { data: number[] }[]
    }
    expect(lineOption.xAxis.data).toEqual(['第1轮', '第2轮', '第3轮', '第4轮', '第5轮'])
    expect(lineOption.series[0].data[4]).toBe(88)
  })

  it('report 为空时仍初始化但不填充数据', () => {
    mountStat(null)

    expect(chartModule.init).toHaveBeenCalledTimes(2)
    expect(chartInstance.setOption).not.toHaveBeenCalled()
  })

  it('报告数据更新后重新填充图表', async () => {
    const wrapper = mountStat(makeReport())
    chartInstance.setOption.mockClear()

    await wrapper.setProps({ report: makeReport({ passed_cases: 18, failed_cases: 0 }) })
    await nextTick()
    await flushPromises()

    expect(chartInstance.setOption).toHaveBeenCalledTimes(2)
    const pieOption = chartInstance.setOption.mock.calls[0][0] as {
      series: { data: { value: number }[] }[]
    }
    expect(pieOption.series[0].data[0].value).toBe(18)
  })

  it('窗口尺寸变化时重绘两个图表', () => {
    mountStat(makeReport())

    window.dispatchEvent(new Event('resize'))

    expect(chartInstance.resize).toHaveBeenCalledTimes(2)
  })

  it('卸载时销毁图表并移除 resize 监听', () => {
    const wrapper = mountStat(makeReport())

    const index = mountedWrappers.indexOf(wrapper)
    if (index >= 0) mountedWrappers.splice(index, 1)
    wrapper.unmount()
    chartInstance.resize.mockClear()
    window.dispatchEvent(new Event('resize'))

    expect(chartInstance.dispose).toHaveBeenCalledTimes(2)
    expect(chartInstance.resize).not.toHaveBeenCalled()
  })
})
