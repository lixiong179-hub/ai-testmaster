import { describe, it, expect } from 'vitest'
import {
  layeredAutoLayout,
  compactAutoLayout,
  typeLayeredAutoLayout,
  focusedPathAutoLayout,
  swimlaneAutoLayout,
  autoLayoutByMode,
  DEFAULT_LAYOUT_OPTIONS,
  COMPACT_OPTIONS,
  SWIMLANE_OPTIONS,
  LAYOUT_MODE_LABELS,
} from '../useFlowLayout'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

function node(
  id: string,
  flowType: 'main' | 'branch' | 'exception' | 'bypass',
  mainOrder?: number,
  flowMeta?: Record<string, unknown>
): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { flow_type: flowType, main_order: mainOrder, flow_meta: flowMeta },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): FlowGraphEdge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as FlowGraphEdge
}

function pos(nodes: FlowEditorNode[], id: string) {
  return nodes.find((n) => n.id === id)?.position
}

describe('useFlowLayout — 标准布局', () => {
  it('主干按顺序等距排布在主线上', () => {
    const nodes = [node('a', 'main', 1), node('b', 'main', 2), node('c', 'main', 3)]

    const out = layeredAutoLayout(nodes, [])

    expect(pos(out, 'a')).toEqual({ x: 0, y: 0 })
    expect(pos(out, 'b')).toEqual({ x: DEFAULT_LAYOUT_OPTIONS.mainGapX, y: 0 })
    expect(pos(out, 'c')).toEqual({ x: DEFAULT_LAYOUT_OPTIONS.mainGapX * 2, y: 0 })
  })

  it('分支子节点挂在主干下方，超出每列上限后换列', () => {
    const nodes = [
      node('m', 'main', 1),
      node('b1', 'branch'),
      node('b2', 'branch'),
      node('b3', 'branch'),
      node('b4', 'branch'),
      node('b5', 'branch'),
    ]
    const edges = ['b1', 'b2', 'b3', 'b4', 'b5'].map((id, i) => edge(`e${i}`, 'm', id, 'branch'))

    const out = layeredAutoLayout(nodes, edges)

    // 5 个子节点、每列最多 4 个 -> 2 列
    expect(pos(out, 'b1')).toEqual({ x: 0, y: 200 })
    expect(pos(out, 'b2')).toEqual({ x: 280, y: 200 })
    // 第 5 个回绕到第 1 列的第 3 行
    expect(pos(out, 'b5')).toEqual({ x: 0, y: 200 + 2 * 200 })
  })

  it('异常/弹窗子节点排在主干上方', () => {
    const nodes = [node('m', 'main', 1), node('ex', 'exception')]

    const out = layeredAutoLayout(nodes, [edge('e1', 'm', 'ex', 'exception')])

    expect(pos(out, 'ex')).toEqual({ x: 0, y: 0 - 200 })
  })

  it('孙节点按层级缩进', () => {
    const nodes = [node('m', 'main', 1), node('b', 'branch'), node('g', 'branch')]
    const edges = [edge('e1', 'm', 'b', 'branch'), edge('e2', 'b', 'g', 'branch')]

    const out = layeredAutoLayout(nodes, edges)

    expect(pos(out, 'b')).toEqual({ x: 0, y: 200 })
    expect(pos(out, 'g')).toEqual({ x: 0 + 1 * DEFAULT_LAYOUT_OPTIONS.nestedIndentX, y: 200 + 200 })
  })

  it('flow_meta.parent_node_id 优先于连线推导的父节点', () => {
    const nodes = [
      node('m1', 'main', 1),
      node('m2', 'main', 2),
      node('x', 'branch', undefined, { parent_node_id: 'm1' }),
    ]
    const edges = [edge('e1', 'm2', 'x', 'normal')]

    const out = layeredAutoLayout(nodes, edges)

    expect(pos(out, 'x')).toEqual({ x: 0, y: 200 })
  })

  it('语义边优先于普通边作为父节点来源', () => {
    const nodes = [node('m1', 'main', 1), node('m2', 'main', 2), node('x', 'branch')]
    // 普通边 m1 -> x 先出现，语义边 m2 -> x 应覆盖
    const edges = [edge('e1', 'm1', 'x', 'normal'), edge('e2', 'm2', 'x', 'branch')]

    const out = layeredAutoLayout(nodes, edges)

    expect(pos(out, 'x')).toEqual({ x: 280, y: 200 })
  })

  it('无父节点的孤儿节点排在主干右侧并纵向堆叠', () => {
    const nodes = [node('m', 'main', 1), node('o1', 'branch'), node('o2', 'branch')]

    const out = layeredAutoLayout(nodes, [])

    const orphanX = 0 + DEFAULT_LAYOUT_OPTIONS.mainGapX * 2
    expect(pos(out, 'o1')).toEqual({ x: orphanX, y: 0 })
    expect(pos(out, 'o2')).toEqual({ x: orphanX, y: 200 })
  })

  it('支持自定义间距参数', () => {
    const nodes = [node('a', 'main', 1), node('b', 'main', 2)]

    const out = layeredAutoLayout(nodes, [], { mainGapX: 100, mainStartY: 50 })

    expect(pos(out, 'a')).toEqual({ x: 0, y: 50 })
    expect(pos(out, 'b')).toEqual({ x: 100, y: 50 })
  })

  it('节点顺序与入参保持一致（仅改坐标）', () => {
    const nodes = [node('b', 'main', 2), node('a', 'main', 1)]

    const out = layeredAutoLayout(nodes, [])

    expect(out.map((n) => n.id)).toEqual(['b', 'a'])
  })
})

describe('useFlowLayout — 紧凑 / 按类型分层', () => {
  it('紧凑布局使用更小的间距', () => {
    const nodes = [node('a', 'main', 1), node('b', 'main', 2), node('c', 'branch')]
    const edges = [edge('e1', 'a', 'c', 'branch')]

    const out = compactAutoLayout(nodes, edges)

    expect(pos(out, 'b')).toEqual({ x: COMPACT_OPTIONS.mainGapX, y: 0 })
    expect(pos(out, 'c')).toEqual({ x: 0, y: COMPACT_OPTIONS.branchStartY })
  })

  it('按类型分层：分支在下方、异常与弹窗在上方', () => {
    const nodes = [
      node('m', 'main', 1),
      node('b', 'branch'),
      node('ex', 'exception'),
      node('by', 'bypass'),
      node('o', 'branch'),
    ]
    const edges = [
      edge('e1', 'm', 'b', 'branch'),
      edge('e2', 'm', 'ex', 'exception'),
      edge('e3', 'm', 'by', 'bypass'),
    ]

    const out = typeLayeredAutoLayout(nodes, edges)

    expect(pos(out, 'm')).toEqual({ x: 0, y: 0 })
    expect(pos(out, 'b')).toEqual({ x: 0, y: 200 })
    expect(pos(out, 'ex')).toEqual({ x: 0, y: -200 })
    expect(pos(out, 'by')).toEqual({ x: 280, y: -200 })
    // 无连线的分支节点仍先落在「分支层」，孤儿处理只兜底未被定位的节点
    expect(pos(out, 'o')).toEqual({ x: 280, y: 200 })
  })
})

describe('useFlowLayout — 聚焦路径 / 泳道', () => {
  it('未聚焦时退回标准布局', () => {
    const nodes = [node('a', 'main', 1), node('b', 'main', 2)]

    expect(focusedPathAutoLayout(nodes, [], null)).toEqual(layeredAutoLayout(nodes, []))
  })

  it('聚焦后仅整理路径节点，非路径节点位置不变', () => {
    const nodes = [node('a', 'main', 1), node('b', 'main', 2), node('c', 'branch')]
    nodes[0].position = { x: -100, y: -100 }
    nodes[1].position = { x: -100, y: -100 }
    nodes[2].position = { x: 999, y: 999 }
    const edges = [edge('e1', 'a', 'b', 'normal')]

    const out = focusedPathAutoLayout(nodes, edges, 'a')

    expect(pos(out, 'a')).toEqual({ x: 0, y: 0 })
    expect(pos(out, 'b')).toEqual({ x: 280, y: 0 })
    expect(pos(out, 'c')).toEqual({ x: 999, y: 999 })
  })

  it('泳道布局按每行 6 个主干预换行', () => {
    const nodes = Array.from({ length: 7 }, (_, i) => node(`m${i}`, 'main', i + 1))

    const out = swimlaneAutoLayout(nodes, [])

    const rowGapY =
      (SWIMLANE_OPTIONS.branchStartY as number) +
      (SWIMLANE_OPTIONS.branchGapY as number) * 2 +
      (SWIMLANE_OPTIONS.typeGapY as number)
    expect(pos(out, 'm0')).toEqual({ x: 0, y: 0 })
    expect(pos(out, 'm5')).toEqual({ x: 5 * (SWIMLANE_OPTIONS.mainGapX as number), y: 0 })
    expect(pos(out, 'm6')).toEqual({ x: 0, y: rowGapY })
  })

  it('泳道布局分支在下方、异常在上方', () => {
    const nodes = [node('m', 'main', 1), node('b', 'branch'), node('ex', 'exception')]
    const edges = [edge('e1', 'm', 'b', 'branch'), edge('e2', 'm', 'ex', 'exception')]

    const out = swimlaneAutoLayout(nodes, edges)

    expect(pos(out, 'b')).toEqual({ x: 0, y: 180 })
    expect(pos(out, 'ex')).toEqual({ x: 0, y: -180 })
  })
})

describe('useFlowLayout — 模式分发', () => {
  const nodes = [node('a', 'main', 1), node('b', 'main', 2)]
  const edges: FlowGraphEdge[] = []

  it.each([
    ['standard', layeredAutoLayout],
    ['compact', compactAutoLayout],
    ['type-layered', typeLayeredAutoLayout],
    ['swimlane', swimlaneAutoLayout],
  ] as const)('%s 分发到对应实现', (mode, fn) => {
    expect(autoLayoutByMode(mode, nodes, edges)).toEqual(fn(nodes, edges))
  })

  it('focused-path 透传聚焦节点', () => {
    expect(autoLayoutByMode('focused-path', nodes, edges, 'b')).toEqual(
      focusedPathAutoLayout(nodes, edges, 'b')
    )
  })

  it('未知模式回退标准布局', () => {
    expect(autoLayoutByMode('unknown' as never, nodes, edges)).toEqual(
      layeredAutoLayout(nodes, edges)
    )
  })

  it('布局模式文案覆盖五种模式', () => {
    expect(Object.keys(LAYOUT_MODE_LABELS)).toEqual([
      'standard',
      'compact',
      'type-layered',
      'focused-path',
      'swimlane',
    ])
  })
})
