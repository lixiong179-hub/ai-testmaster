import { ref, computed, type Ref } from 'vue'
import { useCaseStore } from '@/store/case'
import type { TestCase } from '@/api/case'

/** 筛选表单状态类型 */
export interface CaseFilterForm {
  module: string
  priority: number | null
  case_type: string
  keyword: string
  lifecycle_status: string[]
}

/** 分页状态类型 */
export interface PaginationState {
  currentPage: number
  pageSize: number
}

export interface UseCaseFilterOptions {
  caseStore: ReturnType<typeof useCaseStore>
  pagination: Ref<PaginationState>
  selectedProjectId: Ref<number | null>
}

/** 用例筛选与统计 composable */
export function useCaseFilter(options: UseCaseFilterOptions) {
  const { caseStore, pagination, selectedProjectId } = options

  // 筛选条件
  const filter = ref<CaseFilterForm>({
    module: '',
    priority: null,
    case_type: '',
    keyword: '',
    lifecycle_status: [],
  })

  // 筛选区域展开状态
  const filterExpanded = ref(true)

  // 需求文件筛选
  const selectedRequirementFileId = ref<number | null>(null)

  // 是否有激活的筛选条件
  const hasActiveFilter = computed((): boolean => {
    return (
      filter.value.module !== '' ||
      filter.value.priority !== null ||
      filter.value.keyword !== '' ||
      filter.value.case_type !== '' ||
      filter.value.lifecycle_status.length > 0 ||
      selectedRequirementFileId.value !== null
    )
  })

  // ---- 统计数据计算 ----

  const successCount = computed((): number => {
    return caseStore.testCases.filter((c) => c.generate_status === 1).length
  })

  const failedCount = computed((): number => {
    return caseStore.testCases.filter((c) => c.generate_status === 2).length
  })

  const manualCount = computed((): number => {
    const MANUAL_TYPES = ['manual', '功能', '功能测试', 'functional']
    return caseStore.testCases.filter((c) => MANUAL_TYPES.includes(c.case_type)).length
  })

  const uiCount = computed((): number => {
    const UI_TYPES = ['ui_automation', 'UI', 'UI自动化']
    return caseStore.testCases.filter((c) => UI_TYPES.includes(c.case_type)).length
  })

  const apiCount = computed((): number => {
    const API_TYPES = ['api_automation', 'API', '接口']
    return caseStore.testCases.filter((c) => API_TYPES.includes(c.case_type)).length
  })

  const highPriorityCount = computed((): number => {
    return caseStore.testCases.filter((c) => c.priority === 1).length
  })

  const mediumPriorityCount = computed((): number => {
    return caseStore.testCases.filter((c) => c.priority === 2).length
  })

  const lowPriorityCount = computed((): number => {
    return caseStore.testCases.filter((c) => c.priority === 3).length
  })

  // 模块列表（去重排序）
  const modules = computed((): string[] => {
    const moduleSet = new Set<string>()
    caseStore.testCases.forEach((caseItem) => {
      if (caseItem.module) moduleSet.add(caseItem.module)
    })
    return Array.from(moduleSet).sort()
  })

  // 筛选后的测试用例
  const filteredTestCases = computed((): TestCase[] => {
    let filtered = caseStore.testCases

    if (selectedRequirementFileId.value !== null) {
      filtered = filtered.filter(
        (caseItem) => (caseItem as any).requirement_file_id === selectedRequirementFileId.value
      )
    }

    if (filter.value.lifecycle_status.length > 0) {
      filtered = filtered.filter((caseItem) =>
        filter.value.lifecycle_status.includes(caseItem.lifecycle_status || 'active')
      )
    }

    if (filter.value.module) {
      filtered = filtered.filter((caseItem) => caseItem.module === filter.value.module)
    }

    if (filter.value.priority !== null) {
      filtered = filtered.filter((caseItem) => caseItem.priority === filter.value.priority)
    }

    if (filter.value.case_type) {
      filtered = filtered.filter((caseItem) => caseItem.case_type === filter.value.case_type)
    }

    if (filter.value.keyword) {
      const keyword = filter.value.keyword.toLowerCase()
      filtered = filtered.filter(
        (caseItem) =>
          (caseItem.title && caseItem.title.toLowerCase().includes(keyword)) ||
          (caseItem.case_no && caseItem.case_no.toLowerCase().includes(keyword))
      )
    }

    return filtered
  })

  // ---- 筛选操作方法 ----

  /** 筛选条件变更时重置分页到第一页 */
  const handleFilterChange = (): void => {
    pagination.value.currentPage = 1
  }

  /** 点击统计卡片快速筛选 */
  const applyStatsCardFilter = (caseType: string | null): void => {
    if (caseType === null) {
      filter.value = {
        module: '',
        priority: null,
        case_type: '',
        keyword: '',
        lifecycle_status: [],
      }
    } else {
      filter.value = { ...filter.value, case_type: caseType }
    }
    handleFilterChange()
  }

  /** 重置全部筛选条件 */
  const resetFilter = (): void => {
    filter.value = { module: '', priority: null, case_type: '', keyword: '', lifecycle_status: [] }
    selectedRequirementFileId.value = null
    pagination.value.currentPage = 1
    // 重新加载当前项目的全部用例
    if (selectedProjectId.value) {
      caseStore.fetchTestCases(selectedProjectId.value)
    }
  }

  return {
    filter,
    filterExpanded,
    selectedRequirementFileId,
    hasActiveFilter,
    successCount,
    failedCount,
    manualCount,
    uiCount,
    apiCount,
    highPriorityCount,
    mediumPriorityCount,
    lowPriorityCount,
    modules,
    filteredTestCases,
    handleFilterChange,
    applyStatsCardFilter,
    resetFilter,
  }
}
