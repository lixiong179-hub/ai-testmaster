import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, ref } from 'vue'
import { XmindImportKey } from '../../useXmindImport'
import XmindPreviewStep from '../XmindPreviewStep.vue'

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' }, effect: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { type: { type: String, default: '' }, title: { type: String, default: '' } },
  template: '<div class="el-alert" :data-type="type"><slot name="title" /><slot /></div>',
})

const ElRadioGroupStub = defineComponent({
  name: 'ElRadioGroup',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue', 'change'],
  template: '<div class="el-radio-group"><slot /></div>',
})

const ElRadioButtonStub = defineComponent({
  name: 'ElRadioButton',
  props: { value: { type: String, default: '' } },
  emits: ['click'],
  template: '<button class="el-radio-button" :data-value="value"><slot /></button>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  template: '<div class="el-table"><slot /></div>',
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { prop: { type: String, default: '' }, label: { type: String, default: '' } },
  template: '<div class="el-table-column" :data-prop="prop" />',
})

const ElPaginationStub = defineComponent({
  name: 'ElPagination',
  props: {
    currentPage: { type: Number, default: 1 },
    pageSize: { type: Number, default: 10 },
    total: { type: Number, default: 0 },
  },
  template: '<div class="el-pagination" :data-total="total" :data-page="currentPage" />',
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: { percentage: { type: Number, default: 0 } },
  template: '<div class="el-progress">{{ percentage }}%</div>',
})

const stubs = {
  ElTag: ElTagStub,
  ElAlert: ElAlertStub,
  ElRadioGroup: ElRadioGroupStub,
  ElRadioButton: ElRadioButtonStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElPagination: ElPaginationStub,
  ElProgress: ElProgressStub,
}

type PreviewPoint = { module: string; point: string; priority: number }

function setup(
  options: {
    step?: number
    points?: PreviewPoint[]
    cases?: Record<string, unknown>[]
    skipped?: number
    tab?: 'points' | 'cases'
  } = {}
) {
  const pointsSource = ref<PreviewPoint[]>(
    options.points ?? [{ module: '登录', point: '账号登录', priority: 1 }]
  )
  const ctx = {
    currentStep: ref(options.step ?? 1),
    loading: ref(false),
    aiEnhance: ref(false),
    importProgress: ref<Record<string, number> | null>(null),
    importProgressText: ref(''),
    previewData: pointsSource,
    previewCaseData: ref(options.cases ?? []),
    previewSkippedCount: ref(options.skipped ?? 0),
    previewSkippedReasons: ref<string[]>([]),
    activePreviewTab: ref<'points' | 'cases'>(options.tab ?? 'points'),
    currentPage: ref(3),
    pageSize: ref(10),
    isCasePreviewMode: ref(false),
    hasCasePreview: ref((options.cases ?? []).length > 0),
    currentPreviewTotal: ref(42),
    highPriorityCount: ref(2),
    mediumPriorityCount: ref(3),
    lowPriorityCount: ref(4),
    previewAiTimeout: ref(false),
    previewTotalPaths: ref(20),
    isAiSamplePreview: ref(false),
    paginatedPreviewData: ref(pointsSource.value),
    paginatedPreviewCases: ref(options.cases ?? []),
    getPriorityType: vi.fn(() => 'danger'),
    getPriorityLabel: vi.fn(() => '高'),
    formatCaseStepSummary: vi.fn(() => '步骤摘要'),
  }

  const wrapper = mount(XmindPreviewStep, {
    global: { stubs, provide: { [XmindImportKey as symbol]: ctx } },
  })
  return { ctx, wrapper }
}

describe('XmindPreviewStep — 渲染条件', () => {
  it('非预览步骤不渲染', () => {
    const { wrapper } = setup({ step: 2 })

    expect(wrapper.find('.preview-area').exists()).toBe(false)
  })

  it('展示测试点与优先级统计标签', () => {
    const { wrapper } = setup()

    const tags = wrapper.findAll('.preview-header .el-tag').map((t) => t.text())
    expect(tags).toEqual(['测试点 1 条', '高优先级: 2', '中优先级: 3', '低优先级: 4'])
  })

  it('存在用例预览时追加用例数与场景树标签', () => {
    const { ctx, wrapper } = setup({ cases: [{ title: 'A' }, { title: 'B' }] })
    ctx.isCasePreviewMode.value = true

    return nextTick().then(() => {
      const tags = wrapper.findAll('.preview-header .el-tag').map((t) => t.text())
      expect(tags).toContain('测试用例 2 条')
      expect(tags).toContain('识别为场景树导入')
    })
  })

  it('跳过节点时展示告警与原因', async () => {
    const { ctx, wrapper } = setup({ skipped: 3 })
    ctx.previewSkippedReasons.value = ['模块为空', '测试点为空']
    await nextTick()

    const alert = wrapper.find('.preview-skipped-alert')
    expect(alert.text()).toContain('检测到 3 个节点未导入预览')
    expect(alert.findAll('.preview-skipped-reasons .el-tag').map((t) => t.text())).toEqual([
      '模块为空',
      '测试点为空',
    ])
    expect(wrapper.findAll('.preview-header .el-tag').map((t) => t.text())).toContain(
      '已跳过 3 个节点'
    )
  })
})

describe('XmindPreviewStep — 模式提示', () => {
  it('场景树模式与 AI 超时、采样提示可叠加', async () => {
    const { ctx, wrapper } = setup()
    ctx.isCasePreviewMode.value = true
    ctx.previewAiTimeout.value = true
    ctx.isAiSamplePreview.value = true
    await nextTick()

    expect(wrapper.find('.preview-mode-alert').text()).toContain('双通道导入')
    expect(wrapper.find('.preview-ai-timeout-alert').text()).toContain('AI增强解析超时')
    expect(wrapper.findAll('.preview-mode-alert')[1].text()).toContain(
      '已解析前 0 条路径（共 20 条）'
    )
  })

  it('无提示条件时不渲染任何告警', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-alert').exists()).toBe(false)
  })
})

describe('XmindPreviewStep — 视图切换与分页', () => {
  it('有双视图时展示切换器，默认渲染测试点表格', () => {
    const { wrapper } = setup({ cases: [{ title: 'A' }] })

    const switcher = wrapper.find('.preview-switcher')
    expect(switcher.exists()).toBe(true)
    expect(switcher.findAll('.el-radio-button').map((b) => b.text())).toEqual([
      '测试点预览',
      '测试用例预览',
    ])

    const table = wrapper.findComponent(ElTableStub)
    expect(table.props('data')).toEqual([{ module: '登录', point: '账号登录', priority: 1 }])
  })

  it('切到用例视图渲染用例表格并保持分页', () => {
    const cases = [{ title: 'A', step_count: 2 }]
    const { wrapper } = setup({ cases, tab: 'cases' })

    const table = wrapper.findComponent(ElTableStub)
    expect(table.props('data')).toEqual(cases)
    expect(wrapper.find('.el-pagination').attributes('data-total')).toBe('42')
    expect(wrapper.find('.el-pagination').attributes('data-page')).toBe('3')
  })

  it('无用例时切回单表格视图', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.preview-switcher').exists()).toBe(false)
    expect(wrapper.findAllComponents(ElTableStub)).toHaveLength(1)
  })
})

describe('XmindPreviewStep — 解析进度', () => {
  it('仅在加载中且开启增强时展示进度文案', async () => {
    const { ctx, wrapper } = setup()
    expect(wrapper.find('.import-progress-area').exists()).toBe(false)

    ctx.loading.value = true
    ctx.aiEnhance.value = true
    ctx.importProgressText.value = '正在解析第 2 批'
    await nextTick()

    expect(wrapper.find('.import-progress-text').text()).toBe('正在解析第 2 批')
  })

  it('多批次时渲染批次进度条', async () => {
    const { ctx, wrapper } = setup()
    ctx.loading.value = true
    ctx.aiEnhance.value = true
    ctx.importProgressText.value = '解析中'
    ctx.importProgress.value = { total_batches: 4, completed_batches: 1, percentage: 25 }
    await nextTick()

    expect(wrapper.find('.el-progress').text()).toBe('25%')
  })
})
