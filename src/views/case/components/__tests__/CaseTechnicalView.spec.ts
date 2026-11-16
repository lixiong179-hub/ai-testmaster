import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { computed, defineComponent, h, inject, provide, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/case/useCaseDetail', () => ({
  useCaseDetail: () => state.current,
}))

import CaseTechnicalView from '../CaseTechnicalView.vue'

const ROW_KEY = Symbol('tableRow')

const ElIconStub = defineComponent({
  name: 'ElIcon',
  props: { size: { type: [Number, String], default: '' } },
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    size: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    link: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :data-loading="loading" @click="$emit('click')"><slot /></button>`,
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: '' } },
  template: '<div class="el-alert" :data-type="type">{{ title }}</div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElSkeletonStub = defineComponent({
  name: 'ElSkeleton',
  template: '<div class="el-skeleton" />',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<input class="el-input" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const RowProvider = defineComponent({
  name: 'RowProvider',
  props: { row: { type: Object, default: () => ({}) }, index: { type: Number, default: 0 } },
  setup(props, { slots }) {
    provide(
      ROW_KEY,
      computed(() => ({ row: props.row, $index: props.index }))
    )
    return () => h('div', { class: 'table-row' }, slots.default?.())
  },
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { class: 'el-table' },
        (props.data as Record<string, unknown>[]).map((row, index) =>
          h(RowProvider, { row, index }, { default: () => slots.default?.() })
        )
      )
  },
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { label: { type: String, default: '' } },
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

const TestDataEditorStub = defineComponent({
  name: 'TestDataEditor',
  props: { stepId: { type: Number, default: 0 }, stepAction: { type: String, default: '' } },
  template: '<div class="test-data-editor" :data-step-id="stepId" :data-action="stepAction" />',
})

const stubs = {
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElAlert: ElAlertStub,
  ElTag: ElTagStub,
  ElSkeleton: ElSkeletonStub,
  ElEmpty: ElEmptyStub,
  ElInput: ElInputStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  TestDataEditor: TestDataEditorStub,
}

function step(overrides: Record<string, unknown> = {}) {
  return {
    id: 21,
    step_id: 21,
    step_number: 1,
    action: '点击登录',
    expected_result: '跳转首页',
    locator_status: 'matched',
    locator: { locator_type: 'xpath', locator_value: '//button', xpath: '//button' },
    input_value: '',
    action_type: 'click',
    test_data: [],
    ...overrides,
  }
}

function setup(
  options: {
    loading?: boolean
    data?: Record<string, unknown> | null
    issueType?: string
  } = {}
) {
  const technicalViewData = ref<Record<string, unknown> | null>(
    options.data === undefined ? { steps: [step()], locator_coverage: 0.82 } : options.data
  )
  const ctx = {
    viewLoading: ref(options.loading ?? false),
    technicalViewData,
    formatLocatorCoverage: vi.fn((v: number) => `${Math.round(v * 100)}%`),
    batchLocatorVisible: ref(false),
    parsePrecondition: vi.fn(),
    parsePreconditionLoading: ref(false),
    addPreconditionStep: vi.fn(),
    deletePreconditionStep: vi.fn(),
    isCorrectionMode: ref(false),
    failureReason: ref(''),
    aiAnalysisText: ref(''),
    showSuggestionPanel: ref(true),
    getActionTypeTagType: vi.fn(() => 'primary'),
    getLocatorStatusType: vi.fn(() => 'success'),
    getLocatorStatusLabel: vi.fn(() => '已定位'),
    getStepRowClass: vi.fn(() => ''),
    editingCell: ref<{ stepIndex: number; field: string } | null>(null),
    editingValue: ref(''),
    saveCellEdit: vi.fn(),
    cellSaving: ref(false),
    cancelCellEdit: vi.fn(),
    startCellEdit: vi.fn((index: number, field: string, value: string) => {
      ctx.editingCell = ref({ stepIndex: index, field })
      ctx.editingValue = ref(value ?? '')
    }),
    issueType: ref(options.issueType ?? 'case_issue'),
    openAddLocator: vi.fn(),
  }
  state.current = ctx

  const wrapper = mount(CaseTechnicalView, { global: { stubs } })
  return { ctx, wrapper, technicalViewData }
}

describe('CaseTechnicalView — 加载与空态', () => {
  it('加载中展示骨架屏', () => {
    const { wrapper } = setup({ loading: true })

    expect(wrapper.find('.loading-container .el-skeleton').exists()).toBe(true)
    expect(wrapper.find('.el-table').exists()).toBe(false)
  })

  it('无技术视图数据时不渲染内容', () => {
    const { wrapper } = setup({ data: null })

    expect(wrapper.find('.loading-container').exists()).toBe(false)
    expect(wrapper.find('.el-table').exists()).toBe(false)
    expect(wrapper.find('.coverage-info').exists()).toBe(false)
  })

  it('展示定位覆盖率并支持打开批量补充定位', async () => {
    const { ctx, wrapper } = setup()

    expect(wrapper.find('.coverage-info .el-alert').text()).toBe('定位覆盖率: 82%')

    await wrapper
      .findAll('.coverage-info button')
      .find((b) => b.text().includes('批量补充定位'))!
      .trigger('click')
    expect(ctx.batchLocatorVisible.value).toBe(true)
  })
})

describe('CaseTechnicalView — 前置条件', () => {
  it('无前置条件时不渲染区块', () => {
    const { wrapper } = setup({ data: { steps: [], locator_coverage: 1 } })

    expect(wrapper.find('.precondition-section').exists()).toBe(false)
  })

  it('展示前置条件、步骤数与表格', () => {
    const { wrapper } = setup({
      data: {
        locator_coverage: 1,
        precondition: '已登录',
        precondition_steps: [
          {
            step_number: 1,
            action: '打开登录页',
            action_type: 'click',
            input_value: 'admin',
            target_element: 'username',
            locator_status: 'matched',
          },
          {
            step_number: 2,
            action: '输入密码',
            action_type: 'input',
            input_value: '',
            target_element: 'pwd',
            locator_status: 'missing',
          },
        ],
        steps: [],
      },
    })

    expect(wrapper.find('.precondition-section .el-alert').text()).toBe('前置条件: 已登录')
    expect(wrapper.find('.precondition-section .el-tag').text()).toBe('2 个步骤')
    const rows = wrapper.findAll('.precondition-section .table-row')
    expect(rows.length).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('打开登录页')
    expect(wrapper.text()).toContain('添加数据')
  })

  it('无步骤时给出占位提示', () => {
    const { wrapper } = setup({
      data: { locator_coverage: 1, precondition: '已登录', precondition_steps: [], steps: [] },
    })

    expect(wrapper.text()).toContain('暂无前置条件步骤')
  })

  it('AI解析 / 添加步骤 / 删除步骤回调', async () => {
    const { ctx, wrapper } = setup({
      data: {
        locator_coverage: 1,
        precondition: '已登录',
        precondition_steps: [
          { step_number: 1, action: 'A', action_type: 'click', locator_status: 'matched' },
        ],
        steps: [],
      },
    })

    const headerButtons = wrapper.findAll('.precondition-header button')
    await headerButtons[0].trigger('click')
    expect(ctx.parsePrecondition).toHaveBeenCalledTimes(1)
    expect(headerButtons[0].attributes('data-loading')).toBe('false')

    await headerButtons[1].trigger('click')
    expect(ctx.addPreconditionStep).toHaveBeenCalledTimes(1)

    const deleteBtn = wrapper
      .findAll('.precondition-section button')
      .find((b) => b.text() === '删除')!
    await deleteBtn.trigger('click')
    expect(ctx.deletePreconditionStep).toHaveBeenCalledWith(0)
  })
})

describe('CaseTechnicalView — 智能建议面板', () => {
  it('非纠正模式不渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.suggestion-panel').exists()).toBe(false)
  })

  it('纠正模式下展示失败原因与 AI 分析并支持收起', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.isCorrectionMode as { value: boolean }).value = true
    ;(ctx.failureReason as { value: string }).value = '按钮不存在'
    ;(ctx.aiAnalysisText as { value: string }).value = '定位器失效'
    await wrapper.vm.$nextTick()

    const panel = wrapper.find('.suggestion-panel')
    expect(panel.text()).toContain('按钮不存在')
    expect(panel.text()).toContain('定位器失效')

    await panel
      .findAll('button')
      .find((b) => b.text() === '收起')!
      .trigger('click')
    expect(ctx.showSuggestionPanel.value).toBe(false)
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.suggestion-body').exists()).toBe(false)
  })
})

describe('CaseTechnicalView — 步骤表格', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染步骤内容与定位信息', () => {
    const { wrapper } = setup()

    const row = wrapper.find('.table-row')
    expect(row.text()).toContain('点击登录')
    expect(row.text()).toContain('跳转首页')
    expect(row.text()).toContain('已定位')
    expect(row.text()).toContain('//button')
  })

  it('双击单元格进入行内编辑', async () => {
    const { ctx, wrapper } = setup()
    const cells = wrapper.findAll('.table-row .cell-display')

    await cells[0].trigger('dblclick')

    expect(ctx.startCellEdit).toHaveBeenCalledWith(0, 'action', '点击登录')
  })

  it('编辑态渲染输入框与保存/取消', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.editingCell as { value: unknown }).value = { stepIndex: 0, field: 'action' }
    ;(ctx.editingValue as { value: string }).value = '新操作'
    await wrapper.vm.$nextTick()

    const editing = wrapper.find('.cell-editing')
    expect(editing.find('.el-input').element as HTMLInputElement).toHaveProperty('value', '新操作')

    const actions = editing.findAll('button')
    await actions[0].trigger('click')
    expect(ctx.saveCellEdit).toHaveBeenCalledTimes(1)

    await actions[1].trigger('click')
    expect(ctx.cancelCellEdit).toHaveBeenCalledTimes(1)
  })

  it('Bug 问题隐藏编辑图标与添加定位列', async () => {
    const { wrapper } = setup({ issueType: 'product_bug' })

    expect(wrapper.findAll('.table-row .edit-icon')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('添加定位')
  })

  it('定位缺失时提供添加定位入口', async () => {
    const { ctx, wrapper } = setup({
      data: {
        locator_coverage: 0,
        steps: [step({ locator: {}, locator_status: 'missing' })],
      },
    })

    const addBtn = wrapper.findAll('button').find((b) => b.text() === '添加定位')!
    await addBtn.trigger('click')

    expect(ctx.openAddLocator).toHaveBeenCalledWith(0, expect.objectContaining({ id: 21 }))
  })

  it('步骤为空时展示空态', () => {
    const { wrapper } = setup({ data: { locator_coverage: 1, steps: [] } })

    expect(wrapper.find('.el-empty').text()).toBe('暂无测试步骤')
  })
})

describe('CaseTechnicalView — 测试数据', () => {
  it('无数据时展示添加数据入口', async () => {
    const { wrapper } = setup()

    const btn = wrapper.findAll('button').find((b) => b.text() === '添加数据')
    expect(btn).toBeDefined()
  })

  it('有 input_value 时展示输入标签与编辑入口', async () => {
    const { wrapper } = setup({
      data: { locator_coverage: 1, steps: [step({ input_value: 'admin', action_type: 'click' })] },
    })

    expect(wrapper.find('.test-data-value').text()).toBe('admin')
    expect(wrapper.find('.test-data-item .el-tag').text()).toBe('输入')
  })

  it('select 类型展示选择标签', () => {
    const { wrapper } = setup({
      data: { locator_coverage: 1, steps: [step({ input_value: '选项A', action_type: 'select' })] },
    })

    expect(wrapper.find('.test-data-item .el-tag').text()).toBe('选择')
  })

  it('test_data 数组逐项渲染字段名与取值', () => {
    const { wrapper } = setup({
      data: {
        locator_coverage: 1,
        steps: [
          step({
            input_value: '',
            test_data: [{ field_name: '账号', data_value: 'admin' }],
          }),
        ],
      },
    })

    expect(wrapper.findAll('.test-data-item .el-tag').map((t) => t.text())).toEqual(['账号'])
    expect(wrapper.find('.test-data-value').text()).toBe('admin')
  })

  it('test_data 缺失取值时展示占位符', () => {
    const { wrapper } = setup({
      data: {
        locator_coverage: 1,
        steps: [step({ input_value: '', test_data: [{ field_name: '密码', data_value: '' }] })],
      },
    })

    expect(wrapper.find('.test-data-value').text()).toBe('-')
  })

  it('打开测试数据编辑器并展示步骤信息，收起后隐藏', async () => {
    const { wrapper } = setup()

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '添加数据')!
      .trigger('click')
    await flushPromises()

    const editor = wrapper.find('.test-data-editor')
    expect(editor.exists()).toBe(true)
    expect(editor.attributes('data-step-id')).toBe('21')
    expect(editor.attributes('data-action')).toBe('点击登录')

    await wrapper
      .findAll('.editor-header-bar button')
      .find((b) => b.text() === '收起')!
      .trigger('click')
    expect(wrapper.find('.test-data-editor').exists()).toBe(false)
  })

  it('切换步骤时二次确认，取消则不切换', async () => {
    const { wrapper } = setup({
      data: {
        locator_coverage: 1,
        steps: [step({ id: 21 }), step({ id: 22, step_id: 22, step_number: 2, action: '第二步' })],
      },
    })
    const confirmSpy = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '添加数据')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.find('.test-data-editor').attributes('data-step-id')).toBe('21')

    const secondRowButtons = wrapper.findAll('.table-row')[1].findAll('button')
    await secondRowButtons.find((b) => b.text() === '添加数据')!.trigger('click')
    await flushPromises()

    expect(confirmSpy).toHaveBeenCalled()
    expect(wrapper.find('.test-data-editor').attributes('data-step-id')).toBe('21')
  })

  it('确认后切换到新步骤', async () => {
    const { wrapper } = setup({
      data: {
        locator_coverage: 1,
        steps: [step({ id: 21 }), step({ id: 22, step_id: 22, step_number: 2, action: '第二步' })],
      },
    })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)

    await wrapper
      .findAll('button')
      .find((b) => b.text() === '添加数据')!
      .trigger('click')
    await flushPromises()

    const secondRowButtons = wrapper.findAll('.table-row')[1].findAll('button')
    await secondRowButtons.find((b) => b.text() === '添加数据')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.test-data-editor').attributes('data-step-id')).toBe('22')
  })
})
