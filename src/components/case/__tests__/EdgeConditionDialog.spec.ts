import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import EdgeConditionDialog from '../EdgeConditionDialog.vue'

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

describe('EdgeConditionDialog', () => {
  const mountDialog = (props: Record<string, unknown> = {}) =>
    mount(EdgeConditionDialog, {
      props: {
        visible: false,
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

  it('should show condition input for branch edge type', async () => {
    const wrapper = mountDialog({ visible: true })

    await wrapper.find('.el-select').setValue('branch')
    await nextTick()

    expect(wrapper.find('textarea').exists()).toBe(true)
    expect(wrapper.text()).toContain('触发条件')
  })

  it('should always show condition textarea (all fields visible)', () => {
    const wrapper = mountDialog({ visible: true })
    expect(wrapper.find('textarea').exists()).toBe(true)
  })

  it('should emit confirm with correct data', async () => {
    const wrapper = mountDialog({ visible: true })

    await wrapper.find('.el-select').setValue('branch')
    await nextTick()
    await wrapper.find('textarea').setValue('用户点击高级筛选按钮')
    await nextTick()

    const confirmBtn = wrapper.findAll('button').find((btn) => btn.text() === '确认')
    expect(confirmBtn).toBeDefined()
    await confirmBtn!.trigger('click')

    expect(wrapper.emitted('confirm')).toEqual([
      [
        {
          edge_type: 'branch',
          condition: '用户点击高级筛选按钮',
          trigger_action: '',
          pre_action: '',
          note: '',
          label: '条件分支',
        },
      ],
    ])
  })

  it('should emit update:visible when clicking cancel', async () => {
    const wrapper = mountDialog({ visible: true })

    const cancelBtn = wrapper.findAll('button').find((btn) => btn.text() === '取消')
    expect(cancelBtn).toBeDefined()
    await cancelBtn!.trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('should reset form values when dialog closes', async () => {
    const wrapper = mountDialog({ visible: true })

    await wrapper.find('.el-select').setValue('branch')
    await nextTick()
    const textareas = wrapper.findAll('textarea')
    await textareas[0].setValue('测试条件')
    await nextTick()

    await wrapper.findComponent(ElDialogStub).vm.$emit('close')
    await nextTick()
    await wrapper.setProps({ visible: false })
    await nextTick()
    await wrapper.setProps({ visible: true })
    await nextTick()

    expect((textareas[0].element as HTMLTextAreaElement).value).toBe('')
  })

  it('should populate form when edgeData is provided', async () => {
    const edgeData = {
      edge_type: 'exception' as const,
      condition: '网络超时错误',
    }
    const wrapper = mountDialog({ visible: true, edgeData })
    await nextTick()

    expect((wrapper.find('textarea').element as HTMLTextAreaElement).value).toBe('网络超时错误')
  })

  it('should use correct placeholder for different edge types', async () => {
    const testCases = [
      { type: 'branch' as const, expectedPlaceholder: '例如：用户点击高级筛选按钮' },
      { type: 'exception' as const, expectedPlaceholder: '例如：输入非法字符或接口超时' },
      { type: 'bypass' as const, expectedPlaceholder: '例如：进入页面自动弹出' },
    ]

    for (const testCase of testCases) {
      const wrapper = mountDialog({
        visible: true,
        edgeData: {
          edge_type: testCase.type,
          condition: '',
          trigger_action: '',
          pre_action: '',
          note: '',
        },
      })
      await nextTick()

      const textareas = wrapper.findAll('textarea')
      expect(textareas[0].attributes('placeholder')).toBe(testCase.expectedPlaceholder)
    }
  })
})
