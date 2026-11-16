import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/execution/useTestExecution', () => ({
  useTestExecution: () => state.current,
  ISSUE_TYPE_LABELS: {
    product_bug: '产品缺陷',
    case_issue: '用例问题',
  },
  ISSUE_TYPE_COLORS: {
    product_bug: 'danger',
    case_issue: 'warning',
  },
}))

import ExecutionStepsPanel from '../ExecutionStepsPanel.vue'

const actions = {
  selectStep: vi.fn(),
  handleCorrectCase: vi.fn(),
  handleAnalyzeFailure: vi.fn(),
}

function makeStep(over: Record<string, unknown> = {}) {
  return {
    action: 'click',
    display_action: '',
    description: '点击登录按钮',
    target: '#login',
    status: 'passed',
    execution_time: 2,
    timestamp: '2026-11-16T08:00:00Z',
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    viewMode: ref('list'),
    executionSteps: ref([
      makeStep({ status: 'passed' }),
      makeStep({
        status: 'failed',
        display_action: '输入账号',
        target: null,
        execution_time: null,
      }),
      makeStep({ status: 'running' }),
      makeStep({ status: 'pending' }),
    ]),
    currentStepIndex: ref(1),
    issueTypeMap: ref<Record<number, string>>({ 1: 'case_issue' }),
    analysisLoading: ref(false),
    getStepStatusType: (status: string) => (status === 'failed' ? 'danger' : 'success'),
    getStepStatusText: (status: string) => ({ passed: '通过', failed: '失败' })[status] ?? status,
    getTimelineItemType: (status: string) => (status === 'passed' ? 'success' : 'primary'),
    getTimelineIcon: () => null,
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPanel(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(ExecutionStepsPanel)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ExecutionStepsPanel — 列表视图', () => {
  it('渲染步骤：动作文案优先 display_action，其次 description', async () => {
    const wrapper = await mountPanel()

    const items = wrapper.findAll('.step-item')
    expect(items).toHaveLength(4)
    expect(items[0].find('.step-action').text()).toBe('点击登录按钮')
    expect(items[1].find('.step-action').text()).toBe('输入账号')
    expect(items[0].find('.step-number').text()).toBe('1')
  })

  it('按状态附加样式并展示状态标签与耗时', async () => {
    const wrapper = await mountPanel()

    const items = wrapper.findAll('.step-item')
    expect(items[0].classes()).toContain('success')
    expect(items[1].classes()).toContain('failed')
    expect(items[1].classes()).toContain('active')
    expect(items[2].classes()).toContain('running')
    expect(items[0].text()).toContain('通过')
    expect(items[0].find('.execution-time').text()).toBe('2s')
    // 无执行时长时不渲染
    expect(items[1].find('.execution-time').exists()).toBe(false)
  })

  it('有 target 时展示目标元素', async () => {
    const wrapper = await mountPanel()

    expect(wrapper.findAll('.step-item')[0].find('.step-target').text()).toBe('#login')
    expect(wrapper.findAll('.step-item')[1].find('.step-target').exists()).toBe(false)
  })

  it('点击步骤透传索引', async () => {
    const wrapper = await mountPanel()

    await wrapper.findAll('.step-item')[2].trigger('click')

    expect(actions.selectStep).toHaveBeenCalledWith(2)
  })

  it('失败步骤展示问题类型与纠正、分析按钮', async () => {
    const wrapper = await mountPanel()

    const failed = wrapper.findAll('.step-item')[1]
    expect(failed.find('.issue-tag').text()).toBe('用例问题')

    const buttons = failed.findAll('.step-actions .el-button')
    expect(buttons.map((n) => n.text())).toEqual(['纠正用例', '分析失败'])

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(actions.handleCorrectCase).toHaveBeenCalledWith(
      expect.objectContaining({ display_action: '输入账号' }),
      1
    )
    expect(actions.handleAnalyzeFailure).toHaveBeenCalledWith(expect.any(Object), 1)
  })

  it('判定为产品缺陷时隐藏纠正用例入口', async () => {
    const wrapper = await mountPanel({ issueTypeMap: ref({ 1: 'product_bug' }) })

    const failed = wrapper.findAll('.step-item')[1]
    expect(failed.find('.issue-tag').text()).toBe('产品缺陷')
    expect(failed.findAll('.step-actions .el-button').map((n) => n.text())).toEqual(['分析失败'])
  })

  it('分析进行中按钮进入 loading 态', async () => {
    const wrapper = await mountPanel({ analysisLoading: ref(true) })

    const buttons = wrapper.findAll('.step-item')[1].findAll('.step-actions .el-button')
    expect(buttons[buttons.length - 1].classes()).toContain('is-loading')
  })
})

describe('ExecutionStepsPanel — 时间轴视图', () => {
  it('切换视图模式后渲染时间轴', async () => {
    const wrapper = await mountPanel({ viewMode: ref('timeline') })

    expect(wrapper.find('.steps-list').exists()).toBe(false)
    expect(wrapper.findAll('.el-timeline-item')).toHaveLength(4)
    expect(wrapper.findAll('.timeline-step')[0].text()).toContain('点击登录按钮')
  })

  it('点击时间轴条目透传索引', async () => {
    const wrapper = await mountPanel({ viewMode: ref('timeline') })

    await wrapper.findAll('.timeline-step')[3].trigger('click')

    expect(actions.selectStep).toHaveBeenCalledWith(3)
  })

  it('视图模式切换控件透传 v-model', async () => {
    const wrapper = await mountPanel()

    wrapper.findComponent({ name: 'ElRadioGroup' }).vm.$emit('update:modelValue', 'timeline')
    await flushPromises()

    expect((ctx.viewMode as { value: string }).value).toBe('timeline')
  })
})
