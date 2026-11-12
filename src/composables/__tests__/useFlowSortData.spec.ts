import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import useFlowSortData from '../useFlowSortData'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

vi.mock('@vue-flow/core', () => ({ MarkerType: { ArrowClosed: 'arrowclosed' } }))

function node(id: string, screenId: number, mainOrder?: number, flowType = 'main'): FlowEditorNode {
  return {
    id,
    position: { x: mainOrder ? (mainOrder - 1) * 280 : 0, y: 0 },
    data: {
      screen_id: screenId,
      screen_name: `页面${screenId}`,
      flow_type: flowType,
      main_order: mainOrder,
      summary: '摘要',
    },
  } as unknown as FlowEditorNode
}

function edge(
  id: string,
  source: string,
  target: string,
  data: Record<string, unknown> = { edge_type: 'normal' },
  label?: string
): FlowGraphEdge {
  return { id, source, target, label, data } as unknown as FlowGraphEdge
}

function setup(nodes: FlowEditorNode[], edges: FlowGraphEdge[]) {
  const vueFlowNodes = ref(nodes)
  const vueFlowEdges = ref(edges)
  const emit = vi.fn()
  const flowSortStore = {
    updateNodes: vi.fn(),
    updateEdges: vi.fn(),
    triggerAutoSave: vi.fn(),
  }
  const moduleInfo = ref<{ name: string; description: string } | undefined>(undefined)

  const api = useFlowSortData({
    vueFlowNodes,
    vueFlowEdges,
    emit,
    flowSortStore: flowSortStore as never,
    getNodeData: (n) => n.data as never,
    moduleInfo,
  })

  return { api, vueFlowNodes, vueFlowEdges, emit, flowSortStore, moduleInfo }
}

describe('useFlowSortData — serializeEdge', () => {
  it('端点缺失 screen_id 时返回 null', () => {
    const { api } = setup([node('a', 1)], [edge('e1', 'a', 'ghost')])

    expect(api.serializeEdge(edge('e1', 'a', 'ghost'))).toBeNull()
  })

  it('screen_id 字符串化并补默认样式与标签', () => {
    const { api } = setup([node('a', 1), node('b', 2)], [])

    const result = api.serializeEdge(edge('e1', 'a', 'b', {}))

    expect(result).toEqual({
      id: 'e1',
      source: '1',
      target: '2',
      edge_type: 'normal',
      condition: undefined,
      trigger_action: undefined,
      label: '连线',
      pre_action: undefined,
      note: undefined,
    })
  })

  it('保留边上的条件、前置动作与自定义标签', () => {
    const { api } = setup([node('a', 1), node('b', 2)], [])
    const e = edge(
      'e1',
      'a',
      'b',
      { edge_type: 'branch', condition: '点击登录', pre_action: '关闭弹窗', note: '备注' },
      '  分支线  '
    )

    expect(api.serializeEdge(e)).toMatchObject({
      edge_type: 'branch',
      condition: '点击登录',
      pre_action: '关闭弹窗',
      note: '备注',
      label: '  分支线  ',
    })
  })
})

describe('useFlowSortData — emitSortData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('序列化节点/边并同步 store 与自动保存', () => {
    const { api, emit, flowSortStore } = setup(
      [node('a', 1, 1), node('b', 2, 2)],
      [edge('e1', 'a', 'b')]
    )

    api.emitSortData()

    expect(emit).toHaveBeenCalledWith(
      'update:sort-data',
      expect.objectContaining({ mode: 'graph' })
    )
    const payload = emit.mock.calls[0][1]
    expect(payload.nodes).toHaveLength(2)
    expect(payload.nodes[0]).toMatchObject({ screen_id: 1, screen_name: '页面1' })
    expect(payload.edges).toHaveLength(1)
    expect(flowSortStore.updateNodes).toHaveBeenCalledTimes(1)
    expect(flowSortStore.updateEdges).toHaveBeenCalledTimes(1)
    expect(flowSortStore.triggerAutoSave).toHaveBeenCalledTimes(1)
  })

  it('从连线推导 main_order 并回写到节点', () => {
    const { api, vueFlowNodes } = setup([node('a', 1, 2), node('b', 2, 1)], [edge('e1', 'b', 'a')])

    api.emitSortData()

    const orderOf = (id: string) =>
      (vueFlowNodes.value.find((n) => n.id === id)?.data as { main_order?: number }).main_order
    expect(orderOf('a')).toBe(2)
    expect(orderOf('b')).toBe(1)
  })

  it('无法序列化的边被过滤掉', () => {
    const { api, emit } = setup([node('a', 1)], [edge('e1', 'a', 'ghost')])

    api.emitSortData()

    expect(emit.mock.calls[0][1].edges).toEqual([])
  })
})

describe('useFlowSortData — 提交数据与校验', () => {
  it('screen_order 按主干优先顺序从 1 连续编号', () => {
    const { api } = setup([node('b', 2, 2), node('a', 1, 1, 'branch')], [])

    const submit = api.getFlowSortSubmitData().flow_sort_data

    expect(submit.nodes.map((n) => n.screen_id)).toEqual([2, 1])
    expect(submit.nodes.map((n) => n.screen_order)).toEqual([1, 2])
    expect(submit.nodes[1]).toMatchObject({ summary: '摘要' })
  })

  it('module_info 缺省时回退空对象', () => {
    const { api, moduleInfo } = setup([node('a', 1, 1)], [])

    expect(api.getFlowSortSubmitData().flow_sort_data.module_info).toEqual({
      name: '',
      description: '',
    })

    moduleInfo.value = { name: '登录模块', description: '登录链路' }
    expect(api.getFlowSortSubmitData().flow_sort_data.module_info).toEqual({
      name: '登录模块',
      description: '登录链路',
    })
  })

  it('校验结果透传给 validateFlowData（无主干报错）', () => {
    const { api } = setup([node('a', 1, undefined, 'branch')], [])

    const result = api.getFlowValidationIssues()

    expect(result.errors).toContain('至少需要保留一个主干节点')
  })
})
