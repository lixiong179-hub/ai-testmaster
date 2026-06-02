import request from '@/utils/request'

export interface GenerationBatchCreatePayload {
  project_id: number
  entry_type: 'NEW_FEATURE_GENERATION'
  scenario_type: 'B1_REQUIREMENT_TESTPOINT' | 'A1_REQUIREMENT_TESTPOINT_UI'
  generation_strategy: 'REQUIREMENT_TESTPOINT_STANDARD_GENERATION' | 'FULL_CONTEXT_GENERATION_LITE'
  requirement_file_ids: number[]
  test_point_ids: number[]
  ui_screen_ids: number[]
  client_request_id?: string
}

export interface GenerationBatchResponse {
  id: number
  batch_no: string
  project_id: number
  user_id: number
  entry_type: string
  scenario_type: string
  generation_strategy: string
  status: string
  requirement_file_ids: number[]
  test_point_ids: number[]
  ui_screen_ids: number[]
  context_stats: Record<string, unknown>
  warnings: NormalizedWarning[]
  evidence_refs: Record<string, unknown>
  quality_summary: Record<string, unknown>
  created_at: string
  updated_at: string | null
}

export interface NormalizedWarning {
  code: string
  message: string
  detail: Record<string, unknown>
}

export interface GenerationBatchUpdatePayload {
  status?: string
  context_stats?: Record<string, unknown>
  warnings?: NormalizedWarning[]
  evidence_refs?: Record<string, unknown>
  quality_summary?: Record<string, unknown>
}

export interface PreviewCasePayload {
  client_id: string
  source_test_point_id?: number | null
  requirement_file_id?: number | null
  title: string
  module?: string
  precondition?: string
  steps: PreviewStepPayload[]
  expected_result: string
  priority?: number
  case_type?: string
  case_category?: string | null
  quality_status?: 'passed' | 'warning' | 'pending_review' | 'rejected'
  quality_issues?: Record<string, unknown>[]
  selected_for_save?: boolean
  source_refs?: Record<string, unknown>
  classification?: string | null
  history_case_id?: number | null
  update_action?: 'create_new' | 'update_existing' | 'skip' | 'deprecate' | null
  diff_fields?: Record<string, { old: unknown; new: unknown }> | null
}

export interface PreviewStepPayload {
  step: string | number
  action: string
  param?: string
  expected_result?: string | null
  test_data?: Record<string, unknown> | Record<string, unknown>[] | null
  description?: string | null
  ui_elements?: (string | Record<string, unknown>)[] | null
  action_type?: string | null
  input_value?: string | null
  target_element?: string | null
}

export interface GenerationBatchSavePayload {
  idempotency_key: string
  save_mode: 'draft' | 'formal' | 'passed_only'
  cases: PreviewCasePayload[]
}

export interface BatchSaveFailureItem {
  client_id?: string | null
  title?: string | null
  reason: string
}

export interface GenerationBatchSaveResponse {
  batch_id: number
  idempotency_key: string
  save_mode: string
  saved_count: number
  failed_count: number
  saved_case_ids: number[]
  failures: BatchSaveFailureItem[]
  status: 'saved' | 'partial_saved' | 'failed'
}

function extractData<T>(response: unknown): T {
  const resp = response as { code?: number; data?: T }
  if (resp && resp.data !== undefined) return resp.data
  return response as T
}

export const generationBatchApi = {
  create: async (data: GenerationBatchCreatePayload): Promise<GenerationBatchResponse> => {
    const response = await request.post('/api/v1/generation-batches', data)
    return extractData<GenerationBatchResponse>(response)
  },

  get: async (batchId: number): Promise<GenerationBatchResponse> => {
    const response = await request.get(`/api/v1/generation-batches/${batchId}`)
    return extractData<GenerationBatchResponse>(response)
  },

  update: async (batchId: number, data: GenerationBatchUpdatePayload): Promise<GenerationBatchResponse> => {
    const response = await request.patch(`/api/v1/generation-batches/${batchId}`, data)
    return extractData<GenerationBatchResponse>(response)
  },

  save: async (batchId: number, data: GenerationBatchSavePayload): Promise<GenerationBatchSaveResponse> => {
    const response = await request.post(`/api/v1/generation-batches/${batchId}/save`, data)
    return extractData<GenerationBatchSaveResponse>(response)
  },
}
