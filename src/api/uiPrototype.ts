import request from '@/utils/request'

export interface UIPrototypeProject {
  id: number
  project_id: number
  iteration_id?: number
  name: string
  description?: string
  source: string
  screen_count: number
  parsed_count: number
  parse_status: string
  create_time: string
  update_time: string
}

export interface UIElement {
  type: 'button' | 'input' | 'text' | 'icon' | 'link' | 'image' | 'container'
  label: string
  description?: string
  position: { x: number; y: number; width?: number; height?: number }
  interactive?: boolean
  state?: string
  semantic_hint?: string
}

export interface UILayoutConstraint {
  constraint: string
  priority: 'high' | 'medium' | 'low'
  target?: string
  value?: string
}

export interface UIVisualStyle {
  background_color?: string
  theme_color?: string
  border_radius_style?: string
  shadow_style?: string
  typography?: Record<string, unknown>
  spacing?: Record<string, unknown>
}

export interface UINavigationFlow {
  flows?: Array<{ from: string; to: string; trigger?: string }>
  navigation?: Array<{ screen: string; actions?: string[] }>
}

export interface UISpec {
  elements?: UIElement[]
  flows?: Array<{ from: string; to: string; trigger?: string }>
  navigation?: Array<{ screen: string; actions?: string[] }>
  layout_constraints?: UILayoutConstraint[]
  visual_style?: UIVisualStyle
  warnings?: string[]
}

export interface UIScreen {
  id: number
  project_id: number
  prototype_project_id?: number
  prototype_name: string
  screen_name: string
  screen_order: number
  original_file_path?: string
  original_file_name?: string
  file_type: string
  file_size?: number
  parse_status: string
  parse_status_text: string
  parse_model?: string
  parse_error?: string
  summary?: string
  element_count: number
  button_count: number
  input_count: number
  is_entry_point: boolean
  is_end_point: boolean
  review_status: string
  create_time: string
  update_time: string
  ui_spec?: UISpec
  layout_checks?: Array<Record<string, unknown>>
  navigation_flow?: UINavigationFlow
}

export interface UIScreenListResponse {
  code: number
  msg: string
  data: {
    total: number
    items: UIScreen[]
    page: number
    page_size: number
  }
}

export interface UIPrototypeUploadResponse {
  code: number
  message: string
  data: {
    screen_ids: number[]
    total: number
  }
}

export interface UIScreenDetailResponse {
  screen: UIScreen
  spec?: UISpec
}

export interface UIParseResponse {
  task_id: string
  screen_ids: number[]
  message: string
}

export interface UIScreenOrderResponse {
  screen_id: number
  screen_order: number
  message: string
}

export interface UIDeleteResponse {
  message: string
}

export const uiPrototypeApi = {
  getUIPrototypeProjectList: async (
    projectId: number,
    page: number = 1,
    pageSize: number = 100,
    iterationId?: number
  ): Promise<UIPrototypeProject[]> => {
    const params: Record<string, string | number> = { page, page_size: pageSize }
    if (iterationId) {
      params.iteration_id = iterationId
    }
    return request.get(`/api/v1/ui-prototype/project/list/${projectId}`, { params })
  },

  createUIPrototypeProject: async (
    projectId: number,
    name: string,
    description: string = '',
    source: string = 'manual'
  ): Promise<UIPrototypeProject> => {
    return request.post('/api/v1/ui-prototype/project', {
      project_id: projectId,
      name,
      description,
      source,
    })
  },

  uploadUIScreens: async (
    projectId: number,
    files: File[],
    prototypeName: string,
    prototypeProjectId?: number,
    iterationId?: number
  ): Promise<UIPrototypeUploadResponse> => {
    const formData = new FormData()
    formData.append('project_id', projectId.toString())
    formData.append('prototype_name', prototypeName)
    if (prototypeProjectId) {
      formData.append('prototype_project_id', prototypeProjectId.toString())
    }
    if (iterationId) {
      formData.append('iteration_id', iterationId.toString())
    }
    files.forEach((file) => {
      formData.append('files', file)
    })
    return request.post('/api/v1/ui-prototype/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  getUIScreenList: async (
    projectId: number,
    prototypeProjectId?: number,
    page: number = 1,
    pageSize: number = 100
  ): Promise<UIScreenListResponse> => {
    const params: Record<string, string | number> = { page, page_size: pageSize }
    if (prototypeProjectId) {
      params.prototype_project_id = prototypeProjectId
    }
    return request.get(`/api/v1/ui-prototype/screens/${projectId}`, { params })
  },

  getUIScreenDetail: async (screenId: number): Promise<UIScreenDetailResponse> => {
    return request.get(`/api/v1/ui-prototype/screen/${screenId}`)
  },

  deleteUIScreen: async (screenId: number): Promise<UIDeleteResponse> => {
    return request.delete(`/api/v1/ui-prototype/screen/${screenId}`)
  },

  deleteUIPrototypeProject: async (prototypeProjectId: number): Promise<UIDeleteResponse> => {
    return request.delete(`/api/v1/ui-prototype/project/${prototypeProjectId}`)
  },

  parseUIScreens: async (
    screenIds: number[],
    prototypeProjectId?: number,
    parseMode?: string
  ): Promise<UIParseResponse> => {
    return request.post('/api/v1/ui-prototype/parse', {
      screen_ids: screenIds,
      prototype_project_id: prototypeProjectId,
      parse_mode: parseMode,
    })
  },

  updateUIScreenOrder: async (
    screenId: number,
    screenOrder: number
  ): Promise<UIScreenOrderResponse> => {
    return request.put(`/api/v1/ui-prototype/screen/${screenId}/order`, {
      screen_order: screenOrder,
    })
  },
}

export const UIPrototypeAPI = uiPrototypeApi
export default uiPrototypeApi
