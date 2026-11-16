import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick, reactive, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/flowSort/useFlowSortEditor', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/flowSort/useFlowSortEditor')>()
  return { ...actual, useFlowSortEditor: () => mockCtx.current }
})

import { LAYOUT_MODE_LABELS } from '@/composables/flowSort/useFlowSortEditor'
import FlowSortToolbar from '../FlowSortToolbar.vue'

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: '' },
  },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElButtonGroupStub = defineComponent({
  name: 'ElButtonGroup',
  template: '<div class="el-button-group"><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTooltipStub = defineComponent({
  name: 'ElTooltip',
  props: { content: { type: String, default: '' } },
  template: '<span class="el-tooltip" :data-content="content"><slot /></span>',
})

const ElDividerStub = defineComponent({
  name: 'ElDivider',
  template: '<span class="el-divider" />',
})

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  emits: ['command'],
  template: '<div class="el-dropdown"><slot /><slot name="dropdown" /></div>',
})

const ElDropdownMenuStub = defineComponent({
  name: 'ElDropdownMenu',
  template: '<div class="el-dropdown-menu"><slot /></div>',
})

const ElDropdownItemStub = defineComponent({
  name: 'ElDropdownItem',
  props: { command: { type: [String, Number], default: '' } },
  template:
    '<div class="el-dropdown-item" :data-command="command" @click="$emit(\'click\')"><slot /></div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  emits: ['update:modelValue', 'input', 'clear', 'focus', 'blur', 'keydown'],
  template: `<input class="el-input" :value="modelValue" :placeholder="placeholder" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const ElLinkStub = defineComponent({
  name: 'ElLink',
  emits: ['click'],
  template: '<a class="el-link" @click="$emit(\'click\')"><slot /></a>',
})

const stubs = {
  ElButton: ElButtonStub,
  ElButtonGroup: ElButtonGroupStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElTooltip: ElTooltipStub,
  ElDivider: ElDividerStub,
  ElDropdown: ElDropdownStub,
  ElDropdownMenu: ElDropdownMenuStub,
  ElDropdownItem: ElDropdownItemStub,
  ElInput: ElInputStub,
  ElLink: ElLinkStub,
}

function setup(options: { quickMode?: boolean; saveStatus?: string; edges?: unknown[] } = {}) {
  const flowSortStore = reactive({
    quickMode: options.quickMode ?? false,
    setQuickMode: vi.fn((value: boolean) => {
      flowSortStore.quickMode = value
    }),
    saveStatus: options.saveStatus ?? 'unsaved',
    projectId: 9,
    manualSave: vi.fn(),
    manualRetrySave: vi.fn(),
    isBackendLoaded: true,
    edges: (options.edges ?? []) as unknown[],
  })

  const ctx: Record<string, unknown> = {
    flowSortStore,
    props: { screens: [{ id: 1 }, { id: 2 }, { id: 3 }] },
    vueFlowNodes: ref([
      { id: 'n1', data: { flow_type: 'main' } },
      { id: 'n2', data: { flow_type: 'main' } },
      { id: 'n3', data: { flow_type: 'branch' } },
    ]),
    vueFlowEdges: ref([]),
    displayMode: ref<'overview' | 'edit'>('edit'),
    handleFitView: vi.fn(),
    showMainStepList: ref(false),
    flowFilter: ref('all'),
    applyFlowFilter: vi.fn(),
    handleLayoutModeChange: vi.fn(),
    layoutMode: ref('LR'),
    handlePreviewPrompt: vi.fn(),
    handleUndo: vi.fn(),
    canUndo: ref(false),
    showCompletenessPanel: ref(false),
    selectedNodes: ref<string[]>([]),
    handleDeleteSelected: vi.fn(),
    handleBatchFlowTypeChange: vi.fn(),
    getSelectedMainNodeId: vi.fn(() => null),
    getSelectedMainOrder: vi.fn(() => 2),
    moveSelectedMainNode: vi.fn(),
    canMoveMainBackward: vi.fn(() => false),
    canMoveMainForward: vi.fn(() => true),
    canQuickCreateBranch: ref(false),
    handleQuickCreateBranch: vi.fn(),
    showEdgeSuggestion: ref(false),
    isPlaying: ref(false),
    startPlayback: vi.fn(),
    stopPlayback: vi.fn(),
    searchKeyword: ref(''),
    debouncedSearch: vi.fn(),
    clearSearch: vi.fn(),
    locateFirstMatch: vi.fn(),
    showSearchDropdown: ref(false),
    handleSearchBlur: vi.fn(),
    searchResults: ref<Record<string, unknown>[]>([]),
    locateNode: vi.fn(),
  }
  mockCtx.current = ctx

  const wrapper = mount(FlowSortToolbar, { global: { stubs } })
  return { ctx, flowSortStore, wrapper }
}

const buttonByText = (wrapper: ReturnType<typeof setup>['wrapper'], text: string) =>
  wrapper.findAll('button').find((b) => b.text().replace(/\s+/g, '') === text)

describe('FlowSortToolbar — 生成策略', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('流程编排模式展示标题、说明与图例', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.editor-title').text()).toBe('流程编排')
    expect(wrapper.find('.editor-subtitle').text()).toContain('总览查看流程全貌')
    expect(wrapper.findAll('.legend-item').map((l) => l.text())).toEqual([
      '主干',
      '分支',
      '异常',
      '弹窗',
    ])
  })

  it('快速生成模式展示标题、说明与页面预览摘要', () => {
    const { wrapper } = setup({ quickMode: true })

    expect(wrapper.find('.editor-title').text()).toBe('快速生成')
    expect(wrapper.find('.editor-subtitle').text()).toContain('按已选 UI 页面生成测试用例')
    expect(wrapper.find('.quick-toolbar-summary').text()).toContain('页面预览 3')
    expect(wrapper.find('.flow-legend').exists()).toBe(false)
  })

  it('切换按钮写入 store 的 quickMode', async () => {
    const { flowSortStore, wrapper } = setup()

    await buttonByText(wrapper, '快速生成')!.trigger('click')
    expect(flowSortStore.setQuickMode).toHaveBeenCalledWith(true)

    await buttonByText(wrapper, '流程编排')!.trigger('click')
    expect(flowSortStore.setQuickMode).toHaveBeenCalledWith(false)
  })

  it('快速模式下存在连线时提示可切换编排（含内联链接）', async () => {
    const { ctx, flowSortStore, wrapper } = setup({ quickMode: true })
    ;(ctx.vueFlowEdges as { value: unknown[] }).value = [{ id: 'e1' }]
    await nextTick()

    const warning = wrapper.findAll('.mode-hint-warning')
    expect(warning[0].text()).toContain('已手动添加连线')

    await warning[0].find('.el-link').trigger('click')
    expect(flowSortStore.setQuickMode).toHaveBeenCalledWith(false)
  })

  it('后端已加载连线且未提示过时给出建议，可永久关闭', async () => {
    const { wrapper } = setup({ quickMode: true, edges: [{ id: 'e1' }] })
    await nextTick()

    const hint = wrapper
      .findAll('.mode-hint-warning')
      .find((w) => w.text().includes('检测到已配置的流程连线'))
    expect(hint).toBeDefined()

    await hint!.find('.dismiss-link').trigger('click')
    expect(localStorage.getItem('flow-editor-quick-mode-hint-dismissed')).toBe('true')
  })

  it('已关闭过提示时不再展示建议', async () => {
    localStorage.setItem('flow-editor-quick-mode-hint-dismissed', 'true')
    const { wrapper } = setup({ quickMode: true, edges: [{ id: 'e1' }] })
    await nextTick()

    expect(
      wrapper.findAll('.mode-hint-warning').some((w) => w.text().includes('检测到已配置的流程连线'))
    ).toBe(false)
  })
})

describe('FlowSortToolbar — 总览视图', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('总览模式展示适配视图与统计', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.displayMode as { value: string }).value = 'overview'
    await nextTick()

    expect(wrapper.findAll('.overview-stats .el-tag').map((t) => t.text())).toEqual([
      '3 个页面',
      '2 个主干',
    ])
    expect(buttonByText(wrapper, '总览')!.attributes('data-type')).toBe('primary')

    await wrapper.find('.el-tooltip[data-content="适配视图"] button').trigger('click')
    expect(ctx.handleFitView).toHaveBeenCalledTimes(1)
  })

  it('调整模式展示主干步列表、撤销与完整度开关', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.el-tooltip[data-content="主干步骤列表"] button').trigger('click')
    expect((ctx.showMainStepList as { value: boolean }).value).toBe(true)

    await wrapper.find('.el-tooltip[data-content="流程完整度"] button').trigger('click')
    expect((ctx.showCompletenessPanel as { value: boolean }).value).toBe(true)

    const undoBtn = wrapper.find('.el-tooltip[data-content="撤销 (Ctrl+Z)"] button')
    expect(undoBtn.attributes('disabled')).toBeDefined()
  })

  it('筛选命令写入 flowFilter 并应用', async () => {
    const { ctx, wrapper } = setup()
    const dropdown = wrapper.findAllComponents(ElDropdownStub)[0]

    dropdown.vm.$emit('command', 'branch')

    expect((ctx.flowFilter as { value: string }).value).toBe('branch')
    expect(ctx.applyFlowFilter).toHaveBeenCalledTimes(1)
  })

  it('布局模式下拉按 LAYOUT_MODE_LABELS 渲染并回传命令', async () => {
    const { ctx, wrapper } = setup()
    const labels = Object.values(LAYOUT_MODE_LABELS) as string[]

    const layoutDropdown = wrapper
      .findAllComponents(ElDropdownStub)
      .find((d) => labels.every((label) => d.text().includes(label)))!

    expect(layoutDropdown.findAll('.el-dropdown-item')).toHaveLength(labels.length)

    layoutDropdown.vm.$emit('command', 'TB')

    expect(ctx.handleLayoutModeChange).toHaveBeenCalledWith('TB')
  })

  it('预览 Prompt 触发对应动作', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.el-tooltip[data-content="预览 Prompt (Ctrl+P)"] button').trigger('click')

    expect(ctx.handlePreviewPrompt).toHaveBeenCalledTimes(1)
  })
})

describe('FlowSortToolbar — 选中与主干操作', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('选中多个节点时展示删除与批量类型入口', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.selectedNodes as { value: string[] }).value = ['n1', 'n2']
    await nextTick()

    expect(wrapper.find('.selection-info').text()).toContain('已选 2 个节点')

    await buttonByText(wrapper, '批量设置类型')!.trigger('click')
    const batchDropdown = wrapper
      .findAllComponents(ElDropdownStub)
      .find((d) => d.text().includes('主干流程'))!
    batchDropdown.vm.$emit('command', 'exception')

    expect(ctx.handleBatchFlowTypeChange).toHaveBeenCalledWith('exception')
  })

  it('单选时隐藏批量类型，删除按钮可用', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.selectedNodes as { value: string[] }).value = ['n1']
    await nextTick()

    expect(wrapper.text()).not.toContain('批量设置类型')

    await buttonByText(wrapper, '删除')!.trigger('click')
    expect(ctx.handleDeleteSelected).toHaveBeenCalledTimes(1)
  })

  it('选中主干节点时展示步序与前后移按钮状态', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.getSelectedMainNodeId as ReturnType<typeof vi.fn>).mockReturnValue('n2')
    ;(ctx.selectedNodes as { value: string[] }).value = ['n2']
    await nextTick()

    expect(wrapper.find('.main-order-actions').text()).toContain('主干第 2 步')

    const [backward, forward] = wrapper.findAll('.main-order-actions button')
    expect(backward.attributes('disabled')).toBeDefined()
    expect(forward.attributes('disabled')).toBeUndefined()

    await forward.trigger('click')
    expect(ctx.moveSelectedMainNode).toHaveBeenCalledWith(1)
  })

  it('可创建分支时展示入口', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.canQuickCreateBranch as { value: boolean }).value = true
    await nextTick()

    await buttonByText(wrapper, '创建分支')!.trigger('click')

    expect(ctx.handleQuickCreateBranch).toHaveBeenCalledTimes(1)
  })
})

describe('FlowSortToolbar — 播放与搜索', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('播放按钮在未播放时启动、播放中停止', async () => {
    const { ctx, wrapper } = setup()
    // zoom-controls 内顺序：智能识别 → 路径播放 → 搜索
    const playBtn = () => wrapper.findAll('.zoom-controls button')[1]

    await playBtn().trigger('click')
    expect(ctx.startPlayback).toHaveBeenCalledTimes(1)
    expect(ctx.stopPlayback).not.toHaveBeenCalled()
    ;(ctx.isPlaying as { value: boolean }).value = true
    await nextTick()
    await playBtn().trigger('click')
    expect(ctx.stopPlayback).toHaveBeenCalledTimes(1)
  })

  it('搜索有结果时展示下拉并可定位', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.showSearchDropdown as { value: boolean }).value = true
    ;(ctx.searchResults as { value: unknown[] }).value = [
      { id: 'n3', screen_name: '登录页', flow_type: 'branch' },
    ]
    await nextTick()

    const item = wrapper.find('.search-result-item')
    expect(item.text()).toContain('登录页')
    expect(item.find('.el-tag').text()).toBe('分支')

    await item.trigger('click')
    expect(ctx.locateNode).toHaveBeenCalledWith('n3')
  })

  it('搜索无结果时展示空态', async () => {
    const { ctx, wrapper } = setup()
    ;(ctx.showSearchDropdown as { value: boolean }).value = true
    ;(ctx.searchKeyword as { value: string }).value = '不存在'
    ;(ctx.searchResults as { value: unknown[] }).value = []
    await nextTick()

    expect(wrapper.find('.search-empty').text()).toBe('未找到匹配页面')
  })
})

describe('FlowSortToolbar — 保存状态', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('未保存且有项目时点击保存调用 manualSave', async () => {
    const { flowSortStore, wrapper } = setup({ saveStatus: 'unsaved' })

    await wrapper.find('.save-controls button').trigger('click')

    expect(flowSortStore.manualSave).toHaveBeenCalledTimes(1)
  })

  it('未保存且无项目时保存按钮禁用并提示', () => {
    const { flowSortStore, wrapper } = setup({ saveStatus: 'unsaved' })
    flowSortStore.projectId = null as unknown as number

    return nextTick().then(() => {
      const btn = wrapper.find('.save-controls button')
      expect(btn.attributes('disabled')).toBeDefined()
      expect(wrapper.find('.save-controls .el-tooltip').attributes('data-content')).toBe(
        '请先选择项目'
      )
    })
  })

  it.each([
    ['saving', '保存中...'],
    ['saved', '已保存'],
  ])('状态 %s 展示 %s', (status, text) => {
    const { wrapper } = setup({ saveStatus: status })

    expect(wrapper.find('.save-controls').text()).toBe(text)
  })

  it('保存失败时可点击重试', async () => {
    const { flowSortStore, wrapper } = setup({ saveStatus: 'error' })

    expect(wrapper.find('.save-controls').text()).toContain('保存失败')

    await wrapper.find('.save-status-inner').trigger('click')
    expect(flowSortStore.manualRetrySave).toHaveBeenCalledTimes(1)
  })
})
