import request from '@/utils/request'

export const analyzeCaseQuality = (caseId: number) => {
  return request.get(`/api/v1/quality/cases/${caseId}/quality`)
}

export const getCaseQualityTrend = (caseId: number, days: number = 30) => {
  return request.get(`/api/v1/quality/cases/${caseId}/quality/trend`, { params: { days } })
}

export const estimateCaseCost = (caseId: number) => {
  return request.get(`/api/v1/quality/cases/${caseId}/cost-statistics`)
}

export const optimizeCaseLocators = (caseId: number) => {
  return request.post(`/api/v1/quality/cases/${caseId}/optimize-locators`)
}

export const getProjectCostSummary = (projectId: number) => {
  return request.get(`/api/v1/quality/projects/${projectId}/cost-statistics`)
}

export const batchAnalyzeCases = (caseIds: number[]) => {
  return request.post('/api/v1/quality/batch-analyze', caseIds)
}

// ========== 后验质量评分（Posterior Quality Scoring） ==========

/** 后验质量评分结果（对应后端 PosteriorResultResponse） */
export interface PosteriorResult {
  project_id: number
  /** 后验质量综合分（0-100） */
  posterior_quality_score: number
  /** 评审通过率 */
  review_pass_rate: number
  /** 执行通过率 */
  execution_pass_rate: number
  /** 修改率 */
  modification_rate: number
  total_reviewed: number
  total_executed: number
  total_cases: number
  /** 执行样本是否达到最小样本数（false 时评分仅供参考） */
  meets_min_executions: boolean
}

/** 项目后验质量统计（对应后端 PosteriorStatsResponse） */
export interface PosteriorStats {
  project_id: number
  avg_posterior_score: number | null
  max_posterior_score: number | null
  min_posterior_score: number | null
  total_cases: number
  scored_cases: number
  unscored_cases: number
  /** 分数分布：A_90_100 / B_75_89 / C_60_74 / D_0_59 */
  distribution: Record<string, number>
}

/** 后验评分接口的统一响应结构（响应拦截器已解包为 ApiResponse 形态） */
export interface PosteriorApiResponse<T> {
  code: number
  message: string
  data: T
}

/**
 * 触发项目后验质量评分（写操作）
 * POST /api/v1/quality/posterior/{projectId}
 *
 * 说明：本函数**不吞异常**——计算失败（500）或项目不存在（404）时由调用方捕获处理。
 */
export function triggerPosteriorScoring(
  projectId: number
): Promise<PosteriorApiResponse<PosteriorResult>> {
  return request.post(
    `/api/v1/quality/posterior/${projectId}`
  ) as unknown as Promise<PosteriorApiResponse<PosteriorResult>>
}

/**
 * 查询项目后验质量统计
 * GET /api/v1/quality/posterior/{projectId}/result
 *
 * 未评分项目返回 `avg_posterior_score` 等字段为 null，属正常返回。
 */
export function getPosteriorResult(
  projectId: number
): Promise<PosteriorApiResponse<PosteriorStats>> {
  return request.get(
    `/api/v1/quality/posterior/${projectId}/result`
  ) as unknown as Promise<PosteriorApiResponse<PosteriorStats>>
}
