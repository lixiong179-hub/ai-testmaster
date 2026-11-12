import { describe, it, expect } from 'vitest'
import { computeFlowStats, deriveStatsIssues } from '../useFlowStats'
import type { FlowEditorNode, FlowGraphEdge } from '../useFlowEditor'

function node(id: string, flowType: 'main' | 'branch' | 'exception' | 'bypass'): FlowEditorNode {
  return { id, data: { flow_type: flowType } } as unknown as FlowEditorNode
}

function edge(
  id: string,
  source: string,
  target: string,
  edgeType: 'normal' | 'branch' | 'exception' | 'bypass' = 'normal',
  condition = ''
): FlowGraphEdge {
  return {
    id,
    source,
    target,
    data: { edge_type: edgeType, condition },
  } as unknown as FlowGraphEdge
}

describe('computeFlowStats — 基础统计', () => {
  it('空输入返回全 0 且评分为 0', () => {
    const stats = computeFlowStats([], [])

    expect(stats.totalNodes).toBe(0)
    expect(stats.totalEdges).toBe(0)
    expect(stats.completenessScore).toBe(0)
  })

  it('按 flow_type / edge_type 分类计数', () => {
    const stats = computeFlowStats(
      [node('a', 'main'), node('b', 'branch'), node('c', 'exception'), node('d', 'bypass')],
      [
        edge('e1', 'a', 'b', 'normal'),
        edge('e2', 'a', 'b', 'branch', '条件'),
        edge('e3', 'a', 'c', 'exception', '异常'),
        edge('e4', 'a', 'd', 'bypass', '弹窗'),
      ]
    )

    expect(stats).toMatchObject({
      totalNodes: 4,
      mainNodes: 1,
      branchNodes: 1,
      exceptionNodes: 1,
      bypassNodes: 1,
      totalEdges: 4,
      normalEdges: 1,
      branchEdges: 1,
      exceptionEdges: 1,
      bypassEdges: 1,
      orphanNodes: 0,
      missingConditionEdges: 0,
    })
  })

  it('缺少 flow_type 的节点按 main 计', () => {
    const stats = computeFlowStats([{ id: 'x', data: {} } as unknown as FlowEditorNode], [])

    expect(stats.mainNodes).toBe(1)
  })

  it('孤立节点 = 未出现在任何连线端点的节点', () => {
    const stats = computeFlowStats(
      [node('a', 'main'), node('b', 'main'), node('c', 'branch')],
      [edge('e1', 'a', 'b')]
    )

    expect(stats.orphanNodes).toBe(1)
  })

  it('非 normal 连线且 condition 为空/空白计入缺条件', () => {
    const stats = computeFlowStats(
      [node('a', 'main'), node('b', 'branch')],
      [
        edge('e1', 'a', 'b', 'normal', ''),
        edge('e2', 'a', 'b', 'branch', '   '),
        edge('e3', 'a', 'b', 'exception', '异常'),
      ]
    )

    expect(stats.missingConditionEdges).toBe(1)
  })
})

describe('computeFlowStats — 完整度评分', () => {
  it('主干连通且无缺陷为 100', () => {
    const stats = computeFlowStats([node('a', 'main'), node('b', 'main')], [edge('e1', 'a', 'b')])

    expect(stats.completenessScore).toBe(100)
  })

  it('无主干扣 35 分（叠加孤立节点扣分）', () => {
    const stats = computeFlowStats([node('a', 'branch')], [])

    // 100 - 35（无主干） - 5（1 个孤立节点）
    expect(stats.completenessScore).toBe(60)
  })

  it('多主干但无 normal 连线扣 15 分', () => {
    const stats = computeFlowStats(
      [node('a', 'main'), node('b', 'main')],
      [edge('e1', 'a', 'b', 'branch', '条件')]
    )

    expect(stats.completenessScore).toBe(85)
  })

  it('孤立节点每 5 分、上限 20 分', () => {
    const nodes = [
      node('m1', 'main'),
      node('m2', 'main'),
      node('x1', 'branch'),
      node('x2', 'branch'),
      node('x3', 'branch'),
    ]

    // 100 - 15（多主干无 normal 连线） - 20（5 个孤立节点，封顶） - 15（有节点零连线）
    expect(computeFlowStats(nodes, []).completenessScore).toBe(50)
  })

  it('缺条件连线每条 3 分、上限 15 分', () => {
    const nodes = [node('a', 'main'), node('b', 'branch')]
    const three = [
      edge('e1', 'a', 'b', 'normal'),
      edge('e2', 'a', 'b', 'branch', ''),
      edge('e3', 'a', 'b', 'exception', ''),
      edge('e4', 'a', 'b', 'bypass', ''),
    ]
    const six = [
      ...three,
      edge('e5', 'a', 'b', 'branch', ''),
      edge('e6', 'a', 'b', 'exception', ''),
      edge('e7', 'a', 'b', 'bypass', ''),
    ]

    expect(computeFlowStats(nodes, three).completenessScore).toBe(91)
    expect(computeFlowStats(nodes, six).completenessScore).toBe(85)
  })

  it('多主干且零连线：三项扣分叠加', () => {
    const stats = computeFlowStats([node('a', 'main'), node('b', 'main')], [])

    // 100 - 15（多主干无 normal） - 10（2 个孤立节点） - 15（零连线）
    expect(stats.completenessScore).toBe(60)
  })

  it('评分为负时钳制到 0', () => {
    const nodes = Array.from({ length: 10 }, (_, i) => node(`b${i}`, 'branch'))

    expect(computeFlowStats(nodes, []).completenessScore).toBe(30)
  })
})

describe('deriveStatsIssues — 问题推导', () => {
  it('空流程图返回单条 error 并提前结束', () => {
    const issues = deriveStatsIssues(computeFlowStats([], []))

    expect(issues).toEqual([{ type: 'error', message: '流程图节点列表为空' }])
  })

  it('无主干给 error', () => {
    const issues = deriveStatsIssues(computeFlowStats([node('a', 'branch')], []))

    expect(issues.some((i) => i.type === 'error' && i.message.includes('缺少主干节点'))).toBe(true)
  })

  it('多主干无正常连线给 warning', () => {
    const issues = deriveStatsIssues(
      computeFlowStats(
        [node('a', 'main'), node('b', 'main')],
        [edge('e1', 'a', 'b', 'branch', 'c')]
      )
    )

    expect(issues.some((i) => i.message.includes('没有正常连线'))).toBe(true)
  })

  it('孤立节点与缺条件连线分别给 warning 并带数量', () => {
    const issues = deriveStatsIssues(
      computeFlowStats(
        [node('a', 'main'), node('b', 'branch'), node('c', 'branch')],
        [edge('e1', 'a', 'b', 'branch', '')]
      )
    )

    expect(issues.some((i) => i.message === '1 个节点未连线（孤立节点）')).toBe(true)
    expect(issues.some((i) => i.message === '1 条分支/异常/弹窗连线缺少触发条件')).toBe(true)
  })

  it('健康流程无任何问题', () => {
    const issues = deriveStatsIssues(
      computeFlowStats([node('a', 'main'), node('b', 'main')], [edge('e1', 'a', 'b')])
    )

    expect(issues).toEqual([])
  })
})
