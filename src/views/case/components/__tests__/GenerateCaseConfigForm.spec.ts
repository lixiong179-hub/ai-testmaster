import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { ElMessageBox } from 'element-plus'

const store = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => store.current,
}))

import GenerateCaseConfigForm from '../GenerateCaseConfigForm.vue'

const ElCardStub = defineComponent({
  name: 'ElCard',
  template:
    '<div class="el-card"><div class="el-card__header"><slot name="header" /></div><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    size: { type: String, default: 'default' },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :data-loading="loading" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: {
    model: { type: Object, default: () => ({}) },
    labelWidth: { type: String, default: '' },
  },
  template: '<form class="el-form"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: {
    type: { type: String, default: 'primary' },
    effect: { type: String, default: 'light' },
    size: { type: String, default: 'default' },
    round: { type: Boolean, default: false },
  },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: {
    type: { type: String, default: 'info' },
    title: { type: String, default: '' },
    closable: { type: Boolean, default: true },
    showIcon: { type: Boolean, default: false },
  },
  template:
    '<div class="el-alert" :data-type="type"><span class="alert-title"><slot name="title">{{ title }}</slot></span><slot /></div>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: undefined },
    placeholder: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'change'],
  template: '<div class="el-select" :data-placeholder="placeholder"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: {
    modelValue: { type: String, default: '' },
    type: { type: String, default: 'text' },
    rows: { type: Number, default: 2 },
    placeholder: { type: String, default: '' },
  },
  template:
    '<input class="el-input" :data-type="type" :value="modelValue" :placeholder="placeholder" />',
})

const ElSwitchStub = defineComponent({
  name: 'ElSwitch',
  props: {
    modelValue: { type: Boolean, default: false },
    activeText: { type: String, default: '' },
    inactiveText: { type: String, default: '' },
  },
  template:
    '<div class="el-switch" :data-value="modelValue" :data-active="activeText" :data-inactive="inactiveText"></div>',
})

const ElRadioGroupStub = defineComponent({
  name: 'ElRadioGroup',
  props: { modelValue: { type: String, default: '' }, size: { type: String, default: '' } },
  template: '<div class="el-radio-group" :data-value="modelValue"><slot /></div>',
})

const ElRadioButtonStub = defineComponent({
  name: 'ElRadioButton',
  props: { value: { type: String, default: '' } },
  template: '<label class="el-radio-button" :data-value="value"><slot /></label>',
})

const ElStatisticStub = defineComponent({
  name: 'ElStatistic',
  props: { title: { type: String, default: '' }, value: { type: Number, default: 0 } },
  template: '<div class="el-statistic" :data-title="title" :data-value="value"></div>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTooltipStub = defineComponent({
  name: 'ElTooltip',
  props: { content: { type: String, default: '' }, placement: { type: String, default: '' } },
  template: '<span class="el-tooltip"><slot /></span>',
})

const ContextHealthPanelStub = defineComponent({
  name: 'ContextHealthPanel',
  props: {
    contextStats: { type: Object, default: null },
    warnings: { type: Array, default: () => [] },
    evidenceRefs: { type: Object, default: null },
  },
  template: '<div class="health-panel-stub"></div>',
})

const EvidenceRefsPanelStub = defineComponent({
  name: 'EvidenceRefsPanel',
  props: {
    contextStats: { type: Object, default: null },
    warnings: { type: Array, default: () => [] },
    evidenceRefs: { type: Object, default: null },
  },
  template: '<div class="evidence-panel-stub"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElButton: ElButtonStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElTag: ElTagStub,
  ElAlert: ElAlertStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElInput: ElInputStub,
  ElSwitch: ElSwitchStub,
  ElRadioGroup: ElRadioGroupStub,
  ElRadioButton: ElRadioButtonStub,
  ElStatistic: ElStatisticStub,
  ElIcon: ElIconStub,
  ElTooltip: ElTooltipStub,
  ContextHealthPanel: ContextHealthPanelStub,
  EvidenceRefsPanel: EvidenceRefsPanelStub,
}

type FormData = {
  project_id: number
  test_point_ids: number[]
  requirement_file_ids: number[]
  ui_screen_ids: number[]
  ui_file_ids: number[]
  case_type: string
  exec_mode: string
  extra_requirements: string
  priority: number
  enhanced_mode: boolean
}

type StoreOverrides = {
  currentStep?: number
  caseType?: string
  projectType?: string
  testPointIds?: number[]
  requirementFileIds?: number[]
  uiScreenIds?: number[]
  uiFileIds?: number[]
  uiPrototypeProjects?: unknown[]
  quality?: {
    title: string
    description: string
    missing: string[]
    mode: string
    sourceTags: string[]
    warnings: string[]
  }
  contextStats?: Record<string, unknown> | null
  evidenceRefs?: Record<string, unknown> | null
  selectedPoints?: Array<{ id: number; module: string; point: string; priority: number }>
  generating?: boolean
  canGenerate?: boolean
  buttonLabel?: string
}

function createStore(overrides: StoreOverrides = {}) {
  const formData = reactive<FormData>({
    project_id: 1,
    test_point_ids: overrides.testPointIds ?? [],
    requirement_file_ids: overrides.requirementFileIds ?? [],
    ui_screen_ids: overrides.uiScreenIds ?? [],
    ui_file_ids: overrides.uiFileIds ?? [],
    case_type: overrides.caseType ?? '',
    exec_mode: 'all',
    extra_requirements: '',
    priority: 2,
    enhanced_mode: false,
  })

  return {
    currentStep: overrides.currentStep ?? 1,
    formData,
    projects: [{ id: 1, name: '项目A', project_type: overrides.projectType ?? 'web' }],
    uiPrototypeProjects: overrides.uiPrototypeProjects ?? [],
    contextQuality:
      overrides.quality ??
      ({
        title: '完整上下文',
        description: '已包含需求与原型',
        missing: [],
        mode: 'new_full_generation',
        sourceTags: ['需求文档', 'UI原型'],
        warnings: [],
      } as never),
    contextStats: overrides.contextStats ?? null,
    serverWarnings: [],
    evidenceRefs: overrides.evidenceRefs ?? null,
    selectedTestPointsForDisplay: overrides.selectedPoints ?? [],
    generating: overrides.generating ?? false,
    canGenerate: overrides.canGenerate ?? true,
    generateButtonLabel: overrides.buttonLabel ?? '3 条测试点',
    getPriorityType: (priority: number) => ({ 1: 'danger', 2: 'warning', 3: 'info' })[priority],
    getPriorityLabel: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority],
    resetForm: vi.fn(),
    handleCaseTypeChange: vi.fn(),
  }
}

function setup(overrides: StoreOverrides = {}) {
  const fake = createStore(overrides)
  store.current = fake

  const wrapper = mount(GenerateCaseConfigForm, { global: { stubs } })
  return { fake, wrapper }
}

function formItemByLabel(wrapper: ReturnType<typeof setup>['wrapper'], label: string) {
  return wrapper.findAll('.el-form-item').find((i) => i.attributes('data-label') === label)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
})

describe('GenerateCaseConfigForm — 步骤与头部', () => {
  it('非配置步骤不渲染', () => {
    const { wrapper } = setup({ currentStep: 2 })

    expect(wrapper.find('.step-card').exists()).toBe(false)
  })

  it('展示标题并支持返回上一步', async () => {
    const { wrapper } = setup()

    expect(wrapper.find('.el-card__header').text()).toContain('配置测试参数')
    await wrapper.find('.el-card__header .el-button').trigger('click')

    expect(wrapper.emitted('prev')).toHaveLength(1)
  })
})

describe('GenerateCaseConfigForm — 上下文质量', () => {
  it('上下文完整时展示成功标签', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.quality-title').text()).toBe('完整上下文')
    expect(wrapper.find('.quality-desc').text()).toBe('已包含需求与原型')
    const tag = wrapper.find('.quality-main .el-tag')
    expect(tag.text()).toBe('完整上下文')
    expect(tag.attributes('data-type')).toBe('success')
  })

  it('缺失上下文时展示告警标签与补齐建议', () => {
    const { wrapper } = setup({
      quality: {
        title: '轻量上下文',
        description: '仅命中部分文档',
        missing: ['需求文档', 'UI原型'],
        mode: 'lite',
        sourceTags: [],
        warnings: ['历史用例可能过期'],
      },
    })

    const tag = wrapper.find('.quality-main .el-tag')
    expect(tag.text()).toBe('轻量/待补齐')
    expect(tag.attributes('data-type')).toBe('warning')

    const alerts = wrapper.findAll('.quality-card .el-alert')
    expect(alerts).toHaveLength(2)
    expect(alerts[0].find('.alert-title').text()).toBe('建议补齐：需求文档、UI原型')
    expect(alerts[0].attributes('data-type')).toBe('warning')
    expect(alerts[1].find('.alert-title').text()).toBe('历史用例可能过期')
    expect(alerts[1].attributes('data-type')).toBe('info')
    expect(wrapper.find('.quality-tags').exists()).toBe(false)
  })

  it('来源标签按数组渲染', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.quality-tags .el-tag').map((t) => t.text())).toEqual([
      '需求文档',
      'UI原型',
    ])
  })

  it('按上下文统计与证据渲染子面板', () => {
    const refs = { requirement: [] }
    const withPanels = setup({
      contextStats: { completeness_score: 80 },
      evidenceRefs: refs,
    }).wrapper
    expect(withPanels.find('.health-panel-stub').exists()).toBe(true)
    expect(withPanels.find('.evidence-panel-stub').exists()).toBe(true)

    const withoutPanels = setup().wrapper
    expect(withoutPanels.find('.health-panel-stub').exists()).toBe(false)
    expect(withoutPanels.find('.evidence-panel-stub').exists()).toBe(false)
  })
})

describe('GenerateCaseConfigForm — 范围统计与测试点', () => {
  it('统计已选测试点、需求文档与 UI 原型数量', () => {
    const { wrapper } = setup({
      testPointIds: [1, 2],
      requirementFileIds: [3, 4, 5],
      uiScreenIds: [],
      uiFileIds: [6, 7, 8, 9],
    })

    const stats = wrapper.findAll('.el-statistic')
    expect(stats.map((s) => s.attributes('data-title'))).toEqual([
      '已选测试点',
      '需求文档',
      'UI原型',
    ])
    expect(stats.map((s) => s.attributes('data-value'))).toEqual(['2', '3', '4'])
  })

  it('UI 原型优先取屏幕数量', () => {
    const { wrapper } = setup({ uiScreenIds: [1, 2, 3], uiFileIds: [4] })

    const stats = wrapper.findAll('.el-statistic')
    expect(stats[2].attributes('data-value')).toBe('3')
  })

  it('展示测试点列表与优先级标签，超出 5 条给出提示', () => {
    const selectedPoints = Array.from({ length: 6 }, (_, i) => ({
      id: i + 1,
      module: `模块${i + 1}`,
      point: `测试点${i + 1}`,
      priority: 1,
    }))
    const { wrapper } = setup({
      selectedPoints,
      testPointIds: selectedPoints.map((p) => p.id),
    })

    const items = wrapper.findAll('.st-item')
    expect(items).toHaveLength(6)
    expect(items[0].find('.st-mod').text()).toBe('模块1')
    expect(items[0].find('.st-point').text()).toBe('测试点1')
    expect(items[0].find('.el-tag').text()).toBe('高')
    expect(wrapper.find('.st-more').text()).toBe('还有 1 个测试点未展示...')
  })

  it('未选测试点时展示自动分析提示', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.scope-testpoints').exists()).toBe(false)
    expect(wrapper.find('.scope-preview > .el-alert').text()).toContain(
      'AI 将基于所选需求文档和测试点自动分析并生成测试用例'
    )
  })
})

describe('GenerateCaseConfigForm — 用例类型', () => {
  it('用例类型下拉提供五种类型并转发选择', async () => {
    const { fake, wrapper } = setup()

    const item = formItemByLabel(wrapper, '用例类型')!
    expect(item.findAll('.el-option').map((o) => o.text())).toEqual([
      'UI自动化',
      '手工测试',
      'API自动化',
      '性能测试',
      '安全测试',
    ])

    item.findComponent(ElSelectStub).vm.$emit('change', 'api_automation')
    await flushPromises()

    expect(fake.handleCaseTypeChange).toHaveBeenCalledWith('api_automation')
  })

  it('UI 自动化展示执行方式三选', () => {
    const { wrapper } = setup({ caseType: 'ui_automation' })

    const group = wrapper.find('.exec-mode-group')
    expect(group.exists()).toBe(true)
    expect(group.findAll('.el-radio-button').map((r) => r.attributes('data-value'))).toEqual([
      'all',
      'ui_auto',
      'manual',
    ])
    expect(wrapper.find('.el-tooltip').exists()).toBe(true)
  })

  it.each([
    ['api_automation', 'success', 'API自动化模式'],
    ['performance', 'warning', '性能测试模式'],
    ['security', 'error', '安全测试模式'],
  ])('类型 %s 展示 %s 模式说明', (caseType, type, title) => {
    const { wrapper } = setup({ caseType })

    const alert = formItemByLabel(wrapper, '用例类型')!.find('.el-alert')
    expect(alert.attributes('data-type')).toBe(type)
    expect(alert.find('.alert-title').text()).toBe(title)
  })

  it('手工测试不展示额外配置', () => {
    const { wrapper } = setup({ caseType: 'manual' })

    const item = formItemByLabel(wrapper, '用例类型')!
    expect(item.find('.exec-mode-group').exists()).toBe(false)
    expect(item.find('.el-alert').exists()).toBe(false)
  })
})

describe('GenerateCaseConfigForm — 其它字段与提交', () => {
  it('补充要求、优先级与增强模式配置项', () => {
    const { wrapper } = setup()

    expect(formItemByLabel(wrapper, '补充要求')!.find('.el-input').attributes('placeholder')).toBe(
      '可选：补充特殊要求'
    )
    expect(formItemByLabel(wrapper, '补充要求')!.find('.form-tip').text()).toBe(
      '不填则由 AI 根据测试点智能判断，通常无需填写'
    )
    expect(
      formItemByLabel(wrapper, '优先级')!
        .findAll('.el-option')
        .map((o) => o.text())
    ).toEqual(['P0-高（核心流程）', 'P2-中（主要功能）', 'P3-低（边缘场景）'])
    const switchEl = formItemByLabel(wrapper, '增强模式')!.find('.el-switch')
    expect(switchEl.attributes('data-active')).toBe('启用')
    expect(switchEl.attributes('data-inactive')).toBe('禁用')
  })

  it('生成按钮展示标签、loading 与禁用态并转发事件', async () => {
    const { wrapper } = setup({ generating: true, canGenerate: false, buttonLabel: '7 条测试点' })

    const buttons = wrapper.findAll('.el-button')
    const generateBtn = buttons[buttons.length - 2]
    expect(generateBtn.text()).toContain('开始生成 (7 条测试点)')
    expect(generateBtn.attributes('data-loading')).toBe('true')
    expect(generateBtn.attributes('disabled')).toBeDefined()

    const resetBtn = buttons[buttons.length - 1]
    expect(resetBtn.text()).toBe('重置')
    await resetBtn.trigger('click')
    expect(store.current!.resetForm as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1)
  })

  it('生成按钮可点击时抛出 generate', async () => {
    const { wrapper } = setup()

    const buttons = wrapper.findAll('.el-button')
    await buttons[buttons.length - 2].trigger('click')

    expect(wrapper.emitted('generate')).toHaveLength(1)
  })
})

describe('GenerateCaseConfigForm — 缺少 UI 原型降级', () => {
  async function selectUiAutomation(wrapper: ReturnType<typeof setup>['wrapper']) {
    formItemByLabel(wrapper, '用例类型')!
      .findComponent(ElSelectStub)
      .vm.$emit('change', 'ui_automation')
    await flushPromises()
  }

  it('web 项目缺原型时确认后降级为手工用例', async () => {
    const { fake, wrapper } = setup({ projectType: 'web', uiPrototypeProjects: [] })

    await selectUiAutomation(wrapper)

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '当前项目未上传UI原型图，将降级为手工用例模式生成，UI步骤标记为【待确认UI】。',
      '缺少UI原型图',
      expect.objectContaining({ type: 'warning' })
    )
    expect(fake.formData.case_type).toBe('manual')
    expect(fake.formData.exec_mode).toBe('all')
  })

  it('取消确认同样降级为手工用例', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue(new Error('cancel'))
    const { fake, wrapper } = setup({ projectType: 'app', uiPrototypeProjects: [] })

    await selectUiAutomation(wrapper)

    expect(fake.formData.case_type).toBe('manual')
    expect(fake.formData.exec_mode).toBe('all')
  })

  it('已有原型或非 UI 项目类型时不弹确认', async () => {
    const withPrototype = setup({ projectType: 'web', uiPrototypeProjects: [{ id: 1 }] }).wrapper
    await selectUiAutomation(withPrototype)
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()

    const apiProject = setup({ projectType: 'api', uiPrototypeProjects: [] }).wrapper
    await selectUiAutomation(apiProject)
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  })

  it('选择其它用例类型不触发确认', async () => {
    const { fake, wrapper } = setup({ projectType: 'web', uiPrototypeProjects: [] })

    formItemByLabel(wrapper, '用例类型')!.findComponent(ElSelectStub).vm.$emit('change', 'manual')
    await flushPromises()

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(fake.handleCaseTypeChange).toHaveBeenCalledWith('manual')
  })
})
