import { describe, it, expect } from 'vitest'
import { useFlowHistory, useFlowSelection } from '../flowEditorComposables'

function node(id: string, overrides: Record<string, unknown> = {}) {
  return { id, data: { flow_type: 'main', main_order: 1 }, ...overrides } as never
}

function edge(id: string) {
  return { id, source: 'a', target: 'b' } as never
}

describe('useFlowHistory', () => {
  it('初始不可撤销', () => {
    const { historyStack, canUndo, undo } = useFlowHistory()

    expect(historyStack.value).toEqual([])
    expect(canUndo.value).toBe(false)
    expect(undo()).toBeNull()
  })

  it('保存快照后可撤销并深拷贝数据', () => {
    const { canUndo, saveToHistory, undo } = useFlowHistory()
    const nodes = [node('a')]
    const edges = [edge('e1')]

    saveToHistory(nodes, edges)

    expect(canUndo.value).toBe(true)
    nodes[0] = node('changed')

    const snapshot = undo()
    expect(snapshot?.nodes[0]).toMatchObject({ id: 'a' })
    expect(snapshot?.edges).toHaveLength(1)
    expect(canUndo.value).toBe(false)
  })

  it('撤销按后进先出顺序返回', () => {
    const { saveToHistory, undo } = useFlowHistory()

    saveToHistory([node('first')], [])
    saveToHistory([node('second')], [])

    expect(undo()?.nodes[0]).toMatchObject({ id: 'second' })
    expect(undo()?.nodes[0]).toMatchObject({ id: 'first' })
  })

  it('历史栈最多保留 50 条', () => {
    const { historyStack, saveToHistory } = useFlowHistory()

    for (let i = 0; i < 55; i++) {
      saveToHistory([node(`n${i}`)], [])
    }

    expect(historyStack.value).toHaveLength(50)
    expect(historyStack.value[0].nodes[0]).toMatchObject({ id: 'n5' })
  })
})

describe('useFlowSelection', () => {
  it('初始状态无可选节点', () => {
    const { selectedNodes, draggingNodeId, getSelectedMainNodeId, getSelectedMainOrder } =
      useFlowSelection()

    expect(selectedNodes.value).toEqual([])
    expect(draggingNodeId.value).toBeNull()
    expect(getSelectedMainNodeId([node('a')])).toBeNull()
    expect(getSelectedMainOrder([node('a')])).toBeNull()
  })

  it('多选时不返回主节点', () => {
    const { selectedNodes, getSelectedMainNodeId } = useFlowSelection()
    selectedNodes.value = ['a', 'b']

    expect(getSelectedMainNodeId([node('a'), node('b')])).toBeNull()
  })

  it('单选主节点时返回 ID 与顺序', () => {
    const { selectedNodes, getSelectedMainNodeId, getSelectedMainOrder } = useFlowSelection()
    selectedNodes.value = ['a']

    expect(getSelectedMainNodeId([node('a', { data: { flow_type: 'main', main_order: 3 } })])).toBe(
      'a'
    )
    expect(getSelectedMainOrder([node('a', { data: { flow_type: 'main', main_order: 3 } })])).toBe(
      3
    )
  })

  it('单选非主节点时返回空', () => {
    const { selectedNodes, getSelectedMainNodeId, getSelectedMainOrder } = useFlowSelection()
    selectedNodes.value = ['a']

    const nodes = [node('a', { data: { flow_type: 'branch' } })]
    expect(getSelectedMainNodeId(nodes)).toBeNull()
    expect(getSelectedMainOrder(nodes)).toBeNull()
  })

  it('主节点缺失 main_order 时返回 null', () => {
    const { selectedNodes, getSelectedMainOrder } = useFlowSelection()
    selectedNodes.value = ['a']

    expect(getSelectedMainOrder([node('a', { data: { flow_type: 'main' } })])).toBeNull()
  })

  it('选中节点不在列表中时返回空', () => {
    const { selectedNodes, getSelectedMainNodeId, getSelectedMainOrder } = useFlowSelection()
    selectedNodes.value = ['x']

    expect(getSelectedMainNodeId([node('a')])).toBeNull()
    expect(getSelectedMainOrder([node('a')])).toBeNull()
  })

  it('拖拽节点 ID 可读写', () => {
    const { draggingNodeId } = useFlowSelection()

    draggingNodeId.value = 'a'
    expect(draggingNodeId.value).toBe('a')
  })
})
