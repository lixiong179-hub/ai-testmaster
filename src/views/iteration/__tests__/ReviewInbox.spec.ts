import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useReviewInbox', () => ({
  useReviewInbox: () => state.current,
}))

import ReviewInbox from '../ReviewInbox.vue'

const actions = {
  toggleHint: vi.fn(),
  onSelectionChange: vi.fn(),
  onTabChange: vi.fn(),
  goBack: vi.fn(),
  fetchDecisions: vi.fn(),
  handleDecide: vi.fn(),
  handleResetDecision: vi.fn(),
  handleUndoDecision: vi.fn(),
  handleUndoFinalize: vi.fn(),
  handleBatchAcceptHighConfidence: vi.fn(),
}

function makeDecision(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    target_kind: 'case',
    target_id: 100 + id,
    ai_verdict: 'keep',
    ai_confidence: 92,
    ai_reason: '用例仍符合需求',
    modification_hint: null,
    deprecate_reason: null,
    human_verdict: null,
    conflict_marker: false,
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  const decisions = over.decisions ?? ref([makeDecision(1), makeDecision(2)])
  return {
    decisions,
    loading: ref(false),
    finalizing: ref(false),
    errorMsg: ref(''),
    reviewStatus: ref('in_progress'),
    activeTab: ref('all'),
    expandedHints: reactive(new Set<number>()),
    tabs: ref([
      { key: 'all', label: '全部', count: 2 },
      { key: 'conflict', label: '冲突', count: 0 },
    ]),
    filteredDecisions: decisions,
    statusTagType: 'warning',
    statusText: '评审中',
    hasHighConfidenceUndecided: ref(true),
    undoWindowOpen: ref(false),
    verdictLabel: (verdict: string) =>
      ({ keep: '采纳', modify: '修改', deprecate: '否决' })[verdict] ?? verdict,
    verdictTagType: () => 'success',
    confidenceColor: () => '#67c23a',
    isSelectable: () => true,
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPage(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(ReviewInbox)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ReviewInbox — 头部操作', () => {
  it('返回按钮触发 goBack', async () => {
    const wrapper = await mountPage()

    const backBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('返回'))!
    await backBtn.trigger('click')

    expect(actions.goBack).toHaveBeenCalledTimes(1)
  })

  it('评审中展示状态标签、批量采纳与最终化按钮', async () => {
    const wrapper = await mountPage()

    expect(wrapper.find('.header-left .el-tag').text()).toBe('评审中')
    expect(wrapper.text()).toContain('批量采纳高置信度 (≥85%)')
    expect(wrapper.text()).toContain('最终化评审')
    expect(wrapper.text()).not.toContain('撤销最终化')
  })

  it('无高置信度待定项时隐藏批量采纳', async () => {
    const wrapper = await mountPage({ hasHighConfidenceUndecided: ref(false) })

    expect(wrapper.text()).not.toContain('批量采纳高置信度')
  })

  it('撤销窗口打开时展示撤销最终化', async () => {
    const wrapper = await mountPage({ undoWindowOpen: ref(true) })

    const undoBtn = wrapper.findAll('.el-button').find((node) => node.text() === '撤销最终化')!
    await undoBtn.trigger('click')

    expect(actions.handleUndoFinalize).toHaveBeenCalledTimes(1)
  })

  it('刷新按钮触发重新加载', async () => {
    const wrapper = await mountPage()

    const refreshBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('刷新'))!
    await refreshBtn.trigger('click')

    expect(actions.fetchDecisions).toHaveBeenCalledTimes(1)
  })

  it('加载中刷新按钮进入 loading 态', async () => {
    const wrapper = await mountPage({ loading: ref(true) })

    const refreshBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('刷新'))!
    expect(refreshBtn.classes()).toContain('is-loading')
  })

  it('点击批量采纳触发对应处理', async () => {
    const wrapper = await mountPage()

    const batchBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('批量采纳'))!
    await batchBtn.trigger('click')

    expect(actions.handleBatchAcceptHighConfidence).toHaveBeenCalledTimes(1)
  })
})

describe('ReviewInbox — 加载态与错误态', () => {
  it('首次加载展示骨架屏', async () => {
    const wrapper = await mountPage({ loading: ref(true), decisions: ref([]) })

    expect(wrapper.find('.el-skeleton').exists()).toBe(true)
    expect(wrapper.find('.decisions-table').exists()).toBe(false)
  })

  it('错误信息以告警条展示', async () => {
    const wrapper = await mountPage({ errorMsg: ref('加载评审项失败') })

    expect(wrapper.find('.el-alert').text()).toContain('加载评审项失败')
    expect(wrapper.find('.decisions-table').exists()).toBe(false)
  })

  it('页签展示各状态计数', async () => {
    const wrapper = await mountPage()

    const labels = wrapper.findAll('.el-tabs__item').map((node) => node.text())
    expect(labels).toEqual(['全部 (2)', '冲突 (0)'])
  })
})

describe('ReviewInbox — 决策表格', () => {
  it('渲染目标 ID、AI 判定与冲突标记', async () => {
    const wrapper = await mountPage({
      decisions: ref([
        makeDecision(1, { conflict_marker: true }),
        makeDecision(2, { ai_verdict: 'deprecate', ai_confidence: null }),
      ]),
    })

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].find('.target-id').text()).toBe('case-101')
    expect(rows[0].text()).toContain('采纳')
    expect(rows[0].text()).toContain('冲突')
    expect(rows[1].text()).toContain('否决')
    // 置信度为空时展示占位符
    expect(rows[1].text()).toContain('—')
  })

  it('点击采纳/修改/否决透传行与判定', async () => {
    const wrapper = await mountPage({ decisions: ref([makeDecision(1)]) })

    const row = wrapper.findAll('.el-table__row')[0]
    const btn = (text: string) => row.findAll('.el-button').find((node) => node.text() === text)!

    await btn('采纳').trigger('click')
    await btn('修改').trigger('click')
    await btn('否决').trigger('click')

    expect(actions.handleDecide).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ id: 1 }),
      'keep'
    )
    expect(actions.handleDecide).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ id: 1 }),
      'modify'
    )
    expect(actions.handleDecide).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({ id: 1 }),
      'deprecate'
    )
  })

  it('修改提示默认收起，展开按钮触发 toggleHint', async () => {
    const wrapper = await mountPage({
      decisions: ref([makeDecision(1, { modification_hint: '补充边界值断言' })]),
    })

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.text()).not.toContain('补充边界值断言')

    const toggleBtn = row.findAll('.el-button').find((node) => node.text().includes('展开提示'))!
    await toggleBtn.trigger('click')

    expect(actions.toggleHint).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('已展开的提示渲染提示文案', async () => {
    ctx = makeCtx({
      decisions: ref([makeDecision(1, { modification_hint: '补充边界值断言' })]),
    })
    ;(ctx.expandedHints as Set<number>).add(1)
    state.current = ctx

    const wrapper = mount(ReviewInbox)
    await flushPromises()

    expect(wrapper.findAll('.el-table__row')[0].text()).toContain('补充边界值断言')
  })

  it('已有人工判定时展示重置按钮', async () => {
    const wrapper = await mountPage({
      decisions: ref([makeDecision(1, { human_verdict: 'modify' })]),
    })

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.find('.human-decision').exists()).toBe(true)
    expect(row.text()).toContain('修改')

    await row
      .findAll('.el-button')
      .find((node) => node.text() === '重置')!
      .trigger('click')
    expect(actions.handleResetDecision).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('评审已最终化时不再提供决策与重置入口', async () => {
    const wrapper = await mountPage({
      reviewStatus: ref('finalized'),
      decisions: ref([makeDecision(1, { human_verdict: 'keep' })]),
    })

    const row = wrapper.findAll('.el-table__row')[0]
    expect(row.find('.decision-buttons').exists()).toBe(false)
    expect(row.text()).not.toContain('重置')
    // 最终化后仍可查看状态，但不显示最终化按钮
    expect(wrapper.text()).not.toContain('最终化评审')
  })

  it('表格选择事件透传选中行', async () => {
    const wrapper = await mountPage()

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [{ id: 1 }])

    expect(actions.onSelectionChange).toHaveBeenCalledWith([{ id: 1 }])
  })

  it('点击页签触发 onTabChange', async () => {
    const wrapper = await mountPage()

    await wrapper.findAll('.el-tabs__item')[1].trigger('click')

    expect(actions.onTabChange).toHaveBeenCalledWith('conflict')
  })
})
