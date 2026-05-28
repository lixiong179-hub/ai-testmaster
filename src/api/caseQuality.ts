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
