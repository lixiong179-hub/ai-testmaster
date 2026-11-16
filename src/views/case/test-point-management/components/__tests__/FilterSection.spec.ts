import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive, ref } from 'vue'
import { TestPointMgmtKey } from '../../useTestPointManagement'
import FilterSection from '../FilterSection.vue'

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: '<div class="el-card"><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" @click="$emit(\'click\')"><slot /></button>',
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: {
    model: { type: Object, default: () => ({}) },
    inline: { type: Boolean, default: false },
  },
  template: '<form class="el-form" :data-inline="inline"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '' },
    clearable: { type: Boolean, default: false },
  },
  template: '<input class="el-input" :value="modelValue" :placeholder="placeholder" />',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: undefined },
    placeholder: { type: String, default: '' },
    clearable: { type: Boolean, default: false },
    filterable: { type: Boolean, default: false },
  },
  template:
    '<div class="el-select" :data-placeholder="placeholder" :data-filterable="filterable"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElDatePickerStub = defineComponent({
  name: 'ElDatePicker',
  props: {
    modelValue: { type: [Array, String], default: undefined },
    type: { type: String, default: '' },
    valueFormat: { type: String, default: '' },
    rangeSeparator: { type: String, default: '' },
    startPlaceholder: { type: String, default: '' },
    endPlaceholder: { type: String, default: '' },
  },
  template:
    '<div class="el-date-picker" :data-type="type" :data-format="valueFormat" :data-separator="rangeSeparator" :data-start="startPlaceholder" :data-end="endPlaceholder"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElButton: ElButtonStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElInput: ElInputStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElDatePicker: ElDatePickerStub,
}

function setup(patch: Partial<{ priority: number; requirementId: number }> = {}) {
  const filters = reactive({
    module: '',
    priority: patch.priority,
    requirement_id: patch.requirementId,
    created_by: '',
    keyword: '',
  })
  const ctx = {
    filters,
    dateRange: ref<[string, string] | null>(null),
    requirementOptions: ref([
      { id: 21, req_no: 'REQ-001', title: '登录' },
      { id: 22, req_no: 'REQ-002', title: '支付' },
    ]),
    fetchTestPoints: vi.fn(),
    resetFilters: vi.fn(),
  }

  const wrapper = mount(FilterSection, {
    global: { stubs, provide: { [TestPointMgmtKey as symbol]: ctx } },
  })
  return { ctx, filters, wrapper }
}

function formItemByLabel(wrapper: ReturnType<typeof setup>['wrapper'], label: string) {
  return wrapper.findAll('.el-form-item').find((i) => i.attributes('data-label') === label)
}

describe('FilterSection — 结构与按钮', () => {
  it('展示标题、副标题与两个操作按钮', async () => {
    const { ctx, wrapper } = setup()

    expect(wrapper.find('.section-title').text()).toBe('筛选与定位')
    expect(wrapper.find('.section-subtitle').text()).toContain('快速收敛测试点范围')

    const buttons = wrapper.findAll('.section-actions .el-button')
    expect(buttons.map((b) => b.text())).toEqual(['查询', '重置'])
    expect(buttons[0].attributes('data-type')).toBe('primary')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(ctx.fetchTestPoints).toHaveBeenCalledTimes(1)
    expect(ctx.resetFilters).toHaveBeenCalledTimes(1)
  })
})

describe('FilterSection — 筛选字段', () => {
  it('模块与创建人输入框占位文案', () => {
    const { wrapper } = setup()

    expect(formItemByLabel(wrapper, '模块')!.find('input').attributes('placeholder')).toBe(
      '模块名称'
    )
    expect(formItemByLabel(wrapper, '创建人')!.find('input').attributes('placeholder')).toBe(
      '创建人'
    )
  })

  it('优先级下拉固定三档', () => {
    const { wrapper } = setup()

    const item = formItemByLabel(wrapper, '优先级')!
    expect(item.find('.el-select').attributes('data-placeholder')).toBe('全部')
    expect(item.findAll('.el-option').map((o) => o.text())).toEqual(['高', '中', '低'])
    expect(item.findAll('.el-option').map((o) => o.attributes('data-value'))).toEqual([
      '1',
      '2',
      '3',
    ])
  })

  it('需求下拉按 req_no + title 拼接并支持搜索', () => {
    const { wrapper } = setup()

    const item = formItemByLabel(wrapper, '需求')!
    expect(item.find('.el-select').attributes('data-placeholder')).toBe('全部需求')
    expect(item.find('.el-select').attributes('data-filterable')).toBe('true')
    expect(item.findAll('.el-option').map((o) => o.text())).toEqual([
      'REQ-001 - 登录',
      'REQ-002 - 支付',
    ])
  })

  it('创建时间使用日期范围控件', () => {
    const { wrapper } = setup()

    const picker = formItemByLabel(wrapper, '创建时间')!.find('.el-date-picker')
    expect(picker.attributes('data-type')).toBe('daterange')
    expect(picker.attributes('data-format')).toBe('YYYY-MM-DD')
    expect(picker.attributes('data-separator')).toBe('至')
    expect(picker.attributes('data-start')).toBe('开始日期')
    expect(picker.attributes('data-end')).toBe('结束日期')
  })

  it('关键词输入回车触发查询', async () => {
    const { ctx, wrapper } = setup()

    const input = formItemByLabel(wrapper, '关键词')!.find('input')
    expect(input.attributes('placeholder')).toBe('搜索模块/功能/测试点')

    await input.trigger('keyup', { key: 'Enter' })

    expect(ctx.fetchTestPoints).toHaveBeenCalledTimes(1)
  })

  it('表单以 inline 模式渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.filter-form').attributes('data-inline')).toBe('true')
    expect(wrapper.findAll('.el-form-item')).toHaveLength(6)
  })
})
