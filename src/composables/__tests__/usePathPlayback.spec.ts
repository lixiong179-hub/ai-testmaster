import { describe, it, expect } from 'vitest'
import type { Edge } from '@vue-flow/core'
import { usePathPlayback } from '../usePathPlayback'
import type { FlowEditorNode } from '../useFlowEditor'

function node(
  id: string,
  name: string,
  flowType: 'main' | 'branch',
  order: number,
  position = { x: 0, y: 0 }
): FlowEditorNode {
  return {
    id,
    position,
    data: { screen_name: name, flow_type: flowType, main_order: order },
  } as unknown as FlowEditorNode
}

function edge(id: string, source: string, target: string, edgeType: string): Edge {
  return { id, source, target, data: { edge_type: edgeType } } as unknown as Edge
}

function graph() {
  const nodes = [
    node('m1', '登录页', 'main', 1, { x: 0, y: 0 }),
    node('b1', '登录失败页', 'branch', 0, { x: 0, y: 120 }),
    node('m2', '首页', 'main', 2, { x: 280, y: 0 }),
  ]
  const edges = [
    edge('e1', 'm1', 'm2', 'normal'),
    edge('eb', 'm1', 'b1', 'branch'),
    edge('ebm', 'b1', 'm2', 'normal'),
  ]
  return { nodes, edges }
}

describe('usePathPlayback — 主干路径构建', () => {
  it('按主干顺序生成步骤并标注分支入口', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()

    api.startPlayback(nodes, edges)

    expect(api.isPlaying.value).toBe(true)
    expect(api.currentPlayIndex.value).toBe(0)
    expect(api.playPath.value).toHaveLength(2)
    expect(api.playPath.value[0]).toEqual({
      nodeId: 'm1',
      screenName: '登录页',
      flowType: 'main',
      isBranchChoice: true,
      branchOptions: [{ edgeId: 'eb', targetNodeId: 'b1', targetName: '登录失败页' }],
      nextEdgeId: 'e1',
    })
    expect(api.playPath.value[1]).toMatchObject({
      nodeId: 'm2',
      isBranchChoice: false,
      branchOptions: [],
      nextEdgeId: null,
    })
  })

  it('无主干节点时不进入播放', () => {
    const api = usePathPlayback()

    api.startPlayback([node('b1', '分支页', 'branch', 0)], [])

    expect(api.isPlaying.value).toBe(false)
    expect(api.playPath.value).toEqual([])
  })

  it('缺省名称回退占位文案', () => {
    const api = usePathPlayback()
    const nodes = [
      { id: 'm1', position: { x: 0, y: 0 }, data: { flow_type: 'main' } },
    ] as unknown as FlowEditorNode[]

    api.startPlayback(nodes, [])

    expect(api.playPath.value[0].screenName).toBe('未命名页面')
  })
})

describe('usePathPlayback — 播放状态派生', () => {
  it('未播放时当前节点/连线为空', () => {
    const api = usePathPlayback()

    expect(api.currentPlayNodeId.value).toBeNull()
    expect(api.currentPlayEdgeId.value).toBeNull()
    expect(api.getStepInfo()).toBe('')
  })

  it('播放中按索引返回节点、连线与进度文案', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()

    api.startPlayback(nodes, edges)
    expect(api.currentPlayNodeId.value).toBe('m1')
    expect(api.currentPlayEdgeId.value).toBe('e1')
    expect(api.hasPrevStep.value).toBe(false)
    expect(api.hasNextStep.value).toBe(true)
    expect(api.getStepInfo()).toBe('第 1 / 2 步')

    api.goToStep(1)
    expect(api.currentPlayNodeId.value).toBe('m2')
    expect(api.currentPlayEdgeId.value).toBeNull()
    expect(api.hasPrevStep.value).toBe(true)
    expect(api.hasNextStep.value).toBe(false)
    expect(api.getStepInfo()).toBe('第 2 / 2 步')
  })
})

describe('usePathPlayback — 步进与分支', () => {
  it('分支步先展开选择，再次前进才移动', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)

    api.nextStep()
    expect(api.showBranchChoice.value).toBe(true)
    expect(api.currentPlayIndex.value).toBe(0)

    api.nextStep()
    expect(api.showBranchChoice.value).toBe(false)
    expect(api.currentPlayIndex.value).toBe(1)
  })

  it('末步不再前进，首步不再后退', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)

    api.goToStep(1)
    api.nextStep()
    expect(api.currentPlayIndex.value).toBe(1)

    api.goToStep(0)
    api.prevStep()
    expect(api.currentPlayIndex.value).toBe(0)
  })

  it('后退关闭分支选择', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)
    api.goToStep(1)
    api.showBranchChoice.value = true

    api.prevStep()

    expect(api.currentPlayIndex.value).toBe(0)
    expect(api.showBranchChoice.value).toBe(false)
  })

  it('goToStep 越界忽略', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)

    api.goToStep(-1)
    expect(api.currentPlayIndex.value).toBe(0)

    api.goToStep(9)
    expect(api.currentPlayIndex.value).toBe(0)
  })

  it('跟随分支插入分支步并拼接后续主干', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)
    api.nextStep()

    api.followBranch('b1', edges, nodes)

    expect(api.playPath.value.map((s) => s.nodeId)).toEqual(['m1', 'b1', 'm2'])
    expect(api.currentPlayIndex.value).toBe(1)
    expect(api.showBranchChoice.value).toBe(false)
    expect(api.playPath.value[1]).toEqual({
      nodeId: 'b1',
      screenName: '登录失败页',
      flowType: 'branch',
      isBranchChoice: false,
      branchOptions: [],
      nextEdgeId: 'ebm',
    })
  })

  it('未开始播放时跟随分支无副作用', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()

    api.followBranch('b1', edges, nodes)

    expect(api.playPath.value).toEqual([])
    expect(api.currentPlayIndex.value).toBe(0)
  })

  it('stopPlayback 清空全部播放状态', () => {
    const api = usePathPlayback()
    const { nodes, edges } = graph()
    api.startPlayback(nodes, edges)
    api.showBranchChoice.value = true

    api.stopPlayback()

    expect(api.isPlaying.value).toBe(false)
    expect(api.playPath.value).toEqual([])
    expect(api.currentPlayIndex.value).toBe(0)
    expect(api.showBranchChoice.value).toBe(false)
    expect(api.currentPlayNodeId.value).toBeNull()
  })
})
