import { describe, expect, it } from 'vitest'
import type { Edge } from '@vue-flow/core'
import {
  getMainNodesInOrder,
  getOrderedNodesForSubmit,
  normalizeMainNodeOrders,
  layoutMainNodesByOrder,
  getMainNodeCount,
  validateFlowData,
  normalizeEdges,
  EDGE_STYLES,
} from '../useFlowEditor'
import type { FlowEditorNode, EditorNodeData } from '../useFlowEditor'

const makeNode = (
  id: string,
  flowType: 'main' | 'branch' | 'exception' | 'bypass',
  overrides: Partial<FlowEditorNode> = {}
): FlowEditorNode => ({
  id,
  type: 'custom',
  position: { x: 0, y: 0 },
  data: {
    screen_id: Number(id.replace('node_', '')),
    screen_name: `页面${id}`,
    flow_type: flowType,
    main_order: flowType === 'main' ? undefined : undefined,
    ...overrides.data,
  },
  ...overrides,
})

const makeMainNode = (id: string, mainOrder: number, x = 0) =>
  makeNode(id, 'main', {
    position: { x, y: 0 },
    data: {
      screen_id: Number(id.replace('node_', '')),
      screen_name: `页面${id}`,
      flow_type: 'main',
      main_order: mainOrder,
    },
  })

describe('getMainNodesInOrder', () => {
  it('should return only main nodes sorted by main_order', () => {
    const nodes = [
      makeMainNode('node_3', 2),
      makeMainNode('node_1', 1),
      makeMainNode('node_2', 3),
      makeNode('node_4', 'branch'),
    ]
    const result = getMainNodesInOrder(nodes)
    expect(result.map((n) => n.id)).toEqual(['node_1', 'node_3', 'node_2'])
  })

  it('should fall back to x position when main_order is equal', () => {
    const nodes = [makeMainNode('node_2', 1, 300), makeMainNode('node_1', 1, 100)]
    const result = getMainNodesInOrder(nodes)
    expect(result.map((n) => n.id)).toEqual(['node_1', 'node_2'])
  })

  it('should return empty array when no main nodes', () => {
    const nodes = [makeNode('node_1', 'branch'), makeNode('node_2', 'exception')]
    const result = getMainNodesInOrder(nodes)
    expect(result).toEqual([])
  })
})

describe('getOrderedNodesForSubmit', () => {
  it('should place main nodes first in order, then other nodes by position', () => {
    const nodes = [
      makeNode('node_4', 'branch', { position: { x: 100, y: 200 } }),
      makeMainNode('node_2', 2, 280),
      makeMainNode('node_1', 1, 0),
      makeNode('node_3', 'exception', { position: { x: 100, y: 100 } }),
    ]
    const result = getOrderedNodesForSubmit(nodes)
    expect(result.map((n) => n.id)).toEqual(['node_1', 'node_2', 'node_3', 'node_4'])
  })
})

describe('normalizeMainNodeOrders', () => {
  it('should reassign sequential main_order starting from 1', () => {
    const nodes = [
      makeMainNode('node_1', 5),
      makeMainNode('node_2', 10),
      makeNode('node_3', 'branch'),
    ]
    const result = normalizeMainNodeOrders(nodes)
    const mainResult = result.filter((n) => n.data.flow_type === 'main')
    expect(mainResult.map((n) => (n.data as EditorNodeData).main_order)).toEqual([1, 2])
  })

  it('should remove main_order from non-main nodes', () => {
    const nodes = [
      makeMainNode('node_1', 1),
      {
        ...makeNode('node_2', 'branch'),
        data: { ...makeNode('node_2', 'branch').data, main_order: 3 },
      },
    ]
    const result = normalizeMainNodeOrders(nodes)
    const branchNode = result.find((n) => n.id === 'node_2')
    expect((branchNode?.data as EditorNodeData).main_order).toBeUndefined()
  })
})

describe('layoutMainNodesByOrder', () => {
  it('should position main nodes at x = index * 280', () => {
    const nodes = [makeMainNode('node_1', 1, 500), makeMainNode('node_2', 2, 999)]
    const result = layoutMainNodesByOrder(nodes)
    const mainResult = result.filter((n) => n.data.flow_type === 'main')
    expect(mainResult[0].position.x).toBe(0)
    expect(mainResult[1].position.x).toBe(280)
  })
})

describe('getMainNodeCount', () => {
  it('should count only main nodes', () => {
    const nodes = [
      makeMainNode('node_1', 1),
      makeMainNode('node_2', 2),
      makeNode('node_3', 'branch'),
    ]
    expect(getMainNodeCount(nodes)).toBe(2)
  })
})

describe('validateFlowData', () => {
  it('should error when no main nodes', () => {
    const result = validateFlowData([{ screen_id: 1, screen_name: 'A', flow_type: 'branch' }], [])
    expect(result.errors).toContain('至少需要保留一个主干节点')
  })

  it('should error when screen_name is empty', () => {
    const result = validateFlowData([{ screen_id: 1, screen_name: '  ', flow_type: 'main' }], [])
    expect(result.errors.length).toBeGreaterThan(0)
  })

  it('should WARN (not error) when branch edge lacks condition', () => {
    const result = validateFlowData(
      [{ screen_id: 1, screen_name: 'A', flow_type: 'main' }],
      [{ source: '1', target: '2', edge_type: 'branch', condition: '', label: '分支1' }]
    )
    expect(result.errors).not.toContain(expect.stringContaining('分支触发条件'))
    expect(result.warnings.some((w) => w.includes('分支触发条件') && w.includes('自动推断'))).toBe(
      true
    )
  })

  it('should WARN (not error) when exception edge lacks condition', () => {
    const result = validateFlowData(
      [{ screen_id: 1, screen_name: 'A', flow_type: 'main' }],
      [{ source: '1', target: '2', edge_type: 'exception', condition: '', label: '异常1' }]
    )
    expect(result.warnings.some((w) => w.includes('异常场景') && w.includes('自动推断'))).toBe(true)
  })

  it('should not warn when branch edge has condition', () => {
    const result = validateFlowData(
      [{ screen_id: 1, screen_name: 'A', flow_type: 'main' }],
      [{ source: '1', target: '2', edge_type: 'branch', condition: '点击按钮', label: '分支1' }]
    )
    expect(result.warnings.some((w) => w.includes('分支触发条件'))).toBe(false)
  })

  it('should warn when multiple main nodes have no normal edges', () => {
    const result = validateFlowData(
      [
        { screen_id: 1, screen_name: 'A', flow_type: 'main' },
        { screen_id: 2, screen_name: 'B', flow_type: 'main' },
      ],
      []
    )
    expect(result.warnings.some((w) => w.includes('没有正常连线'))).toBe(true)
  })

  it('should return no issues for valid data', () => {
    const result = validateFlowData(
      [
        { screen_id: 1, screen_name: 'A', flow_type: 'main' },
        { screen_id: 2, screen_name: 'B', flow_type: 'main' },
      ],
      [{ source: '1', target: '2', edge_type: 'normal', condition: '', label: '' }]
    )
    expect(result.errors).toEqual([])
    expect(result.warnings).toEqual([])
  })
})

describe('normalizeEdges', () => {
  it('should apply EDGE_STYLES based on edge_type', () => {
    const edges = [
      { id: 'e1', source: 'a', target: 'b', data: { edge_type: 'branch' } },
      { id: 'e2', source: 'a', target: 'c', data: { edge_type: 'normal' } },
    ]
    const result = normalizeEdges(edges as unknown as Edge[])
    expect((result[0].style as unknown as { stroke?: string })?.stroke).toBe(EDGE_STYLES.branch.stroke)
    expect(result[0].animated).toBe(true)
    expect((result[1].style as unknown as { stroke?: string })?.stroke).toBe(EDGE_STYLES.normal.stroke)
    expect(result[1].animated).toBe(false)
  })

  it('should create arrow marker with correct color', () => {
    const edges = [{ id: 'e1', source: 'a', target: 'b', data: { edge_type: 'exception' } }]
    const result = normalizeEdges(edges as unknown as Edge[])
    expect((result[0].markerEnd as unknown as { color?: string })?.color).toBe(EDGE_STYLES.exception.stroke)
  })
})
