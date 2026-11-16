import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'

const storeMock = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => storeMock.current,
}))

import GenerateCaseStepSection from '../GenerateCaseStepSection.vue'

const ElTimelineStub = defineComponent({
  name: 'ElTimeline',
  template: '<div class="el-timeline"><slot /></div>',
})

const ElTimelineItemStub = defineComponent({
  name: 'ElTimelineItem',
  props: { timestamp: { type: String, default: '' } },
  template: '<div class="el-timeline-item" :data-timestamp="timestamp"><slot /></div>',
})

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: '<div class="el-card"><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { disabled: { type: Boolean, default: false } },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  template: '<span class="el-tag"><slot /></span>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<input class="el-input" :value="modelValue" :placeholder="placeholder" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const stubs = {
  ElTimeline: ElTimelineStub,
  ElTimelineItem: ElTimelineItemStub,
  ElCard: ElCardStub,
  ElButton: ElButtonStub,
  ElTag: ElTagStub,
  ElEmpty: ElEmptyStub,
  ElInput: ElInputStub,
}

function setup(
  options: {
    isEditingResult?: boolean
    viewingSteps?: Array<Record<string, unknown>>
    editingSteps?: Array<Record<string, unknown>>
  } = {}
) {
  const store = reactive({
    isEditingResult: options.isEditingResult ?? false,
    viewingCase: { steps: options.viewingSteps ?? [] },
    editingCase: { steps: options.editingSteps ?? [] },
    addEditStep: vi.fn(),
    removeEditStep: vi.fn(),
    cleanExpectedResult: vi.fn((value: string) => `clean(${value})`),
  })
  storeMock.current = store

  const wrapper = mount(GenerateCaseStepSection, { global: { stubs } })
  return { store, wrapper }
}

describe('GenerateCaseStepSection — 查看态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('按步骤渲染时间线与内容', () => {
    const { store, wrapper } = setup({
      viewingSteps: [
        {
          step: 1,
          description: '打开登录页',
          display_action: '点击登录按钮',
          expected_result: '进入首页',
          test_data: { 用户名: 'admin' },
        },
        {
          step: 2,
          action: '输入 admin',
          expected_result: '输入成功',
        },
      ],
    })

    const items = wrapper.findAll('.el-timeline-item')
    expect(items).toHaveLength(2)
    expect(items[0].attributes('data-timestamp')).toBe('步骤 1')
    expect(items[0].text()).toContain('打开登录页')
    expect(items[0].text()).toContain('点击登录按钮')
    expect(items[0].find('.el-tag').text()).toBe('用户名: admin')
    expect(items[1].text()).toContain('输入 admin')
    expect(store.cleanExpectedResult).toHaveBeenCalledWith('进入首页')
    expect(wrapper.text()).toContain('clean(进入首页)')
  })

  it('缺少 step 字段时以序号兜底，操作回退 description', () => {
    const { wrapper } = setup({
      viewingSteps: [{ description: '仅描述', expected_result: '' }],
    })

    const item = wrapper.find('.el-timeline-item')
    expect(item.attributes('data-timestamp')).toBe('步骤 1')
    expect(item.text()).toContain('仅描述')
  })

  it('无 test_data 时不渲染数据区块', () => {
    const { wrapper } = setup({
      viewingSteps: [{ step: 1, description: 'A', expected_result: 'B' }],
    })

    expect(wrapper.find('.step-data').exists()).toBe(false)
  })

  it('查看态不渲染添加步骤按钮', () => {
    const { wrapper } = setup({
      viewingSteps: [{ step: 1, description: 'A', expected_result: 'B' }],
    })

    expect(wrapper.text()).not.toContain('添加步骤')
  })

  it('步骤为空时展示空态', () => {
    const { wrapper } = setup({ viewingSteps: [] })

    expect(wrapper.find('.empty-steps .el-empty').text()).toBe('暂无测试步骤')
  })
})

describe('GenerateCaseStepSection — 编辑态', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('编辑态展示添加按钮并渲染可编辑卡片', () => {
    const { store, wrapper } = setup({
      isEditingResult: true,
      editingSteps: [{ action: '点击', expected_result: '成功', param: '' }],
    })

    const addButton = wrapper.findAll('.el-button')[0]
    expect(addButton.text()).toContain('添加步骤')

    return addButton.trigger('click').then(() => {
      expect(store.addEditStep).toHaveBeenCalledTimes(1)
      expect(wrapper.findAll('.editable-step-card')).toHaveLength(1)
      expect(wrapper.find('.step-num').text()).toBe('步骤 1')
      expect(wrapper.find('.el-timeline').exists()).toBe(false)
    })
  })

  it('仅一个步骤时删除按钮禁用', () => {
    const { wrapper } = setup({
      isEditingResult: true,
      editingSteps: [{ action: 'A', expected_result: 'B' }],
    })

    const deleteBtn = wrapper.find('.step-card-header .el-button')
    expect(deleteBtn.attributes('disabled')).toBeDefined()
  })

  it('多步骤时可删除并回传索引', async () => {
    const { store, wrapper } = setup({
      isEditingResult: true,
      editingSteps: [
        { action: 'A', expected_result: 'B' },
        { action: 'C', expected_result: 'D' },
      ],
    })

    const deleteButtons = wrapper.findAll('.step-card-header .el-button')
    expect(deleteButtons[1].attributes('disabled')).toBeUndefined()

    await deleteButtons[1].trigger('click')
    expect(store.removeEditStep).toHaveBeenCalledWith(1)
  })

  it('输入框双向写回步骤字段', async () => {
    const steps = [{ action: 'A', expected_result: 'B', param: 'p' }]
    const { wrapper } = setup({ isEditingResult: true, editingSteps: steps })

    const inputs = wrapper.findAll('.editable-step-card .el-input')
    await inputs[0].setValue('新操作')
    await inputs[1].setValue('新预期')
    await inputs[2].setValue('新参数')

    expect(steps[0]).toMatchObject({
      action: '新操作',
      expected_result: '新预期',
      param: '新参数',
    })
  })

  it('编辑态无步骤时给出提示文案', () => {
    const { wrapper } = setup({ isEditingResult: true, editingSteps: [] })

    expect(wrapper.find('.empty-steps-hint').text()).toContain('暂无步骤，点击上方"添加步骤"')
  })
})
