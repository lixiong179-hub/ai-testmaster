import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { pipelineApi, type PipelineRun } from '@/api/pipeline'

export function usePipelineProgress() {
  const route = useRoute()
  const router = useRouter()

  const runId = computed(() => Number(route.params.runId))
  const runData = ref<PipelineRun | null>(null)
  const loading = ref(false)
  const initialLoading = ref(true)
  const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const showConfirmDialog = ref(false)

  const isPolling = computed(() => runData.value?.status === 'running' || runData.value?.status === 'pending')

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
            key: string; label: string; type: 'select' | 'textarea' | 'number' | 'text'
            options?: Array<{ label: string; value: string }>; placeholder?: string; required?: boolean
          }>
        }
      }
    }
    return null
  })

  const stepNameMap: Record<string, string> = {
    signal_gatherer: '信号采集', testpoint_alignment: '测试点对齐',
    case_generation: '用例生成', quality_gate: '质量门禁', persist: '用例持久化',
  }

  const artifactKindMap: Record<string, string> = {
    raw_signals: '原始信号', aligned_testpoints: '对齐测试点',
    generated_cases: '生成用例', quality_scores: '质量评分',
  }

  const runStatusType = computed(() => {
    const map: Record<string, string> = { pending: 'info', running: '', completed: 'success', failed: 'danger', waiting_for_user: 'warning', cancelled: 'info' }
    return map[runData.value?.status || ''] || 'info'
  })

  const runStatusText = computed(() => {
    const map: Record<string, string> = { pending: '等待中', running: '运行中', completed: '已完成', failed: '失败', waiting_for_user: '等待确认', cancelled: '已取消' }
    return map[runData.value?.status || ''] || runData.value?.status || ''
  })

  const duration = computed(() => {
    if (!runData.value?.started_at) return '—'
    const start = new Date(runData.value.started_at).getTime()
    const end = runData.value.finished_at ? new Date(runData.value.finished_at).getTime() : Date.now()
    return formatDuration(end - start)
  })

  function stepStatusType(status: string): string {
    const map: Record<string, string> = { pending: 'info', running: '', done: 'success', failed: 'danger', skipped: 'info', degraded: 'warning' }
    return map[status] || 'info'
  }

  function stepStatusText(status: string): string {
    const map: Record<string, string> = { pending: '等待中', running: '运行中', done: '已完成', failed: '失败', skipped: '已跳过', degraded: '降级完成' }
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
    try { return new Date(time).toLocaleString('zh-CN') } catch { return time }
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
      if (!isPolling.value) stopPolling()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '获取 Pipeline 状态失败'
      ElMessage.error(msg)
    } finally {
      loading.value = false; initialLoading.value = false
    }
  }

  async function handleResume() {
    if (runData.value?.status === 'waiting_for_user') showConfirmDialog.value = true
    else doResume({})
  }

  function handleConfirmResume(payload: Record<string, unknown>) {
    showConfirmDialog.value = false; doResume(payload)
  }

  async function doResume(payload: Record<string, unknown>) {
    if (!runData.value) return
    try {
      await pipelineApi.resumePipeline(runData.value.id, Object.keys(payload).length > 0 ? payload : undefined)
      ElMessage.success('Pipeline 已恢复'); await fetchRunData(); startPolling()
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'status' in e && (e as { status: number }).status === 409) ElMessage.warning('Pipeline 状态已变更，请刷新')
      else ElMessage.error('恢复失败')
    }
  }

  function startPolling() { stopPolling(); if (isPolling.value) pollingTimer.value = setInterval(fetchRunData, 5000) }
  function stopPolling() { if (pollingTimer.value) { clearInterval(pollingTimer.value); pollingTimer.value = null } }
  function goBack() { router.back() }

  onMounted(async () => { await fetchRunData(true); startPolling() })
  onUnmounted(() => { stopPolling() })

  return {
    runData, loading, initialLoading, isPolling, showConfirmDialog,
    confirmReason, confirmSchema, stepNameMap, artifactKindMap,
    runStatusType, runStatusText, duration,
    stepStatusType, stepStatusText, stepDuration, confidenceColor, formatTime,
    fetchRunData, handleResume, handleConfirmResume, goBack,
  }
}
