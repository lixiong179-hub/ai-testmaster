import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'

const store = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => store.current,
}))

import ContextHistoryCases from '../ContextHistoryCases.vue'

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElSkeletonStub = defineComponent({
  name: 'ElSkeleton',
  props: { rows: { type: Number, default: 0 }, animated: { type: Boolean, default: false } },
  template: '<div class="el-skeleton" :data-rows="rows"></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    link: { type: Boolean, default: false },
    type: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: Array, default: () => [] },
    multiple: { type: Boolean, default: false },
    filterable: { type: Boolean, default: false },
    clearable: { type: Boolean, default: false },
    collapseTags: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    maxCollapseTags: { type: Number, default: 0 },
  },
  emits: ['update:modelValue', 'change'],
  template:
    '<div class="el-select" :data-placeholder="placeholder" :data-multiple="multiple"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const stubs = {
  ElFormItem: ElFormItemStub,
  ElSkeleton: ElSkeletonStub,
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
}

type CaseRow = { id: number; module: string; title: string }

function setup(
  options: { projectId?: number; loading?: boolean; cases?: CaseRow[]; selected?: number[] } = {}
) {
  const state = reactive({
    formData: reactive({ project_id: options.projectId ?? 1 }),
    isLoadingProjectCases: options.loading ?? false,
    projectCases: (options.cases ?? [
      { id: 1, module: '登录', title: '密码登录' },
      { id: 2, module: '支付', title: '订单支付' },
    ]) as CaseRow[],
    selectedHistoryCaseIds: options.selected ?? [],
    _historyCaseUserCleared: false,
  })
  store.current = state

  const wrapper = mount(ContextHistoryCases, { global: { stubs } })
  return { state, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ContextHistoryCases — 状态分支', () => {
  it('未选择项目时不渲染表单项', () => {
    const { wrapper } = setup({ projectId: 0 })

    expect(wrapper.find('.el-form-item').exists()).toBe(false)
  })

  it('加载中展示骨架屏', () => {
    const { wrapper } = setup({ loading: true })

    expect(wrapper.find('.el-skeleton').attributes('data-rows')).toBe('1')
    expect(wrapper.find('.el-select').exists()).toBe(false)
  })

  it('无用例时展示引导文案', () => {
    const { wrapper } = setup({ cases: [] })

    expect(wrapper.find('.el-form-item').text()).toContain('当前项目暂无用例')
    expect(wrapper.find('.history-case-selector').exists()).toBe(false)
  })
})

describe('ContextHistoryCases — 选择器', () => {
  it('展示总数与用例选项', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.history-case-stat').text().replace(/\s+/g, '')).toBe('共2条')
    expect(wrapper.findAll('.el-option').map((o) => o.text())).toEqual([
      '[登录] 密码登录',
      '[支付] 订单支付',
    ])
    expect(wrapper.find('.el-select').attributes('data-placeholder')).toBe(
      '默认评审全部用例，可取消勾选不想评审的用例'
    )
    expect(wrapper.find('.el-select').attributes('data-multiple')).toBe('true')
  })

  it('已选数量标签与提示联动', async () => {
    const { state, wrapper } = setup({ selected: [1] })

    expect(wrapper.findAll('.history-case-toolbar .el-tag')[0].text()).toBe('已选 1')
    expect(wrapper.find('.history-case-tip').text()).toBe('已选 1 条')

    state.selectedHistoryCaseIds = []
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.history-case-toolbar .el-tag').exists()).toBe(false)
    expect(wrapper.find('.history-case-tip').text()).toBe('不选择则默认评审项目全部用例')
  })

  it('全选按钮在全部选中时禁用，点击写入全部 ID', async () => {
    const { state, wrapper } = setup({ selected: [1, 2] })
    const buttons = wrapper.findAll('.history-case-actions .el-button')

    expect(buttons[0].text()).toBe('全选')
    expect(buttons[0].attributes('disabled')).toBeDefined()

    state.selectedHistoryCaseIds = []
    await wrapper.vm.$nextTick()
    expect(
      wrapper.findAll('.history-case-actions .el-button')[0].attributes('disabled')
    ).toBeUndefined()

    await wrapper.findAll('.history-case-actions .el-button')[0].trigger('click')
    expect(state.selectedHistoryCaseIds).toEqual([1, 2])
  })

  it('清空按钮仅在已选时可用，点击清空并标记用户清除', async () => {
    const { state, wrapper } = setup({ selected: [1] })

    await wrapper.findAll('.history-case-actions .el-button')[1].trigger('click')

    expect(state.selectedHistoryCaseIds).toEqual([])
    expect(state._historyCaseUserCleared).toBe(true)
    expect(
      wrapper.findAll('.history-case-actions .el-button')[1].attributes('disabled')
    ).toBeDefined()
  })

  it('下拉选择变化同步用户清除标记', async () => {
    const { state, wrapper } = setup({ selected: [1] })
    const select = wrapper.findComponent(ElSelectStub)

    select.vm.$emit('change', [])
    expect(state._historyCaseUserCleared).toBe(true)

    select.vm.$emit('change', [2])
    expect(state._historyCaseUserCleared).toBe(false)
  })
})
