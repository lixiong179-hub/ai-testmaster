import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { TestCase } from '@/types/testCase'
import type {
  TestCaseCreate,
  TestCaseUpdateData,
  StepLocatorUpdateData,
  CaseQueryParams,
  CasePageResponse,
  TestCaseExecute,
  CorrectionResponse,
  VerificationResponse,
  TestCaseListResponse,
  TestCaseListParams,
  SupplementResponse,
  QualityAnalysisResult,
} from './types'
import { extractResponseData } from './types'

function cleanParams<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== ''
    )
  ) as Partial<T>
}

export const crudApi = {
  getCaseList: async (params: CaseQueryParams): Promise<CasePageResponse> => {
    const response = await request.get('/api/v1/test-case/', { params: cleanParams(params) })
    return response as unknown as CasePageResponse
  },

  getCase: async (id: number): Promise<TestCase> => {
    const response = await request.get(`/api/v1/test-case/${id}`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  getCaseDetail: async (caseId: number): Promise<TestCase> => {
    const response = await request.get(`/api/v1/test-case/${caseId}`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  createCase: async (data: TestCaseCreate): Promise<TestCase> => {
    const response = await request.post('/api/v1/test-case/', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  updateCase: async (id: number, data: TestCaseUpdateData): Promise<TestCase> => {
    const response = await request.put(`/api/v1/test-case/${id}`, data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  updateStepLocator: async (
    caseId: number,
    stepId: number,
    data: StepLocatorUpdateData
  ): Promise<Record<string, unknown>> => {
    const response = await request.put(`/api/v1/test-case/${caseId}/steps/${stepId}/locator`, data)
    return extractResponseData<Record<string, unknown>>(
      response as unknown as ApiResponse<Record<string, unknown>> | Record<string, unknown>
    )
  },

  deleteCase: async (id: number, projectId?: number): Promise<void> => {
    await request.delete(`/api/v1/test-case/${id}`, {
      params: projectId ? { project_id: projectId } : undefined,
    })
  },

  executeCase: async (data: TestCaseExecute): Promise<TestCase> => {
    const response = await request.post('/api/v1/test-case/execute', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  startCorrection: async (caseId: number): Promise<CorrectionResponse> => {
    const response = await request.post(`/api/v1/test-case/${caseId}/start-correction`)
    return extractResponseData<CorrectionResponse>(
      response as unknown as ApiResponse<CorrectionResponse> | CorrectionResponse
    )
  },

  submitVerification: async (caseId: number): Promise<VerificationResponse> => {
    const response = await request.post(`/api/v1/test-case/${caseId}/submit-verification`)
    return extractResponseData<VerificationResponse>(
      response as unknown as ApiResponse<VerificationResponse> | VerificationResponse
    )
  },

  getList: async (projectId: number, params: TestCaseListParams): Promise<TestCaseListResponse> => {
    const response = await request.get('/api/v1/test-case/', {
      params: cleanParams({ project_id: projectId, ...params }),
    })
    return extractResponseData<TestCaseListResponse>(
      response as unknown as ApiResponse<TestCaseListResponse> | TestCaseListResponse
    )
  },

  delete: async (id: number, projectId: number): Promise<void> => {
    await crudApi.deleteCase(id, projectId)
  },

  getSupplementData: async (caseId: number): Promise<SupplementResponse> => {
    const response = await request.get(`/api/v1/test-case/${caseId}/supplement`)
    return extractResponseData<SupplementResponse>(
      response as unknown as ApiResponse<SupplementResponse> | SupplementResponse
    )
  },

  supplementCase: async (
    caseId: number,
    payload: Record<string, unknown>
  ): Promise<SupplementResponse> => {
    const response = await request.post(`/api/v1/test-case/${caseId}/supplement`, payload)
    return extractResponseData<SupplementResponse>(
      response as unknown as ApiResponse<SupplementResponse> | SupplementResponse
    )
  },

  getQualityAnalysis: async (projectId: number): Promise<QualityAnalysisResult> => {
    const response = await request.get(`/api/v1/quality/projects/${projectId}/quality`)
    return extractResponseData<QualityAnalysisResult>(
      response as unknown as ApiResponse<QualityAnalysisResult> | QualityAnalysisResult
    )
  },
}
