import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useTestPointManagement', () => ({
  useTestPointManagement: () => state.current,
  TestPointMgmtKey: Symbol('testPointMgmt'),
}))

import TestPointManagementPage from '../index.vue'

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: '' },
    placeholder: { type: String, default: '' },
    filterable: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change'],
  template:
    '<div class="el-select" :data-placeholder="placeholder" :data-filterable="filterable"><slot name="prefix" /><slot /></div>',
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
    disabled: { type: Boolean, default: false },
    link: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :data-link="link" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: `<div class="el-empty">
    <div class="empty-image"><slot name="image" /></div>
    <div class="empty-description"><slot name="description" /><span class="empty-text">{{ description }}</span></div>
  </div>`,
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: { percentage: { type: Number, default: 0 }, status: { type: String, default: '' } },
  template: '<div class="el-progress" :data-percentage="percentage" :data-status="status"></div>',
})

const StatsCardsStub = defineComponent({
  name: 'StatsCards',
  template: '<div class="stats-cards-stub"></div>',
})
const FilterSectionStub = defineComponent({
  name: 'FilterSection',
  template: '<div class="filter-section-stub"></div>',
})
const TestPointTableStub = defineComponent({
  name: 'TestPointTable',
  template: '<div class="test-point-table-stub"></div>',
})
const TestPointFormDialogStub = defineComponent({
  name: 'TestPointFormDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    projectId: { type: Number, default: 0 },
    editingPoint: { type: Object, default: null },
  },
  emits: ['update:modelValue', 'success'],
  template: '<div class="form-dialog-stub" :data-project="projectId"></div>',
})
const TestPointCasesDialogStub = defineComponent({
  name: 'TestPointCasesDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    testPoint: { type: Object, default: null },
  },
  template: '<div class="cases-dialog-stub" :data-visible="modelValue"></div>',
})
const TestPointExtractDialogStub = defineComponent({
  name: 'TestPointExtractDialog',
  props: {
    visible: { type: Boolean, default: false },
    projectId: { type: Number, default: 0 },
    initialFileId: { type: Number, default: undefined },
  },
  emits: ['update:visible', 'saved'],
  template: '<div class="extract-dialog-stub" :data-file="initialFileId"></div>',
})
const XmindImportDialogStub = defineComponent({
  name: 'XmindImportDialog',
  props: { visible: { type: Boolean, default: false }, projectId: { type: Number, default: 0 } },
  emits: ['update:visible', 'imported'],
  template: '<div class="xmind-dialog-stub"></div>',
})

const stubs = {
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElButton: ElButtonStub,
  ElEmpty: ElEmptyStub,
  ElDialog: ElDialogStub,
  ElProgress: ElProgressStub,
  StatsCards: StatsCardsStub,
  FilterSection: FilterSectionStub,
  TestPointTable: TestPointTableStub,
  TestPointFormDialog: TestPointFormDialogStub,
  TestPointCasesDialog: TestPointCasesDialogStub,
  TestPointExtractDialog: TestPointExtractDialogStub,
  XmindImportDialog: XmindImportDialogStub,
}

type PageOverrides = {
  selectedProjectId?: number
  selectedProjectName?: string
  total?: number
  generating?: boolean
  generateProgress?: number
  generateMessage?: string
  progressStatus?: string
  extractDialogVisible?: boolean
  initialExtractFileId?: number | null
  editingPoint?: Record<string, unknown> | null
  casesDialogVisible?: boolean
}

function setup(overrides: PageOverrides = {}) {
  const handlers = {
    handleProjectChange: vi.fn(),
    openCreateDialog: vi.fn(),
    openExtractDialog: vi.fn(),
    openXmindImportDialog: vi.fn(),
    openLegacyExtractGuide: vi.fn(),
    openTaskList: vi.fn(),
    handleIngestSaved: vi.fn(),
    fetchTestPoints: vi.fn(),
  }
  state.current = {
    generateDialogVisible: ref(false),
    generateProgress: ref(overrides.generateProgress ?? 0),
    generateMessage: ref(overrides.generateMessage ?? ''),
    generating: ref(overrides.generating ?? false),
    xmindImportDialogVisible: ref(false),
    extractDialogVisible: ref(overrides.extractDialogVisible ?? false),
    initialExtractFileId: ref(overrides.initialExtractFileId ?? null),
    projects: ref([
      { id: 1, name: '项目A' },
      { id: 2, name: '项目B' },
    ]),
    selectedProjectId: ref(overrides.selectedProjectId ?? 1),
    total: ref(overrides.total ?? 12),
    formDialogVisible: ref(false),
    casesDialogVisible: ref(overrides.casesDialogVisible ?? false),
    editingPoint: ref(overrides.editingPoint ?? null),
    currentTestPoint: ref(null),
    selectedProjectName: ref(overrides.selectedProjectName ?? ''),
    progressStatus: ref(overrides.progressStatus ?? ''),
    ...handlers,
  }

  const wrapper = mount(TestPointManagementPage, { global: { stubs } })
  return { wrapper, ctx: state.current!, handlers }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('测试点管理页 — 页头', () => {
  it('展示标题、副标题与主入口标签', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.hero-kicker').text()).toBe('Test Point Workspace')
    expect(wrapper.find('.page-title').text()).toBe('测试点管理')
    expect(wrapper.find('.page-subtitle').text()).toContain('统一管理测试点')
    expect(wrapper.findAll('.hero-meta .el-tag')[0].text()).toBe('主入口工作台')
  })

  it('按需展示当前项目与筛选结果标签', () => {
    const noName = setup({ selectedProjectId: 0, selectedProjectName: '' }).wrapper
    expect(noName.findAll('.hero-meta .el-tag')).toHaveLength(1)

    const withName = setup({ selectedProjectName: '项目A', total: 12 }).wrapper
    const tags = withName.findAll('.hero-meta .el-tag')
    expect(tags).toHaveLength(3)
    expect(tags[1].text()).toBe('当前项目：项目A')
    expect(tags[2].text()).toBe('筛选结果：12')
  })

  it('未选项目时不展示筛选结果标签', () => {
    const { wrapper } = setup({ selectedProjectId: 0, selectedProjectName: '项目A' })

    expect(wrapper.findAll('.hero-meta .el-tag')).toHaveLength(2)
  })

  it('项目下拉渲染占位与选项并转发切换', () => {
    const { wrapper, handlers } = setup()

    const select = wrapper.findComponent(ElSelectStub)
    expect(select.attributes('data-placeholder')).toBe('请选择项目')
    expect(select.attributes('data-filterable')).toBe('true')
    expect(wrapper.findAll('.el-option').map((o) => o.text())).toEqual(['项目A', '项目B'])

    select.vm.$emit('change', 2)

    expect(handlers.handleProjectChange).toHaveBeenCalledWith(2)
  })
})

describe('测试点管理页 — 操作区', () => {
  it('未选项目时所有操作按钮禁用', () => {
    const { wrapper } = setup({ selectedProjectId: 0 })

    const buttons = wrapper.findAll('.header-actions .el-button')
    expect(buttons).toHaveLength(5)
    expect(buttons.every((b) => b.attributes('disabled') !== undefined)).toBe(true)
  })

  it('已选项目时按钮可用并按序转发动作', async () => {
    const { wrapper, handlers } = setup()

    const buttons = wrapper.findAll('.header-actions .el-button')
    expect(buttons.every((b) => b.attributes('disabled') === undefined)).toBe(true)

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')
    await buttons[3].trigger('click')
    await buttons[4].trigger('click')

    expect(handlers.openTaskList).toHaveBeenCalledTimes(1)
    expect(handlers.openExtractDialog).toHaveBeenCalledTimes(1)
    expect(handlers.openXmindImportDialog).toHaveBeenCalledTimes(1)
    expect(handlers.openCreateDialog).toHaveBeenCalledTimes(1)
    expect(handlers.openLegacyExtractGuide).toHaveBeenCalledTimes(1)
    expect(buttons[4].attributes('data-link')).toBe('true')
  })
})

describe('测试点管理页 — 工作区', () => {
  it('未选项目时展示引导空态且不渲染子区块', () => {
    const { wrapper } = setup({ selectedProjectId: 0 })

    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.find('.empty-description').text()).toContain(
      '从这里开始统一管理测试点、提取需求结果和生成关联用例。'
    )
    expect(wrapper.find('.stats-cards-stub').exists()).toBe(false)
  })

  it('已选项目时渲染统计、筛选与列表', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-empty').exists()).toBe(false)
    expect(wrapper.find('.stats-cards-stub').exists()).toBe(true)
    expect(wrapper.find('.filter-section-stub').exists()).toBe(true)
    expect(wrapper.find('.test-point-table-stub').exists()).toBe(true)
  })
})

describe('测试点管理页 — 弹层联动', () => {
  it('表单弹窗透传项目 ID 与编辑对象，成功后刷新列表', async () => {
    const editingPoint = { id: 3, module: '支付' }
    const { wrapper, handlers } = setup({ editingPoint })

    const dialog = wrapper.findComponent(TestPointFormDialogStub)
    expect(dialog.props('projectId')).toBe(1)
    expect(dialog.props('editingPoint')).toEqual(editingPoint)
    expect(dialog.props('modelValue')).toBe(false)

    dialog.vm.$emit('success')

    expect(handlers.fetchTestPoints).toHaveBeenCalledTimes(1)
  })

  it('关联用例与提取弹窗按状态打开', async () => {
    const { ctx, wrapper, handlers } = setup({
      extractDialogVisible: true,
      initialExtractFileId: 33,
    })
    ;(ctx.casesDialogVisible as { value: boolean }).value = true
    await wrapper.vm.$nextTick()

    expect(wrapper.findComponent(TestPointCasesDialogStub).props('modelValue')).toBe(true)
    expect(wrapper.findComponent(TestPointExtractDialogStub).props('visible')).toBe(true)
    expect(wrapper.findComponent(TestPointExtractDialogStub).props('initialFileId')).toBe(33)

    wrapper.findComponent(TestPointExtractDialogStub).vm.$emit('saved')
    wrapper.findComponent(XmindImportDialogStub).vm.$emit('imported')

    expect(handlers.handleIngestSaved).toHaveBeenCalledTimes(2)
  })

  it('生成进度弹窗展示进度与状态并支持关闭', () => {
    const { ctx, wrapper } = setup({
      generating: true,
      generateProgress: 60,
      generateMessage: '正在生成第 3 条',
      progressStatus: 'warning',
    })
    ;(ctx.generateDialogVisible as { value: boolean }).value = true

    return wrapper.vm.$nextTick().then(() => {
      const dialog = wrapper.find('.el-dialog')
      expect(dialog.attributes('data-title')).toBe('生成测试用例进度')
      expect(wrapper.find('.generate-status-title').text()).toBe('正在处理测试点')
      expect(wrapper.find('.el-progress').attributes('data-percentage')).toBe('60')
      expect(wrapper.find('.el-progress').attributes('data-status')).toBe('warning')
      expect(wrapper.find('.generate-message').text()).toBe('正在生成第 3 条')

      const closeBtn = wrapper.find('.el-dialog__footer .el-button')
      expect(closeBtn.attributes('disabled')).toBeDefined()
      ;(ctx.generating as { value: boolean }).value = false
      return wrapper.vm.$nextTick().then(async () => {
        expect(wrapper.find('.generate-status-title').text()).toBe('生成流程已结束')
        const closeBtnAfter = wrapper.find('.el-dialog__footer .el-button')
        expect(closeBtnAfter.attributes('disabled')).toBeUndefined()

        await closeBtnAfter.trigger('click')
        expect((ctx.generateDialogVisible as { value: boolean }).value).toBe(false)
      })
    })
  })
})
