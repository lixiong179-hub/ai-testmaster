import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'

const store = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => store.current,
}))

import ContextTestPointSelector from '../ContextTestPointSelector.vue'

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: Array, default: () => [] },
    multiple: { type: Boolean, default: false },
    filterable: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
    collapseTags: { type: Boolean, default: false },
    maxCollapseTags: { type: Number, default: 0 },
  },
  template: `<div class="el-select" :data-placeholder="placeholder" :data-multiple="multiple">
    <slot name="header" />
    <slot />
    <slot name="footer" />
    <slot name="empty" />
  </div>`,
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template:
    '<div class="el-option" :data-value="value"><span class="option-label">{{ label }}</span><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    link: { type: Boolean, default: false },
    type: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'default' },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: {
    type: { type: String, default: 'primary' },
    effect: { type: String, default: 'light' },
    closable: { type: Boolean, default: false },
    size: { type: String, default: 'default' },
  },
  emits: ['close', 'click'],
  template: `<span class="el-tag" :data-type="type" @click="$emit('click')">
    <slot />
    <i v-if="closable" class="tag-close" @click.stop="$emit('close')"></i>
  </span>`,
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElPaginationStub = defineComponent({
  name: 'ElPagination',
  props: {
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 10 },
    total: { type: Number, default: 0 },
    layout: { type: String, default: '' },
  },
  emits: ['current-change'],
  template:
    '<div class="el-pagination" :data-total="total" :data-page="currentPage" :data-size="pageSize"></div>',
})

const ElPopoverStub = defineComponent({
  name: 'ElPopover',
  props: { placement: { type: String, default: '' }, width: { type: Number, default: 150 } },
  template:
    '<div class="el-popover"><slot name="reference" /><div class="popover-body"><slot /></div></div>',
})

const stubs = {
  ElFormItem: ElFormItemStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElButton: ElButtonStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElPagination: ElPaginationStub,
  ElPopover: ElPopoverStub,
}

type Point = { id: number; module: string; point: string; priority: number }

const points: Point[] = [
  { id: 1, module: '登录', point: '密码登录', priority: 1 },
  { id: 2, module: '支付', point: '订单支付', priority: 2 },
  { id: 3, module: '搜索', point: '关键词搜索', priority: 3 },
]

function createStore(
  options: {
    total?: number
    selected?: number[]
    page?: number
    pageSize?: number
    allIds?: number[]
  } = {}
) {
  const selected = options.selected ?? []
  return {
    testPointTotal: options.total ?? 0,
    testPointAllIds: options.allIds ?? points.map((p) => p.id),
    testPointPage: options.page ?? 1,
    testPointPageSize: options.pageSize ?? 10,
    testPointSelectKey: 0,
    testPoints: points,
    formData: { test_point_ids: selected },
    selectAllTestPoints: vi.fn(),
    deselectAllTestPoints: vi.fn(),
    selectCurrentPageAll: vi.fn(),
    addTestPoint: vi.fn(),
    removeTestPoint: vi.fn(),
    getPriorityType: (priority: number) => ({ 1: 'danger', 2: 'warning', 3: 'info' })[priority],
    getPriorityLabel: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority],
    getSelectedTagType: () => 'success',
    getTestPointLabel: (id: number) => `测试点-${id}`,
    goToTestPointPage: vi.fn(),
  }
}

function setup(
  options: {
    total?: number
    selected?: number[]
    page?: number
    pageSize?: number
    related?: number[]
    allIds?: number[]
  } = {}
) {
  const fake = createStore(options)
  store.current = fake

  const wrapper = mount(ContextTestPointSelector, {
    props: { relatedTestPointIds: options.related ?? [] },
    global: { stubs },
  })
  return { store: fake, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ContextTestPointSelector — 工具栏', () => {
  it('无数据且未选择时不渲染工具栏', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-form-item').attributes('data-label')).toBe('测试点')
    expect(wrapper.find('.tp-toolbar').exists()).toBe(false)
  })

  it('展示总数与已选数量', () => {
    const { wrapper } = setup({ total: 42, selected: [1, 2] })

    expect(wrapper.find('.tp-stat').text().replace(/\s+/g, '')).toBe('共42条')
    expect(wrapper.findAll('.tp-toolbar-left .el-tag')[0].text()).toBe('已选 2')
  })

  it('全选按钮按可选数量禁用并转发', async () => {
    const { store: fake, wrapper } = setup({ total: 3 })
    const buttons = wrapper.findAll('.tp-toolbar-right .el-button')

    expect(buttons[0].text()).toBe('全选')
    expect(buttons[0].attributes('disabled')).toBeUndefined()

    await buttons[0].trigger('click')
    expect(fake.selectAllTestPoints).toHaveBeenCalledTimes(1)
  })

  it('无可选测试点时禁用全选，已选时清空可用并转发', async () => {
    const { store: fake, wrapper } = setup({ total: 3, selected: [1], allIds: [] })

    const buttons = wrapper.findAll('.tp-toolbar-right .el-button')
    expect(buttons[0].attributes('disabled')).toBeDefined()
    expect(buttons[1].attributes('disabled')).toBeUndefined()

    await buttons[1].trigger('click')
    expect(fake.deselectAllTestPoints).toHaveBeenCalledTimes(1)
  })
})

describe('ContextTestPointSelector — 选项与勾选', () => {
  it('按模块与测试点渲染选项并标记已选', () => {
    const { wrapper } = setup({ total: 3, selected: [2] })

    const options = wrapper.findAll('.el-option .option-label')
    expect(options.map((o) => o.text())).toEqual([
      '登录 - 密码登录',
      '支付 - 订单支付',
      '搜索 - 关键词搜索',
    ])
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes.map((c) => (c.element as HTMLInputElement).checked)).toEqual([
      false,
      true,
      false,
    ])
  })

  it('勾选与取消勾选分别调用增删', async () => {
    const { store: fake, wrapper } = setup({ total: 3, selected: [2] })
    const [first, second] = wrapper.findAll('input[type="checkbox"]')

    Object.defineProperty(first.element, 'checked', { value: true, configurable: true })
    await first.trigger('change')
    expect(fake.addTestPoint).toHaveBeenCalledWith(1)

    Object.defineProperty(second.element, 'checked', { value: false, configurable: true })
    await second.trigger('change')
    expect(fake.removeTestPoint).toHaveBeenCalledWith(2)
  })

  it('选项内展示优先级标签与重复测试点描述', () => {
    const { wrapper } = setup({ total: 3 })

    const firstOption = wrapper.findAll('.el-option')[0]
    expect(firstOption.find('.tp-mod').text()).toBe('登录')
    expect(firstOption.find('.tp-point').text()).toBe('密码登录')
    expect(firstOption.find('.el-tag').text()).toBe('高')
    expect(firstOption.find('.tp-row2').text()).toBe('密码登录')
  })

  it('下拉头部展示分页信息并可本页全选', async () => {
    const { store: fake, wrapper } = setup({ total: 25, pageSize: 10, page: 2 })

    expect(wrapper.find('.tp-d-info span').text()).toBe('2/3')
    await wrapper.find('.tp-d-info .el-button').trigger('click')

    expect(fake.selectCurrentPageAll).toHaveBeenCalledTimes(1)
  })

  it('底部有总数时展示分页并转发页码', async () => {
    const { store: fake, wrapper } = setup({ total: 25, pageSize: 10, page: 2 })

    const pagination = wrapper.findComponent(ElPaginationStub)
    expect(pagination.attributes('data-total')).toBe('25')
    expect(pagination.attributes('data-page')).toBe('2')

    pagination.vm.$emit('current-change', 3)
    expect(fake.goToTestPointPage).toHaveBeenCalledWith(3)
  })

  it('无总数时不渲染底部与分页', () => {
    const { wrapper } = setup({ total: 0 })

    expect(wrapper.find('.tp-d-footer').exists()).toBe(false)
    expect(wrapper.find('.el-pagination').exists()).toBe(false)
  })

  it('空态提示文案', () => {
    const { wrapper } = setup({ total: 0 })

    expect(wrapper.find('.tp-empty').text()).toBe(
      '暂无测试点，请先选择项目或确认项目下已创建测试点'
    )
  })
})

describe('ContextTestPointSelector — 已选标签', () => {
  it('最多展示 6 个可关闭标签，关闭即移除', async () => {
    const { store: fake, wrapper } = setup({ total: 8, selected: [1, 2, 3] })

    const chips = wrapper.findAll('.tp-chips > .el-tag')
    expect(chips.map((c) => c.text())).toEqual(['测试点-1', '测试点-2', '测试点-3'])

    await chips[0].find('.tag-close').trigger('click')
    expect(fake.removeTestPoint).toHaveBeenCalledWith(1)
  })

  it('超过 6 个时折叠为 +N 并在浮层列出剩余', () => {
    const selected = [1, 2, 3, 4, 5, 6, 7, 8]
    const { wrapper } = setup({ total: 8, selected })

    const chips = wrapper.findAll('.tp-chips > .el-tag')
    expect(chips).toHaveLength(6)
    const popoverTagsAll = wrapper.findAll('.el-popover .el-tag')
    expect(popoverTagsAll[0].text()).toBe('+2')
    expect(popoverTagsAll[0].attributes('data-type')).toBe('info')
    const popoverTags = wrapper.find('.popover-body').findAll('.el-tag')
    expect(popoverTags.map((t) => t.text())).toEqual(['测试点-7', '测试点-8'])
  })

  it('未选择时不渲染标签区', () => {
    const { wrapper } = setup({ total: 3 })

    expect(wrapper.find('.tp-chips').exists()).toBe(false)
  })
})

describe('ContextTestPointSelector — 推荐测试点', () => {
  it('按选中状态区分标签颜色并支持点击增删', async () => {
    const { store: fake, wrapper } = setup({ total: 3, selected: [2], related: [1, 2] })

    const tags = wrapper.findAll('.tp-recommend-tag')
    expect(wrapper.find('.tp-recommend-header').text()).toContain('推荐测试点（基于选中页面路径）')
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['info', 'success'])

    await tags[0].trigger('click')
    await tags[1].trigger('click')

    expect(fake.addTestPoint).toHaveBeenCalledWith(1)
    expect(fake.removeTestPoint).toHaveBeenCalledWith(2)
  })

  it('无推荐时不渲染推荐区', () => {
    const { wrapper } = setup({ total: 3, related: [] })

    expect(wrapper.find('.tp-recommend').exists()).toBe(false)
  })
})
