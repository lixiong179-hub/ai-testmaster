import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGenerateState, type GenerateState } from '../state'
import { createGenerateComputed, type GenerateComputed } from '../computed'
import { createCaseActions } from '../caseActions'

const { mockConfirm, mockMessage, mockCaseApi, mockFlowSortStore, mockSaveSingle } = vi.hoisted(
  () => ({
    mockConfirm: vi.fn(),
    mockMessage: {
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    },
    mockCaseApi: {
      aiGenerateCaseEnhanced: vi.fn(),
      deleteCase: vi.fn(),
      batchDeleteCases: vi.fn(),
    },
    mockFlowSortStore: { quickMode: true, nodes: [] as unknown[] },
    mockSaveSingle: vi.fn(),
  })
)

vi.mock('element-plus', () => ({
  ElMessage: mockMessage,
  ElMessageBox: { confirm: mockConfirm },
}))
vi.mock('@/api/case', () => ({ default: mockCaseApi }))
vi.mock('@/store/flowSort', () => ({ useFlowSortStore: () => mockFlowSortStore }))

function setup() {
  const state: GenerateState = createGenerateState()
  const computed: GenerateComputed = createGenerateComputed(state)
  // getActions 存在自引用（批量重新生成会回调 handleRegenerateCase），用可变持有者打通
  const holder: Record<string, unknown> = { saveSingleCaseToDb: mockSaveSingle }
  const actions = createCaseActions(state, computed, () => holder as never)
  Object.assign(holder, actions)
  return { state, computed, actions }
}

function seedCases(state: GenerateState, count = 3) {
  state.generatedCases.value = Array.from({ length: count }, (_, i) => ({
    title: `用例${i}`,
    module: 'M',
    steps: [],
    priority: 2,
    _dbId: 100 + i,
  })) as never
}

describe('createCaseActions — 删除单条', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createCaseActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setup())
  })

  it('索引无效时静默返回', async () => {
    await actions.handleDeleteCase(5)
    expect(mockConfirm).not.toHaveBeenCalled()
  })

  it('用户取消确认时不删除', async () => {
    seedCases(state)
    mockConfirm.mockRejectedValueOnce(new Error('cancel'))

    await actions.handleDeleteCase(0)

    expect(state.generatedCases.value).toHaveLength(3)
    expect(mockCaseApi.deleteCase).not.toHaveBeenCalled()
  })

  it('已入库用例：先删库再移除内存项，并修正选择集索引', async () => {
    seedCases(state)
    state.selectedCaseIndices.value = new Set([0, 1, 2])
    state.currentCaseIndex.value = 1
    state.formData.project_id = 10
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.deleteCase.mockResolvedValueOnce(undefined)

    await actions.handleDeleteCase(0)

    expect(mockCaseApi.deleteCase).toHaveBeenCalledWith(100, 10)
    expect(state.generatedCases.value.map((c) => c.title)).toEqual(['用例1', '用例2'])
    expect([...state.selectedCaseIndices.value].sort()).toEqual([0, 1])
    expect(mockMessage.success).toHaveBeenCalledWith('用例已删除')
  })

  it('删库失败时保留用例并提示', async () => {
    seedCases(state)
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.deleteCase.mockRejectedValueOnce(new Error('500'))

    await actions.handleDeleteCase(0)

    expect(state.generatedCases.value).toHaveLength(3)
    expect(mockMessage.error).toHaveBeenCalledWith('数据库删除失败，请稍后重试')
  })

  it('未入库用例直接移除；删除后空列表重置索引为 -1', async () => {
    seedCases(state, 1)
    state.generatedCases.value[0]._dbId = undefined
    state.currentCaseIndex.value = 0
    mockConfirm.mockResolvedValueOnce('confirm')

    await actions.handleDeleteCase(0)

    expect(mockCaseApi.deleteCase).not.toHaveBeenCalled()
    expect(state.generatedCases.value).toEqual([])
    expect(state.currentCaseIndex.value).toBe(-1)
  })

  it('删除后当前索引越界时收敛到最后一条', async () => {
    seedCases(state, 2)
    state.currentCaseIndex.value = 1
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.deleteCase.mockResolvedValueOnce(undefined)

    await actions.handleDeleteCase(1)

    expect(state.currentCaseIndex.value).toBe(0)
  })
})

describe('createCaseActions — 批量删除', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createCaseActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setup())
  })

  it('未选择时给出警告且不弹确认', async () => {
    await actions.handleDeleteSelected()
    expect(mockMessage.warning).toHaveBeenCalledWith('请先选择要删除的用例')
    expect(mockConfirm).not.toHaveBeenCalled()
  })

  it('按降序索引删除，避免位移错位', async () => {
    seedCases(state)
    state.selectedCaseIndices.value = new Set([0, 2])
    state.formData.project_id = 10
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.batchDeleteCases.mockResolvedValueOnce(undefined)

    await actions.handleDeleteSelected()

    expect(mockCaseApi.batchDeleteCases).toHaveBeenCalledWith([102, 100], 10)
    expect(state.generatedCases.value.map((c) => c.title)).toEqual(['用例1'])
    expect(state.selectedCaseIndices.value.size).toBe(0)
    expect(mockMessage.success).toHaveBeenCalledWith('已删除 2 条用例')
  })

  it('批量删库失败时保留全部用例并提示', async () => {
    seedCases(state)
    state.selectedCaseIndices.value = new Set([1])
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.batchDeleteCases.mockRejectedValueOnce(new Error('500'))

    await actions.handleDeleteSelected()

    expect(state.generatedCases.value).toHaveLength(3)
    expect(mockMessage.error).toHaveBeenCalledWith('数据库批量删除失败，请稍后重试')
  })
})

describe('createCaseActions — 重新生成', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createCaseActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setup())
  })

  it('索引无效时直接返回', async () => {
    await actions.handleRegenerateCase(0)
    expect(mockCaseApi.aiGenerateCaseEnhanced).not.toHaveBeenCalled()
  })

  it('成功：覆盖内存用例、重新入库、清理旧记录并置进度 100', async () => {
    seedCases(state, 1)
    state.formData.project_id = 10
    state.formData.case_type = 'ui_automation'
    state.formData.priority = 1
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.aiGenerateCaseEnhanced.mockResolvedValueOnce({
      cases: [{ title: '新用例', module: '新模块', steps: [{ step: 1 }], priority: 3 }],
    })
    mockSaveSingle.mockResolvedValueOnce(true)
    mockCaseApi.deleteCase.mockResolvedValueOnce(undefined)

    await actions.handleRegenerateCase(0)

    const updated = state.generatedCases.value[0]
    expect(updated).toMatchObject({
      title: '新用例',
      module: '新模块',
      priority: 3,
      _saved: false,
      ai_change_type: 'added',
    })
    expect(updated._dbId).toBeUndefined()
    expect(mockSaveSingle).toHaveBeenCalledTimes(1)
    expect(mockCaseApi.deleteCase).toHaveBeenCalledWith(100, 10)
    expect(state.progress.value).toBe(100)
    expect(state.generating.value).toBe(false)
    expect(mockMessage.success).toHaveBeenCalledWith('用例重新生成成功')
  })

  it('AI 未返回用例数据：提示错误且保持 generating=false', async () => {
    seedCases(state, 1)
    mockCaseApi.aiGenerateCaseEnhanced.mockResolvedValueOnce({ cases: [] })

    await actions.handleRegenerateCase(0, true)

    expect(mockMessage.error).toHaveBeenCalledWith('AI 未返回有效用例数据')
    expect(state.generating.value).toBe(false)
  })

  it('保存失败时标记 _error', async () => {
    seedCases(state, 1)
    mockCaseApi.aiGenerateCaseEnhanced.mockResolvedValueOnce({
      cases: [{ title: '新用例' }],
    })
    mockSaveSingle.mockResolvedValueOnce(false)

    await actions.handleRegenerateCase(0, true)

    expect(state.generatedCases.value[0]._error).toBe('保存失败')
  })

  it('preserveGenerating=true 时保留生成中状态（供批量场景串行）', async () => {
    seedCases(state, 1)
    mockCaseApi.aiGenerateCaseEnhanced.mockResolvedValueOnce({ cases: [{ title: 'X' }] })
    mockSaveSingle.mockResolvedValueOnce(true)

    await actions.handleRegenerateCase(0, true, true)

    expect(state.generating.value).toBe(true)
  })
})

describe('createCaseActions — 批量重新生成与取消', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createCaseActions>

  beforeEach(() => {
    vi.clearAllMocks()
    ;({ state, actions } = setup())
  })

  it('未选择时警告', async () => {
    await actions.handleRegenerateSelected()
    expect(mockMessage.warning).toHaveBeenCalledWith('请先选择要重新生成的用例')
  })

  it('批量重新生成按升序逐条串行执行', async () => {
    seedCases(state)
    state.selectedCaseIndices.value = new Set([2, 0])
    mockConfirm.mockResolvedValueOnce('confirm')
    mockCaseApi.aiGenerateCaseEnhanced.mockResolvedValue({ cases: [{ title: '新' }] })
    mockSaveSingle.mockResolvedValue(true)

    await actions.handleRegenerateSelected()

    expect(mockCaseApi.aiGenerateCaseEnhanced).toHaveBeenCalledTimes(2)
    expect(state.generating.value).toBe(false)
  })

  it('生成中取消：确认后复位进度文案与错误', async () => {
    state.generating.value = true
    state.progressText.value = '生成中'
    state.errorMessage.value = '旧错误'
    mockConfirm.mockResolvedValueOnce('confirm')

    await actions.handleCancel()
    await Promise.resolve()
    await Promise.resolve()

    expect(state.generating.value).toBe(false)
    expect(state.progressText.value).toBe('已取消')
    expect(state.errorMessage.value).toBe('')
    expect(mockMessage.info).toHaveBeenCalledWith('生成已取消')
  })

  it('非生成中取消为空操作', async () => {
    await actions.handleCancel()
    expect(mockConfirm).not.toHaveBeenCalled()
  })
})
