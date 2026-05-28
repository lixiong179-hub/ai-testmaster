/**
 * 技术视图管理 Composable
 * 职责：技术视图数据获取、视图切换、定位状态标签/覆盖率格式化
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { TagType } from '@/types/element-plus'
import { testCaseViewApi } from '@/api/testCaseView'
import type { TechnicalView } from '@/api/testCaseView'

/** 视图类型常量 */
export const VIEW_TYPES = {
  BUSINESS: 'business',
  TECHNICAL: 'technical',
} as const

export type ViewType = (typeof VIEW_TYPES)[keyof typeof VIEW_TYPES]

/** 定位状态映射表 */
const LOCATOR_STATUS_MAP: Record<string, { label: string; type: TagType }> = {
  recorded: { label: '已定位', type: 'success' },
  pending: { label: '待定位', type: 'warning' },
  failed: { label: '定位失败', type: 'danger' },
}

export function useTechnicalView(caseId: { value: number }) {
  const currentView = ref<ViewType>(VIEW_TYPES.BUSINESS)
  const viewLoading = ref(false)
  const technicalViewData = ref<TechnicalView | null>(null)

  /** 获取技术视图数据 */
  const fetchTechnicalView = async () => {
    if (!caseId.value) return
    viewLoading.value = true
    try {
      technicalViewData.value = await testCaseViewApi.getTechnicalView(caseId.value)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string }
      console.error('获取技术视图失败:', error)
      const errorMsg = err.response?.data?.detail || err.message || '获取技术视图失败'
      ElMessage.error(errorMsg)
    } finally {
      viewLoading.value = false
    }
  }

  /** 切换视图，切换到技术视图时自动拉取数据 */
  const handleViewChange = async (view: ViewType) => {
    if (currentView.value === view) return
    currentView.value = view
    if (view === VIEW_TYPES.TECHNICAL) {
      await fetchTechnicalView()
    }
  }

  /** 获取定位状态对应的 Tag 类型 */
  const getLocatorStatusType = (status: string): TagType => {
    return LOCATOR_STATUS_MAP[status]?.type || 'info'
  }

  /** 获取定位状态对应的中文标签 */
  const getLocatorStatusLabel = (status: string): string => {
    return LOCATOR_STATUS_MAP[status]?.label || status
  }

  /** 格式化定位覆盖率显示 */
  const formatLocatorCoverage = (coverage: number | string): string => {
    if (typeof coverage === 'number') {
      return `${coverage.toFixed(1)}%`
    }
    if (typeof coverage === 'string' && coverage.endsWith('%')) {
      return coverage
    }
    return `${coverage}%`
  }

  return {
    currentView,
    viewLoading,
    technicalViewData,
    fetchTechnicalView,
    handleViewChange,
    getLocatorStatusType,
    getLocatorStatusLabel,
    formatLocatorCoverage,
  }
}
