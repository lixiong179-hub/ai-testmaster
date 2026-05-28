import request from '@/utils/request'

export interface UIPrototypeFlowSummary {
  has_flow: boolean
  node_count: number
  edge_count: number
  entry_screen?: string
  end_screens?: string[]
  branch_count: number
  exception_count: number
  warning_count: number
  key_path_count: number
}

export interface UIFlowGenerateResponse {
  code: number
  msg: string
  message?: string
  data: {
    success: boolean
  }
}

export const uiPrototypeFlowApi = {
  generatePageFlow: async (prototypeProjectId: number): Promise<UIFlowGenerateResponse> => {
    return request.post('/api/v1/ui-prototype/flow/generate', {
      prototype_project_id: prototypeProjectId,
    })
  },
}
