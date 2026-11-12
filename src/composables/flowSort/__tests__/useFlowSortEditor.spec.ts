import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { provideFlowSortEditor, type FlowSortEditorProps } from '../useFlowSortEditor'
import { useFlowSortEditorSync } from '../useFlowSortEditorSync'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import type { UIScreen } from '@/api/uiPrototype'

const { mockMessage, mockFlowSortStore, mockFitView, mockSetCenter, mockViewport } = vi.hoisted(
  () => ({
    mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
    mockFlowSortStore: {
      quickMode: false,
      nodes: [] as unknown[],
      edges: [] as unknown[],
      isBackendLoaded: false,
      updateNodes: vi.fn(),
      updateEdges: vi.fn(),
      triggerAutoSave: vi.fn(),
      manualSave: vi.fn(),
      reset: vi.fn(),
      setProjectId: vi.fn(),
    },
    mockFitView: vi.fn(),
    mockSetCenter: vi.fn(),
    mockViewport: { value: { x: 0, y: 0, zoom: 1 } },
  })
)

vi.mock('@vue-flow/core', () => ({
  MarkerType: { ArrowClosed: 'arrowclosed' },
  useVueFlow: () => ({
    fitView: mockFitView,
    viewport: mockViewport,
    setCenter: mockSetCenter,
  }),
}))
vi.mock('element-plus', () => ({
  ElMessage: mockMessage,
  ElMessageBox: { confirm: vi.fn() },
}))
vi.mock('@/store/flowSort', async () => {
  const { reactive } = await import('vue')
  // 用 reactive 包装，watch(() => store.xxx) 才能正常触发
  const store = reactive(mockFlowSortStore)
  return { useFlowSortStore: () => store }
})
vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => ({ formData: { test_point_ids: [] }, testPoints: [] }),
}))
vi.mock('@/composables/useTestPointLink', () => ({
  useTestPointLink: () => ({ getRelatedScreenIds: () => new Set<number>() }),
}))

function screen(id: number, name = `页面${id}`): UIScreen {
  return {
    id,
    screen_name: name,
    summary: `摘要${id}`,
    element_count: 3,
    ui_spec: { elements: [{ type: 'button', label: '提交', position: { x: 1, y: 2 } }] },
  } as unknown as UIScreen
}

type Ctx = ReturnType<typeof provideFlowSortEditor>

function mountEditor(props: Partial<FlowSortEditorProps> = {}) {
  let ctx!: Ctx
  const emit = vi.fn()
  const Comp = defineComponent({
    setup(_props, { emit: _emit }) {
      const c = provideFlowSortEditor(
        {
          screens: props.screens ?? [screen(1), screen(2)],
          screenImageUrls: props.screenImageUrls,
          moduleInfo: props.moduleInfo,
          highlightedScreenIds: props.highlightedScreenIds,
        },
        emit as never
      )
      useFlowSortEditorSync(c)
      ctx = c
      return () => null
    },
  })
  const wrapper = mount(Comp)
  return { wrapper, ctx, emit }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockFlowSortStore.quickMode = false
  mockFlowSortStore.nodes = []
  mockFlowSortStore.edges = []
  mockFlowSortStore.isBackendLoaded = false
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useFlowSortEditor — 由 screens 生成画布', () => {
  it('编辑模式下主干节点等距排布并自动连线', () => {
    const { ctx, emit } = mountEditor()

    expect(ctx.vueFlowNodes.value.map((n) => n.position.x)).toEqual([0, 280])
    expect(ctx.vueFlowNodes.value[0].data).toMatchObject({
      screen_id: 1,
      screen_name: '页面1',
      flow_type: 'main',
      main_order: 1,
    })
    // ui_spec.elements 被扁平化为画布节点数据
    expect(ctx.vueFlowNodes.value[0].data.ui_spec_elements?.[0]).toMatchObject({
      type: 'button',
      label: '提交',
      position: '{"x":1,"y":2}',
    })
    expect(ctx.vueFlowEdges.value).toHaveLength(1)
    expect(emit).toHaveBeenCalledWith(
      'update:sort-data',
      expect.objectContaining({ mode: 'graph' })
    )
  })

  it('快速模式按 4 列网格排布且不自动连线', () => {
    mockFlowSortStore.quickMode = true
    const { ctx } = mountEditor({
      screens: [screen(1), screen(2), screen(3), screen(4), screen(5)],
    })

    const positions = ctx.vueFlowNodes.value.map((n) => [n.position.x, n.position.y])
    expect(positions).toEqual([
      [0, 0],
      [280, 0],
      [560, 0],
      [840, 0],
      [0, 260],
    ])
    expect(ctx.vueFlowEdges.value).toEqual([])
  })

  it('image_url 优先取 props.screenImageUrls', () => {
    const { ctx } = mountEditor({ screenImageUrls: { 1: 'http://img/1.png' } })

    expect(ctx.vueFlowNodes.value[0].data.image_url).toBe('http://img/1.png')
    expect(ctx.vueFlowNodes.value[1].data.image_url).toBe('')
  })
})

describe('useFlowSortEditor — 交互态', () => {
  it('默认概览模式，切换模式后重置搜索并重新适配视图', async () => {
    const { ctx } = mountEditor()
    expect(ctx.displayMode.value).toBe('overview')
    expect(ctx.isOverviewMode.value).toBe(true)

    ctx.searchKeyword.value = '登录'
    ctx.displayMode.value = 'edit'
    await nextTick()
    await nextTick()

    expect(ctx.searchKeyword.value).toBe('')
    expect(mockFitView).toHaveBeenCalled()
  })

  it('选择变更同步选中节点', () => {
    const { ctx } = mountEditor()

    ctx.handleSelectionChange({ nodes: [{ id: 'node_1' }, { id: 'node_2' }] as never })

    expect(ctx.selectedNodes.value).toEqual(['node_1', 'node_2'])
  })

  it('点击节点打开详情面板，点击画布关闭', () => {
    const { ctx } = mountEditor()

    ctx.handleNodeClick({ node: { id: 'node_1' } as never })
    expect(ctx.showDetailPanel.value).toBe(true)
    expect(ctx.detailPanelNodeId.value).toBe('node_1')
    expect(ctx.detailPanelNodeData.value).toMatchObject({ screen_id: 1, screen_name: '页面1' })

    ctx.handlePaneClick()
    expect(ctx.showDetailPanel.value).toBe(false)
    expect(ctx.detailPanelNodeData.value).toBeNull()
  })

  it('折叠分组时隐藏其子节点与关联边', () => {
    const { ctx } = mountEditor()
    // 手动造一条分支边：node_1 → node_2（branch）
    ctx.vueFlowNodes.value = ctx.vueFlowNodes.value.map((n) =>
      n.id === 'node_2' ? { ...n, data: { ...n.data, flow_type: 'branch' } } : n
    )
    ctx.vueFlowEdges.value = [
      {
        id: 'e1',
        source: 'node_1',
        target: 'node_2',
        data: { edge_type: 'branch' },
      } as never,
    ]

    ctx.handleToggleCollapse('node_1')
    expect(ctx.collapsedParentNodeIds.value).toEqual(['node_1'])
    expect(ctx.getChildBranchCount('node_1')).toBe(1)

    ctx.applyCollapsedHidden()
    const child = ctx.vueFlowNodes.value.find((n) => n.id === 'node_2')
    expect(child?.hidden).toBe(true)
    expect(ctx.vueFlowEdges.value[0].hidden).toBe(true)

    ctx.handleToggleCollapse('node_1')
    expect(ctx.collapsedParentNodeIds.value).toEqual([])
  })

  it('canQuickCreateBranch 要求恰好选中一个主干节点', () => {
    const { ctx } = mountEditor()

    expect(ctx.canQuickCreateBranch.value).toBe(false)

    ctx.selectedNodes.value = ['node_1']
    expect(ctx.canQuickCreateBranch.value).toBe(true)

    ctx.selectedNodes.value = ['node_1', 'node_2']
    expect(ctx.canQuickCreateBranch.value).toBe(false)
  })

  it('minimap 颜色按 flow_type 映射，未知回退主色', () => {
    const { ctx } = mountEditor()

    expect(ctx.minimapNodeColor({ data: { flow_type: 'branch' } } as never)).toBe('#67c23a')
    expect(ctx.minimapNodeColor({ data: { flow_type: 'x' } } as never)).toBe('#409eff')
    expect(ctx.minimapNodeColor({ data: {} } as never)).toBe('#409eff')
  })
})

describe('useFlowSortEditor — 布局与排序', () => {
  it('切换布局模式触发自动布局并提示完成', () => {
    const { ctx } = mountEditor()

    ctx.handleLayoutModeChange('horizontal')

    expect(ctx.layoutMode.value).toBe('horizontal')
    expect(mockMessage.success).toHaveBeenCalledTimes(1)
    expect(ctx.vueFlowNodes.value).toHaveLength(2)
  })

  it('主干步骤重排按 orderedIds 重编号 main_order', () => {
    const { ctx } = mountEditor()

    ctx.handleMainStepReorder(['node_2', 'node_1'])

    const orderOf = (id: string) =>
      (ctx.vueFlowNodes.value.find((n) => n.id === id)?.data as { main_order?: number }).main_order
    expect(orderOf('node_2')).toBe(1)
    expect(orderOf('node_1')).toBe(2)
  })

  it('mainNodeOptions 主干深度为 0，非主干按父边取深度', () => {
    const { ctx } = mountEditor()

    const options = ctx.mainNodeOptions.value
    expect(options).toHaveLength(2)
    expect(options.every((o) => o.depth === 0)).toBe(true)
  })
})

describe('useFlowSortEditor — 过滤与快捷操作', () => {
  it('过滤 branch 时保留主干与分支节点，隐藏其他', () => {
    const { ctx } = mountEditor({
      screens: [screen(1), screen(2), screen(3)],
    })
    ctx.vueFlowNodes.value = ctx.vueFlowNodes.value.map((n, i) => ({
      ...n,
      data: { ...n.data, flow_type: i === 2 ? 'exception' : 'main' },
    }))

    ctx.flowFilter.value = 'branch'
    ctx.applyFlowFilter()

    const hidden = Object.fromEntries(ctx.vueFlowNodes.value.map((n) => [n.id, n.hidden]))
    expect(hidden).toEqual({ node_1: false, node_2: false, node_3: true })

    ctx.flowFilter.value = 'all'
    ctx.applyFlowFilter()
    expect(ctx.vueFlowNodes.value.every((n) => n.hidden === false)).toBe(true)
  })

  it('节点预览事件携带 screen 信息', () => {
    const { ctx, emit } = mountEditor()

    ctx.handleNodePreview({ screen_id: 7, screen_name: '详情页', image_url: 'i.png' } as never)

    expect(emit).toHaveBeenCalledWith('preview-screen', {
      screen_id: 7,
      screen_name: '详情页',
      image_url: 'i.png',
    })
  })

  it('定位节点设置焦点、选中与画布中心', () => {
    const { ctx } = mountEditor()

    ctx.handleDetailLocateNode('node_2')

    expect(ctx.focusedNodeId.value).toBe('node_2')
    expect(ctx.selectedNodes.value).toEqual(['node_2'])
    expect(ctx.detailPanelNodeId.value).toBe('node_2')
    expect(mockSetCenter).toHaveBeenCalledWith(280, 0, expect.objectContaining({ duration: 300 }))
  })
})

describe('useFlowSortEditor — 键盘快捷键', () => {
  function keydown(init: Partial<KeyboardEvent>, target: Partial<HTMLElement> = {}) {
    return {
      key: init.key ?? '',
      code: init.code ?? '',
      ctrlKey: init.ctrlKey ?? false,
      metaKey: init.metaKey ?? false,
      preventDefault: vi.fn(),
      target: { tagName: 'DIV', ...target } as unknown as HTMLElement,
    } as unknown as KeyboardEvent
  }

  it('输入框内不响应快捷键', () => {
    const { ctx } = mountEditor()
    ctx.selectedNodes.value = ['node_1']

    ctx.handleKeyDown(keydown({ key: 'Delete' }, { tagName: 'INPUT' }))

    expect(ctx.selectedNodes.value).toEqual(['node_1'])
  })

  it('Delete 删除选中节点', () => {
    const { ctx } = mountEditor()
    ctx.selectedNodes.value = ['node_2']

    ctx.handleKeyDown(keydown({ key: 'Delete' }))

    expect(ctx.vueFlowNodes.value.map((n) => n.id)).toEqual(['node_1'])
  })

  it('Esc 清空选中，Ctrl+0 适配视图', () => {
    const { ctx } = mountEditor()
    ctx.selectedNodes.value = ['node_1']

    ctx.handleKeyDown(keydown({ key: 'Escape' }))
    expect(ctx.selectedNodes.value).toEqual([])

    mockFitView.mockClear()
    ctx.handleKeyDown(keydown({ key: '0', ctrlKey: true }))
    expect(mockFitView).toHaveBeenCalledWith({ duration: 220, padding: 0.15 })
  })

  it('Ctrl+P 打开提示词预览', () => {
    const { ctx } = mountEditor()

    ctx.handleKeyDown(keydown({ key: 'p', ctrlKey: true }))

    expect(ctx.showPromptPreview.value).toBe(true)
  })

  it('Space 预览当前选中节点', () => {
    const { ctx, emit } = mountEditor()
    ctx.selectedNodes.value = ['node_1']

    ctx.handleKeyDown(keydown({ key: ' ', code: 'Space' }))

    expect(emit).toHaveBeenCalledWith('preview-screen', expect.objectContaining({ screen_id: 1 }))
  })

  it('快速模式只保留 Ctrl+S 保存，忽略删除等编辑快捷键', () => {
    mockFlowSortStore.quickMode = true
    const { ctx } = mountEditor()
    ctx.selectedNodes.value = ['node_1']

    ctx.handleKeyDown(keydown({ key: 'Delete' }))
    expect(ctx.vueFlowNodes.value).toHaveLength(2)

    ctx.handleKeyDown(keydown({ key: 's', ctrlKey: true }))
    expect(mockFlowSortStore.manualSave).toHaveBeenCalledTimes(1)
  })
})

describe('useFlowSortEditor — 拖拽自动连线', () => {
  it('拖拽结束在阈值内自动补边', () => {
    const { ctx } = mountEditor({
      screens: [screen(1), screen(2)],
    })
    ctx.vueFlowEdges.value = []
    ctx.vueFlowNodes.value = ctx.vueFlowNodes.value.map((n, i) => ({
      ...n,
      position: { x: i * 100, y: 0 },
    })) as FlowEditorNode[]
    ctx.selectedNodes.value = ['node_2']

    ctx.onNodeDragStop()

    expect(ctx.vueFlowEdges.value).toHaveLength(1)
    expect(ctx.vueFlowEdges.value[0]).toMatchObject({ source: 'node_1', target: 'node_2' })
    expect(mockMessage.success).toHaveBeenCalledWith('已自动连接 1 条邻近连线')
  })

  it('已存在反向连线时不重复创建', () => {
    const { ctx } = mountEditor()
    ctx.vueFlowNodes.value = ctx.vueFlowNodes.value.map((n, i) => ({
      ...n,
      position: { x: i * 100, y: 0 },
    })) as FlowEditorNode[]
    ctx.vueFlowEdges.value = [
      { id: 'e1', source: 'node_1', target: 'node_2', data: { edge_type: 'normal' } } as never,
    ]
    ctx.selectedNodes.value = ['node_2']

    ctx.onNodeDragStop()

    expect(ctx.vueFlowEdges.value).toHaveLength(1)
  })

  it('快速模式不自动连线', () => {
    mockFlowSortStore.quickMode = true
    const { ctx } = mountEditor({ screens: [screen(1), screen(2)] })
    ctx.selectedNodes.value = ['node_2']

    ctx.onNodeDragStop()

    expect(ctx.vueFlowEdges.value).toHaveLength(0)
    expect(mockMessage.success).not.toHaveBeenCalled()
  })
})

describe('useFlowSortEditor — 后端数据还原', () => {
  it('isBackendLoaded 置真后按 store 节点/边还原画布', async () => {
    const { ctx } = mountEditor()
    mockFlowSortStore.nodes = [
      {
        id: 'node_9',
        screen_id: 1,
        screen_name: '页面1',
        summary: 's',
        flow_type: 'main',
        main_order: 1,
        position: { x: 10, y: 20 },
        ui_spec_elements: [],
      },
    ]
    mockFlowSortStore.edges = [
      { id: 'e1', source: '1', target: '1', edge_type: 'normal', label: '连线' },
    ]

    // 必须通过 store 代理赋值，直接改原始对象不会触发 watch
    ;(ctx.flowSortStore as unknown as { isBackendLoaded: boolean }).isBackendLoaded = true
    await nextTick()
    await nextTick()
    await nextTick()

    expect(ctx.vueFlowNodes.value).toHaveLength(1)
    expect(ctx.vueFlowNodes.value[0].position).toEqual({ x: 10, y: 20 })
    expect(ctx.isRestoredFromBackend.value).toBe(true)
  })
})
