import { describe, it, expect, vi } from 'vitest'
import { ref } from 'vue'
import { useFlowPathHighlight } from '../useFlowPathHighlight'
import { EDGE_STYLES, OVERVIEW_EDGE_STYLES } from '@/composables/useFlowEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

vi.mock('@vue-flow/core', () => ({ MarkerType: { ArrowClosed: 'arrowclosed' } }))

function node(id: string): FlowEditorNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: { screen_id: Number(id), screen_name: id, flow_type: 'main' },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType = 'normal'): FlowGraphEdge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as FlowGraphEdge
}

/** applyAllEdgeStyles 会给边补上 class，而 FlowGraphEdge 未声明该字段 */
type StyledEdge = FlowGraphEdge & { class?: string }

function setup(isOverview = false) {
  const vueFlowNodes = ref([node('1'), node('2'), node('3'), node('4')])
  const vueFlowEdges = ref([
    edge('e1', '1', '2'),
    edge('e2', '2', '3'),
    edge('e3', '3', '4'),
    edge('e4', '2', '4', 'branch'),
  ])
  const isOverviewMode = ref(isOverview)
  const collapsedParentNodeIds = ref<string[]>(['3', '4'])

  const api = useFlowPathHighlight({
    vueFlowNodes,
    vueFlowEdges,
    getNodeData: (n) => n.data as never,
    isOverviewMode,
    collapsedParentNodeIds,
  })

  return { api, vueFlowNodes, vueFlowEdges, isOverviewMode, collapsedParentNodeIds }
}

describe('useFlowPathHighlight — 路径推导', () => {
  it('未聚焦时四个集合均为空', () => {
    const { api } = setup()

    expect(api.upstreamNodeIds.value.size).toBe(0)
    expect(api.downstreamNodeIds.value.size).toBe(0)
    expect(api.allPathNodeIds.value.size).toBe(0)
    expect(api.pathHighlightedEdgeIds.value.size).toBe(0)
  })

  it('聚焦节点后计算上下游并合并为完整路径', () => {
    const { api } = setup()
    api.focusedNodeId.value = '3'

    expect([...api.upstreamNodeIds.value].sort()).toEqual(['1', '2'])
    expect([...api.downstreamNodeIds.value]).toEqual(['4'])
    expect([...api.allPathNodeIds.value].sort()).toEqual(['1', '2', '3', '4'])
    // e1(1-2) / e2(2-3) / e3(3-4) 命中路径；e4(2-4) 两端都在路径内也算相关
    expect([...api.pathHighlightedEdgeIds.value].sort()).toEqual(['e1', 'e2', 'e3', 'e4'])
  })

  it('聚焦叶子节点时下游为空', () => {
    const { api } = setup()
    api.focusedNodeId.value = '4'

    expect(api.downstreamNodeIds.value.size).toBe(0)
    expect(api.upstreamNodeIds.value.has('2')).toBe(true)
  })
})

describe('useFlowPathHighlight — 边样式', () => {
  it('未聚焦时只套基础样式，不加高亮 class', () => {
    const { api } = setup()

    const styled = api.applyAllEdgeStyles([edge('e1', '1', '2')]) as StyledEdge[]

    expect(styled[0].class).toBeUndefined()
    expect(styled[0].style).toMatchObject({ stroke: EDGE_STYLES.normal.stroke })
  })

  it('聚焦后路径内边 strokeWidth=3 并打高亮 class，其余变暗', () => {
    const { api } = setup()
    api.focusedNodeId.value = '2'

    const styled = api.applyAllEdgeStyles([
      edge('e1', '1', '2'),
      edge('e9', '9', '8'),
    ]) as StyledEdge[]

    const highlighted = styled.find((e) => e.id === 'e1')
    const dimmed = styled.find((e) => e.id === 'e9')
    expect(highlighted?.class).toBe('edge-path-highlighted')
    expect(highlighted?.style).toMatchObject({ strokeWidth: 3 })
    expect(dimmed?.class).toBe('edge-path-dimmed')
    expect(dimmed?.style).toMatchObject({ strokeWidth: 1 })
  })

  it('概览模式切换样式表', () => {
    const { api, isOverviewMode } = setup()

    expect(api.currentEdgeStyles.value).toBe(EDGE_STYLES)

    isOverviewMode.value = true
    expect(api.currentEdgeStyles.value).toBe(OVERVIEW_EDGE_STYLES)
  })

  it('getEdgeStyle 未知类型回退 normal', () => {
    const { api } = setup()

    expect(api.getEdgeStyle('branch')).toBe(EDGE_STYLES.branch)
    expect(api.getEdgeStyle('__unknown__')).toBe(EDGE_STYLES.normal)
  })

  it('defaultEdgeOptions 使用 normal 样式与箭头颜色', () => {
    const { api } = setup()

    const options = api.defaultEdgeOptions.value
    expect(options.style).toBe(EDGE_STYLES.normal)
    expect(options.markerEnd).toMatchObject({
      type: 'arrowclosed',
      color: EDGE_STYLES.normal.stroke,
    })
  })
})

describe('useFlowPathHighlight — 交互', () => {
  it('点击节点：选中并设置焦点，同时从折叠列表移除', () => {
    const { api, collapsedParentNodeIds } = setup()

    api.handleNodeClick({ node: { id: '3' } as never })

    expect(api.selectedNodes.value).toEqual(['3'])
    expect(api.focusedNodeId.value).toBe('3')
    expect(collapsedParentNodeIds.value).toEqual(['4'])
  })

  it('再次点击同一节点取消焦点（保留选中）', () => {
    const { api } = setup()

    api.handleNodeClick({ node: { id: '2' } as never })
    api.handleNodeClick({ node: { id: '2' } as never })

    expect(api.focusedNodeId.value).toBeNull()
    expect(api.selectedNodes.value).toEqual(['2'])
  })

  it('点击画布清空选中与焦点', () => {
    const { api } = setup()
    api.handleNodeClick({ node: { id: '2' } as never })

    api.handlePaneClick()

    expect(api.selectedNodes.value).toEqual([])
    expect(api.focusedNodeId.value).toBeNull()
  })
})
