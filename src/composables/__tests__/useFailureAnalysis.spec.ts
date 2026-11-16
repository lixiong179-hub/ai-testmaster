import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('@/api/testExecution', () => ({
  analyzeFailure: vi.fn(),
}))

import { analyzeFailure } from '@/api/testExecution'
import { ISSUE_TYPE_COLORS, ISSUE_TYPE_LABELS, useFailureAnalysis } from '../useFailureAnalysis'
import { silenceConsole, silenceElMessage } from '@/test-utils'

const analyzeMock = vi.mocked(analyzeFailure)

function setup(executionStatus: Record<string, unknown> | null = { case_id: 10 }) {
  const statusRef = ref<Record<string, unknown> | null>(executionStatus)
  const api = useFailureAnalysis({ executionStatus: statusRef })
  return { api, executionStatus: statusRef }
}

describe('useFailureAnalysis — 常量映射', () => {
  it('问题类型标签与颜色映射固定', () => {
    expect(ISSUE_TYPE_LABELS).toEqual({
      case_issue: '用例问题',
      product_bug: 'Bug问题',
      needs_review: '待人工判断',
    })
    expect(ISSUE_TYPE_COLORS).toEqual({
      case_issue: 'warning',
      product_bug: 'danger',
      needs_review: 'info',
    })
  })
})

describe('useFailureAnalysis — 失败分析', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    silenceElMessage('warning')
    silenceElMessage('error')
    silenceConsole('error')
  })

  it('已存在分析结果时直接复用，不重复请求', async () => {
    const { api } = setup()
    api.failureAnalysisMap.value[1] = {
      suggested_type: 'case_issue',
      reason: 'cached',
      ai_analysis: '',
    } as never

    await api.handleAnalyzeFailure({ result_id: 1 }, 1)

    expect(analyzeMock).not.toHaveBeenCalled()
  })

  it('缺少结果ID时提示且不请求', async () => {
    const { api } = setup()

    await api.handleAnalyzeFailure({}, 0)

    expect(ElMessage.warning).toHaveBeenCalledWith('无法获取执行结果ID，请稍后重试')
    expect(analyzeMock).not.toHaveBeenCalled()
    expect(api.analysisLoading.value).toBe(false)
  })

  it('优先使用 result_id，缺失时回退 id', async () => {
    analyzeMock.mockResolvedValue({ data: { suggested_type: 'case_issue' } } as never)
    const { api } = setup()

    await api.handleAnalyzeFailure({ id: 33 }, 2)

    expect(analyzeMock).toHaveBeenCalledWith(33)
    expect(api.failureAnalysisMap.value[2]).toMatchObject({ suggested_type: 'case_issue' })
    expect(api.issueTypeMap.value[2]).toBe('case_issue')
  })

  it('兼容双层 data 包装的返回结构', async () => {
    analyzeMock.mockResolvedValue({
      data: { data: { suggested_type: 'product_bug', reason: 'r', ai_analysis: 'a' } },
    } as never)
    const { api } = setup()

    await api.handleAnalyzeFailure({ result_id: 5 }, 0)

    expect(api.failureAnalysisMap.value[0]).toEqual({
      suggested_type: 'product_bug',
      reason: 'r',
      ai_analysis: 'a',
    })
    expect(api.issueTypeMap.value[0]).toBe('product_bug')
  })

  it('异常时优先展示后端 detail', async () => {
    analyzeMock.mockRejectedValue({ response: { data: { detail: '模型超时' } } })
    const { api } = setup()

    await api.handleAnalyzeFailure({ result_id: 5 }, 0)

    expect(ElMessage.error).toHaveBeenCalledWith('模型超时')
    expect(api.analysisLoading.value).toBe(false)
  })

  it('异常无 detail 时使用兜底文案', async () => {
    analyzeMock.mockRejectedValue(new Error('boom'))
    const { api } = setup()

    await api.handleAnalyzeFailure({ result_id: 5 }, 0)

    expect(ElMessage.error).toHaveBeenCalledWith('分析失败原因出错')
  })

  it('分析进行中 analysisLoading 为 true', async () => {
    let resolveFn: ((value: unknown) => void) | undefined
    analyzeMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFn = resolve
      }) as never
    )
    const { api } = setup()

    const pending = api.handleAnalyzeFailure({ result_id: 5 }, 0)
    expect(api.analysisLoading.value).toBe(true)

    resolveFn?.({ data: { suggested_type: 'needs_review' } })
    await pending

    expect(api.analysisLoading.value).toBe(false)
  })
})

describe('useFailureAnalysis — 用例纠正跳转', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    silenceElMessage('warning')
  })

  it('Bug 问题禁止跳转修改用例', () => {
    const { api } = setup()
    api.issueTypeMap.value[0] = 'product_bug'

    api.handleCorrectCase({ case_id: 8 }, 0)

    expect(ElMessage.warning).toHaveBeenCalledWith('这是Bug问题，不允许修改用例！')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('缺少用例ID时提示且不跳转', () => {
    const { api } = setup({ case_id: undefined })

    api.handleCorrectCase({}, 0)

    expect(ElMessage.warning).toHaveBeenCalledWith('无法获取用例ID')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('优先使用步骤 case_id，缺失时回退执行状态', () => {
    const { api } = setup({ case_id: 99 })

    api.handleCorrectCase({}, 3)
    expect(pushMock).toHaveBeenLastCalledWith({
      path: '/home/case/detail/99',
      query: expect.any(Object),
    })

    api.handleCorrectCase({ case_id: 7 }, 4)
    expect(pushMock).toHaveBeenLastCalledWith({
      path: '/home/case/detail/7',
      query: expect.any(Object),
    })
  })

  it('携带问题类型与分析结论（已编码）', () => {
    const { api } = setup()
    api.issueTypeMap.value[1] = 'case_issue'
    api.failureAnalysisMap.value[1] = {
      suggested_type: 'case_issue',
      reason: '按钮不存在',
      ai_analysis: '断言失败',
    } as never

    api.handleCorrectCase({ case_id: 7 }, 1)

    expect(pushMock).toHaveBeenCalledWith({
      path: '/home/case/detail/7',
      query: {
        correction: 'true',
        stepIndex: '1',
        issueType: 'case_issue',
        failureReason: encodeURIComponent('按钮不存在'),
        aiAnalysis: encodeURIComponent('断言失败'),
      },
    })
  })

  it('无分析结果时问题类型回退 case_issue 且不带分析字段', () => {
    const { api } = setup()

    api.handleCorrectCase({ case_id: 7 }, 2)

    const arg = pushMock.mock.calls[0][0] as { query: Record<string, string> }
    expect(arg.query).toEqual({
      correction: 'true',
      stepIndex: '2',
      issueType: 'case_issue',
    })
  })
})
