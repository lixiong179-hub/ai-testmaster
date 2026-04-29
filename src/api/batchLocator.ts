/**
 * 批量元素定位API
 */
import request from '@/utils/request'

export interface BatchRecordRequest {
  skip_existing?: boolean
  execute_precondition?: boolean
  use_mcp?: boolean
}

export interface BatchRecordResponse {
  success: boolean
  message: string
  case_id: number
  task_id?: string
}

export interface BatchRecordStatus {
  case_id: number
  status: string
  progress: number
  current_step?: number
  total_steps: number
  message?: string
}

export interface StepResult {
  step_id: number
  step_number: number
  action: string
  success: boolean
  message: string
  locator_id?: number
  css_selector?: string
  confidence?: number
  duration: number
  locator_type?: string
  locator_value?: string
}

export interface BatchRecordReport {
  case_id: number
  case_title: string
  total_steps: number
  success_count: number
  failed_count: number
  skipped_count: number
  start_time: string
  end_time?: string
  duration: number
  status: string
  step_results: StepResult[]
  error_message?: string
}

export interface BatchTask {
  case_id: number
  case_title: string
  status: string
  progress: number
  total_steps: number
  completed_steps: number
}

/**
 * 启动批量元素定位记录
 */
export const startBatchRecord = (
  caseId: number,
  data: BatchRecordRequest = {}
): Promise<BatchRecordResponse> => {
  return request.post(`/batch-locator/cases/${caseId}/batch-record`, data)
}

/**
 * 获取批量记录任务状态
 */
export const getBatchRecordStatus = (caseId: number): Promise<BatchRecordStatus> => {
  return request.get(`/batch-locator/cases/${caseId}/batch-record-status`)
}

/**
 * 获取批量记录完整报告
 */
export const getBatchRecordReport = (caseId: number): Promise<BatchRecordReport> => {
  return request.get(`/batch-locator/cases/${caseId}/batch-record-report`)
}

/**
 * 取消批量记录任务
 */
export const cancelBatchRecord = (caseId: number): Promise<{ success: boolean; message: string }> => {
  return request.post(`/batch-locator/cases/${caseId}/batch-record-cancel`)
}

/**
 * 获取所有批量任务列表
 */
export const listBatchTasks = (): Promise<BatchTask[]> => {
  return request.get('/batch-locator/batch-tasks')
}

/**
 * 批量元素定位API对象
 */
export const batchLocatorApi = {
  startBatchRecord,
  getBatchRecordStatus,
  getBatchRecordReport,
  cancelBatchRecord,
  listBatchTasks
}

export default batchLocatorApi
