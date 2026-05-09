import request, { type ApiResponse } from '@/utils/request'

// ============== 类型定义 ==============

export interface TestCaseStep {
  step: number
  action: string
  param: string
}

export interface TestCase {
  id: number
  case_no: string
  project_id: number
  module: string
  title: string
  precondition?: string
  steps?: TestCaseStep[]
  expected_result?: string
  priority: number
  case_type: string
  exec_script?: string
  create_time?: string
  generate_status?: number
  lifecycle_status?: string
  parent_case_id?: number | null
  ai_change_type?: 'added' | 'modified' | 'deprecated'
}

export interface TestCaseCreate {
  project_id: number
  case_no?: string
  module?: string
  title: string
  precondition?: string
  steps?: TestCaseStep[]
  expected_result?: string
  priority?: number
  case_type?: string
  generate_status?: number
  parent_case_id?: number | null
  ai_change_type?: 'added' | 'modified' | 'deprecated'
}

export interface TestCaseExecute {
  case_id: number
  project_id?: number
  environment?: string
}

export interface TestPointData {
  id: number
  module: string
  function: string
  point: string
  priority: number
}

export interface FlowNodeSubmitData {
  screen_id: number
  screen_order: number
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  screen_name: string
  ocr_text?: string
  summary?: string
  ui_spec_elements?: Array<{
    type: string
    label: string
    semantic?: string
    position?: string
    interactive?: boolean
  }>
}

export interface FlowEdgeSubmitData {
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
}

export interface FlowSortSubmitData {
  nodes: FlowNodeSubmitData[]
  edges: FlowEdgeSubmitData[]
  module_info?: {
    name: string
    description: string
  }
}

export interface TestCaseAIEnhancedRequest {
  project_id: number
  description: string
  case_type?: string
  priority?: number
  enhanced_mode?: boolean
  exec_mode?: string
  extra_requirements?: string
  mode?: 'linear' | 'graph'
  flow_sort_data?: FlowSortSubmitData
  context?: {
    requirement_content: string
    ui_description: string
    test_point?: TestPointData[]
    ui_specs?: unknown[]
    test_points?: unknown[]
    test_point_ids?: number[]
    current_test_point?: unknown
    project_config?: unknown
  }
}

export interface CaseQueryParams {
  project_id?: number
  page?: number
  page_size?: number
  module?: string
  priority?: number
  case_type?: string
  keyword?: string
  lifecycle_status?: string
}

export interface CasePageResponse {
  code: number
  data: {
    items: TestCase[]
    total: number
  }
}

export interface TestCaseGenerateRequest {
  project_id: number
  point_ids?: number[]
}

export interface TestCaseListResponse {
  code: number
  msg: string
  data: {
    test_cases: TestCase[]
  }
}

export interface TestCaseRetryRequest {
  case_ids?: number[]
}

export interface ImportResult {
  success: number
  failed: number
}

export interface StepUpdateData {
  step_number?: number
  action: string
  expected_result: string
  param?: string
}

export interface TestCaseUpdateData {
  module?: string
  title?: string
  precondition?: string
  steps?: StepUpdateData[]
  expected_result?: string
  priority?: number
  case_type?: string
  exec_script?: string
  test_category?: string
}

export interface StepLocatorUpdateData {
  locator_type?: string
  locator_value?: string
  css_selector?: string
  xpath?: string
  confidence?: number
  ai_coordinate?: string | { x: number; y: number }
}

export interface CaseVersionItem {
  id: number
  case_id: number
  version_number: number
  change_summary: string
  create_time: string
}

export interface CaseVersionDetail {
  id: number
  case_id: number
  version_number: number
  change_summary: string
  snapshot: TestCase
  create_time: string
}

export interface CaseVersionCompareResult {
  from_version: CaseVersionDetail
  to_version: CaseVersionDetail
  diff: Record<string, unknown>
}

export interface CaseVersionPageResponse {
  items: CaseVersionItem[]
  total: number
  page: number
  page_size: number
}

export interface CorrectionResponse {
  case_id: number
  status: string
  message: string
}

export interface VerificationResponse {
  case_id: number
  status: string
  message: string
}

export interface AIEnhancedGenerateResponse {
  case_id: number
  case_no: string
  title: string
  name?: string
  module?: string
  case_type?: string
  type?: string
  precondition?: string
  steps: TestCaseStep[]
  test_data: Record<string, Record<string, string | number | boolean | null>>
  expected_result?: string
  priority?: number
  change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
  message: string
  // AI 返回的 change_type 映射为 ai_change_type 入库
}

function extractResponseData<T>(response: ApiResponse<T> | T): T {
  if (response && typeof response === 'object' && 'data' in response && 'code' in response) {
    return (response as ApiResponse<T>).data
  }
  return response as T
}

// ============== API 定义 ==============

export interface LineageNode {
  id: number
  case_no: string
  title: string
  lifecycle_status: string
  iteration_id?: number | null
  created_at?: string | null
  parent_case_id?: number | null
  children: LineageNode[]
}

export interface LineageResponse {
  root: LineageNode
  ancestors: LineageNode[]
  chain_length: number
  warning: boolean
  warning_threshold: number
}

export const testCaseApi = {
  getCaseList: async (params: CaseQueryParams): Promise<CasePageResponse> => {
    const response = await request.get('/api/v1/testCase/', { params })
    return response as unknown as CasePageResponse
  },

  getCase: async (id: number): Promise<TestCase> => {
    const response = await request.get(`/api/v1/testCase/${id}`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  getCaseDetail: async (caseId: number): Promise<TestCase> => {
    const response = await request.get(`/api/v1/testCase/${caseId}`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  createCase: async (data: TestCaseCreate): Promise<TestCase> => {
    const response = await request.post('/api/v1/testCase/', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  updateCase: async (id: number, data: TestCaseUpdateData): Promise<TestCase> => {
    const response = await request.put(`/api/v1/testCase/${id}`, data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  updateStepLocator: async (
    caseId: number,
    stepId: number,
    data: StepLocatorUpdateData
  ): Promise<Record<string, unknown>> => {
    const response = await request.put(`/api/v1/testCase/${caseId}/steps/${stepId}/locator`, data)
    return extractResponseData<Record<string, unknown>>(
      response as unknown as ApiResponse<Record<string, unknown>> | Record<string, unknown>
    )
  },

  getCaseVersions: async (
    caseId: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<CaseVersionPageResponse> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/versions`, {
      params: { page, page_size: pageSize },
    })
    return extractResponseData<CaseVersionPageResponse>(
      response as unknown as ApiResponse<CaseVersionPageResponse> | CaseVersionPageResponse
    )
  },

  getCaseVersionDetail: async (caseId: number, versionId: number): Promise<CaseVersionDetail> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/versions/${versionId}`)
    return extractResponseData<CaseVersionDetail>(
      response as unknown as ApiResponse<CaseVersionDetail> | CaseVersionDetail
    )
  },

  compareCaseVersions: async (
    caseId: number,
    fromVersion: number,
    toVersion: number
  ): Promise<CaseVersionCompareResult> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/versions/compare`, {
      params: { from: fromVersion, to: toVersion },
    })
    return extractResponseData<CaseVersionCompareResult>(
      response as unknown as ApiResponse<CaseVersionCompareResult> | CaseVersionCompareResult
    )
  },

  rollbackCaseVersion: async (caseId: number, versionId: number): Promise<TestCase> => {
    const response = await request.post(`/api/v1/testCase/${caseId}/versions/${versionId}/restore`)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  startCorrection: async (caseId: number): Promise<CorrectionResponse> => {
    const response = await request.post(`/api/v1/testCase/${caseId}/start-correction`)
    return extractResponseData<CorrectionResponse>(
      response as unknown as ApiResponse<CorrectionResponse> | CorrectionResponse
    )
  },

  submitVerification: async (caseId: number): Promise<VerificationResponse> => {
    const response = await request.post(`/api/v1/testCase/${caseId}/submit-verification`)
    return extractResponseData<VerificationResponse>(
      response as unknown as ApiResponse<VerificationResponse> | VerificationResponse
    )
  },

  deleteCase: async (id: number): Promise<void> => {
    await request.delete(`/api/v1/testCase/${id}`)
  },

  batchDeleteCases: async (
    caseIds: number[]
  ): Promise<{
    success_count: number
    fail_count: number
    not_found_count: number
    deleted_ids: number[]
    total: number
    message: string
  }> => {
    const response = await request.post('/api/v1/testCase/batch-delete', { caseIds: caseIds })
    return extractResponseData<{
      success_count: number
      fail_count: number
      not_found_count: number
      deleted_ids: number[]
      total: number
      message: string
    }>(
      response as unknown as
        | ApiResponse<{
            success_count: number
            fail_count: number
            not_found_count: number
            deleted_ids: number[]
            total: number
            message: string
          }>
        | {
            success_count: number
            fail_count: number
            not_found_count: number
            deleted_ids: number[]
            total: number
            message: string
          }
    )
  },

  batchRestoreCases: async (
    caseIds: number[]
  ): Promise<{
    success_count: number
    fail_count: number
    not_found_count: number
    restored_ids: number[]
    total: number
    message: string
  }> => {
    const response = await request.post('/api/v1/testCase/batch-restore', { caseIds: caseIds })
    return extractResponseData<{
      success_count: number
      fail_count: number
      not_found_count: number
      restored_ids: number[]
      total: number
      message: string
    }>(
      response as unknown as
        | ApiResponse<{
            success_count: number
            fail_count: number
            not_found_count: number
            restored_ids: number[]
            total: number
            message: string
          }>
        | {
            success_count: number
            fail_count: number
            not_found_count: number
            restored_ids: number[]
            total: number
            message: string
          }
    )
  },

  executeCase: async (data: TestCaseExecute): Promise<TestCase> => {
    const response = await request.post('/api/v1/testCase/execute', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  aiGenerateCase: async (data: TestCaseAIGenerate): Promise<TestCase> => {
    const response = await request.post('/api/v1/testCase/ai-generate', data)
    return extractResponseData<TestCase>(response as unknown as ApiResponse<TestCase> | TestCase)
  },

  aiGenerateCaseEnhanced: async (
    data: TestCaseAIEnhancedRequest
  ): Promise<AIEnhancedGenerateResponse> => {
    const response = await request.post('/api/v1/testCase/ai-generate-enhanced', data)
    return extractResponseData<AIEnhancedGenerateResponse>(
      response as unknown as ApiResponse<AIEnhancedGenerateResponse> | AIEnhancedGenerateResponse
    )
  },

  generate: async (
    data: TestCaseGenerateRequest
  ): Promise<AsyncGenerator<{ progress: number; message?: string }>> => {
    const response = await request.post('/api/v1/testCase/generate', data, {
      responseType: 'stream',
    })

    return new Promise((resolve) => {
      const stream = response.data as ReadableStream
      const reader = stream.getReader()

      const generator = (async function* () {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = new TextDecoder('utf-8').decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.trim()) {
              try {
                const progress: { progress: number; message?: string } = JSON.parse(line)
                yield progress
              } catch (e: unknown) {
                console.error('解析进度数据失败:', e instanceof Error ? e.message : String(e))
              }
            }
          }
        }
      })()

      resolve(generator)
    })
  },

  retry: async (
    projectId: number,
    data: TestCaseRetryRequest
  ): Promise<AsyncGenerator<{ progress: number; message?: string }>> => {
    const response = await request.post(`/api/v1/testCase/retry/${projectId}`, data, {
      responseType: 'stream',
    })

    return new Promise((resolve) => {
      const stream = response.data as ReadableStream
      const reader = stream.getReader()

      const generator = (async function* () {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = new TextDecoder('utf-8').decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.trim()) {
              try {
                const progress: { progress: number; message?: string } = JSON.parse(line)
                yield progress
              } catch (e: unknown) {
                console.error('解析进度数据失败:', e instanceof Error ? e.message : String(e))
              }
            }
          }
        }
      })()

      resolve(generator)
    })
  },

  importCases: async (file: File): Promise<ImportResult> => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await request.post('/api/v1/testCase/import', formData)
    return extractResponseData<ImportResult>(
      response as unknown as ApiResponse<ImportResult> | ImportResult
    )
  },

  getLineage: async (caseId: number): Promise<LineageResponse> => {
    const response = await request.get(`/api/v1/testCase/${caseId}/lineage`)
    return extractResponseData<LineageResponse>(
      response as unknown as ApiResponse<LineageResponse> | LineageResponse
    )
  },
}

// @ts-ignore: 保留向后兼容引用
export const caseApi = testCaseApi

export default testCaseApi
