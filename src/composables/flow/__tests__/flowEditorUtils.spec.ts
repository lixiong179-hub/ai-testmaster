import { describe, it, expect, vi } from 'vitest'
import type { Edge } from '@vue-flow/core'
import {
  getNodeData,
  getMainNodesInOrder,
  getOrderedNodesForSubmit,
  normalizeMainNodeOrders,
  layoutMainNodesByOrder,
  getMainNodeCount,
  createEdgeMarker,
  normalizeEdge,
  normalizeEdges,
  validateFlowData,
  inferEdgeType,
  generateAutoEdges,
  computeUpstreamNodeIds,
  computeDownstreamNodeIds,
  computeRelatedEdgeIds,
  computeBranchChildren,
} from '../flowEditorUtils'
import { EDGE_STYLES } from '../flowEditorConstants'
import type { FlowEditorNode, FlowEdgeInput } from '../flowEditorTypes'

vi.mock('@vue-flow/core', () => ({ MarkerType: { ArrowClosed: 'arrowclosed' } }))

function node(
  id: string,
  flowType: 'main' | 'branch' | 'exception' | 'bypass',
  x: number,
  y = 0,
  mainOrder?: number
): FlowEditorNode {
  return {
    id,
    position: { x, y },
    data: { flow_type: flowType, main_order: mainOrder, screen_name: id },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): Edge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as Edge
}

describe('flowEditorUtils — 节点顺序', () => {
  it('getNodeData 直接暴露 data', () => {
    const n = node('a', 'main', 0)
    expect(getNodeData(n)).toBe(n.data)
  })

  it('无连线时按 main_order 升序，缺失排最后再按 x', () => {
    const nodes = [
      node('c', 'main', 10, 0, undefined),
      node('b', 'main', 500, 0, 1),
      node('a', 'main', 0, 0, 2),
    ]

    expect(getMainNodesInOrder(nodes).map((n) => n.id)).toEqual(['b', 'a', 'c'])
  })

  it('有连线时按主干拓扑排序（边优先于 main_order）', () => {
    const nodes = [
      node('a', 'main', 900, 0, 1),
      node('b', 'main', 0, 0, 2),
      node('c', 'main', 0, 0, 3),
    ]
    const edges = [edge('e1', 'a', 'b'), edge('e2', 'b', 'c')]

    expect(getMainNodesInOrder(nodes, edges).map((n) => n.id)).toEqual(['a', 'b', 'c'])
  })

  it('只排序主干节点，分支节点不参与；缺 main_order 的排最后', () => {
    const nodes = [node('a', 'main', 0), node('x', 'branch', 10), node('b', 'main', 300, 0, 1)]

    expect(getMainNodesInOrder(nodes).map((n) => n.id)).toEqual(['b', 'a'])
  })

  it('getOrderedNodesForSubmit：主干在前，其余按 x 再 y', () => {
    const nodes = [
      node('x1', 'branch', 500),
      node('m2', 'main', 300, 0, 2),
      node('m1', 'main', 0, 0, 1),
      node('x2', 'bypass', 100),
    ]

    expect(getOrderedNodesForSubmit(nodes).map((n) => n.id)).toEqual(['m1', 'm2', 'x2', 'x1'])
  })

  it('normalizeMainNodeOrders：主干重排 1..n，非主干移除 main_order', () => {
    const nodes = [
      node('m2', 'main', 300, 0, 9),
      node('m1', 'main', 0, 0, 9),
      { ...node('x', 'branch', 100), data: { flow_type: 'branch', main_order: 5 } } as never,
    ]

    const result = normalizeMainNodeOrders(nodes)

    expect(result[0].data).toMatchObject({ main_order: 2 })
    expect(result[1].data).toMatchObject({ main_order: 1 })
    expect(result[2].data).not.toHaveProperty('main_order')
  })

  it('layoutMainNodesByOrder：主干按 280 间距重排 x，保留 y；非主干位置不变', () => {
    const nodes = [
      node('m2', 'main', 900, 40, 2),
      node('m1', 'main', 500, 10, 1),
      node('x', 'branch', 777, 88),
    ]

    const result = layoutMainNodesByOrder(nodes)

    expect(result[0].position).toEqual({ x: 280, y: 40 })
    expect(result[1].position).toEqual({ x: 0, y: 10 })
    expect(result[2].position).toEqual({ x: 777, y: 88 })
  })

  it('getMainNodeCount 只统计主干', () => {
    expect(getMainNodeCount([node('a', 'main', 0), node('b', 'branch', 1)])).toBe(1)
  })
})

describe('flowEditorUtils — 连线样式归一', () => {
  it('createEdgeMarker 生成闭合箭头标记', () => {
    expect(createEdgeMarker('#fff')).toEqual({
      type: 'arrowclosed',
      width: 20,
      height: 20,
      color: '#fff',
    })
  })

  it('normalizeEdge：按 edge_type 取样式并生成 marker', () => {
    const result = normalizeEdge(edge('e', 'a', 'b', 'exception'))

    expect(result.type).toBe('default')
    expect(result.animated).toBe(true)
    expect(result.style).toMatchObject(EDGE_STYLES.exception)
    expect(result.markerEnd).toMatchObject({ color: EDGE_STYLES.exception.stroke })
  })

  it('normalizeEdge：normal 连线不闪烁动画', () => {
    expect(normalizeEdge(edge('e', 'a', 'b')).animated).toBe(false)
  })

  it('normalizeEdge：自定义 stroke 覆盖基础样式', () => {
    const e = { ...edge('e', 'a', 'b'), style: { stroke: '#123456' } } as unknown as Edge

    expect(normalizeEdge(e).style).toMatchObject({ stroke: '#123456' })
  })

  it('normalizeEdge：概览模式强制基础线宽且不闪烁', () => {
    const result = normalizeEdge(edge('e', 'a', 'b', 'branch'), undefined, true)

    expect(result.animated).toBe(false)
    expect(result.style).toMatchObject({ strokeWidth: EDGE_STYLES.branch.strokeWidth })
  })

  it('normalizeEdge：支持自定义样式表，未知类型回落 normal', () => {
    const styleMap = { normal: { stroke: '#000', strokeWidth: 1 } }

    expect(normalizeEdge(edge('e', 'a', 'b', 'unknown'), styleMap).style).toMatchObject({
      stroke: '#000',
    })
  })

  it('normalizeEdges 批量处理', () => {
    expect(normalizeEdges([edge('e1', 'a', 'b'), edge('e2', 'b', 'c')])).toHaveLength(2)
  })
})

describe('flowEditorUtils — 校验规则', () => {
  const baseNode = (over: Record<string, unknown> = {}) => ({
    screen_id: 1,
    screen_name: '首页',
    flow_type: 'main' as const,
    position: { x: 0, y: 0 },
    ...over,
  })

  it('无主干节点报错', () => {
    const result = validateFlowData([baseNode({ flow_type: 'branch' })], [])

    expect(result.errors).toContain('至少需要保留一个主干节点')
  })

  it('未命名页面报错', () => {
    const result = validateFlowData([baseNode({ screen_name: '   ' })], [])

    expect(result.errors.some((e) => e.includes('未命名页面'))).toBe(true)
  })

  it('坐标越界给出警告', () => {
    const result = validateFlowData([baseNode({ position: { x: 20000, y: 0 } })], [])

    expect(result.warnings.some((w) => w.includes('超出画布'))).toBe(true)
  })

  it('两点距离小于 50 判定重叠', () => {
    const result = validateFlowData(
      [
        baseNode({ screen_id: 1, screen_name: 'A' }),
        baseNode({ screen_id: 2, screen_name: 'B', position: { x: 30, y: 0 } }),
      ],
      []
    )

    expect(result.warnings.some((w) => w.includes('位置重叠'))).toBe(true)
  })

  it('多主干但无 normal 连线给出警告', () => {
    const result = validateFlowData(
      [baseNode({ screen_id: 1 }), baseNode({ screen_id: 2, position: { x: 400, y: 0 } })],
      []
    )

    expect(result.warnings.some((w) => w.includes('没有正常连线'))).toBe(true)
  })

  it('分支/异常/弹窗连线缺 condition 时按类型提示', () => {
    const nodes = [
      baseNode({ screen_id: 1 }),
      baseNode({ screen_id: 2, position: { x: 400, y: 0 } }),
    ]
    const edges: FlowEdgeInput[] = [
      { source: '1', target: '2', edge_type: 'normal', condition: '', label: '主干' },
      { source: '1', target: '2', edge_type: 'branch', condition: '  ', label: '分支线' },
      { source: '1', target: '2', edge_type: 'exception', condition: '', label: '异常线' },
      { source: '1', target: '2', edge_type: 'bypass', condition: '', label: '弹窗线' },
    ]

    const result = validateFlowData(nodes, edges)

    expect(result.warnings).toContain('分支线 缺少分支触发条件，系统将自动推断')
    expect(result.warnings).toContain('异常线 缺少异常场景，系统将自动推断')
    expect(result.warnings).toContain('弹窗线 缺少弹窗出现时机，系统将自动推断')
    expect(result.warnings.some((w) => w.startsWith('主干'))).toBe(false)
  })

  it('条件填写的分支连线不再提示', () => {
    const nodes = [
      baseNode({ screen_id: 1 }),
      baseNode({ screen_id: 2, position: { x: 400, y: 0 } }),
    ]
    const edges: FlowEdgeInput[] = [
      { source: '1', target: '2', edge_type: 'normal', condition: '', label: '主干' },
      { source: '1', target: '2', edge_type: 'branch', condition: '点击登录', label: '分支线' },
    ]

    expect(validateFlowData(nodes, edges).warnings.some((w) => w.includes('缺少'))).toBe(false)
  })
})

describe('flowEditorUtils — 自动连线与拓扑', () => {
  it('inferEdgeType：主干到主干为 normal，句柄水平', () => {
    expect(inferEdgeType('main', 'main')).toEqual({
      edgeType: 'normal',
      sourceHandle: 'source-right',
      targetHandle: 'target-left',
    })
  })

  it('inferEdgeType：目标类型决定分支/异常/弹窗及句柄方向', () => {
    expect(inferEdgeType('main', 'branch')).toMatchObject({
      edgeType: 'branch',
      sourceHandle: 'source-bottom',
      targetHandle: 'target-top',
    })
    expect(inferEdgeType('main', 'exception')).toMatchObject({
      edgeType: 'exception',
      sourceHandle: 'source-top',
      targetHandle: 'target-bottom',
    })
    expect(inferEdgeType('main', 'bypass')).toMatchObject({ edgeType: 'bypass' })
  })

  it('inferEdgeType：非主干到主干回落 normal', () => {
    expect(inferEdgeType('branch', 'main').edgeType).toBe('normal')
  })

  it('generateAutoEdges：阈值内按从左到右建边并带 auto id', () => {
    const nodes = [node('b', 'main', 200), node('a', 'main', 0)]

    const edges = generateAutoEdges(nodes, 350)

    expect(edges).toHaveLength(1)
    expect(edges[0]).toMatchObject({
      id: 'auto_a_b',
      source: 'a',
      target: 'b',
      data: { edge_type: 'normal' },
    })
  })

  it('generateAutoEdges：超出阈值不连线', () => {
    expect(generateAutoEdges([node('a', 'main', 0), node('b', 'main', 400)], 350)).toHaveLength(0)
  })

  it('generateAutoEdges：同 x 时按 y 决定方向', () => {
    const edges = generateAutoEdges([node('b', 'main', 0, 100), node('a', 'main', 0, 0)], 350)

    expect(edges[0]).toMatchObject({ source: 'a', target: 'b' })
  })

  it('上游/下游集合按有向边递归展开', () => {
    const edges = [edge('e1', 'a', 'b'), edge('e2', 'b', 'c'), edge('e3', 'c', 'd')]

    expect([...computeUpstreamNodeIds(edges, 'c')].sort()).toEqual(['a', 'b'])
    expect([...computeDownstreamNodeIds(edges, 'b')].sort()).toEqual(['c', 'd'])
  })

  it('自环边不影响上下游计算', () => {
    expect(computeUpstreamNodeIds([edge('e', 'a', 'a')], 'a').size).toBe(0)
  })

  it('computeRelatedEdgeIds 收集任一端口命中的边', () => {
    const edges = [edge('e1', 'a', 'b'), edge('e2', 'c', 'd')]

    expect([...computeRelatedEdgeIds(edges, new Set(['b']))]).toEqual(['e1'])
  })

  it('computeBranchChildren 只取分支/异常/弹窗边', () => {
    const nodes = [node('a', 'main', 0), node('b', 'branch', 100), node('c', 'main', 300)]
    const edges = [
      edge('e1', 'a', 'b', 'branch'),
      edge('e2', 'a', 'c', 'normal'),
      edge('e3', 'a', 'ghost', 'exception'),
    ]

    const result = computeBranchChildren(nodes, edges, 'a')

    expect(result).toHaveLength(1)
    expect(result[0].node.id).toBe('b')
    expect(result[0].edge.id).toBe('e1')
  })
})
