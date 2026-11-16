import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'

const storeMock = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => storeMock.current,
}))

import GenerateCaseNavBar from '../GenerateCaseNavBar.vue'

const ElCheckboxStub = defineComponent({
  name: 'ElCheckbox',
  props: {
    modelValue: { type: Boolean, default: false },
    indeterminate: { type: Boolean, default: false },
  },
  emits: ['change', 'click'],
  template: `<input
    type="checkbox"
    class="el-checkbox"
    :checked="modelValue"
    :data-indeterminate="indeterminate"
    @change="$emit('change', $event.target.checked)"
    @click="$emit('click')"
  />`,
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :data-loading="loading" @click="$emit('click')"><slot /></button>`,
})

const stubs = { ElCheckbox: ElCheckboxStub, ElButton: ElButtonStub }

function setup(
  options: {
    cases?: Array<Record<string, unknown>>
    isEditingResult?: boolean
    selected?: number[]
    index?: number
    generating?: boolean
  } = {}
) {
  const cases = options.cases ?? [
    { title: '用例一' },
    { title: '用例二', _error: true },
    { title: '用例三', _saved: true },
  ]
  const selectedIndices = new Set(options.selected ?? [])

  const store = reactive({
    generatedCases: cases,
    isEditingResult: options.isEditingResult ?? false,
    currentCaseIndex: options.index ?? 0,
    selectedCaseIndices: selectedIndices,
    generating: options.generating ?? false,
    get allSelected() {
      return cases.length > 0 && cases.every((_, idx) => selectedIndices.has(idx))
    },
    get hasSelected() {
      return selectedIndices.size > 0
    },
    get selectedCount() {
      return selectedIndices.size
    },
    toggleSelectAll: vi.fn(() => {
      if (selectedIndices.size === cases.length) selectedIndices.clear()
      else cases.forEach((_, idx) => selectedIndices.add(idx))
    }),
    toggleCaseSelection: vi.fn((idx: number) => {
      if (selectedIndices.has(idx)) selectedIndices.delete(idx)
      else selectedIndices.add(idx)
    }),
    handleRegenerateSelected: vi.fn(),
    handleDeleteSelected: vi.fn(),
  })
  storeMock.current = store

  const wrapper = mount(GenerateCaseNavBar, { global: { stubs } })
  return { store, wrapper, selectedIndices }
}

const navButtons = (wrapper: ReturnType<typeof setup>['wrapper']) =>
  wrapper.findAll('.case-nav-btn')

describe('GenerateCaseNavBar — 渲染条件', () => {
  it('无生成结果时不渲染', () => {
    const { wrapper } = setup({ cases: [] })

    expect(wrapper.find('.case-nav-bar').exists()).toBe(false)
  })

  it('编辑结果时不渲染', () => {
    const { wrapper } = setup({ isEditingResult: true })

    expect(wrapper.find('.case-nav-bar').exists()).toBe(false)
  })

  it('渲染全部序号并标注 active / error / saved / selected', () => {
    const { wrapper } = setup({ selected: [0] })

    const dots = wrapper.findAll('.case-dot')
    expect(dots).toHaveLength(3)
    expect(dots.map((d) => d.text())).toEqual(['1', '2', '3'])
    expect(dots[0].classes()).toEqual(expect.arrayContaining(['active', 'selected']))
    expect(dots[1].classes()).toContain('error')
    expect(dots[2].classes()).toContain('saved')
    expect(dots[1].attributes('title')).toBe('用例二')
  })
})

describe('GenerateCaseNavBar — 翻页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('首条禁用上一条、末条禁用下一条', async () => {
    const { store, wrapper } = setup()
    expect(navButtons(wrapper)[0].attributes('disabled')).toBeDefined()
    expect(navButtons(wrapper)[1].attributes('disabled')).toBeUndefined()

    store.currentCaseIndex = 2
    await wrapper.vm.$nextTick()

    expect(navButtons(wrapper)[0].attributes('disabled')).toBeUndefined()
    expect(navButtons(wrapper)[1].attributes('disabled')).toBeDefined()
  })

  it('上一条 / 下一条调整索引', async () => {
    const { store, wrapper } = setup({ index: 1 })

    await navButtons(wrapper)[0].trigger('click')
    expect(store.currentCaseIndex).toBe(0)

    await navButtons(wrapper)[1].trigger('click')
    expect(store.currentCaseIndex).toBe(1)
  })

  it('点击序号跳转到该条', async () => {
    const { store, wrapper } = setup()

    await wrapper.findAll('.case-dot')[2].trigger('click')

    expect(store.currentCaseIndex).toBe(2)
  })
})

describe('GenerateCaseNavBar — 选择', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('顶部复选框触发全选/取消全选并反映 indeterminate', async () => {
    const { store, wrapper } = setup({ selected: [1] })

    const header = wrapper.find('.case-nav-bar > .el-checkbox')
    expect(header.attributes('data-indeterminate')).toBe('true')

    await header.trigger('change')

    expect(store.toggleSelectAll).toHaveBeenCalledTimes(1)
  })

  it('全部选中时 indeterminate 为 false', () => {
    const { wrapper } = setup({ selected: [0, 1, 2] })

    expect(wrapper.find('.case-nav-bar > .el-checkbox').attributes('data-indeterminate')).toBe(
      'false'
    )
  })

  it('序号内复选框切换选中且不触发跳转', async () => {
    const { store, wrapper } = setup({ index: 0 })

    const dotCheckbox = wrapper.findAll('.case-dot')[1].find('.el-checkbox')
    await dotCheckbox.trigger('change')

    expect(store.toggleCaseSelection).toHaveBeenCalledWith(1)
    expect(store.currentCaseIndex).toBe(0)
  })
})

describe('GenerateCaseNavBar — 批量操作', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('无选中时不渲染批量操作区', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.case-batch-actions').exists()).toBe(false)
  })

  it('有选中时展示计数并触发重新生成与删除', async () => {
    const { store, wrapper } = setup({ selected: [0, 2], generating: true })

    const actions = wrapper.find('.case-batch-actions')
    expect(actions.text()).toContain('重新生成 (2)')
    expect(actions.text()).toContain('删除 (2)')

    const buttons = actions.findAll('.el-button')
    expect(buttons[0].attributes('data-loading')).toBe('true')

    await buttons[0].trigger('click')
    expect(store.handleRegenerateSelected).toHaveBeenCalledTimes(1)

    await buttons[1].trigger('click')
    expect(store.handleDeleteSelected).toHaveBeenCalledTimes(1)
  })
})
