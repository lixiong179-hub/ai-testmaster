import type { ComputedRef, Ref } from 'vue'
import type { TestCase, AIEnhancedGenerateQuality } from '@/api/case'
import type { Project } from '@/api/project'
import type { ProjectFile } from '@/api/file'
import type { TestPoint } from '@/api/testPoint'
import type { ProgressStatus, TagType } from '@/types/element-plus'
import type { UIPrototypeProject, UIScreen } from '@/api/uiPrototype'
import type { FlowEdgeData, FlowNodeData } from '@/store/flowSort'

export interface GeneratedStep {
  step: number | string
  action: string
  param?: string
  expected_result?: string
  action_type?: string
  input_value?: string
  target_element?: string
  test_data?: Record<string, unknown>
  description?: string
  display_action?: string
  ui_elements?: Array<{ type?: string; label?: string }>
}

export interface GeneratedCase {
  id: number
  test_point_id: number | null
  test_point_label: string
  title: string
  module: string
  case_type: string
  test_category?: string
  precondition: string
  test_data?: Record<string, Record<string, string | number | boolean | null>>
  steps: GeneratedStep[]
  expected_result: string
  priority: number
  scene?: string
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
  _error?: string
  _saved?: boolean
  _dbId?: number
}

export interface EditingCase {
  title: string
  module: string
  case_type: string
  test_category?: string
  precondition: string
  expected_result: string
  priority: number
  steps: GeneratedStep[]
  test_data?: Record<string, Record<string, string | number | boolean | null>>
  ai_change_type?: 'added' | 'modified' | 'deprecated'
  parent_case_id?: number | null
}

export interface ContextPreview {
  title: string
  type: 'success' | 'warning' | 'info' | 'error'
  requirement?: string
  ui?: string
  uiSpecs?: number
  requirement_content?: string
  test_points?: TestPoint[]
}

export interface GenerateFormData {
  project_id: number | ''
  requirement_file_ids: number[]
  ui_file_ids: number[]
  ui_screen_ids: number[]
  test_point_ids: number[]
  test_points_data: TestPoint[]
  scene: string
  case_type: string
  exec_mode: 'all' | 'ui_auto' | 'manual'
  priority: number
  enhanced_mode: boolean
  extra_requirements: string
}

export interface SaveSingleCaseParam {
  id: number
  test_point_id?: number | null
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
  _saved?: boolean
  _dbId?: number
}

export interface StoreActions {
  nextCaseId: () => number
  handleSourceFileChange: () => void
  loadTestPoints: (page?: number, append?: boolean, refreshKey?: boolean) => Promise<void>
  loadProjectFiles: () => Promise<void>
  loadUIPrototypeProjects: () => Promise<void>
  loadProjectCases: () => Promise<void>
  loadUIScreens: (uiPrototypeProjectId: number) => Promise<void>
  saveSingleCaseToDb: (c: SaveSingleCaseParam) => Promise<boolean>
  handleRegenerateCase: (
    index: number,
    skipConfirm?: boolean,
    preserveGenerating?: boolean
  ) => Promise<void>
}

export interface UseGenerateFormReturn {
  linkedFilename: Ref<string>
  currentStep: Ref<number>
  saving: Ref<boolean>
  errorMessage: Ref<string>
  errorSuggestions: Ref<string[]>
  projects: Ref<Project[]>
  projectsLoading: Ref<boolean>
  projectsLoaded: Ref<boolean>
  requirementFiles: Ref<ProjectFile[]>
  uiFiles: Ref<ProjectFile[]>
  uiPrototypeProjects: Ref<UIPrototypeProject[]>
  selectedUiPrototypeProjectId: Ref<number | ''>
  uiScreens: Ref<UIScreen[]>
  screenImageUrls: Ref<Record<number, string>>
  isLoadingScreenImages: Ref<boolean>
  showParseWarning: Ref<boolean>
  projectCases: Ref<TestCase[]>
  selectedHistoryCaseIds: Ref<number[]>
  _historyCaseUserCleared: Ref<boolean>
  isLoadingProjectCases: Ref<boolean>
  contextPreview: Ref<ContextPreview | null>
  lastContext: Ref<Record<string, unknown>>
  formData: GenerateFormData
  generationQuality: Ref<AIEnhancedGenerateQuality | null>
  selectedUiPrototypeProject: ComputedRef<UIPrototypeProject | null>
  flowSortModuleInfo: ComputedRef<{ name: string; description: string }>
  screenPreviewStatusType: ComputedRef<string>
  screenPreviewStatusText: ComputedRef<string>
  canGenerate: ComputedRef<boolean>
  generateButtonLabel: ComputedRef<string>
  progressStatus: ComputedRef<ProgressStatus>
  getProjects: (forceReload?: boolean) => Promise<void>
  loadProjectFiles: () => Promise<void>
  loadUIPrototypeProjects: () => Promise<void>
  loadUIScreens: (uiPrototypeProjectId: number) => Promise<void>
  loadScreenImages: () => Promise<void>
  handleUIPrototypeProjectChange: (projectId: number | string) => Promise<void>
  handleProjectChange: () => Promise<void>
  handleProjectFocus: () => void
  extractFileContent: () => Promise<void>
  nextStep: () => void
  prevStep: () => void
  skipToStep2: () => void
  handleCaseTypeChange: (val: string) => void
  loadProjectCases: () => Promise<void>
  cleanupScreenImages: () => void
  cleanupStaleScreenImages: () => void
}

export interface UseGenerateTestPointReturn {
  testPoints: Ref<TestPoint[]>
  testPointPage: Ref<number>
  testPointPageSize: Ref<number>
  testPointTotal: Ref<number>
  testPointAllIds: Ref<number[]>
  testPointSelectKey: Ref<number>
  isLoadingMore: Ref<boolean>
  testPointCache: Map<number, TestPoint>
  selectedTestPointsForDisplay: ComputedRef<
    Array<
      | TestPoint
      | {
          id: number
          module: string
          function: string
          point: string
          priority: number
        }
    >
  >
  loadTestPoints: (page?: number, append?: boolean, refreshKey?: boolean) => Promise<void>
  handleSourceFileChange: () => void
  selectAllTestPoints: () => void
  deselectAllTestPoints: () => void
  addTestPoint: (id: number) => void
  removeTestPoint: (id: number) => void
  getTestPointLabel: (id: number) => string
  selectCurrentPageAll: () => void
  goToTestPointPage: (page: number) => Promise<void>
  getSelectedTagType: (id: number) => TagType
}

export interface UseGenerateAIReturn {
  generating: Ref<boolean>
  progress: Ref<number>
  progressText: Ref<string>
  generatedCases: Ref<GeneratedCase[]>
  currentCaseIndex: Ref<number>
  isEditingResult: Ref<boolean>
  editingCase: Ref<EditingCase>
  selectedCaseIndices: Ref<Set<number>>
  issueDialogVisible: Ref<boolean>
  issueDialogValidation: Ref<{ errors: string[]; warnings: string[] }>
  allSelected: ComputedRef<boolean>
  hasSelected: ComputedRef<boolean>
  selectedCount: ComputedRef<number>
  viewingCase: ComputedRef<GeneratedCase | null>
  toggleCaseSelection: (index: number) => void
  toggleSelectAll: () => void
  handleGenerate: (
    flowSortEditorRef: {
      getFlowSortSubmitData?: () => { flow_sort_data: Record<string, unknown> }
      getFlowValidationIssues?: () => { errors: string[]; warnings: string[] }
    } | null
  ) => Promise<void>
  handleRegenerateCase: (
    index: number,
    skipConfirm?: boolean,
    preserveGenerating?: boolean
  ) => Promise<void>
  handleDeleteCase: (index: number) => Promise<void>
  handleRegenerateSelected: () => Promise<void>
  handleDeleteSelected: () => Promise<void>
  handleCancel: () => void
  handleSaveCase: () => Promise<void>
  startEditResult: () => void
  cancelEditResult: () => void
  addEditStep: () => void
  removeEditStep: (index: number) => void
  handleRetry: () => void
  resetForm: () => void
  resetGenerateState: () => void
  handleFlowSortUpdate: (data: {
    mode: string
    nodes: FlowNodeData[]
    edges: FlowEdgeData[]
  }) => void
  onIssueDialogConfirm: () => void
  onIssueDialogCancel: () => void
  getPriorityType: (priority: number) => TagType
  getTypeTagType: (type: string) => TagType
  getTypeLabel: (type: string) => string
  getPriorityTagType: (priority: unknown) => TagType
  getPriorityLabel: (priority: unknown) => string
  getDataTypeLabel: (key: string | number) => string
  cleanExpectedResult: (text: string) => string
  normalizeExpectedResult: (raw: string | undefined | null, fallback?: string) => string
}

export const TEST_POINT_CACHE_MAX = 500

export function filterValidImageUrl(url?: string): string | undefined {
  if (!url) return undefined
  const trimmed = url.trim()
  if (!trimmed || trimmed.startsWith('blob:')) return undefined
  return trimmed
}

export async function ensureTokenFresh(): Promise<void> {
  return Promise.resolve()
}

export function generateCaseNo(projectId: number | '', extraSuffix?: number): string {
  const ts = Date.now()
  const rand = Math.random().toString(36).substring(2, 8)
  const suffix = extraSuffix != null ? `-${extraSuffix}` : ''
  return `CASE${String(projectId)}-${ts}-${rand}${suffix}`
}

export function normalizePriority(priority: unknown): number {
  if (typeof priority === 'number') {
    if (priority < 1) return 1
    if (priority > 3) return 3
    return priority
  }
  const pMap: Record<string, number> = {
    P0: 1,
    P1: 1,
    P2: 2,
    P3: 3,
    high: 1,
    medium: 2,
    low: 3,
    '1': 1,
    '2': 2,
    '3': 3,
  }
  return pMap[String(priority)] || 2
}

export function extractListItems(res: unknown): unknown[] {
  if (!res || typeof res !== 'object') return []
  if (Array.isArray(res)) return res
  if (Array.isArray((res as Record<string, unknown>).items)) {
    return (res as Record<string, unknown>).items as unknown[]
  }
  const d = (res as Record<string, unknown>).data
  if (d && typeof d === 'object' && Array.isArray((d as Record<string, unknown>).items)) {
    return (d as Record<string, unknown>).items as unknown[]
  }
  return []
}
