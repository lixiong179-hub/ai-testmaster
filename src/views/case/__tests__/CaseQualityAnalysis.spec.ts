import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, h, inject, ref, type Ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useCaseQualityAnalysis', () => ({
  useCaseQualityAnalysis: () => state.current,
}))

import CaseQualityAnalysis from '../CaseQualityAnalysis.vue'

const ROWS_KEY = Symbol('rows')

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: undefined },
    placeholder: { type: String, default: '' },
    filterable: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change'],
  template: '<div class="el-select" :data-placeholder="placeholder"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElCardStub = defineComponent({
  name: 'ElCard',
  props: { shadow: { type: String, default: 'always' } },
  template: '<div class="el-card"><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, size: { type: String, default: 'default' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElProgressStub = defineComponent({
  name: 'ElProgress',
  props: {
    percentage: { type: Number, default: 0 },
    strokeWidth: { type: Number, default: 6 },
    color: { type: String, default: '' },
  },
  template: '<div class="el-progress" :data-percentage="percentage" :data-color="color"></div>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  props: { size: { type: Number, default: 0 }, color: { type: String, default: '' } },
  template: '<i class="el-icon"><slot /></i>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] }, border: { type: Boolean, default: false } },
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

const ElDescriptionsStub = defineComponent({
  name: 'ElDescriptions',
  props: { column: { type: Number, default: 1 }, border: { type: Boolean, default: false } },
  template: '<div class="el-descriptions"><slot /></div>',
})

const ElDescriptionsItemStub = defineComponent({
  name: 'ElDescriptionsItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="desc-item" :data-label="label"><slot /></div>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  template: '<div class="el-dialog" v-if="modelValue" :data-title="title"><slot /></div>',
})

const stubs = {
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElCard: ElCardStub,
  ElTag: ElTagStub,
  ElProgress: ElProgressStub,
  ElIcon: ElIconStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElDescriptions: ElDescriptionsStub,
  ElDescriptionsItem: ElDescriptionsItemStub,
  ElEmpty: ElEmptyStub,
  ElDialog: ElDialogStub,
}

type Dimension = {
  name: string
  label?: string
  score: number
  summary: string
  detail?: string
  suggestions?: string[]
}

type AnalysisResult = {
  overall_score: number
  dimensions: Dimension[]
  optimization?: { items: Array<Record<string, unknown>> }
}

const dimensions: Dimension[] = [
  {
    name: 'coverage',
    label: '覆盖率',
    score: 85,
    summary: '覆盖较完整',
    detail: '覆盖明细',
    suggestions: ['补充边界用例', '补充异常流', '补充兼容性', '第四条不应展示'],
  },
  {
    name: 'complexity',
    score: 55,
    summary: '步骤偏长',
    suggestions: [],
  },
]

const optimizationItems = [
  { type: '合并', target: '用例A/用例B', action: '合并重复步骤', impact: '高' },
]

type PageOverrides = {
  analysisResult?: AnalysisResult | null
  loading?: boolean
  costSummary?: Record<string, unknown> | null
  costLoading?: boolean
  dialogVisible?: boolean
  dialogContent?: string
}

function setup(overrides: PageOverrides = {}) {
  const analysisRef = ref<AnalysisResult | null>(overrides.analysisResult ?? null)
  const handlers = {
    handleProjectChange: vi.fn(),
    showDetail: vi.fn(),
  }
  state.current = {
    loading: ref(overrides.loading ?? false),
    projects: ref([
      { id: 1, name: '项目A' },
      { id: 2, name: '项目B' },
    ]),
    selectedProjectId: ref(1),
    analysisResult: analysisRef,
    dialogVisible: ref(overrides.dialogVisible ?? false),
    dialogContent: ref(overrides.dialogContent ?? ''),
    overallScore: computed(() => analysisRef.value?.overall_score ?? 0),
    scoreLevel: computed(() => {
      const s = analysisRef.value?.overall_score ?? 0
      return s >= 80 ? 'success' : s >= 60 ? 'warning' : 'danger'
    }),
    scoreLabel: computed(() => {
      const s = analysisRef.value?.overall_score ?? 0
      return s >= 80 ? '优秀' : s >= 60 ? '良好' : '需改进'
    }),
    costSummary: ref(overrides.costSummary ?? null),
    costLoading: ref(overrides.costLoading ?? false),
    ...handlers,
  }

  const items = analysisRef.value?.optimization?.items ?? []
  const wrapper = mount(CaseQualityAnalysis, {
    global: { stubs, provide: { [ROWS_KEY]: ref(items) } },
  })
  return { wrapper, handlers, analysisRef }
}

const richResult: AnalysisResult = {
  overall_score: 85,
  dimensions,
  optimization: { items: optimizationItems },
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('CaseQualityAnalysis — 页头与空态', () => {
  it('展示标题、项目下拉与选项，并转发切换', async () => {
    const { wrapper, handlers } = setup()

    expect(wrapper.find('.page-title').text()).toBe('用例质量分析')
    const select = wrapper.findComponent(ElSelectStub)
    expect(select.attributes('data-placeholder')).toBe('请选择项目')
    expect(wrapper.findAll('.el-option').map((o) => o.text())).toEqual(['项目A', '项目B'])

    select.vm.$emit('change', 2)
    expect(handlers.handleProjectChange).toHaveBeenCalledTimes(1)
  })

  it('未加载结果时展示引导空态', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-empty').text()).toBe('请选择项目后查看质量分析')
  })

  it('加载中不展示空态', () => {
    const { wrapper } = setup({ loading: true })

    expect(wrapper.find('.el-empty').exists()).toBe(false)
  })
})

describe('CaseQualityAnalysis — 评分与维度', () => {
  it('评分环展示分数、等级与描边', () => {
    const { wrapper } = setup({ analysisResult: richResult })

    expect(wrapper.find('.score-ring').classes()).toContain('success')
    expect(wrapper.find('.score-num').text()).toBe('85')
    expect(wrapper.find('.score-label').text()).toBe('优秀')
    expect(wrapper.find('.score-desc').text()).toContain('综合评分基于覆盖率、复杂度、冗余度和成本')

    const circle = wrapper.findAll('circle')[1]
    expect(circle.attributes('stroke')).toBe('#67c23a')
    expect(circle.attributes('stroke-dasharray')).toMatch(/^266\.9\d* 314$/)
  })

  it('维度卡按标签、分值与颜色渲染', () => {
    const { wrapper } = setup({ analysisResult: richResult })

    const cards = wrapper.findAll('.dim-card')
    expect(cards).toHaveLength(2)
    expect(cards[0].find('.dim-name').text()).toBe('覆盖率')
    const tag = cards[0].find('.el-tag')
    expect(tag.text()).toBe('85分')
    expect(tag.attributes('data-type')).toBe('success')
    expect(cards[0].find('.el-progress').attributes('data-percentage')).toBe('85')
    expect(cards[0].find('.el-progress').attributes('data-color')).toBe('#67c23a')

    expect(cards[1].find('.dim-name').text()).toBe('complexity')
    expect(cards[1].find('.el-tag').attributes('data-type')).toBe('danger')
    expect(cards[1].find('.el-progress').attributes('data-color')).toBe('#f56c6c')
    expect(cards[1].find('.dim-summary').text()).toBe('步骤偏长')
  })

  it('建议最多展示三条', () => {
    const { wrapper } = setup({ analysisResult: richResult })

    const suggestions = wrapper.findAll('.dim-card')[0].findAll('.suggestion-item')
    expect(suggestions).toHaveLength(3)
    expect(suggestions.map((s) => s.text())).toEqual(['补充边界用例', '补充异常流', '补充兼容性'])
    expect(wrapper.findAll('.dim-card')[1].find('.dim-suggestions').exists()).toBe(false)
  })

  it('点击维度卡展示详情内容', async () => {
    const { wrapper, handlers } = setup({ analysisResult: richResult })

    await wrapper.findAll('.dim-card')[0].trigger('click')
    await wrapper.findAll('.dim-card')[1].trigger('click')

    expect(handlers.showDetail).toHaveBeenNthCalledWith(1, '覆盖明细')
    expect(handlers.showDetail).toHaveBeenNthCalledWith(2, 'complexity')
  })
})

describe('CaseQualityAnalysis — 优化建议与成本', () => {
  it('渲染优化建议表四列与数据行', () => {
    const { wrapper } = setup({ analysisResult: richResult })

    expect(wrapper.find('.optimization-section h3').text()).toBe('优化建议')
    expect(wrapper.findAll('.el-table-column').map((c) => c.attributes('data-label'))).toEqual([
      '类型',
      '目标',
      '建议操作',
      '预期影响',
    ])
    expect(wrapper.find('.el-table').attributes('data-rows')).toBe('1')
    const cells = wrapper.findAll('.el-table-column[data-prop="action"] .el-table-cell')
    expect(cells.map((c) => c.text())).toEqual(['合并重复步骤'])
  })

  it('无优化建议时不渲染该区块', () => {
    const { wrapper } = setup({ analysisResult: { overall_score: 70, dimensions: [] } })

    expect(wrapper.find('.optimization-section').exists()).toBe(false)
  })

  it('成本统计按三项展示并兜底占位', () => {
    const { wrapper } = setup({
      analysisResult: richResult,
      costSummary: { total_tokens: 1234, total_api_calls: 12, estimated_cost: 0.5 },
    })

    expect(wrapper.find('.cost-section h3').text()).toBe('成本统计')
    const items = wrapper.findAll('.desc-item')
    expect(items.map((i) => i.attributes('data-label'))).toEqual([
      '总Token消耗',
      '总API调用次数',
      '估算成本',
    ])
    expect(items.map((i) => i.text())).toEqual(['1234', '12', '0.5'])
  })

  it('成本字段缺失时展示占位符', () => {
    const { wrapper } = setup({ analysisResult: richResult, costSummary: {} })

    expect(wrapper.findAll('.desc-item').map((i) => i.text())).toEqual(['-', '-', '-'])
  })

  it('无成本数据时不渲染成本区块', () => {
    const { wrapper } = setup({ analysisResult: richResult })

    expect(wrapper.find('.cost-section').exists()).toBe(false)
  })
})

describe('CaseQualityAnalysis — 详情弹窗', () => {
  it('弹窗打开时展示详情文案', () => {
    const { wrapper } = setup({
      analysisResult: richResult,
      dialogVisible: true,
      dialogContent: '详细说明',
    })

    const dialog = wrapper.find('.el-dialog')
    expect(dialog.attributes('data-title')).toBe('详细分析')
    expect(dialog.text()).toBe('详细说明')
  })
})
