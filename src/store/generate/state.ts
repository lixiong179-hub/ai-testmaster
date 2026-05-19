import { ref, reactive } from 'vue'
import type { Ref } from 'vue'
import type { Project } from '@/api/project'
import type { ProjectFile } from '@/api/file'
import type { TestPoint } from '@/api/testPoint'
import type { UIPrototypeProject, UIScreen } from '@/api/uiPrototype'
import type { TestCase } from '@/api/case'
import type {
  GenerateFormData,
  GeneratedCase,
  EditingCase,
  ContextPreview,
} from './types'

export interface GenerateState {
  caseIdSeq: Ref<number>
  nextCaseId: () => number
  currentStep: Ref<number>
  generating: Ref<boolean>
  saving: Ref<boolean>
  progress: Ref<number>
  progressText: Ref<string>
  errorMessage: Ref<string>
  errorSuggestions: Ref<string[]>
  projects: Ref<Project[]>
  projectsLoading: Ref<boolean>
  projectsLoaded: Ref<boolean>
  requirementFiles: Ref<ProjectFile[]>
  uiFiles: Ref<ProjectFile[]>
  testPoints: Ref<TestPoint[]>
  uiPrototypeProjects: Ref<UIPrototypeProject[]>
  selectedUiPrototypeProjectId: Ref<number | ''>
  uiScreens: Ref<UIScreen[]>
  screenImageUrls: Ref<Record<number, string>>
  isLoadingScreenImages: Ref<boolean>
  showParseWarning: Ref<boolean>
  projectCases: Ref<TestCase[]>
  selectedHistoryCaseIds: Ref<number[]>
  isLoadingProjectCases: Ref<boolean>
  _historyCaseUserCleared: Ref<boolean>
  testPointPage: Ref<number>
  testPointPageSize: Ref<number>
  testPointTotal: Ref<number>
  testPointAllIds: Ref<number[]>
  testPointSelectKey: Ref<number>
  isLoadingMore: Ref<boolean>
  testPointCache: Map<number, TestPoint>
  contextPreview: Ref<ContextPreview | null>
  lastContext: Ref<Record<string, unknown>>
  generatedCases: Ref<GeneratedCase[]>
  currentCaseIndex: Ref<number>
  isEditingResult: Ref<boolean>
  editingCase: Ref<EditingCase>
  selectedCaseIndices: Ref<Set<number>>
  issueDialogVisible: Ref<boolean>
  issueDialogValidation: Ref<{ errors: string[]; warnings: string[] }>
  issueDialogResolver: Ref<((confirmed: boolean) => void) | null>
  formData: GenerateFormData
}

export function createGenerateState(): GenerateState {
  const caseIdSeq = ref(0)
  const nextCaseId = () => ++caseIdSeq.value

  const currentStep = ref(0)
  const generating = ref(false)
  const saving = ref(false)
  const progress = ref(0)
  const progressText = ref('准备生成...')
  const errorMessage = ref('')
  const errorSuggestions = ref<string[]>([])

  const projects = ref<Project[]>([])
  const projectsLoading = ref(false)
  const projectsLoaded = ref(false)
  const requirementFiles = ref<ProjectFile[]>([])
  const uiFiles = ref<ProjectFile[]>([])
  const testPoints = ref<TestPoint[]>([])

  const uiPrototypeProjects = ref<UIPrototypeProject[]>([])
  const selectedUiPrototypeProjectId = ref<number | ''>('')
  const uiScreens = ref<UIScreen[]>([])
  const screenImageUrls = ref<Record<number, string>>({})
  const isLoadingScreenImages = ref(false)
  const showParseWarning = ref(true)

  const projectCases = ref<TestCase[]>([])
  const selectedHistoryCaseIds = ref<number[]>([])
  const isLoadingProjectCases = ref(false)
  const _historyCaseUserCleared = ref(false)

  const testPointPage = ref(1)
  const testPointPageSize = ref(10)
  const testPointTotal = ref(0)
  const testPointAllIds = ref<number[]>([])
  const testPointSelectKey = ref(0)
  const isLoadingMore = ref(false)
  const testPointCache = reactive(new Map<number, TestPoint>())

  const contextPreview = ref<ContextPreview | null>(null)
  const lastContext = ref<Record<string, unknown>>({})

  const generatedCases = ref<GeneratedCase[]>([])
  const currentCaseIndex = ref<number>(-1)
  const isEditingResult = ref(false)
  const editingCase = ref<EditingCase>({
    title: '',
    module: '',
    case_type: '功能测试',
    precondition: '',
    expected_result: '',
    priority: 2,
    steps: [],
  })

  const selectedCaseIndices = ref<Set<number>>(new Set())

  const issueDialogVisible = ref(false)
  const issueDialogValidation = ref<{ errors: string[]; warnings: string[] }>({
    errors: [],
    warnings: [],
  })
  const issueDialogResolver = ref<((confirmed: boolean) => void) | null>(null)

  const formData = reactive<GenerateFormData>({
    project_id: '',
    requirement_file_ids: [],
    ui_file_ids: [],
    ui_screen_ids: [],
    test_point_ids: [],
    test_points_data: [],
    scene: '',
    case_type: '',
    exec_mode: 'all',
    priority: 2,
    enhanced_mode: true,
    extra_requirements: '',
  })

  return {
    caseIdSeq,
    nextCaseId,
    currentStep,
    generating,
    saving,
    progress,
    progressText,
    errorMessage,
    errorSuggestions,
    projects,
    projectsLoading,
    projectsLoaded,
    requirementFiles,
    uiFiles,
    testPoints,
    uiPrototypeProjects,
    selectedUiPrototypeProjectId,
    uiScreens,
    screenImageUrls,
    isLoadingScreenImages,
    showParseWarning,
    projectCases,
    selectedHistoryCaseIds,
    isLoadingProjectCases,
    _historyCaseUserCleared,
    testPointPage,
    testPointPageSize,
    testPointTotal,
    testPointAllIds,
    testPointSelectKey,
    isLoadingMore,
    testPointCache,
    contextPreview,
    lastContext,
    generatedCases,
    currentCaseIndex,
    isEditingResult,
    editingCase,
    selectedCaseIndices,
    issueDialogVisible,
    issueDialogValidation,
    issueDialogResolver,
    formData,
  }
}
