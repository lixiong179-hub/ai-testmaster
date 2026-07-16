import request from '@/utils/request'
import type { TestPoint, TestPointDraft, TestPointBatchSaveResponse } from '@/types/testPoint'
import {
  type TestPointApiResponse,
  type TestPointListResponse,
  type DeleteTestData,
  type BatchDeleteData,
  type XmindPreviewResponse,
  type XmindImportResponse,
  type XmindImportSSECallbacks,
  type XmindImportProgressEvent,
  type RelatedTestCaseListResponse,
  type TestPointRequirementOptionListResponse,
  type TestPointRequirementOption,
  type BatchGenerateParams,
  type TestPointExtractRequest,
  type TestPointExtractResponse,
  type TestPointListParams,
  type TestPointFormData,
  type TestPointUpdateData,
  type TestPointAnalyzeRequest,
  type AnalysisProgress,
  unwrapApiPayload,
  createSseGenerator,
} from './testPointTypes'

export type {
  TestPoint,
  TestPointAnalyzeRequest,
  TestPointDraft,
  TestPointApiResponse,
  TestPointListResponse,
  DeleteTestData,
  BatchDeleteData,
  XmindPreviewResponse,
  XmindImportResponse,
  XmindImportSSECallbacks,
  XmindImportProgressEvent,
  XmindPreviewItem,
  XmindPreviewCaseStep,
  XmindPreviewCaseItem,
  RelatedTestCaseListResponse,
  TestPointRequirementOptionListResponse,
  BatchGenerateParams,
  AnalysisProgress,
} from './testPointTypes'

export const testPointApi = {
  analyze: async (data: TestPointAnalyzeRequest): Promise<AsyncGenerator<AnalysisProgress>> => {
    return createSseGenerator<AnalysisProgress>('/api/v1/test-point/analyze', data)
  },

  extract: async (data: TestPointExtractRequest): Promise<TestPointExtractResponse> => {
    const response = (await request.post(
      '/api/v1/test-point/extract',
      data
    )) as TestPointApiResponse<TestPointExtractResponse>
    return response.data
  },

  getList: async (
    projectId: number,
    params?: TestPointListParams
  ): Promise<TestPointListResponse> => {
    const response = (await request.get(`/api/v1/test-point/list/${projectId}`, {
      params,
    })) as TestPointApiResponse<TestPointListResponse>
    return response.data
  },

  getDetail: async (testPointId: number, projectId: number): Promise<TestPoint> => {
    return request.get(`/api/v1/test-point/detail/${testPointId}`, {
      params: { project_id: projectId },
    }) as unknown as Promise<TestPoint>
  },

  create: async (data: TestPointFormData): Promise<TestPoint> => {
    return request.post('/api/v1/test-point/', data) as unknown as Promise<TestPoint>
  },

  update: async (
    testPointId: number,
    data: TestPointUpdateData
  ): Promise<TestPointApiResponse<TestPoint>> => {
    return request.put(`/api/v1/test-point/${testPointId}`, data, {
      params: { project_id: data.project_id },
    }) as unknown as Promise<TestPointApiResponse<TestPoint>>
  },

  delete: async (
    testPointId: number,
    projectId: number
  ): Promise<TestPointApiResponse<DeleteTestData>> => {
    return request.delete(`/api/v1/test-point/${testPointId}`, {
      params: { project_id: projectId },
    }) as unknown as Promise<TestPointApiResponse<DeleteTestData>>
  },

  batchDelete: async (
    projectId: number,
    ids: number[]
  ): Promise<TestPointApiResponse<BatchDeleteData>> => {
    return request.delete('/api/v1/test-point/batch', {
      params: { project_id: projectId },
      data: ids,
    }) as unknown as Promise<TestPointApiResponse<BatchDeleteData>>
  },

  batchSave: async (
    projectId: number,
    items: TestPointDraft[]
  ): Promise<TestPointApiResponse<TestPointBatchSaveResponse>> => {
    return request.post('/api/v1/test-point/batch-save', items, {
      params: { project_id: projectId },
      headers: { 'Content-Type': 'application/json' },
    }) as unknown as Promise<TestPointApiResponse<TestPointBatchSaveResponse>>
  },

  getRelatedCases: async (
    testPointId: number,
    projectId: number,
    page: number = 1,
    pageSize: number = 10
  ): Promise<RelatedTestCaseListResponse> => {
    const response = (await request.get(`/api/v1/test-point/${testPointId}/test-cases`, {
      params: { project_id: projectId, page, page_size: pageSize },
    })) as TestPointApiResponse<RelatedTestCaseListResponse>
    return response.data
  },

  getRequirementOptions: async (projectId: number): Promise<TestPointRequirementOption[]> => {
    const response = (await request.get(
      `/api/v1/test-point/requirements/${projectId}`
    )) as TestPointApiResponse<TestPointRequirementOptionListResponse>
    return response.data.items
  },

  batchGenerateStream: async (
    payload: BatchGenerateParams
  ): Promise<AsyncGenerator<AnalysisProgress>> => {
    return createSseGenerator<AnalysisProgress>(
      '/api/v1/test-point/batch-generate-cases/stream',
      payload
    )
  },

  importXmind: async (
    file: File,
    projectId: number,
    preview: boolean = false,
    aiEnhance: boolean = false
  ): Promise<XmindPreviewResponse | XmindImportResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('project_id', String(projectId))
    formData.append('preview', String(preview))
    formData.append('ai_enhance', String(aiEnhance))
    const response = await request.post('/api/v1/test-point/import-xmind', formData)
    return unwrapApiPayload(
      response as unknown as TestPointApiResponse<XmindPreviewResponse | XmindImportResponse>
    )
  },

  importXmindStream: async (
    file: File,
    projectId: number,
    preview: boolean,
    callbacks: XmindImportSSECallbacks
  ): Promise<void> => {
    const baseUrl = import.meta.env?.VITE_API_BASE_URL || ''
    const token = localStorage.getItem('token')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('project_id', String(projectId))
    formData.append('preview', String(preview))
    const response = await fetch(`${baseUrl}/api/v1/test-point/import-xmind-stream`, {
      method: 'POST',
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    })
    if (!response.ok || !response.body) {
      const errorText = await response.text()
      callbacks.onError?.(errorText || '导入请求失败')
      return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let currentEvent = ''
    let currentDataParts: string[] = []
    const processEvent = () => {
      if (currentEvent && currentDataParts.length > 0) {
        const currentData = currentDataParts.join('\n')
        try {
          const parsed = JSON.parse(currentData)
          if (currentEvent === 'progress') callbacks.onProgress?.(parsed as XmindImportProgressEvent)
          else if (currentEvent === 'result')
            callbacks.onResult?.(parsed as XmindPreviewResponse | XmindImportResponse)
          else if (currentEvent === 'error')
            callbacks.onError?.(parsed.detail || '导入失败', parsed.error_type)
        } catch {
          /* ignore */
        }
        currentEvent = ''
        currentDataParts = []
      }
    }
    let reading = true
    while (reading) {
      const { done, value } = await reader.read()
      if (done) {
        reading = false
        break
      }
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('event: ')) currentEvent = line.slice(7).trim()
        else if (line.startsWith('data: ')) currentDataParts.push(line.slice(6))
        else if (line === '') processEvent()
      }
    }
    if (buffer.trim()) {
      const remaining = buffer.trim()
      if (remaining.startsWith('event: ')) currentEvent = remaining.slice(7).trim()
      else if (remaining.startsWith('data: ')) currentDataParts.push(remaining.slice(6))
      processEvent()
    }
  },
}
