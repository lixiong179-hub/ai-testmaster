import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { useFlowEdgeOps } from '../useFlowEdgeOps'
import {
  getNodeData,
  inferEdgeType,
  normalizeEdges,
  EDGE_STYLES,
} from '@/composables/useFlowEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

const { mockMessage } = vi.hoisted(() => ({
  mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@vue-flow/core', () => ({ MarkerType: { ArrowClosed: 'arrowclosed' } }))
vi.mock('element-plus', () => ({
  ElMessage: mockMessage,
  ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
}))

function node(id: string, flowType: 'main' | 'branch' | 'exception' | 'bypass' = 'main') {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { flow_type: flowType },
  } as unknown as FlowEditorNode
}

function edge(
  id: string,
  source: string,
  target: string,
  data: Record<string, unknown> = { edge_type: 'normal' }
): FlowGraphEdge {
  return { id, source, target, data } as unknown as FlowGraphEdge
}

function setup() {
  const vueFlowNodes = ref<FlowEditorNode[]>([node('a'), node('b'), node('c')])
  const vueFlowEdges = ref<FlowGraphEdge[]>([edge('e1', 'a', 'b')])
  const historyStack = ref<Array<{ nodes: FlowEditorNode[]; edges: FlowGraphEdge[] }>>([])
  const isOverviewMode = ref(false)
  const isProgrammaticEdgeChange = ref(false)
  const emitSortData = vi.fn()
  const saveSnapshot = vi.fn()
  const applyAllEdgeStyles = vi.fn((edges: FlowGraphEdge[]) => edges)
  const currentEdgeStyles = ref(EDGE_STYLES)

  const api = useFlowEdgeOps({
    vueFlowNodes,
    vueFlowEdges,
    emitSortData,
    saveSnapshot,
    historyStack,
    applyAllEdgeStyles,
    currentEdgeStyles,
    isOverviewMode,
    normalizeEdges: (edges, styleMap, overview) =>
      normalizeEdges(edges, styleMap, overview) as unknown as FlowGraphEdge[],
    isProgrammaticEdgeChange,
  })

  return {
    api,
    vueFlowNodes,
    vueFlowEdges,
    historyStack,
    isProgrammaticEdgeChange,
    emitSortData,
    saveSnapshot,
    applyAllEdgeStyles,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useFlowEdgeOps — 新建连接', () => {
  it('带 handle 时直接开弹窗并暂存连接', () => {
    const { api } = setup()

    api.onConnect({ source: 'a', target: 'c', sourceHandle: 's', targetHandle: 't' } as never)

    expect(api.conditionDialogVisible.value).toBe(true)
    expect(api.currentConnection.value).toEqual({
      source: 'a',
      target: 'c',
      sourceHandle: 's',
      targetHandle: 't',
    })
    expect(api.currentEdgeForm.value).toBeNull()
  })

  it('缺 handle 时按节点类型推断', () => {
    const { api, vueFlowNodes } = setup()
    vueFlowNodes.value[2] = node('c', 'exception')

    api.onConnect({ source: 'a', target: 'c' } as never)

    expect(api.currentConnection.value).toMatchObject({
      sourceHandle: 'source-top',
      targetHandle: 'target-bottom',
    })
  })

  it('节点不存在时回退水平 handle', () => {
    const { api } = setup()

    api.onConnect({ source: 'ghost1', target: 'ghost2' } as never)

    expect(api.currentConnection.value).toMatchObject({
      sourceHandle: 'source-right',
      targetHandle: 'target-left',
    })
  })
})

describe('useFlowEdgeOps — 编辑与删除', () => {
  it('编辑边时回填表单并调用关闭 tooltip 回调', () => {
    const { api } = setup()
    const closeTooltip = vi.fn()

    api.handleEditEdge(
      edge('e1', 'a', 'b', {
        edge_type: 'branch',
        condition: '点击',
        trigger_action: 'go',
        pre_action: 'close',
        note: '备注',
      }),
      closeTooltip
    )

    expect(closeTooltip).toHaveBeenCalled()
    expect(api.editingEdgeId.value).toBe('e1')
    expect(api.currentEdgeForm.value).toEqual({
      edge_type: 'branch',
      condition: '点击',
      trigger_action: 'go',
      pre_action: 'close',
      note: '备注',
    })
    expect(api.conditionDialogVisible.value).toBe(true)
  })

  it('删除边：保存快照并提示，程序化标志被边 watch 一次性消费', () => {
    const { api, vueFlowEdges, emitSortData, saveSnapshot, isProgrammaticEdgeChange } = setup()

    api.handleDeleteEdge(edge('e1', 'a', 'b'))

    expect(saveSnapshot).toHaveBeenCalledTimes(1)
    // 删除时置真的标志会被 sync watch 立即消费，避免后续误判为用户删除
    expect(isProgrammaticEdgeChange.value).toBe(false)
    expect(vueFlowEdges.value).toEqual([])
    expect(emitSortData).toHaveBeenCalledTimes(1)
    expect(mockMessage.success).toHaveBeenCalledWith('已删除连线')
  })
})

describe('useFlowEdgeOps — 条件确认', () => {
  const confirmData = {
    edge_type: 'branch',
    condition: '点击登录',
    trigger_action: 'submit',
    pre_action: 'close',
    note: '备注',
    label: '分支线',
  }

  it('编辑模式更新目标边并提示', () => {
    const { api, vueFlowEdges, applyAllEdgeStyles } = setup()
    api.handleEditEdge(edge('e1', 'a', 'b'))

    api.onEdgeConditionConfirm(confirmData)

    expect(applyAllEdgeStyles).toHaveBeenCalled()
    expect(vueFlowEdges.value[0]).toMatchObject({
      label: '分支线',
      data: {
        edge_type: 'branch',
        condition: '点击登录',
        trigger_action: 'submit',
        pre_action: 'close',
        note: '备注',
      },
    })
    expect(mockMessage.success).toHaveBeenCalledWith('连线属性已更新')
    expect(api.conditionDialogVisible.value).toBe(false)
  })

  it('新建模式：自连被拦截', () => {
    const { api, vueFlowEdges } = setup()
    api.onConnect({ source: 'a', target: 'a' } as never)

    api.onEdgeConditionConfirm(confirmData)

    expect(mockMessage.warning).toHaveBeenCalledWith('不能连接到自身')
    expect(vueFlowEdges.value).toHaveLength(1)
  })

  it('新建模式：重复连线被拦截', () => {
    const { api, vueFlowEdges } = setup()
    api.onConnect({ source: 'a', target: 'b' } as never)

    api.onEdgeConditionConfirm(confirmData)

    expect(mockMessage.warning).toHaveBeenCalledWith('已存在相同连线')
    expect(vueFlowEdges.value).toHaveLength(1)
  })

  it('新建模式：正常追加并带样式归一', () => {
    const { api, vueFlowEdges, emitSortData } = setup()
    api.onConnect({ source: 'b', target: 'c' } as never)

    api.onEdgeConditionConfirm(confirmData)

    expect(vueFlowEdges.value).toHaveLength(2)
    expect(vueFlowEdges.value[1]).toMatchObject({
      source: 'b',
      target: 'c',
      animated: true,
      data: expect.objectContaining({ edge_type: 'branch', condition: '点击登录' }),
    })
    expect(vueFlowEdges.value[1].markerEnd).toBeDefined()
    expect(emitSortData).toHaveBeenCalled()
  })

  it('自连被拦截后关闭弹窗并清空连接（可继续重新连线）', () => {
    const { api } = setup()
    api.onConnect({ source: 'a', target: 'a' } as never)

    api.onEdgeConditionConfirm({
      edge_type: 'normal',
      condition: '',
      trigger_action: '',
      pre_action: '',
      note: '',
      label: '连线',
    })

    expect(api.conditionDialogVisible.value).toBe(false)
    expect(api.currentConnection.value).toBeNull()
  })
})

describe('useFlowEdgeOps — 变更与建议', () => {
  it('删除边时优先复用「删除前快照」写入历史栈', () => {
    const { api, vueFlowEdges, historyStack, saveSnapshot } = setup()
    vueFlowEdges.value = [edge('e1', 'a', 'b')]
    vueFlowEdges.value = [] // 触发 sync watch 捕获快照
    saveSnapshot.mockClear()

    api.onEdgesChange([{ type: 'remove', id: 'e1' }] as never)

    expect(historyStack.value).toHaveLength(1)
    expect(saveSnapshot).not.toHaveBeenCalled()
  })

  it('无删除前快照时退回 saveSnapshot', () => {
    const { api, saveSnapshot } = setup()

    api.onEdgesChange([{ type: 'remove', id: 'e1' }] as never)

    expect(saveSnapshot).toHaveBeenCalledTimes(1)
  })

  it('仅非删除变更时不写快照', () => {
    const { api, saveSnapshot, historyStack } = setup()

    api.onEdgesChange([{ type: 'select', id: 'e1' }] as never)

    expect(saveSnapshot).not.toHaveBeenCalled()
    expect(historyStack.value).toHaveLength(0)
  })

  it('程序化变更不会写入删除前快照', () => {
    const { api, vueFlowEdges, historyStack, isProgrammaticEdgeChange } = setup()
    isProgrammaticEdgeChange.value = true
    vueFlowEdges.value = []

    api.onEdgesChange([] as never)

    expect(historyStack.value).toHaveLength(0)
    expect(isProgrammaticEdgeChange.value).toBe(false)
  })

  it('未接受任何建议时不动作', () => {
    const { api, vueFlowEdges, saveSnapshot } = setup()

    api.handleEdgeSuggestionsConfirmed([])

    expect(saveSnapshot).not.toHaveBeenCalled()
    expect(vueFlowEdges.value).toHaveLength(1)
  })

  it('接受建议后按目标类型推断边型并提示', () => {
    const { api, vueFlowNodes, vueFlowEdges } = setup()
    vueFlowNodes.value[2] = node('c', 'exception')

    api.handleEdgeSuggestionsConfirmed([{ sourceNodeId: 'a', targetNodeId: 'c' }] as never)

    const created = vueFlowEdges.value.find((e) => e.target === 'c')
    expect(created?.data?.edge_type).toBe('exception')
    expect(created?.sourceHandle).toBe(inferEdgeType('main', 'exception').sourceHandle)
    expect(mockMessage.success).toHaveBeenCalledWith('已应用 1 条建议连线')
  })

  it('getNodeData 与推断保持一致（类型契约）', () => {
    const { vueFlowNodes } = setup()

    expect(getNodeData(vueFlowNodes.value[0]).flow_type).toBe('main')
  })
})
