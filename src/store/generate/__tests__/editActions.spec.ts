import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGenerateState, type GenerateState } from '../state'
import { createGenerateComputed, type GenerateComputed } from '../computed'
import { createEditActions } from '../editActions'

const { mockUpdateNodes, mockUpdateEdges, mockTriggerAutoSave } = vi.hoisted(() => ({
  mockUpdateNodes: vi.fn(),
  mockUpdateEdges: vi.fn(),
  mockTriggerAutoSave: vi.fn(),
}))

vi.mock('@/store/flowSort', () => ({
  useFlowSortStore: () => ({
    updateNodes: mockUpdateNodes,
    updateEdges: mockUpdateEdges,
    triggerAutoSave: mockTriggerAutoSave,
  }),
}))

function setup() {
  const state: GenerateState = createGenerateState()
  const computed: GenerateComputed = createGenerateComputed(state)
  const actions = createEditActions(state, computed)
  return { state, computed, actions }
}

describe('createEditActions — 步骤流转', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createEditActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setup())
  })

  it('nextStep/prevStep 在 0..2 之间收敛', () => {
    expect(state.currentStep.value).toBe(0)

    actions.prevStep()
    expect(state.currentStep.value).toBe(0)

    actions.nextStep()
    actions.nextStep()
    actions.nextStep()
    expect(state.currentStep.value).toBe(2)

    actions.prevStep()
    expect(state.currentStep.value).toBe(1)
  })

  it('skipToStep2 直接落到第 2 步', () => {
    state.currentStep.value = 2
    actions.skipToStep2()
    expect(state.currentStep.value).toBe(1)
  })

  it('handleCaseTypeChange：非 UI 自动化时 exec_mode 重置为 all', () => {
    state.formData.exec_mode = 'ui_auto'
    actions.handleCaseTypeChange('ui_automation')
    expect(state.formData.exec_mode).toBe('ui_auto')

    actions.handleCaseTypeChange('api_automation')
    expect(state.formData.exec_mode).toBe('all')
  })
})

describe('createEditActions — 用例选择', () => {
  it('toggleCaseSelection 增删选中项且不修改原集合', () => {
    const { state, actions } = setup()
    const original = new Set([0])
    state.selectedCaseIndices.value = original

    actions.toggleCaseSelection(1)
    expect([...state.selectedCaseIndices.value].sort()).toEqual([0, 1])
    expect([...original]).toEqual([0])

    actions.toggleCaseSelection(0)
    expect([...state.selectedCaseIndices.value]).toEqual([1])
  })

  it('toggleSelectAll：未全选时全选，全选时清空', () => {
    const { state, actions } = setup()
    state.generatedCases.value = [{ title: 'A' }, { title: 'B' }, { title: 'C' }] as never

    actions.toggleSelectAll()
    expect([...state.selectedCaseIndices.value].sort()).toEqual([0, 1, 2])

    actions.toggleSelectAll()
    expect(state.selectedCaseIndices.value.size).toBe(0)
  })

  it('toggleSelectAll：空列表时不会误判为全选', () => {
    const { state, actions } = setup()
    actions.toggleSelectAll()
    expect(state.selectedCaseIndices.value.size).toBe(0)
  })
})

describe('createEditActions — 结果编辑态', () => {
  it('startEditResult 深拷贝当前用例步骤，避免直接引用', () => {
    const { state, actions } = setup()
    const steps = [{ step: 1, action: '点击', param: '', expected_result: '', test_data: {} }]
    state.generatedCases.value = [{ title: 'A', steps, priority: 1 }] as never
    state.currentCaseIndex.value = 0

    actions.startEditResult()

    expect(state.isEditingResult.value).toBe(true)
    expect(state.editingCase.value.title).toBe('A')
    expect(state.editingCase.value.priority).toBe(1)
    expect(state.editingCase.value.steps).toEqual(steps)
    expect(state.editingCase.value.steps).not.toBe(steps)
    expect(state.editingCase.value.steps[0]).not.toBe(steps[0])
  })

  it('startEditResult 无用例时不做任何修改', () => {
    const { state, actions } = setup()
    actions.startEditResult()
    expect(state.isEditingResult.value).toBe(false)
  })

  it('cancelEditResult 关闭编辑态', () => {
    const { state, actions } = setup()
    state.isEditingResult.value = true
    actions.cancelEditResult()
    expect(state.isEditingResult.value).toBe(false)
  })

  it('addEditStep 追加步骤并递增序号', () => {
    const { state, actions } = setup()
    state.editingCase.value.steps = [
      { step: 1, action: 'a', param: '', expected_result: '', test_data: {} },
    ]

    actions.addEditStep()

    expect(state.editingCase.value.steps).toHaveLength(2)
    expect(state.editingCase.value.steps[1]).toMatchObject({ step: 2, action: '' })
  })

  it('removeEditStep 删除后重排序号，且至少保留一步', () => {
    const { state, actions } = setup()
    state.editingCase.value.steps = [
      { step: 1, action: 'a', param: '', expected_result: '', test_data: {} },
      { step: 2, action: 'b', param: '', expected_result: '', test_data: {} },
      { step: 3, action: 'c', param: '', expected_result: '', test_data: {} },
    ]

    actions.removeEditStep(0)
    expect(state.editingCase.value.steps.map((s) => s.action)).toEqual(['b', 'c'])
    expect(state.editingCase.value.steps.map((s) => s.step)).toEqual([1, 2])

    actions.removeEditStep(0)
    actions.removeEditStep(0)
    expect(state.editingCase.value.steps).toHaveLength(1)
  })
})

describe('createEditActions — 重置与重试', () => {
  it('handleRetry 清空错误与建议', () => {
    const { state, actions } = setup()
    state.errorMessage.value = 'boom'
    state.errorSuggestions.value = ['a']

    actions.handleRetry()

    expect(state.errorMessage.value).toBe('')
    expect(state.errorSuggestions.value).toEqual([])
  })

  it('resetForm 复位表单、用例与步骤', () => {
    const { state, actions } = setup()
    state.currentStep.value = 2
    state.formData.scene = '场景'
    state.formData.case_type = 'ui_automation'
    state.formData.exec_mode = 'ui_auto'
    state.formData.priority = 1
    state.formData.enhanced_mode = false
    state.currentCaseIndex.value = 3
    state.selectedCaseIndices.value = new Set([0])
    state.caseIdSeq.value = 5
    state.isEditingResult.value = true
    state.lastContext.value = { a: 1 }

    actions.resetForm()

    expect(state.currentStep.value).toBe(0)
    expect(state.formData.scene).toBe('')
    expect(state.formData.case_type).toBe('')
    expect(state.formData.exec_mode).toBe('all')
    expect(state.formData.priority).toBe(2)
    expect(state.formData.enhanced_mode).toBe(true)
    expect(state.generatedCases.value).toEqual([])
    expect(state.currentCaseIndex.value).toBe(-1)
    expect(state.selectedCaseIndices.value.size).toBe(0)
    expect(state.caseIdSeq.value).toBe(0)
    expect(state.isEditingResult.value).toBe(false)
    expect(state.lastContext.value).toEqual({})
  })

  it('resetGenerateState 只清生成产物，不动表单与步骤', () => {
    const { state, actions } = setup()
    state.currentStep.value = 2
    state.formData.scene = '场景'
    state.generating.value = true
    state.progress.value = 60
    state.errorMessage.value = 'boom'
    state.generatedCases.value = [{ title: 'A' }] as never
    state.currentCaseIndex.value = 0
    state.selectedCaseIndices.value = new Set([0])
    state.caseIdSeq.value = 2
    state.contextStats.value = { foo: 1 } as never
    state.serverWarnings.value = [{ code: 'w' }] as never
    state.evidenceRefs.value = { bar: 1 } as never

    actions.resetGenerateState()

    expect(state.generating.value).toBe(false)
    expect(state.progress.value).toBe(0)
    expect(state.errorMessage.value).toBe('')
    expect(state.generatedCases.value).toEqual([])
    expect(state.currentCaseIndex.value).toBe(-1)
    expect(state.selectedCaseIndices.value.size).toBe(0)
    expect(state.caseIdSeq.value).toBe(0)
    expect(state.contextStats.value).toBeNull()
    expect(state.serverWarnings.value).toEqual([])
    expect(state.evidenceRefs.value).toBeNull()
    expect(state.currentStep.value).toBe(2)
    expect(state.formData.scene).toBe('场景')
  })
})

describe('createEditActions — 标签映射', () => {
  it('getPriorityType 覆盖 1..4 与未知值', () => {
    const { actions } = setup()
    expect(actions.getPriorityType(1)).toBe('danger')
    expect(actions.getPriorityType(2)).toBe('warning')
    expect(actions.getPriorityType(3)).toBe('info')
    expect(actions.getPriorityType(4)).toBe('success')
    expect(actions.getPriorityType(9)).toBe('info')
  })

  it('getSelectedTagType 优先缓存，其次 testPoints，缺失返回 primary', () => {
    const { state, actions } = setup()
    state.testPointCache.set(1, { id: 1, priority: 1 } as never)

    expect(actions.getSelectedTagType(1)).toBe('danger')

    state.testPoints.value = [{ id: 2, priority: 3 } as never]
    expect(actions.getSelectedTagType(2)).toBe('info')
    expect(actions.getSelectedTagType(3)).toBe('primary')
  })

  it('getTypeTagType / getTypeLabel 覆盖别名与兜底', () => {
    const { actions } = setup()
    expect(actions.getTypeTagType('ui_automation')).toBe('success')
    expect(actions.getTypeTagType('功能测试')).toBe('info')
    expect(actions.getTypeTagType('unknown')).toBe('info')

    expect(actions.getTypeLabel('ui_automation')).toBe('UI自动化')
    expect(actions.getTypeLabel('接口')).toBe('API自动化')
    expect(actions.getTypeLabel('未定义类型')).toBe('未定义类型')
  })

  it('getPriorityTagType / getPriorityLabel 兼容数字与 P 前缀', () => {
    const { actions } = setup()
    expect(actions.getPriorityTagType(1)).toBe('danger')
    expect(actions.getPriorityTagType('P2')).toBe('warning')
    expect(actions.getPriorityTagType('P9')).toBe('info')

    expect(actions.getPriorityLabel(1)).toBe('高(P0)')
    expect(actions.getPriorityLabel('P3')).toBe('P3-低')
    expect(actions.getPriorityLabel('P9')).toBe('P9')
  })

  it('getDataTypeLabel 映射三类数据并保留未知键', () => {
    const { actions } = setup()
    expect(actions.getDataTypeLabel('normal')).toBe('正向数据')
    expect(actions.getDataTypeLabel('boundary')).toBe('边界值')
    expect(actions.getDataTypeLabel(2)).toBe('2')
  })

  it('cleanExpectedResult 去掉【n】前缀，空串原样返回', () => {
    const { actions } = setup()
    expect(actions.cleanExpectedResult('【3】跳转成功')).toBe('跳转成功')
    expect(actions.cleanExpectedResult('跳转成功')).toBe('跳转成功')
    expect(actions.cleanExpectedResult('')).toBe('')
  })
})

describe('createEditActions — 流程编排回写', () => {
  it('handleFlowSortUpdate 同步屏幕 ID 并写回 flowSort store', () => {
    const { state, actions } = setup()
    const nodes = [
      { screen_id: 11, id: 'n1' },
      { screen_id: 12, id: 'n2' },
    ] as never
    const edges = [{ id: 'e1' }] as never

    actions.handleFlowSortUpdate({ mode: 'graph', nodes, edges })

    expect(state.formData.ui_screen_ids).toEqual([11, 12])
    expect(mockUpdateNodes).toHaveBeenCalledWith(nodes)
    expect(mockUpdateEdges).toHaveBeenCalledWith(edges)
    expect(mockTriggerAutoSave).toHaveBeenCalledTimes(1)
  })
})
