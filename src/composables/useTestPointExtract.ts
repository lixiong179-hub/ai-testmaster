import { ref, reactive, computed, onUnmounted, provide, inject, type InjectionKey } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type TableInstance } from 'element-plus'
import request from '@/utils/request'
import { testPointApi } from '@/api/testPoint'
import type { TestPointDraft } from '@/types/testPoint'

export interface TestPointItem {
  id: number
  module: string
  function?: string
  point: string
  priority: number
  ai_prompt?: string
  create_time?: string
  _raw?: Record<string, unknown>
}

export interface ProjectItem {
  id: number
  name: string
}

export interface FileItem {
  id: number
  project_id: number
  file_name: string
  file_url: string
  file_type: string
  size: number
  upload_time: string
  file_source: string
  resource_type?: string
}

export interface ResourceRow {
  source: 'file'
  id: number
  project_id: number
  display_name: string
  resource_type: string
  type_label: string
  size_text: string
  time_text: string
}

interface TestPointListResponse {
  code: number
  data?: {
    items: TestPointItem[]
    total: number
  }
  message?: string
}

const PROGRESS_PHASES = [
  { end: 20, text: '正在读取文件内容...' },
  { end: 40, text: '正在解析文档结构...' },
  { end: 65, text: 'AI 正在分析需求并提取测试点...' },
  { end: 85, text: '正在整理测试点数据...' },
]

export type TestPointExtractState = ReturnType<typeof createExtractState>

const EXTRACT_KEY: InjectionKey<TestPointExtractState> = Symbol('testPointExtract')

function createExtractState() {
  const router = useRouter()
  const route = useRoute()

  const currentStep = ref(0)

  const formData = reactive({
    project_id: '' as number | '',
  })

  const projects = ref<ProjectItem[]>([])
  const files = ref<FileItem[]>([])
  const selectedResource = ref<ResourceRow | null>(null)
  const testPoints = ref<TestPointItem[]>([])
  const extracting = ref(false)
  const saving = ref(false)
  const batchDeleting = ref(false)
  const deleting = ref(false)
  const savedFromDb = ref(false)
  const loadingTestPoints = ref(false)

  const selectedRows = ref<TestPointItem[]>([])
  const testPointTable = ref<TableInstance>()
  const currentPage = ref(1)
  const pageSize = ref(10)
  const dbTotal = ref(0)

  const progress = ref(0)
  const progressText = ref('准备提取...')
  let progressInterval: ReturnType<typeof setInterval> | null = null

  const errorMessage = ref('')
  const dialogVisible = ref(false)
  const resourceTypeFilter = ref('')

  const editForm = reactive<TestPointItem>({
    id: 0,
    module: '',
    function: '',
    point: '',
    priority: 2,
  })

  const editingIndex = ref(-1)
  const updating = ref(false)

  const selectedProjectInfo = computed(() => {
    if (!formData.project_id) return null
    return projects.value.find((p) => p.id === formData.project_id) || null
  })

  const currentProjectId = computed(() => {
    return formData.project_id ? Number(formData.project_id) : 0
  })

  const resourceRows = computed<ResourceRow[]>(() => {
    return files.value.map((f) => ({
      source: 'file' as const,
      id: f.id,
      project_id: f.project_id,
      display_name: f.file_name,
      resource_type: f.resource_type || 'other',
      type_label: getResourceTypeLabel(f.resource_type || 'other'),
      size_text: formatFileSize(f.size),
      time_text: f.upload_time,
    }))
  })

  const filteredResourceRows = computed(() => {
    if (!resourceTypeFilter.value) return resourceRows.value
    return resourceRows.value.filter((r) => r.resource_type === resourceTypeFilter.value)
  })

  const progressStatus = computed(() => {
    if (progress.value === 100) return 'success'
    if (errorMessage.value) return 'exception'
    return ''
  })

  const paginatedTestPoints = computed(() => {
    if (savedFromDb.value) return testPoints.value
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    return testPoints.value.slice(start, end)
  })

  const moduleCount = computed(() => {
    const modules = new Set(testPoints.value.map((tp) => tp.module || '未分类'))
    return modules.size
  })

  const totalDisplayCount = computed(() => {
    return savedFromDb.value ? dbTotal.value : testPoints.value.length
  })

  function formatFileSize(size: number): string {
    if (size < 1024) {
      return size + ' B'
    } else if (size < 1024 * 1024) {
      return (size / 1024).toFixed(2) + ' KB'
    } else {
      return (size / (1024 * 1024)).toFixed(2) + ' MB'
    }
  }

  function getResourceTypeLabel(type: string) {
    const labelMap: Record<string, string> = {
      requirement: '需求文档',
      ui_mockup: 'UI原型图',
      api_doc: 'API文档',
      test_data: '测试数据',
      other: '其他',
    }
    return labelMap[type] || type
  }

  function getResourceTypeTagType(type: string) {
    const tagMap: Record<string, string> = {
      requirement: 'primary',
      ui_mockup: 'warning',
      api_doc: 'success',
      test_data: 'info',
      other: 'info',
    }
    return tagMap[type] || 'info'
  }

  function getResourceIcon(type: string): 'Document' | 'Picture' | 'DocumentCopy' | 'Files' {
    const iconMap: Record<string, 'Document' | 'Picture' | 'DocumentCopy' | 'Files'> = {
      requirement: 'Document',
      ui_mockup: 'Picture',
      api_doc: 'DocumentCopy',
      test_data: 'Files',
      other: 'Document',
    }
    return iconMap[type] || 'Document'
  }

  function getPriorityTagType(priority: number | string) {
    const p = Number(priority)
    if (p === 1) return 'danger'
    if (p === 2) return 'warning'
    return 'info'
  }

  function getPriorityLabel(priority: number | string) {
    const p = Number(priority)
    if (p === 1) return '高'
    if (p === 2) return '中'
    return '低'
  }

  function getPriorityCount(priority: number): number {
    return testPoints.value.filter((tp) => tp.priority === priority).length
  }

  function getModuleDistribution(): Record<string, number> {
    const distribution: Record<string, number> = {}
    testPoints.value.forEach((tp) => {
      const module = tp.module || '未分类'
      distribution[module] = (distribution[module] || 0) + 1
    })
    return distribution
  }

  function getResourceTypeCount(type: string): number {
    return files.value.filter((f) => f.resource_type === type).length
  }

  function getResourceTypePercentage(type: string): number {
    const total = files.value.length
    if (total === 0) return 0
    return Math.round((getResourceTypeCount(type) / total) * 100)
  }

  // ==================== API ====================

  async function getProjects() {
    try {
      const response = await request.get('/api/v1/project/list')
      if (response && response.data && response.data.items) {
        projects.value = response.data.items.filter(
          (project: ProjectItem) => project.name !== '默认项目'
        )
      } else {
        projects.value = []
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
      projects.value = []
    }
  }

  async function loadResources(projectId: number) {
    try {
      const fileRes = await request.get(`/api/v1/file/list/${projectId}`)
      if (fileRes && fileRes.data && fileRes.data.items) {
        files.value = fileRes.data.items
      } else {
        files.value = []
      }
    } catch (error) {
      console.error('获取文件列表失败:', error)
      files.value = []
    }
  }

  async function loadSavedTestPoints(projectId: number, page = 1) {
    loadingTestPoints.value = true
    try {
      const response: TestPointListResponse = await request.get(
        `/api/v1/test-point/list/${projectId}`,
        {
          params: { page, page_size: pageSize.value },
        }
      )
      if (response?.code === 200 && response.data) {
        testPoints.value = (response.data.items || []) as TestPointItem[]
        dbTotal.value = response.data.total || 0
        savedFromDb.value = true
        currentPage.value = page
      }
    } catch (error) {
      console.error('加载测试点失败:', error)
    } finally {
      loadingTestPoints.value = false
    }
  }

  // ==================== 事件处理 ====================

  async function handleProjectChange(projectId: number) {
    if (projectId) {
      await loadResources(projectId)
      selectedResource.value = null
      testPoints.value = []
      savedFromDb.value = false
      dbTotal.value = 0
      currentPage.value = 1
      errorMessage.value = ''
      await loadSavedTestPoints(projectId)
    } else {
      files.value = []
      selectedResource.value = null
      testPoints.value = []
      savedFromDb.value = false
      dbTotal.value = 0
      currentPage.value = 1
    }
  }

  function handleResourceSelect(row: ResourceRow) {
    selectedResource.value = row
  }

  function goToExtract(row?: ResourceRow) {
    const target = row ?? selectedResource.value
    if (!target) {
      ElMessage.warning('请先选择需求文件')
      return
    }
    selectedResource.value = target
    currentStep.value = 2
  }

  function startExtract() {
    if (!selectedResource.value) {
      ElMessage.warning('请先选择需求文件')
      return
    }
    extractTestPoints()
  }

  function retryExtract() {
    errorMessage.value = ''
    extractTestPoints()
  }

  function goToNextStep() {
    if (currentStep.value === 0 && !formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }
    if (currentStep.value === 1 && !selectedResource.value) {
      ElMessage.warning('请先选择需求资源')
      return
    }
    if (currentStep.value < 3) {
      currentStep.value++
    }
  }

  function goToPrevStep() {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  function handlePageChange(page: number) {
    if (savedFromDb.value && formData.project_id) {
      loadSavedTestPoints(Number(formData.project_id), page)
    } else {
      currentPage.value = page
    }
  }

  // ==================== 核心提取逻辑 ====================

  async function extractTestPoints() {
    const target = selectedResource.value
    if (!target) {
      ElMessage.warning('请先选择需求文件')
      return
    }

    if (extracting.value) {
      ElMessage.warning('正在提取中，请稍候')
      return
    }

    testPoints.value = []
    savedFromDb.value = false
    dbTotal.value = 0
    currentPage.value = 1
    errorMessage.value = ''
    extracting.value = true
    progress.value = 0
    progressText.value = '正在读取文件内容...'

    if (progressInterval) {
      clearInterval(progressInterval)
      progressInterval = null
    }

    let phaseIndex = 0

    progressInterval = setInterval(() => {
      if (phaseIndex < PROGRESS_PHASES.length) {
        const targetProgress = PROGRESS_PHASES[phaseIndex].end
        if (progress.value < targetProgress) {
          progress.value = Math.round(
            Math.min(progress.value + Math.random() * 4 + 1, targetProgress)
          )
          progressText.value = PROGRESS_PHASES[phaseIndex].text
        } else {
          phaseIndex++
        }
      }
    }, 300)

    try {
      progressText.value = PROGRESS_PHASES[PROGRESS_PHASES.length - 1].text

      const response = await testPointApi.extract({
        file_id: target.id,
      })

      if (response && response.items) {
        testPoints.value = response.items.map((item: TestPointDraft, index: number) => ({
          id: item.id ?? index + 1,
          module: item.module || '',
          point: item.point || '',
          priority: typeof item.priority === 'number' ? item.priority : 2,
          ai_prompt: item.ai_prompt ?? undefined,
          create_time: item.create_time ?? undefined,
          _raw: { ...item } as Record<string, unknown>,
        }))
        savedFromDb.value = false
        ElMessage.success(`测试点提取成功，共 ${testPoints.value.length} 个`)
      } else {
        ElMessage.warning('未提取到测试点')
      }

      clearInterval(progressInterval)
      progressInterval = null
      progress.value = 100
      progressText.value = `提取完成！共 ${testPoints.value.length} 个测试点`
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      if (progressInterval) {
        clearInterval(progressInterval)
        progressInterval = null
      }
      progress.value = 0

      const detail = err.response?.data?.detail
      if (
        typeof detail === 'string' &&
        !detail.includes('traceback') &&
        !detail.includes('stack')
      ) {
        errorMessage.value = detail.length > 200 ? detail.slice(0, 200) + '...' : detail
      } else if (err.response?.data?.message) {
        errorMessage.value = err.response.data.message
      } else {
        errorMessage.value = '测试点提取失败，请检查网络连接或稍后重试'
      }

      ElMessage.error('提取失败，请查看错误信息')
    } finally {
      extracting.value = false
    }
  }

  function handleCancel() {
    ElMessageBox.confirm('确定要取消提取吗？', '取消确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      if (progressInterval) {
        clearInterval(progressInterval)
        progressInterval = null
      }
      extracting.value = false
      progress.value = 0
      progressText.value = '已取消'
      ElMessage.info('提取已取消')
    })
  }

  // ==================== 多选和批量操作 ====================

  function handleSelectionChange(rows: TestPointItem[]) {
    selectedRows.value = rows
  }

  function clearSelection() {
    selectedRows.value = []
    if (testPointTable.value) {
      testPointTable.value.clearSelection()
    }
  }

  async function batchDeleteTestPoints() {
    if (selectedRows.value.length === 0) {
      ElMessage.warning('请先选择要删除的测试点')
      return
    }

    if (!formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }

    try {
      await ElMessageBox.confirm(
        `确定要删除选中的 ${selectedRows.value.length} 个测试点吗？此操作不可恢复！`,
        '批量删除确认',
        {
          confirmButtonText: '确定删除',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )

      batchDeleting.value = true

      const ids = selectedRows.value.map((row) => row.id)

      const result = await testPointApi.batchDelete(Number(formData.project_id), ids)

      if (result.code === 200) {
        ElMessage.success(result.message || `成功删除 ${result.data.deleted_count} 个测试点`)
        clearSelection()

        if (savedFromDb.value) {
          await loadSavedTestPoints(Number(formData.project_id), currentPage.value)
        } else {
          const deletedIds = new Set(ids)
          testPoints.value = testPoints.value.filter((item) => !deletedIds.has(item.id))
        }
      } else {
        throw new Error(result.message || '批量删除失败')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      if (error !== 'cancel') {
        console.error('批量删除失败:', error)
        ElMessage.error(
          err.response?.data?.detail ||
            err.response?.data?.message ||
            err.message ||
            '批量删除失败，请稍后重试'
        )
      }
    } finally {
      batchDeleting.value = false
    }
  }

  // ==================== 编辑功能 ====================

  function editTestPoint(testPoint: TestPointItem) {
    const index = testPoints.value.findIndex((item) => item.id === testPoint.id)
    editingIndex.value = index
    editForm.id = testPoint.id
    editForm.module = testPoint.module
    editForm.function = testPoint.function || ''
    editForm.point = testPoint.point
    editForm.priority = testPoint.priority || 2
    dialogVisible.value = true
  }

  async function saveTestPoint() {
    if (!editForm.module || !editForm.point) {
      ElMessage.warning('请填写完整的测试点信息')
      return
    }

    try {
      updating.value = true

      const index = editingIndex.value
      if (index !== -1 && index < testPoints.value.length) {
        const currentPoint = testPoints.value[index]

        if (currentPoint.id && savedFromDb.value && formData.project_id) {
          const result = await testPointApi.update(currentPoint.id, {
            project_id: Number(formData.project_id),
            module: editForm.module,
            function: editForm.function,
            point: editForm.point,
            priority: editForm.priority,
            ai_prompt: currentPoint.ai_prompt,
          })

          if (result.code === 200) {
            testPoints.value[index] = {
              ...result.data,
              ai_prompt: result.data.ai_prompt ?? undefined,
              _raw: result.data as unknown as Record<string, unknown>,
            }
            ElMessage.success('测试点更新成功')
            dialogVisible.value = false

            await loadSavedTestPoints(Number(formData.project_id), currentPage.value)
          } else {
            throw new Error(result.message || '更新失败')
          }
        } else {
          testPoints.value[index] = { ...editForm }
          ElMessage.success('测试点更新成功（本地）')
          dialogVisible.value = false
        }
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('保存测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '保存失败，请稍后重试'
      )
    } finally {
      updating.value = false
    }
  }

  // ==================== 删除功能 ====================

  async function deleteTestPoint(testPoint: TestPointItem) {
    try {
      if (!formData.project_id) {
        ElMessage.warning('请先选择项目')
        return
      }

      deleting.value = true

      if (testPoint.id && savedFromDb.value) {
        const result = await testPointApi.delete(testPoint.id, Number(formData.project_id))

        if (result.code === 200) {
          ElMessage.success('删除成功')
          let targetPage = currentPage.value
          const totalAfterDelete = dbTotal.value - 1
          const maxPage = Math.max(1, Math.ceil(totalAfterDelete / pageSize.value))
          if (targetPage > maxPage) {
            targetPage = maxPage
          }
          await loadSavedTestPoints(Number(formData.project_id), targetPage)
        } else {
          ElMessage.error(result.message || '删除失败')
        }
      } else {
        const index = testPoints.value.findIndex((item) => item.id === testPoint.id)
        if (index !== -1) {
          testPoints.value.splice(index, 1)
        }
        ElMessage.success('删除成功（本地）')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('删除测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '删除失败，请稍后重试'
      )
    } finally {
      deleting.value = false
    }
  }

  // ==================== 保存与生成 ====================

  async function saveToDatabase() {
    if (testPoints.value.length === 0) {
      ElMessage.warning('没有可保存的测试点')
      return
    }

    const projectId =
      selectedResource.value?.project_id || (formData.project_id ? Number(formData.project_id) : 0)
    if (!projectId) {
      ElMessage.warning('请先选择项目')
      return
    }

    saving.value = true
    try {
      const rawData = testPoints.value
        .map((tp) =>
          tp._raw
            ? JSON.parse(JSON.stringify(tp._raw))
            : {
                module: tp.module,
                point: tp.point,
                priority: tp.priority,
              }
        )
        .filter((raw) => raw && raw.module && raw.point)

      if (rawData.length === 0) {
        ElMessage.warning('没有有效的测试点数据')
        saving.value = false
        return
      }

      const response = await testPointApi.batchSave(projectId, rawData)

      if (response?.code === 200) {
        ElMessage.success(response?.message || `成功保存 ${rawData.length} 个测试点`)
        savedFromDb.value = true
        await loadSavedTestPoints(projectId)
      } else {
        ElMessage.error(response?.message || '保存失败')
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      console.error('保存测试点失败:', error)
      ElMessage.error(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          err.message ||
          '保存到数据库失败'
      )
    } finally {
      saving.value = false
    }
  }

  function generateTestCases() {
    if (testPoints.value.length === 0) {
      ElMessage.warning('请先提取或加载测试点')
      return
    }

    const projectId =
      selectedResource.value?.project_id || (formData.project_id ? Number(formData.project_id) : 0)
    if (!projectId) {
      ElMessage.warning('请先选择项目')
      return
    }

    const query: Record<string, string> = {
      project_id: String(projectId),
      test_point_ids: JSON.stringify(testPoints.value.map((tp) => tp.id)),
    }

    if (selectedResource.value) {
      query.file_id = String(selectedResource.value.id)
      query.filename = selectedResource.value.display_name
    }

    router.push({ path: '/home/case/ai-generate', query })
  }

  function goToManagement() {
    const query: Record<string, string> = {}
    const projectId = currentProjectId.value
    if (projectId) {
      query.projectId = String(projectId)
    }
    router.push({
      path: '/home/case/test-point-management',
      query,
    })
  }

  async function init() {
    await getProjects()

    const idParam = Number(route.query.file_id)
    const projectIdParam = Number(route.query.project_id)

    if (projectIdParam) {
      formData.project_id = projectIdParam
      await loadResources(projectIdParam)
      await loadSavedTestPoints(projectIdParam)
      if (idParam) {
        const row = resourceRows.value.find((r) => r.id === idParam)
        if (row) {
          selectedResource.value = row
        }
      }
    }
  }

  function cleanup() {
    if (progressInterval) {
      clearInterval(progressInterval)
      progressInterval = null
    }
  }

  onUnmounted(cleanup)

  return {
    currentStep,
    formData,
    projects,
    files,
    selectedResource,
    testPoints,
    extracting,
    saving,
    batchDeleting,
    deleting,
    savedFromDb,
    loadingTestPoints,
    selectedRows,
    testPointTable,
    currentPage,
    pageSize,
    dbTotal,
    progress,
    progressText,
    errorMessage,
    dialogVisible,
    resourceTypeFilter,
    editForm,
    editingIndex,
    updating,
    selectedProjectInfo,
    currentProjectId,
    resourceRows,
    filteredResourceRows,
    progressStatus,
    paginatedTestPoints,
    moduleCount,
    totalDisplayCount,
    formatFileSize,
    getResourceTypeLabel,
    getResourceTypeTagType,
    getResourceIcon,
    getPriorityTagType,
    getPriorityLabel,
    getPriorityCount,
    getModuleDistribution,
    getResourceTypeCount,
    getResourceTypePercentage,
    getProjects,
    loadResources,
    loadSavedTestPoints,
    handleProjectChange,
    handleResourceSelect,
    goToExtract,
    startExtract,
    retryExtract,
    goToNextStep,
    goToPrevStep,
    handlePageChange,
    extractTestPoints,
    handleCancel,
    handleSelectionChange,
    clearSelection,
    batchDeleteTestPoints,
    editTestPoint,
    saveTestPoint,
    deleteTestPoint,
    saveToDatabase,
    generateTestCases,
    goToManagement,
    init,
    cleanup,
  }
}

export function provideTestPointExtract() {
  const state = createExtractState()
  provide(EXTRACT_KEY, state)
  return state
}

export function useTestPointExtract(): TestPointExtractState {
  const state = inject(EXTRACT_KEY)
  if (!state) {
    throw new Error(
      'useTestPointExtract() must be called within a component tree that provides test point extract state.'
    )
  }
  return state
}
