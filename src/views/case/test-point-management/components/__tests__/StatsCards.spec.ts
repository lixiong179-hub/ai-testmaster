import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { TestPointMgmtKey } from '../../useTestPointManagement'
import StatsCards from '../StatsCards.vue'

function setup(priority?: 1 | 2 | 3) {
  const filters = reactive({ priority })
  const ctx = {
    statsTotal: 120,
    highCount: 30,
    mediumCount: 60,
    lowCount: 30,
    generatedCaseCount: 45,
    filters,
    applyPriorityFilter: vi.fn(),
  }

  const wrapper = mount(StatsCards, {
    global: { provide: { [TestPointMgmtKey as symbol]: ctx } },
  })
  return { ctx, filters, wrapper }
}

describe('StatsCards — 数值展示', () => {
  it('渲染五张卡片及对应数值', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.stat-caption').map((n) => n.text())).toEqual([
      '全部测试点',
      '高优先级',
      '中优先级',
      '低优先级',
      '已生成用例',
    ])
    expect(wrapper.findAll('.stat-value').map((n) => n.text())).toEqual([
      '120',
      '30',
      '60',
      '30',
      '45',
    ])
    expect(wrapper.findAll('.stat-label').map((n) => n.text())).toEqual([
      '当前筛选范围内总数',
      '点击快速筛选高优先级',
      '适合常规回归与覆盖补齐',
      '可作为补充储备任务',
      '已绑定到测试用例的累计数量',
    ])
  })

  it('仅前四张为可点击按钮，已生成用例为静态卡片', () => {
    const { wrapper } = setup()

    const cards = wrapper.findAll('.stat-card')
    expect(cards).toHaveLength(5)
    expect(cards.slice(0, 4).every((c) => c.element.tagName === 'BUTTON')).toBe(true)
    expect(cards[4].element.tagName).toBe('DIV')
    expect(cards[4].classes()).toContain('generated')
    expect(cards[4].classes()).toContain('non-clickable')
  })
})

describe('StatsCards — 快捷筛选', () => {
  it('未设置优先级时"全部"卡片高亮', () => {
    const { wrapper } = setup()

    const cards = wrapper.findAll('.stat-card')
    expect(cards[0].classes()).toContain('is-active')
    expect(cards[1].classes()).not.toContain('is-active')
  })

  it.each([1, 2, 3] as const)('优先级 %s 时对应卡片高亮', (priority) => {
    const { wrapper } = setup(priority)

    const active = wrapper.findAll('.stat-card').filter((c) => c.classes().includes('is-active'))
    expect(active).toHaveLength(1)
    expect(active[0].find('.stat-caption').text()).toBe(
      { 1: '高优先级', 2: '中优先级', 3: '低优先级' }[priority]
    )
  })

  it('点击全部卡片清除优先级筛选', async () => {
    const { ctx, wrapper } = setup(1)

    await wrapper.findAll('.stat-card')[0].trigger('click')

    expect(ctx.applyPriorityFilter).toHaveBeenCalledWith(undefined)
  })

  it.each([
    [1, 1],
    [2, 2],
    [3, 3],
  ])('点击第 %s 类卡片应用优先级 %s', async (index, priority) => {
    const { ctx, wrapper } = setup()

    await wrapper.findAll('.stat-card')[index].trigger('click')

    expect(ctx.applyPriorityFilter).toHaveBeenCalledWith(priority)
  })
})
