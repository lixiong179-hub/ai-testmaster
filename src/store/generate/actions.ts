import { computed, watch } from 'vue'
import type { ComputedRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import caseApi from '@/api/case'
import type { TestCaseAIEnhancedRequest, TestCaseApiStep } from '@/api/case'
import { fileApi } from '@/api/file'
import ProjectAPI, { type ProjectListResponse } from '@/api/project'
import type { Project } from '@/api/project'
import { testPointApi, type TestPoint } from '@/api/testPoint'
import { uiPrototypeApi, type UIScreen } from '@/api/uiPrototype'
import { useFlowSortStore, type FlowEdgeData, type FlowNodeData } from '@/store/flowSort'
import type { TagType, ProgressStatus } from '@/types/element-plus'
import type { UIPrototypeProject } from '@/api/uiPrototype'
import { type ApiResponse } from '@/utils/request'
import {
  getGenerationCapabilityQuality,
  type GenerationContextQuality,
} from '@/types/generationCapability'
import type {
  GeneratedStep,
  GeneratedCase,
  SaveSingleCaseParam,
  StoreActions,
  ContextStats,
  ServerWarning,
  EvidenceRefs,
  GenerateState,
} from './state'
import { extractListItems, generateCaseNo, normalizePriority, TEST_POINT_CACHE_MAX } from './state'

// ========== generateHelpers 内部类型与函数 ==========

interface FlowSortEditorRef {
  getFlowSortSubmitData?: () => { flow_sort_data: Record<string, unknown> }
  getFlowValidationIssues?: () => { errors: string[]; warnings: string[] }
}

interface ActiveUiFlowStore {
  quickMode: boolean
  nodes: { length: number }
}

function getFlowNodeKeys(node: { id?: string; screen_id?: unknown }): string[] {
  const keys: string[] = []
  if (node.screen_id !== undefined && node.screen_id !== null) {
    keys.push(String(node.screen_id))
  }
  if (node.id) {
    keys.push(String(node.id))
  }
  return keys
}

function getEdgeEndpoint(edge: Record<string, unknown>, key: 'source' | 'target'): string {
  return String(edge[key] ?? '')
}

function edgeTouchesNode(
  edge: Record<string, unknown>,
  node: { id?: string; screen_id?: unknown }
): boolean {
  const nodeKeys = new Set(getFlowNodeKeys(node))
  return (
    nodeKeys.has(getEdgeEndpoint(edge, 'source')) || nodeKeys.has(getEdgeEndpoint(edge, 'target'))
  )
}

function getScreenId(item: unknown): number | null {
  if (!item || typeof item !== 'object') return null
  const raw = (item as Record<string, unknown>).screen_id
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

function parseUiDescriptionItems(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (typeof value !== 'string' || !value.trim()) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function filterItemsByScreenIds(items: unknown, screenIds: Set<number>): unknown[] {
  if (!Array.isArray(items)) return []
  return items.filter((item) => {
    const screenId = getScreenId(item)
    return screenId !== null && screenIds.has(screenId)
  })
}

function filterContextForScreens(
  context: Record<string, unknown>,
  nodes: Array<{ screen_id?: unknown }>
): Record<string, unknown> {
  const screenIds = new Set(
    nodes.map((node) => Number(node.screen_id)).filter((id) => Number.isFinite(id))
  )
  if (screenIds.size === 0) return context

  const scopedContext: Record<string, unknown> = { ...context }
  const filteredUiSpecs = filterItemsByScreenIds(context.ui_specs, screenIds)
  if (Array.isArray(context.ui_specs)) {
    scopedContext.ui_specs = filteredUiSpecs
  }

  const uiDescriptions = Array.isArray(context.ui_descriptions)
    ? context.ui_descriptions
    : parseUiDescriptionItems(context.ui_description)
  if (uiDescriptions.length > 0) {
    const filteredUiDescriptions = filterItemsByScreenIds(uiDescriptions, screenIds)
    scopedContext.ui_descriptions = filteredUiDescriptions
    scopedContext.ui_description = JSON.stringify(filteredUiDescriptions)
  }

  return scopedContext
}

export function hasActiveUiFlow(state: GenerateState, flowSortStore: ActiveUiFlowStore): boolean {
  if (flowSortStore.quickMode === true) return false
  return Boolean(
    state.selectedUiPrototypeProjectId.value &&
    state.formData.ui_screen_ids.length > 0 &&
    (flowSortStore.nodes.length > 0 || state.uiScreens.value.length > 0)
  )
}

async function callAiAndSaveResults(
  apiData: Record<string, unknown>,
  state: GenerateState,
  getActions: () => StoreActions,
  testPointId: number | null,
  label: string
): Promise<void> {
  const generateResult = await caseApi.aiGenerateCaseEnhanced(
    apiData as unknown as TestCaseAIEnhancedRequest
  )
  const casesData = generateResult.cases

  for (let cIdx = 0; cIdx < casesData.length; cIdx++) {
    const caseData = casesData[cIdx]
    state.generatedCases.value.push({
      id: getActions().nextCaseId(),
      test_point_id: testPointId,
      test_point_label: `${label} - ${caseData.case_category || '正向'}`,
      title: caseData.title || caseData.name || `${label} 测试用例`,
      module: caseData.module || '',
      case_type: caseData.case_type || caseData.type || state.formData.case_type,
      test_category: caseData.test_category || caseData.case_category || '',
      precondition: caseData.precondition || '',
      test_data: caseData.test_data,
      steps: (caseData.steps || []) as GeneratedStep[],
      expected_result: caseData.expected_result || '',
      priority: caseData.priority || state.formData.priority,
      scene: state.formData.scene,
      ai_change_type: caseData.change_type || 'added',
      parent_case_id: caseData.parent_case_id ?? null,
    })

    state.progressText.value = `正在保存 ${caseData.title || '用例'}...`
    const saved = await getActions().saveSingleCaseToDb(
      state.generatedCases.value[state.generatedCases.value.length - 1]
    )
    if (!saved) {
      state.generatedCases.value[state.generatedCases.value.length - 1]._error = '保存失败'
    }
  }
}

function pushErrorCase(
  state: GenerateState,
  getActions: () => StoreActions,
  testPointId: number | null,
  label: string,
  module: string,
  error: unknown
): void {
  const err = error as {
    response?: { data?: { detail?: string } }
    message?: string
  }
  state.generatedCases.value.push({
    id: getActions().nextCaseId(),
    test_point_id: testPointId,
    test_point_label: label,
    title: `${label} 测试用例（生成失败）`,
    module,
    case_type: state.formData.case_type,
    precondition: '',
    test_data: {},
    steps: [],
    expected_result: '',
    priority: state.formData.priority,
    _error: err.response?.data?.detail || err.message || '生成失败',
    scene: state.formData.scene,
    ai_change_type: 'added',
    parent_case_id: null,
  })
}

export function buildFlowSortData(
  state: GenerateState,
  computed: GenerateComputed,
  flowSortEditorRef: FlowSortEditorRef | null
): Record<string, unknown> {
  const flowSortStore = useFlowSortStore()
  const flowSortSubmitData = flowSortEditorRef?.getFlowSortSubmitData?.()
  return (
    flowSortSubmitData?.flow_sort_data || {
      nodes:
        flowSortStore.nodes.length > 0
          ? [...flowSortStore.nodes]
              .sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
              .map((n, index) => ({
                screen_id: n.screen_id,
                screen_order: index + 1,
                flow_type: n.flow_type,
                main_order: n.main_order,
                screen_name: n.screen_name,
                ui_spec_elements: n.ui_spec_elements || [],
                summary: n.summary || '',
                flow_meta: n.flow_meta || undefined,
              }))
          : state.uiScreens.value.map((screen, index) => ({
              screen_id: screen.id,
              screen_order: index + 1,
              flow_type: 'main' as const,
              screen_name: screen.screen_name,
              ui_spec_elements: screen.ui_spec?.elements || [],
              summary: screen.summary || '',
            })),
      edges: flowSortStore.edges.map((e) => ({
        source: String(e.source),
        target: String(e.target),
        edge_type: e.edge_type,
        condition: e.condition || '',
        label: e.label || '',
        trigger_action: e.trigger_action || '',
        pre_action: e.pre_action || '',
        note: e.note || '',
      })),
      module_info: computed.flowSortModuleInfo.value,
    }
  )
}

export async function generateForTestPoints(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions,
  context: Record<string, unknown>,
  targetPoints: number[],
  flowSortEditorRef: FlowSortEditorRef | null
): Promise<void> {
  const total = targetPoints.length
  let completed = 0
  const allTestPoints = (context.test_points || []) as TestPoint[]
  const flowSortStore = useFlowSortStore()
  const useGraphMode = hasActiveUiFlow(state, flowSortStore)

  const progressInterval = setInterval(() => {
    const targetPct = Math.min(70, 25 + Math.round((completed / total) * 45))
    if (state.progress.value < targetPct) {
      state.progress.value = targetPct
      state.progressText.value = `AI生成中... ${completed}/${total}`
    }
  }, 500)

  for (let i = 0; i < targetPoints.length; i++) {
    if (!state.generating.value) break

    const tpId = targetPoints[i]
    const tpInfo = allTestPoints.find((tp) => tp.id === tpId)
    const tpLabel = tpInfo ? `${tpInfo.module} - ${tpInfo.point}` : `测试点#${tpId}`

    try {
      const apiData: Record<string, unknown> = {
        project_id: Number(state.formData.project_id),
        description: state.formData.scene || `为"${tpLabel}"生成详细测试用例`,
        case_type: state.formData.case_type,
        exec_mode: state.formData.exec_mode,
        priority: state.formData.priority,
        enhanced_mode: state.formData.enhanced_mode,
        extra_requirements: state.formData.extra_requirements,
        context: {
          ...context,
          current_test_point: tpInfo || { id: tpId },
          test_point_ids: [tpId],
        },
      }
      apiData.mode = useGraphMode ? 'graph' : 'linear'
      if (useGraphMode) {
        apiData.flow_sort_data = buildFlowSortData(state, computed, flowSortEditorRef)
      }

      state.progress.value = 50
      state.progressText.value = 'AI正在生成测试用例...'

      await callAiAndSaveResults(apiData, state, getActions, tpId, tpLabel)
    } catch (err: unknown) {
      pushErrorCase(state, getActions, tpId, tpLabel, tpInfo?.module || '', err)
    }

    completed++
    state.progress.value = Math.round((completed / total) * 90)
    state.progressText.value = `生成中... ${completed}/${total}`
  }

  clearInterval(progressInterval)
}

export async function generateForFlowNodes(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions,
  context: Record<string, unknown>,
  flowSortEditorRef: FlowSortEditorRef | null
): Promise<void> {
  const flowSortStore = useFlowSortStore()
  const useGraphMode = hasActiveUiFlow(state, flowSortStore)
  const flowNodes =
    useGraphMode && flowSortStore.nodes.length > 0
      ? [...flowSortStore.nodes].sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
      : useGraphMode
        ? state.uiScreens.value.map((screen, index) => ({
            screen_id: screen.id,
            screen_order: index + 1,
            flow_type: 'main' as const,
            screen_name: screen.screen_name,
            ui_spec_elements: screen.ui_spec?.elements || [],
            summary: screen.summary || '',
          }))
        : []

  if (flowNodes.length <= 1) {
    await generateSingle(state, computed, getActions, context, flowSortEditorRef)
    return
  }

  const total = flowNodes.length
  let completed = 0
  const flowSortSubmitData = flowSortEditorRef?.getFlowSortSubmitData?.()
  const allEdges = (flowSortSubmitData?.flow_sort_data?.edges ||
    flowSortStore.edges.map((e) => ({
      source: String(e.source),
      target: String(e.target),
      edge_type: e.edge_type,
      condition: e.condition || '',
      label: e.label || '',
      trigger_action: e.trigger_action || '',
      pre_action: e.pre_action || '',
      note: e.note || '',
    }))) as Array<Record<string, unknown>>

  const progressInterval = setInterval(() => {
    const targetPct = Math.min(70, 25 + Math.round((completed / total) * 45))
    if (state.progress.value < targetPct) {
      state.progress.value = targetPct
      state.progressText.value = `AI生成中... ${completed}/${total}`
    }
  }, 500)

  for (let i = 0; i < flowNodes.length; i++) {
    if (!state.generating.value) break

    const node = flowNodes[i]
    const nodeLabel = node.screen_name || `页面#${node.screen_id}`

    try {
      const nodeEdges = allEdges.filter((e) => edgeTouchesNode(e, node))
      const connectedKeys = new Set<string>(getFlowNodeKeys(node))
      nodeEdges.forEach((edge) => {
        connectedKeys.add(getEdgeEndpoint(edge, 'source'))
        connectedKeys.add(getEdgeEndpoint(edge, 'target'))
      })
      const scopedNodes = flowNodes.filter((candidate) =>
        getFlowNodeKeys(candidate).some((key) => connectedKeys.has(key))
      )
      const validScopedKeys = new Set(
        scopedNodes.flatMap((candidate) => getFlowNodeKeys(candidate))
      )
      const scopedEdges = nodeEdges.filter(
        (edge) =>
          validScopedKeys.has(getEdgeEndpoint(edge, 'source')) &&
          validScopedKeys.has(getEdgeEndpoint(edge, 'target'))
      )
      const scopedContext = filterContextForScreens(context, scopedNodes)
      const nodeFlowData = {
        nodes: scopedNodes,
        edges: scopedEdges,
        module_info: computed.flowSortModuleInfo.value,
      }

      const apiData: Record<string, unknown> = {
        project_id: Number(state.formData.project_id),
        description: state.formData.scene || `为页面"${nodeLabel}"生成详细测试用例`,
        case_type: state.formData.case_type,
        exec_mode: state.formData.exec_mode,
        priority: state.formData.priority,
        enhanced_mode: state.formData.enhanced_mode,
        extra_requirements: state.formData.extra_requirements,
        mode: useGraphMode ? 'graph' : 'linear',
        flow_sort_data: nodeFlowData,
        context: {
          ...scopedContext,
          current_test_point: {
            module: nodeLabel,
            point: `${nodeLabel}页面测试`,
            priority: state.formData.priority,
          },
        },
      }

      state.progress.value = 50
      state.progressText.value = `AI正在为"${nodeLabel}"生成测试用例...`

      await callAiAndSaveResults(apiData, state, getActions, null, nodeLabel)
    } catch (err: unknown) {
      pushErrorCase(state, getActions, null, nodeLabel, nodeLabel, err)
    }

    completed++
    state.progress.value = Math.round((completed / total) * 90)
    state.progressText.value = `生成中... ${completed}/${total}`
  }

  clearInterval(progressInterval)
}

export async function generateSingle(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions,
  context: Record<string, unknown>,
  flowSortEditorRef: FlowSortEditorRef | null
): Promise<void> {
  const flowSortStore = useFlowSortStore()
  const useGraphMode = hasActiveUiFlow(state, flowSortStore)

  let completed = 0
  const totalSteps = 3

  const progressInterval = setInterval(() => {
    const targetPct = Math.min(70, 25 + Math.round((completed / totalSteps) * 45))
    if (state.progress.value < targetPct) {
      state.progress.value = targetPct
      state.progressText.value = `AI生成中... ${completed}/${totalSteps}`
    }
  }, 500)

  state.progress.value = 25
  state.progressText.value = 'AI正在生成测试用例...'
  completed = 1

  const apiData: Record<string, unknown> = {
    project_id: Number(state.formData.project_id),
    description: state.formData.scene || '基于需求文档和UI原型生成测试用例',
    case_type: state.formData.case_type,
    exec_mode: state.formData.exec_mode,
    priority: state.formData.priority,
    enhanced_mode: state.formData.enhanced_mode,
    extra_requirements: state.formData.extra_requirements,
    context: context,
  }
  apiData.mode = useGraphMode ? 'graph' : 'linear'
  if (useGraphMode) {
    apiData.flow_sort_data = buildFlowSortData(state, computed, flowSortEditorRef)
  }

  state.progress.value = 50
  state.progressText.value = 'AI正在生成测试用例...'
  completed = 2

  await callAiAndSaveResults(apiData, state, getActions, null, 'AI生成')

  state.progress.value = 90
  state.progressText.value = '生成中... 3/3'
  completed = 3

  clearInterval(progressInterval)
}

export type { FlowSortEditorRef }

// ========== computed ==========

export interface GenerateComputed {
  selectedUiPrototypeProject: ComputedRef<UIPrototypeProject | null>
  flowSortModuleInfo: ComputedRef<{ name: string; description: string }>
  screenPreviewStatusType: ComputedRef<TagType>
  screenPreviewStatusText: ComputedRef<string>
  viewingCase: ComputedRef<GeneratedCase | null>
  selectedTestPointsForDisplay: ComputedRef<
    Array<
      TestPoint | { id: number; module: string; function: string; point: string; priority: number }
    >
  >
  contextQuality: ComputedRef<GenerationContextQuality>
  canGenerate: ComputedRef<boolean>
  generateButtonLabel: ComputedRef<string>
  progressStatus: ComputedRef<ProgressStatus>
  allSelected: ComputedRef<boolean>
  hasSelected: ComputedRef<boolean>
  selectedCount: ComputedRef<number>
}

export function createGenerateComputed(state: GenerateState): GenerateComputed {
  const effectiveHistoryCaseCount = computed(() =>
    state.selectedHistoryCaseIds.value.length > 0
      ? state.selectedHistoryCaseIds.value.length
      : state._historyCaseUserCleared.value
        ? 0
        : state.projectCases.value.length
  )

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

  const screenPreviewStatusType = computed<TagType>(() => {
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

  const contextQuality = computed(() =>
    getGenerationCapabilityQuality({
      requirementCount: state.formData.requirement_file_ids.length,
      testPointCount: state.formData.test_point_ids.length,
      uiScreenCount: state.formData.ui_screen_ids.length || state.formData.ui_file_ids.length,
      hasPageFlow: Boolean(
        (selectedUiPrototypeProject.value as { has_flow?: boolean } | null)?.has_flow
      ),
      historyCaseCount: effectiveHistoryCaseCount.value,
    })
  )

  const canGenerate = computed(() => {
    return (
      state.formData.test_point_ids.length > 0 ||
      state.formData.requirement_file_ids.length > 0 ||
      state.formData.ui_file_ids.length > 0 ||
      state.formData.ui_screen_ids.length > 0 ||
      effectiveHistoryCaseCount.value > 0
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
    if (effectiveHistoryCaseCount.value > 0) {
      return `${effectiveHistoryCaseCount.value} 条历史用例`
    }
    if (state.formData.case_type === 'api_automation') return '接口用例'
    return '开始'
  })

  const progressStatus = computed<ProgressStatus>(() => {
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
    contextQuality,
    canGenerate,
    generateButtonLabel,
    progressStatus,
    allSelected,
    hasSelected,
    selectedCount,
  }
}

// ========== caseActions ==========

export function createCaseActions(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions
) {
  const handleRegenerateCase = async (
    index: number,
    skipConfirm: boolean = false,
    preserveGenerating: boolean = false
  ) => {
    const c = state.generatedCases.value[index]
    if (!c) return

    if (!skipConfirm) {
      try {
        await ElMessageBox.confirm(
          `将重新生成用例"${c.title}"，当前内容将被覆盖，是否继续？`,
          '确认重新生成',
          { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }

    state.generating.value = true
    state.progress.value = 10
    state.progressText.value = '正在调用AI重新生成...'

    try {
      const flowSortStore = useFlowSortStore()
      const useGraphMode =
        flowSortStore.quickMode === false &&
        Boolean(
          state.selectedUiPrototypeProjectId.value &&
          state.formData.ui_screen_ids.length > 0 &&
          flowSortStore.nodes.length > 0
        )
      const apiData: Record<string, unknown> = {
        project_id: Number(state.formData.project_id),
        description: state.formData.scene || `重新生成用例"${c.title}"`,
        case_type: state.formData.case_type || c.case_type,
        exec_mode: state.formData.exec_mode || 'all',
        priority: state.formData.priority || c.priority || 2,
        enhanced_mode:
          state.formData.enhanced_mode !== undefined ? state.formData.enhanced_mode : true,
        extra_requirements: state.formData.extra_requirements || '',
        mode: useGraphMode ? ('graph' as const) : ('linear' as const),
        flow_sort_data: useGraphMode ? buildFlowSortData(state, computed, null) : undefined,
        context: {
          base_case: {
            title: c.title,
            module: c.module,
            precondition: c.precondition,
            steps: c.steps || [],
            expected_result: c.expected_result,
          },
          requirement_content: state.contextPreview.value?.requirement_content || '',
          ui_description: (state.lastContext.value as Record<string, string>).ui_description || '',
          ui_specs: (state.lastContext.value as Record<string, unknown[]>).ui_specs || [],
          test_points: state.contextPreview.value?.test_points || [],
          history_cases: (state.lastContext.value as Record<string, unknown[]>).history_cases || [],
        },
      }

      const generateResult = await caseApi.aiGenerateCaseEnhanced(
        apiData as unknown as import('@/api/case').TestCaseAIEnhancedRequest
      )
      const casesData = generateResult.cases
      const caseData = casesData[0]
      if (!caseData) {
        throw new Error('AI 未返回有效用例数据')
      }

      const oldDbId = c._dbId

      state.generatedCases.value[index] = {
        ...state.generatedCases.value[index],
        title: caseData.title || caseData.name || '',
        module: caseData.module || '',
        case_type: caseData.case_type || caseData.type || '',
        precondition: caseData.precondition || '',
        test_data: caseData.test_data,
        steps: (caseData.steps || []) as GeneratedStep[],
        expected_result: caseData.expected_result || '',
        priority: caseData.priority || state.formData.priority,
        ai_change_type: caseData.change_type || 'added',
        parent_case_id: caseData.parent_case_id ?? null,
        _error: undefined,
        _saved: false,
        _dbId: undefined,
      }

      state.progressText.value = '正在保存...'
      const saved = await getActions().saveSingleCaseToDb(state.generatedCases.value[index])
      if (!saved) {
        state.generatedCases.value[index]._error = '保存失败'
      }

      if (oldDbId && saved) {
        try {
          await caseApi.deleteCase(oldDbId, Number(state.formData.project_id) || undefined)
        } catch {
          console.warn(`[handleRegenerateCase] 删除旧用例 #${oldDbId} 失败，可能产生冗余数据`)
        }
      }

      state.progress.value = 100
      state.progressText.value = '重新生成完成！'
      ElMessage.success('用例重新生成成功')
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      ElMessage.error(
        err.response?.data?.detail || err.response?.data?.message || err.message || '重新生成失败'
      )
    } finally {
      if (!preserveGenerating) {
        state.generating.value = false
      }
    }
  }

  const handleDeleteCase = async (index: number) => {
    const c = state.generatedCases.value[index]
    if (!c) return

    try {
      await ElMessageBox.confirm(`确定要删除用例"${c.title}"吗？删除后不可恢复。`, '确认删除', {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      })
    } catch {
      return
    }

    if (c._dbId) {
      try {
        await caseApi.deleteCase(c._dbId, Number(state.formData.project_id) || undefined)
      } catch (e) {
        console.error(`[handleDeleteCase] 删除数据库用例 #${c._dbId} 失败:`, e)
        ElMessage.error('数据库删除失败，请稍后重试')
        return
      }
    }

    state.generatedCases.value.splice(index, 1)
    state.selectedCaseIndices.value = new Set(
      [...state.selectedCaseIndices.value]
        .filter((i) => i !== index)
        .map((i) => (i > index ? i - 1 : i))
    )

    if (state.generatedCases.value.length === 0) {
      state.currentCaseIndex.value = -1
    } else if (state.currentCaseIndex.value >= state.generatedCases.value.length) {
      state.currentCaseIndex.value = state.generatedCases.value.length - 1
    }

    ElMessage.success('用例已删除')
  }

  const handleRegenerateSelected = async () => {
    const indices = [...state.selectedCaseIndices.value].sort((a, b) => a - b)
    if (indices.length === 0) {
      ElMessage.warning('请先选择要重新生成的用例')
      return
    }

    try {
      await ElMessageBox.confirm(
        `将重新生成选中的 ${indices.length} 条用例，当前内容将被覆盖，是否继续？`,
        '确认批量重新生成',
        { confirmButtonText: '重新生成', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }

    state.generating.value = true
    try {
      for (const idx of indices) {
        await getActions().handleRegenerateCase(idx, true, true)
        if (!state.generating.value) break
      }
    } finally {
      state.generating.value = false
    }
  }

  const handleDeleteSelected = async () => {
    const indices = [...state.selectedCaseIndices.value].sort((a, b) => b - a)
    if (indices.length === 0) {
      ElMessage.warning('请先选择要删除的用例')
      return
    }

    try {
      await ElMessageBox.confirm(
        `确定要删除选中的 ${indices.length} 条用例吗？删除后不可恢复。`,
        '确认批量删除',
        { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }

    const dbIds = indices
      .map((i) => state.generatedCases.value[i]?._dbId)
      .filter((id): id is number => id !== undefined)

    if (dbIds.length > 0) {
      try {
        await caseApi.batchDeleteCases(dbIds, Number(state.formData.project_id) || undefined)
      } catch (e) {
        console.error('[handleDeleteSelected] 批量删除数据库用例失败:', e)
        ElMessage.error('数据库批量删除失败，请稍后重试')
        return
      }
    }

    for (const idx of indices) {
      state.generatedCases.value.splice(idx, 1)
    }

    state.selectedCaseIndices.value = new Set()

    if (state.generatedCases.value.length === 0) {
      state.currentCaseIndex.value = -1
    } else if (state.currentCaseIndex.value >= state.generatedCases.value.length) {
      state.currentCaseIndex.value = state.generatedCases.value.length - 1
    }

    ElMessage.success(`已删除 ${indices.length} 条用例`)
  }

  const handleCancel = () => {
    if (!state.generating.value) return
    ElMessageBox.confirm('确定要取消生成吗？', '取消确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      state.generating.value = false
      state.progressText.value = '已取消'
      state.errorMessage.value = ''
      ElMessage.info('生成已取消')
    })
  }

  return {
    handleRegenerateCase,
    handleDeleteCase,
    handleRegenerateSelected,
    handleDeleteSelected,
    handleCancel,
  }
}

// ========== projectActions ==========

const HISTORY_CASE_LIFECYCLE_STATUSES = [
  'draft',
  'active',
  'pending_review',
  'needs_modify',
  'locator_broken',
].join(',')

export function createProjectActions(state: GenerateState, getActions: () => StoreActions) {
  const getProjects = async (forceReload: boolean = false) => {
    if (state.projectsLoaded.value && !forceReload && state.projects.value.length > 0) {
      return
    }
    state.projectsLoading.value = true
    try {
      const response: ProjectListResponse = await ProjectAPI.getProjects({
        page: 1,
        page_size: 1000,
      })
      if (response?.data?.items) {
        state.projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
        state.projectsLoaded.value = true
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
    } finally {
      state.projectsLoading.value = false
    }
  }

  const loadProjectFiles = async () => {
    try {
      const response = await fileApi.getFileList(state.formData.project_id as number)
      const items = extractListItems(response) as import('@/api/file').ProjectFile[]
      state.requirementFiles.value = items.filter((f) => f.resource_type === 'requirement')
      state.uiFiles.value = items.filter((f) => f.resource_type === 'ui_mockup')
    } catch (error) {
      console.error('获取文件列表失败:', error)
    }
  }

  const loadProjectCases = async () => {
    if (!state.formData.project_id) {
      state.projectCases.value = []
      return
    }
    state.isLoadingProjectCases.value = true
    try {
      const response = await caseApi.getCaseList({
        project_id: state.formData.project_id as number,
        lifecycle_status: HISTORY_CASE_LIFECYCLE_STATUSES,
        page_size: 500,
      })
      state.projectCases.value = response?.data?.items || []
    } catch (e) {
      console.warn('加载项目用例失败:', e)
      state.projectCases.value = []
    } finally {
      state.isLoadingProjectCases.value = false
    }
  }

  const handleProjectChange = () => {
    state.formData.requirement_file_ids = []
    state.formData.ui_file_ids = []
    state.formData.ui_screen_ids = []
    state.formData.test_point_ids = []
    state.contextPreview.value = null
    state.lastContext.value = {}
    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.selectedUiPrototypeProjectId.value = ''
    state.uiPrototypeProjects.value = []
    state.uiScreens.value = []
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
    if (state.formData.project_id) {
      flowSortStore.setProjectId(state.formData.project_id as number)
    }
    state.selectedHistoryCaseIds.value = []
    state._historyCaseUserCleared.value = false
    state.projectCases.value = []
    getActions().handleSourceFileChange()
    getActions().loadProjectFiles()
    getActions().loadUIPrototypeProjects()
    getActions().loadProjectCases()
    getActions().loadTestPoints(1)
  }

  const handleProjectFocus = () => {
    if (!state.projectsLoaded.value || state.projects.value.length === 0) {
      getProjects()
    }
  }

  const extractFileContent = async () => {
    if (
      state.formData.requirement_file_ids.length === 0 &&
      state.formData.ui_file_ids.length === 0
    ) {
      ElMessage.warning('请先选择文件')
      return
    }
    const allFileIds = [...state.formData.requirement_file_ids, ...state.formData.ui_file_ids]
    try {
      const response = await fileApi.extractContent({
        file_ids: allFileIds,
        project_id: Number(state.formData.project_id),
      })
      const resData = ((response as unknown as { data?: unknown })?.data ?? response) as {
        code?: number
        data?: { success?: number; failed?: number }
        msg?: string
        message?: string
      }
      if (resData?.code === 200) {
        await getActions().loadProjectFiles()
        const data = resData.data as { success?: number; failed?: number }
        state.contextPreview.value = {
          title: `内容提取完成：成功 ${data?.success || 0} 个，失败 ${data?.failed || 0} 个`,
          type: (data?.failed || 0) > 0 ? 'warning' : 'success',
          requirement: `选择了 ${allFileIds.length} 个文件`,
          ui:
            state.formData.ui_screen_ids.length > 0
              ? `${state.formData.ui_screen_ids.length} 个屏幕`
              : state.formData.ui_file_ids.length > 0
                ? `${state.formData.ui_file_ids.length} 个文件`
                : '',
          uiSpecs: (state.lastContext.value as Record<string, unknown[]>)?.ui_specs?.length || 0,
        }
        ElMessage.success('文件内容提取完成')
      } else {
        ElMessage.error(resData?.msg || resData?.message || '提取内容失败')
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err.response?.data?.detail || '提取内容失败')
    }
  }

  return {
    getProjects,
    loadProjectFiles,
    loadProjectCases,
    handleProjectChange,
    handleProjectFocus,
    extractFileContent,
  }
}

// ========== uiPrototypeActions ==========

export function createUiPrototypeActions(state: GenerateState, getActions: () => StoreActions) {
  const loadUIPrototypeProjects = async () => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIPrototypeProjectList(
        state.formData.project_id as number
      )
      state.uiPrototypeProjects.value = extractListItems(
        response
      ) as import('@/api/uiPrototype').UIPrototypeProject[]
    } catch (error) {
      console.error('获取 UI 原型项目列表失败:', error)
    }
  }

  const cleanupScreenImages = () => {
    Object.values(state.screenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    state.screenImageUrls.value = {}
  }

  const loadScreenImages = async () => {
    if (state.isLoadingScreenImages.value) return
    state.isLoadingScreenImages.value = true
    try {
      const screensToLoad = state.uiScreens.value.filter(
        (screen) =>
          screen.id && screen.original_file_path && !state.screenImageUrls.value[screen.id]
      )
      const BATCH_SIZE = 5
      for (let i = 0; i < screensToLoad.length; i += BATCH_SIZE) {
        const batch = screensToLoad.slice(i, i + BATCH_SIZE)
        await Promise.allSettled(
          batch.map(async (screen) => {
            try {
              const response = await fileApi.getPreviewScreen(screen.id)
              const blob =
                response.data instanceof Blob
                  ? response.data
                  : new Blob([response.data], { type: 'image/jpeg' })
              if (blob.size > 0) {
                const oldUrl = state.screenImageUrls.value[screen.id]
                if (oldUrl?.startsWith('blob:')) {
                  URL.revokeObjectURL(oldUrl)
                }
                state.screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
              }
            } catch (e) {
              console.warn(`加载屏幕图片失败: ${screen.id}`, e)
            }
          })
        )
      }
    } finally {
      state.isLoadingScreenImages.value = false
    }
  }

  const loadUIScreens = async (uiPrototypeProjectId: number) => {
    if (!state.formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIScreenList(
        state.formData.project_id as number,
        uiPrototypeProjectId
      )
      state.uiScreens.value = (extractListItems(response) as UIScreen[]).sort(
        (a: UIScreen, b: UIScreen) => (a.screen_order || 0) - (b.screen_order || 0)
      )
      cleanupScreenImages()
      await loadScreenImages()
    } catch (error) {
      console.error('获取 UI 屏幕列表失败:', error)
      state.uiScreens.value = []
      cleanupScreenImages()
    }
  }

  const buildNodeElements = (screen: UIScreen): FlowNodeData['ui_spec_elements'] => {
    return (screen.ui_spec?.elements || []).map((el) => ({
      type: el.type,
      label: el.label,
      semantic: el.semantic_hint || el.description,
      position: typeof el.position === 'string' ? el.position : JSON.stringify(el.position),
      interactive: el.interactive,
      state: el.state,
      description: el.description,
    }))
  }

  const buildDefaultFlowNodes = (): FlowNodeData[] => {
    return state.uiScreens.value.map((screen, index) => ({
      id: `node_${screen.id}`,
      screen_id: screen.id,
      screen_name: screen.screen_name,
      summary: screen.summary || '',
      ui_spec_elements: buildNodeElements(screen),
      flow_type: 'main',
      main_order: index + 1,
      image_url: state.screenImageUrls.value[screen.id] || '',
      position: { x: index * 280, y: 0 },
    }))
  }

  const buildDefaultFlowEdges = (nodes: FlowNodeData[]): FlowEdgeData[] => {
    return nodes.slice(0, -1).map((node, index) => {
      const next = nodes[index + 1]
      return {
        id: `auto_${node.id}_${next.id}`,
        source: String(node.screen_id),
        target: String(next.screen_id),
        edge_type: 'normal',
        label: '连线',
      }
    })
  }

  const syncFlowSortStoreWithCurrentScreens = () => {
    const flowSortStore = useFlowSortStore()
    const screenById = new Map(state.uiScreens.value.map((screen) => [screen.id, screen]))
    if (screenById.size === 0) {
      flowSortStore.updateNodes([])
      flowSortStore.updateEdges([])
      return
    }

    const compatibleNodes = flowSortStore.nodes.filter((node) => screenById.has(node.screen_id))
    if (compatibleNodes.length === 0) {
      const nodes = buildDefaultFlowNodes()
      flowSortStore.updateNodes(nodes)
      flowSortStore.updateEdges(buildDefaultFlowEdges(nodes))
      return
    }

    const validScreenIds = new Set(compatibleNodes.map((node) => String(node.screen_id)))
    const validNodeIds = new Set(compatibleNodes.map((node) => node.id))
    const compatibleEdges = flowSortStore.edges.filter((edge) => {
      const source = String(edge.source)
      const target = String(edge.target)
      return (
        (validScreenIds.has(source) || validNodeIds.has(source)) &&
        (validScreenIds.has(target) || validNodeIds.has(target))
      )
    })
    const hydratedNodes = compatibleNodes.map((node, index) => {
      const screen = screenById.get(node.screen_id)
      return {
        ...node,
        screen_name: screen?.screen_name || node.screen_name,
        summary: screen?.summary || node.summary || '',
        ui_spec_elements: screen ? buildNodeElements(screen) : node.ui_spec_elements,
        image_url: state.screenImageUrls.value[node.screen_id] || node.image_url || '',
        main_order: node.flow_type === 'main' ? node.main_order || index + 1 : node.main_order,
      }
    })
    flowSortStore.updateNodes(hydratedNodes)
    flowSortStore.updateEdges(compatibleEdges)
  }

  const handleUIPrototypeProjectChange = async (projectId: number | string) => {
    state.showParseWarning.value = true
    state.lastContext.value = {}
    state.selectedUiPrototypeProjectId.value = projectId as number | ''
    const flowSortStore = useFlowSortStore()
    state.uiScreens.value = []
    state.formData.ui_screen_ids = []
    cleanupScreenImages()
    flowSortStore.reset()
    if (projectId) {
      if (state.formData.project_id) {
        flowSortStore.setProjectId(state.formData.project_id as number)
      }
      await getActions().loadUIScreens(projectId as number)
      if (state.formData.project_id) {
        await flowSortStore.loadFromBackend()
      }
      syncFlowSortStoreWithCurrentScreens()
      state.formData.ui_screen_ids = state.uiScreens.value.map((s) => s.id)
    } else {
      flowSortStore.reset()
    }
  }

  return {
    loadUIPrototypeProjects,
    loadUIScreens,
    loadScreenImages,
    handleUIPrototypeProjectChange,
    cleanupScreenImages,
  }
}

// ========== testPointActions ==========

export function createTestPointActions(state: GenerateState) {
  const loadTestPoints = async (
    page: number = 1,
    append: boolean = false,
    refreshKey: boolean = true
  ) => {
    if (!state.formData.project_id) return
    try {
      const apiData = await testPointApi.getList(state.formData.project_id as number, {
        page,
        page_size: state.testPointPageSize.value,
      })
      if (apiData) {
        const newItems = apiData.items || []
        if (append && page > 1) {
          state.testPoints.value = [...state.testPoints.value, ...newItems]
        } else {
          state.testPoints.value = newItems
        }
        newItems.forEach((item: TestPoint) => {
          state.testPointCache.set(item.id, item)
          if (!state.testPointAllIds.value.includes(item.id)) {
            state.testPointAllIds.value.push(item.id)
          }
        })
        if (state.testPointCache.size > TEST_POINT_CACHE_MAX) {
          const overflow = state.testPointCache.size - TEST_POINT_CACHE_MAX
          let count = 0
          for (const key of state.testPointCache.keys()) {
            if (count >= overflow) break
            state.testPointCache.delete(key)
            count++
          }
        }
        state.testPointTotal.value = apiData.total || 0
        state.testPointPage.value = page
        if (refreshKey) {
          state.testPointSelectKey.value++
        }
        if (
          state.testPointAllIds.value.length < state.testPointTotal.value &&
          page === 1 &&
          state.testPointTotal.value <= 200
        ) {
          const allApiData = await testPointApi.getList(state.formData.project_id as number, {
            page: 1,
            page_size: Math.min(state.testPointTotal.value, 200),
          })
          if (allApiData?.items) {
            state.testPointAllIds.value = allApiData.items.map((item: TestPoint) => item.id)
          }
        }
      }
    } catch (error) {
      console.error('获取测试点列表失败:', error)
    }
  }

  const handleSourceFileChange = () => {
    if (!state.formData.project_id) return
    state.testPointPage.value = 1
    state.testPointTotal.value = 0
    state.testPointAllIds.value = []
    state.formData.test_point_ids = []
    state.testPoints.value = []
    state.testPointCache.clear()
    state.testPointSelectKey.value++
  }

  const selectAllTestPoints = () => {
    if (state.testPointAllIds.value.length > 0) {
      state.formData.test_point_ids = [...state.testPointAllIds.value]
    }
  }

  const deselectAllTestPoints = () => {
    state.formData.test_point_ids = []
  }

  const addTestPoint = (id: number) => {
    if (!state.formData.test_point_ids.includes(id)) {
      state.formData.test_point_ids.push(id)
    }
  }

  const removeTestPoint = (id: number) => {
    const index = state.formData.test_point_ids.indexOf(id)
    if (index !== -1) {
      state.formData.test_point_ids.splice(index, 1)
    }
  }

  const getTestPointLabel = (id: number): string => {
    let point = state.testPointCache.get(id)
    if (!point) {
      point = state.testPoints.value.find((p) => p.id === id)
    }
    if (point) {
      return `${point.module} - ${point.point}`
    }
    return `测试点 #${id}`
  }

  const selectCurrentPageAll = () => {
    const visibleIds = state.testPoints.value.map((p) => p.id)
    const currentSet = new Set(state.formData.test_point_ids)
    visibleIds.forEach((id) => {
      if (!currentSet.has(id)) {
        state.formData.test_point_ids.push(id)
      }
    })
  }

  const goToTestPointPage = async (page: number) => {
    if (state.isLoadingMore.value) return
    state.isLoadingMore.value = true
    try {
      await loadTestPoints(page, false, false)
    } finally {
      state.isLoadingMore.value = false
    }
  }

  return {
    loadTestPoints,
    handleSourceFileChange,
    selectAllTestPoints,
    deselectAllTestPoints,
    addTestPoint,
    removeTestPoint,
    getTestPointLabel,
    selectCurrentPageAll,
    goToTestPointPage,
  }
}

// ========== saveActions ==========

export function createSaveActions(state: GenerateState, computed: GenerateComputed) {
  const buildStepsPayload = (steps: GeneratedStep[] | undefined): TestCaseApiStep[] => {
    return (steps || []).map((s: GeneratedStep, i: number) => ({
      step: String(s.step || i + 1),
      action: s.action || '',
      param: s.input_value || s.param || '',
      expected_result: s.expected_result || '',
      action_type: s.action_type || '',
      input_value: s.input_value || '',
      target_element: s.target_element || '',
      ui_elements: s.ui_elements || [],
    }))
  }

  const buildCaseCreatePayload = (c: {
    id?: number
    title?: string
    module?: string
    case_type?: string
    precondition?: string
    steps?: GeneratedStep[]
    expected_result?: string
    priority?: number
    test_category?: string
    test_data?: Record<string, unknown>
    parent_case_id?: number | null
    ai_change_type?: 'added' | 'modified' | 'deprecated'
    test_point_id?: number | null
  }) => {
    const stepsPayload = buildStepsPayload(c.steps)
    const priority = normalizePriority(c.priority ?? 2)
    return {
      project_id: Number(state.formData.project_id),
      test_point_id: c.test_point_id ?? undefined,
      case_no: generateCaseNo(state.formData.project_id, c.id),
      title: c.title || '未命名测试用例',
      module: c.module || '默认模块',
      case_type: c.case_type || '',
      precondition: c.precondition || '系统已通过配置自动登录至目标页面',
      steps:
        stepsPayload.length > 0
          ? stepsPayload
          : [{ step: 1, action: '执行测试', param: '预期结果正常' }],
      expected_result: c.expected_result || '操作成功',
      priority,
      test_category: c.test_category || c.case_type || '',
      test_data: (c.test_data || {}) as Record<
        string,
        Record<string, string | number | boolean | null>
      >,
      generate_status: 1,
      parent_case_id: c.parent_case_id ?? undefined,
      ai_change_type: c.ai_change_type || undefined,
    }
  }

  const saveSingleCaseToDb = async (c: SaveSingleCaseParam): Promise<boolean> => {
    try {
      const payload = buildCaseCreatePayload(c)
      const created = await caseApi.createCase(payload)
      c._saved = true
      c._dbId = created.id
      return true
    } catch (e) {
      console.error(`[saveSingleCaseToDb] 用例 "${c.title}" 保存失败:`, e)
      return false
    }
  }

  const handleSaveCase = async () => {
    const caseToSave = state.isEditingResult.value
      ? state.editingCase.value
      : computed.viewingCase.value
    if (!caseToSave) {
      ElMessage.warning('没有可保存的用例')
      return
    }
    if ('_error' in caseToSave && caseToSave._error) {
      ElMessage.warning('该用例生成失败，无法保存，请重新生成')
      return
    }
    if (!state.formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }

    state.saving.value = true
    try {
      const currentCase = computed.viewingCase.value
      const dbId = currentCase?._dbId

      const payload = buildCaseCreatePayload({
        title: caseToSave.title,
        module: caseToSave.module,
        case_type: caseToSave.case_type,
        precondition: caseToSave.precondition,
        steps: caseToSave.steps,
        expected_result: caseToSave.expected_result,
        priority: caseToSave.priority,
        test_category: caseToSave.test_category,
        test_data: caseToSave.test_data,
        parent_case_id: caseToSave.parent_case_id,
        ai_change_type: caseToSave.ai_change_type,
        test_point_id: currentCase?.test_point_id,
      })

      if (dbId) {
        const updatePayload: import('@/api/case').TestCaseUpdateData = {
          title: caseToSave.title,
          module: caseToSave.module,
          case_type: caseToSave.case_type,
          precondition: caseToSave.precondition,
          steps: (caseToSave.steps || []).map((s, i) => ({
            step_number: typeof s.step === 'number' ? s.step : i + 1,
            action: s.action || '',
            expected_result: s.expected_result || '',
            param: s.input_value || s.param || '',
          })),
          expected_result: caseToSave.expected_result,
          priority: payload.priority,
          test_category: caseToSave.test_category || caseToSave.case_type,
        }
        await caseApi.updateCase(dbId, updatePayload)
        ElMessage.success(`"${caseToSave.title}" 更新成功`)
      } else {
        const created = await caseApi.createCase(payload)
        ElMessage.success(`"${caseToSave.title}" 保存成功`)
        if (
          state.currentCaseIndex.value >= 0 &&
          state.currentCaseIndex.value < state.generatedCases.value.length
        ) {
          state.generatedCases.value[state.currentCaseIndex.value]._saved = true
          state.generatedCases.value[state.currentCaseIndex.value]._dbId = created.id
        }
      }

      const wasEditing = state.isEditingResult.value

      state.isEditingResult.value = false
      if (
        state.currentCaseIndex.value >= 0 &&
        state.currentCaseIndex.value < state.generatedCases.value.length
      ) {
        const target = state.generatedCases.value[state.currentCaseIndex.value]
        target._saved = true
        if (wasEditing) {
          target.title = caseToSave.title
          target.module = caseToSave.module
          target.case_type = caseToSave.case_type
          target.precondition = caseToSave.precondition
          target.expected_result = caseToSave.expected_result
          target.priority = caseToSave.priority
          target.steps = caseToSave.steps
          if (caseToSave.test_data) {
            target.test_data = caseToSave.test_data
          }
        }
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      const detail = err.response?.data?.detail
      ElMessage.error(detail && typeof detail === 'string' ? detail : '保存失败，请检查必填字段')
    } finally {
      state.saving.value = false
    }
  }

  return {
    buildStepsPayload,
    buildCaseCreatePayload,
    saveSingleCaseToDb,
    handleSaveCase,
  }
}

// ========== generateActions ==========

export function createGenerateActions(
  state: GenerateState,
  computed: GenerateComputed,
  getActions: () => StoreActions
) {
  const generateErrorSuggestions = () => {
    const error = state.errorMessage.value.toLowerCase()
    if (
      error.includes('认证') ||
      error.includes('authentication') ||
      (error.includes('api') && error.includes('key')) ||
      error.includes('503') ||
      error.includes('无效')
    ) {
      state.errorSuggestions.value = [
        '请检查 .env 文件中的 DEEPSEEK_API_KEY 是否配置正确',
        '访问 https://platform.deepseek.com/ 获取有效的 API Key',
        '确保 API Key 没有过期或被禁用',
        '如果问题持续，请联系管理员检查 DeepSeek 服务状态',
      ]
      return
    }
    if (
      error.includes('429') ||
      error.includes('rate limit') ||
      error.includes('频率') ||
      error.includes('过多')
    ) {
      state.errorSuggestions.value = [
        'AI服务请求频率过高，请稍后重试',
        '建议降低请求频率或等待一段时间后再试',
        '可以尝试分批生成测试用例',
      ]
      return
    }
    state.errorSuggestions.value = [
      '请确保输入的测试场景描述清晰具体',
      '建议先配置需求文档和UI原型图链接',
      '检查网络连接是否正常',
      '稍后重试，可能是API服务暂时不可用',
      '如果问题持续，请联系管理员',
    ]
  }

  const showValidationDialog = (validation: {
    errors: string[]
    warnings: string[]
  }): Promise<boolean> => {
    state.issueDialogValidation.value = validation
    state.issueDialogVisible.value = true
    return new Promise((resolve) => {
      state.issueDialogResolver.value = resolve
    })
  }

  const onIssueDialogConfirm = () => {
    state.issueDialogVisible.value = false
    state.issueDialogResolver.value?.(true)
    state.issueDialogResolver.value = null
  }

  const onIssueDialogCancel = () => {
    state.issueDialogVisible.value = false
    state.issueDialogResolver.value?.(false)
    state.issueDialogResolver.value = null
  }

  const handleGenerate = async (flowSortEditorRef: FlowSortEditorRef | null) => {
    if (!computed.canGenerate.value) {
      ElMessage.warning('请先选择测试点、需求文档、UI原型图或历史用例')
      return
    }

    if (state.selectedUiPrototypeProjectId.value && state.uiScreens.value.length > 0) {
      const flowSortStore = useFlowSortStore()
      if (flowSortStore.quickMode === false) {
        const validation = flowSortEditorRef?.getFlowValidationIssues?.()
        if (validation?.errors.length) {
          const confirmed = await showValidationDialog(validation)
          if (!confirmed) return
        }
        if (validation?.warnings.length) {
          const confirmed = await showValidationDialog({
            errors: [],
            warnings: validation.warnings,
          })
          if (!confirmed) return
        }
      }
    }

    const targetPoints =
      state.formData.test_point_ids.length > 0
        ? state.formData.test_point_ids
        : (state.contextPreview.value?.test_points || []).map((tp) => tp.id)

    const MAX_COUNT = 20
    if (targetPoints.length > MAX_COUNT) {
      try {
        await ElMessageBox.confirm(
          `当前选择了 ${targetPoints.length} 个测试点，将逐个生成用例，可能需要较长时间。是否继续？`,
          '确认生成',
          { confirmButtonText: '继续生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }
    if (targetPoints.length === 0) {
      try {
        await ElMessageBox.confirm(
          '将基于选中的历史用例、需求文档和UI原型直接生成测试用例，是否继续？',
          '确认生成',
          { confirmButtonText: '继续生成', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
    }

    state.generatedCases.value = []
    state.currentCaseIndex.value = -1
    state.errorMessage.value = ''
    state.errorSuggestions.value = []
    state.generating.value = true
    state.progress.value = 0
    state.progressText.value =
      targetPoints.length > 0
        ? `准备生成 ${targetPoints.length} 条测试用例...`
        : '准备生成测试用例...'
    state.currentStep.value = 2

    try {
      let context: Record<string, unknown> = {
        requirement_content: '',
        ui_description: '',
        test_points: [],
        project_config: null,
      }

      state.progress.value = 5
      state.progressText.value = '正在准备生成上下文...'

      if (state.formData.project_id) {
        const contextResponse = (await caseApi.generateContext({
          project_id: Number(state.formData.project_id),
          requirement_file_ids:
            state.formData.requirement_file_ids.length > 0
              ? state.formData.requirement_file_ids
              : undefined,
          ui_file_ids:
            state.formData.ui_file_ids.length > 0 ? state.formData.ui_file_ids : undefined,
          ui_screen_ids:
            state.formData.ui_screen_ids.length > 0 ? state.formData.ui_screen_ids : undefined,
          test_point_ids: targetPoints.length > 0 ? targetPoints : undefined,
          history_case_ids:
            state.selectedHistoryCaseIds.value.length > 0
              ? state.selectedHistoryCaseIds.value
              : state.selectedHistoryCaseIds.value.length === 0 &&
                  state._historyCaseUserCleared.value
                ? []
                : undefined,
        })) as unknown as ApiResponse<{
          requirement_content?: string
          ui_descriptions?: unknown[]
          ui_specs?: unknown[]
          test_points?: TestPoint[]
          project_config?: unknown
          history_cases?: unknown[]
          context_stats?: Record<string, unknown>
          warnings?: unknown[]
          evidence_refs?: Record<string, unknown>
        }>

        if (contextResponse?.data) {
          const data = contextResponse.data
          const contextTestPoints = targetPoints.length > 0 ? data.test_points || [] : []
          context = {
            requirement_content: data.requirement_content || '',
            ui_descriptions: data.ui_descriptions || [],
            ui_description: Array.isArray(data.ui_descriptions) && data.ui_descriptions.length > 0
              ? JSON.stringify(data.ui_descriptions)
              : '',
            ui_specs: data.ui_specs || [],
            test_points: contextTestPoints,
            project_config: data.project_config || null,
            history_cases: data.history_cases || [],
          }
          state.lastContext.value = { ...context }

          // 提取上下文健康检查信息
          state.contextStats.value = (data.context_stats as unknown as ContextStats) || null
          state.serverWarnings.value = Array.isArray(data.warnings) ? (data.warnings as unknown as ServerWarning[]) : []
          state.evidenceRefs.value = (data.evidence_refs as unknown as EvidenceRefs) || null

          state.progress.value = 15
          state.progressText.value = '上下文准备完成，开始构建生成数据...'
        }
      }

      if (targetPoints.length > 0) {
        await generateForTestPoints(
          state,
          computed,
          getActions,
          context,
          targetPoints,
          flowSortEditorRef
        )
      } else {
        await generateForFlowNodes(state, computed, getActions, context, flowSortEditorRef)
      }

      if (!state.generating.value) {
        state.progressText.value = `已取消，已生成 ${state.generatedCases.value.length} 条`
      } else {
        state.currentCaseIndex.value = 0
        state.progress.value = 100
        state.progressText.value = `生成完成！共 ${state.generatedCases.value.length} 条`
        const failCount = state.generatedCases.value.filter((c) => c._error).length
        if (failCount === 0) {
          ElMessage.success(`成功生成 ${state.generatedCases.value.length} 条测试用例`)
        } else {
          ElMessage.warning(
            `生成完成：${state.generatedCases.value.length - failCount} 成功，${failCount} 失败`
          )
        }
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      state.progress.value = 100
      state.progressText.value = '生成失败'
      state.errorMessage.value =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'AI生成测试用例失败'
      generateErrorSuggestions()
      ElMessage.error(state.errorMessage.value)
    } finally {
      state.generating.value = false
    }
  }

  return {
    generateErrorSuggestions,
    showValidationDialog,
    onIssueDialogConfirm,
    onIssueDialogCancel,
    handleGenerate,
  }
}

// ========== editActions ==========

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
