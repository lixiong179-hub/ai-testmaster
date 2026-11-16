import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'
import type { PipelineRun } from '@/api/pipeline'

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
  getPipelineRun: vi.fn(),
  getPipelineSummary: vi.fn(),
  getInferredSummary: vi.fn(),
  supplementSignals: vi.fn(),
  getArtifactDetail: vi.fn(),
  resumePipeline: vi.fn(),
  runPipeline: vi.fn(),
  getReviewsByIteration: vi.fn(),
  getRunCost: vi.fn(),
}))

const route = vi.hoisted(() => ({ params: { runId: '5' } as Record<string, string> }))

vi.mock('vue-router', () => ({
  useRoute: () => route,
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
}))

vi.mock('@/api/pipeline', () => ({
  pipelineApi: {
    getPipelineRun: mocks.getPipelineRun,
    getPipelineSummary: mocks.getPipelineSummary,
    getInferredSummary: mocks.getInferredSummary,
    supplementSignals: mocks.supplementSignals,
    getArtifactDetail: mocks.getArtifactDetail,
    resumePipeline: mocks.resumePipeline,
    runPipeline: mocks.runPipeline,
  },
}))

vi.mock('@/api/review', () => ({
  reviewApi: { getReviewsByIteration: mocks.getReviewsByIteration },
}))

vi.mock('@/api/aiInvocation', () => ({
  aiInvocationApi: { getRunCost: mocks.getRunCost },
  usdToCny: (usd: number) => Number((usd * 7.25).toFixed(4)),
}))

class FakeWebSocket {
  static instances: FakeWebSocket[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()
  constructor(public url: string) {
    FakeWebSocket.instances.push(this)
  }
  emitOpen() {
    this.onopen?.()
  }
  emitClose() {
    this.onclose?.()
  }
  emitMessage(data: unknown) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) })
  }
}

vi.stubGlobal('WebSocket', FakeWebSocket)

import { usePipelineProgress } from '../usePipelineProgress'

type Ctx = ReturnType<typeof usePipelineProgress>

const host = createComposableHost<Ctx>(() => usePipelineProgress())
let ctx: Ctx

function makeRun(over: Record<string, unknown> = {}): PipelineRun {
  return {
    id: 5,
    status: 'running',
    iteration_id: 3,
    started_at: '2026-11-16T08:00:00Z',
    finished_at: null,
    error: null,
    pause_payload: null,
    steps: [],
    ...over,
  } as unknown as PipelineRun
}

async function mountHost(run: Record<string, unknown> = { status: 'completed' }) {
  mocks.getPipelineRun.mockResolvedValue({ data: makeRun(run) })
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function lastWs() {
  return FakeWebSocket.instances[FakeWebSocket.instances.length - 1]
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  FakeWebSocket.instances = []
  route.params = { runId: '5' }
  localStorage.removeItem('token')
  mocks.getPipelineSummary.mockResolvedValue({ data: { total_cases: 3 } })
  mocks.getInferredSummary.mockResolvedValue({ data: { business_flow: '下单' } })
  mocks.getReviewsByIteration.mockResolvedValue({ data: { reviews: [] } })
  mocks.getRunCost.mockResolvedValue({ data: { totalTokens: 1200, totalCostUsd: 0.4 } })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('usePipelineProgress — 派生状态与格式化', () => {
  it('从路由参数解析 runId 并在挂载时拉取运行详情', async () => {
    await mountHost()

    expect(mocks.getPipelineRun).toHaveBeenCalledWith(5)
    expect(ctx.runData.value?.id).toBe(5)
    expect(ctx.initialLoading.value).toBe(false)
  })

  it('运行状态映射文案与标签色', async () => {
    await mountHost({ status: 'waiting_for_user' })

    expect(ctx.runStatusText.value).toBe('等待确认')
    expect(ctx.runStatusType.value).toBe('warning')
  })

  it('未知状态回退为原始值', async () => {
    await mountHost({ status: 'unknown_state' })

    expect(ctx.runStatusText.value).toBe('unknown_state')
    expect(ctx.runStatusType.value).toBe('info')
  })

  it('步骤状态映射覆盖降级完成并透传未知值', async () => {
    await mountHost()

    expect(ctx.stepStatusText('degraded')).toBe('降级完成')
    expect(ctx.stepStatusType('degraded')).toBe('warning')
    expect(ctx.stepStatusText('weird')).toBe('weird')
    expect(ctx.stepStatusType('weird')).toBe('info')
  })

  it('el-step 状态映射', async () => {
    await mountHost()

    expect(ctx.stepElStatus('done')).toBe('success')
    expect(ctx.stepElStatus('degraded')).toBe('success')
    expect(ctx.stepElStatus('running')).toBe('process')
    expect(ctx.stepElStatus('failed')).toBe('error')
    expect(ctx.stepElStatus('pending')).toBe('wait')
  })

  it('置信度分三档配色', async () => {
    await mountHost()

    expect(ctx.confidenceColor(0.9)).toBe('#67c23a')
    expect(ctx.confidenceColor(0.75)).toBe('#e6a23c')
    expect(ctx.confidenceColor(0.5)).toBe('#f56c6c')
  })

  it('时间格式化：空值占位、合法值转本地串', async () => {
    await mountHost()

    expect(ctx.formatTime(null)).toBe('—')
    expect(ctx.formatTime('2026-11-16T08:00:00Z')).toMatch(/2026/)
  })

  it('运行时长：缺开始时间占位，结束时间计算为秒/分', async () => {
    await mountHost({
      status: 'completed',
      started_at: '2026-11-16T08:00:00Z',
      finished_at: '2026-11-16T08:00:45Z',
    })

    expect(ctx.duration.value).toBe('45秒')

    await mountHost({
      status: 'completed',
      started_at: '2026-11-16T08:00:00Z',
      finished_at: '2026-11-16T08:02:05Z',
    })
    expect(ctx.duration.value).toBe('2分5秒')

    await mountHost({ started_at: null })
    expect(ctx.duration.value).toBe('—')
  })

  it('未结束的运行使用当前时间计算时长（小时级）', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-16T10:00:00Z'))
    await mountHost({ status: 'running', started_at: '2026-11-16T08:00:00Z' })

    expect(ctx.duration.value).toBe('2时0分')
  })

  it('步骤时长同样支持占位与进行中计算', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-11-16T08:00:30Z'))
    await mountHost()

    expect(ctx.stepDuration({ started_at: null, finished_at: null })).toBe('—')
    expect(ctx.stepDuration({ started_at: '2026-11-16T08:00:00Z', finished_at: null })).toBe('30秒')
  })

  it('人工确认原因优先取 pause_payload.reason，其次 error，最后兜底文案', async () => {
    await mountHost({ pause_payload: { reason: '需要人工选择模块' }, error: 'boom' })
    expect(ctx.confirmReason.value).toBe('需要人工选择模块')

    await mountHost({ pause_payload: null, error: '步骤失败' })
    expect(ctx.confirmReason.value).toBe('步骤失败')

    await mountHost({ pause_payload: null, error: null })
    expect(ctx.confirmReason.value).toBe('Pipeline 需要人工确认后继续')
  })

  it('pause_payload 中的 schema 透出给确认弹窗', async () => {
    const schema = { fields: [{ key: 'module', label: '模块', type: 'select' }] }
    await mountHost({ pause_payload: { schema } })

    expect(ctx.confirmSchema.value).toEqual(schema)
  })

  it('无 schema 时确认弹窗使用默认表单', async () => {
    await mountHost({ pause_payload: { reason: 'need input' } })

    expect(ctx.confirmSchema.value).toBeNull()
  })

  it('终态横幅仅在 completed/failed/cancelled 时出现', async () => {
    await mountHost({ status: 'completed' })
    expect(ctx.terminalBanner.value).toEqual({ status: 'completed', cls: 'terminal-completed' })

    await mountHost({ status: 'running' })
    expect(ctx.terminalBanner.value).toBeNull()
  })

  it('活跃步骤索引取正在运行的步骤，否则等于步骤数', async () => {
    await mountHost({
      steps: [{ status: 'done' }, { status: 'running' }, { status: 'pending' }],
    })
    expect(ctx.activeStepIndex.value).toBe(1)

    await mountHost({ steps: [{ status: 'done' }, { status: 'done' }] })
    expect(ctx.activeStepIndex.value).toBe(2)
  })
})

describe('usePipelineProgress — 数据加载', () => {
  it('runId 缺失时不请求', async () => {
    route.params = {}
    await mountHost()

    expect(mocks.getPipelineRun).not.toHaveBeenCalled()
  })

  it('拉取失败时提示错误信息', async () => {
    mocks.getPipelineRun.mockRejectedValue(new Error('运行不存在'))
    await host.mount()
    ctx = host.ctx

    expect(ElMessage.error).toHaveBeenCalledWith('运行不存在')
    expect(ctx.loading.value).toBe(false)
  })

  it('拉取失败且非 Error 时使用兜底文案', async () => {
    mocks.getPipelineRun.mockRejectedValue('boom')
    await host.mount()
    ctx = host.ctx

    expect(ElMessage.error).toHaveBeenCalledWith('获取 Pipeline 状态失败')
  })

  it('完成态自动加载摘要与 AI 推断', async () => {
    await mountHost({ status: 'completed' })
    await flushPromises()

    expect(mocks.getPipelineSummary).toHaveBeenCalledWith(5)
    expect(mocks.getInferredSummary).toHaveBeenCalledWith(5)
    expect(ctx.pipelineSummary.value).toEqual({ total_cases: 3 })
    expect(ctx.inferredSummary.value).toEqual({ business_flow: '下单' })
    expect(ctx.summaryLoading.value).toBe(false)
  })

  it('未完成时不加载摘要', async () => {
    await mountHost({ status: 'running' })

    expect(mocks.getPipelineSummary).not.toHaveBeenCalled()
  })

  it('已加载过摘要时不重复请求', async () => {
    await mountHost({ status: 'completed' })
    mocks.getPipelineSummary.mockClear()

    await ctx.loadPipelineSummary()

    expect(mocks.getPipelineSummary).not.toHaveBeenCalled()
  })

  it('摘要加载失败时提示', async () => {
    mocks.getPipelineSummary.mockRejectedValue(new Error('摘要服务异常'))
    await mountHost({ status: 'completed' })
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('摘要服务异常')
    expect(ctx.summaryLoading.value).toBe(false)
  })

  it('摘要接口返回空数据时保留 null', async () => {
    mocks.getPipelineSummary.mockResolvedValue({ data: null })
    mocks.getInferredSummary.mockResolvedValue({ data: null })
    await mountHost({ status: 'completed' })
    await flushPromises()

    expect(ctx.pipelineSummary.value).toBeNull()
    expect(ctx.inferredSummary.value).toBeNull()
  })
})

describe('usePipelineProgress — 信号补全与产物详情', () => {
  it('补全信号成功后提示并刷新运行详情', async () => {
    await mountHost({ status: 'waiting_for_user' })
    mocks.supplementSignals.mockResolvedValue({ code: 0 })
    mocks.getPipelineRun.mockClear()

    const payload = {
      confirmed_capabilities: [{ id: 'order' }],
      answers: [],
      change_summary: null,
      notes: '已确认下单能力',
    }
    await ctx.handleSupplementSignals(payload)

    expect(mocks.supplementSignals).toHaveBeenCalledWith(5, payload)
    expect(ElMessage.success).toHaveBeenCalledWith('信号补全成功')
    expect(mocks.getPipelineRun).toHaveBeenCalledTimes(1)
  })

  it('补全信号失败时提示', async () => {
    await mountHost({ status: 'waiting_for_user' })
    mocks.supplementSignals.mockRejectedValue(new Error('信号格式错误'))

    await ctx.handleSupplementSignals({
      confirmed_capabilities: [],
      answers: [],
      change_summary: null,
      notes: null,
    })

    expect(ElMessage.error).toHaveBeenCalledWith('信号格式错误')
  })

  it('展开产物详情并按运行 ID 请求', async () => {
    await mountHost()
    mocks.getArtifactDetail.mockResolvedValue({ data: { id: 11, content: '原始信号' } })

    await ctx.toggleArtifactDetail(11)

    expect(mocks.getArtifactDetail).toHaveBeenCalledWith(5, 11)
    expect(ctx.expandedArtifactId.value).toBe(11)
    expect(ctx.artifactDetail.value).toEqual({ id: 11, content: '原始信号' })
    expect(ctx.artifactDetailLoading.value).toBe(false)
  })

  it('再次点击同一条产物收起详情且不重复请求', async () => {
    await mountHost()
    mocks.getArtifactDetail.mockResolvedValue({ data: { id: 11 } })
    await ctx.toggleArtifactDetail(11)
    mocks.getArtifactDetail.mockClear()

    await ctx.toggleArtifactDetail(11)

    expect(mocks.getArtifactDetail).not.toHaveBeenCalled()
    expect(ctx.expandedArtifactId.value).toBeNull()
    expect(ctx.artifactDetail.value).toBeNull()
  })

  it('产物详情失败时提示并收起', async () => {
    await mountHost()
    mocks.getArtifactDetail.mockRejectedValue(new Error('产物不存在'))

    await ctx.toggleArtifactDetail(11)

    expect(ElMessage.error).toHaveBeenCalledWith('产物不存在')
    expect(ctx.expandedArtifactId.value).toBeNull()
  })

  it('运行数据未就绪时不请求产物详情', async () => {
    await mountHost({ status: 'completed' })
    ;(ctx.runData as { value: unknown }).value = null

    await ctx.toggleArtifactDetail(11)

    expect(mocks.getArtifactDetail).not.toHaveBeenCalled()
  })
})

describe('usePipelineProgress — 恢复运行', () => {
  it('等待人工确认时打开确认弹窗', async () => {
    await mountHost({ status: 'waiting_for_user' })

    await ctx.handleResume()

    expect(ctx.showConfirmDialog.value).toBe(true)
    expect(mocks.resumePipeline).not.toHaveBeenCalled()
  })

  it('非等待态直接恢复且不带 payload', async () => {
    await mountHost({ status: 'failed' })
    mocks.resumePipeline.mockResolvedValue({ code: 0 })
    mocks.getPipelineRun.mockClear()

    await ctx.handleResume()
    await flushPromises()

    expect(mocks.resumePipeline).toHaveBeenCalledWith(5, undefined)
    expect(ElMessage.success).toHaveBeenCalledWith('Pipeline 已恢复')
  })

  it('确认弹窗提交后关闭并携带 payload 恢复', async () => {
    await mountHost({ status: 'waiting_for_user' })
    ctx.showConfirmDialog.value = true
    mocks.resumePipeline.mockResolvedValue({ code: 0 })

    ctx.handleConfirmResume({ module: 'order' })
    await flushPromises()

    expect(ctx.showConfirmDialog.value).toBe(false)
    expect(mocks.resumePipeline).toHaveBeenCalledWith(5, { module: 'order' })
  })

  it('恢复冲突（409）时提示状态已变更', async () => {
    await mountHost({ status: 'failed' })
    mocks.resumePipeline.mockRejectedValue({ status: 409 })

    await ctx.handleConfirmResume({})
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalledWith('Pipeline 状态已变更，请刷新')
  })

  it('恢复失败时提示失败', async () => {
    await mountHost({ status: 'failed' })
    mocks.resumePipeline.mockRejectedValue(new Error('boom'))

    await ctx.handleConfirmResume({})
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('恢复失败')
  })
})

describe('usePipelineProgress — WebSocket', () => {
  it('无 token 时不建立连接', async () => {
    await mountHost()

    expect(FakeWebSocket.instances).toHaveLength(0)
  })

  it('按 token 拼接 ws 地址，连接成功后停止轮询', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    const ws = lastWs()

    expect(ws.url).toContain('/api/v1/ws/pipeline/5?token=tk-1')
    ws.emitOpen()

    expect(ctx.isPolling.value).toBe(true)
  })

  it('收到进度推送时刷新运行详情', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    mocks.getPipelineRun.mockClear()

    lastWs().emitMessage({
      type: 'pipeline_progress',
      run_id: 5,
      pipeline_status: 'running',
      step_name: 'case_generation',
      status: 'running',
      progress: 30,
    })
    await flushPromises()

    expect(mocks.getPipelineRun).toHaveBeenCalledTimes(1)
  })

  it('收到终态推送时关闭连接', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    const ws = lastWs()

    ws.emitMessage({ type: 'pipeline_progress', run_id: 5, pipeline_status: 'completed' })

    expect(ws.close).toHaveBeenCalled()
  })

  it('忽略非 pipeline_progress 与非法 JSON 消息', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    mocks.getPipelineRun.mockClear()

    lastWs().emitMessage({ type: 'heartbeat' })
    lastWs().emitMessage('not-json{')
    await flushPromises()

    expect(mocks.getPipelineRun).not.toHaveBeenCalled()
  })

  it('连接关闭后按退避策略重连', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    vi.useFakeTimers()
    FakeWebSocket.instances[0].emitClose()

    await vi.advanceTimersByTimeAsync(2000)
    expect(FakeWebSocket.instances).toHaveLength(2)

    FakeWebSocket.instances[1].emitClose()
    await vi.advanceTimersByTimeAsync(3999)
    expect(FakeWebSocket.instances).toHaveLength(2)
    await vi.advanceTimersByTimeAsync(1)
    expect(FakeWebSocket.instances).toHaveLength(3)
  })

  it('重连次数用尽后回退到轮询', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    vi.useFakeTimers()

    // 连续 3 次断开触发退避重连
    for (let i = 0; i < 3; i++) {
      FakeWebSocket.instances[i].emitClose()
      await vi.advanceTimersByTimeAsync(2000 * Math.pow(2, i))
    }

    mocks.getPipelineRun.mockClear()
    FakeWebSocket.instances[3].emitClose()
    await vi.advanceTimersByTimeAsync(5000)

    expect(mocks.getPipelineRun).toHaveBeenCalled()
  })

  it('连接异常时标记未连接', async () => {
    localStorage.setItem('token', 'tk-1')
    await mountHost({ status: 'running' })
    const ws = lastWs()
    ws.emitOpen()

    ws.onerror?.()

    expect(ctx.isPolling.value).toBe(true)
  })

  it('卸载时主动断开且不再重连', async () => {
    localStorage.setItem('token', 'tk-1')
    const wrapper = await mountHost({ status: 'running' })
    const ws = lastWs()
    vi.useFakeTimers()

    wrapper.unmount()
    ws.emitClose()
    await vi.advanceTimersByTimeAsync(10000)

    expect(ws.close).toHaveBeenCalled()
    expect(FakeWebSocket.instances).toHaveLength(1)
  })
})

describe('usePipelineProgress — 轮询', () => {
  it('运行中按 5 秒轮询，完成后停止', async () => {
    // 轮询定时器在挂载时创建，需先启用假定时器
    vi.useFakeTimers()
    await mountHost({ status: 'running' })
    mocks.getPipelineRun.mockClear()
    mocks.getPipelineRun.mockResolvedValue({ data: makeRun({ status: 'running' }) })

    await vi.advanceTimersByTimeAsync(5000)
    expect(mocks.getPipelineRun).toHaveBeenCalledTimes(1)

    mocks.getPipelineRun.mockResolvedValue({ data: makeRun({ status: 'completed' }) })
    await vi.advanceTimersByTimeAsync(5000)
    expect(mocks.getPipelineRun).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(15000)
    expect(mocks.getPipelineRun).toHaveBeenCalledTimes(2)
  })
})

describe('usePipelineProgress — 跳转与重试', () => {
  it('返回上一页', async () => {
    await mountHost()

    ctx.goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
  })

  it('跳转评审 Inbox：定位最新评审记录', async () => {
    await mountHost({ status: 'completed' })
    mocks.getReviewsByIteration.mockResolvedValue({ data: { reviews: [{ id: 42 }] } })

    await ctx.goToReviewInbox()

    expect(mocks.getReviewsByIteration).toHaveBeenCalledWith(3)
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'IterationReviewInbox',
      params: { reviewId: '42' },
      query: { iteration_id: '3' },
    })
  })

  it('无评审记录时跳转评审列表占位页', async () => {
    await mountHost({ status: 'completed' })

    await ctx.goToReviewInbox()

    expect(mocks.push).toHaveBeenCalledWith('/home/iteration/review/0')
  })

  it('评审查询失败时仍回退到评审列表', async () => {
    await mountHost({ status: 'completed' })
    mocks.getReviewsByIteration.mockRejectedValue(new Error('boom'))

    await ctx.goToReviewInbox()

    expect(mocks.push).toHaveBeenCalledWith('/home/iteration/review/0')
  })

  it('缺少迭代信息时提示且不跳转', async () => {
    await mountHost({ status: 'failed', iteration_id: null })

    await ctx.goToReviewInbox()

    expect(ElMessage.warning).toHaveBeenCalledWith('缺少迭代信息，无法跳转评审')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('重试以场景 4 启动并跳转新运行', async () => {
    await mountHost({ status: 'failed' })
    mocks.runPipeline.mockResolvedValue({ data: { run_id: 66 } })

    await ctx.retryPipeline()

    expect(mocks.runPipeline).toHaveBeenCalledWith(3, { scenario: 4 })
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'IterationPipelineProgress',
      params: { runId: 66 },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('已重新启动 Pipeline')
  })

  it('重试未返回运行 ID 时提示', async () => {
    await mountHost({ status: 'failed' })
    mocks.runPipeline.mockResolvedValue({ data: {} })

    await ctx.retryPipeline()

    expect(ElMessage.error).toHaveBeenCalledWith('重试失败：未返回运行 ID')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('重试失败时提示', async () => {
    await mountHost({ status: 'failed' })
    mocks.runPipeline.mockRejectedValue(new Error('boom'))

    await ctx.retryPipeline()

    expect(ElMessage.error).toHaveBeenCalledWith('重试 Pipeline 失败')
  })

  it('缺少迭代信息时无法重试', async () => {
    await mountHost({ status: 'failed', iteration_id: null })

    await ctx.retryPipeline()

    expect(ElMessage.warning).toHaveBeenCalledWith('缺少迭代信息，无法重试')
    expect(mocks.runPipeline).not.toHaveBeenCalled()
  })
})

describe('usePipelineProgress — Token 用量', () => {
  it('初始展示占位文案', async () => {
    mocks.getRunCost.mockResolvedValue({ data: { totalTokens: 0, totalCostUsd: 0 } })
    await host.mount()
    ctx = host.ctx

    expect(ctx.tokenUsageText.value).toContain('Token:')
  })

  it('拉取账单后按千分位与人民币展示', async () => {
    mocks.getRunCost.mockResolvedValue({ data: { totalTokens: 12345, totalCostUsd: 0.4 } })
    await mountHost()
    await ctx.fetchTokenUsage()

    expect(mocks.getRunCost).toHaveBeenCalledWith(5)
    expect(ctx.tokenUsageText.value).toBe('Token: 12,345 | 成本: ¥2.90')
  })

  it('账单接口直接返回统计体时同样解析', async () => {
    await mountHost()
    mocks.getRunCost.mockResolvedValue({ totalTokens: 1000, totalCostUsd: 0.2 })

    await ctx.fetchTokenUsage()

    expect(ctx.tokenUsageText.value).toBe('Token: 1,000 | 成本: ¥1.45')
  })

  it('账单拉取失败时清空用量', async () => {
    await mountHost()
    mocks.getRunCost.mockRejectedValue(new Error('boom'))

    await ctx.fetchTokenUsage()

    expect(ctx.tokenUsageText.value).toBe('Token: — | 成本: —')
  })
})
