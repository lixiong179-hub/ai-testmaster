import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { silenceElMessage } from '@/test-utils'
import type {
  XmindImportResponse,
  XmindPreviewCaseItem,
  XmindPreviewItem,
  XmindPreviewResponse,
  XmindImportProgressEvent,
} from '@/api/testPoint'

const mocks = vi.hoisted(() => ({
  importXmind: vi.fn(),
  importXmindStream: vi.fn(),
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: {
    importXmind: mocks.importXmind,
    importXmindStream: mocks.importXmindStream,
  },
}))

import { useXmindImport } from '../useXmindImport'

const PROJECT_ID = 9

function makePoint(overrides: Partial<XmindPreviewItem> = {}): XmindPreviewItem {
  return {
    module: '登录',
    point: '登录成功',
    priority: 1,
    ...overrides,
  } as XmindPreviewItem
}

function makeCase(overrides: Partial<XmindPreviewCaseItem> = {}): XmindPreviewCaseItem {
  return {
    title: '登录用例',
    module: '登录',
    priority: 2,
    steps: [
      { step_number: 1, display_action: '输入账号', action: 'input' },
      { step_number: 2, display_action: '', description: '点击登录', action: 'click' },
      { step_number: 3, display_action: '', description: '', action: 'submit' },
    ],
    ...overrides,
  } as XmindPreviewCaseItem
}

function makePreview(overrides: Partial<XmindPreviewResponse> = {}): XmindPreviewResponse {
  return {
    preview_mode: 'test_points',
    items: [makePoint(), makePoint({ priority: 2 }), makePoint({ priority: 3 })],
    case_items: [],
    skipped_count: 2,
    skipped_reasons: ['缺少模块'],
    ai_timeout: false,
    total_paths: 5,
    ...overrides,
  } as XmindPreviewResponse
}

function makeImportResult(overrides: Partial<XmindImportResponse> = {}): XmindImportResponse {
  return {
    saved_count: 3,
    saved_case_count: 1,
    total_parsed: 4,
    skipped_count: 1,
    skipped_reasons: ['重复'],
    ai_timeout: false,
    ...overrides,
  } as XmindImportResponse
}

function progressEvent(
  overrides: Partial<XmindImportProgressEvent> = {}
): XmindImportProgressEvent {
  return {
    status: 'running',
    completed_batches: 1,
    total_batches: 3,
    percentage: 33,
    ...overrides,
  } as XmindImportProgressEvent
}

let file: File
/** AI 流式回调里需要读取的上下文（在用例内赋值） */
let streamCtx: ReturnType<typeof useXmindImport>

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  file = new File(['xmind'], 'cases.xmind')
})

describe('useXmindImport — 初始状态与计算属性', () => {
  it('初始状态为上传步骤且默认预览测试点', () => {
    const ctx = useXmindImport(PROJECT_ID)

    expect(ctx.currentStep.value).toBe(0)
    expect(ctx.previewMode.value).toBe('test_points')
    expect(ctx.activePreviewTab.value).toBe('points')
    expect(ctx.pageSize).toBe(20)
    expect(ctx.previewData.value).toEqual([])
    expect(ctx.importResult.value.success).toBe(false)
  })

  it('按 20 条分页截取测试点与用例', () => {
    const ctx = useXmindImport(PROJECT_ID)
    ctx.previewData.value = Array.from({ length: 25 }, (_, i) => makePoint({ point: `p${i}` }))
    ctx.previewCaseData.value = Array.from({ length: 22 }, (_, i) => makeCase({ title: `c${i}` }))

    expect(ctx.paginatedPreviewData.value).toHaveLength(20)
    expect(ctx.paginatedPreviewCases.value).toHaveLength(20)

    ctx.currentPage.value = 2
    expect(ctx.paginatedPreviewData.value).toHaveLength(5)
    expect(ctx.paginatedPreviewCases.value).toHaveLength(2)
  })

  it('存在用例数据时开启用例预览展示', () => {
    const ctx = useXmindImport(PROJECT_ID)
    expect(ctx.hasCasePreview.value).toBe(false)

    ctx.previewCaseData.value = [makeCase()]
    expect(ctx.hasCasePreview.value).toBe(true)

    ctx.previewMode.value = 'test_cases'
    expect(ctx.isCasePreviewMode.value).toBe(true)
  })

  it('当前预览总数跟随激活页签', () => {
    const ctx = useXmindImport(PROJECT_ID)
    ctx.previewData.value = [makePoint(), makePoint()]
    ctx.previewCaseData.value = [makeCase()]

    expect(ctx.currentPreviewTotal.value).toBe(2)

    ctx.activePreviewTab.value = 'cases'
    expect(ctx.currentPreviewTotal.value).toBe(1)
  })

  it('按优先级统计数量', () => {
    const ctx = useXmindImport(PROJECT_ID)
    ctx.previewData.value = [
      makePoint({ priority: 1 }),
      makePoint({ priority: 1 }),
      makePoint({ priority: 2 }),
      makePoint({ priority: 3 }),
    ]

    expect(ctx.highPriorityCount.value).toBe(2)
    expect(ctx.mediumPriorityCount.value).toBe(1)
    expect(ctx.lowPriorityCount.value).toBe(1)
  })

  it('AI 抽样预览仅在开启 AI 且抽样数小于总路径时为真', () => {
    const ctx = useXmindImport(PROJECT_ID)

    ctx.aiEnhance.value = true
    ctx.previewTotalPaths.value = 10
    ctx.previewCaseData.value = [makeCase()]
    expect(ctx.isAiSamplePreview.value).toBe(true)

    ctx.previewCaseData.value = Array.from({ length: 10 }, () => makeCase())
    expect(ctx.isAiSamplePreview.value).toBe(false)

    ctx.aiEnhance.value = false
    expect(ctx.isAiSamplePreview.value).toBe(false)
  })
})

describe('useXmindImport — 展示格式化', () => {
  it('优先级颜色与文案映射', () => {
    const ctx = useXmindImport(PROJECT_ID)

    expect(ctx.getPriorityType(1)).toBe('danger')
    expect(ctx.getPriorityType(2)).toBe('warning')
    expect(ctx.getPriorityType(3)).toBe('success')
    expect(ctx.getPriorityType(9)).toBe('info')

    expect(ctx.getPriorityLabel(1)).toBe('高')
    expect(ctx.getPriorityLabel(2)).toBe('中')
    expect(ctx.getPriorityLabel(3)).toBe('低')
    expect(ctx.getPriorityLabel(9)).toBe('未知')
  })

  it('步骤摘要按序号拼接，字段依次回退', () => {
    const ctx = useXmindImport(PROJECT_ID)

    expect(ctx.formatCaseStepSummary(makeCase())).toBe('1.输入账号 → 2.点击登录 → 3.submit')
    expect(ctx.formatCaseStepSummary(makeCase({ steps: [] }))).toBe('无步骤')
  })

  it.each([
    [512, '512 B'],
    [2048, '2.0 KB'],
    [3 * 1024 * 1024, '3.0 MB'],
  ])('文件大小 %s 展示为 %s', (size, expected) => {
    expect(useXmindImport(PROJECT_ID).formatFileSize(size)).toBe(expected)
  })
})

describe('useXmindImport — 预览', () => {
  it('未选择文件时预览直接返回', async () => {
    const ctx = useXmindImport(PROJECT_ID)

    await ctx.handlePreview()

    expect(mocks.importXmind).not.toHaveBeenCalled()
    expect(ctx.loading.value).toBe(false)
  })

  it('普通模式预览成功后写入预览数据并进入第 2 步', async () => {
    mocks.importXmind.mockResolvedValue(makePreview({ preview_mode: 'test_cases' }))
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file

    await ctx.handlePreview()

    expect(mocks.importXmind).toHaveBeenCalledWith(file, PROJECT_ID, true, false)
    expect(ctx.previewMode.value).toBe('test_cases')
    expect(ctx.previewData.value).toHaveLength(3)
    expect(ctx.activePreviewTab.value).toBe('cases')
    expect(ctx.previewSkippedCount.value).toBe(2)
    expect(ctx.previewSkippedReasons.value).toEqual(['缺少模块'])
    expect(ctx.previewTotalPaths.value).toBe(5)
    expect(ctx.currentStep.value).toBe(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('普通模式预览失败时提示错误信息', async () => {
    mocks.importXmind.mockRejectedValue(new Error('文件解析失败'))
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file

    await ctx.handlePreview()

    expect(ElMessage.error).toHaveBeenCalledWith('文件解析失败')
    expect(ctx.loading.value).toBe(false)
  })

  it('普通模式预览失败且无 message 时使用兜底文案', async () => {
    mocks.importXmind.mockRejectedValue({})
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file

    await ctx.handlePreview()

    expect(ElMessage.error).toHaveBeenCalledWith('预览失败')
  })

  it('AI 模式预览按阶段切换进度文案并应用结果', async () => {
    const texts: string[] = []
    mocks.importXmindStream.mockImplementation(
      async (
        _file: File,
        _projectId: number,
        _preview: boolean,
        options: {
          onProgress: (event: XmindImportProgressEvent) => void
          onResult: (data: unknown) => void
        }
      ) => {
        options.onProgress(progressEvent({ status: 'starting' }))
        texts.push(streamCtx.importProgressText.value)
        options.onProgress(
          progressEvent({
            status: 'running',
            completed_batches: 2,
            total_batches: 4,
            percentage: 50,
          })
        )
        texts.push(streamCtx.importProgressText.value)
        options.onProgress(progressEvent({ status: 'completed' }))
        texts.push(streamCtx.importProgressText.value)
        options.onResult(makePreview())
      }
    )
    const ctx = useXmindImport(PROJECT_ID)
    streamCtx = ctx
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true

    await ctx.handlePreview()

    expect(mocks.importXmindStream).toHaveBeenCalledWith(file, PROJECT_ID, true, expect.any(Object))
    expect(texts).toEqual([
      '正在启动AI解析...',
      'AI解析中... 2/4 批次完成 (50%)',
      'AI解析完成，正在处理结果...',
    ])
    expect(ctx.currentStep.value).toBe(1)
    expect(ctx.previewData.value).toHaveLength(3)
  })

  it('AI 模式错误回调提示错误', async () => {
    mocks.importXmindStream.mockImplementation(
      async (_f: File, _p: number, _pv: boolean, options: { onError: (d: string) => void }) => {
        options.onError('AI 服务超时')
      }
    )
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true

    await ctx.handlePreview()

    expect(ElMessage.error).toHaveBeenCalledWith('AI 服务超时')
  })

  it('AI 模式抛出异常时提示错误信息', async () => {
    mocks.importXmindStream.mockRejectedValue(new Error('流式解析中断'))
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true

    await ctx.handlePreview()

    expect(ElMessage.error).toHaveBeenCalledWith('流式解析中断')
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useXmindImport — 导入', () => {
  it('未选择文件时导入直接返回', async () => {
    const ctx = useXmindImport(PROJECT_ID)
    const emitImported = vi.fn()

    await ctx.handleImport(emitImported)

    expect(mocks.importXmind).not.toHaveBeenCalled()
    expect(emitImported).not.toHaveBeenCalled()
  })

  it('普通模式导入成功后写入结果并通知父组件', async () => {
    mocks.importXmind.mockResolvedValue(makeImportResult())
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    const emitImported = vi.fn()

    await ctx.handleImport(emitImported)

    expect(mocks.importXmind).toHaveBeenCalledWith(file, PROJECT_ID, false, false)
    expect(emitImported).toHaveBeenCalledTimes(1)
    expect(ctx.importResult.value).toEqual({
      success: true,
      savedCount: 3,
      savedCaseCount: 1,
      totalParsed: 4,
      skippedCount: 1,
      skippedReasons: ['重复'],
      errorMessage: '',
      aiTimeout: false,
    })
    expect(ctx.currentStep.value).toBe(2)
  })

  it('普通模式导入失败时记录错误结果', async () => {
    mocks.importXmind.mockRejectedValue(new Error('数据库写入失败'))
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    const emitImported = vi.fn()

    await ctx.handleImport(emitImported)

    expect(ctx.importResult.value.success).toBe(false)
    expect(ctx.importResult.value.errorMessage).toBe('数据库写入失败')
    expect(ctx.currentStep.value).toBe(2)
    expect(emitImported).not.toHaveBeenCalled()
  })

  it('AI 模式导入成功回调写入结果并通知父组件', async () => {
    mocks.importXmindStream.mockImplementation(
      async (_f: File, _p: number, _pv: boolean, options: { onResult: (d: unknown) => void }) => {
        options.onResult(makeImportResult({ saved_count: 5, ai_timeout: true }))
      }
    )
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true
    const emitImported = vi.fn()

    await ctx.handleImport(emitImported)

    expect(ctx.importResult.value.savedCount).toBe(5)
    expect(ctx.importResult.value.aiTimeout).toBe(true)
    expect(emitImported).toHaveBeenCalledTimes(1)
  })

  it('AI 模式错误回调记录错误结果', async () => {
    mocks.importXmindStream.mockImplementation(
      async (_f: File, _p: number, _pv: boolean, options: { onError: (d: string) => void }) => {
        options.onError('AI 写入失败')
      }
    )
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true
    const emitImported = vi.fn()

    await ctx.handleImport(emitImported)

    expect(ctx.importResult.value.errorMessage).toBe('AI 写入失败')
    expect(ctx.currentStep.value).toBe(2)
    expect(emitImported).not.toHaveBeenCalled()
  })

  it('AI 模式抛出异常时记录错误结果', async () => {
    mocks.importXmindStream.mockRejectedValue(new Error('网络中断'))
    const ctx = useXmindImport(PROJECT_ID)
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true

    await ctx.handleImport(vi.fn())

    expect(ctx.importResult.value.errorMessage).toBe('网络中断')
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useXmindImport — 重置', () => {
  it('resetState 清空所有步骤与预览状态', () => {
    const ctx = useXmindImport(PROJECT_ID)
    ctx.currentStep.value = 2
    ctx.selectedFile.value = file
    ctx.aiEnhance.value = true
    ctx.previewAiTimeout.value = true
    ctx.previewTotalPaths.value = 9
    ctx.previewMode.value = 'test_cases'
    ctx.previewData.value = [makePoint()]
    ctx.previewCaseData.value = [makeCase()]
    ctx.previewSkippedCount.value = 3
    ctx.previewSkippedReasons.value = ['x']
    ctx.activePreviewTab.value = 'cases'
    ctx.importResult.value = { ...ctx.importResult.value, success: true }

    ctx.resetState()

    expect(ctx.currentStep.value).toBe(0)
    expect(ctx.selectedFile.value).toBeNull()
    expect(ctx.aiEnhance.value).toBe(false)
    expect(ctx.previewAiTimeout.value).toBe(false)
    expect(ctx.previewTotalPaths.value).toBe(0)
    expect(ctx.previewMode.value).toBe('test_points')
    expect(ctx.previewData.value).toEqual([])
    expect(ctx.previewCaseData.value).toEqual([])
    expect(ctx.previewSkippedCount.value).toBe(0)
    expect(ctx.previewSkippedReasons.value).toEqual([])
    expect(ctx.activePreviewTab.value).toBe('points')
    expect(ctx.importResult.value.success).toBe(false)
    expect(ctx.loading.value).toBe(false)
  })
})
