import request from '@/utils/request'

export interface HistoryAssetItem {
  id: number
  project_id: number
  asset_type: 'excel' | 'xmind' | 'system_cases'
  original_filename: string | null
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed'
  parse_error: string | null
  case_count: number
  batch_id: number | null
  created_at: string
  updated_at: string | null
}

export interface HistoryParsedCase {
  title: string
  module: string
  precondition: string
  steps: { action: string; expected_result: string }[]
  expected_result: string
  priority: number
  case_type: string
}

export interface HistoryAssetDetail extends HistoryAssetItem {
  parsed_cases: HistoryParsedCase[]
}

export type HistoryClassification = 'REUSE_CASE' | 'UPDATE_CASE' | 'NEW_CASE' | 'DEPRECATED_CASE' | 'CONFIRM_REQUIRED'

export interface HistoryClassificationItem {
  client_id: string
  classification: HistoryClassification
  confidence: number
  history_case: HistoryParsedCase | null
  suggested_case: HistoryParsedCase | null
  diff_fields: Record<string, { old: unknown; new: unknown }> | null
  reason: string
  matched_system_case_id: number | null
}

export interface HistoryClassificationSummary {
  reuse_count: number
  update_count: number
  new_count: number
  deprecated_count: number
  confirm_required_count: number
  total: number
}

export interface HistoryClassificationResponse {
  summary: HistoryClassificationSummary
  items: HistoryClassificationItem[]
}

function extractData<T>(response: unknown): T {
  const resp = response as { code?: number; data?: T }
  if (resp && resp.data !== undefined) return resp.data
  return response as T
}

export const historyAssetApi = {
  upload: async (projectId: number, file: File, assetType: string): Promise<HistoryAssetItem> => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('project_id', String(projectId))
    formData.append('asset_type', assetType)
    const response = await request.post('/api/v1/history-assets/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return extractData<HistoryAssetItem>(response)
  },

  getList: async (projectId: number): Promise<HistoryAssetItem[]> => {
    const response = await request.get('/api/v1/history-assets', { params: { project_id: projectId } })
    return extractData<HistoryAssetItem[]>(response)
  },

  getDetail: async (assetId: number): Promise<HistoryAssetDetail> => {
    const response = await request.get(`/api/v1/history-assets/${assetId}`)
    return extractData<HistoryAssetDetail>(response)
  },

  align: async (params: {
    project_id: number
    history_asset_ids: number[]
    requirement_file_ids?: number[]
    ui_screen_ids?: number[]
  }): Promise<HistoryClassificationResponse> => {
    const formData = new FormData()
    formData.append('project_id', String(params.project_id))
    formData.append('history_asset_ids', JSON.stringify(params.history_asset_ids))
    if (params.requirement_file_ids) formData.append('requirement_file_ids', JSON.stringify(params.requirement_file_ids))
    if (params.ui_screen_ids) formData.append('ui_screen_ids', JSON.stringify(params.ui_screen_ids))
    const response = await request.post('/api/v1/history-assets/align', formData)
    return extractData<HistoryClassificationResponse>(response)
  },

  importSystemCases: async (projectId: number, caseIds: number[]): Promise<HistoryAssetItem> => {
    const formData = new FormData()
    formData.append('project_id', String(projectId))
    formData.append('case_ids', JSON.stringify(caseIds))
    const response = await request.post('/api/v1/history-assets/import-system-cases', formData)
    return extractData<HistoryAssetItem>(response)
  },
}
