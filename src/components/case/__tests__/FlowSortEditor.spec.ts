import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, reactive, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/flowSort/useFlowSortEditor', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/flowSort/useFlowSortEditor')>()
  return { ...actual, provideFlowSortEditor: () => mockCtx.current }
})

vi.mock('@/composables/flowSort/useFlowSortEditorSync', () => ({
  useFlowSortEditorSync: vi.fn(),
}))

import type { UIScreen } from '@/api/uiPrototype'
import FlowSortEditor from '../FlowSortEditor.vue'

const VueFlowStub = defineComponent({
  name: 'VueFlow',
  props: { nodes: { type: Array, default: () => [] }, edges: { type: Array, default: () => [] } },
  template: '<div class="vue-flow"><slot /></div>',
})

const FlowSortToolbarStub = defineComponent({
  name: 'FlowSortToolbar',
  template: '<div class="toolbar-stub" />',
})

const MainStepListStub = defineComponent({
  name: 'MainStepList',
  props: {
    visible: { type: Boolean, default: false },
    activeNodeId: { type: String, default: '' },
  },
  template: '<div class="main-step-list" />',
})

const NodeDetailPanelStub = defineComponent({
  name: 'NodeDetailPanel',
  props: { visible: { type: Boolean, default: false } },
  template: '<div class="node-detail-panel" />',
})

const FlowCompletenessPanelStub = defineComponent({
  name: 'FlowCompletenessPanel',
  props: {
    visible: { type: Boolean, default: false },
    stats: { type: Object, default: () => ({}) },
  },
  template: '<div class="flow-completeness-panel" />',
})

const UIScreenCardStub = defineComponent({
  name: 'UIScreenCard',
  props: {
    screen: { type: Object, default: () => ({}) },
    imageUrl: { type: String, default: '' },
    orderText: { type: [String, Number], default: '' },
    overlayText: { type: String, default: '' },
  },
  emits: ['click'],
  template: `<button class="ui-screen-card" :data-order="orderText" @click="$emit('click', screen)">{{ screen.screen_name }}</button>`,
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  emits: ['click'],
  template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const simpleStub = (name: string) =>
  defineComponent({ name, template: `<div class="${name}-stub" />` })

const stubs = {
  VueFlow: VueFlowStub,
  Background: simpleStub('Background'),
  Controls: simpleStub('Controls'),
  MiniMap: simpleStub('MiniMap'),
  FlowNodeCard: simpleStub('FlowNodeCard'),
  FlowSortToolbar: FlowSortToolbarStub,
  MainStepList: MainStepListStub,
  NodeDetailPanel: NodeDetailPanelStub,
  FlowCompletenessPanel: FlowCompletenessPanelStub,
  FlowSortEdgeTooltip: simpleStub('FlowSortEdgeTooltip'),
  EdgeConditionDialog: simpleStub('EdgeConditionDialog'),
  FlowTypeConfigDialog: simpleStub('FlowTypeConfigDialog'),
  EdgeSuggestionDialog: simpleStub('EdgeSuggestionDialog'),
  FlowPromptPreviewDialog: simpleStub('FlowPromptPreviewDialog'),
  UIScreenCard: UIScreenCardStub,
  ElEmpty: ElEmptyStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  transition: false,
  'transition-group': false,
}

function setup(
  options: { quickMode?: boolean; displayMode?: 'overview' | 'edit'; nodes?: unknown[] } = {}
) {
  const ctx = {
    flowSortStore: reactive({ quickMode: options.quickMode ?? false, edges: [] as unknown[] }),
    displayMode: ref(options.displayMode ?? 'edit'),
    vueFlowNodes: ref(options.nodes ?? []),
    vueFlowEdges: ref<unknown[]>([]),
    showMainStepList: ref(true),
    detailPanelNodeId: ref<string | null>(null),
    showDetailPanel: ref(true),
    detailPanelNodeData: ref<Record<string, unknown> | null>(null),
    showCompletenessPanel: ref(false),
    showEdgeSuggestion: ref(false),
    showPromptPreview: ref(false),
    promptPreviewFlowData: ref({}),
    conditionDialogVisible: ref(false),
    currentEdgeForm: ref(null),
    flowTypeConfigVisible: ref(false),
    pendingFlowTypeChange: ref(null),
    pendingFlowMeta: ref(null),
    mainNodeOptions: ref([]),
    showShortcutsTip: ref(true),
    showGroupBackground: ref(false),
    nodeGroups: ref<unknown[]>([]),
    svgViewBox: ref({ x: 0, y: 0 }),
    currentZoom: ref(1),
    groupPadding: 16,
    minimapNodeColor: vi.fn(() => '#ccc'),
    minimapNodeStroke: vi.fn(() => '#999'),
    defaultEdgeOptions: ref({}),
    editorRef: ref<HTMLElement | null>(null),
    handleKeyDown: vi.fn(),
    onEdgesChange: vi.fn(),
    onConnect: vi.fn(),
    onNodeDragStart: vi.fn(),
    onNodeDragStop: vi.fn(),
    handlePaneClick: vi.fn(),
    onEdgeMouseEnter: vi.fn(),
    onEdgeMouseMove: vi.fn(),
    onEdgeMouseLeave: vi.fn(),
    handleNodeClick: vi.fn(),
    handleSelectionChange: vi.fn(),
    handleMainStepLocateNode: vi.fn(),
    handleMainStepReorder: vi.fn(),
    handleNodePreview: vi.fn(),
    handleFlowTypeChange: vi.fn(),
    handleToggleCollapse: vi.fn(),
    handleDetailFlowTypeChange: vi.fn(),
    handleDetailLocateNode: vi.fn(),
    handleDetailPreview: vi.fn(),
    handleFlowTypeConfigConfirm: vi.fn(),
    onEdgeConditionConfirm: vi.fn(),
    handleEdgeSuggestionsConfirmed: vi.fn(),
    getFlowSortSubmitData: vi.fn(() => ({ mode: 'flow', nodes: [], edges: [] })),
    getFlowValidationIssues: vi.fn(() => []),
    selectedNodes: ref<string[]>([]),
    draggingNodeId: ref<string | null>(null),
    searchMatchIds: ref<string[]>([]),
    focusedNodeId: ref<string | null>(null),
    upstreamNodeIds: ref(new Set<string>()),
    downstreamNodeIds: ref(new Set<string>()),
    allPathNodeIds: ref(new Set<string>()),
    collapsedParentNodeIds: ref<string[]>([]),
    highlightedScreenIds: ref(new Set<number>()),
    getChildBranchCount: vi.fn(() => 0),
  }
  mockCtx.current = ctx

  const wrapper = mount(FlowSortEditor, {
    props: {
      screens: [
        { id: 1, screen_name: '登录页' },
        { id: 2, screen_name: '首页' },
      ] as unknown as UIScreen[],
      screenImageUrls: { 1: 'https://x/1.png' },
    },
    global: { stubs },
  })
  return { ctx, wrapper }
}

describe('FlowSortEditor — 快速生成模式', () => {
  it('渲染页面预览网格并传递序号与图片', () => {
    const { wrapper } = setup({ quickMode: true })

    const cards = wrapper.findAll('.ui-screen-card')
    expect(cards).toHaveLength(2)
    expect(cards.map((c) => c.attributes('data-order'))).toEqual(['1', '2'])
    expect(cards[0].text()).toBe('登录页')
    expect(wrapper.find('.graph-mode').exists()).toBe(false)
    expect(wrapper.find('.flow-sort-editor').classes()).toContain('quick-generation-mode')
  })

  it('无页面时展示空态', () => {
    const { wrapper } = setup({ quickMode: true })
    return wrapper.setProps({ screens: [] }).then(() => {
      expect(wrapper.find('.quick-preview-empty .el-empty').text()).toBe('暂无屏幕')
    })
  })

  it('点击页面卡片回传预览事件数据', async () => {
    const { ctx, wrapper } = setup({ quickMode: true })

    await wrapper.findAll('.ui-screen-card')[0].trigger('click')

    expect(ctx.handleNodePreview).toHaveBeenCalledWith({
      screen_id: 1,
      screen_name: '登录页',
      image_url: 'https://x/1.png',
      flow_type: 'main',
    })
  })

  it('快速模式不渲染画布相关区块', () => {
    const { wrapper } = setup({ quickMode: true })

    expect(wrapper.find('.vue-flow').exists()).toBe(false)
    expect(wrapper.find('.flow-completeness-panel').exists()).toBe(false)
    expect(wrapper.find('.FlowSortEdgeTooltip-stub').exists()).toBe(false)
    expect(wrapper.find('.shortcuts-tip').exists()).toBe(false)
  })
})

describe('FlowSortEditor — 流程编排模式', () => {
  it('渲染画布、工具栏与完整度面板', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.toolbar-stub').exists()).toBe(true)
    expect(wrapper.find('.vue-flow').exists()).toBe(true)
    expect(wrapper.find('.flow-completeness-panel').exists()).toBe(true)
    expect(wrapper.find('.FlowSortEdgeTooltip-stub').exists()).toBe(true)
    expect(wrapper.find('.main-step-list').exists()).toBe(true)
    expect(wrapper.find('.node-detail-panel').exists()).toBe(true)
  })

  it('总览模式隐藏主干步骤列表并加 overview-mode 类', () => {
    const { wrapper } = setup({ displayMode: 'overview' })

    expect(wrapper.find('.main-step-list').exists()).toBe(false)
    expect(wrapper.find('.flow-sort-editor').classes()).toContain('overview-mode')
  })

  it('空图时展示问题条，点击查看详情打开完整度面板', async () => {
    const { ctx, wrapper } = setup()

    const bar = wrapper.find('.flow-issues-bar')
    expect(bar.text()).toContain('1 个流程问题')

    await bar.find('button').trigger('click')
    expect(ctx.showCompletenessPanel.value).toBe(true)
  })

  it('总览模式不展示问题条', () => {
    const { wrapper } = setup({ displayMode: 'overview' })

    expect(wrapper.find('.flow-issues-bar').exists()).toBe(false)
  })

  it('分组背景仅在有分组且开关打开时渲染', async () => {
    const { ctx, wrapper } = setup()
    expect(wrapper.find('.group-bg-svg').exists()).toBe(false)

    ctx.showGroupBackground.value = true
    ctx.nodeGroups.value = [
      {
        id: 'g1',
        label: '主干组',
        color: '#f00',
        strokeColor: '#c00',
        bounds: { x: 10, y: 20, width: 100, height: 50 },
      },
    ]
    await nextTick()

    const svg = wrapper.find('.group-bg-svg')
    expect(svg.exists()).toBe(true)
    expect(svg.find('rect').attributes('width')).toBe('132')
    expect(svg.find('text').text()).toBe('主干组')
  })

  it('快捷键提示可关闭', async () => {
    const { ctx, wrapper } = setup()
    expect(wrapper.find('.shortcuts-tip').exists()).toBe(true)

    ctx.showShortcutsTip.value = false
    await nextTick()
    // 真实 transition 的离场动画在 rAF 后才移除节点
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(wrapper.find('.shortcuts-tip').exists()).toBe(false)
  })
})

describe('FlowSortEditor — 对外暴露', () => {
  it('透传提交数据与校验问题方法', () => {
    const { ctx, wrapper } = setup()

    expect(wrapper.vm.getFlowSortSubmitData()).toEqual({ mode: 'flow', nodes: [], edges: [] })
    expect(wrapper.vm.getFlowValidationIssues()).toEqual([])
    expect(ctx.getFlowSortSubmitData).toHaveBeenCalled()
  })

  it('快速模式下切换 store 后重新渲染', async () => {
    const { ctx, wrapper } = setup({ quickMode: true })

    ctx.flowSortStore.quickMode = false
    await nextTick()

    expect(wrapper.find('.quick-preview-mode').exists()).toBe(false)
    expect(wrapper.find('.vue-flow').exists()).toBe(true)
  })
})
