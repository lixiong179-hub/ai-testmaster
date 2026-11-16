import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, nextTick, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useUIPrototype', () => ({
  useUIPrototype: () => state.current,
}))

import UIPrototypePage from '../ui-prototype.vue'

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: '<div class="el-card"><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    circle: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :data-loading="loading" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, effect: { type: String, default: 'light' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: 'info' } },
  template: '<div class="el-alert" :data-type="type">{{ title }}</div>',
})

const ElRadioGroupStub = defineComponent({
  name: 'ElRadioGroup',
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: '<div class="el-radio-group" :data-model="modelValue"><slot /></div>',
})

const ElRadioButtonStub = defineComponent({
  name: 'ElRadioButton',
  props: { value: { type: String, default: '' } },
  template: '<label class="el-radio-button" :data-value="value"><slot /></label>',
})

const ElStepsStub = defineComponent({
  name: 'ElSteps',
  props: { active: { type: Number, default: 0 } },
  template: '<div class="el-steps" :data-active="active"><slot /></div>',
})

const ElStepStub = defineComponent({
  name: 'ElStep',
  props: {
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    status: { type: String, default: '' },
  },
  template:
    '<div class="el-step" :data-status="status"><span class="step-title">{{ title }}</span><span class="step-desc">{{ description }}</span></div>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ScreenCardGridStub = defineComponent({
  name: 'ScreenCardGrid',
  props: {
    screens: { type: Array, default: () => [] },
    imageUrls: { type: Object, default: () => ({}) },
    loading: { type: Boolean, default: false },
  },
  emits: ['preview', 'parse', 'delete', 'add-screens'],
  template: '<div class="screen-card-grid-stub" :data-count="screens.length"></div>',
})

const ScreenPreviewDialogStub = defineComponent({
  name: 'ScreenPreviewDialog',
  props: {
    visible: { type: Boolean, default: false },
    screen: { type: Object, default: null },
    imageUrls: { type: Object, default: () => ({}) },
  },
  emits: ['update:visible'],
  template: '<div class="screen-preview-dialog-stub" :data-visible="visible"></div>',
})

const ScreenUploadDialogStub = defineComponent({
  name: 'ScreenUploadDialog',
  props: {
    visible: { type: Boolean, default: false },
    uploading: { type: Boolean, default: false },
  },
  emits: ['update:visible', 'submit'],
  template: '<div class="screen-upload-dialog-stub" :data-visible="visible"></div>',
})

const AIParseLoadingStub = defineComponent({
  name: 'AIParseLoading',
  props: {
    visible: { type: Boolean, default: false },
    parseMode: { type: String, default: 'text' },
    totalCount: { type: Number, default: 0 },
    processedCount: { type: Number, default: 0 },
    showCancelButton: { type: Boolean, default: false },
  },
  emits: ['cancel'],
  template: '<div class="ai-parse-loading-stub" :data-mode="parseMode"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  ElTag: ElTagStub,
  ElAlert: ElAlertStub,
  ElRadioGroup: ElRadioGroupStub,
  ElRadioButton: ElRadioButtonStub,
  ElSteps: ElStepsStub,
  ElStep: ElStepStub,
  ElEmpty: ElEmptyStub,
  ScreenCardGrid: ScreenCardGridStub,
  ScreenPreviewDialog: ScreenPreviewDialogStub,
  ScreenUploadDialog: ScreenUploadDialogStub,
  AIParseLoading: AIParseLoadingStub,
}

type ScreenData = { id: number; screen_name?: string; parse_status?: string }

type PageState = {
  prototypeName?: string
  iterationName?: string
  currentIteration?: { name: string; version?: string } | null
  loading?: boolean
  parsing?: boolean
  uploading?: boolean
  flowGenerating?: boolean
  screens?: ScreenData[]
  previewVisible?: boolean
  previewScreen?: ScreenData | null
  uploadDialogVisible?: boolean
  parseMode?: 'text' | 'vision'
  completedScreenCount?: number
  failedScreenCount?: number
  pendingScreenCount?: number
  pendingScreensCount?: number
  processedScreensCount?: number
  hasFlow?: boolean
  flowSummary?: Record<string, unknown> | null
}

const workflowStepsFixture = [
  { title: '上传截图', status: 'success', description: '已上传 2 张' },
  { title: '解析页面', status: 'process', description: '已解析 1/2' },
  { title: '分析页面流转', status: 'wait', description: '至少需要 2 张已解析页面' },
  { title: '生成用例/回归分析', status: 'wait', description: '流转完成后推荐执行' },
]

function setup(overrides: PageState = {}) {
  const parseMode = ref<'text' | 'vision'>(overrides.parseMode ?? 'text')
  const screens = ref<ScreenData[]>(overrides.screens ?? [])
  const handlers = {
    goBack: vi.fn(),
    goToScenario4: vi.fn(),
    goToCaseGenerate: vi.fn(),
    goToFlowEditor: vi.fn(),
    handlePrimaryAction: vi.fn(),
    handlePreviewScreen: vi.fn(),
    handleParseScreen: vi.fn(),
    handleBatchParse: vi.fn(),
    handleGenerateFlow: vi.fn(),
    handleCancelParse: vi.fn(),
    handleDeleteScreen: vi.fn(),
    handleAddScreens: vi.fn(),
    handleUploadSubmit: vi.fn(),
  }

  state.current = {
    prototypeName: computed(() => overrides.prototypeName ?? '洪恩UI原型'),
    iterationName: computed(() => overrides.iterationName ?? ''),
    currentIteration: ref(overrides.currentIteration ?? null),
    loading: ref(overrides.loading ?? false),
    parsing: ref(overrides.parsing ?? false),
    uploading: ref(overrides.uploading ?? false),
    flowGenerating: ref(overrides.flowGenerating ?? false),
    screens,
    screenImageUrls: ref<Record<number, string>>({}),
    previewVisible: ref(overrides.previewVisible ?? false),
    previewScreen: ref(overrides.previewScreen ?? null),
    uploadDialogVisible: ref(overrides.uploadDialogVisible ?? false),
    parseMode,
    completedScreenCount: computed(() => overrides.completedScreenCount ?? 0),
    failedScreenCount: computed(() => overrides.failedScreenCount ?? 0),
    pendingScreenCount: computed(() => overrides.pendingScreenCount ?? 0),
    pendingScreensCount: computed(() => overrides.pendingScreensCount ?? 0),
    processedScreensCount: computed(() => overrides.processedScreensCount ?? 0),
    hasFlow: computed(() => overrides.hasFlow ?? false),
    flowSummary: computed(() => overrides.flowSummary ?? null),
    workflowSteps: ref(workflowStepsFixture),
    primaryActionText: computed(() => '上传截图'),
    ...handlers,
  }

  const wrapper = mount(UIPrototypePage, { global: { stubs } })
  return { wrapper, parseMode, screens, handlers }
}

describe('ui-prototype — 页头', () => {
  it('展示原型名、类型与截图数量', () => {
    const { wrapper } = setup({ screens: [{ id: 1 }, { id: 2 }] })

    expect(wrapper.find('.prototype-title').text()).toBe('洪恩UI原型')
    const tags = wrapper.findAll('.header-tags .el-tag').map((t) => t.text())
    expect(tags).toEqual(['UI原型图', '2张'])
  })

  it('优先展示当前迭代名称与版本', () => {
    const { wrapper } = setup({
      currentIteration: { name: '迭代一期', version: 'v1.0' },
      iterationName: '路由迭代名',
    })

    expect(wrapper.findAll('.header-tags .el-tag')[0].text()).toBe('迭代一期 (v1.0)')
  })

  it('无当前迭代时回退路由迭代名，均缺失则不展示', () => {
    const withName = setup({ iterationName: '路由迭代名' }).wrapper
    expect(withName.findAll('.header-tags .el-tag')[0].text()).toBe('路由迭代名')

    const withoutName = setup().wrapper
    expect(withoutName.findAll('.header-tags .el-tag').map((t) => t.text())).toEqual([
      'UI原型图',
      '0张',
    ])
  })

  it('视觉模式的费用提示仅在 vision 下展示', async () => {
    const { wrapper, parseMode } = setup()
    expect(wrapper.find('.el-alert').exists()).toBe(false)

    parseMode.value = 'vision'
    await nextTick()

    expect(wrapper.find('.el-alert').text()).toContain('视觉模型解析将消耗更多API调用费用')
  })

  it('主操作按钮展示文案与 loading，并转发点击', async () => {
    const { wrapper, handlers } = setup()

    const primaryBtn = wrapper.findAll('.header-right .el-button')[1]
    expect(primaryBtn.text()).toBe('上传截图')
    expect(primaryBtn.attributes('data-loading')).toBe('false')

    await primaryBtn.trigger('click')
    expect(handlers.handlePrimaryAction).toHaveBeenCalledTimes(1)
  })

  it('回退与追加上传按钮生效', async () => {
    const { wrapper, handlers } = setup()

    const backBtn = wrapper.findAll('.header-left .el-button')[0]
    await backBtn.trigger('click')
    expect(handlers.goBack).toHaveBeenCalledTimes(1)

    await wrapper.findAll('.header-right .el-button')[0].trigger('click')
    expect(handlers.handleAddScreens).toHaveBeenCalledTimes(1)
  })
})

describe('ui-prototype — 工作流', () => {
  it('按 workflowSteps 渲染步骤与描述', () => {
    const { wrapper } = setup({ screens: [{ id: 1 }] })

    expect(wrapper.findAll('.el-step').map((s) => s.find('.step-title').text())).toEqual([
      '上传截图',
      '解析页面',
      '分析页面流转',
      '生成用例/回归分析',
    ])
    expect(wrapper.findAll('.el-step').map((s) => s.attributes('data-status'))).toEqual([
      'success',
      'process',
      'wait',
      'wait',
    ])
  })

  it.each([
    [{ screens: [], completedScreenCount: 0, hasFlow: false }, '0'],
    [{ screens: [{ id: 1 }], completedScreenCount: 0, hasFlow: false }, '1'],
    [{ screens: [{ id: 1 }], completedScreenCount: 1, hasFlow: false }, '2'],
    [{ screens: [{ id: 1 }], completedScreenCount: 2, hasFlow: false }, '3'],
    [{ screens: [{ id: 1 }], completedScreenCount: 2, hasFlow: true }, '4'],
  ])('工作流当前步骤按进度推进 %o → %s', (overrides, expected) => {
    const { wrapper } = setup(overrides as PageState)

    expect(wrapper.find('.el-steps').attributes('data-active')).toBe(expected)
  })

  it('解析模式切换按钮与解析按钮文案联动', async () => {
    const { wrapper, parseMode, handlers } = setup({ screens: [{ id: 1 }] })

    expect(wrapper.findComponent(ElRadioGroupStub).props('modelValue')).toBe('text')
    const parseBtn = wrapper.findAll('.workflow-actions .el-button')[1]
    expect(parseBtn.text()).toBe('解析页面')

    parseMode.value = 'vision'
    await nextTick()

    expect(wrapper.findAll('.workflow-actions .el-button')[1].text()).toBe('AI视觉解析')

    await wrapper.findAll('.workflow-actions .el-button')[1].trigger('click')
    expect(handlers.handleBatchParse).toHaveBeenCalledTimes(1)
  })

  it('无截图时禁用解析，解析中同样禁用', () => {
    const empty = setup().wrapper
    expect(empty.findAll('.workflow-actions .el-button')[1].attributes('disabled')).toBeDefined()

    const parsing = setup({ screens: [{ id: 1 }], parsing: true }).wrapper
    expect(parsing.findAll('.workflow-actions .el-button')[1].attributes('disabled')).toBeDefined()
  })

  it('1 张已解析时禁用流转分析，用例与回归入口可用', async () => {
    const { wrapper, handlers } = setup({ screens: [{ id: 1 }], completedScreenCount: 1 })

    const buttons = wrapper.findAll('.workflow-actions .el-button')
    expect(buttons[0].text()).toContain('追加上传')
    expect(buttons[2].attributes('disabled')).toBeDefined()
    expect(buttons[3].attributes('disabled')).toBeUndefined()
    expect(buttons[4].attributes('disabled')).toBeUndefined()

    await buttons[2].trigger('click')
    expect(handlers.handleGenerateFlow).not.toHaveBeenCalled()

    await buttons[3].trigger('click')
    expect(handlers.goToCaseGenerate).toHaveBeenCalledTimes(1)
    await buttons[4].trigger('click')
    expect(handlers.goToScenario4).toHaveBeenCalledTimes(1)
  })

  it('2 张已解析时流转分析入口可点击并转发', async () => {
    const { wrapper, handlers } = setup({
      screens: [{ id: 1 }, { id: 2 }],
      completedScreenCount: 2,
    })

    const buttons = wrapper.findAll('.workflow-actions .el-button')
    expect(buttons[2].attributes('disabled')).toBeUndefined()

    await buttons[0].trigger('click')
    await buttons[2].trigger('click')

    expect(handlers.handleAddScreens).toHaveBeenCalledTimes(1)
    expect(handlers.handleGenerateFlow).toHaveBeenCalledTimes(1)
  })

  it('零已解析页面时禁用用例与回归入口', () => {
    const { wrapper } = setup({ screens: [{ id: 1 }], completedScreenCount: 0 })

    const buttons = wrapper.findAll('.workflow-actions .el-button')
    expect(buttons[3].attributes('disabled')).toBeDefined()
    expect(buttons[4].attributes('disabled')).toBeDefined()
  })
})

describe('ui-prototype — 概览与流转', () => {
  it('概览卡展示总数、已解析、待处理与失败数', () => {
    const { wrapper } = setup({
      screens: [{ id: 1 }, { id: 2 }, { id: 3 }],
      completedScreenCount: 1,
      pendingScreenCount: 1,
      failedScreenCount: 1,
    })

    expect(wrapper.findAll('.overview-label').map((n) => n.text())).toEqual([
      '屏幕总数',
      '已解析',
      '待处理',
      '解析失败',
    ])
    expect(wrapper.findAll('.overview-value').map((n) => n.text())).toEqual(['3', '1', '1', '1'])
  })

  it('有流转时展示六项概览指标', () => {
    const { wrapper } = setup({
      hasFlow: true,
      flowSummary: {
        node_count: 6,
        edge_count: 5,
        entry_screen: '首页',
        end_screens: ['完成页', '错误页'],
        branch_count: 2,
        exception_count: 1,
      },
    })

    expect(wrapper.find('.flow-summary-grid').exists()).toBe(true)
    expect(wrapper.findAll('.flow-summary-item span').map((n) => n.text())).toEqual([
      '页面数',
      '连线数',
      '入口页',
      '终止页',
      '分支',
      '异常/提示',
    ])
    expect(wrapper.findAll('.flow-summary-item strong').map((n) => n.text())).toEqual([
      '6',
      '5',
      '首页',
      '2',
      '2',
      '1',
    ])
    expect(wrapper.find('.el-empty').exists()).toBe(false)
  })

  it('无流转时展示空态与禁用的流程编排入口', () => {
    const { wrapper } = setup({ hasFlow: false })

    expect(wrapper.find('.flow-summary-grid').exists()).toBe(false)
    expect(wrapper.find('.el-empty').text()).toBe(
      '解析至少 2 张页面后，可分析页面流转并在这里查看概览'
    )
    expect(wrapper.find('.flow-overview-card .el-button').attributes('disabled')).toBeDefined()
  })

  it('有流转时流程编排入口可点击并转发', async () => {
    const { wrapper, handlers } = setup({
      hasFlow: true,
      flowSummary: { node_count: 2, edge_count: 1 },
    })

    const btn = wrapper.find('.flow-overview-card .el-button')
    expect(btn.attributes('disabled')).toBeUndefined()

    await btn.trigger('click')
    expect(handlers.goToFlowEditor).toHaveBeenCalledTimes(1)
  })

  it('屏幕列表统计标签与子组件事件转发', async () => {
    const screens = [{ id: 1, screen_name: '首页' }]
    const { wrapper, handlers } = setup({
      screens,
      completedScreenCount: 1,
      pendingScreenCount: 0,
      failedScreenCount: 0,
    })

    expect(wrapper.findAll('.content-tags .el-tag').map((t) => t.text())).toEqual([
      '已解析 1',
      '待处理 0',
      '失败 0',
    ])

    const grid = wrapper.findComponent(ScreenCardGridStub)
    expect(grid.attributes('data-count')).toBe('1')

    grid.vm.$emit('preview', screens[0])
    grid.vm.$emit('parse', screens[0])
    grid.vm.$emit('delete', screens[0])
    grid.vm.$emit('add-screens')

    expect(handlers.handlePreviewScreen).toHaveBeenCalledWith(screens[0])
    expect(handlers.handleParseScreen).toHaveBeenCalledWith(screens[0])
    expect(handlers.handleDeleteScreen).toHaveBeenCalledWith(screens[0])
    expect(handlers.handleAddScreens).toHaveBeenCalledTimes(1)
  })
})

describe('ui-prototype — 弹层', () => {
  it('预览与上传弹层可见性透传', () => {
    const { wrapper } = setup({ previewVisible: true, uploadDialogVisible: true })

    expect(wrapper.findComponent(ScreenPreviewDialogStub).props('visible')).toBe(true)
    expect(wrapper.findComponent(ScreenUploadDialogStub).props('visible')).toBe(true)
  })

  it('上传提交与解析取消事件转发', () => {
    const { wrapper, handlers } = setup()

    wrapper.findComponent(ScreenUploadDialogStub).vm.$emit('submit', [{ name: 'a.png' }])
    wrapper.findComponent(AIParseLoadingStub).vm.$emit('cancel')

    expect(handlers.handleUploadSubmit).toHaveBeenCalledWith([{ name: 'a.png' }])
    expect(handlers.handleCancelParse).toHaveBeenCalledTimes(1)
  })

  it('解析进度组件透传数量与模式', () => {
    const { wrapper } = setup({
      parsing: true,
      parseMode: 'vision',
      pendingScreensCount: 4,
      processedScreensCount: 2,
    })

    const loading = wrapper.findComponent(AIParseLoadingStub)
    expect(loading.props('visible')).toBe(true)
    expect(loading.props('parseMode')).toBe('vision')
    expect(loading.props('totalCount')).toBe(4)
    expect(loading.props('processedCount')).toBe(2)
    expect(loading.props('showCancelButton')).toBe(true)
  })
})
