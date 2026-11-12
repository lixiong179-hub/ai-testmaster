import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createGenerateState, type GenerateState } from '../state'
import { createGenerateComputed, type GenerateComputed } from '../computed'
import { createGenerateActions } from '../generateActions'

const { mockMessage, mockConfirm, mockCaseApi, mockForTestPoints, mockForFlowNodes, mockFlowSort } =
  vi.hoisted(() => ({
    mockMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() },
    mockConfirm: vi.fn(),
    mockCaseApi: { generateContext: vi.fn() },
    mockForTestPoints: vi.fn(),
    mockForFlowNodes: vi.fn(),
    mockFlowSort: { quickMode: true, nodes: [] as unknown[] },
  }))

vi.mock('element-plus', () => ({
  ElMessage: mockMessage,
  ElMessageBox: { confirm: mockConfirm },
}))
vi.mock('@/api/case', () => ({ caseApi: mockCaseApi, default: mockCaseApi }))
vi.mock('@/store/flowSort', () => ({ useFlowSortStore: () => mockFlowSort }))
vi.mock('../generateHelpers', () => ({
  generateForTestPoints: mockForTestPoints,
  generateForFlowNodes: mockForFlowNodes,
}))

function setup() {
  const state: GenerateState = createGenerateState()
  const computed: GenerateComputed = createGenerateComputed(state)
  const actions = createGenerateActions(state, computed, () => ({}) as never)
  return { state, computed, actions }
}

describe('createGenerateActions — 失败建议', () => {
  it('认证类错误给出 API Key 排查清单', () => {
    const { state, actions } = setup()
    state.errorMessage.value = 'Authentication failed: invalid api key'

    actions.generateErrorSuggestions()

    expect(state.errorSuggestions.value).toHaveLength(4)
    expect(state.errorSuggestions.value[0]).toContain('DEEPSEEK_API_KEY')
  })

  it('频率类错误给出限流建议', () => {
    const { state, actions } = setup()
    state.errorMessage.value = '429 rate limit exceeded'

    actions.generateErrorSuggestions()

    expect(state.errorSuggestions.value).toHaveLength(3)
    expect(state.errorSuggestions.value[0]).toContain('请求频率过高')
  })

  it('未知错误给出通用建议', () => {
    const { state, actions } = setup()
    state.errorMessage.value = 'something unexpected'

    actions.generateErrorSuggestions()

    expect(state.errorSuggestions.value).toHaveLength(5)
  })
})

describe('createGenerateActions — 校验弹窗', () => {
  it('showValidationDialog 打开弹窗并由确认回传 true', async () => {
    const { state, actions } = setup()

    const pending = actions.showValidationDialog({ errors: ['缺少起点'], warnings: [] })
    expect(state.issueDialogVisible.value).toBe(true)
    expect(state.issueDialogValidation.value.errors).toEqual(['缺少起点'])

    actions.onIssueDialogConfirm()

    await expect(pending).resolves.toBe(true)
    expect(state.issueDialogVisible.value).toBe(false)
    expect(state.issueDialogResolver.value).toBeNull()
  })

  it('取消回传 false', async () => {
    const { state, actions } = setup()

    const pending = actions.showValidationDialog({ errors: [], warnings: ['存在孤立节点'] })
    actions.onIssueDialogCancel()

    await expect(pending).resolves.toBe(false)
    expect(state.issueDialogVisible.value).toBe(false)
  })
})

describe('createGenerateActions — handleGenerate', () => {
  let state: GenerateState
  let actions: ReturnType<typeof createGenerateActions>

  beforeEach(() => {
    vi.clearAllMocks()
    mockFlowSort.quickMode = true
    mockFlowSort.nodes = []
    ;({ state, actions } = setup())
  })

  it('无任何上下文时告警且不进入生成流程', async () => {
    await actions.handleGenerate(null)

    expect(mockMessage.warning).toHaveBeenCalledWith('请先选择测试点、需求文档、UI原型图或历史用例')
    expect(state.generating.value).toBe(false)
  })

  it('测试点超过 20 个需二次确认，取消则不生成', async () => {
    state.formData.test_point_ids = Array.from({ length: 21 }, (_, i) => i + 1)
    mockConfirm.mockRejectedValueOnce(new Error('cancel'))

    await actions.handleGenerate(null)

    expect(mockConfirm).toHaveBeenCalledTimes(1)
    expect(mockForTestPoints).not.toHaveBeenCalled()
    expect(state.generating.value).toBe(false)
  })

  it('无测试点时确认后走流程节点生成', async () => {
    state.formData.requirement_file_ids = [1]
    mockConfirm.mockResolvedValueOnce('confirm')
    mockForFlowNodes.mockImplementationOnce(async (s: GenerateState) => {
      s.generatedCases.value = [{ title: 'A' }] as never
    })

    await actions.handleGenerate(null)

    expect(mockForFlowNodes).toHaveBeenCalledTimes(1)
    expect(state.currentCaseIndex.value).toBe(0)
    expect(state.progress.value).toBe(100)
    expect(mockMessage.success).toHaveBeenCalledWith('成功生成 1 条测试用例')
  })

  it('有失败用例时给出成功/失败统计警告', async () => {
    state.formData.test_point_ids = [1, 2]
    mockForTestPoints.mockImplementationOnce(async (s: GenerateState) => {
      s.generatedCases.value = [{ title: 'A' }, { title: 'B', _error: 'boom' }] as never
    })

    await actions.handleGenerate(null)

    expect(mockMessage.warning).toHaveBeenCalledWith('生成完成：1 成功，1 失败')
  })

  it('生成上下文并写入 contextStats / warnings / evidenceRefs', async () => {
    state.formData.project_id = 9
    state.formData.test_point_ids = [1]
    mockCaseApi.generateContext.mockResolvedValueOnce({
      data: {
        requirement_content: '需求正文',
        ui_descriptions: [{ screen: '首页' }],
        ui_specs: [{ a: 1 }],
        test_points: [{ id: 1 }],
        history_cases: [{ id: 2 }],
        context_stats: { tokens: 100 },
        warnings: [{ code: 'W1' }],
        evidence_refs: { note: 'ref' },
      },
    })
    mockForTestPoints.mockImplementationOnce(async (s: GenerateState) => {
      s.generatedCases.value = [{ title: 'A' }] as never
    })

    await actions.handleGenerate(null)

    expect(mockCaseApi.generateContext).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 9, test_point_ids: [1] })
    )
    expect(state.lastContext.value).toMatchObject({ requirement_content: '需求正文' })
    expect(state.contextStats.value).toEqual({ tokens: 100 })
    expect(state.serverWarnings.value).toEqual([{ code: 'W1' }])
    expect(state.evidenceRefs.value).toEqual({ note: 'ref' })
  })

  it('生成中途被取消时保留已生成数量文案', async () => {
    state.formData.test_point_ids = [1]
    mockForTestPoints.mockImplementationOnce(async (s: GenerateState) => {
      s.generatedCases.value = [{ title: 'A' }] as never
      s.generating.value = false
    })

    await actions.handleGenerate(null)

    expect(state.progressText.value).toBe('已取消，已生成 1 条')
    expect(mockMessage.success).not.toHaveBeenCalled()
  })

  it('生成异常时记录错误、填充建议并提示', async () => {
    state.formData.project_id = 9
    state.formData.test_point_ids = [1]
    mockCaseApi.generateContext.mockRejectedValueOnce({
      response: { data: { detail: 'AI 服务不可用' } },
    })

    await actions.handleGenerate(null)

    expect(state.progressText.value).toBe('生成失败')
    expect(state.errorMessage.value).toBe('AI 服务不可用')
    expect(state.errorSuggestions.value.length).toBeGreaterThan(0)
    expect(mockMessage.error).toHaveBeenCalledWith('AI 服务不可用')
    expect(state.generating.value).toBe(false)
  })

  it('流程校验有错误且用户不确认时中断', async () => {
    state.formData.ui_screen_ids = [1]
    state.formData.test_point_ids = [1]
    state.selectedUiPrototypeProjectId.value = 5
    state.uiScreens.value = [{ id: 1 }] as never
    mockFlowSort.quickMode = false
    const editorRef = {
      getFlowValidationIssues: () => ({ errors: ['缺少起点'], warnings: [] }),
    }

    await expect(
      (async () => {
        const pending = actions.handleGenerate(editorRef as never)
        // 弹窗打开后取消
        await Promise.resolve()
        actions.onIssueDialogCancel()
        await pending
      })()
    ).resolves.toBeUndefined()

    expect(mockForTestPoints).not.toHaveBeenCalled()
    expect(state.generating.value).toBe(false)
  })
})
