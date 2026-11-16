import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, h, inject, provide, reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/useTestPointExtract', () => ({
  useTestPointExtract: () => state.current,
}))

import Step4Validate from '../Step4Validate.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :disabled="disabled" :data-loading="loading" @click="$emit('click')"><slot /></button>`,
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: '' } },
  template: '<div class="el-alert" :data-type="type">{{ title }}</div>',
})

const ROW_KEY = Symbol('tableRow')

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] }, emptyText: { type: String, default: '' } },
  emits: ['selection-change'],
  setup(props, { slots }) {
    // 让列插槽能拿到首行数据，用于验证行内操作
    provide(
      ROW_KEY,
      computed(() => ({ row: (props.data as Record<string, unknown>[])[0] ?? {}, $index: 0 }))
    )
    return () => h('div', { class: 'el-table' }, slots.default?.())
  },
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { label: { type: String, default: '' }, prop: { type: String, default: '' } },
  setup(props, { slots }) {
    const scope = inject(ROW_KEY, null) as { value: Record<string, unknown> } | null
    return () =>
      h(
        'div',
        { class: 'el-table-column', 'data-label': props.label },
        slots.default ? slots.default(scope?.value ?? {}) : []
      )
  },
})

const ElPaginationStub = defineComponent({
  name: 'ElPagination',
  props: {
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 20 },
    total: { type: Number, default: 0 },
  },
  emits: ['current-change', 'update:current-page'],
  template: '<div class="el-pagination" :data-total="total" :data-page="currentPage" />',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}<slot name="image" /><slot /></div>',
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template:
    '<div v-if="modelValue" class="el-dialog">{{ title }}<slot /><slot name="footer" /></div>',
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  template: '<form class="el-form"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<input class="el-input" :value="modelValue" :placeholder="placeholder" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: { modelValue: { type: [Number, String], default: '' } },
  emits: ['update:modelValue'],
  template: '<div class="el-select"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<span class="el-option" :data-value="value">{{ label }}</span>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElPopconfirmStub = defineComponent({
  name: 'ElPopconfirm',
  props: { title: { type: String, default: '' } },
  emits: ['confirm'],
  template: '<span class="el-popconfirm"><slot name="reference" /></span>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElAlert: ElAlertStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElPagination: ElPaginationStub,
  ElEmpty: ElEmptyStub,
  ElDialog: ElDialogStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElInput: ElInputStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElTag: ElTagStub,
  ElPopconfirm: ElPopconfirmStub,
}

function setup(
  options: {
    testPoints?: Array<Record<string, unknown>>
    paginated?: Array<Record<string, unknown>>
    selected?: Array<Record<string, unknown>>
    currentProjectId?: number | null
    savedFromDb?: boolean
    dbTotal?: number
    pageSize?: number
    dialogVisible?: boolean
    loading?: boolean
  } = {}
) {
  const testPoints = options.testPoints ?? [
    { id: 1, module: '登录', function: '密码', point: '密码错误', priority: 1 },
    { id: 2, module: '登录', function: '密码', point: '密码正确', priority: 2 },
  ]
  const ctx = {
    totalDisplayCount: ref(testPoints.length),
    selectedRows: ref(options.selected ?? []),
    testPoints: ref(testPoints),
    batchDeleting: ref(false),
    saving: ref(false),
    currentProjectId: ref(options.currentProjectId === undefined ? 7 : options.currentProjectId),
    paginatedTestPoints: ref(options.paginated ?? testPoints),
    loadingTestPoints: ref(options.loading ?? false),
    dbTotal: ref(options.dbTotal ?? 0),
    pageSize: ref(options.pageSize ?? 20),
    savedFromDb: ref(options.savedFromDb ?? false),
    currentPage: ref(1),
    updating: ref(false),
    deleting: ref(false),
    dialogVisible: ref(options.dialogVisible ?? false),
    editForm: reactive({ module: '', function: '', point: '', priority: 2 }),
    handleSelectionChange: vi.fn(),
    clearSelection: vi.fn(),
    batchDeleteTestPoints: vi.fn(),
    saveToDatabase: vi.fn(),
    generateTestCases: vi.fn(),
    goToManagement: vi.fn(),
    getPriorityTagType: vi.fn(() => 'danger'),
    getPriorityLabel: vi.fn((p: number) => (p === 1 ? '高' : p === 2 ? '中' : '低')),
    editTestPoint: vi.fn(),
    saveTestPoint: vi.fn(),
    deleteTestPoint: vi.fn(),
    handlePageChange: vi.fn(),
  }
  state.current = ctx

  const wrapper = mount(Step4Validate, { global: { stubs } })
  return { ctx, wrapper }
}

const buttonByText = (wrapper: ReturnType<typeof setup>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text().replace(/\s+/g, '') === text)

describe('Step4Validate — 头部与工具栏', () => {
  it('标题展示总数', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.step-title').text()).toBe('校验提取结果 (共2个)')
  })

  it('有数据时展示批量与操作按钮', async () => {
    const { ctx, wrapper } = setup()

    await buttonByText(wrapper, '保存测试点')!.trigger('click')
    expect(ctx.saveToDatabase).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '进入AI生成')!.trigger('click')
    expect(ctx.generateTestCases).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '回到测试点管理')!.trigger('click')
    expect(ctx.goToManagement).toHaveBeenCalledTimes(1)
  })

  it('无当前项目时禁用回到管理', () => {
    const { wrapper } = setup({ currentProjectId: null })

    expect(buttonByText(wrapper, '回到测试点管理')!.attributes('disabled')).toBeDefined()
  })

  it('有选中项时展示批量信息与删除 loading', async () => {
    const { ctx, wrapper } = setup({ selected: [{ id: 1 }] })

    expect(wrapper.find('.el-alert').text()).toBe('已选择 1 个测试点')
    expect(buttonByText(wrapper, '批量删除')!.attributes('data-loading')).toBe('false')

    await buttonByText(wrapper, '批量删除')!.trigger('click')
    expect(ctx.batchDeleteTestPoints).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '取消选择')!.trigger('click')
    expect(ctx.clearSelection).toHaveBeenCalledTimes(1)
  })

  it('未选中时不展示批量信息', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.batch-info').exists()).toBe(false)
  })
})

describe('Step4Validate — 表格与分页', () => {
  it('表格数据来自 paginatedTestPoints', () => {
    const paginated = [{ id: 9, module: 'A', point: 'P', priority: 3 }]
    const { wrapper } = setup({ paginated })

    expect(wrapper.findComponent(ElTableStub).props('data')).toEqual(paginated)
  })

  it('本地数据超过一页时展示分页并以 testPoints 长度作为总数', () => {
    const { wrapper } = setup({
      testPoints: Array.from({ length: 25 }, (_, i) => ({ id: i + 1 })),
      pageSize: 20,
    })

    const pagination = wrapper.find('.el-pagination')
    expect(pagination.exists()).toBe(true)
    expect(pagination.attributes('data-total')).toBe('25')
  })

  it('数据库模式以 dbTotal 作为总数', () => {
    const { wrapper } = setup({ savedFromDb: true, dbTotal: 100, pageSize: 20 })

    expect(wrapper.find('.el-pagination').attributes('data-total')).toBe('100')
  })

  it('数据不足一页时不渲染分页', () => {
    const { wrapper } = setup({ testPoints: [{ id: 1 }], pageSize: 20 })

    expect(wrapper.find('.el-pagination').exists()).toBe(false)
  })

  it('无数据时展示空态', () => {
    const { wrapper } = setup({ testPoints: [], paginated: [] })

    expect(wrapper.find('.el-table').exists()).toBe(false)
    expect(wrapper.find('.el-empty').text()).toContain('暂无测试点数据，请先提取测试点')
  })
})

describe('Step4Validate — 行内操作', () => {
  it('渲染优先级标签与删除确认', () => {
    const { ctx, wrapper } = setup()

    const popconfirm = wrapper.findComponent(ElPopconfirmStub)
    expect(popconfirm.props('title')).toBe('确定删除此测试点？')
    expect(wrapper.find('.el-table').text()).toContain('高')

    popconfirm.vm.$emit('confirm')
    expect(ctx.deleteTestPoint).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('编辑按钮回传当前行', async () => {
    const { ctx, wrapper } = setup()

    await buttonByText(wrapper, '编辑')!.trigger('click')

    expect(ctx.editTestPoint).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })
})

describe('Step4Validate — 编辑对话框', () => {
  it('未打开时不渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })

  it('打开时渲染表单字段并支持保存与取消', async () => {
    const { ctx, wrapper } = setup({ dialogVisible: true })

    const dialog = wrapper.find('.el-dialog')
    expect(dialog.text()).toContain('编辑测试点')
    expect(wrapper.findAll('.el-form-item').map((f) => f.attributes('data-label'))).toEqual([
      '模块',
      '功能',
      '测试点描述',
      '优先级',
    ])
    expect(wrapper.findAll('.el-option').map((o) => o.text())).toEqual(['高', '中', '低'])

    const inputs = wrapper.findAll('.el-input')
    await inputs[0].setValue('登录模块')
    await inputs[1].setValue('密码验证')
    await inputs[2].setValue('密码错误时提示')

    expect(ctx.editForm).toMatchObject({
      module: '登录模块',
      function: '密码验证',
      point: '密码错误时提示',
    })

    await buttonByText(wrapper, '保存')!.trigger('click')
    expect(ctx.saveTestPoint).toHaveBeenCalledTimes(1)

    await buttonByText(wrapper, '取消')!.trigger('click')
    expect(ctx.dialogVisible.value).toBe(false)
  })
})
