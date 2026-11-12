import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { useFlowMainOrder } from '../useFlowMainOrder'
import type { FlowEditorNode, FlowGraphEdge } from '../useFlowEditor'

const { mockMessage } = vi.hoisted(() => ({
  mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('element-plus', () => ({ ElMessage: mockMessage }))
vi.mock('@/composables/useFlowEditor', () => ({
  getMainNodeCount: (nodes: Array<{ data?: { flow_type?: string } }>) =>
    nodes.filter((n) => n.data?.flow_type === 'main').length,
  layoutMainNodesByOrder: (nodes: unknown[]) => nodes,
}))

function node(id: string, flowType: 'main' | 'branch', mainOrder?: number): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { flow_type: flowType, main_order: mainOrder },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): FlowGraphEdge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as FlowGraphEdge
}

function setup() {
  const vueFlowNodes = ref<FlowEditorNode[]>([
    node('m1', 'main', 1),
    node('m2', 'main', 2),
    node('x1', 'branch'),
  ])
  const vueFlowEdges = ref<FlowGraphEdge[]>([
    edge('e1', 'm1', 'm2'),
    edge('e2', 'm1', 'x1', 'branch'),
  ])
  const selectedNodes = ref<string[]>([])
  const focusedNodeId = ref<string | null>(null)
  const collapsedParentNodeIds = ref<string[]>([])
  const emitSortData = vi.fn()
  const saveSnapshot = vi.fn()
  const isProgrammaticEdgeChange = ref(false)

  const api = useFlowMainOrder({
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    focusedNodeId,
    collapsedParentNodeIds,
    emitSortData,
    saveSnapshot,
    getNodeData: (n) => n.data as never,
    getMainNodesInOrder: (nodes) =>
      [...nodes]
        .filter((n) => (n.data as { flow_type?: string }).flow_type === 'main')
        .sort(
          (a, b) =>
            ((a.data as { main_order?: number }).main_order ?? Number.MAX_SAFE_INTEGER) -
            ((b.data as { main_order?: number }).main_order ?? Number.MAX_SAFE_INTEGER)
        ),
    normalizeMainNodeOrders: (nodes) => nodes,
    applyAllEdgeStyles: (edges) => edges,
    isProgrammaticEdgeChange,
  })

  return {
    api,
    vueFlowNodes,
    vueFlowEdges,
    selectedNodes,
    focusedNodeId,
    collapsedParentNodeIds,
    emitSortData,
    saveSnapshot,
    isProgrammaticEdgeChange,
  }
}

describe('useFlowMainOrder — 选中判定', () => {
  it('仅当恰好选中一个主干节点时返回其 ID', () => {
    const { api, selectedNodes } = setup()

    expect(api.getSelectedMainNodeId()).toBeNull()

    selectedNodes.value = ['m1', 'm2']
    expect(api.getSelectedMainNodeId()).toBeNull()

    selectedNodes.value = ['x1']
    expect(api.getSelectedMainNodeId()).toBeNull()

    selectedNodes.value = ['m2']
    expect(api.getSelectedMainNodeId()).toBe('m2')
  })

  it('getSelectedMainOrder 取 main_order，缺失返回 null', () => {
    const { api, selectedNodes } = setup()

    selectedNodes.value = ['m1']
    expect(api.getSelectedMainOrder()).toBe(1)

    selectedNodes.value = ['x1']
    expect(api.getSelectedMainOrder()).toBeNull()
  })

  it('canMoveMainBackward 要求 order > 1', () => {
    const { api, selectedNodes } = setup()

    selectedNodes.value = ['m1']
    expect(api.canMoveMainBackward()).toBe(false)

    selectedNodes.value = ['m2']
    expect(api.canMoveMainBackward()).toBe(true)

    selectedNodes.value = []
    expect(api.canMoveMainBackward()).toBe(false)
  })

  it('canMoveMainForward 要求 order < 主干总数', () => {
    const { api, selectedNodes } = setup()

    selectedNodes.value = ['m1']
    expect(api.canMoveMainForward()).toBe(true)

    selectedNodes.value = ['m2']
    expect(api.canMoveMainForward()).toBe(false)

    selectedNodes.value = []
    expect(api.canMoveMainForward()).toBe(false)
  })
})

describe('useFlowMainOrder — 删除选中节点', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('无选中时为空操作', () => {
    const { api, saveSnapshot } = setup()

    api.handleDeleteSelected()

    expect(saveSnapshot).not.toHaveBeenCalled()
    expect(mockMessage.success).not.toHaveBeenCalled()
  })

  it('删除节点及其关联边，并清理焦点/折叠/选中态', () => {
    const {
      api,
      vueFlowNodes,
      vueFlowEdges,
      selectedNodes,
      focusedNodeId,
      collapsedParentNodeIds,
      emitSortData,
      saveSnapshot,
      isProgrammaticEdgeChange,
    } = setup()
    selectedNodes.value = ['m1']
    focusedNodeId.value = 'm1'
    collapsedParentNodeIds.value = ['m1', 'm2']

    api.handleDeleteSelected()

    expect(saveSnapshot).toHaveBeenCalledTimes(1)
    expect(isProgrammaticEdgeChange.value).toBe(true)
    expect(vueFlowNodes.value.map((n) => n.id)).toEqual(['m2', 'x1'])
    expect(vueFlowEdges.value.map((e) => e.id)).toEqual([])
    expect(collapsedParentNodeIds.value).toEqual(['m2'])
    expect(focusedNodeId.value).toBeNull()
    expect(selectedNodes.value).toEqual([])
    expect(emitSortData).toHaveBeenCalledTimes(1)
    expect(mockMessage.success).toHaveBeenCalledWith('已删除 1 个节点')
  })

  it('只删除非主干节点时保留主干连线', () => {
    const { api, vueFlowEdges, selectedNodes } = setup()
    selectedNodes.value = ['x1']

    api.handleDeleteSelected()

    expect(vueFlowEdges.value.map((e) => e.id)).toEqual(['e1'])
  })
})

describe('useFlowMainOrder — 主干前移/后移', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('非主干或未选中时不动作', () => {
    const { api, selectedNodes, saveSnapshot } = setup()

    api.moveSelectedMainNode(-1)
    expect(saveSnapshot).not.toHaveBeenCalled()

    selectedNodes.value = ['x1']
    api.moveSelectedMainNode(1)
    expect(saveSnapshot).not.toHaveBeenCalled()
  })

  it('边界处不动作（首节点前移/末节点后移）', () => {
    const { api, selectedNodes, saveSnapshot } = setup()

    selectedNodes.value = ['m1']
    api.moveSelectedMainNode(-1)
    expect(saveSnapshot).not.toHaveBeenCalled()

    selectedNodes.value = ['m2']
    api.moveSelectedMainNode(1)
    expect(saveSnapshot).not.toHaveBeenCalled()
  })

  it('后移末节点前的节点：交换顺序并重建主干连线', () => {
    const { api, vueFlowNodes, vueFlowEdges, selectedNodes, emitSortData, saveSnapshot } = setup()
    selectedNodes.value = ['m1']

    api.moveSelectedMainNode(1)

    expect(saveSnapshot).toHaveBeenCalledTimes(1)
    expect(emitSortData).toHaveBeenCalledTimes(1)
    // 数组顺序不变，交换体现为 main_order 重编号
    const orderOf = (id: string) =>
      (vueFlowNodes.value.find((n) => n.id === id)?.data as { main_order?: number }).main_order
    expect(orderOf('m2')).toBe(1)
    expect(orderOf('m1')).toBe(2)

    const mainEdge = vueFlowEdges.value.find((e) => e.source === 'm2' && e.target === 'm1')
    expect(mainEdge).toBeDefined()
    // 非主干边保留
    expect(vueFlowEdges.value.some((e) => e.id === 'e2')).toBe(true)
  })

  it('前移末节点：顺序交换并保持主干边数量', () => {
    const { api, vueFlowEdges, selectedNodes } = setup()
    selectedNodes.value = ['m2']

    api.moveSelectedMainNode(-1)

    const mainEdges = vueFlowEdges.value.filter(
      (e) => e.data?.edge_type === 'normal' && e.target !== 'x1'
    )
    expect(mainEdges).toHaveLength(1)
    expect(mainEdges[0]).toMatchObject({ source: 'm2', target: 'm1' })
  })
})
