/**
 * 批量元素定位API
 *
 * 后端路由挂载在 /api/v1/batch-locator 前缀下
 */
import request from '@/utils/request'

export interface BatchRecordRequest {
  project_id: number
  case_ids: number[]
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
  description?: string
  display_action?: string
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
 * 后端：POST /api/v1/batch-locator/batch-record
 */
export const startBatchRecord = (
  data: BatchRecordRequest
): Promise<BatchRecordResponse> => {
  return request.post('/api/v1/batch-locator/batch-record', data)
}

/**
 * 获取批量记录任务状态
 * 后端：GET /api/v1/batch-locator/batch-record-status/{task_id}
 */
export const getBatchRecordStatus = (taskId: string): Promise<BatchRecordStatus> => {
  return request.get(`/api/v1/batch-locator/batch-record-status/${taskId}`)
}

/**
 * 获取批量记录完整报告
 * 后端：GET /api/v1/batch-locator/batch-record-report/{task_id}
 */
export const getBatchRecordReport = (taskId: string): Promise<BatchRecordReport> => {
  return request.get(`/api/v1/batch-locator/batch-record-report/${taskId}`)
}

/**
 * 取消批量记录任务
 * 后端：POST /api/v1/batch-locator/batch-record-cancel/{task_id}
 */
export const cancelBatchRecord = (
  taskId: string
): Promise<{ success: boolean; message: string }> => {
  return request.post(`/api/v1/batch-locator/batch-record-cancel/${taskId}`)
}

/**
 * 获取所有批量任务列表
 * 后端：GET /api/v1/batch-locator/batch-tasks
 */
export const listBatchTasks = (): Promise<BatchTask[]> => {
  return request.get('/api/v1/batch-locator/batch-tasks')
}

/**
 * 批量元素定位API对象
 */
export const batchLocatorApi = {
  startBatchRecord,
  getBatchRecordStatus,
  getBatchRecordReport,
  cancelBatchRecord,
  listBatchTasks,
}

export default batchLocatorApi
