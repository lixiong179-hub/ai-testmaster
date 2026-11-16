import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, h, inject, reactive, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/requirement/useResourceManage', async () => {
  const constants =
    await vi.importActual<typeof import('@/constants/resource')>('@/constants/resource')
  return {
    useResourceManage: () => mockCtx.current,
    RESOURCE_TYPE_OPTIONS: constants.RESOURCE_TYPE_OPTIONS,
    RESOURCE_CONFIG: constants.RESOURCE_CONFIG,
  }
})

import ResourceTable from '../ResourceTable.vue'

const ROWS_KEY = Symbol('tableRows')

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: `<div class="el-card">
    <div class="el-card__header"><slot name="header" /></div>
    <div class="el-card__body"><slot /></div>
  </div>`,
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    size: { type: String, default: 'default' },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :disabled="disabled" :data-loading="loading" @click="$emit('click')"><slot /></button>`,
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, size: { type: String, default: 'default' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElLinkStub = defineComponent({
  name: 'ElLink',
  props: {
    href: { type: String, default: undefined },
    type: { type: String, default: '' },
    target: { type: String, default: undefined },
    underline: { type: [String, Boolean], default: undefined },
  },
  emits: ['click'],
  template:
    '<a class="el-link" :href="href" :data-type="type" @click="$emit(\'click\')"><slot /></a>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  template: '<div class="el-table" :data-rows="data.length"><slot /></div>',
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: {
    prop: { type: String, default: '' },
    label: { type: String, default: '' },
    width: { type: [String, Number], default: '' },
    minWidth: { type: [String, Number], default: '' },
  },
  setup(props, { slots }) {
    const rows = inject<RowData[]>(ROWS_KEY, [])
    return () =>
      h(
        'div',
        { class: 'el-table-column', 'data-prop': props.prop, 'data-label': props.label },
        rows.map((row, index) =>
          h(
            'div',
            { class: 'el-table-cell' },
            slots.default ? slots.default({ row, $index: index }) : String(row[props.prop] ?? '')
          )
        )
      )
  },
})

const ElPaginationStub = defineComponent({
  name: 'ElPagination',
  props: {
    total: { type: Number, default: 0 },
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 10 },
  },
  emits: ['size-change', 'current-change', 'update:current-page', 'update:page-size'],
  template:
    '<div class="el-pagination" :data-total="total" :data-page="currentPage" :data-size="pageSize"></div>',
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  template: '<form class="el-form"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' }, prop: { type: String, default: '' } },
  template:
    '<div class="el-form-item" :data-label="label" :data-prop="prop"><label>{{ label }}</label><slot /></div>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: '' },
    placeholder: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: false },
  },
  template:
    '<div class="el-select" :data-placeholder="placeholder" :data-disabled="disabled"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  template: '<input class="el-input" :value="modelValue" :placeholder="placeholder" />',
})

const ElSwitchStub = defineComponent({
  name: 'ElSwitch',
  props: { modelValue: { type: Boolean, default: false } },
  template: '<div class="el-switch" :data-value="modelValue"></div>',
})

const RequirementUploaderStub = defineComponent({
  name: 'RequirementUploader',
  props: {
    projectId: { type: [Number, String], default: '' },
    iterationId: { type: [Number, String], default: null },
    description: { type: String, default: '' },
    showUploadButton: { type: Boolean, default: true },
  },
  emits: ['success', 'error'],
  template:
    '<div class="uploader-stub" :data-project="projectId" :data-iteration="iterationId" :data-show-button="showUploadButton"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  ElTag: ElTagStub,
  ElLink: ElLinkStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElPagination: ElPaginationStub,
  ElDialog: ElDialogStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElInput: ElInputStub,
  ElSwitch: ElSwitchStub,
  RequirementUploader: RequirementUploaderStub,
}

type RowData = Record<string, unknown>

type CtxOverrides = {
  resources?: RowData[]
  isLoading?: boolean
  total?: number
  projectId?: number | ''
  selectedIterationId?: number | null
  dialogVisible?: boolean
  dialogMode?: 'add' | 'edit'
  currentIterationTitle?: string
}

function createCtx(overrides: CtxOverrides = {}) {
  const pagination = reactive({ page: 2, pageSize: 20 })
  const resourceList = reactive({
    resources: overrides.resources ?? ([] as RowData[]),
    isLoading: computed(() => overrides.isLoading ?? false),
    total: overrides.total ?? 0,
    pagination,
    filterForm: reactive({ project_id: overrides.projectId ?? 1, resource_type: '' }),
    getResourceTypeTagType: (type: string) =>
      ({ requirement: 'primary', ui_mockup: 'success', api_doc: 'warning' })[type] ?? 'info',
    getResourceTypeLabel: (type: string) =>
      ({ requirement: '需求文档', ui_mockup: 'UI原型图', api_doc: 'API文档' })[type] ?? '其他文件',
    handleSizeChange: vi.fn(),
    handleCurrentChange: vi.fn(),
  })

  const fileFormData = reactive({
    project_id: overrides.projectId ?? 1,
    iteration_id: null as number | null,
    name: '',
    resource_type: 'requirement',
    description: '',
    is_active: true,
  })

  const ctx = {
    iterationManager: reactive({
      selectedIterationId: overrides.selectedIterationId ?? null,
      getCurrentIterationTitle: () => overrides.currentIterationTitle ?? '迭代一期 (v1.0)',
    }),
    resourceList,
    resourceUpload: reactive({
      fileDialogVisible: overrides.dialogVisible ?? false,
      fileDialogTitle: overrides.dialogMode === 'edit' ? '编辑资源' : '上传文件',
      fileDialogMode: overrides.dialogMode ?? 'add',
      fileFormData,
      fileFormRules: {},
      isSubmitting: false,
    }),
    resourceOperations: {
      handleAnalyze: vi.fn(),
      handleDelete: vi.fn(),
    },
    iterationFormLocalRef: ref(null),
    fileFormLocalRef: ref<unknown>(null),
    uploaderRef: ref<unknown>(null),
    projects: ref([
      { id: 1, name: '项目A' },
      { id: 2, name: '项目B' },
    ]),
    validIterationsForSelectArray: ref([
      { id: 10, name: '迭代一期', version: 'v1.0' },
      { id: 11, name: '迭代二期' },
    ]),
    isFileSubmitting: computed(() => false),
    handleAddFileWrapper: vi.fn(),
    handleEditWrapper: vi.fn(),
    handleBatchUploadSuccess: vi.fn(),
    handleBatchUploadError: vi.fn(),
    handleFileSubmitWrapper: vi.fn(),
    handleReset: vi.fn(),
    init: vi.fn(),
    cleanup: vi.fn(),
  }
  mockCtx.current = ctx

  const wrapper = mount(ResourceTable, {
    global: {
      stubs,
      provide: { [ROWS_KEY]: resourceList.resources },
    },
  })
  return { ctx, wrapper }
}

const uiPrototypeRow: RowData = {
  id: 3,
  name: '登录页原型',
  resource_type: 'ui_mockup',
  source_type: 'ui_prototype',
  screen_count: 3,
  is_active: true,
  created_at: '2026-11-01 10:00',
}

const fileRow: RowData = {
  id: 5,
  name: '需求文档v1.2.docx',
  resource_type: 'requirement',
  source_type: 'file',
  is_active: false,
  upload_time: '2026-11-02 12:00',
}

describe('ResourceTable — 卡片头部', () => {
  it('展示当前迭代标题与上传按钮', () => {
    const { ctx, wrapper } = createCtx()

    expect(wrapper.find('.resource-title').text()).toBe('迭代一期 (v1.0)')
    const uploadBtn = wrapper.find('.resource-actions .el-button')
    expect(uploadBtn.text()).toContain('上传文件')
    expect(uploadBtn.attributes('disabled')).toBeUndefined()

    uploadBtn.trigger('click')
    expect(ctx.handleAddFileWrapper).toHaveBeenCalledTimes(1)
  })

  it('未选择项目时禁用上传按钮', () => {
    const { wrapper } = createCtx({ projectId: '' })

    expect(wrapper.find('.resource-actions .el-button').attributes('disabled')).toBeDefined()
  })
})

describe('ResourceTable — 表格数据', () => {
  it('按行渲染并可点击资源名进入编辑', async () => {
    const { ctx, wrapper } = createCtx({ resources: [uiPrototypeRow, fileRow] })

    const rows = wrapper.findAll('.el-table-column[data-prop="id"] .el-table-cell')
    expect(rows.map((r) => r.text())).toEqual(['3', '5'])

    const nameCells = wrapper.findAll('.el-table-column[data-prop="name"] .el-table-cell')
    expect(nameCells[0].text()).toBe('登录页原型3张图片')
    expect(nameCells[0].find('.el-link').attributes('href')).toBeUndefined()
    expect(nameCells[1].find('.el-link').attributes('href')).toBe('/api/v1/file/preview/5')

    await nameCells[0].find('.el-link').trigger('click')
    expect(ctx.handleEditWrapper).toHaveBeenCalledWith(uiPrototypeRow)
  })

  it('无 source_type 的记录以纯文本展示', () => {
    const { wrapper } = createCtx({
      resources: [{ id: 9, name: '手工记录', resource_type: 'other', is_active: true }],
    })

    const cell = wrapper.find('.el-table-column[data-prop="name"] .el-table-cell')
    expect(cell.find('.el-link').exists()).toBe(false)
    expect(cell.find('span').text()).toBe('手工记录')
  })

  it('类型列使用标签文案与颜色', () => {
    const { wrapper } = createCtx({ resources: [uiPrototypeRow, fileRow] })

    const tags = wrapper.findAll('.el-table-column[data-prop="resource_type"] .el-tag')
    expect(tags.map((t) => t.text())).toEqual(['UI原型图', '需求文档'])
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['success', 'primary'])
  })

  it('状态列按 is_active 展示启用/禁用', () => {
    const { wrapper } = createCtx({ resources: [uiPrototypeRow, fileRow] })

    const tags = wrapper.findAll('.el-table-column[data-prop="is_active"] .el-tag')
    expect(tags.map((t) => t.text())).toEqual(['启用', '禁用'])
    expect(tags.map((t) => t.attributes('data-type'))).toEqual(['success', 'info'])
  })

  it('上传时间优先取 upload_time，其次 created_at，缺失展示占位', () => {
    const { wrapper } = createCtx({
      resources: [uiPrototypeRow, fileRow, { id: 10, name: '无时间', is_active: true }],
    })

    const cells = wrapper.findAll('.el-table-column[data-prop="upload_time"] .el-table-cell')
    expect(cells.map((c) => c.text())).toEqual(['2026-11-01 10:00', '2026-11-02 12:00', '-'])
  })

  it('操作列按资源类型切换编辑/查看文案并转发事件', async () => {
    const { ctx, wrapper } = createCtx({ resources: [uiPrototypeRow, fileRow] })

    const actionCells = wrapper.findAll('.el-table-column[data-prop=""] .table-actions')
    expect(actionCells).toHaveLength(2)
    const firstButtons = actionCells[0].findAll('.el-button')
    expect(firstButtons.map((b) => b.text())).toEqual(['AI分析', '查看', '删除'])
    expect(actionCells[1].findAll('.el-button').map((b) => b.text())).toEqual([
      'AI分析',
      '编辑',
      '删除',
    ])

    await firstButtons[0].trigger('click')
    await firstButtons[1].trigger('click')
    await firstButtons[2].trigger('click')
    expect(ctx.resourceOperations.handleAnalyze).toHaveBeenCalledWith(uiPrototypeRow)
    expect(ctx.handleEditWrapper).toHaveBeenCalledWith(uiPrototypeRow)
    expect(ctx.resourceOperations.handleDelete).toHaveBeenCalledWith(uiPrototypeRow)
  })
})

describe('ResourceTable — 空态与分页', () => {
  it('加载完成且无数据时展示空态', () => {
    const { wrapper } = createCtx({ resources: [] })

    expect(wrapper.find('.empty-resources').exists()).toBe(true)
    expect(wrapper.find('.empty-title').text()).toBe('暂无资源')
    expect(wrapper.find('.el-pagination').exists()).toBe(false)
  })

  it('加载中不展示空态', () => {
    const { wrapper } = createCtx({ resources: [], isLoading: true })

    expect(wrapper.find('.empty-resources').exists()).toBe(false)
  })

  it('空态按钮也走上传入口', async () => {
    const { ctx, wrapper } = createCtx({ resources: [] })

    await wrapper.find('.empty-resources .el-button').trigger('click')

    expect(ctx.handleAddFileWrapper).toHaveBeenCalledTimes(1)
  })

  it('total 大于 0 时渲染分页并转发翻页事件', () => {
    const { ctx, wrapper } = createCtx({ resources: [fileRow], total: 40 })

    const pagination = wrapper.findComponent(ElPaginationStub)
    expect(pagination.exists()).toBe(true)
    expect(pagination.attributes('data-total')).toBe('40')
    expect(pagination.attributes('data-page')).toBe('2')
    expect(pagination.attributes('data-size')).toBe('20')

    pagination.vm.$emit('size-change', 50)
    pagination.vm.$emit('current-change', 3)

    expect(ctx.resourceList.handleSizeChange).toHaveBeenCalledWith(50)
    expect(ctx.resourceList.handleCurrentChange).toHaveBeenCalledWith(3)
  })
})

describe('ResourceTable — 上传/编辑弹窗', () => {
  it('add 模式展示文件上传组件并隐藏编辑字段', () => {
    const { wrapper } = createCtx({ dialogVisible: true, dialogMode: 'add' })

    const dialog = wrapper.find('.el-dialog')
    expect(dialog.attributes('data-title')).toBe('上传文件')

    const uploader = wrapper.find('.uploader-stub')
    expect(uploader.exists()).toBe(true)
    expect(uploader.attributes('data-project')).toBe('1')
    expect(uploader.attributes('data-show-button')).toBe('false')

    const labels = wrapper.findAll('.el-form-item').map((i) => i.attributes('data-label'))
    expect(labels).toContain('选择文件')
    expect(labels).not.toContain('资源名称')
    expect(labels).not.toContain('资源类型')
    expect(labels).not.toContain('启用状态')
    expect(wrapper.findAll('.el-switch')).toHaveLength(0)
  })

  it('edit 模式展示名称、类型、启用状态且不再渲染上传组件', () => {
    const { wrapper } = createCtx({ dialogVisible: true, dialogMode: 'edit' })

    const labels = wrapper.findAll('.el-form-item').map((i) => i.attributes('data-label'))
    expect(labels).toEqual(expect.arrayContaining(['资源名称', '资源类型', '启用状态']))
    expect(labels).not.toContain('选择文件')
    expect(wrapper.find('.uploader-stub').exists()).toBe(false)
    const typeItem = wrapper
      .findAll('.el-form-item')
      .find((i) => i.attributes('data-prop') === 'resource_type')
    expect(typeItem!.findAll('.el-option').map((o) => o.text())).toEqual([
      '需求文档',
      'UI原型图',
      'API文档',
      '测试数据',
      '其他文件',
    ])
  })

  it('未选择迭代时展示迭代下拉与未分类选项', () => {
    const { wrapper } = createCtx({ dialogVisible: true, dialogMode: 'add' })

    const iterationItem = wrapper
      .findAll('.el-form-item')
      .find((i) => i.attributes('data-prop') === 'iteration_id')
    expect(iterationItem).toBeDefined()
    expect(iterationItem!.findAll('.el-option').map((o) => o.text())).toEqual([
      '不归属任何迭代（未分类）',
      '迭代一期 (v1.0)',
      '迭代二期 (v1.0)',
    ])
  })

  it('已选中具体迭代时以标签展示迭代名', () => {
    const { wrapper } = createCtx({ dialogVisible: true, selectedIterationId: 10 })

    expect(wrapper.find('.iteration-hint .el-tag').text()).toBe('迭代一期 (v1.0)')
    expect(wrapper.find('.iteration-hint .el-tag').attributes('data-type')).toBe('success')
    expect(
      wrapper.findAll('.el-form-item').some((i) => i.attributes('data-prop') === 'iteration_id')
    ).toBe(false)
  })

  it('选中未分类时展示未分类标签', () => {
    const { wrapper } = createCtx({ dialogVisible: true, selectedIterationId: 0 })

    expect(wrapper.find('.iteration-hint .el-tag').text()).toBe('未分类')
    expect(wrapper.find('.iteration-hint .el-tag').attributes('data-type')).toBe('info')
  })

  it('底部按钮分别关闭弹窗与提交表单', async () => {
    const { ctx, wrapper } = createCtx({ dialogVisible: true, dialogMode: 'add' })

    const footerButtons = wrapper.findAll('.el-dialog__footer .el-button')
    expect(footerButtons.map((b) => b.text())).toEqual(['取消', '确定'])

    await footerButtons[1].trigger('click')
    expect(ctx.handleFileSubmitWrapper).toHaveBeenCalledTimes(1)

    await footerButtons[0].trigger('click')
    expect(ctx.resourceUpload.fileDialogVisible).toBe(false)
  })

  it('弹窗关闭时不渲染内容', () => {
    const { wrapper } = createCtx({ dialogVisible: false })

    expect(wrapper.find('.el-dialog').exists()).toBe(false)
  })
})
