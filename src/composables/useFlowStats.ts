import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'

/** 流程完整度统计数据 */
export interface FlowStats {
  /** 节点总数 */
  totalNodes: number
  /** 主干节点数 */
  mainNodes: number
  /** 分支节点数 */
  branchNodes: number
  /** 异常路径节点数 */
  exceptionNodes: number
  /** 弹窗/浮层节点数 */
  bypassNodes: number
  /** 连线总数 */
  totalEdges: number
  /** 正常连线数（主干间） */
  normalEdges: number
  /** 分支连线数 */
  branchEdges: number
  /** 异常连线数 */
  exceptionEdges: number
  /** 弹窗/浮层连线数 */
  bypassEdges: number
  /** 未连线节点数（孤立节点） */
  orphanNodes: number
  /** 缺条件连线数（分支/异常/弹窗连线缺少 condition） */
  missingConditionEdges: number
  /** 完整度评分 0-100 */
  completenessScore: number
}

/** 流程完整度问题项（用于面板高亮展示） */
export interface FlowStatsIssue {
  type: 'error' | 'warning'
  message: string
}

type FlowType = FlowNodeData['flow_type']
type EdgeType = FlowEdgeData['edge_type']

/** 从 VueFlow 编辑器节点/连线计算流程统计数据 */
export function computeFlowStats(nodes: FlowEditorNode[], edges: FlowGraphEdge[]): FlowStats {
  const nodeTypeCounts: Record<FlowType, number> = { main: 0, branch: 0, exception: 0, bypass: 0 }
  const edgeTypeCounts: Record<EdgeType, number> = { normal: 0, branch: 0, exception: 0, bypass: 0 }

  for (const node of nodes) {
    const ft = (node.data?.flow_type as FlowType) || 'main'
    if (ft in nodeTypeCounts) nodeTypeCounts[ft]++
  }

  for (const edge of edges) {
    const et = (edge.data?.edge_type as EdgeType) || 'normal'
    if (et in edgeTypeCounts) edgeTypeCounts[et]++
  }

  // 计算孤立节点：没有任何连线关联的节点
  const connectedNodeIds = new Set<string>()
  for (const edge of edges) {
    if (edge.source) connectedNodeIds.add(edge.source)
    if (edge.target) connectedNodeIds.add(edge.target)
  }
  const orphanCount = nodes.filter((n) => !connectedNodeIds.has(n.id)).length

  // 计算缺条件连线：分支/异常/弹窗连线缺少 condition
  let missingConditionCount = 0
  for (const edge of edges) {
    const et = (edge.data?.edge_type as EdgeType) || 'normal'
    if (et !== 'normal') {
      const cond = (edge.data?.condition as string | undefined) || ''
      if (!cond.trim()) missingConditionCount++
    }
  }

  const score = calcCompletenessScore(
    nodeTypeCounts,
    edgeTypeCounts,
    orphanCount,
    missingConditionCount
  )

  return {
    totalNodes: nodes.length,
    mainNodes: nodeTypeCounts.main,
    branchNodes: nodeTypeCounts.branch,
    exceptionNodes: nodeTypeCounts.exception,
    bypassNodes: nodeTypeCounts.bypass,
    totalEdges: edges.length,
    normalEdges: edgeTypeCounts.normal,
    branchEdges: edgeTypeCounts.branch,
    exceptionEdges: edgeTypeCounts.exception,
    bypassEdges: edgeTypeCounts.bypass,
    orphanNodes: orphanCount,
    missingConditionEdges: missingConditionCount,
    completenessScore: score,
  }
}

/** 从统计数据推导问题列表 */
export function deriveStatsIssues(stats: FlowStats): FlowStatsIssue[] {
  const issues: FlowStatsIssue[] = []

  if (stats.totalNodes === 0) {
    issues.push({ type: 'error', message: '流程图节点列表为空' })
    return issues
  }
  if (stats.mainNodes === 0) {
    issues.push({ type: 'error', message: '缺少主干节点，至少需要一个主干节点' })
  }
  if (stats.mainNodes > 1 && stats.normalEdges === 0) {
    issues.push({
      type: 'warning',
      message: '多个主干节点但没有正常连线，主干流程可能不完整',
    })
  }
  if (stats.orphanNodes > 0) {
    issues.push({
      type: 'warning',
      message: `${stats.orphanNodes} 个节点未连线（孤立节点）`,
    })
  }
  if (stats.missingConditionEdges > 0) {
    issues.push({
      type: 'warning',
      message: `${stats.missingConditionEdges} 条分支/异常/弹窗连线缺少触发条件`,
    })
  }

  return issues
}

/** 完整度评分算法 */
function calcCompletenessScore(
  nodeTypeCounts: Record<FlowType, number>,
  edgeTypeCounts: Record<EdgeType, number>,
  orphanCount: number,
  missingConditionCount: number
): number {
  if (
    nodeTypeCounts.main +
      nodeTypeCounts.branch +
      nodeTypeCounts.exception +
      nodeTypeCounts.bypass ===
    0
  ) {
    return 0
  }

  let score = 100

  // 无主干节点：严重扣分
  if (nodeTypeCounts.main === 0) score -= 35

  // 多个主干但无正常连线
  if (nodeTypeCounts.main > 1 && edgeTypeCounts.normal === 0) score -= 15

  // 孤立节点扣分（每节点扣5分，上限20分）
  score -= Math.min(orphanCount * 5, 20)

  // 缺条件连线扣分（每条扣3分，上限15分）
  score -= Math.min(missingConditionCount * 3, 15)

  // 有节点但无连线扣分
  const totalNodes =
    nodeTypeCounts.main + nodeTypeCounts.branch + nodeTypeCounts.exception + nodeTypeCounts.bypass
  if (
    totalNodes > 1 &&
    edgeTypeCounts.normal +
      edgeTypeCounts.branch +
      edgeTypeCounts.exception +
      edgeTypeCounts.bypass ===
      0
  ) {
    score -= 15
  }

  return Math.max(0, Math.min(100, score))
}
