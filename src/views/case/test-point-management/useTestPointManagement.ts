import { computed, onMounted, reactive, ref, type InjectionKey } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import projectApi, { type Project } from '@/api/project'
import { testPointApi } from '@/api/testPoint'
import type {
  AnalysisProgress,
  TestPoint,
  TestPointListParams,
  TestPointListStats,
  TestPointRequirementOption,
} from '@/types/testPoint'

export const TestPointMgmtKey: InjectionKey<ReturnType<typeof useTestPointManagement>> =
  Symbol('TestPointMgmt')

export function useTestPointManagement() {
  const route = useRoute()
  const router = useRouter()
  const loading = ref(false)
  const generating = ref(false)
  const generateDialogVisible = ref(false)
  const generateProgress = ref(0)
  const generateMessage = ref('')
  const generateStatus = ref<'running' | 'success' | 'partial' | 'warning' | 'error'>('running')
  const xmindImportDialogVisible = ref(false)
  const extractDialogVisible = ref(false)
  const initialExtractFileId = ref<number>(Number(route.query.file_id) || 0)
  const hasConsumedInitialExtract = ref(false)
  const projects = ref<Project[]>([])
  const testPoints = ref<TestPoint[]>([])
  const requirementOptions = ref<TestPointRequirementOption[]>([])
  const selectedRows = ref<TestPoint[]>([])
  const initialProjectId = Number(route.query.projectId || route.query.project_id)
  const selectedProjectId = ref<number | undefined>(
    Number.isFinite(initialProjectId) && initialProjectId > 0 ? initialProjectId : undefined
  )
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(10)
  const dateRange = ref<string[]>([])
  const formDialogVisible = ref(false)
  const casesDialogVisible = ref(false)
  const editingPoint = ref<TestPoint | null>(null)
  const currentTestPoint = ref<TestPoint | null>(null)
  const listStats = ref<TestPointListStats>({
    total: 0,
    high_priority_count: 0,
    medium_priority_count: 0,
    low_priority_count: 0,
    generated_case_count: 0,
  })
  const filters = reactive<TestPointListParams>({
    module: '',
    created_by: '',
    keyword: '',
    sort_by: 'create_time',
    sort_order: 'desc',
  })

  const highCount = computed(() => listStats.value.high_priority_count)
  const mediumCount = computed(() => listStats.value.medium_priority_count)
  const lowCount = computed(() => listStats.value.low_priority_count)
  const statsTotal = computed(() => listStats.value.total)
  const generatedCaseCount = computed(() => listStats.value.generated_case_count)
  const selectedProjectName = computed(
    () => projects.value.find((p) => p.id === selectedProjectId.value)?.name || ''
  )
  const progressStatus = computed<'success' | 'warning' | 'exception' | undefined>(() => {
    if (generateStatus.value === 'success') return 'success'
    if (generateStatus.value === 'partial' || generateStatus.value === 'warning') return 'warning'
    if (generateStatus.value === 'error') return 'exception'
    return undefined
  })

  function createEmptyStats(): TestPointListStats {
    return {
      total: 0,
      high_priority_count: 0,
      medium_priority_count: 0,
      low_priority_count: 0,
      generated_case_count: 0,
    }
  }
  function priorityText(p: number): string {
    return p === 1 ? '高' : p === 2 ? '中' : '低'
  }
  function priorityTagType(p: number): 'danger' | 'warning' | 'info' {
    return p === 1 ? 'danger' : p === 2 ? 'warning' : 'info'
  }
  function isCancelError(e: unknown): boolean {
    return e === 'cancel' || e === 'close'
  }

  async function loadProjects(): Promise<void> {
    try {
      const response = await projectApi.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data.items.filter((p) => p.name !== '默认项目')
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载项目失败')
    }
  }

  async function fetchTestPoints(): Promise<void> {
    if (!selectedProjectId.value) {
      testPoints.value = []
      total.value = 0
      listStats.value = createEmptyStats()
      return
    }
    loading.value = true
    try {
      const response = await testPointApi.getList(selectedProjectId.value, {
        ...filters,
        created_from: dateRange.value[0],
        created_to: dateRange.value[1],
        page: page.value,
        page_size: pageSize.value,
      })
      testPoints.value = response.items
      total.value = response.total
      listStats.value = response.stats
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : '加载测试点失败')
      testPoints.value = []
      total.value = 0
      listStats.value = createEmptyStats()
    } finally {
      loading.value = false
    }
  }

  async function refreshManagementData(): Promise<void> {
    if (!selectedProjectId.value) return
    await Promise.all([loadRequirementOptions(), fetchTestPoints()])
  }

  async function loadRequirementOptions(): Promise<void> {
    if (!selectedProjectId.value) {
      requirementOptions.value = []
      return
    }
    try {
      requirementOptions.value = await testPointApi.getRequirementOptions(selectedProjectId.value)
    } catch (error) {
      requirementOptions.value = []
      ElMessage.error(error instanceof Error ? error.message : '加载需求列表失败')
    }
  }

  function resetProjectScopedState(): void {
    page.value = 1
    total.value = 0
    testPoints.value = []
    selectedRows.value = []
    requirementOptions.value = []
    currentTestPoint.value = null
    listStats.value = createEmptyStats()
    filters.module = ''
    filters.priority = undefined
    filters.requirement_id = undefined
    filters.created_by = ''
    filters.keyword = ''
    filters.sort_by = 'create_time'
    filters.sort_order = 'desc'
    dateRange.value = []
  }

  async function handleProjectChange(): Promise<void> {
    resetProjectScopedState()
    if (!selectedProjectId.value) return
    await refreshManagementData()
    maybeOpenInitialExtractDialog()
  }

  function handleSelectionChange(rows: TestPoint[]): void {
    selectedRows.value = rows
  }
  function openCreateDialog(): void {
    editingPoint.value = null
    formDialogVisible.value = true
  }
  function openEditDialog(row: TestPoint): void {
    editingPoint.value = row
    formDialogVisible.value = true
  }
  function openCasesDialog(row: TestPoint): void {
    currentTestPoint.value = row
    casesDialogVisible.value = true
  }
  function applyPriorityFilter(priority?: number): void {
    filters.priority = priority
    page.value = 1
    void fetchTestPoints()
  }
  function openXmindImportDialog(): void {
    xmindImportDialogVisible.value = true
  }
  function openExtractDialog(): void {
    extractDialogVisible.value = true
  }
  function openLegacyExtractGuide(): void {
    openExtractDialog()
  }
  function openTaskList(): void {
    if (!selectedProjectId.value) return
    void router.push(`/home/task/list/${selectedProjectId.value}`)
  }
  async function handleIngestSaved(): Promise<void> {
    await refreshManagementData()
  }

  function maybeOpenInitialExtractDialog(): void {
    if (hasConsumedInitialExtract.value || !selectedProjectId.value) return
    const shouldOpen = route.query.openExtract === '1' || Boolean(route.query.file_id)
    if (!shouldOpen) return
    hasConsumedInitialExtract.value = true
    if (route.query.file_id) {
      initialExtractFileId.value = Number(route.query.file_id)
    }
    extractDialogVisible.value = true
  }

  function requireSelectedProjectId(): number | null {
    if (!selectedProjectId.value) {
      ElMessage.warning('请先选择项目')
      return null
    }
    return selectedProjectId.value
  }

  async function handleDelete(row: TestPoint): Promise<void> {
    try {
      await ElMessageBox.confirm(`确定删除测试点"${row.point}"吗？`, '提示', { type: 'warning' })
      await testPointApi.delete(row.id, row.project_id)
      ElMessage.success('删除成功')
      await fetchTestPoints()
    } catch (error) {
      if (!isCancelError(error) && error instanceof Error && error.message) {
        ElMessage.error(error.message)
      }
    }
  }

  async function handleBatchDelete(): Promise<void> {
    const projectId = requireSelectedProjectId()
    if (!projectId) return
    try {
      await ElMessageBox.confirm('确定删除选中的测试点吗？', '提示', { type: 'warning' })
      await testPointApi.batchDelete(
        projectId,
        selectedRows.value.map((i) => i.id)
      )
      selectedRows.value = []
      ElMessage.success('批量删除成功')
      await fetchTestPoints()
    } catch (error) {
      if (!isCancelError(error) && error instanceof Error && error.message) {
        ElMessage.error(error.message)
      }
    }
  }

  async function startGenerate(testPointIds: number[]): Promise<void> {
    const projectId = requireSelectedProjectId()
    if (!projectId) return
    generateDialogVisible.value = true
    generating.value = true
    generateProgress.value = 0
    generateMessage.value = '准备开始生成...'
    generateStatus.value = 'running'
    try {
      const generator = await testPointApi.batchGenerateStream({
        project_id: projectId,
        test_point_ids: testPointIds,
      })
      for await (const progress of generator) {
        const sp = progress as AnalysisProgress
        generateProgress.value = sp.progress ?? generateProgress.value
        generateMessage.value = sp.message ?? '生成中...'
        if (sp.status === 'error') generateStatus.value = 'error'
        else if (sp.status === 'partial') generateStatus.value = 'partial'
        else if (sp.status === 'warning') {
          if (generateStatus.value === 'running') generateStatus.value = 'warning'
        } else if (sp.status === 'success' || sp.status === 'completed') {
          if (generateStatus.value === 'running') generateStatus.value = 'success'
        }
      }
      if (generateStatus.value === 'running') generateStatus.value = 'success'
      if (generateStatus.value === 'success') ElMessage.success('测试用例生成完成')
      else if (generateStatus.value === 'partial' || generateStatus.value === 'warning')
        ElMessage.warning(generateMessage.value || '测试用例部分生成成功，请检查结果')
      await fetchTestPoints()
    } catch (error) {
      generateStatus.value = 'error'
      generateMessage.value = error instanceof Error ? error.message : '生成失败'
      ElMessage.error(generateMessage.value)
    } finally {
      generating.value = false
    }
  }

  async function handleGenerate(row: TestPoint): Promise<void> {
    try {
      await ElMessageBox.confirm(`确定为"${row.point}"生成测试用例吗？`, '提示', {
        type: 'warning',
      })
      await startGenerate([row.id])
    } catch (error) {
      if (!isCancelError(error) && error instanceof Error && error.message)
        ElMessage.error(error.message)
    }
  }

  async function handleBatchGenerate(): Promise<void> {
    try {
      await ElMessageBox.confirm('确定为选中的测试点批量生成测试用例吗？', '提示', {
        type: 'warning',
      })
      await startGenerate(selectedRows.value.map((i) => i.id))
    } catch (error) {
      if (!isCancelError(error) && error instanceof Error && error.message)
        ElMessage.error(error.message)
    }
  }

  function handleSortChange({
    prop,
    order,
  }: {
    prop: string
    order: 'ascending' | 'descending' | null
  }): void {
    filters.sort_by = (prop as TestPointListParams['sort_by']) || 'create_time'
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
    void fetchTestPoints()
  }
  function handlePageSizeChange(size: number): void {
    pageSize.value = size
    page.value = 1
    void fetchTestPoints()
  }
  function resetFilters(): void {
    filters.module = ''
    filters.priority = undefined
    filters.requirement_id = undefined
    filters.created_by = ''
    filters.keyword = ''
    filters.sort_by = 'create_time'
    filters.sort_order = 'desc'
    dateRange.value = []
    page.value = 1
    void fetchTestPoints()
  }

  onMounted(async () => {
    await loadProjects()
    if (selectedProjectId.value) await handleProjectChange()
  })

  return {
    loading,
    generating,
    generateDialogVisible,
    generateProgress,
    generateMessage,
    generateStatus,
    xmindImportDialogVisible,
    extractDialogVisible,
    initialExtractFileId,
    projects,
    testPoints,
    requirementOptions,
    selectedRows,
    selectedProjectId,
    total,
    page,
    pageSize,
    dateRange,
    formDialogVisible,
    casesDialogVisible,
    editingPoint,
    currentTestPoint,
    listStats,
    filters,
    highCount,
    mediumCount,
    lowCount,
    statsTotal,
    generatedCaseCount,
    selectedProjectName,
    progressStatus,
    priorityText,
    priorityTagType,
    handleProjectChange,
    handleSelectionChange,
    openCreateDialog,
    openEditDialog,
    openCasesDialog,
    applyPriorityFilter,
    openXmindImportDialog,
    openExtractDialog,
    openLegacyExtractGuide,
    openTaskList,
    handleIngestSaved,
    handleDelete,
    handleBatchDelete,
    handleGenerate,
    handleBatchGenerate,
    handleSortChange,
    handlePageSizeChange,
    resetFilters,
    fetchTestPoints,
  }
}
