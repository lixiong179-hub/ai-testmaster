// 测试用例类型定义
export interface StepLocator {
  css_selector?: string
  xpath?: string
  element_type?: string
  confidence?: number
}

export interface TestCaseStep {
  step?: number | string
  action?: string
  param?: string
  expected_result?: string
  test_data?: Record<string, string | number | boolean | null>
  description?: string
  display_action?: string
  has_locator?: boolean
  locator?: StepLocator | null
  is_business_view?: boolean
  step_number?: number
  step_id?: number
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
  test_category?: string
  exec_script?: string
  create_time?: string
  generate_status?: number
  lifecycle_status?: string
  parent_case_id?: number | null
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  depends_on?: string | null
  anchor_step?: number | null
  fallback_steps?: string | null
  setup_api_calls?: string | null
}

export interface TestCaseListResponse {
  items: TestCase[]
  total: number
  page: number
  page_size: number
  stats?: {
    total: number
    automated: number
    manual: number
    high_priority: number
  }
}

export interface TestCaseAIGenerate {
  scene: string
  case_type: string
}
