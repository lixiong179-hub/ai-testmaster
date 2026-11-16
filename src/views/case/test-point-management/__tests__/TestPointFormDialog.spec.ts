import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  validate: vi.fn(),
  resetFields: vi.fn(),
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: { create: mocks.create, update: mocks.update },
}))

import TestPointFormDialog from '../TestPointFormDialog.vue'

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['close'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: {
    model: { type: Object, default: () => ({}) },
    rules: { type: Object, default: () => ({}) },
  },
  setup(_props, { slots, expose }) {
    expose({ validate: mocks.validate, resetFields: mocks.resetFields })
    return () => h('form', { class: 'el-form' }, slots.default?.())
  },
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' }, prop: { type: String, default: '' } },
  template:
    '<div class="el-form-item" :data-label="label" :data-prop="prop"><label>{{ label }}</label><slot /></div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    type: { type: String, default: 'text' },
  },
  template:
    '<input class="el-input" :data-type="type" :value="modelValue" :placeholder="placeholder" />',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: { modelValue: { type: [Number, String], default: undefined } },
  template: '<div class="el-select" :data-value="modelValue"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :data-loading="loading" @click="$emit(\'click\')"><slot /></button>',
})

const stubs = {
  ElDialog: ElDialogStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElInput: ElInputStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElButton: ElButtonStub,
}

type DialogProps = {
  modelValue: boolean
  projectId: number
  editingPoint: Record<string, unknown> | null
}

function setup(overrides: Partial<DialogProps> = {}) {
  const props: DialogProps = {
    modelValue: true,
    projectId: 9,
    editingPoint: null,
    ...overrides,
  }
  const wrapper = mount(TestPointFormDialog, {
    props: props as never,
    global: { stubs },
  })
  return { wrapper }
}

function inputByPlaceholder(wrapper: ReturnType<typeof setup>['wrapper'], placeholder: string) {
  return wrapper.find(`.el-input[placeholder="${placeholder}"]`)
}

async function submit(wrapper: ReturnType<typeof setup>['wrapper']) {
  await wrapper.findAll('.el-dialog__footer .el-button')[1].trigger('click')
  await flushPromises()
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.validate.mockResolvedValue(true)
  mocks.create.mockResolvedValue({ id: 1 })
  mocks.update.mockResolvedValue({ id: 1 })
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
})

describe('TestPointFormDialog — 标题与说明', () => {
  it('新增模式展示创建标题与引导文案', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('新增测试点')
    expect(wrapper.find('.hero-title').text()).toBe('创建新的测试点条目')
    expect(wrapper.find('.hero-subtitle').text()).toContain('建议补齐模块、功能和 AI 提示词')
  })

  it('编辑模式展示更新标题', () => {
    const { wrapper } = setup({
      editingPoint: { id: 3, module: '支付', point: '幂等', priority: 3, ai_prompt: '' },
    })

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('编辑测试点')
    expect(wrapper.find('.hero-title').text()).toBe('更新测试点信息')
  })

  it('modelValue 为 false 时不渲染内容', () => {
    const { wrapper } = setup({ modelValue: false })

    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })
})

describe('TestPointFormDialog — 表单回填', () => {
  it('新增时使用默认值与当前项目', () => {
    const { wrapper } = setup()

    expect(inputByPlaceholder(wrapper, '如：登录中心').attributes('value')).toBe('')
    expect(inputByPlaceholder(wrapper, '如：登录中心').attributes('data-type')).toBe('text')
    expect(
      wrapper.find('.el-input[placeholder="描述本条测试点关注的行为、校验或边界情况"]').exists()
    ).toBe(true)
    expect(wrapper.find('.el-select').attributes('data-value')).toBe('2')
  })

  it('编辑时回填既有测试点字段与优先级', () => {
    const { wrapper } = setup({
      editingPoint: {
        id: 3,
        module: '支付',
        point: '重复支付幂等',
        priority: 3,
        ai_prompt: '提示词',
      },
    })

    expect(inputByPlaceholder(wrapper, '如：登录中心').attributes('value')).toBe('支付')
    expect(
      wrapper
        .find('.el-input[placeholder="描述本条测试点关注的行为、校验或边界情况"]')
        .attributes('value')
    ).toBe('重复支付幂等')
    expect(
      wrapper.find('.el-input[placeholder="可选，补充 AI 生成上下文"]').attributes('value')
    ).toBe('提示词')
    expect(wrapper.find('.el-select').attributes('data-value')).toBe('3')
  })

  it('优先级下拉提供高中低三档', () => {
    const { wrapper } = setup()

    const item = wrapper.find('.el-form-item[data-prop="priority"]')
    expect(item.findAll('.el-option').map((o) => o.text())).toEqual(['高', '中', '低'])
  })

  it('关闭时重置表单字段', async () => {
    const { wrapper } = setup()
    mocks.resetFields.mockClear()

    await wrapper.setProps({ modelValue: false })

    expect(mocks.resetFields).toHaveBeenCalledTimes(1)
  })
})

describe('TestPointFormDialog — 提交', () => {
  it('新增保存成功后提示、抛 success 并关闭', async () => {
    const { wrapper } = setup()

    await submit(wrapper)

    expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: 9,
        module: '',
        point: '',
        priority: 2,
        ai_prompt: '',
      })
    )
    expect(mocks.update).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('测试点创建成功')
    expect(wrapper.emitted('success')).toHaveLength(1)
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('编辑保存走更新接口并携带 id', async () => {
    const { wrapper } = setup({
      editingPoint: { id: 7, module: '支付', point: '幂等', priority: 1, ai_prompt: '' },
    })

    await submit(wrapper)

    expect(mocks.update).toHaveBeenCalledWith(7, expect.objectContaining({ module: '支付' }))
    expect(mocks.create).not.toHaveBeenCalled()
    expect(ElMessage.success).toHaveBeenCalledWith('测试点更新成功')
  })

  it('校验失败时不提交', async () => {
    mocks.validate.mockResolvedValue(false)
    const { wrapper } = setup()

    await submit(wrapper)

    expect(mocks.create).not.toHaveBeenCalled()
    expect(wrapper.emitted('success')).toBeUndefined()
  })

  it('接口异常时展示错误信息且不关闭弹窗', async () => {
    mocks.create.mockRejectedValue(new Error('模块已存在'))
    const { wrapper } = setup()

    await submit(wrapper)

    expect(ElMessage.error).toHaveBeenCalledWith('模块已存在')
    expect(wrapper.emitted('success')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('取消按钮直接关闭弹窗', async () => {
    const { wrapper } = setup()

    await wrapper.findAll('.el-dialog__footer .el-button')[0].trigger('click')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('弹窗自带关闭事件同样触发关闭', () => {
    const { wrapper } = setup()

    wrapper.findComponent(ElDialogStub).vm.$emit('close')

    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })
})
