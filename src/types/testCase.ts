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
