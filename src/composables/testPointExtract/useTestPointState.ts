import { computed } from 'vue'
import request from '@/utils/request'
import type { ExtractSharedState, TestPointListResponse, TestPointItem } from './types'

export function useTestPointState(state: ExtractSharedState) {
  const progressStatus = computed(() => {
    if (state.progress.value === 100) return 'success'
    if (state.errorMessage.value) return 'exception'
    return ''
  })

  const paginatedTestPoints = computed(() => {
    if (state.savedFromDb.value) return state.testPoints.value
    const start = (state.currentPage.value - 1) * state.pageSize.value
    const end = start + state.pageSize.value
    return state.testPoints.value.slice(start, end)
  })

  const moduleCount = computed(() => {
    const modules = new Set(state.testPoints.value.map((tp) => tp.module || '未分类'))
    return modules.size
  })

  const totalDisplayCount = computed(() => {
    return state.savedFromDb.value ? state.dbTotal.value : state.testPoints.value.length
  })

  function getPriorityTagType(priority: number | string): string {
    const p = Number(priority)
    if (p === 1) return 'danger'
    if (p === 2) return 'warning'
    return 'info'
  }

  function getPriorityLabel(priority: number | string): string {
    const p = Number(priority)
    if (p === 1) return '高'
    if (p === 2) return '中'
    return '低'
  }

  function getPriorityCount(priority: number): number {
    return state.testPoints.value.filter((tp) => tp.priority === priority).length
  }

  function getModuleDistribution(): Record<string, number> {
    const distribution: Record<string, number> = {}
    state.testPoints.value.forEach((tp) => {
      const module = tp.module || '未分类'
      distribution[module] = (distribution[module] || 0) + 1
    })
    return distribution
  }

  async function loadSavedTestPoints(projectId: number, page = 1): Promise<void> {
    state.loadingTestPoints.value = true
    try {
      const response: TestPointListResponse = await request.get(
        `/api/v1/test-point/list/${projectId}`,
        {
          params: { page, page_size: state.pageSize.value },
        }
      )
      if (response?.code === 200 && response.data) {
        state.testPoints.value = (response.data.items || []) as TestPointItem[]
        state.dbTotal.value = response.data.total || 0
        state.savedFromDb.value = true
        state.currentPage.value = page
      }
    } catch (error) {
      console.error('加载测试点失败:', error)
    } finally {
      state.loadingTestPoints.value = false
    }
  }

  function handlePageChange(page: number): void {
    if (state.savedFromDb.value && state.formData.project_id) {
      loadSavedTestPoints(Number(state.formData.project_id), page)
    } else {
      state.currentPage.value = page
    }
  }

  function handleSelectionChange(rows: TestPointItem[]): void {
    state.selectedRows.value = rows
  }

  function clearSelection(): void {
    state.selectedRows.value = []
    if (state.testPointTable.value) {
      state.testPointTable.value.clearSelection()
    }
  }

  return {
    progressStatus,
    paginatedTestPoints,
    moduleCount,
    totalDisplayCount,
    getPriorityTagType,
    getPriorityLabel,
    getPriorityCount,
    getModuleDistribution,
    loadSavedTestPoints,
    handlePageChange,
    handleSelectionChange,
    clearSelection,
  }
}
