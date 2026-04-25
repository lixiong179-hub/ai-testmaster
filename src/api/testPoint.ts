import request from '@/utils/request'
import type {
  AnalysisProgress,
  RelatedTestCase,
  TestPoint,
  TestPointAnalyzeRequest,
  TestPointBatchSaveResponse,
  TestPointDraft,
  TestPointExtractRequest,
  TestPointExtractResponse,
  TestPointFormData,
  TestPointListParams,
  TestPointListStats,
  TestPointRequirementOption,
  TestPointUpdateData,
} from '@/types/testPoint'

export type {
  AnalysisProgress,
  RelatedTestCase,
  TestPoint,
  TestPointAnalyzeRequest,
  TestPointBatchSaveResponse,
  TestPointDraft,
  TestPointExtractRequest,
  TestPointExtractResponse,
  TestPointFormData,
  TestPointListParams,
  TestPointListStats,
  TestPointRequirementOption,
  TestPointUpdateData,
} from '@/types/testPoint'

export interface TestPointApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface TestPointListResponse {
  total: number
  items: TestPoint[]
  page: number
  page_size: number
  stats: TestPointListStats
}

export interface DeleteTestData {
  id: number
}

export interface BatchDeleteData {
  deleted_count: number
  requested_count: number
}

export interface XmindPreviewItem {
  module: string
  function: string
  point: string
  priority: number
}

export interface XmindPreviewCaseStep {
  step_number: number
  action: string
  expected_result: string
}

export interface XmindPreviewCaseItem {
  module: string
  function: string
  title: string
  precondition: string
  expected_result: string
  priority: number
  step_count: number
  steps: XmindPreviewCaseStep[]
}

export interface XmindPreviewResponse {
  preview_mode: 'test_points' | 'test_cases'
  total: number
  items: XmindPreviewItem[]
  case_total: number
  case_items: XmindPreviewCaseItem[]
  skipped_count: number
  skipped_reasons: string[]
  ai_timeout?: boolean
}

export interface XmindImportResponse {
  saved_count: number
  saved_case_count?: number
  total_parsed: number
  skipped_count: number
  skipped_reasons: string[]
  ai_timeout?: boolean
}

function unwrapApiPayload<T>(response: TestPointApiResponse<T> | T): T {
  if (
    response &&
    typeof response === 'object' &&
    'data' in response &&
    (('code' in response && typeof response.code === 'number') ||
      'message' in response ||
      'msg' in response)
  ) {
    return response.data as T
  }
  return response as T
}

export interface RelatedTestCaseListResponse {
  total: number
  items: RelatedTestCase[]
}

export interface TestPointRequirementOptionListResponse {
  items: TestPointRequirementOption[]
}

export interface BatchGenerateParams {
  project_id: number
  test_point_ids: number[]
  case_type?: string
}

async function createSseGenerator<T>(url: string, payload: unknown): Promise<AsyncGenerator<T>> {
  const baseUrl = import.meta.env?.VITE_API_BASE_URL || ''
  const token = localStorage.getItem('token')
  const response = await fetch(`${baseUrl}${url}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    const errorText = await response.text()
    throw new Error(errorText || '流式请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')

  return (async function* streamGenerator() {
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() ?? ''

      for (const chunk of chunks) {
        const lines = chunk.split('\n')
        for (const line of lines) {
          const trimmedLine = line.trim()
          if (!trimmedLine.startsWith('data:')) {
            continue
          }

          const payloadText = trimmedLine.slice(5).trim()
          if (!payloadText || payloadText === '[DONE]') {
            if (payloadText === '[DONE]') {
              return
            }
            continue
          }

          yield JSON.parse(payloadText) as T
        }
      }
    }
  })()
}

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
      params: {
        project_id: projectId,
        page,
        page_size: pageSize,
      },
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
    const response = (await request.post('/api/v1/test-point/import-xmind', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })) as
      | TestPointApiResponse<XmindPreviewResponse | XmindImportResponse>
      | XmindPreviewResponse
      | XmindImportResponse
    return unwrapApiPayload(response)
  },
}
