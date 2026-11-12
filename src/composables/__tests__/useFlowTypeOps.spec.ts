import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, nextTick } from 'vue'
import { useFlowTypeOps } from '../useFlowTypeOps'
import {
  getNodeData,
  getMainNodesInOrder,
  normalizeMainNodeOrders,
  normalizeEdges,
  inferEdgeType,
  EDGE_STYLES,
  FLOW_TYPE_LABEL_MAP,
} from '@/composables/useFlowEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

const { mockMessage, mockPrompt, mockFitView } = vi.hoisted(() => ({
  mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
  mockPrompt: vi.fn(),
  mockFitView: vi.fn(),
}))

vi.mock('@vue-flow/core', () => ({ MarkerType: { ArrowClosed: 'arrowclosed' } }))
vi.mock('element-plus', () => ({
  ElMessage: mockMessage,
  ElMessageBox: { confirm: vi.fn(), prompt: mockPrompt },
}))

function node(
  id: string,
  flowType: 'main' | 'branch' | 'exception' | 'bypass',
  mainOrder?: number,
  flowMeta?: Record<string, unknown>
): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { flow_type: flowType, main_order: mainOrder, flow_meta: flowMeta, screen_name: id },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): FlowGraphEdge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as FlowGraphEdge
}

function setup(nodes: FlowEditorNode[], edges: FlowGraphEdge[]) {
  const vueFlowNodes = ref(nodes)
  const vueFlowEdges = ref(edges)
  const selectedNodes = ref<string[]>([])
  const layoutMode = ref('standard')
  const focusedNodeId = ref<string | null>(null)
  const isProgrammaticEdgeChange = ref(false)
  const isOverviewMode = ref(false)
  const emitSortData = vi.fn()
  const saveSnapshot = vi.fn()
  const autoLayout = vi.fn((_mode: string, n: FlowEditorNode[]) => n)

  const api = useFlowTypeOps({
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    emitSortData,
    saveSnapshot,
    applyAllEdgeStyles: (e) => e,
    currentEdgeStyles: ref(EDGE_STYLES),
    isOverviewMode,
    getNodeData,
    getMainNodesInOrder: (n, e) => getMainNodesInOrder(n, e as never),
    normalizeMainNodeOrders: (n, e) => normalizeMainNodeOrders(n, e as never),
    normalizeEdges: (e, s, o) => normalizeEdges(e, s, o) as never,
    autoLayoutByMode: autoLayout as never,
    layoutMode,
    focusedNodeId,
    getEdgeStyle: (type) => EDGE_STYLES[type] || EDGE_STYLES.normal,
    isProgrammaticEdgeChange,
    fitView: mockFitView,
  })

  return {
    api,
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    emitSortData,
    saveSnapshot,
    autoLayout,
    isProgrammaticEdgeChange,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useFlowTypeOps — 类型变更入口', () => {
  it('改为非主干类型时先打开配置弹窗', () => {
    const { api, vueFlowNodes } = setup([node('m', 'main', 1)], [])

    api.handleFlowTypeChange('m', 'branch')

    expect(api.flowTypeConfigVisible.value).toBe(true)
    expect(api.pendingFlowTypeChange.value).toEqual({ nodeId: 'm', type: 'branch' })
    expect(api.pendingFlowMeta.value).toBeNull()
    expect(getNodeData(vueFlowNodes.value[0]).flow_type).toBe('main')
  })

  it('携带原 flow_meta 作为弹窗预填', () => {
    const meta = { parent_main_node_id: 'x', trigger_condition: '点击' }
    const { api } = setup([node('b', 'branch', undefined, meta)], [])

    api.handleFlowTypeChange('b', 'exception')

    expect(api.pendingFlowMeta.value).toEqual(meta)
  })

  it('改为 main 时清理入向语义边、重排主干并聚焦布局', () => {
    const { api, vueFlowNodes, vueFlowEdges, emitSortData, autoLayout, isProgrammaticEdgeChange } =
      setup(
        [node('m1', 'main', 1), node('b', 'branch')],
        [edge('e1', 'm1', 'b', 'branch'), edge('e2', 'b', 'm1', 'normal')]
      )

    api.handleFlowTypeChange('b', 'main')

    expect(isProgrammaticEdgeChange.value).toBe(true)
    expect(vueFlowEdges.value.map((e) => e.id)).toEqual(['e2'])
    expect(getNodeData(vueFlowNodes.value[1]).flow_type).toBe('main')
    expect(emitSortData).toHaveBeenCalled()
    expect(autoLayout).toHaveBeenCalledWith(
      'focused-path',
      expect.anything(),
      expect.anything(),
      'b'
    )
  })

  it('节点不存在时静默返回', () => {
    const { api, emitSortData } = setup([node('m', 'main', 1)], [])

    api.handleFlowTypeChange('ghost', 'branch')

    expect(api.flowTypeConfigVisible.value).toBe(false)
    expect(emitSortData).not.toHaveBeenCalled()
  })
})

describe('useFlowTypeOps — 配置确认', () => {
  it('无待处理变更时直接返回', () => {
    const { api, saveSnapshot } = setup([node('m', 'main', 1)], [])

    api.handleFlowTypeConfigConfirm({} as never)

    expect(saveSnapshot).not.toHaveBeenCalled()
  })

  it('主干转分支（中间节点）：断开前后主干边并补直连', () => {
    const { api, vueFlowNodes, vueFlowEdges, emitSortData } = setup(
      [node('m1', 'main', 1), node('m2', 'main', 2), node('m3', 'main', 3)],
      [edge('e1', 'm1', 'm2'), edge('e2', 'm2', 'm3')]
    )
    api.handleFlowTypeChange('m2', 'branch')

    api.handleFlowTypeConfigConfirm({ parent_main_node_id: 'm1', trigger_condition: '点击去重' })

    expect(getNodeData(vueFlowNodes.value[1]).flow_type).toBe('branch')
    expect(getNodeData(vueFlowNodes.value[1]).main_order).toBeUndefined()

    const ids = vueFlowEdges.value.map((e) => `${e.source}->${e.target}`)
    // 原主干边被断开，改为「前驱 -> 后继」直连 + 「前驱 -> 该节点」语义边
    expect(ids).not.toContain('m2->m3')
    expect([...ids].sort()).toEqual(['m1->m2', 'm1->m3'])

    const branchEdge = vueFlowEdges.value.find((e) => e.target === 'm2' && e.source === 'm1')
    expect(branchEdge?.data).toMatchObject({ edge_type: 'branch', condition: '点击去重' })
    expect(branchEdge?.label).toBe('分支：点击去重')
    expect(emitSortData).toHaveBeenCalled()
  })

  it('主干转分支（首节点）：只断开后继边，不补直连', () => {
    const { api, vueFlowEdges } = setup(
      [node('m1', 'main', 1), node('m2', 'main', 2)],
      [edge('e1', 'm1', 'm2')]
    )
    api.handleFlowTypeChange('m1', 'branch')

    api.handleFlowTypeConfigConfirm({ parent_main_node_id: '' })

    const ids = vueFlowEdges.value.map((e) => `${e.source}->${e.target}`)
    expect(ids).toEqual([])
  })

  it('非主干改类型：旧语义父边被替换为新类型的单条边', () => {
    const { api, vueFlowEdges } = setup(
      [node('m', 'main', 1), node('b', 'branch')],
      [edge('e1', 'm', 'b', 'branch')]
    )
    api.handleFlowTypeChange('b', 'exception')

    api.handleFlowTypeConfigConfirm({ parent_main_node_id: 'm', trigger_condition: '接口异常' })

    expect(vueFlowEdges.value).toHaveLength(1)
    expect(vueFlowEdges.value[0]).toMatchObject({
      source: 'm',
      target: 'b',
      label: '异常：接口异常',
    })
    expect(vueFlowEdges.value[0].data).toMatchObject({ edge_type: 'exception' })
  })

  it('确认后关闭弹窗、清空待处理态并适配视图', async () => {
    const { api } = setup([node('m', 'main', 1), node('b', 'branch')], [])
    api.handleFlowTypeChange('b', 'bypass')

    api.handleFlowTypeConfigConfirm({ parent_main_node_id: 'm' })
    await nextTick()

    expect(api.flowTypeConfigVisible.value).toBe(false)
    expect(api.pendingFlowTypeChange.value).toBeNull()
    expect(api.pendingFlowMeta.value).toBeNull()
    expect(mockFitView).toHaveBeenCalledWith({ duration: 300, padding: 0.15 })
  })
})

describe('useFlowTypeOps — 快速创建分支', () => {
  it('未选中单个主干节点时不动作', async () => {
    const { api, selectedNodes } = setup([node('m', 'main', 1)], [])

    await api.handleQuickCreateBranch()
    expect(mockPrompt).not.toHaveBeenCalled()

    selectedNodes.value = ['m']
    await api.handleQuickCreateBranch()
  })

  it('确认后创建虚拟分支节点与分支边', async () => {
    mockPrompt.mockResolvedValueOnce({ value: '  去重分支  ' })
    const { api, vueFlowNodes, vueFlowEdges, selectedNodes, emitSortData, saveSnapshot } = setup(
      [node('m', 'main', 1)],
      []
    )
    selectedNodes.value = ['m']

    await api.handleQuickCreateBranch()

    expect(saveSnapshot).toHaveBeenCalled()
    expect(vueFlowNodes.value).toHaveLength(2)
    const created = vueFlowNodes.value[1]
    expect(created.data).toMatchObject({
      screen_id: -1001,
      screen_name: '去重分支',
      flow_type: 'branch',
    })
    expect(created.position.y).toBe(280)
    expect(vueFlowEdges.value[0]).toMatchObject({
      source: 'm',
      target: created.id,
      label: '去重分支',
    })
    expect(selectedNodes.value).toEqual([created.id])
    expect(emitSortData).toHaveBeenCalled()
    expect(mockMessage.success).toHaveBeenCalledWith('已创建分支节点：去重分支')
  })

  it('用户取消时静默返回', async () => {
    mockPrompt.mockRejectedValueOnce(new Error('cancel'))
    const { api, vueFlowNodes, selectedNodes } = setup([node('m', 'main', 1)], [])
    selectedNodes.value = ['m']

    await api.handleQuickCreateBranch()

    expect(vueFlowNodes.value).toHaveLength(1)
    expect(mockMessage.success).not.toHaveBeenCalled()
  })
})

describe('useFlowTypeOps — 批量改类型', () => {
  it('选中少于 2 个时不动作', () => {
    const { api, selectedNodes, saveSnapshot } = setup([node('m', 'main', 1)], [])
    selectedNodes.value = ['m']

    api.handleBatchFlowTypeChange('branch')

    expect(saveSnapshot).not.toHaveBeenCalled()
  })

  it('批量改为分支：清空 flow_meta/main_order 并重算边类型', () => {
    const { api, vueFlowNodes, vueFlowEdges, selectedNodes, emitSortData } = setup(
      [node('m1', 'main', 1), node('m2', 'main', 2)],
      [edge('e1', 'm1', 'm2')]
    )
    selectedNodes.value = ['m1', 'm2']

    api.handleBatchFlowTypeChange('branch')

    expect(vueFlowNodes.value.map((n) => getNodeData(n).flow_type)).toEqual(['branch', 'branch'])
    expect(getNodeData(vueFlowNodes.value[0]).main_order).toBeUndefined()
    expect(vueFlowEdges.value[0].data).toMatchObject({ edge_type: 'branch' })
    expect(vueFlowEdges.value[0].sourceHandle).toBe(inferEdgeType('branch', 'branch').sourceHandle)
    expect(emitSortData).toHaveBeenCalled()
    expect(mockMessage.success).toHaveBeenCalledWith(
      `已将 2 个节点设为${FLOW_TYPE_LABEL_MAP.branch}`
    )
  })

  it('批量改为 main：清理入向语义边', () => {
    const { api, vueFlowEdges, selectedNodes } = setup(
      [node('m', 'main', 1), node('b1', 'branch'), node('b2', 'branch')],
      [edge('e1', 'm', 'b1', 'branch'), edge('e2', 'm', 'b2', 'branch')]
    )
    selectedNodes.value = ['b1', 'b2']

    api.handleBatchFlowTypeChange('main')

    expect(vueFlowEdges.value).toEqual([])
  })
})
