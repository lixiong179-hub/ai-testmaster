import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useFlowGroupBackground, groupPadding } from '../useFlowGroupBackground'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

const { mockViewport } = vi.hoisted(() => ({ mockViewport: { value: { x: 10, y: 20, zoom: 1 } } }))

vi.mock('@vue-flow/core', () => ({
  MarkerType: { ArrowClosed: 'arrowclosed' },
  useVueFlow: () => ({ viewport: ref(mockViewport.value) }),
}))

function node(
  id: string,
  flowType: 'main' | 'branch' | 'exception' | 'bypass',
  x = 0,
  y = 0,
  hidden = false
): FlowEditorNode {
  return {
    id,
    hidden,
    position: { x, y },
    data: { flow_type: flowType, screen_name: `页面${id}` },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): FlowGraphEdge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as FlowGraphEdge
}

function setup(nodes: FlowEditorNode[], edges: FlowGraphEdge[] = []) {
  const vueFlowNodes = ref(nodes)
  const vueFlowEdges = ref(edges)

  const api = useFlowGroupBackground({
    vueFlowNodes,
    vueFlowEdges,
    getNodeData: (n) => n.data as never,
  })

  return { api, vueFlowNodes, vueFlowEdges }
}

describe('useFlowGroupBackground — 分组边界', () => {
  it('空画布无分组', () => {
    const { api } = setup([])

    expect(api.nodeGroups.value).toEqual([])
  })

  it('关闭背景开关后不产生分组', () => {
    const { api } = setup([node('1', 'main')])
    api.showGroupBackground.value = false

    expect(api.nodeGroups.value).toEqual([])
  })

  it('单个主干节点按卡片尺寸圈定边界并带模块标题', () => {
    const { api } = setup([node('1', 'main', 100, 50)])

    const [group] = api.nodeGroups.value
    expect(group).toMatchObject({ id: '1', label: '页面1 模块' })
    expect(group.bounds).toEqual({ x: 100, y: 50, width: 220, height: 200 })
  })

  it('主干节点连同分支子节点合并到同一分组，边界取并集', () => {
    const { api } = setup(
      [node('1', 'main', 0, 0), node('b1', 'branch', 400, 300)],
      [edge('e1', '1', 'b1', 'branch')]
    )

    const [group] = api.nodeGroups.value
    expect(group.id).toBe('1')
    expect(group.bounds).toEqual({ x: 0, y: 0, width: 620, height: 500 })
  })

  it('未归属的分支节点进入「未分组」组', () => {
    const { api } = setup([node('1', 'main'), node('x', 'branch', 600, 0)])

    const orphan = api.nodeGroups.value.find((g) => g.id === '__orphans__')
    expect(orphan).toMatchObject({ label: '未分组' })
    expect(orphan?.bounds.x).toBe(600)
  })

  it('隐藏节点不参与分组', () => {
    const { api } = setup([node('1', 'main'), node('2', 'main', 500, 0, true)])

    expect(api.nodeGroups.value.map((g) => g.id)).toEqual(['1'])
  })

  it('分支节点颜色取 branch 配色', () => {
    const { api } = setup([node('x', 'branch')])

    const [group] = api.nodeGroups.value
    expect(group.color).toBe('rgba(103, 194, 58, 0.08)')
  })
})

describe('useFlowGroupBackground — 子节点映射与视口', () => {
  it('branchChildrenMap 只收分支/异常/弹窗边且目标存在', () => {
    const { api } = setup(
      [node('1', 'main'), node('b', 'branch'), node('e', 'exception')],
      [
        edge('e1', '1', 'b', 'branch'),
        edge('e2', '1', 'e', 'exception'),
        edge('e3', '1', 'ghost', 'bypass'),
        edge('e4', '1', 'b', 'normal'),
      ]
    )

    const children = api.branchChildrenMap.value.get('1') ?? []
    expect(children.map((c) => c.node.id)).toEqual(['b', 'e'])
    expect(children[0].edge.id).toBe('e1')
  })

  it('svgViewBox 跟随画布视口偏移', () => {
    const { api } = setup([node('1', 'main')])

    expect(api.svgViewBox.value).toEqual({ x: 10, y: 20 })
  })

  it('导出分组内边距常量', () => {
    expect(groupPadding).toBe(20)
  })
})
