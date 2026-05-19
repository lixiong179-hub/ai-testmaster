/**
 * 用例质量分析API
 */
import request from '@/utils/request'

/**
 * 分析用例质量
 */
export const analyzeCaseQuality = (caseId: number) => {
  return request.get(`/api/v1/quality/cases/${caseId}/quality`)
}

/**
 * 分析项目质量
 */
export const analyzeProjectQuality = (projectId: number) => {
  return request.get(`/api/v1/quality/projects/${projectId}/quality`)
}

/**
 * 获取用例质量趋势
 */
export const getCaseQualityTrend = (caseId: number, days: number = 30) => {
  return request.get(`/api/v1/quality/cases/${caseId}/quality/trend`, {
    params: { days },
  })
}

/**
 * 获取用例成本统计
 * 后端：GET /api/v1/quality/cases/{case_id}/cost-statistics
 */
export const estimateCaseCost = (caseId: number) => {
  return request.get(`/api/v1/quality/cases/${caseId}/cost-statistics`)
}

/**
 * 优化用例定位
 */
export const optimizeCaseLocators = (caseId: number) => {
  return request.post(`/api/v1/quality/cases/${caseId}/optimize-locators`)
}

/**
 * 获取项目成本统计
 * 后端：GET /api/v1/quality/projects/{project_id}/cost-statistics
 */
export const getProjectCostSummary = (projectId: number) => {
  return request.get(`/api/v1/quality/projects/${projectId}/cost-statistics`)
}

/**
 * 批量分析用例
 */
export const batchAnalyzeCases = (caseIds: number[]) => {
  return request.post('/api/v1/quality/batch-analyze', caseIds)
}
