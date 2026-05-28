import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { BatchCreateRequest, BatchCreateResponse, ImportResult } from './types'
import { extractResponseData } from './types'

interface BatchDeleteResult {
  success_count: number
  fail_count: number
  not_found_count: number
  deleted_ids: number[]
  total: number
  message: string
}

interface BatchRestoreResult {
  success_count: number
  fail_count: number
  not_found_count: number
  restored_ids: number[]
  total: number
  message: string
}

export const batchApi = {
  batchCreateCases: async (data: BatchCreateRequest): Promise<BatchCreateResponse> => {
    const response = await request.post('/api/v1/testCase/batch-create', data)
    return extractResponseData<BatchCreateResponse>(
      response as unknown as ApiResponse<BatchCreateResponse> | BatchCreateResponse
    )
  },

  batchDeleteCases: async (caseIds: number[], projectId?: number): Promise<BatchDeleteResult> => {
    const response = await request.post('/api/v1/testCase/batch-delete', {
      ...(projectId ? { project_id: projectId } : {}),
      caseIds,
    })
    return extractResponseData<BatchDeleteResult>(
      response as unknown as ApiResponse<BatchDeleteResult> | BatchDeleteResult
    )
  },

  batchDelete: async (projectId: number, caseIds: number[]): Promise<BatchDeleteResult> => {
    return batchApi.batchDeleteCases(caseIds, projectId)
  },

  batchRestoreCases: async (caseIds: number[], projectId?: number): Promise<BatchRestoreResult> => {
    const response = await request.post('/api/v1/testCase/batch-restore', {
      ...(projectId ? { project_id: projectId } : {}),
      caseIds,
    })
    return extractResponseData<BatchRestoreResult>(
      response as unknown as ApiResponse<BatchRestoreResult> | BatchRestoreResult
    )
  },

  importCases: async (file: File): Promise<ImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await request.post('/api/v1/testCase/import', formData)
    return extractResponseData<ImportResult>(
      response as unknown as ApiResponse<ImportResult> | ImportResult
    )
  },
}
