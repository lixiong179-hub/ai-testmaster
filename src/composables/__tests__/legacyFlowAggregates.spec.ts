/**
 * B-04 登记测试：遗留聚合模块的「零生产引用」事实冻结。
 *
 * `useFlowSort.ts` / `useFlowInteraction.ts` / `useFlowCore.ts` 合计约 3.47k 行，
 * 是拆分前的单体聚合层，能力已由 `composables/flowSort/*` 与
 * `composables/useFlow{Layout,TypeOps,EdgeOps,Search,PathHighlight,GroupBackground}.ts` 取代。
 *
 * 全仓引用现状（2026-11-13 实测）：
 * - useFlowSort.ts        0 处
 * - useFlowInteraction.ts 仅被 useFlowSort.ts 引用
 * - useFlowCore.ts        仅被上述两个文件引用
 *
 * 按 B-04 纪律「零引用候选本轮仅登记、不删除」，本测试只冻结对外导出契约：
 * 若这些模块被删除或导出被改，测试会失败，提醒复核登记结论并走 P4 清理流程。
 */
import { describe, it, expect } from 'vitest'
import * as flowSort from '../useFlowSort'
import * as flowInteraction from '../useFlowInteraction'
import * as flowCore from '../useFlowCore'

describe('遗留聚合模块 — 导出契约冻结', () => {
  it('useFlowSort 仍导出编排上下文与统计工具', () => {
    expect(typeof flowSort.provideFlowSortEditor).toBe('function')
    expect(typeof flowSort.useFlowSortEditor).toBe('function')
    expect(typeof flowSort.useFlowSortData).toBe('function')
    expect(typeof flowSort.computeFlowStats).toBe('function')
    expect(typeof flowSort.deriveStatsIssues).toBe('function')
    expect(flowSort.FLOW_SORT_EDITOR_KEY).toBeDefined()
  })

  it('useFlowInteraction 仍导出交互子模块', () => {
    expect(typeof flowInteraction.useFlowSearch).toBe('function')
    expect(typeof flowInteraction.useFlowEdgeOps).toBe('function')
    expect(typeof flowInteraction.useFlowTypeOps).toBe('function')
    expect(typeof flowInteraction.useFlowEdgeTooltip).toBe('function')
    expect(typeof flowInteraction.useFlowPathHighlight).toBe('function')
  })

  it('useFlowCore 仍导出核心装配入口', () => {
    expect(Object.keys(flowCore).length).toBeGreaterThan(0)
  })

  it('统计工具与拆分后的 useFlowStats 结果一致（防口径漂移）', async () => {
    const { computeFlowStats: splitStats } = await import('../useFlowStats')
    const nodes = [
      { id: 'a', data: { flow_type: 'main' } },
      { id: 'b', data: { flow_type: 'main' } },
    ] as never
    const edges = [{ id: 'e1', source: 'a', target: 'b', data: { edge_type: 'normal' } }] as never

    const legacy = flowSort.computeFlowStats(nodes, edges)
    const current = splitStats(nodes, edges)

    expect(legacy.totalNodes).toBe(current.totalNodes)
    expect(legacy.totalEdges).toBe(current.totalEdges)
    expect(legacy.completenessScore).toBe(current.completenessScore)
  })
})
