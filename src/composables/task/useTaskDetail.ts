import { type InjectionKey, inject, provide, ref, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { TagType, ProgressStatus } from '@/types/element-plus'
import { useTaskStore } from '@/store/task'
import { wsClient } from '@/utils/websocket'
import { getConnectedDevices } from '@/api/testExecution'

export type TaskDetailContext = ReturnType<typeof createTaskDetailContext>
export const TASK_DETAIL_KEY: InjectionKey<TaskDetailContext> = Symbol('taskDetail')

function createTaskDetailContext() {
  const route = useRoute()
  const taskStore = useTaskStore()

  const taskId = computed(() => Number(route.params.taskId) || 0)
  const projectId = computed(() => Number(route.query.project_id) || 0)
  const loading = computed(() => taskStore.loading)
  const actionLoading = ref(false)
  const executionMode = ref<
    'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart'
  >('smart')
  const mobileDeviceId = ref('')
  const connectedDevices = ref<Array<{ udid: string; model?: string; state: string }>>([])
  const loadingDevices = ref(false)
  const activeNames = ref(['results'])
  const logActiveNames = ref(['logs'])
  const autoScroll = ref(true)
  const scrollbarRef = ref<any>(null)
  const logContainerRef = ref<HTMLElement | null>(null)
  const logDialogVisible = ref(false)
  const currentCaseLog = ref('')
  const screenshotDialogVisible = ref(false)
  const currentScreenshot = ref('')
  const errorDialogVisible = ref(false)
  const currentError = ref('')
  let pollTimer: number | null = null

  const taskDetail = computed(() => taskStore.taskDetail)
  const taskResults = computed(() => taskStore.taskResults)
  const executionLogs = computed(() => taskStore.executionLogs)
  const taskPassRate = computed(() => {
    if (!taskDetail.value) return 0
    const { total_count, success_count } = taskDetail.value
    return total_count > 0 ? Math.round((success_count / total_count) * 100) : 0
  })

  const taskStatusText = (status: number) => taskStore.taskStatusText(status)
  const taskStatusColor = (status: number): TagType => taskStore.taskStatusColor(status)
  const execStatusText = (status: number) => taskStore.execStatusText(status)
  const execStatusColor = (status: number): TagType => taskStore.execStatusColor(status)
  const logStatusText = (status: number) => taskStore.logStatusText(status)
  const logStatusColor = (status: number): TagType => taskStore.logStatusColor(status)

  const getLogItemClass = (status: number) => {
    if (status === 3) return 'log-warning'
    if (status === 2) return 'log-error'
    if (status === 1) return 'log-success'
    return ''
  }

  const getProgressColor = (progress: number) => {
    if (progress < 30) return '#409EFF'
    if (progress < 70) return '#E6A23C'
    return '#67C23A'
  }

  const getProgressStatus = (): ProgressStatus | undefined => {
    if (!taskDetail.value) return undefined
    if (taskDetail.value.status === 3) return 'exception'
    if (taskDetail.value.status === 2 && taskDetail.value.fail_count === 0) return 'success'
    return undefined
  }

  const formatTime = (timestamp: string) => {
    if (!timestamp) return '-'
    return new Date(timestamp).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const fetchTaskDetail = async () => {
    try {
      await taskStore.fetchTaskDetail(taskId.value, projectId.value)
    } catch (error: any) {
      ElMessage.error(error.message || '获取任务详情失败')
    }
  }

  const fetchTaskResults = async () => {
    try {
      await taskStore.fetchTaskResults(taskId.value, projectId.value)
    } catch (error: any) {
      console.error('获取执行结果失败:', error)
    }
  }

  const refreshAll = async () => {
    await Promise.all([fetchTaskDetail(), fetchTaskResults()])
  }

  const loadConnectedDevices = async () => {
    loadingDevices.value = true
    try {
      const res = await getConnectedDevices()
      if (res.data?.code === 200) connectedDevices.value = res.data.data || []
    } catch (error) {
      console.error('获取设备列表失败:', error)
    } finally {
      loadingDevices.value = false
    }
  }

  const startTask = async () => {
    if (executionMode.value.startsWith('mobile_') && !mobileDeviceId.value) {
      ElMessage.warning('移动端模式请先选择目标设备')
      return
    }
    try {
      actionLoading.value = true
      await taskStore.startTask(
        taskId.value,
        projectId.value,
        executionMode.value,
        executionMode.value.startsWith('mobile_') ? mobileDeviceId.value : undefined
      )
      ElMessage.success('任务已启动')
      await fetchTaskDetail()
      startPolling()
    } catch (error: any) {
      ElMessage.error(error.message || '启动任务失败')
    } finally {
      actionLoading.value = false
    }
  }

  const stopTask = async () => {
    try {
      await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      actionLoading.value = true
      await taskStore.stopTask(taskId.value, projectId.value)
      ElMessage.success('任务已停止')
      await fetchTaskDetail()
      stopPolling()
    } catch (error: any) {
      if (error !== 'cancel') ElMessage.error(error.message || '停止任务失败')
    } finally {
      actionLoading.value = false
    }
  }

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const exportResults = () => {
    if (taskResults.value.length === 0) {
      ElMessage.warning('暂无结果可导出')
      return
    }
    const results = taskResults.value.map((r: any) => ({
      case_no: r.case_no,
      case_id: r.case_id,
      exec_status: execStatusText(r.exec_status),
      exec_time: r.exec_time || '-',
      error_msg: r.error_msg || '',
    }))
    const csv = [
      ['用例编号', '用例ID', '执行状态', '执行时长', '错误信息'].join(','),
      ...results.map((r) =>
        [r.case_no, r.case_id, r.exec_status, r.exec_time, `"${r.error_msg}"`].join(',')
      ),
    ].join('\n')
    downloadFile(csv, `task_${taskId.value}_results.csv`, 'text/csv')
  }

  const viewCaseLog = (result: any) => {
    currentCaseLog.value = result.exec_log || '暂无日志'
    logDialogVisible.value = true
  }
  const copyLog = async () => {
    try {
      await navigator.clipboard.writeText(currentCaseLog.value)
      ElMessage.success('日志已复制到剪贴板')
    } catch {
      ElMessage.error('复制失败')
    }
  }
  const viewScreenshot = (result: any) => {
    if (result.screenshot_url) {
      currentScreenshot.value = result.screenshot_url
      screenshotDialogVisible.value = true
    } else ElMessage.warning('暂无截图')
  }
  const viewError = (result: any) => {
    currentError.value = result.error_msg || '暂无错误信息'
    errorDialogVisible.value = true
  }
  const clearLogs = () => taskStore.clearExecutionLogs()

  const exportLogs = () => {
    if (executionLogs.value.length === 0) {
      ElMessage.warning('暂无日志可导出')
      return
    }
    const logs = executionLogs.value
      .map(
        (log: any) =>
          `[${formatTime(log.timestamp)}] [${logStatusText(log.status)}] ${log.case_no ? `[${log.case_no}] ` : ''}${log.log}`
      )
      .join('\n')
    downloadFile(logs, `task_${taskId.value}_logs.txt`, 'text/plain')
  }

  const scrollToBottom = () => {
    if (autoScroll.value && logContainerRef.value)
      nextTick(() => {
        if (scrollbarRef.value) scrollbarRef.value.setScrollTop(logContainerRef.value!.scrollHeight)
      })
  }

  const startPolling = () => {
    if (pollTimer) return
    pollTimer = window.setInterval(async () => {
      await fetchTaskDetail()
      await fetchTaskResults()
      if (taskDetail.value && taskDetail.value.status !== 1) stopPolling()
    }, 3000)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  const handleWsMessage = (data: any) => {
    if (data.type === 'log')
      taskStore.addExecutionLog({
        task_id: taskId.value,
        case_id: data.case_id,
        case_no: data.case_no,
        status: data.status,
        log: data.log,
        timestamp: data.timestamp || new Date().toISOString(),
      })
    else if (data.type === 'progress')
      taskStore.updateExecutionProgress({
        task_id: taskId.value,
        progress: data.progress,
        success_count: data.success_count,
        fail_count: data.fail_count,
        current_case: data.current_case,
        total_cases: data.total_cases,
        timestamp: new Date().toISOString(),
      })
    else if (data.type === 'status') {
      taskStore.updateTaskStatus(taskId.value, data.status)
      if (data.status !== 1) stopPolling()
    }
  }

  watch(
    () => taskStore.executionLogs.length,
    () => scrollToBottom()
  )
  watch(
    () => taskDetail.value?.status,
    (s) => {
      if (s === 1) startPolling()
      else stopPolling()
    }
  )

  const init = async () => {
    taskStore.clearExecutionLogs()
    await fetchTaskDetail()
    await fetchTaskResults()
    if (taskDetail.value?.status === 1) startPolling()
    const token = localStorage.getItem('token')
    if (token) {
      wsClient.connect(taskId.value, projectId.value, token)
      wsClient.onMessage(handleWsMessage)
    }
  }

  const cleanup = () => {
    stopPolling()
    wsClient.offMessage(handleWsMessage)
    wsClient.disconnect()
    taskStore.clearExecutionLogs()
  }

  return {
    taskId,
    projectId,
    loading,
    actionLoading,
    executionMode,
    mobileDeviceId,
    connectedDevices,
    loadingDevices,
    activeNames,
    logActiveNames,
    autoScroll,
    scrollbarRef,
    logContainerRef,
    logDialogVisible,
    currentCaseLog,
    screenshotDialogVisible,
    currentScreenshot,
    errorDialogVisible,
    currentError,
    taskDetail,
    taskResults,
    executionLogs,
    taskPassRate,
    taskStatusText,
    taskStatusColor,
    execStatusText,
    execStatusColor,
    logStatusText,
    logStatusColor,
    getLogItemClass,
    getProgressColor,
    getProgressStatus,
    formatTime,
    fetchTaskDetail,
    fetchTaskResults,
    refreshAll,
    loadConnectedDevices,
    startTask,
    stopTask,
    exportResults,
    viewCaseLog,
    copyLog,
    viewScreenshot,
    viewError,
    clearLogs,
    exportLogs,
    init,
    cleanup,
  }
}

export function provideTaskDetail() {
  const ctx = createTaskDetailContext()
  provide(TASK_DETAIL_KEY, ctx)
  return ctx
}

export function useTaskDetail() {
  const ctx = inject(TASK_DETAIL_KEY)
  if (!ctx) throw new Error('TaskDetail context not provided')
  return ctx
}
