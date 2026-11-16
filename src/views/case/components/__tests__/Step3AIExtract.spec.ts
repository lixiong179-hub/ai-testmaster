import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/useTestPointExtract', () => ({
  useTestPointExtract: () => state.current,
}))

import Step3AIExtract from '../Step3AIExtract.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  props: { size: { type: [Number, String], default: '' }, color: { type: String, default: '' } },
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' }, disabled: { type: Boolean, default: false } },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}<slot name="description" /><slot /></div>',
})

const ElSkeletonStub = defineComponent({
  name: 'ElSkeleton',
  props: { rows: { type: Number, default: 0 }, animated: { type: Boolean, default: false } },
  template: '<div class="el-skeleton" />',
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: {
    percentage: { type: Number, default: 0 },
    status: { type: String, default: '' },
  },
  template: '<div class="el-progress" :data-status="status">{{ percentage }}%</div>',
})

const ElResultStub = defineComponent({
  name: 'ElResult',
  props: { title: { type: String, default: '' }, subTitle: { type: String, default: '' } },
  template:
    '<div class="el-result">{{ title }}<p class="result-sub">{{ subTitle }}</p><slot name="extra" /></div>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElEmpty: ElEmptyStub,
  ElSkeleton: ElSkeletonStub,
  ElProgress: ElProgressStub,
  ElResult: ElResultStub,
}

const resource = {
  id: 5,
  display_name: '需求文档.pdf',
  type_label: '需求文档',
  size_text: '2.5 MB',
  resource_type: 'requirement',
}

function setup(
  options: {
    resource?: Record<string, unknown> | null
    extracting?: boolean
    error?: string
    points?: Array<{ module: string; priority: number }>
  } = {}
) {
  const ctx = {
    selectedResource: ref(options.resource === undefined ? resource : options.resource),
    extracting: ref(options.extracting ?? false),
    progress: ref(42),
    progressStatus: ref(''),
    progressText: ref('正在解析需求文档...'),
    errorMessage: ref(options.error ?? ''),
    testPoints: ref(options.points ?? []),
    moduleCount: ref(3),
    getResourceIcon: vi.fn(() => null),
    getPriorityCount: vi.fn(
      (priority: number) => (options.points ?? []).filter((p) => p.priority === priority).length
    ),
    handleCancel: vi.fn(),
    retryExtract: vi.fn(),
    startExtract: vi.fn(),
    goToNextStep: vi.fn(),
  }
  state.current = ctx

  const wrapper = mount(Step3AIExtract, { global: { stubs } })
  return { ctx, wrapper }
}

const buttonByText = (wrapper: ReturnType<typeof setup>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text().replace(/\s+/g, '') === text)

describe('Step3AIExtract — 资源与待提取态', () => {
  it('展示已选资源信息', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.resource-name').text()).toBe('需求文档.pdf')
    expect(wrapper.find('.resource-meta').text()).toBe('需求文档 · 2.5 MB')
    expect(wrapper.find('.el-icon').exists()).toBe(true)
  })

  it('未选资源时不展示资源卡片', () => {
    const { wrapper } = setup({ resource: null })

    expect(wrapper.find('.selected-resource-card').exists()).toBe(false)
  })

  it('待提取态展示空态与禁用按钮', () => {
    const { wrapper } = setup({ resource: null })

    expect(wrapper.find('.extract-ready').exists()).toBe(true)
    const start = buttonByText(wrapper, '开始提取')!
    expect(start.attributes('disabled')).toBeDefined()
  })

  it('已选资源时可开始提取', async () => {
    const { ctx, wrapper } = setup()

    const start = buttonByText(wrapper, '开始提取')!
    expect(start.attributes('disabled')).toBeUndefined()

    await start.trigger('click')
    expect(ctx.startExtract).toHaveBeenCalledTimes(1)
  })
})

describe('Step3AIExtract — 提取中', () => {
  it('展示骨架屏、进度与取消按钮', async () => {
    const { ctx, wrapper } = setup({ extracting: true })

    expect(wrapper.find('.el-skeleton').exists()).toBe(true)
    expect(wrapper.find('.el-progress').text()).toBe('42%')
    expect(wrapper.find('.progress-text-animated').text()).toBe('正在解析需求文档...')

    await buttonByText(wrapper, '取消提取')!.trigger('click')
    expect(ctx.handleCancel).toHaveBeenCalledTimes(1)
  })

  it('提取中不渲染空态与成功态', () => {
    const { wrapper } = setup({ extracting: true, points: [{ module: 'A', priority: 1 }] })

    expect(wrapper.find('.extract-success').exists()).toBe(false)
    expect(wrapper.find('.extract-ready').exists()).toBe(false)
  })
})

describe('Step3AIExtract — 失败态', () => {
  it('展示错误描述并可重试', async () => {
    const { ctx, wrapper } = setup({ error: '模型超时' })

    const result = wrapper.find('.el-result')
    expect(result.text()).toContain('提取失败')
    expect(result.find('.result-sub').text()).toBe('模型超时')

    await buttonByText(wrapper, '重试')!.trigger('click')
    expect(ctx.retryExtract).toHaveBeenCalledTimes(1)
  })
})

describe('Step3AIExtract — 成功态', () => {
  it('展示总数与优先级/模块统计', () => {
    const { wrapper } = setup({
      points: [
        { module: '登录', priority: 1 },
        { module: '登录', priority: 2 },
        { module: '订单', priority: 3 },
      ],
    })

    expect(wrapper.find('.success-title').text()).toBe('提取成功！')
    expect(wrapper.find('.success-desc').text()).toBe('共提取 3 个测试点')
    expect(wrapper.findAll('.stat-number').map((s) => s.text())).toEqual(['1', '1', '1', '3'])
    expect(wrapper.findAll('.stat-label').map((s) => s.text())).toEqual([
      '高优先级',
      '中优先级',
      '低优先级',
      '模块数',
    ])
  })

  it('下一步与重新提取分别触发回调', async () => {
    const { ctx, wrapper } = setup({ points: [{ module: '登录', priority: 1 }] })

    await buttonByText(wrapper, '下一步：校验结果')!.trigger('click')
    expect(ctx.goToNextStep).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '重新提取')!.trigger('click')
    expect(ctx.retryExtract).toHaveBeenCalledTimes(1)
  })

  it('成功态优先级计数基于 testPoints 实际分布', () => {
    const { wrapper } = setup({
      points: [
        { module: 'A', priority: 1 },
        { module: 'A', priority: 1 },
        { module: 'B', priority: 2 },
      ],
    })

    expect(wrapper.findAll('.stat-number').map((s) => s.text())).toEqual(['2', '1', '0', '3'])
  })
})
