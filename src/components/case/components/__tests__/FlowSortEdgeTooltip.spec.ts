import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref, nextTick } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/flowSort/useFlowSortEditor', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/flowSort/useFlowSortEditor')>()
  return { ...actual, useFlowSortEditor: () => mockCtx.current }
})

import FlowSortEdgeTooltip from '../FlowSortEdgeTooltip.vue'

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { disabled: { type: Boolean, default: false } },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: '<div v-if="modelValue" class="el-dialog"><slot /></div>',
})

const stubs = {
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  ElDialog: ElDialogStub,
}

function edgeData(overrides: Record<string, unknown> = {}) {
  return {
    id: 'e1',
    label: '进入首页',
    data: { edge_type: 'branch' },
    ...overrides,
  }
}

function setup() {
  const ctx = {
    edgeTooltipVisible: ref(false),
    edgeTooltipData: ref<Record<string, unknown> | null>(null),
    edgeTooltipPosition: ref({ x: 10, y: 20 }),
    isPlaying: ref(false),
    hasPrevStep: ref(false),
    hasNextStep: ref(true),
    playPath: ref<Record<string, unknown>[]>([]),
    currentPlayIndex: ref(0),
    showBranchChoice: ref(false),
    vueFlowEdges: ref<unknown[]>([]),
    vueFlowNodes: ref<unknown[]>([]),
    onEdgeTooltipEnter: vi.fn(),
    onEdgeTooltipLeave: vi.fn(),
    handleEditEdge: vi.fn(),
    handleDeleteEdge: vi.fn(),
    prevStep: vi.fn(),
    nextStep: vi.fn(),
    stopPlayback: vi.fn(),
    followBranch: vi.fn(),
    getStepInfo: vi.fn(() => '第 1 / 2 步'),
  }
  mockCtx.current = ctx
  const wrapper = mount(FlowSortEdgeTooltip, { global: { stubs } })
  return { ctx, wrapper }
}

describe('FlowSortEdgeTooltip — 连线气泡', () => {
  it('不可见时不渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.edge-tooltip').exists()).toBe(false)
  })

  it('可见时按类型展示标签与定位', async () => {
    const { ctx, wrapper } = setup()
    ctx.edgeTooltipVisible.value = true
    ctx.edgeTooltipData.value = edgeData()
    await nextTick()

    const tip = wrapper.find('.edge-tooltip')
    expect(tip.exists()).toBe(true)
    expect(tip.attributes('style')).toContain('left: 10px')
    expect(tip.attributes('style')).toContain('top: 20px')
    expect(wrapper.find('.el-tag').text()).toBe('分支')
    expect(wrapper.find('.tooltip-label-text').text()).toBe('进入首页')
  })

  it('未知类型回退默认标签与普通跳转文案', async () => {
    const { ctx, wrapper } = setup()
    ctx.edgeTooltipVisible.value = true
    ctx.edgeTooltipData.value = edgeData({ data: {}, label: '' })
    await nextTick()

    expect(wrapper.find('.el-tag').text()).toBe('跳转')
    expect(wrapper.text()).toContain('普通跳转')
  })

  it('按字段渲染触发条件/动作/前置操作/备注', async () => {
    const { ctx, wrapper } = setup()
    ctx.edgeTooltipVisible.value = true
    ctx.edgeTooltipData.value = edgeData({
      data: {
        edge_type: 'exception',
        condition: '接口超时',
        trigger_action: '点击取消',
        pre_action: '等待加载',
        note: '仅测试环境',
      },
    })
    await nextTick()

    const text = wrapper.text()
    expect(text).toContain('触发条件：')
    expect(text).toContain('接口超时')
    expect(text).toContain('触发动作：')
    expect(text).toContain('点击取消')
    expect(text).toContain('前置操作：')
    expect(text).toContain('等待加载')
    expect(text).toContain('备注：')
    expect(text).toContain('仅测试环境')
    expect(text).not.toContain('普通跳转')
  })

  it('悬停与编辑/删除按钮回调', async () => {
    const { ctx, wrapper } = setup()
    const data = edgeData()
    ctx.edgeTooltipVisible.value = true
    ctx.edgeTooltipData.value = data
    await nextTick()

    await wrapper.find('.edge-tooltip').trigger('mouseenter')
    await wrapper.find('.edge-tooltip').trigger('mouseleave')
    await wrapper.find('.tooltip-edit-btn').trigger('click')
    await wrapper.find('.tooltip-delete-btn').trigger('click')

    expect(ctx.onEdgeTooltipEnter).toHaveBeenCalledTimes(1)
    expect(ctx.onEdgeTooltipLeave).toHaveBeenCalledTimes(1)
    expect(ctx.handleEditEdge).toHaveBeenCalledWith(data)
    expect(ctx.handleDeleteEdge).toHaveBeenCalledWith(data)
  })
})

describe('FlowSortEdgeTooltip — 回放控制条', () => {
  it('未播放时不渲染控制条', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.play-controls').exists()).toBe(false)
  })

  it('播放中展示进度与当前页名，首步禁用上一步', async () => {
    const { ctx, wrapper } = setup()
    ctx.isPlaying.value = true
    ctx.playPath.value = [{ nodeId: 'n1', screenName: '登录页' }, { nodeId: 'n2' }]
    await nextTick()

    expect(wrapper.find('.play-step-info').text()).toBe('第 1 / 2 步')
    expect(wrapper.find('.play-current-name').text()).toBe('登录页')

    const buttons = wrapper.findAll('.play-controls button')
    expect(buttons[0].text()).toContain('上一步')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].text()).toContain('下一步')
    expect(buttons[1].attributes('disabled')).toBeUndefined()
  })

  it('末步禁用下一步，分支步除外', async () => {
    const { ctx, wrapper } = setup()
    ctx.isPlaying.value = true
    ctx.hasNextStep.value = false
    ctx.playPath.value = [{ nodeId: 'n1', isBranchChoice: false }]
    await nextTick()

    expect(wrapper.findAll('.play-controls button')[1].attributes('disabled')).toBeDefined()

    ctx.playPath.value = [{ nodeId: 'n1', isBranchChoice: true }]
    await nextTick()
    expect(wrapper.findAll('.play-controls button')[1].attributes('disabled')).toBeUndefined()
  })

  it('上一步/下一步/退出按钮触发对应动作', async () => {
    const { ctx, wrapper } = setup()
    ctx.isPlaying.value = true
    ctx.hasPrevStep.value = true
    ctx.playPath.value = [{ nodeId: 'n1' }, { nodeId: 'n2' }]
    await nextTick()

    const buttons = wrapper.findAll('.play-controls button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')

    expect(ctx.prevStep).toHaveBeenCalledTimes(1)
    expect(ctx.nextStep).toHaveBeenCalledTimes(1)
    expect(ctx.stopPlayback).toHaveBeenCalledTimes(1)
    expect(buttons[2].text()).toContain('退出')
  })
})

describe('FlowSortEdgeTooltip — 分支选择弹窗', () => {
  it('展示分支选项并可跟随', async () => {
    const { ctx, wrapper } = setup()
    ctx.playPath.value = [
      {
        nodeId: 'n1',
        isBranchChoice: true,
        branchOptions: [
          { edgeId: 'e1', targetNodeId: 'b1', targetName: '登录失败页' },
          { edgeId: 'e2', targetNodeId: 'b2', targetName: '验证码页' },
        ],
      },
    ]
    ctx.showBranchChoice.value = true
    await nextTick()

    const options = wrapper.findAll('.branch-option')
    expect(options).toHaveLength(3)
    expect(options[0].text()).toContain('登录失败页')

    await options[0].trigger('click')

    expect(ctx.followBranch).toHaveBeenCalledWith(
      'b1',
      ctx.vueFlowEdges.value,
      ctx.vueFlowNodes.value
    )
  })

  it('继续主干流程关闭弹窗并前进', async () => {
    const { ctx, wrapper } = setup()
    ctx.playPath.value = [{ nodeId: 'n1', branchOptions: [] }]
    ctx.showBranchChoice.value = true
    await nextTick()

    await wrapper.findAll('.branch-option')[0].trigger('click')

    expect(ctx.showBranchChoice.value).toBe(false)
    expect(ctx.nextStep).toHaveBeenCalledTimes(1)
  })
})
