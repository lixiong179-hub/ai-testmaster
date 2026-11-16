import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

vi.mock('@/api/testExecution', () => ({
  startTestExecution: vi.fn(),
  pauseTestExecution: vi.fn(),
  resumeTestExecution: vi.fn(),
  stopTestExecution: vi.fn(),
}))

import {
  startTestExecution,
  pauseTestExecution,
  resumeTestExecution,
  stopTestExecution,
  type ExecutionMode,
} from '@/api/testExecution'
import { useExecutionControl } from '../useExecutionControl'
import { mockCancel, mockConfirm, silenceConsole, silenceElMessage } from '@/test-utils'

const startMock = vi.mocked(startTestExecution)
const pauseMock = vi.mocked(pauseTestExecution)
const resumeMock = vi.mocked(resumeTestExecution)
const stopMock = vi.mocked(stopTestExecution)

const okBody = (data: Record<string, unknown> = {}) => ({ code: 200, data })

function setup(overrides: Record<string, unknown> = {}) {
  const executionStatus = ref<Record<string, unknown> | null>({
    status: 'idle',
    current_step: 2,
    total_steps: 5,
  })
  const visibilityConfig = ref({ headless: true, recordVideo: false, videoFps: 30 })
  const targetEnv = ref('staging')
  const autoInitEnabled = ref(false)
  const executionMode = ref<ExecutionMode>('realtime')
  const mobileDeviceId = ref('')
  const useMcpMode = ref(true)

  const syncTaskInfoStatus = vi.fn()
  const loadTaskInfo = vi.fn().mockResolvedValue(undefined)
  const loadExecutionStatus = vi.fn().mockResolvedValue(undefined)
  const connectWebSocketForRealtimeUpdate = vi.fn()

  const api = useExecutionControl({
    taskId: () => 42,
    executionStatus,
    visibilityConfig,
    targetEnv,
    autoInitEnabled,
    executionMode,
    mobileDeviceId,
    useMcpMode,
    syncTaskInfoStatus,
    loadTaskInfo,
    loadExecutionStatus,
    connectWebSocketForRealtimeUpdate,
    ...overrides,
  })

  return {
    api,
    executionStatus,
    visibilityConfig,
    targetEnv,
    autoInitEnabled,
    executionMode,
    mobileDeviceId,
    useMcpMode,
    syncTaskInfoStatus,
    loadTaskInfo,
    loadExecutionStatus,
    connectWebSocketForRealtimeUpdate,
  }
}

describe('useExecutionControl — 开始执行', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    startMock.mockResolvedValue(okBody({ task_status: 1, status: 'running' }) as never)
    silenceElMessage('success')
    silenceElMessage('error')
    silenceElMessage('warning')
    silenceElMessage('info')
    silenceConsole('error')
  })

  it('移动端模式未选设备时拦截并提示', async () => {
    const ctx = setup({ executionMode: ref<ExecutionMode>('mobile_realtime') })

    await ctx.api.startExecution()

    expect(ElMessage.warning).toHaveBeenCalledWith('移动端模式请先选择目标设备')
    expect(startMock).not.toHaveBeenCalled()
    expect(ctx.api.controlLoading.value).toBe(false)
  })

  it('按可见性/环境/初始化开关组装入参', async () => {
    const ctx = setup({
      executionMode: ref<ExecutionMode>('mobile_smart'),
      mobileDeviceId: ref('dev-1'),
    })

    await ctx.api.startExecution()

    expect(startMock).toHaveBeenCalledWith(42, {
      headless: true,
      recordVideo: false,
      targetEnv: 'staging',
      skipInit: true,
      executionMode: 'mobile_smart',
      mobileDeviceId: 'dev-1',
      use_mcp: true,
    })
  })

  it('非移动端模式不传 mobileDeviceId', async () => {
    const ctx = setup()

    await ctx.api.startExecution()

    expect(startMock.mock.calls[0][1]?.mobileDeviceId).toBeUndefined()
  })

  it('执行完成后同步终态并刷新数据、连接实时更新', async () => {
    startMock.mockResolvedValue(okBody({ task_status: 2, status: 'completed' }) as never)
    const ctx = setup()

    await ctx.api.startExecution()

    expect(ElMessage.success).toHaveBeenCalledWith('执行完成')
    expect(ctx.syncTaskInfoStatus).toHaveBeenCalledWith(2)
    expect(ctx.executionStatus.value).toEqual({
      status: 'completed',
      current_step: 2,
      total_steps: 5,
    })
    expect(ctx.loadTaskInfo).toHaveBeenCalledTimes(1)
    expect(ctx.loadExecutionStatus).toHaveBeenCalledTimes(1)
    expect(ctx.connectWebSocketForRealtimeUpdate).toHaveBeenCalledTimes(1)
    expect(ctx.api.controlLoading.value).toBe(false)
  })

  it.each([
    [3, '执行失败', 'error'],
    [4, '执行已停止', 'info'],
    [1, '开始执行', 'success'],
  ] as const)('终态码 %i 走对应提示', async (status, text, level) => {
    startMock.mockResolvedValue(okBody({ task_status: status }) as never)
    const ctx = setup()

    await ctx.api.startExecution()

    expect(ElMessage[level]).toHaveBeenCalledWith(text)
    expect(ctx.syncTaskInfoStatus).toHaveBeenCalledWith(status)
  })

  it('缺省终态按 1 处理且 status 回退 running', async () => {
    startMock.mockResolvedValue(okBody({}) as never)
    const ctx = setup()

    await ctx.api.startExecution()

    expect(ctx.syncTaskInfoStatus).toHaveBeenCalledWith(1)
    expect(ctx.executionStatus.value).toEqual({
      status: 'running',
      current_step: 2,
      total_steps: 5,
    })
  })

  it('业务码非 200 时展示后端消息且不刷新', async () => {
    startMock.mockResolvedValue({ code: 500, message: '任务不存在' } as never)
    const ctx = setup()

    await ctx.api.startExecution()

    expect(ElMessage.error).toHaveBeenCalledWith('任务不存在')
    expect(ctx.loadTaskInfo).not.toHaveBeenCalled()
    expect(ctx.loadExecutionStatus).not.toHaveBeenCalled()
  })

  it('请求异常时兜底提示并复位 loading', async () => {
    startMock.mockRejectedValue(new Error('network'))
    const ctx = setup()

    await ctx.api.startExecution()

    expect(ElMessage.error).toHaveBeenCalledWith('开始执行失败')
    expect(console.error).toHaveBeenCalled()
    expect(ctx.api.controlLoading.value).toBe(false)
  })

  it('请求进行中 controlLoading 为 true', async () => {
    let resolveFn: ((value: unknown) => void) | undefined
    startMock.mockReturnValue(
      new Promise((resolve) => {
        resolveFn = resolve
      }) as never
    )
    const ctx = setup()

    const pending = ctx.api.startExecution()
    expect(ctx.api.controlLoading.value).toBe(true)

    resolveFn?.(okBody({}))
    await pending

    expect(ctx.api.controlLoading.value).toBe(false)
  })
})

describe('useExecutionControl — 暂停/恢复/停止', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    pauseMock.mockResolvedValue({ code: 200 } as never)
    resumeMock.mockResolvedValue({ code: 200 } as never)
    stopMock.mockResolvedValue({ code: 200 } as never)
    silenceElMessage('success')
    silenceElMessage('error')
    silenceConsole('error')
  })

  it('暂停成功后刷新执行状态', async () => {
    const ctx = setup()

    await ctx.api.pauseExecution()

    expect(pauseMock).toHaveBeenCalledWith(42)
    expect(ElMessage.success).toHaveBeenCalledWith('已暂停')
    expect(ctx.loadExecutionStatus).toHaveBeenCalledTimes(1)
    expect(ctx.api.controlLoading.value).toBe(false)
  })

  it('暂停异常提示失败', async () => {
    pauseMock.mockRejectedValue(new Error('boom'))
    const ctx = setup()

    await ctx.api.pauseExecution()

    expect(ElMessage.error).toHaveBeenCalledWith('暂停失败')
    expect(ctx.loadExecutionStatus).not.toHaveBeenCalled()
  })

  it('恢复成功后刷新执行状态', async () => {
    const ctx = setup()

    await ctx.api.resumeExecution()

    expect(resumeMock).toHaveBeenCalledWith(42)
    expect(ElMessage.success).toHaveBeenCalledWith('已恢复')
    expect(ctx.loadExecutionStatus).toHaveBeenCalledTimes(1)
  })

  it('恢复异常提示失败', async () => {
    resumeMock.mockRejectedValue(new Error('boom'))
    const ctx = setup()

    await ctx.api.resumeExecution()

    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
  })

  it('确认后停止执行并刷新状态', async () => {
    mockConfirm()
    const ctx = setup()

    await ctx.api.stopExecution()

    expect(ElMessageBox.confirm).toHaveBeenCalledWith('确定要停止执行吗？', '确认', {
      type: 'warning',
    })
    expect(stopMock).toHaveBeenCalledWith(42)
    expect(ElMessage.success).toHaveBeenCalledWith('已停止')
    expect(ctx.loadExecutionStatus).toHaveBeenCalledTimes(1)
  })

  it('取消确认时不请求接口也不报错', async () => {
    mockCancel()
    const ctx = setup()

    await ctx.api.stopExecution()

    expect(stopMock).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ctx.api.controlLoading.value).toBe(false)
  })

  it('非取消异常提示停止失败', async () => {
    mockConfirm()
    stopMock.mockRejectedValue(new Error('boom'))
    const ctx = setup()

    await ctx.api.stopExecution()

    expect(ElMessage.error).toHaveBeenCalledWith('停止失败')
  })
})
