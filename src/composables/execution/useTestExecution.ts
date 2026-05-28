import { type InjectionKey, inject, provide, ref, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose, Loading, Warning } from '@element-plus/icons-vue'
import type { TagType, ProgressStatus } from '@/types/element-plus'
import {
  getExecutionStatus,
  getExecutionLogs,
  getStepScreenshot,
  getVisibilityConfig,
  updateVisibilityConfig,
  getConnectedDevices,
} from '@/api/testExecution'
import type { ExecutionMode } from '@/api/testExecution'
import testTaskApi from '@/api/testTask'
import ProjectAPI from '@/api/project'
import { unwrapApiResponse } from '@/utils/api'
import { useExecutionControl } from '@/composables/useExecutionControl'
import { useExecutionWebSocket } from '@/composables/useExecutionWebSocket'
import { useVideoReplay } from '@/composables/useVideoReplay'
import {
  useFailureAnalysis,
  ISSUE_TYPE_LABELS as _ISSUE_TYPE_LABELS,
  ISSUE_TYPE_COLORS as _ISSUE_TYPE_COLORS,
} from '@/composables/useFailureAnalysis'

export { _ISSUE_TYPE_LABELS as ISSUE_TYPE_LABELS, _ISSUE_TYPE_COLORS as ISSUE_TYPE_COLORS }

export type TestExecutionContext = ReturnType<typeof createTestExecutionContext>
export const TEST_EXECUTION_KEY: InjectionKey<TestExecutionContext> = Symbol('testExecution')

function createTestExecutionContext() {
  const route = useRoute()
  const router = useRouter()
  const taskId = computed(() => Number(route.params.taskId))

  const taskInfo = ref<any>(null)
  const executionStatus = ref<any>(null)
  const executionSteps = ref<any[]>([])
  const executionLogs = ref<any[]>([])
  const currentStepIndex = ref(0)
  const currentScreenshot = ref('')
  const videoUrl = ref('')
  const saveConfigLoading = ref(false)
  const showConfigDialog = ref(false)
  const showScreenshotFullscreen = ref(false)
  const viewMode = ref<'list' | 'timeline'>('list')
  const screenshotType = ref<'before' | 'after'>('after')
  const activeTab = ref('logs')
  const logsContainer = ref<HTMLElement>()
  const visibilityConfig = ref({ headless: true, recordVideo: false, videoFps: 30 })
  const videoResolution = ref('1280x720')
  const targetEnv = ref('test')
  const autoInitEnabled = ref(true)
  const executionMode = ref<ExecutionMode>('smart')
  const mobileDeviceId = ref('')
  const connectedDevices = ref<Array<{ udid: string; model?: string; state: string }>>([])
  const loadingDevices = ref(false)
  const useMcpMode = ref(true)
  const envOptions = ref<Array<{ name: string; url: string; username?: string }>>([])
  const videoPlayer = ref<HTMLVideoElement>()

  const getTaskPayload = () => taskInfo.value?.task || taskInfo.value || null

  const syncTaskInfoStatus = (status: number) => {
    if (!taskInfo.value) return
    if (taskInfo.value?.task) {
      taskInfo.value = { ...taskInfo.value, task: { ...taskInfo.value.task, status } }
      return
    }
    taskInfo.value = { ...taskInfo.value, status }
  }

  const buildExecutionStatusFallback = () => {
    const taskStatus = Number(getTaskPayload()?.status)
    const statusMap: Record<number, string> = {
      0: 'pending',
      1: 'running',
      2: 'completed',
      3: 'failed',
      4: 'stopped',
    }
    const fallbackStatus = statusMap[taskStatus]
    if (!fallbackStatus) return null
    return {
      status: fallbackStatus,
      current_step: Number(executionStatus.value?.current_step || 0),
      total_steps: Number(executionStatus.value?.total_steps || 0),
      estimated_time_remaining: executionStatus.value?.estimated_time_remaining,
    }
  }

  const loadTaskInfo = async () => {
    try {
      const res = await testTaskApi.getTaskDetail(taskId.value)
      const body = unwrapApiResponse<any>(res)
      if (body.code === 200 && body.data) {
        taskInfo.value = body.data
        const taskData = body.data.task || body.data
        const projectId = taskData?.project_id
        if (projectId) {
          const projectRes = await ProjectAPI.getProjectDetail(projectId)
          const projectBody = unwrapApiResponse<any>(projectRes)
          if (projectBody.code === 200 && projectBody.data) {
            const webEnvConfigs = projectBody.data?.web_env_configs
            if (webEnvConfigs && typeof webEnvConfigs === 'object') {
              const options = Object.entries(webEnvConfigs)
                .map(([name, cfg]: [string, any]) => ({
                  name,
                  url: cfg?.url || '',
                  username: cfg?.username || '',
                }))
                .filter((opt) => opt.url)
              envOptions.value = options
              if (options.some((o) => o.name === 'test')) targetEnv.value = 'test'
              else if (options.length > 0) targetEnv.value = options[0].name
            }
          }
        }
      }
      return taskInfo.value
    } catch (error) {
      console.error('加载任务信息失败:', error)
      ElMessage.error('加载任务信息失败')
      return null
    }
  }

  const loadExecutionStatus = async () => {
    try {
      const res = await getExecutionStatus(taskId.value)
      const body = unwrapApiResponse<any>(res)
      if (body.code === 200 && body.data) executionStatus.value = body.data
    } catch (error: any) {
      if (error?.response?.status === 404) {
        if (!getTaskPayload()) await loadTaskInfo()
        const fallbackStatus = buildExecutionStatusFallback()
        if (fallbackStatus) executionStatus.value = fallbackStatus
        return
      }
      console.error('加载执行状态失败:', error)
    }
  }

  const loadExecutionLogs = async () => {
    try {
      const res = await getExecutionLogs(taskId.value)
      const body = unwrapApiResponse<any>(res)
      if (body.code === 200) {
        executionLogs.value = body.data?.logs || []
        nextTick(() => scrollToBottom())
      }
    } catch (error) {
      console.error('加载执行日志失败:', error)
    }
  }

  const currentStep = computed(() => executionSteps.value[currentStepIndex.value])

  const loadStepScreenshot = async () => {
    if (!currentStep.value) return
    try {
      const res = await getStepScreenshot(
        taskId.value,
        currentStep.value.case_id || 0,
        currentStepIndex.value + 1,
        screenshotType.value
      )
      if (currentScreenshot.value && currentScreenshot.value.startsWith('blob:'))
        URL.revokeObjectURL(currentScreenshot.value)
      currentScreenshot.value = URL.createObjectURL(res.data)
    } catch (error) {
      console.error('加载截图失败:', error)
      if (currentScreenshot.value && currentScreenshot.value.startsWith('blob:'))
        URL.revokeObjectURL(currentScreenshot.value)
      currentScreenshot.value = ''
    }
  }

  const loadConnectedDevices = async () => {
    loadingDevices.value = true
    try {
      const res = await getConnectedDevices()
      const body = unwrapApiResponse<any[]>(res)
      if (body.code === 200) connectedDevices.value = body.data || []
    } catch (error) {
      console.error('获取设备列表失败:', error)
    } finally {
      loadingDevices.value = false
    }
  }

  const scrollToBottom = () => {
    if (logsContainer.value) logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }

  const { connectWebSocketForRealtimeUpdate } = useExecutionWebSocket({
    taskId: () => taskId.value,
    executionSteps,
    currentStepIndex,
    executionLogs,
    executionStatus,
    loadStepScreenshot,
    scrollToBottom,
  })
  const { controlLoading, startExecution, pauseExecution, resumeExecution, stopExecution } =
    useExecutionControl({
      taskId: () => taskId.value,
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
      connectWebSocketForRealtimeUpdate: () => connectWebSocketForRealtimeUpdate(),
    })
  const {
    isVideoPlaying,
    videoCurrentTime,
    videoDuration,
    replaySpeed,
    toggleVideoPlay,
    seekVideo,
    onVideoTimeChange,
    startReplay,
    pauseReplay,
    stopReplay,
  } = useVideoReplay({ taskId: () => taskId.value, taskInfo, videoPlayer })
  const {
    failureAnalysisMap,
    analysisLoading,
    issueTypeMap,
    handleAnalyzeFailure,
    handleCorrectCase,
  } = useFailureAnalysis({ executionStatus })

  const progressPercentage = computed(() => {
    if (!executionStatus.value) return 0
    const cs = Number(executionStatus.value.current_step || 0)
    const ts = Number(executionStatus.value.total_steps || 0)
    return ts <= 0 ? 0 : Math.round((cs / ts) * 100)
  })
  const progressStatus = computed<ProgressStatus>(() => {
    const s = executionStatus.value?.status
    if (s === 'completed') return 'success'
    if (s === 'failed') return 'exception'
    return ''
  })
  const statusText = computed(() => {
    const m: Record<string, string> = {
      pending: '等待执行',
      running: '执行中',
      paused: '已暂停',
      completed: '执行完成',
      failed: '执行失败',
      stopped: '已停止',
    }
    return m[executionStatus.value?.status] || '未知状态'
  })
  const statusTagType = computed<TagType>(() => {
    const m: Record<string, TagType> = {
      pending: 'info',
      running: 'primary',
      paused: 'warning',
      completed: 'success',
      failed: 'danger',
      stopped: 'info',
    }
    return m[executionStatus.value?.status] || 'info'
  })

  const selectStep = (index: number) => {
    currentStepIndex.value = index
  }
  const getStepStatusType = (status: string): TagType => {
    const m: Record<string, TagType> = {
      passed: 'success',
      failed: 'danger',
      running: 'primary',
      pending: 'info',
      blocked: 'warning',
    }
    return m[status] || 'info'
  }
  const getStepStatusText = (status: string) => {
    const m: Record<string, string> = {
      passed: '通过',
      failed: '失败',
      running: '执行中',
      pending: '等待',
      blocked: '阻塞',
    }
    return m[status] || status
  }
  const getTimelineItemType = (status: string): TagType => {
    const m: Record<string, TagType> = {
      passed: 'success',
      failed: 'danger',
      running: 'primary',
      blocked: 'warning',
    }
    return m[status] || 'primary'
  }
  const getTimelineIcon = (status: string) => {
    if (status === 'passed') return CircleCheck
    if (status === 'failed') return CircleClose
    if (status === 'running') return Loading
    if (status === 'blocked') return Warning
    return undefined
  }
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}分${secs}秒`
  }
  const formatLogTime = (timestamp: string) => new Date(timestamp).toLocaleTimeString('zh-CN')

  const currentProjectId = computed(() => {
    const td = taskInfo.value?.task || taskInfo.value
    return Number(td?.project_id || route.query.project_id || 0)
  })
  const goBack = () => goToTaskList()
  const goToTaskList = () => {
    if (currentProjectId.value) router.push(`/home/task/list/${currentProjectId.value}`)
    else router.push('/home/project')
  }
  const goToTestPointManagement = () => {
    if (currentProjectId.value)
      router.push({
        path: '/home/case/test-point-management',
        query: { projectId: String(currentProjectId.value) },
      })
    else router.push('/home/case/test-point-management')
  }

  const saveVisibilityConfig = async () => {
    saveConfigLoading.value = true
    try {
      const [width, height] = videoResolution.value.split('x').map(Number)
      const res = await updateVisibilityConfig(
        'task',
        {
          headless: visibilityConfig.value.headless,
          recordVideo: visibilityConfig.value.recordVideo,
          videoResolution: [width, height],
          videoFps: visibilityConfig.value.videoFps,
        },
        taskId.value
      )
      const body = unwrapApiResponse<any>(res)
      if (body.code === 200) {
        ElMessage.success('配置已保存')
        showConfigDialog.value = false
      } else ElMessage.error(body.message || '保存失败')
    } catch (error) {
      console.error('保存配置失败:', error)
      ElMessage.error('保存配置失败')
    } finally {
      saveConfigLoading.value = false
    }
  }

  const loadVisibilityConfig = async () => {
    try {
      const res = await getVisibilityConfig('task', taskId.value)
      const body = unwrapApiResponse<any>(res)
      if (body.code === 200 && body.data) {
        const config = body.data
        visibilityConfig.value.headless = config.headless
        visibilityConfig.value.recordVideo = config.record_video
        visibilityConfig.value.videoFps = config.video_fps
        if (config.video_resolution)
          videoResolution.value = `${config.video_resolution[0]}x${config.video_resolution[1]}`
      }
    } catch (error) {
      console.error('加载配置失败:', error)
    }
  }

  watch(screenshotType, () => loadStepScreenshot())
  watch(currentStepIndex, () => loadStepScreenshot())

  const init = async () => {
    await loadTaskInfo()
    await loadExecutionStatus()
    loadExecutionLogs()
    loadVisibilityConfig()
    connectWebSocketForRealtimeUpdate()
  }

  return {
    taskId,
    taskInfo,
    executionStatus,
    executionSteps,
    executionLogs,
    currentStepIndex,
    currentScreenshot,
    videoUrl,
    saveConfigLoading,
    showConfigDialog,
    showScreenshotFullscreen,
    viewMode,
    screenshotType,
    activeTab,
    logsContainer,
    visibilityConfig,
    videoResolution,
    targetEnv,
    autoInitEnabled,
    executionMode,
    mobileDeviceId,
    connectedDevices,
    loadingDevices,
    useMcpMode,
    envOptions,
    videoPlayer,
    currentStep,
    progressPercentage,
    progressStatus,
    statusText,
    statusTagType,
    controlLoading,
    isVideoPlaying,
    videoCurrentTime,
    videoDuration,
    replaySpeed,
    failureAnalysisMap,
    analysisLoading,
    issueTypeMap,
    selectStep,
    getStepStatusType,
    getStepStatusText,
    getTimelineItemType,
    getTimelineIcon,
    formatTime,
    formatLogTime,
    goBack,
    goToTaskList,
    goToTestPointManagement,
    startExecution,
    pauseExecution,
    resumeExecution,
    stopExecution,
    toggleVideoPlay,
    seekVideo,
    onVideoTimeChange,
    startReplay,
    pauseReplay,
    stopReplay,
    handleAnalyzeFailure,
    handleCorrectCase,
    loadConnectedDevices,
    saveVisibilityConfig,
    init,
    ISSUE_TYPE_LABELS: _ISSUE_TYPE_LABELS,
    ISSUE_TYPE_COLORS: _ISSUE_TYPE_COLORS,
  }
}

export function provideTestExecution() {
  const ctx = createTestExecutionContext()
  provide(TEST_EXECUTION_KEY, ctx)
  return ctx
}

export function useTestExecution() {
  const ctx = inject(TEST_EXECUTION_KEY)
  if (!ctx) throw new Error('TestExecution context not provided')
  return ctx
}
