import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const { mockTaskApi } = vi.hoisted(() => ({
  mockTaskApi: {
    getTaskList: vi.fn(),
    getTaskDetail: vi.fn(),
    getTaskResults: vi.fn(),
    getTaskSummary: vi.fn(),
    createTask: vi.fn(),
    startTask: vi.fn(),
    stopTask: vi.fn(),
    pauseTask: vi.fn(),
    resumeTask: vi.fn(),
    runTask: vi.fn(),
    deleteTask: vi.fn(),
  },
}))

// 保留真实枚举导出（store 依赖 TaskStatus/ExecutionStatus 的具体数值）
vi.mock('@/api/testTask', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/testTask')>()
  return { ...actual, default: mockTaskApi }
})

import { useTaskStore, TaskStatus, ExecutionStatus } from '../task'
import type { TestTask, ExecutionProgress, ExecutionLog } from '../taskTypes'

function makeTask(overrides: Partial<TestTask> = {}): TestTask {
  return {
    id: 1,
    task_name: '回归任务',
    project_id: 10,
    case_ids: [1, 2],
    executor_id: 100,
    status: TaskStatus.WAITING,
    success_count: 0,
    fail_count: 0,
    total_count: 2,
    progress: 0,
    create_time: '2026-01-01T00:00:00',
    ...overrides,
  }
}

function makeProgress(overrides: Partial<ExecutionProgress> = {}): ExecutionProgress {
  return {
    task_id: 1,
    progress: 50,
    success_count: 1,
    fail_count: 1,
    current_case: 1,
    total_cases: 2,
    timestamp: '2026-01-01T00:00:00',
    ...overrides,
  }
}

describe('useTaskStore — getters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('taskStatusText: 6 个状态码全覆盖，未知回退「未知状态」', () => {
    const store = useTaskStore()

    expect(store.taskStatusText(TaskStatus.WAITING)).toBe('等待执行')
    expect(store.taskStatusText(TaskStatus.RUNNING)).toBe('执行中')
    expect(store.taskStatusText(TaskStatus.COMPLETED)).toBe('执行完成')
    expect(store.taskStatusText(TaskStatus.FAILED)).toBe('执行失败')
    expect(store.taskStatusText(TaskStatus.STOPPED)).toBe('已停止')
    expect(store.taskStatusText(TaskStatus.PAUSED)).toBe('已暂停')
    expect(store.taskStatusText(99)).toBe('未知状态')
  })

  it('taskStatusColor: 失败为 danger、暂停与停止为 warning，未知回退 info', () => {
    const store = useTaskStore()

    expect(store.taskStatusColor(TaskStatus.COMPLETED)).toBe('success')
    expect(store.taskStatusColor(TaskStatus.FAILED)).toBe('danger')
    expect(store.taskStatusColor(TaskStatus.PAUSED)).toBe('warning')
    expect(store.taskStatusColor(TaskStatus.STOPPED)).toBe('warning')
    expect(store.taskStatusColor(99)).toBe('info')
  })

  it('execStatusText / execStatusColor: 用例执行态映射完整', () => {
    const store = useTaskStore()

    expect(store.execStatusText(ExecutionStatus.PENDING)).toBe('未执行')
    expect(store.execStatusText(ExecutionStatus.PASSED)).toBe('执行成功')
    expect(store.execStatusText(ExecutionStatus.BLOCKED)).toBe('阻塞')
    expect(store.execStatusColor(ExecutionStatus.PASSED)).toBe('success')
    expect(store.execStatusColor(ExecutionStatus.FAILED)).toBe('danger')
    expect(store.execStatusColor(99)).toBe('info')
  })

  it('taskPassRate: 无详情或总数为 0 时为 0，否则四舍五入', () => {
    const store = useTaskStore()
    expect(store.taskPassRate).toBe(0)

    store.taskDetail = makeTask({ total_count: 0, success_count: 0 })
    expect(store.taskPassRate).toBe(0)

    store.taskDetail = makeTask({ total_count: 3, success_count: 2 })
    expect(store.taskPassRate).toBe(67)
  })

  it('runningTasks: 仅返回 RUNNING 任务', () => {
    const store = useTaskStore()
    store.taskList = [
      makeTask({ id: 1, status: TaskStatus.RUNNING }),
      makeTask({ id: 2, status: TaskStatus.COMPLETED }),
      makeTask({ id: 3, status: TaskStatus.PAUSED }),
    ]

    expect(store.runningTasks.map((t) => t.id)).toEqual([1])
  })
})

describe('useTaskStore — actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchTaskList: 成功写入列表与总数，loading 复位', async () => {
    const store = useTaskStore()
    mockTaskApi.getTaskList.mockResolvedValueOnce({
      code: 200,
      data: { items: [makeTask({ id: 5 })], total: 7 },
    })

    const result = await store.fetchTaskList({ project_id: 10, task_status: 3 })

    expect(mockTaskApi.getTaskList).toHaveBeenCalledWith({ project_id: 10, task_status: 3 })
    expect(result).toEqual({ items: [makeTask({ id: 5 })], total: 7 })
    expect(store.taskList).toHaveLength(1)
    expect(store.loading).toBe(false)
    expect(store.error).toBeNull()
  })

  it('fetchTaskList: 失败记录 error、抛出异常且 loading 复位', async () => {
    const store = useTaskStore()
    mockTaskApi.getTaskList.mockRejectedValueOnce(new Error('后端 500'))

    await expect(store.fetchTaskList()).rejects.toThrow('后端 500')

    expect(store.error).toBe('后端 500')
    expect(store.loading).toBe(false)
  })

  it('fetchTaskDetail: 兼容 data.task 包装结构', async () => {
    const store = useTaskStore()
    mockTaskApi.getTaskDetail.mockResolvedValueOnce({
      code: 200,
      data: { task: makeTask({ id: 9, status: TaskStatus.FAILED }) },
    })

    const detail = await store.fetchTaskDetail(9, 10)

    expect(mockTaskApi.getTaskDetail).toHaveBeenCalledWith(9, 10)
    expect(detail?.id).toBe(9)
    expect(store.taskDetail?.status).toBe(TaskStatus.FAILED)
  })

  it('fetchTaskResults: 数组 / results / items 三种载荷均可归一化', async () => {
    const store = useTaskStore()

    mockTaskApi.getTaskResults.mockResolvedValueOnce({
      code: 200,
      data: [{ id: 1, task_id: 9 }],
    })
    await store.fetchTaskResults(9)
    expect(store.taskResults).toHaveLength(1)

    mockTaskApi.getTaskResults.mockResolvedValueOnce({
      code: 200,
      data: { results: [{ id: 2, task_id: 9 }] },
    })
    await store.fetchTaskResults(9)
    expect(store.taskResults).toHaveLength(1)

    mockTaskApi.getTaskResults.mockResolvedValueOnce({
      code: 200,
      data: {
        items: [
          { id: 3, task_id: 9 },
          { id: 4, task_id: 9 },
        ],
      },
    })
    await store.fetchTaskResults(9)
    expect(store.taskResults).toHaveLength(2)
  })

  it('deleteTask: 成功后从本地列表移除对应任务', async () => {
    const store = useTaskStore()
    store.taskList = [makeTask({ id: 1 }), makeTask({ id: 2 })]
    mockTaskApi.deleteTask.mockResolvedValueOnce({ code: 200 })

    await store.deleteTask(1, 10)

    expect(mockTaskApi.deleteTask).toHaveBeenCalledWith(1, 10)
    expect(store.taskList.map((t) => t.id)).toEqual([2])
  })

  it('updateExecutionProgress: 同步列表与当前详情的进度字段', () => {
    const store = useTaskStore()
    store.taskList = [makeTask({ id: 1, progress: 0 })]
    store.taskDetail = makeTask({ id: 1, progress: 0 })

    store.updateExecutionProgress(makeProgress({ task_id: 1, progress: 66, success_count: 2 }))

    expect(store.executionProgress?.progress).toBe(66)
    expect(store.taskList[0].progress).toBe(66)
    expect(store.taskDetail.progress).toBe(66)
    expect(store.taskDetail.success_count).toBe(2)
  })

  it('updateTaskStatus: 同时刷新列表项与当前详情', () => {
    const store = useTaskStore()
    store.taskList = [makeTask({ id: 1 }), makeTask({ id: 2 })]
    store.taskDetail = makeTask({ id: 1 })

    store.updateTaskStatus(1, TaskStatus.PAUSED)
    store.updateTaskStatus(2, TaskStatus.STOPPED)

    expect(store.taskList[0].status).toBe(TaskStatus.PAUSED)
    expect(store.taskList[1].status).toBe(TaskStatus.STOPPED)
    expect(store.taskDetail.status).toBe(TaskStatus.PAUSED)
  })

  it('addExecutionLog: 超过 1000 条时裁剪为最近 500 条，避免内存无界增长', () => {
    const store = useTaskStore()
    const log = (i: number): ExecutionLog => ({
      task_id: 1,
      status: 0,
      log: `日志 ${i}`,
      timestamp: '2026-01-01T00:00:00',
    })

    for (let i = 0; i < 1001; i += 1) {
      store.addExecutionLog(log(i))
    }

    expect(store.executionLogs).toHaveLength(500)
    expect(store.executionLogs[499].log).toBe('日志 1000')
  })

  it('resetState: 清空全部执行态缓存', () => {
    const store = useTaskStore()
    store.taskList = [makeTask()]
    store.taskDetail = makeTask()
    store.taskResults = [{ id: 1 } as never]
    store.executionLogs = [{ task_id: 1 } as never]
    store.executionProgress = makeProgress()
    store.taskSummary = { task_id: 1 } as never

    store.resetState()

    expect(store.taskList).toEqual([])
    expect(store.taskDetail).toBeNull()
    expect(store.taskResults).toEqual([])
    expect(store.executionLogs).toEqual([])
    expect(store.executionProgress).toBeNull()
    expect(store.taskSummary).toBeNull()
  })
})
