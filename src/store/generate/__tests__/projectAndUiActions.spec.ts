import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGenerateState, type GenerateState } from '../state'
import { createProjectActions } from '../projectActions'
import { createUiPrototypeActions } from '../uiPrototypeActions'

const {
  mockMessage,
  mockGetProjects,
  mockGetFileList,
  mockExtractContent,
  mockGetPreviewScreen,
  mockGetCaseList,
  mockGetUIPrototypeList,
  mockGetUIScreenList,
  mockFlowSort,
} = vi.hoisted(() => {
  const flowSort = {
    nodes: [] as Array<Record<string, unknown>>,
    edges: [] as Array<Record<string, unknown>>,
    reset: vi.fn(),
    setProjectId: vi.fn(),
    updateNodes: vi.fn(),
    updateEdges: vi.fn(),
    loadFromBackend: vi.fn(),
  }
  return {
    mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
    mockGetProjects: vi.fn(),
    mockGetFileList: vi.fn(),
    mockExtractContent: vi.fn(),
    mockGetPreviewScreen: vi.fn(),
    mockGetCaseList: vi.fn(),
    mockGetUIPrototypeList: vi.fn(),
    mockGetUIScreenList: vi.fn(),
    mockFlowSort: flowSort,
  }
})

vi.mock('element-plus', () => ({ ElMessage: mockMessage }))
vi.mock('@/api/project', () => ({ default: { getProjects: mockGetProjects } }))
vi.mock('@/api/file', () => ({
  fileApi: {
    getFileList: mockGetFileList,
    extractContent: mockExtractContent,
    getPreviewScreen: mockGetPreviewScreen,
  },
}))
vi.mock('@/api/case', () => ({ default: { getCaseList: mockGetCaseList } }))
vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: {
    getUIPrototypeProjectList: mockGetUIPrototypeList,
    getUIScreenList: mockGetUIScreenList,
  },
}))
vi.mock('@/store/flowSort', () => ({ useFlowSortStore: () => mockFlowSort }))

function setupProject() {
  const state: GenerateState = createGenerateState()
  const downstream = {
    handleSourceFileChange: vi.fn(),
    loadProjectFiles: vi.fn(),
    loadUIPrototypeProjects: vi.fn(),
    loadProjectCases: vi.fn(),
    loadTestPoints: vi.fn(),
  }
  const actions = createProjectActions(state, () => downstream as never)
  return { state, actions, downstream }
}

function setupUi() {
  const state: GenerateState = createGenerateState()
  const downstream = { loadUIScreens: vi.fn().mockResolvedValue(undefined) }
  const actions = createUiPrototypeActions(state, () => downstream as never)
  return { state, actions, downstream }
}

describe('createProjectActions — 项目与文件加载', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFlowSort.nodes = []
    mockFlowSort.edges = []
  })

  it('getProjects 已加载且非强制刷新时跳过请求', async () => {
    const { state, actions } = setupProject()
    state.projectsLoaded.value = true
    state.projects.value = [{ id: 1 }] as never

    await actions.getProjects()

    expect(mockGetProjects).not.toHaveBeenCalled()
  })

  it('getProjects 过滤「默认项目」并置已加载标记', async () => {
    const { state, actions } = setupProject()
    mockGetProjects.mockResolvedValueOnce({
      data: {
        items: [
          { id: 1, name: '项目A' },
          { id: 2, name: '默认项目' },
        ],
      },
    })

    await actions.getProjects()

    expect(state.projects.value.map((p) => p.name)).toEqual(['项目A'])
    expect(state.projectsLoaded.value).toBe(true)
    expect(state.projectsLoading.value).toBe(false)
  })

  it('getProjects 异常时只记录日志且复位 loading', async () => {
    const { state, actions } = setupProject()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    mockGetProjects.mockRejectedValueOnce(new Error('boom'))

    await actions.getProjects()

    expect(state.projectsLoading.value).toBe(false)
    spy.mockRestore()
  })

  it('loadProjectFiles 按 resource_type 拆分需求与 UI 文件', async () => {
    const { state, actions } = setupProject()
    state.formData.project_id = 3
    mockGetFileList.mockResolvedValueOnce({
      data: {
        items: [
          { id: 1, resource_type: 'requirement' },
          { id: 2, resource_type: 'ui_mockup' },
          { id: 3, resource_type: 'other' },
        ],
      },
    })

    await actions.loadProjectFiles()

    expect(state.requirementFiles.value.map((f) => f.id)).toEqual([1])
    expect(state.uiFiles.value.map((f) => f.id)).toEqual([2])
  })

  it('loadProjectCases 未选项目时清空列表且不发请求', async () => {
    const { state, actions } = setupProject()
    state.projectCases.value = [{ id: 1 }] as never

    await actions.loadProjectCases()

    expect(state.projectCases.value).toEqual([])
    expect(mockGetCaseList).not.toHaveBeenCalled()
  })

  it('loadProjectCases 失败时清空列表并复位 loading', async () => {
    const { state, actions } = setupProject()
    const spy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    state.formData.project_id = 3
    mockGetCaseList.mockRejectedValueOnce(new Error('boom'))

    await actions.loadProjectCases()

    expect(state.projectCases.value).toEqual([])
    expect(state.isLoadingProjectCases.value).toBe(false)
    spy.mockRestore()
  })

  it('handleProjectChange 重置上下文并扇出下游加载', async () => {
    const { state, actions, downstream } = setupProject()
    state.formData.project_id = 8
    state.formData.requirement_file_ids = [1]
    state.formData.ui_file_ids = [2]
    state.formData.ui_screen_ids = [3]
    state.formData.test_point_ids = [4]
    state.contextPreview.value = { title: 't' } as never
    state.lastContext.value = { a: 1 }
    state.generatedCases.value = [{ title: 'A' }] as never
    state.currentCaseIndex.value = 0
    state.selectedUiPrototypeProjectId.value = 5
    state.uiPrototypeProjects.value = [{ id: 5 }] as never
    state.uiScreens.value = [{ id: 6 }] as never
    state.selectedHistoryCaseIds.value = [7]
    state._historyCaseUserCleared.value = true

    actions.handleProjectChange()

    expect(state.formData.requirement_file_ids).toEqual([])
    expect(state.formData.ui_file_ids).toEqual([])
    expect(state.formData.ui_screen_ids).toEqual([])
    expect(state.formData.test_point_ids).toEqual([])
    expect(state.contextPreview.value).toBeNull()
    expect(state.lastContext.value).toEqual({})
    expect(state.generatedCases.value).toEqual([])
    expect(state.currentCaseIndex.value).toBe(-1)
    expect(state.selectedUiPrototypeProjectId.value).toBe('')
    expect(state.uiPrototypeProjects.value).toEqual([])
    expect(state.uiScreens.value).toEqual([])
    expect(state.selectedHistoryCaseIds.value).toEqual([])
    expect(state._historyCaseUserCleared.value).toBe(false)
    expect(state.projectCases.value).toEqual([])

    expect(mockFlowSort.reset).toHaveBeenCalledTimes(1)
    expect(mockFlowSort.setProjectId).toHaveBeenCalledWith(8)
    expect(downstream.handleSourceFileChange).toHaveBeenCalledTimes(1)
    expect(downstream.loadProjectFiles).toHaveBeenCalledTimes(1)
    expect(downstream.loadUIPrototypeProjects).toHaveBeenCalledTimes(1)
    expect(downstream.loadProjectCases).toHaveBeenCalledTimes(1)
    expect(downstream.loadTestPoints).toHaveBeenCalledWith(1)
  })

  it('handleProjectChange 未选项目时不设置项目 ID', () => {
    const { state, actions } = setupProject()
    state.formData.project_id = ''

    actions.handleProjectChange()

    expect(mockFlowSort.setProjectId).not.toHaveBeenCalled()
  })

  it('handleProjectFocus 仅在未加载或空列表时触发加载', () => {
    const { actions } = setupProject()
    mockGetProjects.mockResolvedValue({ data: { items: [] } })

    actions.handleProjectFocus()
    expect(mockGetProjects).toHaveBeenCalledTimes(1)
  })

  it('extractFileContent 未选文件时告警', async () => {
    const { actions } = setupProject()

    await actions.extractFileContent()

    expect(mockMessage.warning).toHaveBeenCalledWith('请先选择文件')
  })

  it('extractFileContent 成功时刷新文件并给出预览摘要', async () => {
    const { state, actions, downstream } = setupProject()
    state.formData.project_id = 3
    state.formData.requirement_file_ids = [1, 2]
    // 真实响应被 request 拦截器包了一层 data，业务 code 在里层
    mockExtractContent.mockResolvedValueOnce({
      data: { code: 200, data: { success: 2, failed: 0 } },
    })

    await actions.extractFileContent()

    expect(downstream.loadProjectFiles).toHaveBeenCalledTimes(1)
    expect(state.contextPreview.value).toMatchObject({
      title: '内容提取完成：成功 2 个，失败 0 个',
      type: 'success',
      requirement: '选择了 2 个文件',
    })
    expect(mockMessage.success).toHaveBeenCalledWith('文件内容提取完成')
  })

  it('extractFileContent 有失败文件时预览类型为 warning', async () => {
    const { state, actions } = setupProject()
    state.formData.project_id = 3
    state.formData.requirement_file_ids = [1]
    mockExtractContent.mockResolvedValueOnce({
      data: { code: 200, data: { success: 0, failed: 1 } },
    })

    await actions.extractFileContent()

    expect(state.contextPreview.value?.type).toBe('warning')
  })

  it('extractFileContent 业务失败时展示后端消息', async () => {
    const { state, actions } = setupProject()
    state.formData.project_id = 3
    state.formData.requirement_file_ids = [1]
    mockExtractContent.mockResolvedValueOnce({ data: { code: 500, msg: '解析服务不可用' } })

    await actions.extractFileContent()

    expect(mockMessage.error).toHaveBeenCalledWith('解析服务不可用')
  })
})

describe('createUiPrototypeActions — 原型与屏幕', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFlowSort.nodes = []
    mockFlowSort.edges = []
  })

  it('loadUIPrototypeProjects 未选项目时不发请求', async () => {
    const { actions } = setupUi()

    await actions.loadUIPrototypeProjects()

    expect(mockGetUIPrototypeList).not.toHaveBeenCalled()
  })

  it('loadUIPrototypeProjects 解析列表包络', async () => {
    const { state, actions } = setupUi()
    state.formData.project_id = 1
    mockGetUIPrototypeList.mockResolvedValueOnce({ data: { items: [{ id: 1 }] } })

    await actions.loadUIPrototypeProjects()

    expect(state.uiPrototypeProjects.value).toHaveLength(1)
  })

  it('loadUIScreens 按 screen_order 升序并清理旧图片', async () => {
    const { state, actions } = setupUi()
    state.formData.project_id = 1
    state.uiScreens.value = [
      { id: 1, screen_order: 2 },
      { id: 2, screen_order: 1 },
    ] as never
    mockGetUIScreenList.mockResolvedValueOnce({
      items: [
        { id: 11, screen_order: 3 },
        { id: 12, screen_order: 1 },
        { id: 13, screen_order: 2 },
      ],
    })

    await actions.loadUIScreens(9)

    expect(state.uiScreens.value.map((s) => s.id)).toEqual([12, 13, 11])
    expect(state.screenImageUrls.value).toEqual({})
  })

  it('loadUIScreens 异常时清空屏幕与图片', async () => {
    const { state, actions } = setupUi()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    state.formData.project_id = 1
    state.uiScreens.value = [{ id: 1 }] as never
    mockGetUIScreenList.mockRejectedValueOnce(new Error('boom'))

    await actions.loadUIScreens(9)

    expect(state.uiScreens.value).toEqual([])
    expect(state.screenImageUrls.value).toEqual({})
    spy.mockRestore()
  })

  it('cleanupScreenImages 仅回收 blob URL 并清空映射', () => {
    const { state, actions } = setupUi()
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    state.screenImageUrls.value = { 1: 'blob:abc', 2: 'https://cdn/x.png' }

    actions.cleanupScreenImages()

    expect(revoke).toHaveBeenCalledWith('blob:abc')
    expect(revoke).toHaveBeenCalledTimes(1)
    expect(state.screenImageUrls.value).toEqual({})
    revoke.mockRestore()
  })

  it('loadScreenImages 加载中重入直接返回', async () => {
    const { state, actions } = setupUi()
    state.isLoadingScreenImages.value = true

    await actions.loadScreenImages()

    expect(mockGetPreviewScreen).not.toHaveBeenCalled()
  })

  it('handleUIPrototypeProjectChange 清空后按新项目重建屏幕选择', async () => {
    const { state, actions, downstream } = setupUi()
    state.formData.project_id = 1
    state.lastContext.value = { a: 1 }
    state.uiScreens.value = [{ id: 5 }] as never
    state.formData.ui_screen_ids = [5]
    downstream.loadUIScreens.mockImplementationOnce(async () => {
      state.uiScreens.value = [{ id: 21 }, { id: 22 }] as never
    })

    await actions.handleUIPrototypeProjectChange(9)

    expect(state.selectedUiPrototypeProjectId.value).toBe(9)
    expect(state.lastContext.value).toEqual({})
    expect(mockFlowSort.reset).toHaveBeenCalled()
    expect(mockFlowSort.setProjectId).toHaveBeenCalledWith(1)
    expect(downstream.loadUIScreens).toHaveBeenCalledWith(9)
    expect(mockFlowSort.loadFromBackend).toHaveBeenCalledTimes(1)
    expect(state.formData.ui_screen_ids).toEqual([21, 22])
  })

  it('handleUIPrototypeProjectChange 传空值时仅重置 flowSort', async () => {
    const { state, actions, downstream } = setupUi()
    state.formData.project_id = 1

    await actions.handleUIPrototypeProjectChange('')

    expect(state.selectedUiPrototypeProjectId.value).toBe('')
    expect(downstream.loadUIScreens).not.toHaveBeenCalled()
    expect(mockFlowSort.reset).toHaveBeenCalledTimes(2)
  })
})
