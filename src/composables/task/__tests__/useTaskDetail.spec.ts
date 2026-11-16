import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createComposableHost, silenceConsole, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  route: {
    params: { taskId: '42' } as Record<string, string>,
    query: { project_id: '7' } as Record<string, string>,
  },
  push: vi.fn(),
  getConnectedDevices: vi.fn(),
  connect: vi.fn(),
  onMessage: vi.fn(),
  offMessage: vi.fn(),
  disconnect: vi.fn(),
  store: {} as Record<string, unknown>,
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/store/task', () => ({
  useTaskStore: () => mocks.store,
}))

vi.mock('@/utils/websocket', () => ({
  wsClient: {
    connect: mocks.connect,
    onMessage: mocks.onMessage,
    offMessage: mocks.offMessage,
    disconnect: mocks.disconnect,
  },
}))

vi.mock('@/api/testExecution', () => ({
  getConnectedDevices: mocks.getConnectedDevices,
}))

import { provideTaskDetail } from '../useTaskDetail'

type Ctx = ReturnType<typeof provideTaskDetail>

let ctx: Ctx

const host = createComposableHost(() => provideTaskDetail())

function createStore(
  detail: Record<string, unknown> | null = {
    id: 42,
    status: 2,
    total_count: 10,
    success_count: 8,
    fail_count: 2,
  }
) {
  return {
    loading: false,
    taskDetail: detail,
    taskResults: [
      {
        case_no: 'TC-001',
        case_id: 1,
        exec_status: 1,
        exec_time: 1.2,
        error_msg: '',
        exec_log: 'log',
      },
    ],
    executionLogs: [{ timestamp: '2026-11-13T10:00:00Z', status: 1, log: 'ok', case_no: 'TC-001' }],
    fetchTaskDetail: vi.fn().mockResolvedValue(undefined),
    fetchTaskResults: vi.fn().mockResolvedValue(undefined),
    startTask: vi.fn().mockResolvedValue(undefined),
    stopTask: vi.fn().mockResolvedValue(undefined),
    pauseTask: vi.fn().mockResolvedValue(undefined),
    resumeTask: vi.fn().mockResolvedValue(undefined),
    clearExecutionLogs: vi.fn(),
    addExecutionLog: vi.fn(),
    updateExecutionProgress: vi.fn(),
    updateTaskStatus: vi.fn(),
    taskStatusText: (s: number) => `状态${s}`,
    taskStatusColor: () => 'success',
    execStatusText: (s: number) => `执行${s}`,
    execStatusColor: () => 'primary',
    logStatusText: (s: number) => `日志${s}`,
    logStatusColor: () => 'info',
  }
}

async function mountHost(storePatch: Partial<Record<string, unknown>> = {}) {
  mocks.store = { ...createStore(), ...storePatch }
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.params = { taskId: '42' }
  mocks.route.query = { project_id: '7' }
  silenceElMessage('success', 'error', 'warning')
  silenceConsole('error')
  mocks.getConnectedDevices.mockResolvedValue({
    data: { code: 200, data: [{ udid: 'dev-1', state: 'device' }] },
  })
})

describe('useTaskDetail — 路由与派生', () => {
  it('解析任务与项目 ID', async () => {
    await mountHost()

    expect(ctx.taskId.value).toBe(42)
    expect(ctx.projectId.value).toBe(7)
  })

  it('通过率按结果计算', async () => {
    await mountHost()

    expect(ctx.taskPassRate.value).toBe(80)
  })

  it('无任务详情时通过率为 0', async () => {
    await mountHost({ taskDetail: null })

    expect(ctx.taskPassRate.value).toBe(0)
  })

  it('日志样式与进度颜色映射', () => {
    expect(ctx.getLogItemClass(3)).toBe('log-warning')
    expect(ctx.getLogItemClass(2)).toBe('log-error')
    expect(ctx.getLogItemClass(1)).toBe('log-success')
    expect(ctx.getLogItemClass(0)).toBe('')

    expect(ctx.getProgressColor(10)).toBe('#409EFF')
    expect(ctx.getProgressColor(50)).toBe('#E6A23C')
    expect(ctx.getProgressColor(90)).toBe('#67C23A')
  })

  it('进度状态按任务状态与失败数派生', async () => {
    await mountHost({ taskDetail: { status: 3, fail_count: 1 } })
    expect(ctx.getProgressStatus()).toBe('exception')

    await mountHost({ taskDetail: { status: 2, fail_count: 0 } })
    expect(ctx.getProgressStatus()).toBe('success')

    await mountHost({ taskDetail: { status: 2, fail_count: 1 } })
    expect(ctx.getProgressStatus()).toBeUndefined()

    await mountHost({ taskDetail: null })
    expect(ctx.getProgressStatus()).toBeUndefined()
  })

  it('时间格式化空值兜底', () => {
    expect(ctx.formatTime('')).toBe('-')
    expect(ctx.formatTime('2026-11-13T10:00:00Z')).toContain('2026')
  })
})

describe('useTaskDetail — 数据加载', () => {
  it('刷新详情与结果', async () => {
    await mountHost()

    await ctx.refreshAll()

    expect(mocks.store.fetchTaskDetail).toHaveBeenCalledWith(42, 7)
    expect(mocks.store.fetchTaskResults).toHaveBeenCalledWith(42, 7)
  })

  it('详情失败提示错误信息或兜底文案', async () => {
    await mountHost()
    ;(mocks.store.fetchTaskDetail as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('详情异常')
    )

    await ctx.fetchTaskDetail()
    expect(ElMessage.error).toHaveBeenCalledWith('详情异常')
    ;(mocks.store.fetchTaskDetail as ReturnType<typeof vi.fn>).mockRejectedValue({})
    await ctx.fetchTaskDetail()
    expect(ElMessage.error).toHaveBeenCalledWith('获取任务详情失败')
  })

  it('结果加载失败仅记录日志', async () => {
    await mountHost()
    ;(mocks.store.fetchTaskResults as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('x'))

    await ctx.fetchTaskResults()

    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(console.error).toHaveBeenCalled()
  })

  it('设备列表加载成功与失败均复位 loading', async () => {
    await mountHost()

    await ctx.loadConnectedDevices()
    expect(ctx.connectedDevices.value).toHaveLength(1)
    expect(ctx.loadingDevices.value).toBe(false)

    mocks.getConnectedDevices.mockRejectedValue(new Error('boom'))
    await ctx.loadConnectedDevices()
    expect(ctx.loadingDevices.value).toBe(false)
  })
})

describe('useTaskDetail — 任务控制', () => {
  it('移动端模式未选设备时阻止启动', async () => {
    await mountHost()
    ctx.executionMode.value = 'mobile_smart'

    await ctx.startTask()

    expect(ElMessage.warning).toHaveBeenCalledWith('移动端模式请先选择目标设备')
    expect(mocks.store.startTask).not.toHaveBeenCalled()
  })

  it('启动任务携带模式与设备并开启轮询', async () => {
    await mountHost()
    ctx.executionMode.value = 'mobile_realtime'
    ctx.mobileDeviceId.value = 'dev-1'

    await ctx.startTask()

    expect(mocks.store.startTask).toHaveBeenCalledWith(42, 7, 'mobile_realtime', 'dev-1')
    expect(ElMessage.success).toHaveBeenCalledWith('任务已启动')
    expect(ctx.actionLoading.value).toBe(false)
    ctx.cleanup()
  })

  it('桌面模式不传设备', async () => {
    await mountHost()

    await ctx.startTask()

    expect(mocks.store.startTask).toHaveBeenCalledWith(42, 7, 'smart', undefined)
    ctx.cleanup()
  })

  it('启动失败提示错误', async () => {
    await mountHost()
    ;(mocks.store.startTask as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('启动异常'))

    await ctx.startTask()

    expect(ElMessage.error).toHaveBeenCalledWith('启动异常')
    expect(ctx.actionLoading.value).toBe(false)
  })

  it('停止任务需确认，取消时不调用接口', async () => {
    await mountHost()
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)

    await ctx.stopTask()
    expect(mocks.store.stopTask).toHaveBeenCalledWith(42, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已停止')

    confirm.mockRejectedValue('cancel')
    await ctx.stopTask()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('重试任务清空日志并使用当前模式重启', async () => {
    await mountHost()
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)

    await ctx.retryTask()

    expect(mocks.store.clearExecutionLogs).toHaveBeenCalled()
    expect(mocks.store.startTask).toHaveBeenCalledWith(42, 7, 'smart', undefined)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已重新启动')
    ctx.cleanup()
  })

  it('暂停与恢复分别调用接口并提示', async () => {
    await mountHost()

    await ctx.pauseTask()
    expect(mocks.store.pauseTask).toHaveBeenCalledWith(42, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已暂停')

    await ctx.resumeTask()
    expect(mocks.store.resumeTask).toHaveBeenCalledWith(42, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已恢复')
    ctx.cleanup()
  })
})

describe('useTaskDetail — 报告入口与按钮状态', () => {
  it.each([
    [2, true, 'primary', '查看测试报告'],
    [3, true, 'danger', '查看失败报告'],
    [4, true, 'primary', '查看测试报告'],
    [1, false, 'primary', '查看测试报告'],
  ])('任务状态 %s 报告入口可见性 %s', async (status, visible, type, text) => {
    await mountHost({ taskDetail: { status, total_count: 1, success_count: 1, fail_count: 0 } })

    expect(ctx.reportEntryVisible.value).toBe(visible)
    expect(ctx.reportButtonType.value).toBe(type)
    expect(ctx.reportButtonText.value).toBe(text)
  })

  it('跳转报告在失败态附带 status', async () => {
    await mountHost({ taskDetail: { status: 3, total_count: 1, success_count: 0, fail_count: 1 } })

    ctx.goToReport()
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'ExecutionReportDetail',
      query: { task_id: '42', status: 'failed' },
    })
  })

  it('非失败态跳转不带 status', async () => {
    await mountHost({ taskDetail: { status: 2, total_count: 1, success_count: 1, fail_count: 0 } })

    ctx.goToReport()
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'ExecutionReportDetail',
      query: { task_id: '42' },
    })
  })

  it('可重试/暂停/恢复按状态判断', async () => {
    await mountHost({ taskDetail: { status: 3 } })
    expect(ctx.canRetry.value).toBe(true)
    expect(ctx.canPause.value).toBe(false)

    await mountHost({ taskDetail: { status: 1 } })
    expect(ctx.canPause.value).toBe(true)
    expect(ctx.canRetry.value).toBe(false)

    await mountHost({ taskDetail: { status: 5 } })
    expect(ctx.canResume.value).toBe(true)
  })
})

describe('useTaskDetail — 导出与查看', () => {
  it('无结果时导出给出警告', async () => {
    await mountHost({ taskResults: [] })

    ctx.exportResults()

    expect(ElMessage.warning).toHaveBeenCalledWith('暂无结果可导出')
  })

  it('有结果时生成 CSV 下载', async () => {
    await mountHost()
    const createObjectURL = vi.mocked(URL.createObjectURL)
    const revokeObjectURL = vi.mocked(URL.revokeObjectURL)
    createObjectURL.mockReturnValue('blob:csv')

    ctx.exportResults()

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:csv')
  })

  it('无日志时导出给出警告', async () => {
    await mountHost({ executionLogs: [] })

    ctx.exportLogs()

    expect(ElMessage.warning).toHaveBeenCalledWith('暂无日志可导出')
  })

  it('查看用例日志与错误写入弹窗内容', async () => {
    await mountHost()

    ctx.viewCaseLog({ exec_log: '' } as never)
    expect(ctx.currentCaseLog.value).toBe('暂无日志')
    expect(ctx.logDialogVisible.value).toBe(true)

    ctx.viewError({ error_msg: '' } as never)
    expect(ctx.currentError.value).toBe('暂无错误信息')
    expect(ctx.errorDialogVisible.value).toBe(true)
  })

  it('查看截图按有无地址分流', async () => {
    await mountHost()

    ctx.viewScreenshot({ screenshot_url: '' } as never)
    expect(ElMessage.warning).toHaveBeenCalledWith('暂无截图')

    ctx.viewScreenshot({ screenshot_url: 'http://img' } as never)
    expect(ctx.currentScreenshot.value).toBe('http://img')
    expect(ctx.screenshotDialogVisible.value).toBe(true)
  })

  it('复制日志成功与失败分别提示', async () => {
    await mountHost()
    ctx.currentCaseLog.value = 'log'
    const writeText = vi.mocked(navigator.clipboard.writeText)
    writeText.mockResolvedValue(undefined)

    await ctx.copyLog()
    expect(writeText).toHaveBeenCalledWith('log')
    expect(ElMessage.success).toHaveBeenCalledWith('日志已复制到剪贴板')

    writeText.mockRejectedValue(new Error('denied'))
    await ctx.copyLog()
    expect(ElMessage.error).toHaveBeenCalledWith('复制失败')
  })
})

describe('useTaskDetail — 初始化与 WebSocket', () => {
  it('init 清空日志、拉取数据并在执行中开启轮询', async () => {
    localStorage.setItem('token', 'tk')
    await mountHost()

    await ctx.init()

    expect(mocks.store.clearExecutionLogs).toHaveBeenCalled()
    expect(mocks.store.fetchTaskDetail).toHaveBeenCalledWith(42, 7)
    expect(mocks.store.fetchTaskResults).toHaveBeenCalledWith(42, 7)
    expect(mocks.connect).toHaveBeenCalledWith(42, 7, 'tk')
    expect(mocks.onMessage).toHaveBeenCalled()

    ctx.cleanup()
    expect(mocks.offMessage).toHaveBeenCalled()
    expect(mocks.disconnect).toHaveBeenCalled()
  })

  it('无 token 时不建立 WebSocket', async () => {
    localStorage.removeItem('token')
    await mountHost()

    await ctx.init()

    expect(mocks.connect).not.toHaveBeenCalled()
  })

  it('WebSocket 消息分发到对应 store 方法', async () => {
    localStorage.setItem('token', 'tk')
    await mountHost()
    await ctx.init()

    const handler = mocks.onMessage.mock.calls[0][0] as (data: unknown) => void

    handler({ type: 'log', status: 1, log: 'hi', case_no: 'TC-1' })
    expect(mocks.store.addExecutionLog).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: 42, log: 'hi', case_no: 'TC-1' })
    )

    handler({ type: 'progress', progress: 50, success_count: 1, fail_count: 0 })
    expect(mocks.store.updateExecutionProgress).toHaveBeenCalledWith(
      expect.objectContaining({ task_id: 42, progress: 50 })
    )

    handler({ type: 'status', status: 2 })
    expect(mocks.store.updateTaskStatus).toHaveBeenCalledWith(42, 2)

    ctx.cleanup()
  })
})
