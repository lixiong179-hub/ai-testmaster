import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/useTestPointExtract', () => ({
  useTestPointExtract: () => state.current,
}))

import RightPreviewPanel from '../RightPreviewPanel.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  props: { size: { type: Number, default: 0 }, color: { type: String, default: '' } },
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" @click="$emit(\'click\', $event)"><slot /></button>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, size: { type: String, default: 'default' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' }, imageSize: { type: Number, default: 100 } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElSkeletonStub = defineComponent({
  name: 'ElSkeleton',
  props: { rows: { type: Number, default: 0 }, animated: { type: Boolean, default: false } },
  template: '<div class="el-skeleton" :data-rows="rows"></div>',
})

const stubs = {
  ElIcon: ElIconStub,
  ElButton: ElButtonStub,
  ElTag: ElTagStub,
  ElEmpty: ElEmptyStub,
  ElSkeleton: ElSkeletonStub,
}

type Resource = {
  id: number
  resource_type: string
  display_name: string
  size_text: string
  time_text: string
}

type TestPoint = { id: number; priority: number; module: string }

type PanelOverrides = {
  step?: number
  project?: Record<string, unknown> | null
  files?: Array<Record<string, unknown>>
  resource?: Resource | null
  extracting?: boolean
  points?: TestPoint[]
  savedFromDb?: boolean
  dbTotal?: number
  selectedRows?: unknown[]
}

function setup(overrides: PanelOverrides = {}) {
  const files = overrides.files ?? [
    { id: 1, resource_type: 'requirement' },
    { id: 2, resource_type: 'requirement' },
    { id: 3, resource_type: 'ui_mockup' },
    { id: 4, resource_type: 'api_doc' },
  ]
  const points = overrides.points ?? [
    { id: 1, priority: 1, module: '登录' },
    { id: 2, priority: 1, module: '登录' },
    { id: 3, priority: 2, module: '支付' },
    { id: 4, priority: 3, module: '搜索' },
  ]

  const getResourceTypeCount = (type: string) =>
    files.filter((f) => f.resource_type === type).length
  const getResourceTypePercentage = (type: string) => {
    const count = getResourceTypeCount(type)
    return files.length === 0 ? 0 : Math.round((count / files.length) * 100)
  }

  state.current = {
    currentStep: ref(overrides.step ?? 0),
    selectedProjectInfo: ref(overrides.project === undefined ? null : overrides.project),
    files: ref(files),
    selectedResource: ref(overrides.resource === undefined ? null : overrides.resource),
    extracting: ref(overrides.extracting ?? false),
    testPoints: computed(() => points),
    savedFromDb: ref(overrides.savedFromDb ?? false),
    dbTotal: ref(overrides.dbTotal ?? 0),
    selectedRows: ref(overrides.selectedRows ?? []),
    getResourceIcon: () => 'span',
    getResourceTypeTagType: () => 'success',
    getResourceTypeLabel: (type: string) =>
      ({ requirement: '需求文档', ui_mockup: 'UI原型图', api_doc: 'API文档' })[type] ?? type,
    getResourceTypeCount,
    getResourceTypePercentage,
    getPriorityCount: (priority: number) => points.filter((p) => p.priority === priority).length,
    getModuleDistribution: () => ({ 登录: 2, 支付: 1, 搜索: 1 }),
    goToNextStep: vi.fn(),
  }

  const wrapper = mount(RightPreviewPanel, { global: { stubs } })
  return { wrapper, store: state.current! }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RightPreviewPanel — 步骤1 欢迎态', () => {
  it('未选项目时展示功能引导', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.welcome-title').text()).toBe('高级测试点提取向导')
    expect(wrapper.find('.welcome-desc').text()).toContain('适用于复杂资源筛选')
    expect(wrapper.findAll('.feature-name').map((n) => n.text())).toEqual([
      '智能解析',
      'AI 提取',
      '数据分析',
    ])
    expect(wrapper.findAll('.feature-desc').map((n) => n.text())).toEqual([
      '自动识别需求文档结构',
      '智能生成测试点',
      '多维度统计分析',
    ])
    expect(wrapper.find('.tip-card').text()).toBe('请先从左侧选择一个项目开始')
    expect(wrapper.find('.project-summary-card').exists()).toBe(false)
  })
})

describe('RightPreviewPanel — 步骤1 项目摘要', () => {
  it('展示项目名称、ID 与资源统计', () => {
    const { wrapper } = setup({ project: { id: 7, name: '项目A' } })

    expect(wrapper.find('.summary-title').text()).toBe('项目A')
    expect(wrapper.find('.summary-id').text()).toBe('ID: 7')
    expect(wrapper.findAll('.stat-number').map((n) => n.text())).toEqual(['4', '2'])
    expect(wrapper.findAll('.stat-text').map((n) => n.text())).toEqual(['资源文件', '需求文档'])
  })

  it('资源类型分布按占比渲染条宽与数量', () => {
    const { wrapper } = setup({ project: { id: 7, name: '项目A' } })

    const bars = wrapper.findAll('.type-bar')
    expect(bars.map((b) => b.attributes('style'))).toEqual([
      'width: 50%;',
      'width: 25%;',
      'width: 25%;',
    ])
    expect(wrapper.findAll('.type-count').map((n) => n.text())).toEqual(['2', '1', '1'])
    expect(wrapper.findAll('.type-label').map((n) => n.text())).toEqual([
      '需求文档',
      'UI原型',
      'API文档',
    ])
  })

  it('下一步按钮推进步骤', async () => {
    const { wrapper, store } = setup({ project: { id: 7, name: '项目A' } })

    await wrapper.find('.next-btn-large').trigger('click')

    expect(store.goToNextStep as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1)
  })
})

describe('RightPreviewPanel — 步骤2 资源详情', () => {
  it('选中资源时展示详情与下一步', async () => {
    const { wrapper, store } = setup({
      step: 1,
      resource: {
        id: 1,
        resource_type: 'requirement',
        display_name: '需求文档v1.docx',
        size_text: '12KB',
        time_text: '2026-11-01',
      },
    })

    expect(wrapper.find('.preview-header').text()).toBe('资源详情')
    expect(wrapper.find('.detail-name').text()).toBe('需求文档v1.docx')
    expect(wrapper.find('.el-tag').text()).toBe('需求文档')
    expect(wrapper.findAll('.stat-value').map((n) => n.text())).toEqual(['12KB', '2026-11-01'])

    await wrapper.find('.next-step-hint .el-button').trigger('click')
    expect(store.goToNextStep as ReturnType<typeof vi.fn>).toHaveBeenCalledTimes(1)
  })

  it('未选资源时展示空态', () => {
    const { wrapper } = setup({ step: 1 })

    expect(wrapper.find('.preview-empty').exists()).toBe(true)
    expect(wrapper.find('.el-empty').text()).toBe('请从左侧选择一个需求资源')
  })
})

describe('RightPreviewPanel — 步骤3 提取结果', () => {
  it('提取中展示骨架与标题', () => {
    const { wrapper } = setup({ step: 2, extracting: true })

    expect(wrapper.find('.preview-header').text()).toBe('提取中...')
    expect(wrapper.find('.el-skeleton').attributes('data-rows')).toBe('4')
  })

  it('有测试点时展示总数、优先级与模块分布', () => {
    const { wrapper } = setup({ step: 2 })

    expect(wrapper.find('.preview-header').text()).toBe('提取结果')
    expect(wrapper.find('.stat-card.total .stat-number').text()).toBe('4')
    expect(wrapper.findAll('.dist-count').map((n) => n.text())).toEqual(['2', '1', '1'])
    expect(wrapper.findAll('.dist-label').map((n) => n.text())).toEqual([
      '高优先级',
      '中优先级',
      '低优先级',
    ])
    expect(wrapper.findAll('.module-item').map((m) => m.text())).toEqual([
      '登录2',
      '支付1',
      '搜索1',
    ])
    expect(wrapper.find('.next-step-hint .el-button').text()).toContain('下一步：管理测试点')
  })

  it('无测试点时展示等待提取', () => {
    const { wrapper } = setup({ step: 2, points: [] })

    expect(wrapper.find('.preview-header').text()).toBe('等待提取')
    expect(wrapper.find('.el-empty').text()).toBe('等待提取测试点')
  })
})

describe('RightPreviewPanel — 步骤4 操作指南', () => {
  it('展示四条指南与快捷统计', () => {
    const { wrapper } = setup({ step: 3, selectedRows: [{ id: 1 }, { id: 2 }] })

    expect(wrapper.find('.preview-header').text()).toBe('操作指南')
    expect(wrapper.findAll('.guide-item span').map((n) => n.text())).toEqual([
      '支持逐条校验提取结果后再保存',
      '可编辑单个测试点后再入库',
      '建议保存后回测试点管理继续日常维护',
      '仅在需要高级流程时再进入 AI 生成页',
    ])
    expect(wrapper.findAll('.qs-label').map((n) => n.text())).toEqual(['总测试点', '已选中'])
    expect(wrapper.findAll('.qs-value').map((n) => n.text())).toEqual(['4', '2'])
  })

  it('已入库时总数取库内统计', () => {
    const { wrapper } = setup({
      step: 3,
      savedFromDb: true,
      dbTotal: 120,
      selectedRows: [{ id: 1 }],
    })

    expect(wrapper.findAll('.qs-value').map((n) => n.text())).toEqual(['120', '1'])
  })

  it('无测试点时不展示快捷统计', () => {
    const { wrapper } = setup({ step: 3, points: [] })

    expect(wrapper.find('.quick-stats').exists()).toBe(false)
  })
})
