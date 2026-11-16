import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  getQualityAnalysis: vi.fn(),
  getProjects: vi.fn(),
  optimizeCaseLocators: vi.fn(),
  getProjectCostSummary: vi.fn(),
  batchAnalyzeCases: vi.fn(),
}))

vi.mock('@/api/case', () => ({
  caseApi: { getQualityAnalysis: mocks.getQualityAnalysis },
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/caseQuality', () => ({
  optimizeCaseLocators: mocks.optimizeCaseLocators,
  getProjectCostSummary: mocks.getProjectCostSummary,
  batchAnalyzeCases: mocks.batchAnalyzeCases,
}))

import { useCaseQualityAnalysis } from '../useCaseQualityAnalysis'

type Ctx = ReturnType<typeof useCaseQualityAnalysis>

let ctx: Ctx

const Host = defineComponent({
  setup() {
    ctx = useCaseQualityAnalysis()
    return () => h('div')
  },
})

async function mountHost() {
  const wrapper = mount(Host)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(ElMessage, 'error').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'success').mockImplementation(() => ({}) as never)
  vi.spyOn(ElMessage, 'warning').mockImplementation(() => ({}) as never)
  mocks.getProjects.mockResolvedValue({ data: { items: [{ id: 1, name: '项目A' }] } })
  mocks.getQualityAnalysis.mockResolvedValue({ overall_score: 85, dimensions: [] })
  mocks.getProjectCostSummary.mockResolvedValue({ data: { total_tokens: 100 } })
  mocks.batchAnalyzeCases.mockResolvedValue({})
  mocks.optimizeCaseLocators.mockResolvedValue({})
})

describe('useCaseQualityAnalysis — 项目加载', () => {
  it('挂载时拉取项目列表', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.projects.value).toEqual([{ id: 1, name: '项目A' }])
  })

  it('项目加载失败时提示 Error 信息', async () => {
    mocks.getProjects.mockRejectedValue(new Error('网络异常'))
    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')
    expect(ctx.projects.value).toEqual([])
  })

  it('非 Error 异常使用兜底文案', async () => {
    mocks.getProjects.mockRejectedValue('boom')
    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('加载项目失败')
  })
})

describe('useCaseQualityAnalysis — 评分派生', () => {
  it.each([
    [90, 'success', '优秀'],
    [80, 'success', '优秀'],
    [70, 'warning', '良好'],
    [60, 'warning', '良好'],
    [59, 'danger', '需改进'],
    [0, 'danger', '需改进'],
  ])('评分 %s → %s/%s', async (score, level, label) => {
    await mountHost()
    ctx.analysisResult.value = { overall_score: score, dimensions: [] } as never

    expect(ctx.overallScore.value).toBe(score)
    expect(ctx.scoreLevel.value).toBe(level)
    expect(ctx.scoreLabel.value).toBe(label)
  })

  it('无结果时评分为 0', async () => {
    await mountHost()

    expect(ctx.overallScore.value).toBe(0)
    expect(ctx.scoreLevel.value).toBe('danger')
  })
})

describe('useCaseQualityAnalysis — 质量分析', () => {
  it('未选项目时不请求', async () => {
    await mountHost()

    await ctx.fetchAnalysis()

    expect(mocks.getQualityAnalysis).not.toHaveBeenCalled()
    expect(ctx.loading.value).toBe(false)
  })

  it('请求成功写入结果并复位 loading', async () => {
    await mountHost()
    ctx.selectedProjectId.value = 3

    await ctx.fetchAnalysis()

    expect(mocks.getQualityAnalysis).toHaveBeenCalledWith(3)
    expect(ctx.analysisResult.value).toEqual({ overall_score: 85, dimensions: [] })
    expect(ctx.loading.value).toBe(false)
  })

  it('请求失败清空结果并提示', async () => {
    mocks.getQualityAnalysis.mockRejectedValue(new Error('分析服务异常'))
    await mountHost()
    ctx.selectedProjectId.value = 3
    ctx.analysisResult.value = { overall_score: 90 } as never

    await ctx.fetchAnalysis()

    expect(ElMessage.error).toHaveBeenCalledWith('分析服务异常')
    expect(ctx.analysisResult.value).toBeNull()
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useCaseQualityAnalysis — 成本统计', () => {
  it('成功时写入 data 并复位 loading', async () => {
    await mountHost()
    ctx.selectedProjectId.value = 2

    await ctx.loadCostSummary()

    expect(mocks.getProjectCostSummary).toHaveBeenCalledWith(2)
    expect(ctx.costSummary.value).toEqual({ total_tokens: 100 })
    expect(ctx.costLoading.value).toBe(false)
  })

  it('失败时提示且不清空既有统计', async () => {
    mocks.getProjectCostSummary.mockRejectedValue(new Error('成本服务不可用'))
    await mountHost()
    ctx.selectedProjectId.value = 2
    ctx.costSummary.value = { total_tokens: 1 } as never

    await ctx.loadCostSummary()

    expect(ElMessage.error).toHaveBeenCalledWith('成本服务不可用')
    expect(ctx.costSummary.value).toEqual({ total_tokens: 1 })
  })

  it('未选项目时不请求', async () => {
    await mountHost()

    await ctx.loadCostSummary()

    expect(mocks.getProjectCostSummary).not.toHaveBeenCalled()
  })
})

describe('useCaseQualityAnalysis — 批量与定位器', () => {
  it('未选用例时给出警告且不请求', async () => {
    await mountHost()

    await ctx.handleBatchAnalyze([])

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择要分析的用例')
    expect(mocks.batchAnalyzeCases).not.toHaveBeenCalled()
  })

  it('批量分析成功后提示并在有项目时刷新', async () => {
    await mountHost()
    ctx.selectedProjectId.value = 5

    await ctx.handleBatchAnalyze([1, 2])

    expect(mocks.batchAnalyzeCases).toHaveBeenCalledWith([1, 2])
    expect(ElMessage.success).toHaveBeenCalledWith('批量分析完成')
    expect(mocks.getQualityAnalysis).toHaveBeenCalledWith(5)
    expect(ctx.batchAnalyzing.value).toBe(false)
  })

  it('批量分析失败提示并复位状态', async () => {
    mocks.batchAnalyzeCases.mockRejectedValue(new Error('批量失败'))
    await mountHost()
    ctx.selectedProjectId.value = 5

    await ctx.handleBatchAnalyze([1])

    expect(ElMessage.error).toHaveBeenCalledWith('批量失败')
    expect(ctx.batchAnalyzing.value).toBe(false)
    expect(mocks.getQualityAnalysis).not.toHaveBeenCalled()
  })

  it('定位器优化成功与失败分别提示', async () => {
    await mountHost()

    await ctx.handleOptimizeLocators(9)
    expect(mocks.optimizeCaseLocators).toHaveBeenCalledWith(9)
    expect(ElMessage.success).toHaveBeenCalledWith('定位器优化完成')

    mocks.optimizeCaseLocators.mockRejectedValue(new Error('优化失败'))
    await ctx.handleOptimizeLocators(9)
    expect(ElMessage.error).toHaveBeenCalledWith('优化失败')
  })
})

describe('useCaseQualityAnalysis — 项目切换与详情', () => {
  it('切换项目清空旧数据并并行拉取分析', async () => {
    await mountHost()
    ctx.analysisResult.value = { overall_score: 10 } as never
    ctx.costSummary.value = { total_tokens: 1 } as never
    ctx.selectedProjectId.value = 4

    await ctx.handleProjectChange()

    expect(mocks.getQualityAnalysis).toHaveBeenCalledWith(4)
    expect(mocks.getProjectCostSummary).toHaveBeenCalledWith(4)
    expect(ctx.analysisResult.value).toEqual({ overall_score: 85, dimensions: [] })
  })

  it('清空项目时仅重置数据不请求', async () => {
    await mountHost()
    ctx.analysisResult.value = { overall_score: 10 } as never
    ctx.costSummary.value = { total_tokens: 1 } as never
    ctx.selectedProjectId.value = undefined

    await ctx.handleProjectChange()

    expect(mocks.getQualityAnalysis).not.toHaveBeenCalled()
    expect(mocks.getProjectCostSummary).not.toHaveBeenCalled()
    expect(ctx.analysisResult.value).toBeNull()
    expect(ctx.costSummary.value).toBeNull()
  })

  it('showDetail 写入内容并打开弹窗', async () => {
    await mountHost()

    ctx.showDetail('维度明细')

    expect(ctx.dialogContent.value).toBe('维度明细')
    expect(ctx.dialogVisible.value).toBe(true)
  })
})
