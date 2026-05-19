import caseApi from '@/api/case'
import type { TestCaseAIEnhancedRequest } from '@/api/case'
import type { TestPoint } from '@/api/testPoint'
import { useFlowSortStore } from '@/store/flowSort'
import type { GeneratedStep } from './types'
import type { GenerateState } from './state'
import type { GenerateComputed } from './computed'
import type { StoreActions } from './types'

interface FlowSortEditorRef {
  getFlowSortSubmitData?: () => { mode: 'graph'; flow_sort_data: Record<string, unknown> }
  getFlowValidationIssues?: () => { errors: string[]; warnings: string[] }
}

async function callAiAndSaveResults(
  apiData: Record<string, unknown>,
  state: GenerateState,
  getActions: () => StoreActions,
  testPointId: number | null,
  label: string
): Promise<void> {
  const casesArray = await caseApi.aiGenerateCaseEnhanced(
    apiData as unknown as TestCaseAIEnhancedRequest
  )
  const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]

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

function buildFlowSortData(
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
      apiData.mode = flowSortStore.nodes.length > 0 ? 'graph' : 'linear'
      apiData.flow_sort_data = buildFlowSortData(state, computed, flowSortEditorRef)

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
  const flowNodes =
    flowSortStore.nodes.length > 0
      ? [...flowSortStore.nodes].sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
      : state.uiScreens.value.map((screen, index) => ({
          screen_id: screen.id,
          screen_order: index + 1,
          flow_type: 'main' as const,
          screen_name: screen.screen_name,
          ui_spec_elements: screen.ui_spec?.elements || [],
          summary: screen.summary || '',
        }))

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
      const nodeFlowData = {
        nodes: [node],
        edges: allEdges.filter(
          (e) =>
            String(e.source) === String(node.screen_id) ||
            String(e.target) === String(node.screen_id)
        ),
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
        mode: 'graph' as const,
        flow_sort_data: nodeFlowData,
        context: {
          ...context,
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
  apiData.mode = flowSortStore.nodes.length > 0 ? 'graph' : 'linear'
  apiData.flow_sort_data = buildFlowSortData(state, computed, flowSortEditorRef)

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
