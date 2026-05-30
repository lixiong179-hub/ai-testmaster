import { useFlowSortStore } from '@/store/flowSort'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import type { TagType } from '@/types/element-plus'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'

export function createEditActions(state: GenerateState, computed: GenerateComputed) {
  const nextStep = () => {
    if (state.currentStep.value < 2) {
      state.currentStep.value++
    }
  }

  const prevStep = () => {
    if (state.currentStep.value > 0) {
      state.currentStep.value--
    }
  }

  const skipToStep2 = () => {
    state.currentStep.value = 1
  }

  const handleCaseTypeChange = (val: string) => {
    if (val !== 'ui_automation') {
      state.formData.exec_mode = 'all'
    }
  }

  const toggleCaseSelection = (index: number) => {
    const s = new Set(state.selectedCaseIndices.value)
    if (s.has(index)) {
      s.delete(index)
    } else {
      s.add(index)
    }
    state.selectedCaseIndices.value = s
  }

  const toggleSelectAll = () => {
    if (computed.allSelected.value) {
      state.selectedCaseIndices.value = new Set()
    } else {
      state.selectedCaseIndices.value = new Set(state.generatedCases.value.map((_, i) => i))
    }
  }

  const startEditResult = () => {
    const current = computed.viewingCase.value
    if (!current) return
    state.editingCase.value = {
      title: current.title || '',
      module: current.module || '',
      case_type: current.case_type || '',
      test_category: current.test_category || '',
      precondition: current.precondition || '',
      expected_result: current.expected_result || '',
      priority: current.priority || 2,
      steps: current.steps ? JSON.parse(JSON.stringify(current.steps)) : [],
      test_data: current.test_data || {},
    }
    state.isEditingResult.value = true
  }

  const cancelEditResult = () => {
    state.isEditingResult.value = false
  }

  const addEditStep = () => {
    state.editingCase.value.steps.push({
      step: state.editingCase.value.steps.length + 1,
      action: '',
      param: '',
      expected_result: '',
      test_data: {},
    })
  }

  const removeEditStep = (index: number) => {
    if (state.editingCase.value.steps.length > 1) {
      state.editingCase.value.steps.splice(index, 1)
      state.editingCase.value.steps.forEach((s, i) => {
        s.step = i + 1
      })
    }
  }

  const handleRetry = () => {
    state.errorMessage.value = ''
    state.errorSuggestions.value = []
  }

  const resetForm = () => {
    state.formData.scene = ''
    state.formData.case_type = ''
    state.formData.exec_mode = 'all'
    state.formData.priority = 2
    state.formData.extra_requirements = ''
    state.formData.enhanced_mode = true
    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.selectedCaseIndices.value = new Set()
    state.caseIdSeq.value = 0
    state.errorMessage.value = ''
    state.errorSuggestions.value = []
    state.isEditingResult.value = false
    state.lastContext.value = {}
    state.currentStep.value = 0
  }

  const getPriorityType = (priority: number): TagType => {
    const types: Record<number, TagType> = { 1: 'danger', 2: 'warning', 3: 'info', 4: 'success' }
    return types[priority] || 'info'
  }

  const getSelectedTagType = (id: number): TagType => {
    const point = state.testPointCache.get(id) || state.testPoints.value.find((p) => p.id === id)
    if (point) {
      return getPriorityType(point.priority)
    }
    return 'primary'
  }

  const getTypeTagType = (type: string): TagType => {
    const typeMap: Record<string, TagType> = {
      ui_automation: 'success',
      manual: 'info',
      api_automation: 'primary',
      performance: 'warning',
      security: 'danger',
      UI: 'success',
      API: 'primary',
      功能: 'info',
      功能测试: 'info',
      functional: 'info',
    }
    return typeMap[type] || 'info'
  }

  const getTypeLabel = (type: string): string => {
    const typeMap: Record<string, string> = {
      ui_automation: 'UI自动化',
      manual: '手工测试',
      api_automation: 'API自动化',
      performance: '性能测试',
      security: '安全测试',
      UI: 'UI自动化',
      API: 'API自动化',
      功能: '手工测试',
      功能测试: '手工测试',
      functional: '手工测试',
      接口: 'API自动化',
      接口测试: 'API自动化',
    }
    return typeMap[type] || type
  }

  const getPriorityTagType = (priority: unknown): TagType => {
    const priorityMap: Record<string, TagType> = {
      '1': 'danger',
      P0: 'danger',
      '2': 'warning',
      P2: 'warning',
      '3': 'info',
      P3: 'info',
    }
    return priorityMap[String(priority)] || 'info'
  }

  const getPriorityLabel = (priority: unknown): string => {
    const priorityMap: Record<string, string> = {
      '1': '高(P0)',
      P0: 'P0-高',
      '2': '中(P2)',
      P2: 'P2-中',
      '3': '低(P3)',
      P3: 'P3-低',
    }
    return priorityMap[String(priority)] || String(priority)
  }

  const getDataTypeLabel = (key: string | number): string => {
    const keyStr = String(key)
    const labelMap: Record<string, string> = {
      normal: '正向数据',
      boundary: '边界值',
      abnormal: '异常数据',
    }
    return labelMap[keyStr] || keyStr
  }

  const cleanExpectedResult = (text: string): string => {
    if (!text) return text
    return text.replace(/^【\d+】\s*/, '')
  }

  const handleFlowSortUpdate = (data: {
    mode: string
    nodes: FlowNodeData[]
    edges: FlowEdgeData[]
  }) => {
    state.formData.ui_screen_ids = data.nodes.map((n) => n.screen_id)
    const flowSortStore = useFlowSortStore()
    flowSortStore.updateNodes(data.nodes)
    flowSortStore.updateEdges(data.edges)
    flowSortStore.triggerAutoSave()
  }

  const resetGenerateState = () => {
    state.generating.value = false
    state.progress.value = 0
    state.errorMessage.value = ''
    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.selectedCaseIndices.value = new Set()
    state.caseIdSeq.value = 0
    state.contextStats.value = null
    state.serverWarnings.value = []
    state.evidenceRefs.value = null
  }

  return {
    nextStep,
    prevStep,
    skipToStep2,
    handleCaseTypeChange,
    toggleCaseSelection,
    toggleSelectAll,
    startEditResult,
    cancelEditResult,
    addEditStep,
    removeEditStep,
    handleRetry,
    resetForm,
    getPriorityType,
    getSelectedTagType,
    getTypeTagType,
    getTypeLabel,
    getPriorityTagType,
    getPriorityLabel,
    getDataTypeLabel,
    cleanExpectedResult,
    handleFlowSortUpdate,
    resetGenerateState,
  }
}
