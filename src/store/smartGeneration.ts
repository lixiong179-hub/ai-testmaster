import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { generationBatchApi } from '@/api/generationBatch'
import type {
  GenerationBatchCreatePayload,
  GenerationBatchSavePayload,
  GenerationBatchSaveResponse,
  NormalizedWarning,
  PreviewCasePayload,
} from '@/api/generationBatch'
import { aiApi } from '@/api/case/ai'
import { aiInvocationApi } from '@/api/aiInvocation'
import type { BatchCostInfo } from '@/api/aiInvocation'
import { uiPrototypeApi, type UIScreen, type UIPrototypeProject } from '@/api/uiPrototype'
import { historyAssetApi } from '@/api/historyAsset'
import type {
  HistoryAssetItem,
  HistoryClassificationResponse,
} from '@/api/historyAsset'

export type SmartGenStep = 'task' | 'material' | 'context' | 'strategy' | 'generating' | 'preview' | 'save_confirm' | 'save_result'
export type TaskType = 'new_feature' | 'history_update' | 'import_asset'
export type QualityStatus = 'passed' | 'warning' | 'pending_review' | 'rejected'

export interface SmartPreviewCase {
  client_id: string
  source_test_point_id: number | null
  requirement_file_id: number | null
  title: string
  module: string
  precondition: string
  steps: Record<string, unknown>[]
  expected_result: string
  priority: number
  case_type: string
  case_category: string | null
  quality_status: QualityStatus
  quality_issues: Record<string, unknown>[]
  selected_for_save: boolean
  dirty: boolean
  regenerating: boolean
  source_refs: Record<string, unknown>
}

export interface GenerationContext {
  requirement_content: string
  ui_descriptions: string[]
  ui_specs: string[]
  test_points: Record<string, unknown>[]
  history_cases: Record<string, unknown>[]
  context_stats: Record<string, unknown>
  warnings: NormalizedWarning[]
  evidence_refs: Record<string, unknown>
  project_config: Record<string, unknown>
  pagination?: Record<string, unknown>
  files_used?: Record<string, unknown>
}

const WARNING_CODE_MAP: Record<string, string> = {
  UI_NO_MATCH: '未找到匹配的 UI 页面，页面元素需要人工确认',
  REQUIREMENT_NOT_FOUND: '未找到关联需求，本次生成可信度较低',
  REQUIREMENT_KEYWORD_MATCH: '未找到直接关联需求，已按关键词匹配相关需求',
  REQUIREMENT_TRIMMED_BY_KEYWORDS: '需求内容较长，已按测试点关键词裁剪',
  UI_SPEC_MISSING: '部分 UI 页面缺少可交互元素解析，相关步骤需确认',
  UI_PARTIAL_MATCH: '部分 UI 页面未纳入上下文，可能缺少页面信息',
  UI_REQUIRED_ELEMENT_MISSING: '当前 UI 资料可能缺少测试点所需页面元素',
  UI_SCREEN_NOT_FOUND: '部分指定 UI 页面不存在，已跳过',
  UI_FILE_NO_PARSED_SCREENS: '上传的 UI 文件尚未完成解析，页面元素需要人工确认',
  HISTORY_NO_SIMILAR_CASE: '未找到相似历史用例，本次不使用历史参考',
  HISTORY_NO_QUERY_TEXT: '测试点信息不足，未使用历史用例参考',
  HISTORY_LOW_TRUST_FILTERED: '部分历史用例与当前资料不匹配，已排除',
  HISTORY_POTENTIALLY_STALE: '部分历史用例可能过时，已不作为生成依据',
  CONTEXT_COMPLETENESS_LOW: '资料完整度较低，建议保存为草稿后人工复核',
  TEST_POINT_NOT_FOUND: '部分测试点不存在，已跳过',
  UNKNOWN: '存在其他资料提示，建议查看详情',
}

function normalizeWarnings(raw: unknown[]): NormalizedWarning[] {
  return raw.map((w) => {
    if (typeof w === 'string') {
      return { code: 'UNKNOWN', message: w, detail: {} }
    }
    if (typeof w === 'object' && w !== null) {
      const obj = w as Record<string, unknown>
      return {
        code: (obj.code as string) || 'UNKNOWN',
        message: (obj.message as string) || '',
        detail: (obj.detail as Record<string, unknown>) || {},
      }
    }
    return { code: 'UNKNOWN', message: String(w), detail: {} }
  })
}

function getWarningUserText(code: string): string {
  return WARNING_CODE_MAP[code] || '存在其他资料提示，建议查看详情'
}

function computeQualityStatus(
  caseData: Partial<SmartPreviewCase>,
  warnings: NormalizedWarning[],
  contextStats: Record<string, unknown>,
): QualityStatus {
  if (!caseData.title || !caseData.steps?.length || !caseData.expected_result) {
    return 'rejected'
  }
  const missingCore = contextStats.missing_core_context as string[] | undefined
  const hasLowCompleteness = warnings.some((w) => w.code === 'CONTEXT_COMPLETENESS_LOW')
  const hasNoRequirement = warnings.some((w) => w.code === 'REQUIREMENT_NOT_FOUND')
  const hasNoUI = warnings.some((w) => w.code === 'UI_NO_MATCH')
  const hasUIElement = caseData.steps?.some(
    (s) => (s as Record<string, unknown>)?.target_element || (s as Record<string, unknown>)?.action_type === 'click',
  )

  if (hasLowCompleteness || hasNoRequirement || (missingCore && missingCore.includes('requirement'))) {
    return 'pending_review'
  }
  if (hasNoUI && hasUIElement) {
    return 'pending_review'
  }
  if (hasNoUI || warnings.some((w) => ['HISTORY_LOW_TRUST_FILTERED', 'HISTORY_POTENTIALLY_STALE'].includes(w.code))) {
    return 'warning'
  }
  return 'passed'
}

function buildSourceRefs(
  caseData: Record<string, unknown>,
  ctx: GenerationContext | null,
  screenDetails: UIScreen[],
): Record<string, unknown> {
  const refs: Record<string, unknown> = {}
  const tpId = caseData.test_point_id as number | undefined
  if (tpId) {
    const tp = ctx?.test_points.find((t) => (t as Record<string, unknown>).id === tpId)
    if (tp) {
      refs.test_point_name = (tp as Record<string, unknown>).name || (tp as Record<string, unknown>).test_point || `测试点${tpId}`
    }
  }
  const reqFileIds = ctx?.context_stats.requirement_file_ids as number[] | undefined
  if (reqFileIds && reqFileIds.length > 0) {
    const reqFiles = ctx?.evidence_refs.requirement_files as Record<string, unknown>[] | undefined
    if (reqFiles && reqFiles.length > 0) {
      refs.requirement_file_name = reqFiles[0].file_name || reqFiles[0].original_name || `需求文件${reqFileIds[0]}`
    }
  }
  const screenId = caseData.ui_screen_id as number | undefined
  if (screenId) {
    const screen = screenDetails.find((s) => s.id === screenId)
    if (screen) {
      refs.ui_screen_name = screen.screen_name
    }
  }
  const uiScreens = ctx?.evidence_refs.ui_screens as Record<string, unknown>[] | undefined
  if (uiScreens && uiScreens.length > 0 && !refs.ui_screen_name) {
    refs.ui_screen_name = (uiScreens[0].screen_name as string) || `页面${uiScreens[0].id}`
  }
  return refs
}

function normalizeGenerationDescription(raw: string): string {
  const trimmed = raw.trim()
  const withFallback = trimmed.length >= 5 ? trimmed : `${trimmed} 生成测试用例`.trim()
  return withFallback.slice(0, 10000)
}

export const useSmartGenerationStore = defineStore('smartGeneration', () => {
  const currentStep = ref<SmartGenStep>('task')
  const selectedTask = ref<TaskType>('new_feature')
  const selectedProjectId = ref<number | ''>('')
  const batchId = ref<number | null>(null)
  const batchNo = ref<string>('')
  const batchStatus = ref<string>('created')

  const requirementFileIds = ref<number[]>([])
  const testPointIds = ref<number[]>([])
  const uiScreenIds = ref<number[]>([])

  const uiPrototypeProjects = ref<UIPrototypeProject[]>([])
  const selectedUIPrototypeProjectId = ref<number | ''>('')
  const uiScreenDetails = ref<UIScreen[]>([])
  const uiScreenImageUrls = ref<Record<number, string>>({})
  const uiUploadDialogVisible = ref(false)
  const uiUploading = ref(false)
  const uiParsing = ref(false)
  let parsePollingTimer: ReturnType<typeof setTimeout> | null = null
  const deselectedUIScreenIds = ref<Set<number>>(new Set())

  const contextStats = ref<Record<string, unknown>>({})
  const warnings = ref<NormalizedWarning[]>([])
  const evidenceRefs = ref<Record<string, unknown>>({})
  const generationContext = ref<GenerationContext | null>(null)
  const strategy = ref<string>('')
  const scenarioType = ref<string>('B1_REQUIREMENT_TESTPOINT')

  const previewCases = ref<SmartPreviewCase[]>([])
  const qualitySummary = ref<Record<string, number>>({ passed: 0, warning: 0, pending_review: 0, rejected: 0 })

  const generating = ref(false)
  const generationProgress = ref<string>('')
  const saving = ref(false)
  const saveResult = ref<GenerationBatchSaveResponse | null>(null)
  const saveError = ref<string>('')
  const batchCost = ref<BatchCostInfo | null>(null)

  const advancedConfig = ref({
    case_type: 'manual' as string,
    exec_mode: 'manual' as string,
    priority: 2 as number,
    enhanced_mode: true,
    mode: 'linear' as string,
  })

  const historyAssets = ref<HistoryAssetItem[]>([])
  const selectedHistoryAssetIds = ref<number[]>([])
  const historyClassification = ref<HistoryClassificationResponse | null>(null)
  const historyAligning = ref(false)
  const historyItemSelections = ref<Map<string, boolean>>(new Map())

  const materialLevel = computed(() => {
    const hasReq = (contextStats.value.requirements_used as number) > 0
    const hasTP = (contextStats.value.test_points_loaded as number) > 0
    const hasUI = (contextStats.value.ui_screens_used as number) > 0
    if (hasReq && hasTP && hasUI) return 'L3'
    if (hasReq && hasTP) return 'L2'
    if (hasTP || hasReq) return 'L1'
    return 'L0'
  })

  const materialLevelText = computed(() => {
    const map: Record<string, string> = {
      L3: '资料充足：需求 + 测试点 + UI',
      L2: '资料较完整：需求 + 测试点',
      L1: '资料不足：仅有部分资料',
      L0: '不建议生成：关键资料为空',
    }
    return map[materialLevel.value] || ''
  })

  const strategyDisplayText = computed(() => {
    if (strategy.value === 'REQUIREMENT_TESTPOINT_STANDARD_GENERATION') return '标准需求生成'
    if (strategy.value === 'FULL_CONTEXT_GENERATION_LITE') return '完整资料生成'
    return strategy.value
  })

  const warningUserTexts = computed(() => {
    return warnings.value.map((w) => ({
      code: w.code,
      text: getWarningUserText(w.code),
      detail: w.detail,
    }))
  })

  const selectedForSaveCount = computed(() => {
    const previewCount = previewCases.value.filter((c) => c.selected_for_save).length
    const historyCount = Array.from(historyItemSelections.value.values()).filter((v) => v === true).length
    return previewCount + historyCount
  })
  const passedCount = computed(() => previewCases.value.filter((c) => c.quality_status === 'passed').length)
  const warningCount = computed(() => previewCases.value.filter((c) => c.quality_status === 'warning').length)
  const pendingReviewCount = computed(() => previewCases.value.filter((c) => c.quality_status === 'pending_review').length)
  const rejectedCount = computed(() => previewCases.value.filter((c) => c.quality_status === 'rejected').length)

  function recalcQualitySummary() {
    qualitySummary.value = {
      passed: previewCases.value.filter((c) => c.quality_status === 'passed').length,
      warning: previewCases.value.filter((c) => c.quality_status === 'warning').length,
      pending_review: previewCases.value.filter((c) => c.quality_status === 'pending_review').length,
      rejected: previewCases.value.filter((c) => c.quality_status === 'rejected').length,
    }
  }

  async function createBatch() {
    if (selectedTask.value === 'history_update') {
      const hasExcel = historyAssets.value.some(
        (a) => a.asset_type === 'excel' && selectedHistoryAssetIds.value.includes(a.id),
      )
      const hasXMind = historyAssets.value.some(
        (a) => a.asset_type === 'xmind' && selectedHistoryAssetIds.value.includes(a.id),
      )
      const hasReq = requirementFileIds.value.length > 0
      const hasUI = uiScreenIds.value.length > 0

      if (hasExcel && hasReq && hasUI) {
        scenarioType.value = 'A2_HISTORY_EXCEL_REQUIREMENT_UI'
        strategy.value = 'HISTORY_INCREMENTAL_UPDATE'
      } else if (hasXMind && hasReq && hasUI) {
        scenarioType.value = 'A3_HISTORY_XMIND_REQUIREMENT_UI'
        strategy.value = 'HISTORY_INCREMENTAL_UPDATE'
      } else if (hasXMind && hasUI) {
        scenarioType.value = 'B2_HISTORY_XMIND_UI'
        strategy.value = 'HISTORY_UI_ADAPTATION'
      } else if (hasExcel && hasUI) {
        scenarioType.value = 'B3_HISTORY_EXCEL_UI'
        strategy.value = 'HISTORY_UI_ADAPTATION'
      } else {
        scenarioType.value = 'A2_HISTORY_EXCEL_REQUIREMENT_UI'
        strategy.value = 'HISTORY_INCREMENTAL_UPDATE'
      }

      const payload: Record<string, unknown> = {
        project_id: selectedProjectId.value as number,
        entry_type: 'HISTORY_UPDATE',
        scenario_type: scenarioType.value,
        generation_strategy: strategy.value,
        requirement_file_ids: requirementFileIds.value,
        test_point_ids: testPointIds.value,
        ui_screen_ids: uiScreenIds.value,
        history_asset_ids: selectedHistoryAssetIds.value,
      }
      const result = await generationBatchApi.create(payload as unknown as GenerationBatchCreatePayload)
      batchId.value = result.id
      batchNo.value = result.batch_no
      batchStatus.value = result.status
      return
    }

    const hasUI = uiScreenIds.value.length > 0
    scenarioType.value = hasUI ? 'A1_REQUIREMENT_TESTPOINT_UI' : 'B1_REQUIREMENT_TESTPOINT'
    strategy.value = hasUI ? 'FULL_CONTEXT_GENERATION_LITE' : 'REQUIREMENT_TESTPOINT_STANDARD_GENERATION'

    const payload: GenerationBatchCreatePayload = {
      project_id: selectedProjectId.value as number,
      entry_type: 'NEW_FEATURE_GENERATION',
      scenario_type: scenarioType.value as GenerationBatchCreatePayload['scenario_type'],
      generation_strategy: strategy.value as GenerationBatchCreatePayload['generation_strategy'],
      requirement_file_ids: requirementFileIds.value,
      test_point_ids: testPointIds.value,
      ui_screen_ids: uiScreenIds.value,
    }
    const result = await generationBatchApi.create(payload)
    batchId.value = result.id
    batchNo.value = result.batch_no
    batchStatus.value = result.status
  }

  async function fetchContext() {
    generationProgress.value = '正在读取需求...'
    const contextResp = await aiApi.generateContext({
      project_id: selectedProjectId.value,
      requirement_file_ids: requirementFileIds.value,
      test_point_ids: testPointIds.value,
      ui_screen_ids: uiScreenIds.value,
      test_point_page: 1,
      test_point_page_size: 500,
    })
    const respData = ((contextResp as { data?: unknown })?.data || contextResp) as Record<string, unknown>

    generationProgress.value = '正在分析测试点...'
    const rawWarnings = normalizeWarnings((respData.warnings as unknown[]) || [])
    warnings.value = rawWarnings
    contextStats.value = (respData.context_stats as Record<string, unknown>) || {}
    evidenceRefs.value = (respData.evidence_refs as Record<string, unknown>) || {}

    generationContext.value = {
      requirement_content: (respData.requirement_content as string) || '',
      ui_descriptions: (respData.ui_descriptions as string[]) || [],
      ui_specs: (respData.ui_specs as string[]) || [],
      test_points: (respData.test_points as Record<string, unknown>[]) || [],
      history_cases: (respData.history_cases as Record<string, unknown>[]) || [],
      context_stats: contextStats.value,
      warnings: rawWarnings,
      evidence_refs: evidenceRefs.value,
      project_config: (respData.project_config as Record<string, unknown>) || {},
      pagination: respData.pagination as Record<string, unknown>,
      files_used: respData.files_used as Record<string, unknown>,
    }

    generationProgress.value = '正在检查 UI 资料...'

    if (selectedTask.value !== 'history_update') {
      const hasUI = uiScreenIds.value.length > 0
      scenarioType.value = hasUI ? 'A1_REQUIREMENT_TESTPOINT_UI' : 'B1_REQUIREMENT_TESTPOINT'
      strategy.value = hasUI ? 'FULL_CONTEXT_GENERATION_LITE' : 'REQUIREMENT_TESTPOINT_STANDARD_GENERATION'
    }

    if (batchId.value) {
      await generationBatchApi.update(batchId.value, {
        status: 'context_ready',
        context_stats: contextStats.value,
        warnings: rawWarnings,
        evidence_refs: evidenceRefs.value,
      })
      batchStatus.value = 'context_ready'
    }

    generationProgress.value = ''
  }

  async function startGeneration() {
    if (!generationContext.value) return
    generating.value = true
    generationProgress.value = '正在组织生成资料...'
    previewCases.value = []

    try {
      if (batchId.value) {
        await generationBatchApi.update(batchId.value, { status: 'generating' })
        batchStatus.value = 'generating'
      }

      const ctx = generationContext.value
      const hasUI = uiScreenIds.value.length > 0
      const caseType = hasUI ? 'manual' : 'manual'
      const execMode = hasUI ? 'all' : 'manual'

      const description = normalizeGenerationDescription(
        `基于本批次需求文档、测试点和可选 UI 资料生成测试用例`,
      )

      generationProgress.value = '正在生成测试用例...'

      const response = await fetch('/api/v1/testCase/ai-enhanced-generate/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          project_id: selectedProjectId.value,
          description,
          case_type: caseType,
          exec_mode: execMode,
          priority: 2,
          enhanced_mode: true,
          mode: 'linear',
          context: {
            requirement_content: ctx.requirement_content,
            test_points: ctx.test_points,
            ui_descriptions: ctx.ui_descriptions,
            ui_specs: ctx.ui_specs,
            history_cases: ctx.history_cases,
            context_stats: ctx.context_stats,
            warnings: ctx.warnings,
            evidence_refs: ctx.evidence_refs,
            project_config: ctx.project_config,
            pagination: ctx.pagination,
            files_used: ctx.files_used,
          },
        }),
      })

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法获取流式响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice(6)
          try {
            const event = JSON.parse(jsonStr)
            if (event.code === 0) {
              if (event.data?.status === 'started') {
                generationProgress.value = '正在准备生成...'
              } else if (event.data?.status === 'building_prompt') {
                generationProgress.value = '正在组织生成资料...'
              } else if (event.data?.status === 'generating') {
                generationProgress.value = '正在生成测试用例...'
              } else if (Array.isArray(event.data)) {
                generationProgress.value = '正在准备预览结果...'
                const cases = event.data
                for (const c of cases) {
                  const previewCase: SmartPreviewCase = {
                    client_id: `case-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                    source_test_point_id: c.test_point_id || null,
                    requirement_file_id: null,
                    title: c.title || '',
                    module: c.module || '',
                    precondition: c.precondition || '',
                    steps: c.steps || [],
                    expected_result: c.expected_result || '',
                    priority: c.priority || 2,
                    case_type: c.case_type || 'manual',
                    case_category: c.test_category || c.case_category || null,
                    quality_status: 'pending_review',
                    quality_issues: [],
                    selected_for_save: true,
                    dirty: false,
                    regenerating: false,
                    source_refs: buildSourceRefs(c, generationContext.value, uiScreenDetails.value),
                  }
                  previewCase.quality_status = computeQualityStatus(previewCase, warnings.value, contextStats.value)
                  if (previewCase.quality_status === 'rejected') {
                    previewCase.selected_for_save = false
                  }
                  previewCases.value.push(previewCase)
                }
              } else if (event.data && typeof event.data === 'object' && !Array.isArray(event.data) && event.data.title) {
                const c = event.data
                const previewCase: SmartPreviewCase = {
                  client_id: `case-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
                  source_test_point_id: c.test_point_id || null,
                  requirement_file_id: null,
                  title: c.title || '',
                  module: c.module || '',
                  precondition: c.precondition || '',
                  steps: c.steps || [],
                  expected_result: c.expected_result || '',
                  priority: c.priority || 2,
                  case_type: c.case_type || 'manual',
                  case_category: c.test_category || c.case_category || null,
                  quality_status: 'pending_review',
                  quality_issues: [],
                  selected_for_save: true,
                  dirty: false,
                  regenerating: false,
                  source_refs: buildSourceRefs(c, generationContext.value, uiScreenDetails.value),
                }
                previewCase.quality_status = computeQualityStatus(previewCase, warnings.value, contextStats.value)
                if (previewCase.quality_status === 'rejected') previewCase.selected_for_save = false
                previewCases.value.push(previewCase)
              }
            } else if (event.code === 1) {
              generationProgress.value = event.message || '生成的用例均未通过质量校验'
            } else if (event.code === 500) {
              throw new Error(event.message || '生成失败')
            }
          } catch {
            // ignore parse errors for incomplete chunks
          }
        }
      }

      recalcQualitySummary()

      if (batchId.value) {
        await generationBatchApi.update(batchId.value, {
          status: 'preview_ready',
          quality_summary: qualitySummary.value as unknown as Record<string, unknown>,
        })
        batchStatus.value = 'preview_ready'
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '生成失败'
      generationProgress.value = msg
      if (batchId.value) {
        await generationBatchApi.update(batchId.value, { status: 'failed' }).catch(() => {})
        batchStatus.value = 'failed'
      }
    } finally {
      generating.value = false
    }
  }

  async function saveBatch(saveMode: 'draft' | 'formal' | 'passed_only') {
    if (!batchId.value) return
    saving.value = true
    saveError.value = ''
    saveResult.value = null

    try {
      const idempotencyKey = `${batchId.value}-${Date.now()}`
      let casesToSave: PreviewCasePayload[]

      if (selectedTask.value === 'history_update' && historyClassification.value) {
        casesToSave = historyClassification.value.items
          .filter((item) => {
            if (item.classification === 'REUSE_CASE') return false
            if (item.classification === 'CONFIRM_REQUIRED') return false
            const userSelection = historyItemSelections.value.get(item.client_id)
            if (userSelection !== true) return false
            return true
          })
          .map((item) => {
            if (item.classification === 'DEPRECATED_CASE') {
              const userSelection = historyItemSelections.value.get(item.client_id)
              return {
                client_id: item.client_id,
                title: '',
                module: '',
                precondition: '',
                steps: [],
                expected_result: '',
                priority: 2,
                case_type: 'manual',
                quality_status: 'pending_review' as const,
                selected_for_save: userSelection === true,
                classification: item.classification,
                history_case_id: item.matched_system_case_id || null,
                update_action: 'deprecate' as const,
                diff_fields: item.diff_fields || null,
              } as PreviewCasePayload
            }
            const caseData = item.suggested_case || item.history_case
            if (!caseData) return null
            let updateAction: 'create_new' | 'update_existing' | 'skip' | 'deprecate' = 'create_new'
            if (item.classification === 'UPDATE_CASE') updateAction = 'update_existing'
            else if (item.classification === 'NEW_CASE') updateAction = 'create_new'
            const userSelection = historyItemSelections.value.get(item.client_id)
            return {
              client_id: item.client_id,
              title: caseData.title || '',
              module: caseData.module || '',
              precondition: caseData.precondition || '',
              steps: (caseData.steps || []).map((s: Record<string, unknown>, idx: number) => ({
                step: s.step ?? s.step_number ?? (idx + 1),
                action: String(s.action || s.step || ''),
                expected_result: String(s.expected_result || ''),
              })),
              expected_result: caseData.expected_result || '',
              priority: caseData.priority || 2,
              case_type: 'manual',
              quality_status: 'pending_review' as const,
              selected_for_save: userSelection === true,
              classification: item.classification,
              history_case_id: item.matched_system_case_id || null,
              update_action: updateAction,
              diff_fields: item.diff_fields || null,
            } as PreviewCasePayload
          })
          .filter((c): c is PreviewCasePayload => c !== null)
      } else {
        casesToSave = previewCases.value
          .filter((c) => {
            if (saveMode === 'passed_only') return c.quality_status === 'passed' || c.quality_status === 'warning'
            return c.selected_for_save
          })
          .map((c) => ({
            client_id: c.client_id,
            source_test_point_id: c.source_test_point_id,
            requirement_file_id: c.requirement_file_id,
            title: c.title,
            module: c.module,
            precondition: c.precondition,
            steps: c.steps as unknown as PreviewCasePayload['steps'],
            expected_result: c.expected_result,
            priority: c.priority,
            case_type: c.case_type,
            case_category: c.case_category,
            quality_status: c.quality_status,
            quality_issues: c.quality_issues,
            selected_for_save: c.selected_for_save,
            source_refs: c.source_refs,
          }))
      }

      if (casesToSave.length === 0) {
        saveError.value = '没有可保存的用例'
        return
      }

      const payload: GenerationBatchSavePayload = {
        idempotency_key: idempotencyKey,
        save_mode: saveMode,
        cases: casesToSave,
      }

      const result = await generationBatchApi.save(batchId.value, payload)
      saveResult.value = result
      batchStatus.value = result.status
      // 保存成功后查询成本
      fetchBatchCost()
    } catch (e: unknown) {
      saveError.value = e instanceof Error ? e.message : '保存失败'
    } finally {
      saving.value = false
    }
  }

  function toggleCaseSelection(clientId: string) {
    const c = previewCases.value.find((pc) => pc.client_id === clientId)
    if (c) c.selected_for_save = !c.selected_for_save
  }

  async function fetchBatchCost() {
    if (!batchId.value) return
    try {
      batchCost.value = await aiInvocationApi.getBatchCost(batchId.value)
    } catch {
      batchCost.value = null
    }
  }

  function removeCase(clientId: string) {
    previewCases.value = previewCases.value.filter((c) => c.client_id !== clientId)
    recalcQualitySummary()
  }

  async function regenerateSingleCase(clientId: string) {
    const caseIndex = previewCases.value.findIndex((c) => c.client_id === clientId)
    if (caseIndex === -1) return
    if (!generationContext.value) return

    const oldCase = previewCases.value[caseIndex]
    oldCase.regenerating = true

    try {
      const ctx = generationContext.value
      const description = normalizeGenerationDescription(
        `重新生成测试用例：${oldCase.title}`,
      )

      const response = await fetch('/api/v1/testCase/ai-enhanced-generate/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: JSON.stringify({
          project_id: selectedProjectId.value,
          description,
          case_type: advancedConfig.value.case_type,
          exec_mode: advancedConfig.value.exec_mode,
          priority: oldCase.priority,
          enhanced_mode: advancedConfig.value.enhanced_mode,
          mode: advancedConfig.value.mode,
          test_point_id: oldCase.source_test_point_id,
          context: {
            requirement_content: ctx.requirement_content,
            test_points: ctx.test_points,
            ui_descriptions: ctx.ui_descriptions,
            ui_specs: ctx.ui_specs,
            history_cases: ctx.history_cases,
            context_stats: ctx.context_stats,
            warnings: ctx.warnings,
            evidence_refs: ctx.evidence_refs,
            project_config: ctx.project_config,
            pagination: ctx.pagination,
            files_used: ctx.files_used,
          },
        }),
      })

      const reader = response.body?.getReader()
      if (!reader) throw new Error('无法获取流式响应')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data: ')) continue
          const jsonStr = trimmed.slice(6)
          try {
            const event = JSON.parse(jsonStr)
            if (event.code === 0) {
              let newCaseData: Record<string, unknown> | null = null
              if (Array.isArray(event.data) && event.data.length > 0) {
                newCaseData = event.data[0]
              } else if (event.data && typeof event.data === 'object' && !Array.isArray(event.data) && event.data.title) {
                newCaseData = event.data
              }
              if (newCaseData) {
                const c = newCaseData
                const replacement: SmartPreviewCase = {
                  client_id: oldCase.client_id,
                  source_test_point_id: (c.test_point_id as number) || oldCase.source_test_point_id,
                  requirement_file_id: oldCase.requirement_file_id,
                  title: (c.title as string) || '',
                  module: (c.module as string) || '',
                  precondition: (c.precondition as string) || '',
                  steps: (c.steps as Record<string, unknown>[]) || [],
                  expected_result: (c.expected_result as string) || '',
                  priority: (c.priority as number) || 2,
                  case_type: (c.case_type as string) || 'manual',
                  case_category: (c.test_category as string) || (c.case_category as string) || null,
                  quality_status: 'pending_review',
                  quality_issues: [],
                  selected_for_save: true,
                  dirty: false,
                  regenerating: false,
                  source_refs: buildSourceRefs(c, generationContext.value, uiScreenDetails.value),
                }
                replacement.quality_status = computeQualityStatus(replacement, warnings.value, contextStats.value)
                if (replacement.quality_status === 'rejected') replacement.selected_for_save = false
                previewCases.value[caseIndex] = replacement
                recalcQualitySummary()
                return
              }
            } else if (event.code === 500) {
              throw new Error(event.message || '重新生成失败')
            }
          } catch (parseErr) {
            if (parseErr instanceof Error && parseErr.message.includes('重新生成')) throw parseErr
          }
        }
      }
    } catch (e: unknown) {
      oldCase.regenerating = false
      throw e
    } finally {
      oldCase.regenerating = false
    }
  }

  const coverageSummary = computed(() => {
    const total = previewCases.value.length
    const byCategory: Record<string, number> = {}
    const byTestPoint: Record<string, number> = {}
    for (const c of previewCases.value) {
      const cat = c.case_category || '未分类'
      byCategory[cat] = (byCategory[cat] || 0) + 1
      const tpKey = c.source_test_point_id ? `TP-${c.source_test_point_id}` : '无测试点'
      byTestPoint[tpKey] = (byTestPoint[tpKey] || 0) + 1
    }
    return { total, byCategory, byTestPoint }
  })

  const evidenceRefsDisplay = computed(() => {
    const refs = evidenceRefs.value
    const result: { type: string; label: string; items: string[] }[] = []
    const reqFiles = refs.requirement_files as Record<string, unknown>[] | undefined
    if (reqFiles && reqFiles.length > 0) {
      result.push({
        type: 'requirement',
        label: '需求文档',
        items: reqFiles.map((f) => (f.file_name as string) || (f.original_name as string) || `文件${f.id}`),
      })
    }
    const uiScreens = refs.ui_screens as Record<string, unknown>[] | undefined
    if (uiScreens && uiScreens.length > 0) {
      result.push({
        type: 'ui',
        label: 'UI页面',
        items: uiScreens.map((s) => (s.screen_name as string) || `页面${s.id}`),
      })
    }
    const historyCases = refs.history_cases as Record<string, unknown>[] | undefined
    if (historyCases && historyCases.length > 0) {
      result.push({
        type: 'history',
        label: '历史参考',
        items: historyCases.map((h) => (h.title as string) || `用例${h.id}`),
      })
    }
    return result
  })

  const uiScreenParseStatusMap = computed(() => {
    const map: Record<number, string> = {}
    for (const s of uiScreenDetails.value) {
      map[s.id] = s.parse_status || 'pending'
    }
    return map
  })

  const uiScreenMatchResults = computed(() => {
    const refs = evidenceRefs.value
    const screens = refs.ui_screens as Record<string, unknown>[] | undefined
    if (!screens || !Array.isArray(screens)) return []
    return screens.map((s) => ({
      screen_name: (s.screen_name as string) || `页面${s.id}`,
      confidence: (s.confidence as string) || 'unknown',
      element_count: (s.element_count as number) || 0,
    }))
  })

  const hasUIParseFailure = computed(() => {
    return uiScreenDetails.value.some((s) => s.parse_status === 'failed')
  })

  const hasUIParsePending = computed(() => {
    return uiScreenDetails.value.some((s) => s.parse_status === 'pending' || s.parse_status === 'running')
  })

  async function loadUIPrototypeProjects() {
    if (!selectedProjectId.value) { uiPrototypeProjects.value = []; return }
    try {
      const resp = await uiPrototypeApi.getUIPrototypeProjectList(selectedProjectId.value as number)
      const data = (resp as { data?: unknown })?.data || resp
      uiPrototypeProjects.value = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
    } catch { uiPrototypeProjects.value = [] }
  }

  async function loadUIScreenDetails() {
    if (!selectedProjectId.value) { uiScreenDetails.value = []; return }
    try {
      const resp = await uiPrototypeApi.getUIScreenList(
        selectedProjectId.value as number,
        selectedUIPrototypeProjectId.value as number || undefined,
      )
      const data = (resp as { data?: unknown })?.data || resp
      const screens = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
      uiScreenDetails.value = screens
      const completedIds = new Set(screens.filter((s) => s.parse_status === 'completed').map((s) => s.id))
      const prevSelected = new Set(uiScreenIds.value)
      const newSelected = [...prevSelected].filter((id) => completedIds.has(id))
      if (newSelected.length === 0 && prevSelected.size === 0) {
        uiScreenIds.value = [...completedIds].filter((id) => !deselectedUIScreenIds.value.has(id))
      } else {
        for (const id of completedIds) {
          if (!prevSelected.has(id) && !deselectedUIScreenIds.value.has(id)) {
            newSelected.push(id)
          }
        }
        uiScreenIds.value = newSelected
      }
    } catch { uiScreenDetails.value = [] }
  }

  async function loadUIScreenImages() {
    for (const screen of uiScreenDetails.value) {
      if (!screen.id || !screen.original_file_path) continue
      if (uiScreenImageUrls.value[screen.id]) continue
      try {
        const resp = await fetch(`/api/v1/file/preview-screen/${screen.id}`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
        })
        if (!resp.ok) continue
        const blob = await resp.blob()
        if (blob.size > 0) {
          uiScreenImageUrls.value[screen.id] = URL.createObjectURL(blob)
        }
      } catch { /* ignore */ }
    }
  }

  async function handleUIPrototypeProjectChange(projectId: number | '') {
    selectedUIPrototypeProjectId.value = projectId
    cancelParsePolling()
    uiScreenDetails.value = []
    uiScreenIds.value = []
    deselectedUIScreenIds.value = new Set()
    Object.values(uiScreenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url)
    })
    uiScreenImageUrls.value = {}
    if (projectId) {
      await loadUIScreenDetails()
      await loadUIScreenImages()
    }
  }

  async function uploadUIScreens(files: File[]) {
    if (!selectedProjectId.value || files.length === 0) return
    uiUploading.value = true
    try {
      const result = await uiPrototypeApi.uploadUIScreens(
        selectedProjectId.value as number,
        files,
        `智能生成上传-${new Date().toLocaleDateString()}`,
        selectedUIPrototypeProjectId.value as number || undefined,
      )
      const respData = (result as { data?: unknown })?.data || result
      const newPrototypeProjectId = (respData as Record<string, unknown>)?.prototype_project_id as number | undefined
      if (newPrototypeProjectId && !selectedUIPrototypeProjectId.value) {
        selectedUIPrototypeProjectId.value = newPrototypeProjectId
        await loadUIPrototypeProjects()
      }
      await loadUIScreenDetails()
      await loadUIScreenImages()
      const pendingIds = uiScreenDetails.value
        .filter((s) => s.parse_status === 'pending')
        .map((s) => s.id)
      if (pendingIds.length > 0) {
        parseUIScreens(pendingIds)
      }
    } finally {
      uiUploading.value = false
    }
  }

  async function parseUIScreens(screenIds: number[]) {
    if (screenIds.length === 0) return
    uiParsing.value = true
    try {
      await uiPrototypeApi.parseUIScreens(screenIds)
      startParsePolling(screenIds)
    } catch {
      uiParsing.value = false
    }
  }

  function cancelParsePolling() {
    if (parsePollingTimer !== null) {
      clearTimeout(parsePollingTimer)
      parsePollingTimer = null
    }
    uiParsing.value = false
  }

  function startParsePolling(screenIds: number[]) {
    const maxPolls = 60
    const pollInterval = 3000
    let pollCount = 0
    cancelParsePolling()
    const poll = async () => {
      try {
        await loadUIScreenDetails()
        const allDone = screenIds.every((sid) => {
          const screen = uiScreenDetails.value.find((s) => s.id === sid)
          return screen && (screen.parse_status === 'completed' || screen.parse_status === 'failed')
        })
        pollCount++
        if (allDone || pollCount >= maxPolls) {
          await loadUIScreenImages()
          parsePollingTimer = null
          uiParsing.value = false
          return
        }
        parsePollingTimer = setTimeout(poll, pollInterval)
      } catch {
        parsePollingTimer = null
        uiParsing.value = false
      }
    }
    parsePollingTimer = setTimeout(poll, pollInterval)
  }

  function toggleUIScreen(screenId: number) {
    const idx = uiScreenIds.value.indexOf(screenId)
    if (idx >= 0) {
      uiScreenIds.value.splice(idx, 1)
      deselectedUIScreenIds.value.add(screenId)
    } else {
      uiScreenIds.value.push(screenId)
      deselectedUIScreenIds.value.delete(screenId)
    }
  }

  async function loadHistoryAssets() {
    if (!selectedProjectId.value) { historyAssets.value = []; return }
    try {
      const result = await historyAssetApi.getList(selectedProjectId.value as number)
      historyAssets.value = Array.isArray(result) ? result : []
    } catch { historyAssets.value = [] }
  }

  async function uploadHistoryAsset(file: File, assetType: string) {
    if (!selectedProjectId.value) return
    const result = await historyAssetApi.upload(selectedProjectId.value as number, file, assetType)
    historyAssets.value.push(result)
    selectedHistoryAssetIds.value.push(result.id)
  }

  async function importSystemCasesAsHistory(caseIds: number[]) {
    if (!selectedProjectId.value || caseIds.length === 0) return
    const result = await historyAssetApi.importSystemCases(selectedProjectId.value as number, caseIds)
    historyAssets.value.push(result)
    selectedHistoryAssetIds.value.push(result.id)
  }

  async function alignHistoryAssets() {
    if (!selectedProjectId.value || selectedHistoryAssetIds.value.length === 0) return
    historyAligning.value = true
    try {
      const result = await historyAssetApi.align({
        project_id: selectedProjectId.value as number,
        history_asset_ids: selectedHistoryAssetIds.value,
        requirement_file_ids: requirementFileIds.value.length > 0 ? requirementFileIds.value : undefined,
        ui_screen_ids: uiScreenIds.value.length > 0 ? uiScreenIds.value : undefined,
      })
      historyClassification.value = result
      const newSelections = new Map(historyItemSelections.value)
      for (const item of result.items) {
        if (item.classification === 'NEW_CASE') {
          newSelections.set(item.client_id, true)
        }
      }
      historyItemSelections.value = newSelections
    } catch {
      historyClassification.value = null
    } finally {
      historyAligning.value = false
    }
  }

  function removeHistoryAsset(assetId: number) {
    selectedHistoryAssetIds.value = selectedHistoryAssetIds.value.filter((id) => id !== assetId)
    historyAssets.value = historyAssets.value.filter((a) => a.id !== assetId)
  }

  function setHistoryItemSelection(clientId: string, selected: boolean) {
    historyItemSelections.value.set(clientId, selected)
  }

  function reset() {
    cancelParsePolling()
    currentStep.value = 'task'
    selectedTask.value = 'new_feature'
    selectedProjectId.value = ''
    batchId.value = null
    batchNo.value = ''
    batchStatus.value = 'created'
    requirementFileIds.value = []
    testPointIds.value = []
    uiScreenIds.value = []
    uiPrototypeProjects.value = []
    selectedUIPrototypeProjectId.value = ''
    uiScreenDetails.value = []
    Object.values(uiScreenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) URL.revokeObjectURL(url)
    })
    uiScreenImageUrls.value = {}
    uiUploadDialogVisible.value = false
    uiUploading.value = false
    uiParsing.value = false
    deselectedUIScreenIds.value = new Set()
    contextStats.value = {}
    warnings.value = []
    evidenceRefs.value = {}
    generationContext.value = null
    strategy.value = ''
    scenarioType.value = 'B1_REQUIREMENT_TESTPOINT'
    previewCases.value = []
    qualitySummary.value = { passed: 0, warning: 0, pending_review: 0, rejected: 0 }
    generating.value = false
    generationProgress.value = ''
    saving.value = false
    saveResult.value = null
    saveError.value = ''
    batchCost.value = null
    advancedConfig.value = {
      case_type: 'manual',
      exec_mode: 'manual',
      priority: 2,
      enhanced_mode: true,
      mode: 'linear',
    }
    historyAssets.value = []
    selectedHistoryAssetIds.value = []
    historyClassification.value = null
    historyAligning.value = false
    historyItemSelections.value = new Map()
  }

  return {
    currentStep,
    selectedTask,
    selectedProjectId,
    batchId,
    batchNo,
    batchStatus,
    requirementFileIds,
    testPointIds,
    uiScreenIds,
    uiPrototypeProjects,
    selectedUIPrototypeProjectId,
    uiScreenDetails,
    uiScreenImageUrls,
    uiUploadDialogVisible,
    uiUploading,
    uiParsing,
    contextStats,
    warnings,
    evidenceRefs,
    generationContext,
    strategy,
    scenarioType,
    previewCases,
    qualitySummary,
    generating,
    generationProgress,
    saving,
    saveResult,
    saveError,
    batchCost,
    advancedConfig,
    materialLevel,
    materialLevelText,
    strategyDisplayText,
    warningUserTexts,
    selectedForSaveCount,
    passedCount,
    warningCount,
    pendingReviewCount,
    rejectedCount,
    createBatch,
    fetchContext,
    startGeneration,
    saveBatch,
    toggleCaseSelection,
    removeCase,
    regenerateSingleCase,
    fetchBatchCost,
    recalcQualitySummary,
    coverageSummary,
    evidenceRefsDisplay,
    uiScreenParseStatusMap,
    uiScreenMatchResults,
    hasUIParseFailure,
    hasUIParsePending,
    loadUIPrototypeProjects,
    loadUIScreenDetails,
    loadUIScreenImages,
    handleUIPrototypeProjectChange,
    uploadUIScreens,
    parseUIScreens,
    cancelParsePolling,
    toggleUIScreen,
    historyAssets,
    selectedHistoryAssetIds,
    historyClassification,
    historyAligning,
    historyItemSelections,
    loadHistoryAssets,
    uploadHistoryAsset,
    importSystemCasesAsHistory,
    alignHistoryAssets,
    removeHistoryAsset,
    setHistoryItemSelection,
    reset,
  }
})
