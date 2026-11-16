import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose, Loading, Warning } from '@element-plus/icons-vue'
import { createComposableHost, silenceConsole, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  route: {
    params: { taskId: '42' } as Record<string, string>,
    query: {} as Record<string, string>,
  },
  push: vi.fn(),
  getExecutionStatus: vi.fn(),
  getExecutionLogs: vi.fn(),
  getStepScreenshot: vi.fn(),
  getVisibilityConfig: vi.fn(),
  updateVisibilityConfig: vi.fn(),
  getConnectedDevices: vi.fn(),
  getTaskDetail: vi.fn(),
  getProjectDetail: vi.fn(),
  connectWs: vi.fn(),
  startExecution: vi.fn(),
  pauseExecution: vi.fn(),
  resumeExecution: vi.fn(),
  stopExecution: vi.fn(),
  toggleVideoPlay: vi.fn(),
  seekVideo: vi.fn(),
  onVideoTimeChange: vi.fn(),
  startReplay: vi.fn(),
  pauseReplay: vi.fn(),
  stopReplay: vi.fn(),
  handleAnalyzeFailure: vi.fn(),
  handleCorrectCase: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/testExecution', () => ({
  getExecutionStatus: mocks.getExecutionStatus,
  getExecutionLogs: mocks.getExecutionLogs,
  getStepScreenshot: mocks.getStepScreenshot,
  getVisibilityConfig: mocks.getVisibilityConfig,
  updateVisibilityConfig: mocks.updateVisibilityConfig,
  getConnectedDevices: mocks.getConnectedDevices,
}))

vi.mock('@/api/testTask', () => ({
  default: { getTaskDetail: mocks.getTaskDetail },
}))

vi.mock('@/api/project', () => ({
  default: { getProjectDetail: mocks.getProjectDetail },
}))

vi.mock('@/composables/useExecutionControl', () => ({
  useExecutionControl: () => ({
    controlLoading: ref(false),
    startExecution: mocks.startExecution,
    pauseExecution: mocks.pauseExecution,
    resumeExecution: mocks.resumeExecution,
    stopExecution: mocks.stopExecution,
  }),
}))

vi.mock('@/composables/useExecutionWebSocket', () => ({
  useExecutionWebSocket: () => ({ connectWebSocketForRealtimeUpdate: mocks.connectWs }),
}))

vi.mock('@/composables/useVideoReplay', () => ({
  useVideoReplay: () => ({
    isVideoPlaying: ref(false),
    videoCurrentTime: ref(0),
    videoDuration: ref(100),
    replaySpeed: ref(1),
    toggleVideoPlay: mocks.toggleVideoPlay,
    seekVideo: mocks.seekVideo,
    onVideoTimeChange: mocks.onVideoTimeChange,
    startReplay: mocks.startReplay,
    pauseReplay: mocks.pauseReplay,
    stopReplay: mocks.stopReplay,
  }),
}))

vi.mock('@/composables/useFailureAnalysis', () => ({
  useFailureAnalysis: () => ({
    failureAnalysisMap: ref({}),
    analysisLoading: ref(false),
    issueTypeMap: ref({}),
    handleAnalyzeFailure: mocks.handleAnalyzeFailure,
    handleCorrectCase: mocks.handleCorrectCase,
  }),
  ISSUE_TYPE_LABELS: { product_bug: '产品缺陷', script_issue: '脚本问题' },
  ISSUE_TYPE_COLORS: { product_bug: 'danger', script_issue: 'warning' },
}))

import { provideTestExecution } from '../useTestExecution'

type Ctx = ReturnType<typeof provideTestExecution>

let ctx: Ctx

const host = createComposableHost(() => provideTestExecution())

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.params = { taskId: '42' }
  mocks.route.query = {}
  silenceElMessage('success', 'error')
  silenceConsole('error')

  mocks.getTaskDetail.mockResolvedValue({
    code: 200,
    data: { task: { id: 42, status: 1, project_id: 7, name: '任务A' } },
  })
  mocks.getProjectDetail.mockResolvedValue({
    code: 200,
    data: {
      web_env_configs: {
        test: { url: 'http://test', username: 'u' },
        dev: { url: 'http://dev' },
        empty: {},
      },
    },
  })
  mocks.getExecutionStatus.mockResolvedValue({
    code: 200,
    data: { status: 'running', current_step: 2, total_steps: 4 },
  })
  mocks.getExecutionLogs.mockResolvedValue({
    code: 200,
    data: { logs: [{ level: 'info', timestamp: '2026-11-13T10:00:00Z', message: '启动' }] },
  })
  mocks.getStepScreenshot.mockResolvedValue({ data: new Blob(['x']) })
  mocks.getVisibilityConfig.mockResolvedValue({
    code: 200,
    data: { headless: false, record_video: true, video_fps: 45, video_resolution: [1920, 1080] },
  })
  mocks.updateVisibilityConfig.mockResolvedValue({ code: 200 })
  mocks.getConnectedDevices.mockResolvedValue({
    code: 200,
    data: [{ udid: 'dev-1', model: 'Pixel', state: 'device' }],
  })
})

describe('useTestExecution — 初始化与任务信息', () => {
  it('taskId 取自路由并加载任务、状态、日志、配置与 WebSocket', async () => {
    await mountHost()

    await ctx.init()

    expect(ctx.taskId.value).toBe(42)
    expect(mocks.getTaskDetail).toHaveBeenCalledWith(42)
    expect(mocks.getExecutionStatus).toHaveBeenCalledWith(42)
    expect(mocks.getExecutionLogs).toHaveBeenCalledWith(42)
    expect(mocks.getVisibilityConfig).toHaveBeenCalledWith('task', 42)
    expect(mocks.connectWs).toHaveBeenCalledTimes(1)
    expect(ctx.taskInfo.value).toMatchObject({ task: { name: '任务A' } })
  })

  it('从项目环境配置生成环境选项并选中 test', async () => {
    await mountHost()

    await ctx.init()

    expect(ctx.envOptions.value).toEqual([
      { name: 'test', url: 'http://test', username: 'u' },
      { name: 'dev', url: 'http://dev', username: '' },
    ])
    expect(ctx.targetEnv.value).toBe('test')
  })

  it('无 test 环境时回退第一个可用环境', async () => {
    mocks.getProjectDetail.mockResolvedValue({
      code: 200,
      data: { web_env_configs: { uat: { url: 'http://uat' } } },
    })
    await mountHost()

    await ctx.init()

    expect(ctx.targetEnv.value).toBe('uat')
  })

  it('任务信息加载失败时提示且保持空值', async () => {
    mocks.getTaskDetail.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.init()

    expect(ElMessage.error).toHaveBeenCalledWith('加载任务信息失败')
    expect(ctx.taskInfo.value).toBeNull()
  })

  it('无项目信息时不请求项目详情', async () => {
    mocks.getTaskDetail.mockResolvedValue({ code: 200, data: { task: { id: 1, status: 0 } } })
    await mountHost()

    await ctx.init()

    expect(mocks.getProjectDetail).not.toHaveBeenCalled()
    expect(ctx.envOptions.value).toEqual([])
  })
})

describe('useTestExecution — 执行状态与日志', () => {
  it('状态接口 404 时回退任务状态映射', async () => {
    mocks.getExecutionStatus.mockRejectedValue({ response: { status: 404 } })
    mocks.getTaskDetail.mockResolvedValue({
      code: 200,
      data: { task: { id: 42, status: 2, project_id: 7 } },
    })
    await mountHost()

    await ctx.init()

    expect(ctx.executionStatus.value).toMatchObject({ status: 'completed' })
  })

  it('404 且无任务信息时先补拉任务详情', async () => {
    mocks.getTaskDetail
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValue({ code: 200, data: { task: { id: 42, status: 1 } } })
    mocks.getExecutionStatus.mockRejectedValue({ response: { status: 404 } })
    await mountHost()

    await ctx.init()

    expect(mocks.getTaskDetail).toHaveBeenCalledTimes(2)
    expect(ctx.executionStatus.value).toMatchObject({ status: 'running' })
  })

  it('日志加载成功写入列表，失败保持静默', async () => {
    await mountHost()

    await ctx.init()
    await flushPromises()
    expect(ctx.executionLogs.value).toHaveLength(1)
    expect(ctx.executionLogs.value[0].message).toBe('启动')

    mocks.getExecutionLogs.mockRejectedValue(new Error('boom'))
    await ctx.init()
    await flushPromises()
    expect(ctx.executionLogs.value).toHaveLength(1)
  })

  it('进度与状态展示按规则派生', async () => {
    await mountHost()

    ctx.executionStatus.value = { status: 'running', current_step: 1, total_steps: 3 }
    expect(ctx.progressPercentage.value).toBe(33)
    expect(ctx.progressStatus.value).toBe('')
    expect(ctx.statusText.value).toBe('执行中')
    expect(ctx.statusTagType.value).toBe('primary')

    ctx.executionStatus.value = { status: 'completed', current_step: 3, total_steps: 3 }
    expect(ctx.progressPercentage.value).toBe(100)
    expect(ctx.progressStatus.value).toBe('success')
    expect(ctx.statusTagType.value).toBe('success')

    ctx.executionStatus.value = { status: 'failed', current_step: 0, total_steps: 0 }
    expect(ctx.progressPercentage.value).toBe(0)
    expect(ctx.progressStatus.value).toBe('exception')
    expect(ctx.statusText.value).toBe('执行失败')

    ctx.executionStatus.value = null
    expect(ctx.statusText.value).toBe('未知状态')
  })

  it('步骤状态与时间轴映射', () => {
    expect(ctx.getStepStatusType('passed')).toBe('success')
    expect(ctx.getStepStatusType('failed')).toBe('danger')
    expect(ctx.getStepStatusType('blocked')).toBe('warning')
    expect(ctx.getStepStatusType('unknown')).toBe('info')

    expect(ctx.getStepStatusText('passed')).toBe('通过')
    expect(ctx.getStepStatusText('blocked')).toBe('阻塞')
    expect(ctx.getStepStatusText('other')).toBe('other')

    expect(ctx.getTimelineItemType('passed')).toBe('success')
    expect(ctx.getTimelineItemType('other')).toBe('primary')

    expect(ctx.getTimelineIcon('passed')).toBe(CircleCheck)
    expect(ctx.getTimelineIcon('failed')).toBe(CircleClose)
    expect(ctx.getTimelineIcon('running')).toBe(Loading)
    expect(ctx.getTimelineIcon('blocked')).toBe(Warning)
    expect(ctx.getTimelineIcon('other')).toBeUndefined()
  })

  it('时间格式化', () => {
    expect(ctx.formatTime(65)).toBe('1分5秒')
    expect(ctx.formatLogTime('2026-11-13T10:00:00Z')).toBeTruthy()
  })
})

describe('useTestExecution — 截图与设备', () => {
  it('切换步骤加载截图并复用 last step', async () => {
    await mountHost()
    ctx.executionSteps.value = [
      { status: 'passed', action: 'a', case_id: 5 },
      { status: 'failed', action: 'b', case_id: 6 },
    ]

    ctx.selectStep(1)
    await flushPromises()

    expect(ctx.currentStepIndex.value).toBe(1)
    expect(mocks.getStepScreenshot).toHaveBeenLastCalledWith(42, 6, 2, 'after')
    expect(ctx.currentScreenshot.value).toContain('blob:')
  })

  it('切换截图类型触发重新加载', async () => {
    await mountHost()
    ctx.executionSteps.value = [{ status: 'passed', action: 'a', case_id: 5 }]
    await flushPromises()

    ctx.screenshotType.value = 'before'
    await flushPromises()

    expect(mocks.getStepScreenshot).toHaveBeenLastCalledWith(42, 5, 1, 'before')
  })

  it('截图加载失败清空地址', async () => {
    mocks.getStepScreenshot.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.executionSteps.value = [{ status: 'passed', action: 'a' }]

    ctx.selectStep(0)
    await flushPromises()

    expect(ctx.currentScreenshot.value).toBe('')
  })

  it('设备列表加载成功与失败均复位 loading', async () => {
    await mountHost()

    await ctx.loadConnectedDevices()
    expect(ctx.connectedDevices.value).toHaveLength(1)
    expect(ctx.loadingDevices.value).toBe(false)

    mocks.getConnectedDevices.mockRejectedValue(new Error('boom'))
    await ctx.loadConnectedDevices()
    expect(ctx.connectedDevices.value).toHaveLength(1)
    expect(ctx.loadingDevices.value).toBe(false)
  })
})

describe('useTestExecution — 配置保存与导航', () => {
  it('保存可见性配置解析分辨率并关闭弹窗', async () => {
    await mountHost()
    ctx.showConfigDialog.value = true
    ctx.videoResolution.value = '1920x1080'
    ctx.visibilityConfig.value = { headless: false, recordVideo: true, videoFps: 45 }

    await ctx.saveVisibilityConfig()

    expect(mocks.updateVisibilityConfig).toHaveBeenCalledWith(
      'task',
      {
        headless: false,
        recordVideo: true,
        videoResolution: [1920, 1080],
        videoFps: 45,
      },
      42
    )
    expect(ElMessage.success).toHaveBeenCalledWith('配置已保存')
    expect(ctx.showConfigDialog.value).toBe(false)
    expect(ctx.saveConfigLoading.value).toBe(false)
  })

  it('保存失败展示错误信息', async () => {
    mocks.updateVisibilityConfig.mockResolvedValue({ code: 500, message: '权限不足' })
    await mountHost()

    await ctx.saveVisibilityConfig()

    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
    expect(ctx.showConfigDialog.value).toBe(false)
  })

  it('保存异常走兜底提示', async () => {
    mocks.updateVisibilityConfig.mockRejectedValue(new Error('network'))
    await mountHost()

    await ctx.saveVisibilityConfig()

    expect(ElMessage.error).toHaveBeenCalledWith('保存配置失败')
    expect(ctx.saveConfigLoading.value).toBe(false)
  })

  it('加载可见性配置写回响应式字段', async () => {
    await mountHost()

    await ctx.init()
    await flushPromises()

    expect(ctx.visibilityConfig.value).toEqual({
      headless: false,
      recordVideo: true,
      videoFps: 45,
    })
    expect(ctx.videoResolution.value).toBe('1920x1080')
  })

  it('导航按项目 ID 跳转任务列表与测试点管理', async () => {
    await mountHost()
    ctx.taskInfo.value = { task: { project_id: 7 } }

    ctx.goToTaskList()
    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/7')

    ctx.goToTestPointManagement()
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: { projectId: '7' },
    })
  })

  it('无项目时回退项目首页与无参测试点页', async () => {
    await mountHost()
    ctx.taskInfo.value = null
    mocks.route.query = {}

    ctx.goBack()
    expect(mocks.push).toHaveBeenCalledWith('/home/project')

    ctx.goToTestPointManagement()
    expect(mocks.push).toHaveBeenCalledWith('/home/case/test-point-management')
  })

  it('路由 query 可补充项目 ID', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.taskInfo.value = null

    ctx.goToTaskList()

    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/9')
  })
})
