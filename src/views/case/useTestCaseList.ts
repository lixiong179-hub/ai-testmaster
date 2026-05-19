import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { caseApi, type TestCase, type TestCaseListParams, type TestCaseListResponse } from '@/api/case'
import projectApi, { type Project } from '@/api/project'

export function useTestCaseList() {
  const route = useRoute()
  const loading = ref(false)
  const projects = ref<Project[]>([])
  const selectedProjectId = ref<number | undefined>(undefined)
  const testCases = ref<TestCase[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const selectedRows = ref<TestCase[]>([])
  const filters = reactive<TestCaseListParams>({
    keyword: '', module: '', priority: undefined, case_type: undefined,
    status: undefined, created_by: '', sort_by: 'create_time', sort_order: 'desc',
  })
  const stats = reactive({ total: 0, automated: 0, manual: 0, highPriority: 0 })

  const initProjectId = Number(route.query.projectId || route.query.project_id)
  if (Number.isFinite(initProjectId) && initProjectId > 0) { selectedProjectId.value = initProjectId }

  const selectedProjectName = computed(() => projects.value.find((p) => p.id === selectedProjectId.value)?.name || '')

  async function loadProjects(): Promise<void> {
    try {
      const response = await projectApi.getProjects({ page: 1, page_size: 100 })
      projects.value = response.data.items
    } catch (error) { ElMessage.error(error instanceof Error ? error.message : '加载项目失败') }
  }

  async function fetchTestCases(): Promise<void> {
    if (!selectedProjectId.value) { testCases.value = []; total.value = 0; return }
    loading.value = true
    try {
      const response: TestCaseListResponse = await caseApi.getList(selectedProjectId.value, {
        ...filters, page: page.value, page_size: pageSize.value,
      })
      testCases.value = response.items
      total.value = response.total
      if (response.stats) { stats.total = response.stats.total; stats.automated = response.stats.automated; stats.manual = response.stats.manual; stats.highPriority = response.stats.high_priority }
    } catch (error) { ElMessage.error(error instanceof Error ? error.message : '加载用例失败'); testCases.value = []; total.value = 0 }
    finally { loading.value = false }
  }

  async function handleProjectChange(): Promise<void> {
    page.value = 1; total.value = 0; testCases.value = []; selectedRows.value = []
    if (selectedProjectId.value) { await fetchTestCases() }
  }

  function handleSelectionChange(rows: TestCase[]): void { selectedRows.value = rows }
  function handleSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }): void {
    filters.sort_by = (prop as TestCaseListParams['sort_by']) || 'create_time'
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
    void fetchTestCases()
  }
  function handlePageSizeChange(size: number): void { pageSize.value = size; page.value = 1; void fetchTestCases() }
  function resetFilters(): void {
    filters.keyword = ''; filters.module = ''; filters.priority = undefined
    filters.case_type = undefined; filters.status = undefined; filters.created_by = ''
    filters.sort_by = 'create_time'; filters.sort_order = 'desc'; page.value = 1
    void fetchTestCases()
  }

  async function handleDelete(row: TestCase): Promise<void> {
    try {
      await ElMessageBox.confirm(`确定删除用例"${row.title}"吗？`, '提示', { type: 'warning' })
      await caseApi.delete(row.id, row.project_id); ElMessage.success('删除成功'); await fetchTestCases()
    } catch (error) { if (error !== 'cancel' && error instanceof Error && error.message) ElMessage.error(error.message) }
  }

  async function handleBatchDelete(): Promise<void> {
    if (!selectedProjectId.value) return
    try {
      await ElMessageBox.confirm('确定删除选中的用例吗？', '提示', { type: 'warning' })
      await caseApi.batchDelete(selectedProjectId.value, selectedRows.value.map((i) => i.id))
      selectedRows.value = []; ElMessage.success('批量删除成功'); await fetchTestCases()
    } catch (error) { if (error !== 'cancel' && error instanceof Error && error.message) ElMessage.error(error.message) }
  }

  function getPriorityType(priority: number): string { return priority === 1 ? 'danger' : priority === 2 ? 'warning' : 'success' }
  function getPriorityLabel(priority: number): string { return priority === 1 ? '高' : priority === 2 ? '中' : '低' }
  function getTypeLabel(type: string): string { const m: Record<string, string> = { ui_automation: 'UI自动化', manual: '手工测试', api_automation: 'API自动化', performance: '性能测试', security: '安全测试' }; return m[type] || type }
  function getTypeTagType(type: string): string { const m: Record<string, string> = { ui_automation: 'primary', manual: 'info', api_automation: 'success', performance: 'warning', security: 'danger' }; return m[type] || 'info' }

  onMounted(async () => { await loadProjects(); if (selectedProjectId.value) await fetchTestCases() })

  return {
    loading, projects, selectedProjectId, testCases, total, page, pageSize,
    selectedRows, filters, stats, selectedProjectName, handleProjectChange,
    handleSelectionChange, handleSortChange, handlePageSizeChange, resetFilters,
    handleDelete, handleBatchDelete, fetchTestCases, getPriorityType,
    getPriorityLabel, getTypeLabel, getTypeTagType,
  }
}
