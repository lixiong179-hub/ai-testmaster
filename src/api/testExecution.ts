/**
 * 测试执行API
 * 用于测试执行过程可视化和控制
 */
import request from '@/utils/request'

/**
 * 开始测试任务执行
 */
export type ExecutionMode = 'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart'

export const startTestExecution = (
  taskId: number,
  config?: {
    headless?: boolean
    recordVideo?: boolean
    targetEnv?: string
    skipInit?: boolean
    executionMode?: ExecutionMode
    mobileDeviceId?: string
    use_mcp?: boolean
  }
) => {
  return request.post(`/api/v1/execution/${taskId}/start`, config)
}

export const getConnectedDevices = () => {
  return request.get('/api/v1/execution/devices')
}

/**
 * 暂停测试执行
 */
export const pauseTestExecution = (taskId: number) => {
  return request.post(`/api/v1/execution/${taskId}/pause`)
}

/**
 * 恢复测试执行
 */
export const resumeTestExecution = (taskId: number) => {
  return request.post(`/api/v1/execution/${taskId}/resume`)
}

/**
 * 停止测试执行
 */
export const stopTestExecution = (taskId: number) => {
  return request.post(`/api/v1/execution/${taskId}/stop`)
}

/**
 * 获取执行状态
 * 后端无独立status端点，通过任务详情获取状态
 */
export const getExecutionStatus = (taskId: number) => {
  return request.get(`/api/v1/test_task/${taskId}`)
}

/**
 * 获取执行日志
 * 后端无独立logs端点，通过任务执行摘要获取
 */
export const getExecutionLogs = (
  taskId: number,
  params?: {
    stepNumber?: number
    limit?: number
  }
) => {
  return request.get(`/api/v1/test_task/${taskId}/summary`, { params })
}

/**
 * 获取步骤截图
 * 后端：GET /api/v1/execution/{task_id}/screenshot/{case_id}/{step_number}/{type}
 */
export const getStepScreenshot = (taskId: number, caseId: number, stepNumber: number, type: 'before' | 'after') => {
  return request.get(`/api/v1/execution/${taskId}/screenshot/${caseId}/${stepNumber}/${type}`, {
    responseType: 'blob',
  })
}

/**
 * 获取执行视频
 */
export const getExecutionVideo = (taskId: number, caseId: number) => {
  return request.get(`/api/v1/execution/${taskId}/case/${caseId}/video`, {
    responseType: 'blob',
  })
}

/**
 * 获取视频信息
 */
export const getVideoInfo = (taskId: number, caseId: number) => {
  return request.get(`/api/v1/execution/${taskId}/case/${caseId}/video/info`)
}

/**
 * 获取回放会话信息
 */
export const getReplaySession = (executionId: string) => {
  return request.get(`/api/v1/execution/replay/${executionId}`)
}

/**
 * 开始回放
 */
export const startReplay = (executionId: string) => {
  return request.post(`/api/v1/execution/replay/${executionId}/start`)
}

/**
 * 暂停回放
 */
export const pauseReplay = (executionId: string) => {
  return request.post(`/api/v1/execution/replay/${executionId}/pause`)
}

/**
 * 恢复回放
 */
export const resumeReplay = (executionId: string) => {
  return request.post(`/api/v1/execution/replay/${executionId}/resume`)
}

/**
 * 停止回放
 */
export const stopReplay = (executionId: string) => {
  return request.post(`/api/v1/execution/replay/${executionId}/stop`)
}

/**
 * 跳转到指定时间
 */
export const seekTo = (executionId: string, timestamp: number) => {
  return request.post(`/api/v1/execution/replay/${executionId}/seek`, { timestamp })
}

/**
 * 设置回放速度
 */
export const setReplaySpeed = (executionId: string, speed: number) => {
  return request.post(`/api/v1/execution/replay/${executionId}/speed`, { speed })
}

/**
 * 获取可见模式配置
 */
export const getVisibilityConfig = (level: 'global' | 'task' | 'case', id?: number) => {
  return request.get('/api/v1/visibility/config', {
    params: { level, id },
  })
}

/**
 * 更新可见模式配置
 */
export const updateVisibilityConfig = (
  level: 'global' | 'task' | 'case',
  config: {
    headless?: boolean
    recordVideo?: boolean
    videoResolution?: [number, number]
    videoFps?: number
  },
  id?: number
) => {
  return request.put('/api/v1/visibility/config', {
    level,
    id,
    ...config,
  })
}

export interface FailureAnalysisResult {
  result_id: number
  case_id: number
  case_title: string
  suggested_type: 'case_issue' | 'product_bug' | 'needs_review'
  confidence: number
  reason: string
  case_issue_indicators: string[]
  bug_issue_indicators: string[]
  error_msg: string
  ai_analysis: string
  screenshot_url: string | null
  analysis_time: string
}

export const analyzeFailure = (resultId: number) => {
  return request.post<FailureAnalysisResult>(
    `/api/v1/execution/results/${resultId}/analyze-failure`
  )
}

export const createQuickVerify = (caseId: number, stepIndices: number[] = []) => {
  return request.post('/api/v1/execution/quick-verify', {
    case_id: caseId,
    step_indices: stepIndices,
  })
}
