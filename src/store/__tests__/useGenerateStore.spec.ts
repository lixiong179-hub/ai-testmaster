import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockProjectApi, mockFileApi, mockCaseApi, mockTestPointApi, mockUiApi, mockFlowSort } =
  vi.hoisted(() => {
    const flowSort = {
      nodes: [] as unknown[],
      edges: [] as unknown[],
      quickMode: true,
      reset: vi.fn(),
      setProjectId: vi.fn(),
      updateNodes: vi.fn(),
      updateEdges: vi.fn(),
      triggerAutoSave: vi.fn(),
      loadFromBackend: vi.fn(),
    }
    return {
      mockProjectApi: { getProjects: vi.fn() },
      mockFileApi: {
        getFileList: vi.fn(),
        extractContent: vi.fn(),
        getPreviewScreen: vi.fn(),
      },
      mockCaseApi: { getCaseList: vi.fn(), createCase: vi.fn(), updateCase: vi.fn() },
      mockTestPointApi: { getList: vi.fn(), batchGenerateStream: vi.fn() },
      mockUiApi: {
        getUIPrototypeProjectList: vi.fn(),
        getUIScreenList: vi.fn(),
      },
      mockFlowSort: flowSort,
    }
  })

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
  ElMessageBox: { confirm: vi.fn() },
}))
vi.mock('@/api/project', () => ({ default: mockProjectApi }))
vi.mock('@/api/file', () => ({ fileApi: mockFileApi }))
vi.mock('@/api/case', () => ({
  default: mockCaseApi,
  caseApi: mockCaseApi,
  testCaseApi: mockCaseApi,
}))
vi.mock('@/api/testPoint', () => ({ testPointApi: mockTestPointApi }))
vi.mock('@/api/uiPrototype', () => ({ uiPrototypeApi: mockUiApi }))
vi.mock('@/store/flowSort', () => ({ useFlowSortStore: () => mockFlowSort }))

import { useGenerateStore } from '../useGenerateStore'

describe('useGenerateStore — 装配契约', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockFlowSort.nodes = []
    mockFlowSort.edges = []
  })

  it('暴露核心状态、派生值与动作', () => {
    const store = useGenerateStore()

    for (const key of [
      'currentStep',
      'generatedCases',
      'formData',
      'viewingCase',
      'canGenerate',
      'generateButtonLabel',
      'handleGenerate',
      'handleSaveCase',
      'handleProjectChange',
    ]) {
      expect(store).toHaveProperty(key)
    }
  })

  it('computed 与 action 共享同一份 state（下一步/选择切换即时反映）', () => {
    const store = useGenerateStore()

    store.nextStep()
    expect(store.currentStep).toBe(1)

    store.generatedCases = [{ title: 'A' }, { title: 'B' }] as never
    store.toggleCaseSelection(1)

    expect(store.hasSelected).toBe(true)
    expect(store.selectedCount).toBe(1)
    expect([...store.selectedCaseIndices]).toEqual([1])
  })

  it('handleProjectChange 通过自引用 getActions 扇出下游加载', async () => {
    const store = useGenerateStore()
    store.formData.project_id = 7
    mockFileApi.getFileList.mockResolvedValue({ data: { items: [] } })
    mockTestPointApi.getList.mockResolvedValue({ items: [], total: 0 })
    mockUiApi.getUIPrototypeProjectList.mockResolvedValue({ items: [] })
    mockCaseApi.getCaseList.mockResolvedValue({ data: { items: [], total: 0 } })

    store.handleProjectChange()
    await Promise.resolve()
    await Promise.resolve()

    expect(mockFlowSort.setProjectId).toHaveBeenCalledWith(7)
    expect(mockFileApi.getFileList).toHaveBeenCalledWith(7)
    expect(mockTestPointApi.getList).toHaveBeenCalled()
    expect(mockUiApi.getUIPrototypeProjectList).toHaveBeenCalledWith(7)
  })

  it('resetForm 复位步骤与用例（跨 action 一致性）', () => {
    const store = useGenerateStore()
    store.currentStep = 2
    store.generatedCases = [{ title: 'A' }] as never
    store.currentCaseIndex = 0

    store.resetForm()

    expect(store.currentStep).toBe(0)
    expect(store.generatedCases).toEqual([])
    expect(store.currentCaseIndex).toBe(-1)
  })
})
