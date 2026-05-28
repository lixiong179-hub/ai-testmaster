import { type InjectionKey, inject, provide, ref, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { TagType } from '@/types/element-plus'
import { testCaseApi } from '@/api/case'
import { testCaseViewApi } from '@/api/testCaseView'
import { downloadFromResponse, parseBlobError } from '@/utils/download'
import { createQuickVerify } from '@/api/testExecution'
import type { TestCase } from '@/types/testCase'
import { useCaseEdit } from '@/composables/useCaseEdit'
import { useTechnicalView, VIEW_TYPES } from '@/composables/useTechnicalView'
import { useCellEdit } from '@/composables/useCellEdit'
import { getLocatorTypeLabel, getLocatorTypeTagType } from '@/utils/locatorType'

const PRIORITY_MAP: Record<number, { label: string; type: TagType }> = {
  1: { label: '高(P1)', type: 'danger' },
  2: { label: '中(P2)', type: 'warning' },
  3: { label: '低(P3)', type: 'success' },
}

export type CaseDetailContext = ReturnType<typeof createCaseDetailContext>
export const CASE_DETAIL_KEY: InjectionKey<CaseDetailContext> = Symbol('caseDetail')

function createCaseDetailContext() {
  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const lineageExpanded = ref(false)
  const isCorrectionMode = ref(false)
  const correctionStepIndex = ref(-1)
  const issueType = ref<'case_issue' | 'product_bug' | 'needs_review'>('case_issue')
  const failureReason = ref('')
  const aiAnalysisText = ref('')
  const showSuggestionPanel = ref(true)
  const quickVerifyVisible = ref(false)
  const quickVerifyLoading = ref(false)
  const selectedVerifySteps = ref<number[]>([])
  const versionHistoryVisible = ref(false)
  const versionList = ref<any[]>([])
  const versionLoading = ref(false)
  const versionTotal = ref(0)
  const versionPage = ref(1)
  const rollbackLoading = ref(false)
  const addLocatorVisible = ref(false)
  const addLocatorLoading = ref(false)
  const addLocatorStepIndex = ref(-1)
  const batchLocatorVisible = ref(false)
  const addLocatorForm = ref({
    css_selector: '',
    xpath: '',
    ai_coordinate: '',
    locator_type: 'css',
  })
  const parsePreconditionLoading = ref(false)
  const caseItem = ref<TestCase | null>(null)
  const exportingExcel = ref(false)

  const businessSteps = computed(() => caseItem.value?.steps || [])
  const caseId = computed(() => Number(route.params.caseId) || 0)

  const fetchCaseDetail = async () => {
    if (!caseId.value) return
    loading.value = true
    try {
      caseItem.value = (await testCaseApi.getCase(caseId.value)) as TestCase
      if (caseItem.value && !caseItem.value.steps) caseItem.value.steps = []
      initEditForm()
    } catch (error: any) {
      console.error('获取用例详情失败:', error)
      ElMessage.error(error.response?.data?.detail || error.message || '获取用例详情失败')
    } finally {
      loading.value = false
    }
  }

  const { isEditing, saving, editForm, initEditForm, toggleEdit, cancelEdit, saveEdit } =
    useCaseEdit(caseItem, caseId, fetchCaseDetail)
  const {
    currentView,
    viewLoading,
    technicalViewData,
    fetchTechnicalView,
    handleViewChange,
    getLocatorStatusType,
    getLocatorStatusLabel,
    formatLocatorCoverage,
  } = useTechnicalView(caseId)
  const { editingCell, editingValue, cellSaving, startCellEdit, cancelCellEdit, saveCellEdit } =
    useCellEdit(caseId, technicalViewData, issueType)

  const handleExportExcel = async () => {
    if (!caseId.value) return
    exportingExcel.value = true
    try {
      const resp = await testCaseViewApi.exportToExcel(caseId.value)
      const fallback = `${caseItem.value?.case_no || `case_${caseId.value}`}.xlsx`
      downloadFromResponse(resp, fallback)
      ElMessage.success('导出成功')
    } catch (err) {
      const msg = await parseBlobError(err, '导出Excel失败')
      console.error('导出Excel失败:', err)
      ElMessage.error(msg)
    } finally {
      exportingExcel.value = false
    }
  }

  const getPriorityType = (priority: number): TagType => PRIORITY_MAP[priority]?.type || 'info'
  const getPriorityLabel = (priority: number) => PRIORITY_MAP[priority]?.label || '中(P2)'

  const getCaseTypeLabel = (type?: string) => {
    const m: Record<string, string> = {
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
    }
    return m[type || ''] || type || '-'
  }
  const getTestCategoryLabel = (category?: string) => getCaseTypeLabel(category)

  const formatTime = (time?: string) => {
    if (!time) return '-'
    try {
      return new Date(time).toLocaleString('zh-CN')
    } catch {
      return time
    }
  }

  const addStep = () => {
    editForm.value.steps.push({ _uid: Date.now() + Math.random(), action: '', expected_result: '' })
  }
  const removeStep = (index: number) => {
    if (editForm.value.steps.length > 1) editForm.value.steps.splice(index, 1)
  }

  const copyCase = async () => {
    if (!caseItem.value) return
    const t =
      `用例编号: ${caseItem.value.case_no}\n模块: ${caseItem.value.module || '-'}\n` +
      `标题: ${caseItem.value.title}\n前置条件: ${caseItem.value.precondition || '-'}\n` +
      `测试步骤:\n${(caseItem.value.steps || []).map((s, i) => `${i + 1}. ${s.display_action || s.description || s.action || '-'}\n   预期结果: ${s.expected_result || '-'}`).join('\n')}\n` +
      `总体预期结果: ${caseItem.value.expected_result || '-'}\n优先级: ${getPriorityLabel(caseItem.value.priority)}\n` +
      `用例类型: ${caseItem.value.case_type || '-'}`
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(t)
        ElMessage.success('用例已复制到剪贴板')
      } else {
        const ta = document.createElement('textarea')
        ta.value = t
        ta.style.position = 'fixed'
        ta.style.left = '-999999px'
        ta.style.top = '-999999px'
        document.body.appendChild(ta)
        ta.focus()
        ta.select()
        try {
          document.execCommand('copy')
            ? ElMessage.success('用例已复制到剪贴板')
            : ElMessage.error('复制失败，请手动复制')
        } catch {
          ElMessage.error('复制失败，请手动复制')
        } finally {
          document.body.removeChild(ta)
        }
      }
    } catch {
      ElMessage.error('复制失败，请手动复制')
    }
  }

  const parsePrecondition = async () => {
    if (!caseId.value) return
    parsePreconditionLoading.value = true
    try {
      const res = await testCaseViewApi.parsePrecondition(caseId.value)
      const data = (res as any).data
      if (data) {
        const steps = Array.isArray(data) ? data : []
        if (steps.length > 0) {
          ElMessage.success(`AI解析成功，生成 ${steps.length} 个步骤`)
          if (technicalViewData.value) technicalViewData.value.precondition_steps = steps
        } else {
          ElMessage.info('AI未解析出可执行步骤')
        }
      }
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || 'AI解析失败')
    } finally {
      parsePreconditionLoading.value = false
    }
  }

  const savePreconditionSteps = async (steps: any[]) => {
    if (!caseId.value) return
    try {
      await testCaseViewApi.batchSavePreconditionSteps(caseId.value, { steps })
    } catch {
      ElMessage.error('保存前置条件步骤失败')
    }
  }

  const addPreconditionStep = () => {
    if (!technicalViewData.value) return
    const steps = [...(technicalViewData.value.precondition_steps || [])]
    steps.push({
      step_number: steps.length + 1,
      action: '新步骤',
      expected_result: '',
      action_type: 'click',
      input_value: '',
      target_element: '',
      has_locator: false,
      locator_status: 'pending',
    })
    technicalViewData.value.precondition_steps = steps
    savePreconditionSteps(steps)
  }

  const deletePreconditionStep = async (index: number) => {
    if (!technicalViewData.value) return
    const steps = [...(technicalViewData.value.precondition_steps || [])]
    steps.splice(index, 1)
    steps.forEach((s: any, i: number) => {
      s.step_number = i + 1
    })
    await savePreconditionSteps(steps)
    technicalViewData.value.precondition_steps = steps
  }

  const getActionTypeTagType = (actionType: string): TagType => {
    const m: Record<string, TagType> = {
      click: 'primary',
      input: 'success',
      navigate: 'warning',
      verify: 'info',
      select: 'success',
      wait: 'info',
      hover: 'primary',
      scroll: 'info',
      refresh: 'info',
      keypress: 'info',
    }
    return m[actionType] || 'info'
  }

  const goBack = () => router.push('/home/case')
  const getStepRowClass = ({ rowIndex }: { row: any; rowIndex: number }) =>
    isCorrectionMode.value && rowIndex === correctionStepIndex.value ? 'highlighted-step' : ''

  const handleCorrectionParams = async () => {
    const query = route.query
    if (query.correction !== 'true') return
    isCorrectionMode.value = true
    correctionStepIndex.value = Number(query.stepIndex) || -1
    issueType.value = (query.issueType as any) || 'case_issue'
    failureReason.value = query.failureReason
      ? decodeURIComponent(query.failureReason as string)
      : ''
    aiAnalysisText.value = query.aiAnalysis ? decodeURIComponent(query.aiAnalysis as string) : ''
    if (issueType.value === 'product_bug') isEditing.value = false
    currentView.value = VIEW_TYPES.TECHNICAL
    await fetchTechnicalView()
    if (issueType.value !== 'product_bug' && caseId.value) {
      try {
        await testCaseApi.startCorrection(caseId.value)
      } catch (error: any) {
        console.error('设置纠正状态失败:', error)
      }
    }
    await nextTick()
    const highlightedRow = document.querySelector('.highlighted-step')
    if (highlightedRow) highlightedRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const openQuickVerify = () => {
    if (!technicalViewData.value) return
    selectedVerifySteps.value = technicalViewData.value.steps.map((s) => s.step_number)
    quickVerifyVisible.value = true
  }

  const executeQuickVerify = async () => {
    if (selectedVerifySteps.value.length === 0) {
      ElMessage.warning('请至少选择一个步骤')
      return
    }
    quickVerifyLoading.value = true
    try {
      await createQuickVerify(caseId.value, selectedVerifySteps.value)
      await testCaseApi.submitVerification(caseId.value)
      ElMessage.success('快速验证任务已创建，即将跳转到执行页面')
      quickVerifyVisible.value = false
      router.push('/home/task/execution/' + caseId.value)
    } catch (error: any) {
      console.error('创建快速验证任务失败:', error)
      ElMessage.error(error.response?.data?.detail || '创建快速验证任务失败')
    } finally {
      quickVerifyLoading.value = false
    }
  }

  const openVersionHistory = () => {
    versionHistoryVisible.value = true
    versionPage.value = 1
    fetchVersionHistory()
  }
  const fetchVersionHistory = async () => {
    if (!caseId.value) return
    versionLoading.value = true
    try {
      const res = await testCaseApi.getCaseVersions(caseId.value, versionPage.value, 20)
      versionList.value = res.items || []
      versionTotal.value = res.total || versionList.value.length
    } catch (error: any) {
      console.error('获取版本历史失败:', error)
      ElMessage.error(error.response?.data?.detail || '获取版本历史失败')
    } finally {
      versionLoading.value = false
    }
  }

  const handleRollback = async (version: any) => {
    rollbackLoading.value = true
    try {
      await testCaseApi.rollbackCaseVersion(caseId.value, version.id)
      ElMessage.success(`已回滚到版本 v${version.version_number}`)
      versionHistoryVisible.value = false
      await fetchCaseDetail()
      if (currentView.value === VIEW_TYPES.TECHNICAL) await fetchTechnicalView()
    } catch (error: any) {
      console.error('回滚失败:', error)
      ElMessage.error(error.response?.data?.detail || '回滚失败')
    } finally {
      rollbackLoading.value = false
    }
  }

  const openAddLocator = (stepIndex: number, _row: any) => {
    addLocatorStepIndex.value = stepIndex
    addLocatorForm.value = { css_selector: '', xpath: '', ai_coordinate: '', locator_type: 'css' }
    addLocatorVisible.value = true
  }

  const saveAddLocator = async () => {
    if (!technicalViewData.value) return
    const step = technicalViewData.value.steps[addLocatorStepIndex.value]
    if (!step) return
    const { css_selector, xpath, ai_coordinate } = addLocatorForm.value
    if (!css_selector && !xpath && !ai_coordinate) {
      ElMessage.warning('请至少填写一种定位信息')
      return
    }
    addLocatorLoading.value = true
    try {
      const stepId = step.step_id || step.step_number
      await testCaseApi.updateStepLocator(caseId.value, stepId, {
        css_selector,
        xpath,
        ai_coordinate,
      })
      if (!step.locator) step.locator = {} as any
      if (css_selector) (step.locator as any).css_selector = css_selector
      if (xpath) (step.locator as any).xpath = xpath
      step.locator_status = 'recorded'
      ElMessage.success('定位信息添加成功')
      addLocatorVisible.value = false
    } catch (error: any) {
      console.error('添加定位失败:', error)
      ElMessage.error(error.response?.data?.detail || '添加定位失败')
    } finally {
      addLocatorLoading.value = false
    }
  }

  const init = async () => {
    if (caseId.value) {
      await fetchCaseDetail()
      await handleCorrectionParams()
    }
  }

  return {
    loading,
    lineageExpanded,
    isCorrectionMode,
    correctionStepIndex,
    issueType,
    failureReason,
    aiAnalysisText,
    showSuggestionPanel,
    quickVerifyVisible,
    quickVerifyLoading,
    selectedVerifySteps,
    versionHistoryVisible,
    versionList,
    versionLoading,
    versionTotal,
    versionPage,
    rollbackLoading,
    addLocatorVisible,
    addLocatorLoading,
    addLocatorStepIndex,
    batchLocatorVisible,
    addLocatorForm,
    parsePreconditionLoading,
    caseItem,
    exportingExcel,
    businessSteps,
    caseId,
    isEditing,
    saving,
    editForm,
    toggleEdit,
    cancelEdit,
    saveEdit,
    currentView,
    viewLoading,
    technicalViewData,
    fetchTechnicalView,
    handleViewChange,
    getLocatorStatusType,
    getLocatorStatusLabel,
    formatLocatorCoverage,
    editingCell,
    editingValue,
    cellSaving,
    startCellEdit,
    cancelCellEdit,
    saveCellEdit,
    handleExportExcel,
    getPriorityType,
    getPriorityLabel,
    getCaseTypeLabel,
    getTestCategoryLabel,
    formatTime,
    addStep,
    removeStep,
    copyCase,
    parsePrecondition,
    addPreconditionStep,
    deletePreconditionStep,
    getActionTypeTagType,
    goBack,
    getStepRowClass,
    handleCorrectionParams,
    openQuickVerify,
    executeQuickVerify,
    openVersionHistory,
    fetchVersionHistory,
    handleRollback,
    openAddLocator,
    saveAddLocator,
    init,
    VIEW_TYPES,
    getLocatorTypeLabel,
    getLocatorTypeTagType,
  }
}

export function provideCaseDetail() {
  const ctx = createCaseDetailContext()
  provide(CASE_DETAIL_KEY, ctx)
  return ctx
}

export function useCaseDetail() {
  const ctx = inject(CASE_DETAIL_KEY)
  if (!ctx) throw new Error('CaseDetail context not provided')
  return ctx
}

export { PRIORITY_MAP, VIEW_TYPES }
