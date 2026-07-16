import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { TestCase } from '@/types/testCase'
import type { CaseVersionPageResponse, CaseVersionDetail, CaseVersionCompareResult } from './types'
import { extractResponseData } from './types'

export const versionApi = {
  getCaseVersions: async (
    caseId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<CaseVersionPageResponse> => {
    const response = await request.get(`/api/v1/test-case/${caseId}/versions`, {
      params: { page, page_size: pageSize },
    })
    return extractResponseData<CaseVersionPageResponse>(
      response as unknown as ApiResponse<CaseVersionPageResponse> | CaseVersionPageResponse
    )
  },

  getCaseVersionDetail: async (caseId: number, versionId: number): Promise<CaseVersionDetail> => {
    const response = await request.get(`/api/v1/test-case/${caseId}/versions/${versionId}`)
    return extractResponseData<CaseVersionDetail>(
      response as unknown as ApiResponse<CaseVersionDetail> | CaseVersionDetail
    )
  },

  compareCaseVersions: async (
    caseId: number,
    fromVersion: number,
    toVersion: number
  ): Promise<CaseVersionCompareResult> => {
    const response = await request.get(`/api/v1/test-case/${caseId}/versions/compare`, {
      params: { from: fromVersion, to: toVersion },
    })
    return extractResponseData<CaseVersionCompareResult>(
      response as unknown as ApiResponse<CaseVersionCompareResult> | CaseVersionCompareResult
    )
  },

  rollbackCaseVersion: async (caseId: number, versionId: number): Promise<TestCase> => {
    const response = await request.post(`/api/v1/test-case/${caseId}/versions/${versionId}/restore`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },
}
