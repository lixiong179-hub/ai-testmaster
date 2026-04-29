export type TestPointPriority = 1 | 2 | 3

export interface TestPoint {
  id: number
  project_id: number
  requirement_id?: number | null
  module: string
  function: string
  point: string
  priority: TestPointPriority
  create_time: string
  created_by?: string | null
  ai_prompt?: string | null
  test_case_count?: number
}

export interface TestPointAnalyzeRequest {
  project_id: number
}

export interface TestPointDraft {
  id?: number
  module: string
  function?: string
  point: string
  priority: number
  ai_prompt?: string | null
  create_time?: string
}

export interface TestPointExtractRequest {
  file_id: number
}

export interface TestPointExtractResponse {
  total: number
  items: TestPointDraft[]
}

export interface TestPointBatchSaveResponse {
  saved_count: number
  total_submitted: number
  items: Array<{
    id: number
    module: string
    function: string
    point: string
    priority: number
  }>
}

export interface AnalysisProgress {
  progress: number
  message?: string
  status?: string
  data?: TestPoint[]
}

export interface TestPointListParams {
  module?: string
  priority?: number
  created_by?: string
  requirement_id?: number
  keyword?: string
  created_from?: string
  created_to?: string
  sort_by?: 'create_time' | 'priority' | 'module' | 'point'
  sort_order?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export interface TestPointFormData {
  project_id: number
  module: string
  function?: string
  point: string
  priority: number
  ai_prompt?: string
}

export interface TestPointUpdateData {
  project_id: number
  module?: string
  function?: string
  point?: string
  priority?: number
  ai_prompt?: string
}

export interface RelatedTestCase {
  id: number
  case_no: string
  title: string
  module: string
  priority: number
  case_type?: string | null
  generate_status: number
  create_time: string
}

export interface TestPointListStats {
  total: number
  high_priority_count: number
  medium_priority_count: number
  low_priority_count: number
  generated_case_count: number
}

export interface TestPointRequirementOption {
  id: number
  req_no: string
  title: string
}
