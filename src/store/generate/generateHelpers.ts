import caseApi from '@/api/case'
import type { TestCaseAIEnhancedRequest } from '@/api/case'
import type { TestPoint } from '@/api/testPoint'
import { useFlowSortStore } from '@/store/flowSort'
import type { GeneratedStep } from './types'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'
import type { StoreActions } from './types'

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
