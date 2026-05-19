import { TaskStatus, ExecutionStatus } from '../api/testTask'

export { TaskStatus, ExecutionStatus }

export interface TestTask {
  id: number
  task_name: string
  project_id: number
  description?: string
  case_ids: number[]
  executor_id: number
  status: number
  start_time?: string
  end_time?: string
  success_count: number
  fail_count: number
  total_count: number
  progress: number
  create_time: string
  update_time?: string
}

export interface TestResult {
  id: number
  task_id: number
  project_id: number
  case_id: number
  case_no: string
  exec_status: number
  exec_time: string
  exec_log?: string
  error_msg?: string
  screenshot_url?: string
  create_time: string
  update_time?: string
}

export interface StepResult {
  step_number: number
  action: string
  status: string
  start_time?: string
  end_time?: string
  duration_ms?: number
  error_message?: string
  execution_detail?: string
}

export interface TaskExecutionResult {
  execution_id: number
  test_case_id: number
  status: string
  start_time: string
  end_time?: string
  duration_ms: number
  step_results: StepResult[]
  actual_result?: string
  error_message?: string
}

export interface ExecutionLog {
  task_id: number
  case_id?: number
  case_no?: string
  status: number
  log: string
  timestamp: string
}

export interface ExecutionProgress {
  task_id: number
  progress: number
  success_count: number
  fail_count: number
  current_case: number
  total_cases: number
  timestamp: string
}

export interface TaskSummary {
  task_id: number
  total_cases: number
  passed_cases: number
  failed_cases: number
  blocked_cases: number
  total_duration_ms: number
  pass_rate: number
}

export function extractTaskResponseData<T>(response: unknown): T {
  const r = response as Record<string, unknown> | undefined
  const data = r?.data
  const deepData = (data as Record<string, unknown> | undefined)?.data
  if (deepData && typeof deepData === 'object') return deepData as T
  if (data && typeof data === 'object') return data as T
  if (r && typeof r === 'object') return r as T
  return {} as T
}
