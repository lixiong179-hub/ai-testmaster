import { type ApiResponse } from '@/utils/request'
import type { TestCase, TestCaseStep, TestCaseAIGenerate } from '@/types/testCase'

export type { TestCase, TestCaseStep, TestCaseAIGenerate }

export interface TestCaseApiStep {
  step?: number | string
  action?: string
  param?: string
  expected_result?: string
  action_type?: string
  input_value?: string
  target_element?: string
  description?: string
  display_action?: string
  ui_elements?: Array<{ type?: string; label?: string }>
}

export interface TestCaseCreate {
  project_id: number
  test_point_id?: number | null
  case_no?: string
  module?: string
  title: string
  precondition?: string
  steps?: TestCaseApiStep[]
  expected_result?: string
  priority?: number
  case_type?: string
  test_category?: string
  test_data?: Record<string, Record<string, string | number | boolean | null>>
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

export interface FlowMetaData {
  parent_node_id?: string
  parent_main_node_id?: string
  trigger_condition?: string
  pre_action?: string
  expected_result?: string
  bypass_reason?: string
  note?: string
}

export interface FlowNodeSubmitData {
  screen_id: number
  screen_order: number
  main_order?: number
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
    state?: string
    description?: string
  }>
  flow_meta?: FlowMetaData
  image_url?: string
}

export interface FlowEdgeSubmitData {
  source: string
  target: string
  edge_type: 'normal' | 'branch' | 'exception' | 'bypass'
  condition?: string
  label: string
  trigger_action?: string
  pre_action?: string
  note?: string
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
    history_cases?: unknown[]
    base_case?: Record<string, unknown>
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

export interface TestCaseListParams {
  page?: number
  page_size?: number
  keyword?: string
  module?: string
  priority?: number
  case_type?: string
  status?: string
  created_by?: string
  target_device?: string
  sort_by?: 'create_time' | 'priority' | 'title' | 'update_time'
  sort_order?: 'asc' | 'desc'
}

export interface SupplementResponse {
  test_case: TestCase
  inferred_capabilities: Array<{ name: string; description: string }>
  questions: Array<{ question: string }>
  change_summary: Array<{ field: string; old_value: string; new_value: string }>
}

export interface QualityAnalysisResult {
  project_id: number
  total_cases: number
  average_score: number
  overall_score: number
  project_requirement_coverage: number
  project_requirement_details: Record<string, unknown> | null
  dimensions?: Array<{
    name: string
    label?: string
    score: number
    summary?: string
    detail?: string
    suggestions?: string[]
  }>
  optimization?: {
    items: Array<{
      type: string
      target: string
      action: string
      impact: string
    }>
  }
  reports: Array<{
    case_id: number
    case_name: string
    overall_score: number
    overall_level: string
    suggestions: string[]
    analyzed_at: string
  }>
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
  test_category?: string
  case_category?: string
  type?: string
  precondition?: string
  steps: TestCaseApiStep[]
  test_data: Record<string, Record<string, string | number | boolean | null>>
  expected_result?: string
  priority?: number
  change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
  message: string
}

export interface AIEnhancedGenerateQuality {
  passed: boolean
  overall_grade: string
  overall_score: number
  d_grade_count: number
  [key: string]: unknown
}

export interface AIEnhancedGenerateResult {
  cases: AIEnhancedGenerateResponse[]
  quality?: AIEnhancedGenerateQuality
}

export interface BatchCreateRequest {
  cases: TestCaseCreate[]
}

export interface BatchCreateResponse {
  success_count: number
  fail_count: number
  created_ids: number[]
  errors: string[]
  total: number
  message: string
}

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

export function extractResponseData<T>(response: ApiResponse<T> | T): T {
  if (response && typeof response === 'object' && 'data' in response && 'code' in response) {
    return (response as ApiResponse<T>).data
  }
  return response as T
}
