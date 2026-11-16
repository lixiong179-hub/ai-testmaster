import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import FlowCompletenessPanel from '../FlowCompletenessPanel.vue'
import type { FlowStats, FlowStatsIssue } from '@/composables/useFlowStats'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  emits: ['click'],
  template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
})

function stats(overrides: Partial<FlowStats> = {}): FlowStats {
  return {
    totalNodes: 8,
    mainNodes: 4,
    branchNodes: 2,
    exceptionNodes: 1,
    bypassNodes: 1,
    totalEdges: 7,
    normalEdges: 3,
    branchEdges: 2,
    exceptionEdges: 1,
    bypassEdges: 1,
    orphanNodes: 0,
    missingConditionEdges: 0,
    completenessScore: 85,
    ...overrides,
  }
}

function mountPanel(
  props: { visible?: boolean; stats?: FlowStats; issues?: FlowStatsIssue[] } = {}
) {
  return mount(FlowCompletenessPanel, {
    props: {
      visible: true,
      stats: stats(),
      issues: [],
      ...props,
    },
    global: { stubs: { ElIcon: ElIconStub, ElButton: ElButtonStub } },
  })
}

describe('FlowCompletenessPanel — 可见性与评分', () => {
  it('不可见时不渲染面板', () => {
    const wrapper = mountPanel({ visible: false })

    expect(wrapper.find('.flow-completeness-panel').exists()).toBe(false)
  })

  it.each([
    [100, 'score-good', '完整度良好'],
    [80, 'score-good', '完整度良好'],
    [79, 'score-warn', '需要调整'],
    [50, 'score-warn', '需要调整'],
    [49, 'score-bad', '存在严重缺失'],
    [0, 'score-bad', '存在严重缺失'],
  ])('评分 %i 对应 %s / %s', (score, levelClass, label) => {
    const wrapper = mountPanel({ stats: stats({ completenessScore: score }) })

    expect(wrapper.find('.score-ring').classes()).toContain(levelClass)
    expect(wrapper.find('.score-value').text()).toBe(String(score))
    expect(wrapper.find('.score-label').text()).toBe(label)
  })
})

describe('FlowCompletenessPanel — 统计展示', () => {
  it('渲染节点与连线统计', () => {
    const wrapper = mountPanel()

    const items = wrapper.findAll('.stat-item')
    expect(items.map((i) => i.text().replace(/\s+/g, ''))).toEqual([
      '主干4',
      '分支2',
      '异常1',
      '弹窗1',
      '正常3',
      '分支2',
      '异常1',
      '弹窗1',
    ])
    expect(wrapper.findAll('.stats-section .section-title').map((t) => t.text())).toEqual([
      '节点统计',
      '连线统计',
    ])
  })
})

describe('FlowCompletenessPanel — 问题提示', () => {
  it('有 error 与 warning 问题时按类型着色', () => {
    const wrapper = mountPanel({
      issues: [
        { type: 'error', message: '存在 2 个孤立节点' },
        { type: 'warning', message: '有 1 条分支连线缺少条件' },
      ],
    })

    const items = wrapper.findAll('.issue-item')
    expect(items).toHaveLength(2)
    expect(items[0].classes()).toContain('issue-error')
    expect(items[0].text()).toContain('存在 2 个孤立节点')
    expect(items[1].classes()).toContain('issue-warning')
    expect(wrapper.find('.all-clear').exists()).toBe(false)
  })

  it('无问题且有节点时展示可继续生成的提示', () => {
    const wrapper = mountPanel({ issues: [] })

    expect(wrapper.find('.issues-section').exists()).toBe(false)
    expect(wrapper.find('.all-clear').text()).toContain('流程完整，可继续生成')
  })

  it('无节点且无问题时既不显示问题区也不显示通过提示', () => {
    const wrapper = mountPanel({ issues: [], stats: stats({ totalNodes: 0 }) })

    expect(wrapper.find('.issues-section').exists()).toBe(false)
    expect(wrapper.find('.all-clear').exists()).toBe(false)
  })
})

describe('FlowCompletenessPanel — 关闭事件', () => {
  it('点击关闭按钮抛 update:visible=false', async () => {
    const wrapper = mountPanel()

    await wrapper.find('.panel-close-btn').trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })
})
