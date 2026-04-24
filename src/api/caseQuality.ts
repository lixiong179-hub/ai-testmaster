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
 * 预估用例成本
 */
export const estimateCaseCost = (caseId: number) => {
  return request.get(`/api/v1/quality/cases/${caseId}/cost-estimate`)
}

/**
 * 优化用例定位
 */
export const optimizeCaseLocators = (caseId: number) => {
  return request.post(`/api/v1/quality/cases/${caseId}/optimize-locators`)
}

/**
 * 获取项目成本汇总
 */
export const getProjectCostSummary = (projectId: number) => {
  return request.get(`/api/v1/quality/projects/${projectId}/cost-summary`)
}

/**
 * 批量分析用例
 */
export const batchAnalyzeCases = (caseIds: number[]) => {
  return request.post('/api/v1/quality/batch-analyze', caseIds)
}
