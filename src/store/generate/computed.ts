import { computed, watch } from 'vue'
import type { ComputedRef } from 'vue'
import type { UIPrototypeProject } from '@/api/uiPrototype'
import type { TestPoint } from '@/api/testPoint'
import type { GeneratedCase } from './types'
import type { GenerateState } from './state'

export interface GenerateComputed {
  selectedUiPrototypeProject: ComputedRef<UIPrototypeProject | null>
  flowSortModuleInfo: ComputedRef<{ name: string; description: string }>
  screenPreviewStatusType: ComputedRef<string>
  screenPreviewStatusText: ComputedRef<string>
  viewingCase: ComputedRef<GeneratedCase | null>
  selectedTestPointsForDisplay: ComputedRef<Array<TestPoint | { id: number; module: string; function: string; point: string; priority: number }>>
  canGenerate: ComputedRef<boolean>
  generateButtonLabel: ComputedRef<string>
  progressStatus: ComputedRef<string>
  allSelected: ComputedRef<boolean>
  hasSelected: ComputedRef<boolean>
  selectedCount: ComputedRef<number>
}

export function createGenerateComputed(state: GenerateState): GenerateComputed {
  const selectedUiPrototypeProject = computed(() => {
    if (!state.selectedUiPrototypeProjectId.value) return null
    return (
      state.uiPrototypeProjects.value.find(
        (p) => p.id === state.selectedUiPrototypeProjectId.value
      ) || null
    )
  })

  const flowSortModuleInfo = computed(() => {
    if (!selectedUiPrototypeProject.value) return { name: '', description: '' }
    return {
      name: selectedUiPrototypeProject.value.name || '',
      description: selectedUiPrototypeProject.value.description || '',
    }
  })

  const screenPreviewStatusType = computed(() => {
    const status = selectedUiPrototypeProject.value?.parse_status
    if (status === 'completed') return 'success'
    if (status === 'partial') return 'warning'
    if (status === 'failed') return 'danger'
    return 'info'
  })

  const screenPreviewStatusText = computed(() => {
    const project = selectedUiPrototypeProject.value
    if (!project) return '未选择版本'
    if (project.parse_status === 'completed') return '全部已解析'
    if (project.parse_status === 'partial') {
      return `部分解析 ${project.parsed_count || 0}/${project.screen_count || state.uiScreens.value.length}`
    }
    if (project.parse_status === 'failed') return '解析失败'
    return '待解析'
  })

  const viewingCase = computed(() => {
    if (
      state.currentCaseIndex.value >= 0 &&
      state.currentCaseIndex.value < state.generatedCases.value.length
    ) {
      return state.generatedCases.value[state.currentCaseIndex.value]
    }
    return state.generatedCases.value[0] || null
  })

  const selectedTestPointsForDisplay = computed(() => {
    const ids = state.formData.test_point_ids.slice(0, 5)
    return ids.map((id) => {
      const tp =
        state.testPoints.value.find((p) => p.id === id) ||
        state.formData.test_points_data.find((p) => p.id === id)
      return tp || { id, module: '?', function: '?', point: '未知测试点', priority: 2 }
    })
  })

  const canGenerate = computed(() => {
    return (
      state.formData.test_point_ids.length > 0 ||
      state.formData.requirement_file_ids.length > 0 ||
      state.formData.ui_file_ids.length > 0 ||
      state.formData.ui_screen_ids.length > 0 ||
      state.selectedHistoryCaseIds.value.length > 0
    )
  })

  const generateButtonLabel = computed(() => {
    const count = state.formData.test_point_ids.length
    if (count > 0) return `${count} 个测试用例`
    if (state.formData.requirement_file_ids.length > 0) {
      return `${state.formData.requirement_file_ids.length} 份需求`
    }
    if (state.formData.ui_screen_ids.length > 0) {
      return `${state.formData.ui_screen_ids.length} 个屏幕`
    }
    if (state.selectedHistoryCaseIds.value.length > 0) {
      return `${state.selectedHistoryCaseIds.value.length} 条历史用例`
    }
    if (state.formData.case_type === 'api_automation') return '接口用例'
    return '开始'
  })

  const progressStatus = computed(() => {
    if (state.progress.value === 100) return 'success'
    if (state.errorMessage.value) return 'exception'
    return ''
  })

  const allSelected = computed(
    () =>
      state.generatedCases.value.length > 0 &&
      state.generatedCases.value.every((_, i) => state.selectedCaseIndices.value.has(i))
  )

  const hasSelected = computed(() => state.selectedCaseIndices.value.size > 0)

  const selectedCount = computed(() => state.selectedCaseIndices.value.size)

  watch(state.currentCaseIndex, () => {
    state.isEditingResult.value = false
  })

  return {
    selectedUiPrototypeProject,
    flowSortModuleInfo,
    screenPreviewStatusType,
    screenPreviewStatusText,
    viewingCase,
    selectedTestPointsForDisplay,
    canGenerate,
    generateButtonLabel,
    progressStatus,
    allSelected,
    hasSelected,
    selectedCount,
  }
}
