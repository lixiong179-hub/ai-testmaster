import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fileApi, type ProjectFile } from '@/api/file'
import { testPointApi, type TestPointDraft } from '@/api/testPoint'

export function useTestPointExtract(
  props: { projectId: number; initialFileId?: number | null },
  visible: { value: boolean }
) {
  const loadingFiles = ref(false)
  const extracting = ref(false)
  const saving = ref(false)
  const progress = ref(0)
  const progressText = ref('准备提取...')
  const selectedFileId = ref<number | undefined>(undefined)
  const files = ref<ProjectFile[]>([])
  const extractedPoints = ref<TestPointDraft[]>([])
  let progressTimer: ReturnType<typeof setInterval> | null = null

  const requirementFiles = computed(() =>
    files.value.filter((file) => file.resource_type === 'requirement' && file.is_active !== false)
  )
  const highPriorityCount = computed(
    () => extractedPoints.value.filter((item) => item.priority === 1).length
  )
  const mediumPriorityCount = computed(
    () => extractedPoints.value.filter((item) => item.priority === 2).length
  )
  const lowPriorityCount = computed(
    () => extractedPoints.value.filter((item) => item.priority === 3).length
  )

  watch(
    () => visible.value,
    async (open) => {
      if (open && props.projectId) await loadFiles()
    }
  )
  watch(
    () => props.initialFileId,
    (fileId) => {
      if (visible.value && fileId) selectedFileId.value = fileId
    }
  )

  function startFakeProgress(): void {
    stopFakeProgress()
    progress.value = 0
    progressText.value = '正在读取文件内容...'
    const phases = [
      { limit: 25, text: '正在读取文件内容...' },
      { limit: 55, text: '正在解析文档结构...' },
      { limit: 80, text: 'AI 正在提取测试点...' },
      { limit: 92, text: '正在整理提取结果...' },
    ]
    let phaseIndex = 0
    progressTimer = setInterval(() => {
      const phase = phases[phaseIndex]
      if (!phase) return
      if (progress.value < phase.limit) {
        progress.value = Math.min(progress.value + Math.round(Math.random() * 4 + 1), phase.limit)
        progressText.value = phase.text
        return
      }
      phaseIndex += 1
    }, 250)
  }

  function stopFakeProgress(): void {
    if (progressTimer) {
      clearInterval(progressTimer)
      progressTimer = null
    }
  }

  async function loadFiles(): Promise<void> {
    loadingFiles.value = true
    try {
      const response = await fileApi.getFileList(props.projectId, undefined, 1, 200)
      files.value = response.data.items || []
      if (props.initialFileId && files.value.some((file) => file.id === props.initialFileId))
        selectedFileId.value = props.initialFileId
      else if (!selectedFileId.value && requirementFiles.value.length > 0)
        selectedFileId.value = requirementFiles.value[0].id
    } catch (error) {
      files.value = []
      ElMessage.error(error instanceof Error ? error.message : '加载需求文档失败')
    } finally {
      loadingFiles.value = false
    }
  }

  async function handleExtract(): Promise<void> {
    if (!selectedFileId.value) {
      ElMessage.warning('请先选择需求文档')
      return
    }
    extracting.value = true
    extractedPoints.value = []
    startFakeProgress()
    try {
      const response = await testPointApi.extract({ file_id: selectedFileId.value })
      extractedPoints.value = response.items.map((item, index) => ({
        id: item.id || index + 1,
        module: item.module || '',
        point: item.point || '',
        priority: item.priority || 2,
        ai_prompt: item.ai_prompt ?? undefined,
        create_time: item.create_time,
      }))
      progress.value = 100
      progressText.value = `提取完成，共 ${extractedPoints.value.length} 个测试点`
      ElMessage.success(progressText.value)
    } catch (error) {
      progress.value = 0
      progressText.value = '提取失败'
      ElMessage.error(error instanceof Error ? error.message : '提取测试点失败')
    } finally {
      stopFakeProgress()
      extracting.value = false
    }
  }

  async function handleSave(): Promise<void> {
    if (extractedPoints.value.length === 0) {
      ElMessage.warning('没有可保存的测试点')
      return
    }
    saving.value = true
    try {
      const payload = extractedPoints.value
        .map((item) => ({
          module: item.module,
          point: item.point,
          priority: item.priority,
          ai_prompt: item.ai_prompt ?? undefined,
        }))
        .filter((item) => item.module && item.point)
      const response = await testPointApi.batchSave(props.projectId, payload)
      ElMessage.success(response.message || `成功保存 ${response.data.saved_count} 个测试点`)
      return
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '保存测试点失败')
    } finally {
      saving.value = false
    }
  }

  function resetState(): void {
    stopFakeProgress()
    extracting.value = false
    saving.value = false
    progress.value = 0
    progressText.value = '准备提取...'
    extractedPoints.value = []
    if (props.initialFileId) selectedFileId.value = props.initialFileId
    else if (requirementFiles.value.length > 0) selectedFileId.value = requirementFiles.value[0].id
    else selectedFileId.value = undefined
  }

  function priorityText(priority: number): string {
    return priority === 1 ? '高' : priority === 2 ? '中' : '低'
  }
  function priorityTagType(priority: number): 'danger' | 'warning' | 'info' {
    return priority === 1 ? 'danger' : priority === 2 ? 'warning' : 'info'
  }
  function formatExtractStatus(status?: string): string {
    if (status === 'completed') return '已提取'
    if (status === 'processing') return '提取中'
    if (status === 'failed') return '提取失败'
    return '待提取'
  }

  return {
    loadingFiles,
    extracting,
    saving,
    progress,
    progressText,
    selectedFileId,
    requirementFiles,
    extractedPoints,
    highPriorityCount,
    mediumPriorityCount,
    lowPriorityCount,
    handleExtract,
    handleSave,
    resetState,
    priorityText,
    priorityTagType,
    formatExtractStatus,
  }
}
