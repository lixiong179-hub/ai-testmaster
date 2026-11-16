import { describe, it, expect } from 'vitest'
import { useEdgeSuggestion } from '../useEdgeSuggestion'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import type { Edge } from '@vue-flow/core'

function node(
  id: string,
  name: string,
  elements: Array<Record<string, unknown>> = []
): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { screen_name: name, ui_spec_elements: elements, flow_type: 'main' },
  } as unknown as FlowEditorNode
}

function edge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target } as Edge
}

describe('useEdgeSuggestion — 名称相似度', () => {
  const { runAnalysis: analyzeTransitions } = useEdgeSuggestion()

  it('同名（忽略大小写）得满分并以名称相似说明', () => {
    const result = analyzeTransitions([node('a', 'Login'), node('b', 'login')], [])

    // 有向建议：a->b 与 b->a 各一条
    expect(result).toHaveLength(2)
    expect(result[0]).toMatchObject({ matchScore: 100, accepted: false })
    expect(result[0].reason).toContain('页面名称')
  })

  it('包含关系得 80 分', () => {
    const result = analyzeTransitions([node('a', '用户登录页'), node('b', '登录')], [])

    const forward = result.find((r) => r.sourceNodeId === 'a')
    expect(forward?.matchScore).toBe(80)
  })

  it('关键词命中不足时不产生建议', () => {
    const result = analyzeTransitions([node('a', '购物车'), node('b', '登录页')], [])

    expect(result).toEqual([])
  })

  it('跳过自身与已存在的连线', () => {
    const nodes = [node('a', '登录页'), node('b', '登录页')]

    // a->b 已存在时只剩反向 b->a
    expect(analyzeTransitions(nodes, [edge('a', 'b')])).toHaveLength(1)
    expect(analyzeTransitions(nodes, [edge('a', 'b')])[0].sourceNodeId).toBe('b')
    // 两个方向都已存在则无建议
    expect(analyzeTransitions(nodes, [edge('a', 'b'), edge('b', 'a')])).toEqual([])
  })

  it('元素文本命中时优先以元素说明原因', () => {
    const result = analyzeTransitions(
      [node('a', '首页', [{ button_text: '去登录页' }]), node('b', '登录页')],
      []
    )

    expect(result[0].reason).toContain('元素 "去登录页"')
    expect(result[0].matchScore).toBeGreaterThanOrEqual(50)
  })

  it('未命名页面回退「未命名」占位', () => {
    const result = analyzeTransitions([node('a', ''), node('b', '')], [])

    // 两个空名称相似度为 0，不产生建议
    expect(result).toEqual([])
  })

  it('结果按匹配分降序排列', () => {
    const nodes = [node('a', '登录'), node('b', '登录'), node('c', '登录页')]

    const result = analyzeTransitions(nodes, [])

    const scores = result.map((r) => r.matchScore)
    expect([...scores].sort((x, y) => y - x)).toEqual(scores)
  })

  it('非字符串元素字段被忽略', () => {
    const result = analyzeTransitions(
      [node('a', '购物车', [{ label: 123 as unknown as string }, {}]), node('b', '登录页')],
      []
    )

    expect(result).toEqual([])
  })
})

describe('useEdgeSuggestion — 状态管理', () => {
  it('runAnalysis 写入并返回建议，clearSuggestions 清空', () => {
    const { suggestions, runAnalysis, clearSuggestions } = useEdgeSuggestion()

    const result = runAnalysis([node('a', '登录页'), node('b', '登录页')], [])

    // 双向各产生一条建议
    expect(result).toHaveLength(2)
    expect(suggestions.value).toHaveLength(2)

    clearSuggestions()
    expect(suggestions.value).toEqual([])
  })
})
