import type {
  RelatedTestCase,
  TestPoint,
  TestPointListStats,
  TestPointRequirementOption,
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
  point: string
  priority: number
  precondition?: string
}

export interface XmindPreviewCaseStep {
  step_number: number
  action: string
  description?: string
  display_action?: string
  expected_result: string
}

export interface XmindPreviewCaseItem {
  module: string
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
  total_paths?: number
}

export interface XmindImportResponse {
  saved_count: number
  saved_case_count?: number
  total_parsed: number
  skipped_count: number
  skipped_reasons: string[]
  ai_timeout?: boolean
}

export interface XmindImportProgressEvent {
  completed_batches: number
  total_batches: number
  completed_paths: number
  total_paths: number
  percentage: number
  status?: string
}

export interface XmindImportSSECallbacks {
  onProgress?: (event: XmindImportProgressEvent) => void
  onResult?: (data: XmindPreviewResponse | XmindImportResponse) => void
  onError?: (detail: string, errorType?: string) => void
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
  test_point_ids?: number[]
  case_type?: string
}

export function unwrapApiPayload<T>(response: TestPointApiResponse<T> | T): T {
  if (
    response &&
    typeof response === 'object' &&
    'data' in response &&
    (('code' in response && typeof response.code === 'number') ||
      'message' in response ||
      'msg' in response)
  )
    return response.data as T
  return response as T
}

export async function createSseGenerator<T>(
  url: string,
  payload: unknown
): Promise<AsyncGenerator<T>> {
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
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() ?? ''
      for (const chunk of chunks) {
        for (const line of chunk.split('\n')) {
          const trimmedLine = line.trim()
          if (!trimmedLine.startsWith('data:')) continue
          const payloadText = trimmedLine.slice(5).trim()
          if (!payloadText || payloadText === '[DONE]') {
            if (payloadText === '[DONE]') return
            continue
          }
          yield JSON.parse(payloadText) as T
        }
      }
    }
  })()
}
