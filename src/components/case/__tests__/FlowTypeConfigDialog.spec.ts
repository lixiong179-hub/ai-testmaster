import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import FlowTypeConfigDialog from '../FlowTypeConfigDialog.vue'

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:modelValue', 'close'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <slot />
      <slot name="footer" />
    </div>
  `,
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  template: '<form class="el-form"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: {
    label: {
      type: String,
      default: '',
    },
  },
  template: `
    <div class="el-form-item">
      <label class="el-form-item__label">{{ label }}</label>
      <div class="el-form-item__content"><slot /></div>
    </div>
  `,
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: `
    <select
      class="el-select"
      :value="modelValue"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <slot />
    </select>
  `,
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: {
    label: {
      type: String,
      default: '',
    },
    value: {
      type: String,
      default: '',
    },
  },
  template: '<option class="el-select-dropdown__item" :value="value">{{ label }}</option>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: {
    modelValue: {
      type: String,
      default: '',
    },
    type: {
      type: String,
      default: 'text',
    },
    placeholder: {
      type: String,
      default: '',
    },
  },
  emits: ['update:modelValue'],
  template: `
    <textarea
      v-if="type === 'textarea'"
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <input
      v-else
      :value="modelValue"
      :placeholder="placeholder"
      @input="$emit('update:modelValue', $event.target.value)"
    />
  `,
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  emits: ['click'],
  template: "<button class='el-button' @click=\"$emit('click')\"><slot /></button>",
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: {
    type: {
      type: String,
      default: '',
    },
  },
  template: '<span class="el-tag" :class="type"><slot /></span>',
})

describe('FlowTypeConfigDialog', () => {
  const mainNodeOptions = [
    { id: 'node_1', screen_id: 1, screen_name: '首页', main_order: 1 },
    { id: 'node_2', screen_id: 2, screen_name: '列表页', main_order: 2 },
  ]

  const mountDialog = (props: Record<string, unknown> = {}) =>
    mount(FlowTypeConfigDialog, {
      props: {
        visible: false,
        flowType: 'branch',
        mainNodeOptions,
        ...props,
      },
      global: {
        stubs: {
          ElDialog: ElDialogStub,
          ElForm: ElFormStub,
          ElFormItem: ElFormItemStub,
          ElSelect: ElSelectStub,
          ElOption: ElOptionStub,
          ElInput: ElInputStub,
          ElButton: ElButtonStub,
          ElTag: ElTagStub,
        },
      },
    })

  it('should not render dialog when visible is false', () => {
    const wrapper = mountDialog({ visible: false })
    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })

  it('should render dialog when visible is true', () => {
    const wrapper = mountDialog({ visible: true })
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
  })

  it('should show branch fields for branch flow type', () => {
    const wrapper = mountDialog({ visible: true, flowType: 'branch' })
    const labels = wrapper.findAll('.el-form-item__label').map((item) => item.text())

    expect(labels).toContain('挂靠主干页面 *')
    expect(labels).toContain('触发条件 *')
    expect(labels).toContain('补充说明')
    expect(labels).not.toContain('前置操作')
    expect(labels).not.toContain('异常现象 / 预期提示')
  })

  it('should show exception fields for exception flow type', () => {
    const wrapper = mountDialog({ visible: true, flowType: 'exception' })
    const labels = wrapper.findAll('.el-form-item__label').map((item) => item.text())

    expect(labels).toContain('挂靠主干页面 *')
    expect(labels).toContain('触发条件 *')
    expect(labels).toContain('前置操作')
    expect(labels).toContain('异常现象 / 预期提示')
    expect(labels).toContain('补充说明')
  })

  it('should show bypass fields for bypass flow type', () => {
    const wrapper = mountDialog({ visible: true, flowType: 'bypass' })
    const labels = wrapper.findAll('.el-form-item__label').map((item) => item.text())

    expect(labels).toContain('挂靠主干页面 *')
    expect(labels).toContain('触发条件 *')
    expect(labels).toContain('跳过原因')
    expect(labels).toContain('直接去向说明')
    expect(labels).toContain('补充说明')
  })

  it('should populate form when initialData is provided', async () => {
    const initialData = {
      parent_main_node_id: 'node_1',
      trigger_condition: '网络超时',
      pre_action: '点击提交按钮',
      expected_result: '显示错误提示',
      note: '支持重试',
    }
    const wrapper = mountDialog({
      visible: true,
      flowType: 'exception',
      initialData,
    })
    await nextTick()

    const selects = wrapper.findAll('.el-select')
    expect((selects[0].element as HTMLSelectElement).value).toBe('node_1')
  })

  it('should emit confirm with correct data', async () => {
    const wrapper = mountDialog({ visible: true, flowType: 'branch' })

    await wrapper.find('.el-select').setValue('node_1')
    await nextTick()

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('用户点击筛选')
    await nextTick()

    const confirmBtn = wrapper.findAll('button').find((btn) => btn.text() === '确认')
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')

    expect(wrapper.emitted('confirm')).toBeDefined()
    const confirmData = wrapper.emitted('confirm')![0][0] as Record<string, unknown>
    expect(confirmData.parent_main_node_id).toBe('node_1')
    expect(confirmData.trigger_condition).toBe('用户点击筛选')
  })

  it('should emit update:visible when clicking cancel', async () => {
    const wrapper = mountDialog({ visible: true })

    const cancelBtn = wrapper.findAll('button').find((btn) => btn.text() === '取消')
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('should validate required fields before confirm', async () => {
    const wrapper = mountDialog({ visible: true, flowType: 'branch' })

    const confirmBtn = wrapper.findAll('button').find((btn) => btn.text() === '确认')
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')

    expect(wrapper.emitted('confirm')).toBeUndefined()
    expect(wrapper.text()).toContain('请选择挂靠的主干页面')
  })

  it('should render main node options correctly', () => {
    const wrapper = mountDialog({ visible: true })
    const options = wrapper.findAll('option')

    expect(options.length).toBe(2)
    expect(options[0].text()).toContain('首页')
    expect(options[1].text()).toContain('列表页')
  })

  it('should reset form when dialog closes and reopens', async () => {
    const wrapper = mountDialog({ visible: true, flowType: 'branch' })

    await wrapper.find('.el-select').setValue('node_1')
    await nextTick()
    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('测试条件')
    await nextTick()

    await wrapper.findComponent(ElDialogStub).vm.$emit('close')
    await nextTick()
    await wrapper.setProps({ visible: false })
    await nextTick()
    await wrapper.setProps({ visible: true })
    await nextTick()

    const selects = wrapper.findAll('.el-select')
    expect((selects[0].element as HTMLSelectElement).value).toBe('')
  })
})
