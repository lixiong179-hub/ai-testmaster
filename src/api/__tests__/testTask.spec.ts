import { describe, it, expect, beforeEach, vi } from 'vitest'

// 使用 vi.hoisted 确保 mock 对象在 vi.mock 工厂执行前已初始化
const { mockRequest } = vi.hoisted(() => ({
  mockRequest: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('@/utils/request', () => ({
  default: mockRequest,
}))

import testTaskApi, { TaskStatus, ExecutionStatus } from '@/api/testTask'

describe('TaskStatus / ExecutionStatus 枚举', () => {
  it('任务状态码与后端 test_tasks.status 对齐（含 PAUSED=5）', () => {
    expect(TaskStatus.WAITING).toBe(0)
    expect(TaskStatus.RUNNING).toBe(1)
    expect(TaskStatus.COMPLETED).toBe(2)
    expect(TaskStatus.FAILED).toBe(3)
    expect(TaskStatus.STOPPED).toBe(4)
    expect(TaskStatus.PAUSED).toBe(5)
  })

  it('用例执行状态码与后端 TestResult.exec_status 对齐', () => {
    expect(ExecutionStatus.PENDING).toBe(0)
    expect(ExecutionStatus.PASSED).toBe(1)
    expect(ExecutionStatus.FAILED).toBe(2)
    expect(ExecutionStatus.BLOCKED).toBe(3)
  })
})

describe('testTaskApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('createTask: POST /api/v1/test-task/ 且 description 缺省补空串', async () => {
    mockRequest.post.mockResolvedValueOnce({ code: 200, data: { task_id: 1 } })

    await testTaskApi.createTask({ task_name: '回归', project_id: 10, case_ids: [1, 2] })

    expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/test-task/', {
      project_id: 10,
      task_name: '回归',
      description: '',
      case_ids: [1, 2],
    })
  })

  it('getTaskList: 查询参数原样透传（使用 task_status 而非 status）', async () => {
    mockRequest.get.mockResolvedValueOnce({ code: 200, data: { items: [], total: 0 } })

    await testTaskApi.getTaskList({ project_id: 10, task_status: 3, page: 2, page_size: 20 })

    expect(mockRequest.get).toHaveBeenCalledWith('/api/v1/test-task/', {
      params: { project_id: 10, task_status: 3, page: 2, page_size: 20 },
    })
  })

  it('getTaskDetail: 有 projectId 时带 project_id，无则传空参数', async () => {
    mockRequest.get.mockResolvedValue({ code: 200, data: {} })

    await testTaskApi.getTaskDetail(5, 10)
    await testTaskApi.getTaskDetail(5)

    expect(mockRequest.get).toHaveBeenNthCalledWith(1, '/api/v1/test-task/5', {
      params: { project_id: 10 },
    })
    expect(mockRequest.get).toHaveBeenNthCalledWith(2, '/api/v1/test-task/5', { params: {} })
  })

  it('startTask: 走 test-task 启动端点并透传执行模式/设备', async () => {
    mockRequest.post.mockResolvedValueOnce({ code: 200, data: {} })

    await testTaskApi.startTask(5, 10, 'mobile_smart', 'device-1')

    expect(mockRequest.post).toHaveBeenCalledWith(
      '/api/v1/test-task/5/start',
      { execution_mode: 'mobile_smart', mobile_device_id: 'device-1' },
      { params: { project_id: 10 } }
    )
  })

  it('stopTask / pauseTask / resumeTask: 统一走 execution 执行控制端点', async () => {
    mockRequest.post.mockResolvedValue({ code: 200, data: {} })

    await testTaskApi.stopTask(5, 10)
    await testTaskApi.pauseTask(5, 10)
    await testTaskApi.resumeTask(5, 10)

    expect(mockRequest.post).toHaveBeenNthCalledWith(1, '/api/v1/execution/5/stop', null, {
      params: { project_id: 10 },
    })
    expect(mockRequest.post).toHaveBeenNthCalledWith(2, '/api/v1/execution/5/pause', null, {
      params: { project_id: 10 },
    })
    expect(mockRequest.post).toHaveBeenNthCalledWith(3, '/api/v1/execution/5/resume', null, {
      params: { project_id: 10 },
    })
  })

  it('getTaskResults / getTaskSummary / runTask / deleteTask: 路径与动作一致', async () => {
    mockRequest.get.mockResolvedValue({ code: 200, data: {} })
    mockRequest.post.mockResolvedValue({ code: 200, data: {} })
    mockRequest.delete.mockResolvedValue({ code: 200, data: {} })

    await testTaskApi.getTaskResults(5, 10)
    await testTaskApi.getTaskSummary(5)
    await testTaskApi.runTask(5, 10)
    await testTaskApi.deleteTask(5)

    expect(mockRequest.get).toHaveBeenNthCalledWith(1, '/api/v1/test-task/5', {
      params: { project_id: 10 },
    })
    expect(mockRequest.get).toHaveBeenNthCalledWith(2, '/api/v1/test-task/5/summary', {
      params: {},
    })
    expect(mockRequest.post).toHaveBeenCalledWith('/api/v1/test-task/5/run', null, {
      params: { project_id: 10 },
    })
    expect(mockRequest.delete).toHaveBeenCalledWith('/api/v1/test-task/5', { params: {} })
  })

  it('getProjectCases: 默认 page/page_size 可被调用方覆盖', async () => {
    mockRequest.get.mockResolvedValue({ code: 200, data: { items: [] } })

    await testTaskApi.getProjectCases(10)
    await testTaskApi.getProjectCases(10, { page: 3, page_size: 50 })

    expect(mockRequest.get).toHaveBeenNthCalledWith(1, '/api/v1/test-case/', {
      params: { project_id: 10, page: 1, page_size: 100 },
    })
    expect(mockRequest.get).toHaveBeenNthCalledWith(2, '/api/v1/test-case/', {
      params: { project_id: 10, page: 3, page_size: 50 },
    })
  })
})
