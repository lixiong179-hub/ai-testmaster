import { ref, computed, type InjectionKey } from 'vue'
import { ElMessage } from 'element-plus'
import {
  testPointApi,
  type XmindPreviewItem,
  type XmindPreviewCaseItem,
  type XmindImportResponse,
  type XmindPreviewResponse,
  type XmindImportProgressEvent,
} from '@/api/testPoint'
import { XMIND_IMPORT_CONFIG } from '@/constants/resource'

interface ImportResultData {
  success: boolean
  savedCount: number
  savedCaseCount: number
  totalParsed: number
  skippedCount: number
  skippedReasons: string[]
  errorMessage: string
  aiTimeout: boolean
}

function createEmptyImportResult(): ImportResultData {
  return { success: false, savedCount: 0, savedCaseCount: 0, totalParsed: 0, skippedCount: 0, skippedReasons: [], errorMessage: '', aiTimeout: false }
}

export const XmindImportKey: InjectionKey<ReturnType<typeof useXmindImport>> = Symbol('XmindImport')

export function useXmindImport(projectId: number) {
  const currentStep = ref(0)
  const selectedFile = ref<File | null>(null)
  const loading = ref(false)
  const previewMode = ref<'test_points' | 'test_cases'>('test_points')
  const previewData = ref<XmindPreviewItem[]>([])
  const previewCaseData = ref<XmindPreviewCaseItem[]>([])
  const previewSkippedCount = ref(0)
  const previewSkippedReasons = ref<string[]>([])
  const activePreviewTab = ref<'points' | 'cases'>('points')
  const currentPage = ref(1)
  const pageSize = 20
  const isDragover = ref(false)
  const aiEnhance = ref(false)
  const previewAiTimeout = ref(false)
  const previewTotalPaths = ref(0)
  const importProgress = ref<XmindImportProgressEvent | null>(null)
  const importProgressText = ref('')
  const importResult = ref<ImportResultData>(createEmptyImportResult())

  const paginatedPreviewData = computed(() => {
    const start = (currentPage.value - 1) * pageSize
    return previewData.value.slice(start, start + pageSize)
  })
  const paginatedPreviewCases = computed(() => {
    const start = (currentPage.value - 1) * pageSize
    return previewCaseData.value.slice(start, start + pageSize)
  })
  const hasCasePreview = computed(() => previewCaseData.value.length > 0)
  const isCasePreviewMode = computed(() => previewMode.value === 'test_cases')
  const currentPreviewTotal = computed(() =>
    activePreviewTab.value === 'cases' ? previewCaseData.value.length : previewData.value.length
  )
  const highPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 1).length)
  const mediumPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 2).length)
  const lowPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 3).length)
  const isAiSamplePreview = computed(
    () => aiEnhance.value && previewTotalPaths.value > 0 && previewTotalPaths.value > previewCaseData.value.length
  )

  function getPriorityType(priority: number): string {
    const map: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'success' }
    return map[priority] || 'info'
  }
  function getPriorityLabel(priority: number): string {
    const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
    return map[priority] || '未知'
  }
  function formatCaseStepSummary(item: XmindPreviewCaseItem): string {
    if (!item.steps.length) return '无步骤'
    return item.steps.map((s) => `${s.step_number}.${s.display_action || s.description || s.action}`).join(' → ')
  }
  function formatFileSize(size: number): string {
    if (size < 1024) return size + ' B'
    if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
    return (size / (1024 * 1024)).toFixed(1) + ' MB'
  }
  function getErrorMessage(error: unknown, defaultMsg: string): string {
    if (error && typeof error === 'object' && 'message' in error) return String(error.message) || defaultMsg
    return defaultMsg
  }

  function applyPreviewResponse(data: XmindPreviewResponse): void {
    previewMode.value = data.preview_mode || 'test_points'
    previewData.value = data.items || []
    previewCaseData.value = data.case_items || []
    previewSkippedCount.value = data.skipped_count || 0
    previewSkippedReasons.value = data.skipped_reasons || []
    previewAiTimeout.value = data.ai_timeout || false
    previewTotalPaths.value = data.total_paths || 0
    activePreviewTab.value = data.preview_mode === 'test_cases' ? 'cases' : 'points'
    currentPage.value = 1
    currentStep.value = 1
  }

  function applyImportResponse(data: XmindImportResponse): void {
    importResult.value = {
      success: true, savedCount: data.saved_count, savedCaseCount: data.saved_case_count || 0,
      totalParsed: data.total_parsed, skippedCount: data.skipped_count,
      skippedReasons: data.skipped_reasons || [], errorMessage: '', aiTimeout: data.ai_timeout || false,
    }
    currentStep.value = 2
  }

  function applyImportError(msg: string): void {
    importResult.value = { ...createEmptyImportResult(), errorMessage: msg }
    currentStep.value = 2
  }

  async function handlePreview(): Promise<void> {
    if (!selectedFile.value) return
    loading.value = true
    importProgress.value = null
    importProgressText.value = ''
    if (aiEnhance.value) {
      try {
        await testPointApi.importXmindStream(selectedFile.value, projectId, true, {
          onProgress: (event) => {
            importProgress.value = event
            importProgressText.value = event.status === 'starting' ? '正在启动AI解析...'
              : event.status === 'completed' ? 'AI解析完成，正在处理结果...'
              : `AI解析中... ${event.completed_batches}/${event.total_batches} 批次完成 (${event.percentage}%)`
          },
          onResult: (data) => { applyPreviewResponse(data as XmindPreviewResponse) },
          onError: (detail) => { ElMessage.error(detail || 'AI预览失败') },
        })
      } catch (error: unknown) { ElMessage.error(getErrorMessage(error, 'AI预览失败')) }
      finally { loading.value = false; importProgress.value = null; importProgressText.value = '' }
    } else {
      try {
        const data = (await testPointApi.importXmind(selectedFile.value, projectId, true, false)) as XmindPreviewResponse
        applyPreviewResponse(data)
      } catch (error: unknown) { ElMessage.error(getErrorMessage(error, '预览失败')) }
      finally { loading.value = false }
    }
  }

  async function handleImport(emitImported: () => void): Promise<void> {
    if (!selectedFile.value) return
    loading.value = true
    importProgress.value = null
    importProgressText.value = ''
    if (aiEnhance.value) {
      try {
        await testPointApi.importXmindStream(selectedFile.value, projectId, false, {
          onProgress: (event) => {
            importProgress.value = event
            importProgressText.value = event.status === 'starting' ? '正在启动AI解析...'
              : event.status === 'completed' ? 'AI解析完成，正在写入数据库...'
              : `AI解析中... ${event.completed_batches}/${event.total_batches} 批次完成 (${event.percentage}%)`
          },
          onResult: (data) => { applyImportResponse(data as XmindImportResponse); emitImported() },
          onError: (detail) => { applyImportError(detail || '导入失败') },
        })
      } catch (error: unknown) { applyImportError(getErrorMessage(error, '导入失败')) }
      finally { loading.value = false; importProgress.value = null; importProgressText.value = '' }
    } else {
      try {
        const data = (await testPointApi.importXmind(selectedFile.value, projectId, false, false)) as XmindImportResponse
        applyImportResponse(data); emitImported()
      } catch (error: unknown) { applyImportError(getErrorMessage(error, '导入失败')) }
      finally { loading.value = false }
    }
  }

  function resetState(): void {
    currentStep.value = 0; selectedFile.value = null; aiEnhance.value = false
    previewAiTimeout.value = false; previewTotalPaths.value = 0; previewMode.value = 'test_points'
    previewData.value = []; previewCaseData.value = []; previewSkippedCount.value = 0
    previewSkippedReasons.value = []; activePreviewTab.value = 'points'
    importResult.value = createEmptyImportResult(); loading.value = false
  }

  return {
    currentStep, selectedFile, loading, previewMode, previewData, previewCaseData,
    previewSkippedCount, previewSkippedReasons, activePreviewTab, currentPage, pageSize,
    isDragover, aiEnhance, previewAiTimeout, previewTotalPaths, importProgress,
    importProgressText, importResult, paginatedPreviewData, paginatedPreviewCases,
    hasCasePreview, isCasePreviewMode, currentPreviewTotal, highPriorityCount,
    mediumPriorityCount, lowPriorityCount, isAiSamplePreview, getPriorityType,
    getPriorityLabel, formatCaseStepSummary, formatFileSize, handlePreview, handleImport, resetState,
  }
}
