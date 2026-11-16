import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, inject, ref, type Ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useTestPointExtract', () => ({
  useTestPointExtract: () => state.current,
}))

import TestPointExtractDialog from '../TestPointExtractDialog.vue'

const ROWS_KEY = Symbol('rows')

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue', 'closed'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: undefined },
    placeholder: { type: String, default: '' },
    filterable: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  template:
    '<div class="el-select" :data-placeholder="placeholder" :data-filterable="filterable" :data-loading="loading"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value"><slot>{{ label }}</slot></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :data-loading="loading" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: { percentage: { type: Number, default: 0 } },
  template: '<div class="el-progress" :data-percentage="percentage"></div>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template:
    '<div class="el-empty"><slot name="image" /><span class="empty-text" :data-desc="description"></span></div>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] }, emptyText: { type: String, default: '' } },
  template: '<div class="el-table" :data-rows="data.length"><slot /></div>',
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { prop: { type: String, default: '' }, label: { type: String, default: '' } },
  setup(props, { slots }) {
    const rowsRef = inject<Ref<Array<Record<string, unknown>>>>(ROWS_KEY, ref([]))
    return () =>
      h(
        'div',
        { class: 'el-table-column', 'data-prop': props.prop, 'data-label': props.label },
        rowsRef.value.map((row, index) =>
          h(
            'div',
            { class: 'el-table-cell' },
            slots.default ? slots.default({ row, $index: index }) : String(row[props.prop] ?? '')
          )
        )
      )
  },
})

const stubs = {
  ElDialog: ElDialogStub,
  ElTag: ElTagStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElButton: ElButtonStub,
  ElProgress: ElProgressStub,
  ElEmpty: ElEmptyStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
}

type PointRow = { module: string; point: string; priority: number }

type ExtractOverrides = {
  loadingFiles?: boolean
  extracting?: boolean
  saving?: boolean
  progress?: number
  progressText?: string
  selectedFileId?: number | null
  requirementFiles?: Array<Record<string, unknown>>
  points?: PointRow[]
  visible?: boolean
}

function setup(overrides: ExtractOverrides = {}) {
  const points = ref<PointRow[]>(overrides.points ?? [])
  const requirementFiles = ref(
    overrides.requirementFiles ?? [
      { id: 31, file_name: '需求文档v1.docx', extract_status: 'pending' },
      { id: 32, file_name: '需求文档v2.docx', extract_status: 'done' },
    ]
  )

  state.current = {
    loadingFiles: ref(overrides.loadingFiles ?? false),
    extracting: ref(overrides.extracting ?? false),
    saving: ref(overrides.saving ?? false),
    progress: ref(overrides.progress ?? 0),
    progressText: ref(overrides.progressText ?? ''),
    selectedFileId: ref<number | null>(overrides.selectedFileId ?? null),
    requirementFiles,
    extractedPoints: points,
    highPriorityCount: ref(1),
    mediumPriorityCount: ref(2),
    lowPriorityCount: ref(3),
    handleExtract: vi.fn(),
    handleSave: vi.fn().mockResolvedValue(undefined),
    resetState: vi.fn(),
    priorityText: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority] ?? '低',
    priorityTagType: (priority: number) =>
      ({ 1: 'danger', 2: 'warning', 3: 'info' })[priority] ?? 'info',
    formatExtractStatus: (status?: string) =>
      (({ pending: '未提取', done: '已提取' }) as Record<string, string>)[status ?? ''] ?? '未知',
  }

  const wrapper = mount(TestPointExtractDialog, {
    props: {
      visible: overrides.visible ?? true,
      projectId: 9,
      initialFileId: 33,
    },
    global: {
      stubs,
      provide: { [ROWS_KEY]: points },
    },
  })
  return { wrapper, points, state: state.current! }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('TestPointExtractDialog — 结构', () => {
  it('展示标题、引导文案与需求提取标签', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('从需求提取测试点')
    expect(wrapper.find('.hero-title').text()).toBe('在当前工作台内完成提取和入库')
    expect(wrapper.find('.hero-subtitle').text()).toContain('选择一个需求文档后即可直接提取')
    expect(wrapper.find('.dialog-hero .el-tag').text()).toBe('需求提取')
  })

  it('文件下拉按需求文档渲染选项与提取状态', () => {
    const { wrapper } = setup()

    const select = wrapper.find('.el-select')
    expect(select.attributes('data-placeholder')).toBe('请选择需求文档')
    expect(select.attributes('data-filterable')).toBe('true')

    const options = wrapper.findAll('.el-option')
    expect(options).toHaveLength(2)
    expect(options[0].find('span').text()).toBe('需求文档v1.docx')
    expect(options[0].find('.el-tag').text()).toBe('未提取')
    expect(options[1].find('.el-tag').text()).toBe('已提取')
  })

  it('文件加载中标记选择器 loading', () => {
    const { wrapper } = setup({ loadingFiles: true })

    expect(wrapper.find('.el-select').attributes('data-loading')).toBe('true')
  })
})

describe('TestPointExtractDialog — 工具栏状态', () => {
  it('未选择文件时禁用提取按钮', async () => {
    const { wrapper, state } = setup()
    const extractBtn = wrapper.findAll('.extract-toolbar .el-button')[0]

    expect(extractBtn.attributes('disabled')).toBeDefined()
    ;(state.selectedFileId as Ref<number | null>).value = 31
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.extract-toolbar .el-button')[0].attributes('disabled')).toBeUndefined()
    await wrapper.findAll('.extract-toolbar .el-button')[0].trigger('click')
    expect(state.handleExtract).toHaveBeenCalledTimes(1)
  })

  it('无提取结果时禁用保存按钮', async () => {
    const { wrapper, points } = setup()
    const saveBtn = () => wrapper.findAll('.extract-toolbar .el-button')[1]

    expect(saveBtn().attributes('disabled')).toBeDefined()

    points.value = [{ module: '登录', point: '锁定', priority: 2 }]
    await wrapper.vm.$nextTick()

    expect(saveBtn().attributes('disabled')).toBeUndefined()
  })

  it('保存成功后抛出 saved 并关闭弹窗', async () => {
    const { wrapper, state, points } = setup()
    points.value = [{ module: '登录', point: '锁定', priority: 1 }]
    await wrapper.vm.$nextTick()

    await wrapper.findAll('.extract-toolbar .el-button')[1].trigger('click')
    await flushPromises()

    expect(state.handleSave).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('saved')).toHaveLength(1)
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('保存中按钮展示 loading', () => {
    const { wrapper, points } = setup({ saving: true })
    points.value = [{ module: '登录', point: '锁定', priority: 1 }]

    return wrapper.vm.$nextTick().then(() => {
      expect(wrapper.findAll('.extract-toolbar .el-button')[1].attributes('data-loading')).toBe(
        'true'
      )
    })
  })
})

describe('TestPointExtractDialog — 进度与空态', () => {
  it('提取中展示进度条与进度文案', () => {
    const { wrapper } = setup({
      extracting: true,
      progress: 40,
      progressText: '正在解析第 2 个章节',
    })

    expect(wrapper.find('.progress-panel').exists()).toBe(true)
    expect(wrapper.find('.el-progress').attributes('data-percentage')).toBe('40')
    expect(wrapper.find('.progress-text').text()).toBe('正在解析第 2 个章节')
    expect(wrapper.find('.el-table').exists()).toBe(false)
  })

  it('无需求文档且加载完毕时展示引导空态', () => {
    const { wrapper } = setup({ requirementFiles: [] })

    const empty = wrapper.find('.el-empty')
    expect(empty.exists()).toBe(true)
    expect(empty.find('.empty-text').attributes('data-desc')).toBe(
      '当前项目暂无需求文档，请先在资源管理中上传 requirement 类型文件'
    )
    expect(wrapper.find('.el-table').exists()).toBe(false)
  })

  it('加载中即使无文档也不展示空态', () => {
    const { wrapper } = setup({ requirementFiles: [], loadingFiles: true })

    expect(wrapper.find('.el-empty').exists()).toBe(false)
  })
})

describe('TestPointExtractDialog — 结果区', () => {
  it('按结果条数与优先级分布渲染摘要', async () => {
    const { wrapper, points } = setup()
    points.value = [
      { module: '登录', point: '锁定', priority: 1 },
      { module: '支付', point: '幂等', priority: 2 },
    ]
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.extract-summary .el-tag').map((t) => t.text())).toEqual([
      '共 2 条',
      '高优先级 1',
      '中优先级 2',
      '低优先级 3',
    ])
  })

  it('无结果时不渲染摘要，仅保留空表格', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.extract-summary').exists()).toBe(false)
    expect(wrapper.find('.el-table').attributes('data-rows')).toBe('0')
  })

  it('表格按列渲染模块、测试点与优先级标签', async () => {
    const { wrapper, points } = setup()
    points.value = [{ module: '登录', point: '账号锁定', priority: 1 }]
    await wrapper.vm.$nextTick()

    const cells = (prop: string) =>
      wrapper.findAll(`.el-table-column[data-prop="${prop}"] .el-table-cell`)
    expect(cells('module').map((c) => c.text())).toEqual(['登录'])
    expect(cells('point').map((c) => c.text())).toEqual(['账号锁定'])

    const tag = wrapper.find('.el-table-column[data-prop="priority"] .el-tag')
    expect(tag.text()).toBe('高')
    expect(tag.attributes('data-type')).toBe('danger')
  })
})

describe('TestPointExtractDialog — 关闭', () => {
  it('底部关闭按钮抛出 update:visible=false', async () => {
    const { wrapper } = setup()

    await wrapper.find('.el-dialog__footer .el-button').trigger('click')

    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })

  it('弹窗关闭动画结束触发状态重置', () => {
    const { wrapper, state } = setup()

    wrapper.findComponent(ElDialogStub).vm.$emit('closed')

    expect(state.resetState).toHaveBeenCalledTimes(1)
  })
})
