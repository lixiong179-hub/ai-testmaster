import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  startBatchRecord: vi.fn(),
  getBatchRecordStatus: vi.fn(),
  getBatchRecordReport: vi.fn(),
  cancelBatchRecord: vi.fn(),
  listBatchTasks: vi.fn(),
}))

vi.mock('@/api/batchLocator', () => ({
  batchLocatorApi: {
    startBatchRecord: mocks.startBatchRecord,
    getBatchRecordStatus: mocks.getBatchRecordStatus,
    getBatchRecordReport: mocks.getBatchRecordReport,
  },
  cancelBatchRecord: mocks.cancelBatchRecord,
  listBatchTasks: mocks.listBatchTasks,
}))

import { useBatchLocator } from '../useBatchLocator'

type Ctx = ReturnType<typeof useBatchLocator>

const host = createComposableHost(() => useBatchLocator(7))
let ctx: Ctx

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

/** 启动定位并推进一次轮询间隔 */
async function runLocate(pending: Promise<void>) {
  await vi.advanceTimersByTimeAsync(2000)
  await pending
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.startBatchRecord.mockResolvedValue({ task_id: 'task-1' })
  mocks.getBatchRecordStatus.mockResolvedValue({ status: 'running', progress: 30 })
  mocks.getBatchRecordReport.mockResolvedValue({
    case_id: 1,
    case_title: '用例1',
    status: 'completed',
    step_results: [
      { success: true, locator_value: '#a' },
      { success: false, locator_value: '#b' },
      { success: true, locator_value: '.c' },
    ],
  })
  mocks.cancelBatchRecord.mockResolvedValue({ code: 200 })
  mocks.listBatchTasks.mockResolvedValue([{ id: 'task-1' }])
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useBatchLocator — 弹窗与状态', () => {
  it('打开弹窗重置全部状态', async () => {
    await mountHost()
    ctx.progress.value = 60
    ctx.results.value = [{ case_id: 1, case_title: 'x', status: 'success' }]
    ctx.error.value = '旧错误'

    ctx.open([1, 2])

    expect(ctx.visible.value).toBe(true)
    expect(ctx.currentView.value).toBe('config')
    expect(ctx.selectedCaseIds.value).toEqual([1, 2])
    expect(ctx.progress.value).toBe(0)
    expect(ctx.results.value).toEqual([])
    expect(ctx.error.value).toBe('')
  })

  it('关闭弹窗隐藏并清理定时器', async () => {
    await mountHost()
    ctx.open([1])

    ctx.close()

    expect(ctx.visible.value).toBe(false)
  })

  it('统计成功、失败与总数', async () => {
    await mountHost()
    ctx.results.value = [
      { case_id: 1, case_title: 'a', status: 'success' },
      { case_id: 2, case_title: 'b', status: 'failed' },
      { case_id: 3, case_title: 'c', status: 'success' },
    ]

    expect(ctx.successCount.value).toBe(2)
    expect(ctx.failCount.value).toBe(1)
    expect(ctx.totalProcessed.value).toBe(3)
    expect(ctx.hasResults.value).toBe(true)
  })

  it('无结果时 hasResults 为 false', async () => {
    await mountHost()

    expect(ctx.hasResults.value).toBe(false)
  })
})

describe('useBatchLocator — 启动定位', () => {
  it('未选用例时给出提示', async () => {
    await mountHost()

    await ctx.startLocate()

    expect(ElMessage.warning).toHaveBeenCalledWith('请选择要定位的用例')
    expect(mocks.startBatchRecord).not.toHaveBeenCalled()
  })

  it('任务完成后写入成功结果并提示', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus.mockResolvedValue({ status: 'completed' })

    const pending = ctx.startLocate()
    await runLocate(pending)

    expect(mocks.startBatchRecord).toHaveBeenCalledWith({
      project_id: 7,
      case_ids: [1],
      skip_existing: true,
      execute_precondition: true,
      use_mcp: true,
    })
    expect(ctx.results.value[0]).toMatchObject({
      case_id: 1,
      case_title: '用例1',
      status: 'success',
      locator: '#a; .c',
    })
    expect(ctx.currentView.value).toBe('report')
    expect(ElMessage.success).toHaveBeenCalledWith('批量定位完成，成功 1 个')
    expect(ctx.loading.value).toBe(false)
  })

  it('任务失败时写入失败结果并提示数量', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus.mockResolvedValue({
      status: 'failed',
      case_id: 9,
      message: '元素未找到',
    })

    const pending = ctx.startLocate()
    await runLocate(pending)

    expect(ctx.results.value[0]).toMatchObject({
      case_id: 9,
      case_title: '用例 9',
      status: 'failed',
      error_message: '元素未找到',
    })
    expect(ElMessage.warning).toHaveBeenCalledWith('批量定位完成，成功 0 个，失败 1 个')
  })

  it('失败状态缺少 message 时使用默认文案', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus.mockResolvedValue({ status: 'failed', case_id: 9 })

    const pending = ctx.startLocate()
    await runLocate(pending)

    expect(ctx.results.value[0].error_message).toBe('定位失败')
  })

  it('查询状态异常时记录失败结果', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus.mockRejectedValue(new Error('接口异常'))

    const pending = ctx.startLocate()
    await runLocate(pending)

    expect(ctx.results.value[0]).toMatchObject({
      case_id: 0,
      case_title: '未知用例',
      status: 'failed',
      error_message: '接口异常',
    })
  })

  it('未返回任务 ID 时进入报告页并提示', async () => {
    mocks.startBatchRecord.mockResolvedValue({})
    await mountHost()
    ctx.open([1])

    await ctx.startLocate()

    expect(ctx.error.value).toBe('未获取到任务ID')
    expect(ctx.currentView.value).toBe('report')
    expect(ElMessage.error).toHaveBeenCalledWith('未获取到任务ID')
  })

  it('轮询 60 次仍未完成时判定超时', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus.mockResolvedValue({ status: 'running' })

    const pending = ctx.startLocate()
    for (let i = 0; i < 60; i += 1) {
      await vi.advanceTimersByTimeAsync(2000)
    }
    await pending

    expect(ctx.results.value[0].error_message).toBe('定位超时')
    expect(mocks.getBatchRecordStatus).toHaveBeenCalledTimes(60)
  })

  it('轮询过程同步进度与提示', async () => {
    await mountHost()
    vi.useFakeTimers()
    ctx.open([1])
    mocks.getBatchRecordStatus
      .mockResolvedValueOnce({ status: 'running', progress: 0 })
      .mockResolvedValueOnce({ status: 'running', message: '处理中' })
      .mockResolvedValue({ status: 'completed' })

    const pending = ctx.startLocate()
    await vi.advanceTimersByTimeAsync(2000)
    expect(ctx.progress.value).toBe(Math.round((1 / 60) * 100))

    await vi.advanceTimersByTimeAsync(2000)
    expect(ctx.progressMessage.value).toBe('处理中')

    await vi.advanceTimersByTimeAsync(2000)
    await pending
    expect(ctx.results.value).toHaveLength(1)
  })
})

describe('useBatchLocator — 结果应用与重试', () => {
  it('重试无失败用例时提示', async () => {
    await mountHost()

    await ctx.retryFailed()

    expect(ElMessage.info).toHaveBeenCalledWith('没有失败的用例')
    expect(mocks.startBatchRecord).not.toHaveBeenCalled()
  })

  it('重试仅针对失败用例', async () => {
    mocks.startBatchRecord.mockRejectedValue(new Error('启动失败'))
    await mountHost()
    ctx.results.value = [
      { case_id: 2, case_title: 'b', status: 'failed' },
      { case_id: 3, case_title: 'c', status: 'success' },
    ]

    await ctx.retryFailed()

    expect(mocks.startBatchRecord).toHaveBeenCalledWith(expect.objectContaining({ case_ids: [2] }))
    expect(ElMessage.error).toHaveBeenCalledWith('启动失败')
  })

  it('无可应用结果时提示', async () => {
    await mountHost()
    ctx.results.value = [{ case_id: 1, case_title: 'a', status: 'failed' }]

    await ctx.applyResults()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有可应用的结果')
  })

  it('应用成功结果后关闭弹窗', async () => {
    await mountHost()
    ctx.open([1])
    ctx.results.value = [
      { case_id: 1, case_title: 'a', status: 'success', locator: '#a' },
      { case_id: 2, case_title: 'b', status: 'success' },
    ]

    await ctx.applyResults()

    expect(ElMessage.success).toHaveBeenCalledWith('已确认 1 个定位器')
    expect(ctx.visible.value).toBe(false)
  })
})

describe('useBatchLocator — 取消与任务列表', () => {
  it('无进行中任务时提示', async () => {
    await mountHost()

    await ctx.cancelTask()

    expect(ElMessage.warning).toHaveBeenCalledWith('没有正在进行的任务')
  })

  it('取消任务成功切换到报告页', async () => {
    await mountHost()
    vi.useFakeTimers()
    mocks.getBatchRecordStatus.mockRejectedValue(new Error('状态查询失败'))
    ctx.open([1])
    const pending = ctx.startLocate()
    await vi.advanceTimersByTimeAsync(2000)
    await pending

    await ctx.cancelTask()

    expect(mocks.cancelBatchRecord).toHaveBeenCalledWith('task-1')
    expect(ElMessage.success).toHaveBeenCalledWith('任务已取消')
    expect(ctx.currentView.value).toBe('report')
  })

  it('取消任务失败提示错误', async () => {
    await mountHost()
    vi.useFakeTimers()
    mocks.getBatchRecordStatus.mockRejectedValue(new Error('状态查询失败'))
    mocks.cancelBatchRecord.mockRejectedValue(new Error('取消失败'))
    ctx.open([1])
    const pending = ctx.startLocate()
    await vi.advanceTimersByTimeAsync(2000)
    await pending

    await ctx.cancelTask()

    expect(ElMessage.error).toHaveBeenCalledWith('取消失败')
  })

  it('加载任务列表成功', async () => {
    await mountHost()

    await ctx.loadBatchTasks()

    expect(ctx.batchTasks.value).toHaveLength(1)
    expect(ctx.tasksLoading.value).toBe(false)
  })

  it('任务列表非数组时置空', async () => {
    mocks.listBatchTasks.mockResolvedValue(null)
    await mountHost()

    await ctx.loadBatchTasks()

    expect(ctx.batchTasks.value).toEqual([])
  })

  it('任务列表加载失败提示错误', async () => {
    mocks.listBatchTasks.mockRejectedValue(new Error('列表失败'))
    await mountHost()

    await ctx.loadBatchTasks()

    expect(ElMessage.error).toHaveBeenCalledWith('列表失败')
    expect(ctx.tasksLoading.value).toBe(false)
  })
})
