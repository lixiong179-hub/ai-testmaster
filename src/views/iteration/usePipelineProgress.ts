import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { TagType } from '@/types/element-plus'
import {
  pipelineApi,
  type PipelineRun,
  type PipelineSummary,
  type InferredSummary,
  type ArtifactDetail,
} from '@/api/pipeline'

/** WebSocket 推送的 Pipeline 进度消息格式 */
interface PipelineProgressMessage {
  type: 'pipeline_progress'
  run_id: number
  step_name: string
  status: string
  progress: number
  pipeline_status: string
}

/** Pipeline 终态集合，收到终态后断开 WebSocket */
const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled']

export function usePipelineProgress() {
  const route = useRoute()
  const router = useRouter()

  const runId = computed(() => Number(route.params.runId))
  const runData = ref<PipelineRun | null>(null)
  const loading = ref(false)
  const initialLoading = ref(true)
  const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const showConfirmDialog = ref(false)

  /** WebSocket 连接实例 */
  let wsConnection: WebSocket | null = null
  /** WebSocket 是否由用户主动断开（组件卸载时），阻止自动重连 */
  let wsIntentionalClose = false
  /** WebSocket 重连退避计数 */
  let wsReconnectAttempts = 0
  const WS_MAX_RECONNECT_ATTEMPTS = 3
  const WS_RECONNECT_BASE_DELAY = 2000
  /** WebSocket 是否已连接（连接后停止轮询） */
  const wsConnected = ref(false)

  /** Pipeline 运行摘要 */
  const pipelineSummary = ref<PipelineSummary | null>(null)
  /** AI 反推业务摘要 */
  const inferredSummary = ref<InferredSummary | null>(null)
  /** 摘要加载状态 */
  const summaryLoading = ref(false)

  /** 当前展开的 artifact 详情 */
  const expandedArtifactId = ref<number | null>(null)
  /** artifact 详情数据 */
  const artifactDetail = ref<ArtifactDetail | null>(null)
  /** artifact 详情加载状态 */
  const artifactDetailLoading = ref(false)

  const isPolling = computed(
    () => runData.value?.status === 'running' || runData.value?.status === 'pending'
  )

  const confirmReason = computed(() => {
    if (runData.value?.pause_payload && typeof runData.value.pause_payload === 'object') {
      return ((runData.value.pause_payload as Record<string, unknown>).reason as string) || ''
    }
    return runData.value?.error || 'Pipeline 需要人工确认后继续'
  })

  const confirmSchema = computed(() => {
    if (runData.value?.pause_payload && typeof runData.value.pause_payload === 'object') {
      const schema = (runData.value.pause_payload as Record<string, unknown>).schema
      if (schema && typeof schema === 'object') {
        return schema as {
          fields: Array<{
            key: string
            label: string
            type: 'select' | 'textarea' | 'number' | 'text'
            options?: Array<{ label: string; value: string }>
            placeholder?: string
            required?: boolean
          }>
        }
      }
    }
    return null
  })

  const stepNameMap: Record<string, string> = {
    signal_gatherer: '信号采集',
    testpoint_alignment: '测试点对齐',
    case_generation: '用例生成',
    quality_gate: '质量门禁',
    persist: '用例持久化',
  }

  const artifactKindMap: Record<string, string> = {
    raw_signals: '原始信号',
    aligned_testpoints: '对齐测试点',
    generated_cases: '生成用例',
    quality_scores: '质量评分',
  }

  const runStatusType = computed<TagType>(() => {
    const map: Record<string, TagType> = {
      pending: 'info',
      running: 'primary',
      completed: 'success',
      failed: 'danger',
      waiting_for_user: 'warning',
      cancelled: 'info',
    }
    return map[runData.value?.status || ''] || 'info'
  })

  const runStatusText = computed(() => {
    const map: Record<string, string> = {
      pending: '等待中',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      waiting_for_user: '等待确认',
      cancelled: '已取消',
    }
    return map[runData.value?.status || ''] || runData.value?.status || ''
  })

  const duration = computed(() => {
    if (!runData.value?.started_at) return '—'
    const start = new Date(runData.value.started_at).getTime()
    const end = runData.value.finished_at
      ? new Date(runData.value.finished_at).getTime()
      : Date.now()
    return formatDuration(end - start)
  })

  function stepStatusType(status: string): TagType {
    const map: Record<string, TagType> = {
      pending: 'info',
      running: 'primary',
      done: 'success',
      failed: 'danger',
      skipped: 'info',
      degraded: 'warning',
    }
    return map[status] || 'info'
  }

  function stepStatusText(status: string): string {
    const map: Record<string, string> = {
      pending: '等待中',
      running: '运行中',
      done: '已完成',
      failed: '失败',
      skipped: '已跳过',
      degraded: '降级完成',
    }
    return map[status] || status
  }

  function stepDuration(step: { started_at: string | null; finished_at: string | null }): string {
    if (!step.started_at) return '—'
    const start = new Date(step.started_at).getTime()
    const end = step.finished_at ? new Date(step.finished_at).getTime() : Date.now()
    return formatDuration(end - start)
  }

  function confidenceColor(confidence: number): string {
    return confidence >= 0.85 ? '#67c23a' : confidence >= 0.7 ? '#e6a23c' : '#f56c6c'
  }

  function formatTime(time: string | null | undefined): string {
    if (!time) return '—'
    try {
      return new Date(time).toLocaleString('zh-CN')
    } catch {
      return time
    }
  }

  function formatDuration(ms: number): string {
    if (ms < 0 || isNaN(ms)) return '—'
    const seconds = Math.floor(ms / 1000)
    if (seconds < 60) return `${seconds}秒`
    const minutes = Math.floor(seconds / 60)
    const remainSeconds = seconds % 60
    if (minutes < 60) return `${minutes}分${remainSeconds}秒`
    const hours = Math.floor(minutes / 60)
    const remainMinutes = minutes % 60
    return `${hours}时${remainMinutes}分`
  }

  async function fetchRunData(isInitial = false) {
    if (!runId.value) return
    if (isInitial) initialLoading.value = true
    loading.value = true
    try {
      const res = await pipelineApi.getPipelineRun(runId.value)
      runData.value = res.data
      if (res.data?.status === 'completed') loadPipelineSummary()
      if (!isPolling.value) stopPolling()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取 Pipeline 状态失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false
      initialLoading.value = false
    }
  }

  /** Pipeline 完成后自动加载运行摘要与AI推断摘要 */
  async function loadPipelineSummary(): Promise<void> {
    if (!runData.value || runData.value.status !== 'completed') return
    if (pipelineSummary.value) return
    summaryLoading.value = true
    try {
      const [summaryRes, inferredRes] = await Promise.all([
        pipelineApi.getPipelineSummary(runData.value.id),
        pipelineApi.getInferredSummary(runData.value.id),
      ])
      pipelineSummary.value = summaryRes.data ?? null
      inferredSummary.value = inferredRes.data ?? null
    } catch (error: unknown) {
      ElMessage.error(error instanceof Error ? error.message : '加载Pipeline摘要失败')
    } finally {
      summaryLoading.value = false
    }
  }

  /** 用户补全信号后保存并刷新 */
  async function handleSupplementSignals(
    signals: import('@/api/pipeline').SupplementSignalsRequest
  ): Promise<void> {
    if (!runData.value) return
    try {
      await pipelineApi.supplementSignals(runData.value.id, signals)
      ElMessage.success('信号补全成功')
      await fetchRunData()
    } catch (error: unknown) {
      ElMessage.error(error instanceof Error ? error.message : '补全信号失败')
    }
  }

  /** 点击 artifact 行展开/收起详情面板 */
  async function toggleArtifactDetail(artifactId: number): Promise<void> {
    if (expandedArtifactId.value === artifactId) {
      expandedArtifactId.value = null
      artifactDetail.value = null
      return
    }
    if (!runData.value) return
    expandedArtifactId.value = artifactId
    artifactDetailLoading.value = true
    try {
      const res = await pipelineApi.getArtifactDetail(runData.value.id, artifactId)
      artifactDetail.value = res.data ?? null
    } catch (error: unknown) {
      ElMessage.error(error instanceof Error ? error.message : '获取产物详情失败')
      artifactDetail.value = null
      expandedArtifactId.value = null
    } finally {
      artifactDetailLoading.value = false
    }
  }

  async function handleResume() {
    if (runData.value?.status === 'waiting_for_user') showConfirmDialog.value = true
    else doResume({})
  }

  function handleConfirmResume(payload: Record<string, unknown>) {
    showConfirmDialog.value = false
    doResume(payload)
  }

  async function doResume(payload: Record<string, unknown>) {
    if (!runData.value) return
    try {
      await pipelineApi.resumePipeline(
        runData.value.id,
        Object.keys(payload).length > 0 ? payload : undefined
      )
      ElMessage.success('Pipeline 已恢复')
      await fetchRunData()
      connectWs()
      startPolling()
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'status' in e && (e as { status: number }).status === 409)
        ElMessage.warning('Pipeline 状态已变更，请刷新')
      else ElMessage.error('恢复失败')
    }
  }

  /** 连接 WebSocket 接收 Pipeline 进度推送，连接成功后自动停止轮询 */
  function connectWs(): void {
    if (!runId.value) return
    const token = localStorage.getItem('token')
    if (!token) return

    wsIntentionalClose = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/api/v1/ws/pipeline/${runId.value}?token=${token}`

    try {
      wsConnection = new WebSocket(wsUrl)

      wsConnection.onopen = () => {
        wsConnected.value = true
        wsReconnectAttempts = 0
        stopPolling()
      }

      wsConnection.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data as string) as PipelineProgressMessage
          if (data.type === 'pipeline_progress') {
            if (!loading.value) fetchRunData()
            if (TERMINAL_STATUSES.includes(data.pipeline_status)) {
              disconnectWs()
            }
          }
        } catch {
          // 非 JSON 消息或心跳响应，忽略
        }
      }

      wsConnection.onclose = () => {
        wsConnected.value = false
        wsConnection = null
        if (wsIntentionalClose) return
        if (wsReconnectAttempts < WS_MAX_RECONNECT_ATTEMPTS) {
          const delay = WS_RECONNECT_BASE_DELAY * Math.pow(2, wsReconnectAttempts)
          wsReconnectAttempts++
          setTimeout(() => connectWs(), delay)
        } else {
          startPolling()
        }
      }

      wsConnection.onerror = () => {
        wsConnected.value = false
      }
    } catch {
      if (isPolling.value) startPolling()
    }
  }

  /** 断开 WebSocket 连接 */
  function disconnectWs(): void {
    wsIntentionalClose = true
    if (wsConnection) {
      wsConnection.close()
      wsConnection = null
    }
    wsConnected.value = false
  }

  function startPolling() {
    stopPolling()
    if (isPolling.value && !wsConnected.value) pollingTimer.value = setInterval(fetchRunData, 5000)
  }
  function stopPolling() {
    if (pollingTimer.value) {
      clearInterval(pollingTimer.value)
      pollingTimer.value = null
    }
  }
  function goBack() {
    router.back()
  }

  onMounted(async () => {
    await fetchRunData(true)
    connectWs()
    startPolling()
  })
  onUnmounted(() => {
    disconnectWs()
    stopPolling()
  })

  return {
    runData,
    loading,
    initialLoading,
    isPolling,
    showConfirmDialog,
    confirmReason,
    confirmSchema,
    stepNameMap,
    artifactKindMap,
    runStatusType,
    runStatusText,
    duration,
    stepStatusType,
    stepStatusText,
    stepDuration,
    confidenceColor,
    formatTime,
    fetchRunData,
    handleResume,
    handleConfirmResume,
    goBack,
    pipelineSummary,
    inferredSummary,
    summaryLoading,
    loadPipelineSummary,
    handleSupplementSignals,
    expandedArtifactId,
    artifactDetail,
    artifactDetailLoading,
    toggleArtifactDetail,
  }
}
