import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import QualityDonutChart from '../QualityDonutChart.vue'

function setup(
  props: Partial<{
    passed: number
    warning: number
    pendingReview: number
    rejected: number
    activeFilter: string | null
    size: number
  }> = {}
) {
  const wrapper = mount(QualityDonutChart, {
    props: {
      passed: 0,
      warning: 0,
      pendingReview: 0,
      rejected: 0,
      ...props,
    } as never,
  })
  return wrapper
}

describe('QualityDonutChart — 空数据', () => {
  it('无数据时展示占位环与 0 总数', () => {
    const wrapper = setup()

    expect(wrapper.findAll('.donut-segment')).toHaveLength(0)
    expect(wrapper.find('circle').exists()).toBe(true)
    expect(wrapper.find('.donut-total').text()).toBe('0')
    expect(wrapper.find('.donut-label').text()).toBe('总用例')
  })

  it('无数据时不渲染图例', () => {
    const wrapper = setup()

    expect(wrapper.findAll('.legend-item')).toHaveLength(0)
  })
})

describe('QualityDonutChart — 分段渲染', () => {
  it('总数等于四类之和并按数量生成扇区', () => {
    const wrapper = setup({ passed: 5, warning: 3, pendingReview: 1, rejected: 1 })

    expect(wrapper.find('.donut-total').text()).toBe('10')
    expect(wrapper.findAll('.donut-segment')).toHaveLength(4)
    expect(wrapper.findAll('circle')).toHaveLength(0)
  })

  it('扇区颜色与图例颜色一致', () => {
    const wrapper = setup({ passed: 5, warning: 3, pendingReview: 1, rejected: 1 })

    const segments = wrapper.findAll('.donut-segment')
    expect(segments.map((s) => s.attributes('fill'))).toEqual([
      '#67c23a',
      '#e6a23c',
      '#909399',
      '#f56c6c',
    ])
    expect(wrapper.findAll('.legend-color').map((c) => c.attributes('style'))).toEqual([
      'background: #67c23a;',
      'background: #e6a23c;',
      'background: #909399;',
      'background: #f56c6c;',
    ])
  })

  it('数量为 0 的分段不生成路径但保留图例', () => {
    const wrapper = setup({ passed: 4 })

    const segments = wrapper.findAll('.donut-segment')
    expect(segments).toHaveLength(4)
    expect(segments[0].attributes('d')).not.toBe('')
    expect(segments[1].attributes('d')).toBe('')
    expect(wrapper.findAll('.legend-item')[1].find('.legend-count').text()).toBe('0')
  })

  it('扇区标题展示标签与条数', () => {
    const wrapper = setup({ passed: 2, rejected: 1 })

    const titles = wrapper.findAll('.donut-segment title').map((t) => t.text())
    expect(titles[0]).toBe('通过: 2 条')
    expect(titles[3]).toBe('不建议保存: 1 条')
  })

  it('全部命中唯一状态时生成整圆路径', () => {
    const wrapper = setup({ passed: 3 })

    expect(wrapper.findAll('.donut-segment')[0].attributes('d')).toContain('A')
    expect(wrapper.find('.donut-total').text()).toBe('3')
  })

  it('size 透传到画布尺寸', () => {
    const wrapper = setup({ passed: 1, size: 200 })

    expect(wrapper.find('svg').attributes('width')).toBe('200')
    expect(wrapper.find('svg').attributes('height')).toBe('200')
    expect(wrapper.find('svg').attributes('viewBox')).toBe('0 0 200 200')
  })
})

describe('QualityDonutChart — 交互', () => {
  it('点击扇区抛出对应状态', async () => {
    const wrapper = setup({ passed: 1, warning: 1 })

    await wrapper.findAll('.donut-segment')[1].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['warning']])
  })

  it('点击已激活扇区抛出 null 取消过滤', async () => {
    const wrapper = setup({ passed: 1, warning: 1, activeFilter: 'passed' })

    await wrapper.findAll('.donut-segment')[0].trigger('click')

    expect(wrapper.emitted('select')).toEqual([[null]])
  })

  it('点击图例同样触发选择', async () => {
    const wrapper = setup({ passed: 1, rejected: 1 })

    await wrapper.findAll('.legend-item')[3].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['rejected']])
  })

  it('激活态与淡化态按 activeFilter 标记', () => {
    const wrapper = setup({ passed: 1, warning: 1, activeFilter: 'passed' })

    const segments = wrapper.findAll('.donut-segment')
    expect(segments[0].classes()).toContain('active')
    expect(segments[1].classes()).toContain('dim')

    const legends = wrapper.findAll('.legend-item')
    expect(legends[0].classes()).toContain('active')
    expect(legends[1].classes()).toContain('dim')
  })
})
