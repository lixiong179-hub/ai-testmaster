import axios from '@/utils/request'

export interface LocatorCoverage {
  total_steps: number
  located_steps: number
  pending_steps: number
  failed_steps: number
  coverage_percentage: number
}

export interface LocatorInfo {
  css_selector?: string
  xpath?: string
  element_type?: string
  ai_coordinate?: { x: number; y: number }
  confidence?: number
  locator_type?: string
  locator_value?: string
}

export interface StepTestData {
  field_name: string
  field_type: string
  data_value: string | null
  generation_rule: string
}

export interface ExecutionHistoryItem {
  execution_id: number
  status: string
  execute_time: string
  duration: number
  error_message?: string
}

export interface TechnicalStep {
  step_id: number
  step_number: number
  action: string
  description?: string
  display_action?: string
  expected_result: string
  has_locator: boolean
  locator_status: 'pending' | 'recorded' | 'failed'
  locator?: LocatorInfo
  test_data?: StepTestData[]
}

export interface TechnicalView {
  case_id: number
  case_no: string
  title: string
  module?: string
  precondition?: string
  precondition_steps?: PreconditionStep[]
  expected_result?: string
  priority: number
  case_type: string
  steps: TechnicalStep[]
  locator_coverage: number
  execution_history: ExecutionHistoryItem[]
}

export interface PreconditionStep {
  id?: number
  test_case_id?: number
  step_number: number
  action: string
  expected_result?: string
  action_type?: string
  input_value?: string
  target_element?: string
  has_locator?: boolean
  locator_status?: 'pending' | 'recorded' | 'failed'
  locator?: LocatorInfo
}

export interface ViewStatistics {
  total_steps: number
  business_view_steps: number
  technical_view_steps: number
  located_steps: number
  pending_steps: number
  locator_coverage: number
}

export interface ExportJsonResponse {
  case_id: number
  case_no: string
  title: string
  steps: TechnicalStep[]
  precondition_steps: PreconditionStep[]
}

export interface ParsePreconditionResponse {
  case_id: number
  steps: PreconditionStep[]
  message: string
}

export interface PreconditionStepsSaveResponse {
  case_id: number
  saved_count: number
  steps: PreconditionStep[]
}

export interface PreconditionStepsResponse {
  case_id: number
  steps: PreconditionStep[]
}

export const testCaseViewApi = {
  getTechnicalView: async (caseId: number): Promise<TechnicalView> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/technical-view`)
    return response.data
  },

  getLocatorCoverage: async (caseId: number): Promise<LocatorCoverage> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/locator-coverage`)
    return response.data
  },

  updateStepViewConfig: async (
    stepId: number,
    config: {
      is_business_view?: number
      is_technical_view?: number
    }
  ): Promise<{ success: boolean }> => {
    const response = await axios.put(`/api/v1/test-case/steps/${stepId}/view-config`, config)
    return response.data
  },

  batchUpdateViewConfig: async (
    caseId: number,
    viewType: 'business' | 'technical',
    visible: boolean
  ): Promise<{ updated_count: number }> => {
    const response = await axios.put(`/api/v1/test-case/${caseId}/batch-view-config`, {
      view_type: viewType,
      visible,
    })
    return response.data
  },

  /**
   * 单条用例导出标准双 Sheet Excel。
   * 返回完整 AxiosResponse 以便读取 Content-Disposition 等响应头。
   */
  exportToExcel: async (caseId: number) => {
    return await axios.post(`/api/v1/test-case/${caseId}/export-excel`, {}, { responseType: 'blob' })
  },

  /**
   * 批量导出功能用例 Excel（按模块分组）。
   * 响应头 `X-Export-Skipped-Count` 表示因权限被忽略的用例数（可能不存在）。
   */
  exportToFunctionalExcel: async (caseIds: number[]) => {
    return await axios.post(
      '/api/v1/test-case/export-functional-excel',
      { case_ids: caseIds },
      { responseType: 'blob' }
    )
  },

  exportToMarkdown: async (caseId: number): Promise<string> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/export-markdown`)
    return response.data
  },

  exportToHtml: async (caseId: number): Promise<string> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/export-html`)
    return response.data
  },

  exportToPython: async (caseId: number): Promise<string> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/export-python`)
    return response.data
  },

  exportToJson: async (caseId: number): Promise<ExportJsonResponse> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/export-json`)
    return response.data
  },

  getViewStatistics: async (caseId: number): Promise<ViewStatistics> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/view-statistics`)
    return response.data
  },

  addStepLocator: async (
    stepId: number,
    locator: {
      css_selector?: string
      xpath?: string
      element_type?: string
    }
  ): Promise<{
    locator_id: number
    message: string
    css_selector?: string
    xpath?: string
  }> => {
    const response = await axios.post(`/api/v1/test-case/steps/${stepId}/locator`, locator)
    return response.data
  },

  parsePrecondition: async (caseId: number): Promise<ParsePreconditionResponse> => {
    const response = await axios.post(`/api/v1/test-case/${caseId}/parse-precondition`)
    return response.data
  },

  batchSavePreconditionSteps: async (
    caseId: number,
    data: { steps: PreconditionStep[] }
  ): Promise<PreconditionStepsSaveResponse> => {
    const response = await axios.put(`/api/v1/test-case/${caseId}/precondition-steps`, data)
    return response.data
  },

  getPreconditionSteps: async (caseId: number): Promise<PreconditionStepsResponse> => {
    const response = await axios.get(`/api/v1/test-case/${caseId}/precondition-steps`)
    return response.data
  },

  downloadFile: (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },
}

export default testCaseViewApi
