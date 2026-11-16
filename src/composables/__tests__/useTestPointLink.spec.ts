import { describe, it, expect } from 'vitest'
import { useTestPointLink } from '../useTestPointLink'
import type { FlowEditorNode } from '@/composables/useFlowEditor'
import type { TestPoint } from '@/types/testPoint'

function point(id: number, module = '', fn = '', p = ''): TestPoint {
  return { id, module, function: fn, point: p, priority: 1 } as unknown as TestPoint
}

function node(id: string, screenId: number, name: string): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { screen_id: screenId, screen_name: name },
  } as unknown as FlowEditorNode
}

describe('useTestPointLink — 名称匹配', () => {
  const { matchScreenName } = useTestPointLink()

  it('空页面名不匹配', () => {
    expect(matchScreenName(point(1, '登录'), '')).toBe(false)
  })

  it('模块名双向包含即命中', () => {
    expect(matchScreenName(point(1, '登录'), '用户登录页')).toBe(true)
    expect(matchScreenName(point(1, '登录模块'), '登录')).toBe(true)
  })

  it('大小写不敏感', () => {
    expect(matchScreenName(point(1, 'Login'), 'login page')).toBe(true)
  })

  it('多个字段部分命中时累加达标', () => {
    const tp = point(1, '登录', '登录', '密码错误')

    expect(matchScreenName(tp, '登录')).toBe(true)
  })

  it('完全无关时不命中', () => {
    expect(matchScreenName(point(1, '购物车', '结算', '库存不足'), '登录页')).toBe(false)
  })

  it('缺失字段被跳过', () => {
    expect(matchScreenName(point(1, '', '', ''), '登录页')).toBe(false)
  })
})

describe('useTestPointLink — 关联屏幕', () => {
  const { getRelatedScreenIds } = useTestPointLink()
  const nodes = [node('n1', 101, '登录页'), node('n2', 102, '首页'), node('n3', 103, '订单列表')]
  const points = [point(1, '登录'), point(2, '订单'), point(3, '个人中心')]

  it('未选测试点或测试点为空时返回空集', () => {
    expect(getRelatedScreenIds([], points, nodes).size).toBe(0)
    expect(getRelatedScreenIds([1], [], nodes).size).toBe(0)
  })

  it('按命中名称收集 screen_id', () => {
    expect([...getRelatedScreenIds([1, 2], points, nodes)].sort()).toEqual([101, 103])
  })

  it('多个测试点命中同一屏幕时去重', () => {
    const tp = [point(1, '登录'), point(2, '登录页')]

    expect([...getRelatedScreenIds([1, 2], tp, nodes)]).toEqual([101])
  })

  it('无任何匹配返回空集', () => {
    expect(getRelatedScreenIds([3], points, nodes).size).toBe(0)
  })
})

describe('useTestPointLink — 关联测试点', () => {
  const { getRelatedTestPointIds } = useTestPointLink()
  const nodes = [node('n1', 101, '登录页'), node('n2', 102, '订单列表')]
  const points = [point(1, '登录'), point(2, '订单'), point(3, '个人中心')]

  it('未选节点或测试点为空时返回空数组', () => {
    expect(getRelatedTestPointIds([], nodes, points)).toEqual([])
    expect(getRelatedTestPointIds(['n1'], nodes, [])).toEqual([])
  })

  it('按选中节点收集命中的测试点 ID', () => {
    expect(getRelatedTestPointIds(['n1', 'n2'], nodes, points).sort()).toEqual([1, 2])
  })

  it('跨节点重复命中只保留一次', () => {
    const shared = [point(9, '页'), point(9, '页')]

    expect(getRelatedTestPointIds(['n1', 'n2'], nodes, shared)).toEqual([9])
  })
})
