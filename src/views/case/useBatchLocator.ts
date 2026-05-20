import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
    batchLocatorApi,
    type BatchRecordReport,
} from '@/api/batchLocator'

interface BatchLocatorResult {
    case_id: number
    case_title: string
    status: string
    locator?: string
    error_message?: string
}

export function useBatchLocator(projectId: number) {
    const visible = ref(false)
    const loading = ref(false)
    const currentView = ref<'config' | 'progress' | 'report'>('config')
    const selectedCaseIds = ref<number[]>([])
    const locatorType = ref<'css' | 'xpath'>('css')
    const aiAssist = ref(true)
    const progress = ref(0)
    const progressMessage = ref('')
    const results = ref<BatchLocatorResult[]>([])
    const error = ref('')
    const pollTimer = ref<number | null>(null)

    const successCount = computed(() => results.value.filter((r) => r.status === 'success').length)
    const failCount = computed(() => results.value.filter((r) => r.status === 'failed').length)
    const totalProcessed = computed(() => results.value.length)
    const hasResults = computed(() => results.value.length > 0)

    function open(caseIds: number[]): void {
        selectedCaseIds.value = caseIds
        currentView.value = 'config'
        progress.value = 0
        progressMessage.value = ''
        results.value = []
        error.value = ''
        visible.value = true
    }

    function close(): void {
        cleanup()
        visible.value = false
    }

    function cleanup(): void {
        if (pollTimer.value) { clearInterval(pollTimer.value); pollTimer.value = null }
    }

    async function startLocate(): Promise<void> {
        if (!selectedCaseIds.value.length) { ElMessage.warning('请选择要定位的用例'); return }
        loading.value = true
        currentView.value = 'progress'
        progress.value = 0
        progressMessage.value = '正在初始化批量定位...'
        results.value = []
        error.value = ''
        try {
            await processBatchLocate()
        } catch (err: unknown) {
            error.value = err instanceof Error ? err.message : '启动批量定位失败'
            currentView.value = 'report'
            ElMessage.error(error.value)
        } finally {
            loading.value = false
        }
    }

    async function processBatchLocate(): Promise<void> {
        loading.value = true
        progressMessage.value = '正在启动批量定位...'
        try {
            const res = await batchLocatorApi.startBatchRecord({
                project_id: projectId,
                case_ids: selectedCaseIds.value,
                skip_existing: true,
                execute_precondition: aiAssist.value,
                use_mcp: aiAssist.value,
            })
            const taskId = res.task_id || ''
            if (!taskId) {
                throw new Error('未获取到任务ID')
            }
            await pollCaseStatus(taskId)
        } catch (err: unknown) {
            error.value = err instanceof Error ? err.message : '启动批量定位失败'
            currentView.value = 'report'
            ElMessage.error(error.value)
        } finally {
            loading.value = false
        }
        cleanup()
        currentView.value = 'report'
        if (failCount.value === 0) {
            ElMessage.success(`批量定位完成，成功 ${successCount.value} 个`)
        } else {
            ElMessage.warning(`批量定位完成，成功 ${successCount.value} 个，失败 ${failCount.value} 个`)
        }
    }

    async function pollCaseStatus(taskId: string): Promise<void> {
        const maxAttempts = 60
        for (let i = 0; i < maxAttempts; i++) {
            await new Promise<void>((resolve) => { setTimeout(resolve, 2000) })
            try {
                const status = await batchLocatorApi.getBatchRecordStatus(taskId)
                if (status.status === 'completed') {
                    const report = await batchLocatorApi.getBatchRecordReport(taskId)
                    results.value.push({
                        case_id: report.case_id,
                        case_title: report.case_title,
                        status: report.status === 'completed' ? 'success' : 'failed',
                        locator: report.step_results
                            .filter((s) => s.success && s.locator_value)
                            .map((s) => s.locator_value)
                            .join('; '),
                        error_message: report.error_message,
                    })
                    return
                }
                if (status.status === 'failed') {
                    results.value.push({
                        case_id: status.case_id,
                        case_title: `用例 ${status.case_id}`,
                        status: 'failed',
                        error_message: status.message || '定位失败',
                    })
                    return
                }
                progress.value = status.progress || Math.round(((i + 1) / maxAttempts) * 100)
                progressMessage.value = status.message || `正在定位... ${i + 1}/${maxAttempts}`
            } catch (err: unknown) {
                results.value.push({
                    case_id: 0,
                    case_title: '未知用例',
                    status: 'failed',
                    error_message: err instanceof Error ? err.message : '查询状态失败',
                })
                return
            }
        }
        results.value.push({
            case_id: 0,
            case_title: '未知用例',
            status: 'failed',
            error_message: '定位超时',
        })
    }

    async function retryFailed(): Promise<void> {
        const failedIds = results.value.filter((r) => r.status === 'failed').map((r) => r.case_id)
        if (!failedIds.length) { ElMessage.info('没有失败的用例'); return }
        selectedCaseIds.value = failedIds
        await startLocate()
    }

    async function applyResults(): Promise<void> {
        const successResults = results.value.filter((r) => r.status === 'success' && r.locator)
        if (!successResults.length) { ElMessage.warning('没有可应用的结果'); return }
        ElMessage.success(`已确认 ${successResults.length} 个定位器`)
        close()
    }

    onUnmounted(cleanup)

    return {
        visible, loading, currentView, selectedCaseIds, locatorType, aiAssist,
        progress, progressMessage, results, error, successCount, failCount,
        totalProcessed, hasResults, open, close, startLocate, retryFailed, applyResults,
    }
}
