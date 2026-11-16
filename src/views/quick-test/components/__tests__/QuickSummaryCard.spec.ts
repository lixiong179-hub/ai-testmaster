import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { SEVERITY_LABELS } from '../../quickTestTypes'
import type { SummaryStats } from '../../quickTestTypes'
import QuickSummaryCard from '../QuickSummaryCard.vue'

function makeSummary(over: Record<string, unknown> = {}): SummaryStats {
  return {
    total: 20,
    passed: 15,
    failed: 5,
    pass_rate: 75,
    duration_sec: 90,
    severity_dist: { p0: 1, p1: 2, p2: 0, p3: 3 },
    ...over,
  } as unknown as SummaryStats
}

function mountCard(summary: SummaryStats | null) {
  return mount(QuickSummaryCard, { props: { summary } })
}

describe('QuickSummaryCard — 空态', () => {
  it('无摘要时展示空态', () => {
    const wrapper = mountCard(null)

    expect(wrapper.find('.el-empty').text()).toContain('暂无摘要数据')
    expect(wrapper.find('.summary-body').exists()).toBe(false)
  })
})

describe('QuickSummaryCard — 统计', () => {
  it('渲染通过率环形图与四项统计', () => {
    const wrapper = mountCard(makeSummary())

    const progress = wrapper.findComponent({ name: 'ElProgress' })
    expect(progress.props('percentage')).toBe(75)
    expect(progress.props('type')).toBe('circle')

    const values = wrapper.findAll('.stat-value').map((node) => node.text())
    expect(values).toEqual(['20', '15', '5', '1分30秒'])
    expect(wrapper.findAll('.stat-label').map((node) => node.text())).toEqual([
      '用例总数',
      '通过',
      '失败',
      '耗时',
    ])
  })

  it('耗时不足一分钟展示秒级，非正数展示占位符', () => {
    const wrapper = mountCard(makeSummary({ duration_sec: 45 }))
    expect(wrapper.findAll('.stat-value')[3].text()).toBe('45s')

    const zero = mountCard(makeSummary({ duration_sec: 0 }))
    expect(zero.findAll('.stat-value')[3].text()).toBe('-')
  })

  it('通过率分三档配色', () => {
    expect(
      mountCard(makeSummary({ pass_rate: 90 }))
        .findComponent({ name: 'ElProgress' })
        .props('color')
    ).toBe('#67c23a')
    expect(
      mountCard(makeSummary({ pass_rate: 60 }))
        .findComponent({ name: 'ElProgress' })
        .props('color')
    ).toBe('#e6a23c')
    expect(
      mountCard(makeSummary({ pass_rate: 20 }))
        .findComponent({ name: 'ElProgress' })
        .props('color')
    ).toBe('#f56c6c')
  })

  it('缺陷严重度分布按 P0 置顶展示数量', () => {
    const wrapper = mountCard(makeSummary())

    const items = wrapper.findAll('.dist-item')
    expect(items).toHaveLength(4)
    expect(items.map((node) => node.find('.el-tag').text())).toEqual([
      SEVERITY_LABELS[1],
      SEVERITY_LABELS[2],
      SEVERITY_LABELS[3],
      SEVERITY_LABELS[4],
    ])
    expect(items.map((node) => node.find('.dist-count').text())).toEqual(['1', '2', '0', '3'])
    expect(items[0].classes()).toContain('sev-p0')
  })

  it('缺少严重度分布时按 0 兜底', () => {
    const wrapper = mountCard(makeSummary({ severity_dist: undefined }))

    expect(wrapper.findAll('.dist-count').map((node) => node.text())).toEqual(['0', '0', '0', '0'])
  })
})

describe('QuickSummaryCard — 响应式', () => {
  beforeEach(() => {
    /* 占位，保持与其它 spec 一致的清理习惯 */
  })

  it('摘要更新后统计随之更新', async () => {
    const wrapper = mountCard(makeSummary())

    await wrapper.setProps({ summary: makeSummary({ passed: 18, failed: 2, pass_rate: 90 }) })

    expect(wrapper.findAll('.stat-value')[1].text()).toBe('18')
    expect(wrapper.findComponent({ name: 'ElProgress' }).props('percentage')).toBe(90)
  })

  it('摘要清空后回到空态', async () => {
    const wrapper = mountCard(makeSummary())

    await wrapper.setProps({ summary: null })

    expect(wrapper.find('.el-empty').exists()).toBe(true)
  })
})
