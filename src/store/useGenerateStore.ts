import { defineStore } from 'pinia'
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { testPointApi, type TestPoint } from '@/api/testPoint'
import { fileApi, type ProjectFile } from '@/api/file'
import { type Project } from '@/api/project'
import caseApi from '@/api/case'
import type { TestCaseApiStep, TestCaseAIEnhancedRequest } from '@/api/case'
import request, { type ApiResponse } from '@/utils/request'
import { uiPrototypeApi, type UIPrototypeProject, type UIScreen } from '@/api/uiPrototype'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'
import { useFlowSortStore } from '@/store/flowSort'

/** 生成用例的步骤数据结构 */
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

/** 生成用例的数据结构 */
export interface GeneratedCase {
  id: number
  test_point_id: number | null // 允许 null，表示没有关联测试点
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

/** 编辑中的用例数据 */
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

/** 上下文预览数据 */
export interface ContextPreview {
  title: string
  type: string
  requirement?: string
  ui?: string
  uiSpecs?: number
  requirement_content?: string
  test_points?: TestPoint[]
}

/** 表单数据 */
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

function generateCaseNo(projectId: number | '', extraSuffix?: number): string {
  const ts = Date.now()
  const rand = Math.random().toString(36).substring(2, 8)
  const suffix = extraSuffix != null ? `-${extraSuffix}` : ''
  return `CASE${String(projectId)}-${ts}-${rand}${suffix}`
}

function normalizePriority(priority: unknown): number {
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

/** 文件列表等接口：分页体在根上或包在 data 内 */
function extractListItems(res: unknown): unknown[] {
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

export const useGenerateStore = defineStore('generate', () => {
  let caseIdSeq = 0
  const nextCaseId = () => ++caseIdSeq

  // ========== 核心状态 ==========
  const currentStep = ref(0)
  const generating = ref(false)
  const saving = ref(false)
  const progress = ref(0)
  const progressText = ref('准备生成...')
  const errorMessage = ref('')
  const errorSuggestions = ref<string[]>([])

  // ========== 项目和文件 ==========
  const projects = ref<Project[]>([])
  const projectsLoading = ref(false)
  const projectsLoaded = ref(false)
  const requirementFiles = ref<ProjectFile[]>([])
  const uiFiles = ref<ProjectFile[]>([])
  const testPoints = ref<TestPoint[]>([])

  // ========== UI 原型相关 ==========
  const uiPrototypeProjects = ref<UIPrototypeProject[]>([])
  const selectedUiPrototypeProjectId = ref<number | ''>('')
  const uiScreens = ref<UIScreen[]>([])
  const screenImageUrls = ref<Record<number, string>>({})
  const isLoadingScreenImages = ref(false)
  const showParseWarning = ref(true)

  // ========== 历史用例参考 ==========
  const projectCases = ref<import('@/api/case').TestCase[]>([])
  const selectedHistoryCaseIds = ref<number[]>([])
  const isLoadingProjectCases = ref(false)
  const _historyCaseUserCleared = ref(false) // 用户是否主动清空过历史用例选择

  // ========== 测试点分页 ==========
  const testPointPage = ref(1)
  const testPointPageSize = ref(10)
  const testPointTotal = ref(0)
  const testPointAllIds = ref<number[]>([])
  const testPointSelectKey = ref(0)
  const isLoadingMore = ref(false)
  const TEST_POINT_CACHE_MAX = 500
  const testPointCache = reactive(new Map<number, TestPoint>())

  // ========== 上下文预览 ==========
  const contextPreview = ref<ContextPreview | null>(null)
  const lastContext = ref<Record<string, unknown>>({})

  // ========== 生成结果 ==========
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
  const allSelected = computed(
    () =>
      generatedCases.value.length > 0 &&
      generatedCases.value.every((_, i) => selectedCaseIndices.value.has(i))
  )
  const hasSelected = computed(() => selectedCaseIndices.value.size > 0)
  const selectedCount = computed(() => selectedCaseIndices.value.size)

  const toggleCaseSelection = (index: number) => {
    const s = new Set(selectedCaseIndices.value)
    if (s.has(index)) {
      s.delete(index)
    } else {
      s.add(index)
    }
    selectedCaseIndices.value = s
  }

  const toggleSelectAll = () => {
    if (allSelected.value) {
      selectedCaseIndices.value = new Set()
    } else {
      selectedCaseIndices.value = new Set(generatedCases.value.map((_, i) => i))
    }
  }

  const issueDialogVisible = ref(false)
  const issueDialogValidation = ref<{ errors: string[]; warnings: string[] }>({
    errors: [],
    warnings: [],
  })
  let issueDialogResolver: ((confirmed: boolean) => void) | null = null

  // ========== 表单数据 ==========
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

  // ========== 计算属性 ==========
  const selectedUiPrototypeProject = computed(() => {
    if (!selectedUiPrototypeProjectId.value) return null
    return (
      uiPrototypeProjects.value.find((p) => p.id === selectedUiPrototypeProjectId.value) || null
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
      return `部分解析 ${project.parsed_count || 0}/${project.screen_count || uiScreens.value.length}`
    }
    if (project.parse_status === 'failed') return '解析失败'
    return '待解析'
  })

  const viewingCase = computed(() => {
    if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
      return generatedCases.value[currentCaseIndex.value]
    }
    return generatedCases.value[0] || null
  })

  const selectedTestPointsForDisplay = computed(() => {
    const ids = formData.test_point_ids.slice(0, 5)
    return ids.map((id) => {
      const tp =
        testPoints.value.find((p) => p.id === id) ||
        formData.test_points_data.find((p) => p.id === id)
      return tp || { id, module: '?', function: '?', point: '未知测试点', priority: 2 }
    })
  })

  const canGenerate = computed(() => {
    return (
      formData.test_point_ids.length > 0 ||
      formData.requirement_file_ids.length > 0 ||
      formData.ui_file_ids.length > 0 ||
      formData.ui_screen_ids.length > 0 ||
      selectedHistoryCaseIds.value.length > 0
    )
  })

  const generateButtonLabel = computed(() => {
    const count = formData.test_point_ids.length
    if (count > 0) return `${count} 个测试用例`
    if (formData.requirement_file_ids.length > 0) {
      return `${formData.requirement_file_ids.length} 份需求`
    }
    if (formData.ui_screen_ids.length > 0) {
      return `${formData.ui_screen_ids.length} 个屏幕`
    }
    if (selectedHistoryCaseIds.value.length > 0) {
      return `${selectedHistoryCaseIds.value.length} 条历史用例`
    }
    if (formData.case_type === 'api_automation') return '接口用例'
    return '开始'
  })

  const progressStatus = computed(() => {
    if (progress.value === 100) return 'success'
    if (errorMessage.value) return 'exception'
    return ''
  })

  watch(currentCaseIndex, () => {
    isEditingResult.value = false
  })

  // ========== 项目和文件操作 ==========
  const getProjects = async (forceReload: boolean = false) => {
    if (projectsLoaded.value && !forceReload && projects.value.length > 0) {
      return
    }
    projectsLoading.value = true
    try {
      const response: ApiResponse<{ items: Project[]; total: number }> = await request.get(
        '/api/v1/project/list',
        { params: { page: 1, page_size: 1000 } }
      )
      if (response?.data?.items) {
        projects.value = response.data.items.filter((p: Project) => p.name !== '默认项目')
        projectsLoaded.value = true
      }
    } catch (error) {
      console.error('获取项目列表失败:', error)
    } finally {
      projectsLoading.value = false
    }
  }

  const loadProjectFiles = async () => {
    try {
      const response = await fileApi.getFileList(formData.project_id as number)
      const items = extractListItems(response) as ProjectFile[]
      requirementFiles.value = items.filter((f) => f.resource_type === 'requirement')
      uiFiles.value = items.filter((f) => f.resource_type === 'ui_mockup')
    } catch (error) {
      console.error('获取文件列表失败:', error)
    }
  }

  // ========== 测试点操作 ==========
  const loadTestPoints = async (
    page: number = 1,
    append: boolean = false,
    refreshKey: boolean = true
  ) => {
    if (!formData.project_id) return
    try {
      const apiData = await testPointApi.getList(formData.project_id as number, {
        page,
        page_size: testPointPageSize.value,
      })
      if (apiData) {
        const newItems = apiData.items || []
        if (append && page > 1) {
          testPoints.value = [...testPoints.value, ...newItems]
        } else {
          testPoints.value = newItems
        }
        newItems.forEach((item: TestPoint) => {
          testPointCache.set(item.id, item)
          if (!testPointAllIds.value.includes(item.id)) {
            testPointAllIds.value.push(item.id)
          }
        })
        if (testPointCache.size > TEST_POINT_CACHE_MAX) {
          const overflow = testPointCache.size - TEST_POINT_CACHE_MAX
          let count = 0
          for (const key of testPointCache.keys()) {
            if (count >= overflow) break
            testPointCache.delete(key)
            count++
          }
        }
        testPointTotal.value = apiData.total || 0
        testPointPage.value = page
        if (refreshKey) {
          testPointSelectKey.value++
        }
        if (
          testPointAllIds.value.length < testPointTotal.value &&
          page === 1 &&
          testPointTotal.value <= 200
        ) {
          const allApiData = await testPointApi.getList(formData.project_id as number, {
            page: 1,
            page_size: Math.min(testPointTotal.value, 200),
          })
          if (allApiData?.items) {
            testPointAllIds.value = allApiData.items.map((item: TestPoint) => item.id)
          }
        }
      }
    } catch (error) {
      console.error('获取测试点列表失败:', error)
    }
  }

  const handleSourceFileChange = () => {
    if (!formData.project_id) return
    testPointPage.value = 1
    testPointTotal.value = 0
    testPointAllIds.value = []
    formData.test_point_ids = []
    testPoints.value = []
    testPointCache.clear()
    testPointSelectKey.value++
  }

  const selectAllTestPoints = () => {
    if (testPointAllIds.value.length > 0) {
      formData.test_point_ids = [...testPointAllIds.value]
    }
  }

  const deselectAllTestPoints = () => {
    formData.test_point_ids = []
  }

  const addTestPoint = (id: number) => {
    if (!formData.test_point_ids.includes(id)) {
      formData.test_point_ids.push(id)
    }
  }

  const removeTestPoint = (id: number) => {
    const index = formData.test_point_ids.indexOf(id)
    if (index !== -1) {
      formData.test_point_ids.splice(index, 1)
    }
  }

  const getTestPointLabel = (id: number): string => {
    let point = testPointCache.get(id)
    if (!point) {
      point = testPoints.value.find((p) => p.id === id)
    }
    if (point) {
      return `${point.module} - ${point.point}`
    }
    return `测试点 #${id}`
  }

  const selectCurrentPageAll = () => {
    const visibleIds = testPoints.value.map((p) => p.id)
    const currentSet = new Set(formData.test_point_ids)
    visibleIds.forEach((id) => {
      if (!currentSet.has(id)) {
        formData.test_point_ids.push(id)
      }
    })
  }

  const goToTestPointPage = async (page: number) => {
    if (isLoadingMore.value) return
    isLoadingMore.value = true
    try {
      await loadTestPoints(page, false, false)
    } finally {
      isLoadingMore.value = false
    }
  }

  // ========== 历史用例加载 ==========
  const loadProjectCases = async () => {
    if (!formData.project_id) {
      projectCases.value = []
      return
    }
    isLoadingProjectCases.value = true
    try {
      const response = await caseApi.getCaseList({
        project_id: formData.project_id as number,
        lifecycle_status: 'active',
        page_size: 500,
      })
      projectCases.value = response?.data?.items || []
    } catch (e) {
      console.warn('加载项目用例失败:', e)
      projectCases.value = []
    } finally {
      isLoadingProjectCases.value = false
    }
  }

  // ========== UI 原型操作 ==========
  const loadUIPrototypeProjects = async () => {
    if (!formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIPrototypeProjectList(formData.project_id as number)
      if (response) {
        uiPrototypeProjects.value = Array.isArray(response)
          ? response
          : (response as Record<string, unknown>)?.data
            ? (response as Record<string, { items: UIPrototypeProject[] }>).data.items || []
            : []
      }
    } catch (error) {
      console.error('获取 UI 原型项目列表失败:', error)
    }
  }

  const loadUIScreens = async (uiPrototypeProjectId: number) => {
    if (!formData.project_id) return
    try {
      const response = await uiPrototypeApi.getUIScreenList(
        formData.project_id as number,
        uiPrototypeProjectId
      )
      if (response?.data?.items) {
        uiScreens.value = response.data.items.sort(
          (a: UIScreen, b: UIScreen) => (a.screen_order || 0) - (b.screen_order || 0)
        )
        cleanupScreenImages()
        await loadScreenImages()
      }
    } catch (error) {
      console.error('获取 UI 屏幕列表失败:', error)
    }
  }

  const loadScreenImages = async () => {
    if (isLoadingScreenImages.value) return
    isLoadingScreenImages.value = true
    try {
      const screensToLoad = uiScreens.value.filter(
        (screen) => screen.id && !screenImageUrls.value[screen.id]
      )
      const BATCH_SIZE = 5
      for (let i = 0; i < screensToLoad.length; i += BATCH_SIZE) {
        const batch = screensToLoad.slice(i, i + BATCH_SIZE)
        await Promise.allSettled(
          batch.map(async (screen) => {
            try {
              const response = await request.get(`/api/v1/file/preview-screen/${screen.id}`, {
                responseType: 'blob',
              })
              const blob =
                response.data instanceof Blob
                  ? response.data
                  : new Blob([response.data], { type: 'image/jpeg' })
              if (blob.size > 0) {
                const oldUrl = screenImageUrls.value[screen.id]
                if (oldUrl?.startsWith('blob:')) {
                  URL.revokeObjectURL(oldUrl)
                }
                screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
              }
            } catch (e) {
              console.warn(`加载屏幕图片失败: ${screen.id}`, e)
            }
          })
        )
      }
    } finally {
      isLoadingScreenImages.value = false
    }
  }

  const handleUIPrototypeProjectChange = async (projectId: number | string) => {
    showParseWarning.value = true
    lastContext.value = {}
    selectedUiPrototypeProjectId.value = projectId as number | ''
    const flowSortStore = useFlowSortStore()
    if (projectId) {
      if (formData.project_id) {
        flowSortStore.setProjectId(formData.project_id as number)
      }
      await loadUIScreens(projectId as number)
      if (formData.project_id) {
        await flowSortStore.loadFromBackend()
      }
      if (uiScreens.value.length > 0) {
        formData.ui_screen_ids = uiScreens.value.map((s) => s.id)
      } else {
        formData.ui_screen_ids = []
      }
    } else {
      uiScreens.value = []
      formData.ui_screen_ids = []
      flowSortStore.reset()
    }
  }

  // ========== 项目变更 ==========
  const handleProjectChange = () => {
    formData.requirement_file_ids = []
    formData.ui_file_ids = []
    formData.ui_screen_ids = []
    formData.test_point_ids = []
    contextPreview.value = null
    lastContext.value = {}
    generatedCases.value = []
    currentCaseIndex.value = -1
    selectedUiPrototypeProjectId.value = ''
    uiPrototypeProjects.value = []
    uiScreens.value = []
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
    if (formData.project_id) {
      flowSortStore.setProjectId(formData.project_id as number)
    }
    selectedHistoryCaseIds.value = []
    _historyCaseUserCleared.value = false
    projectCases.value = []
    handleSourceFileChange()
    loadProjectFiles()
    loadUIPrototypeProjects()
    loadProjectCases()
  }

  const handleProjectFocus = () => {
    if (!projectsLoaded.value || projects.value.length === 0) {
      getProjects()
    }
  }

  // ========== 文件内容提取 ==========
  const extractFileContent = async () => {
    if (formData.requirement_file_ids.length === 0 && formData.ui_file_ids.length === 0) {
      ElMessage.warning('请先选择文件')
      return
    }
    const allFileIds = [...formData.requirement_file_ids, ...formData.ui_file_ids]
    try {
      const response: ApiResponse = await request.post('/api/v1/file/extract-content', {
        file_ids: allFileIds,
        project_id: Number(formData.project_id),
        force_refresh: true,
      })
      if (response?.code === 200) {
        await loadProjectFiles()
        const data = response.data as { success?: number; failed?: number }
        contextPreview.value = {
          title: `内容提取完成：成功 ${data?.success || 0} 个，失败 ${data?.failed || 0} 个`,
          type: (data?.failed || 0) > 0 ? 'warning' : 'success',
          requirement: `选择了 ${allFileIds.length} 个文件`,
          ui:
            formData.ui_screen_ids.length > 0
              ? `${formData.ui_screen_ids.length} 个屏幕`
              : formData.ui_file_ids.length > 0
                ? `${formData.ui_file_ids.length} 个文件`
                : '',
          uiSpecs: (lastContext.value as Record<string, unknown[]>)?.ui_specs?.length || 0,
        }
        ElMessage.success('文件内容提取完成')
      } else {
        ElMessage.error(response?.msg || response?.message || '提取内容失败')
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err.response?.data?.detail || '提取内容失败')
    }
  }

  // ========== 步骤导航 ==========
  const nextStep = () => {
    if (currentStep.value < 2) {
      currentStep.value++
    }
  }

  const prevStep = () => {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  const skipToStep2 = () => {
    currentStep.value = 1
  }

  const handleCaseTypeChange = (val: string) => {
    if (val !== 'ui_automation') {
      formData.exec_mode = 'all'
    }
  }

  // ========== 生成逻辑 ==========
  const generateErrorSuggestions = () => {
    const error = errorMessage.value.toLowerCase()
    if (
      error.includes('认证') ||
      error.includes('authentication') ||
      (error.includes('api') && error.includes('key')) ||
      error.includes('503') ||
      error.includes('无效')
    ) {
      errorSuggestions.value = [
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
      errorSuggestions.value = [
        'AI服务请求频率过高，请稍后重试',
        '建议降低请求频率或等待一段时间后再试',
        '可以尝试分批生成测试用例',
      ]
      return
    }
    errorSuggestions.value = [
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
    issueDialogValidation.value = validation
    issueDialogVisible.value = true
    return new Promise((resolve) => {
      issueDialogResolver = resolve
    })
  }

  const onIssueDialogConfirm = () => {
    issueDialogVisible.value = false
    issueDialogResolver?.(true)
    issueDialogResolver = null
  }

  const onIssueDialogCancel = () => {
    issueDialogVisible.value = false
    issueDialogResolver?.(false)
    issueDialogResolver = null
  }

  const handleGenerate = async (
    flowSortEditorRef: {
      getFlowSortSubmitData?: () => { mode: 'graph'; flow_sort_data: Record<string, unknown> }
      getFlowValidationIssues?: () => { errors: string[]; warnings: string[] }
    } | null
  ) => {
    if (!canGenerate.value) {
      ElMessage.warning('请先选择测试点、需求文档、UI原型图或历史用例')
      return
    }

    // 流程图校验
    if (selectedUiPrototypeProjectId.value && uiScreens.value.length > 0) {
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

    const targetPoints =
      formData.test_point_ids.length > 0
        ? formData.test_point_ids
        : (contextPreview.value?.test_points || []).map((tp) => tp.id)

    // 数量确认：如果是测试点生成，超过20个需要确认；如果是无测试点生成，也需要确认
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

    generatedCases.value = []
    currentCaseIndex.value = -1
    errorMessage.value = ''
    errorSuggestions.value = []
    generating.value = true
    progress.value = 0
    progressText.value =
      targetPoints.length > 0
        ? `准备生成 ${targetPoints.length} 条测试用例...`
        : '准备生成测试用例...'
    currentStep.value = 2

    // 声明进度条计时器变量，确保在两个分支都能访问到
    let progressInterval: ReturnType<typeof setInterval> | null = null

    try {
      let context: Record<string, unknown> = {
        requirement_content: '',
        ui_description: '',
        test_points: [],
        project_config: null,
      }

      progress.value = 5
      progressText.value = '正在准备生成上下文...'

      if (formData.project_id) {
        const contextResponse: ApiResponse<{
          requirement_content?: string
          ui_descriptions?: unknown[]
          ui_specs?: unknown[]
          test_points?: TestPoint[]
          project_config?: unknown
          history_cases?: unknown[]
        }> = await request.post('/api/v1/testCase/generate-context', {
          project_id: Number(formData.project_id),
          requirement_file_ids:
            formData.requirement_file_ids.length > 0 ? formData.requirement_file_ids : undefined,
          ui_file_ids: formData.ui_file_ids.length > 0 ? formData.ui_file_ids : undefined,
          ui_screen_ids: formData.ui_screen_ids.length > 0 ? formData.ui_screen_ids : undefined,
          test_point_ids: targetPoints.length > 0 ? targetPoints : undefined,
          history_case_ids:
            selectedHistoryCaseIds.value.length > 0
              ? selectedHistoryCaseIds.value
              : selectedHistoryCaseIds.value.length === 0 && _historyCaseUserCleared.value
                ? []
                : undefined,
        })

        if (contextResponse?.data) {
          const data = contextResponse.data
          context = {
            requirement_content: data.requirement_content || '',
            ui_description: JSON.stringify(data.ui_descriptions || []),
            ui_specs: data.ui_specs || [],
            test_points: data.test_points || [],
            project_config: data.project_config || null,
            history_cases: data.history_cases || [],
          }
          lastContext.value = { ...context }

          progress.value = 15
          progressText.value = '上下文准备完成，开始构建生成数据...'
        }
      }

      const allTestPoints = (context.test_points || []) as TestPoint[]

      // 如果有测试点，按测试点逐个生成
      if (targetPoints.length > 0) {
        const total = targetPoints.length
        let completed = 0

        progressInterval = setInterval(() => {
          const targetPct = Math.min(70, 25 + Math.round((completed / total) * 45))
          if (progress.value < targetPct) {
            progress.value = targetPct
            progressText.value = `AI生成中... ${completed}/${total}`
          }
        }, 500)

        for (let i = 0; i < targetPoints.length; i++) {
          if (!generating.value) break

          const tpId = targetPoints[i]
          const tpInfo = allTestPoints.find((tp) => tp.id === tpId)
          const tpLabel = tpInfo ? `${tpInfo.module} - ${tpInfo.point}` : `测试点#${tpId}`

          try {
            const flowSortSubmitData = flowSortEditorRef?.getFlowSortSubmitData?.()
            const apiData: Record<string, unknown> = {
              project_id: Number(formData.project_id),
              description: formData.scene || `为"${tpLabel}"生成详细测试用例`,
              case_type: formData.case_type,
              exec_mode: formData.exec_mode,
              priority: formData.priority,
              enhanced_mode: formData.enhanced_mode,
              extra_requirements: formData.extra_requirements,
              context: {
                ...context,
                current_test_point: tpInfo || { id: tpId },
                test_point_ids: [tpId],
              },
            }
            const flowSortStore = useFlowSortStore()
            apiData.mode = flowSortStore.nodes.length > 0 ? 'graph' : 'linear'
            apiData.flow_sort_data = flowSortSubmitData?.flow_sort_data || {
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
                  : uiScreens.value.map((screen, index) => ({
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
              module_info: flowSortModuleInfo.value,
            }

            progress.value = 50
            progressText.value = 'AI正在生成测试用例...'

            const casesArray = await caseApi.aiGenerateCaseEnhanced(
              apiData as unknown as TestCaseAIEnhancedRequest
            )
            const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]

            for (let cIdx = 0; cIdx < casesData.length; cIdx++) {
              const caseData = casesData[cIdx]
              generatedCases.value.push({
                id: nextCaseId(),
                test_point_id: tpId,
                test_point_label: `${tpLabel} - ${caseData.case_category || '正向'}`,
                title: caseData.title || caseData.name || `${tpLabel} 测试用例`,
                module: caseData.module || tpInfo?.module || '',
                case_type: caseData.case_type || caseData.type || formData.case_type,
                test_category: caseData.test_category || caseData.case_category || '',
                precondition: caseData.precondition || '',
                test_data: caseData.test_data,
                steps: (caseData.steps || []) as GeneratedStep[],
                expected_result: caseData.expected_result || '',
                priority: caseData.priority || formData.priority,
                scene: formData.scene,
                ai_change_type: caseData.change_type || 'added',
                parent_case_id: caseData.parent_case_id ?? null,
              })

              progressText.value = `正在保存 ${caseData.title || '用例'}...`
              const saved = await saveSingleCaseToDb(
                generatedCases.value[generatedCases.value.length - 1]
              )
              if (!saved) {
                const failedCase = generatedCases.value[generatedCases.value.length - 1]
                failedCase._error = '保存失败'
              }
            }
          } catch (err: unknown) {
            const error = err as {
              response?: { data?: { detail?: string } }
              message?: string
            }
            generatedCases.value.push({
              id: nextCaseId(),
              test_point_id: tpId,
              test_point_label: tpLabel,
              title: `${tpLabel} 测试用例（生成失败）`,
              module: tpInfo?.module || '',
              case_type: formData.case_type,
              precondition: '',
              test_data: {},
              steps: [],
              expected_result: '',
              priority: formData.priority,
              _error: error.response?.data?.detail || error.message || '生成失败',
              scene: formData.scene,
              ai_change_type: 'added',
              parent_case_id: null,
            })
          }

          completed++
          progress.value = Math.round((completed / total) * 90)
          progressText.value = `生成中... ${completed}/${total}`
        }

        if (progressInterval) clearInterval(progressInterval)
      } else {
        // 没有测试点，按流程节点或UI页面逐个生成
        const flowSortStore = useFlowSortStore()
        const flowNodes =
          flowSortStore.nodes.length > 0
            ? [...flowSortStore.nodes].sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
            : uiScreens.value.map((screen, index) => ({
                screen_id: screen.id,
                screen_order: index + 1,
                flow_type: 'main' as const,
                screen_name: screen.screen_name,
                ui_spec_elements: screen.ui_spec?.elements || [],
                summary: screen.summary || '',
              }))

        if (flowNodes.length > 1) {
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

          progressInterval = setInterval(() => {
            const targetPct = Math.min(70, 25 + Math.round((completed / total) * 45))
            if (progress.value < targetPct) {
              progress.value = targetPct
              progressText.value = `AI生成中... ${completed}/${total}`
            }
          }, 500)

          for (let i = 0; i < flowNodes.length; i++) {
            if (!generating.value) break

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
                module_info: flowSortModuleInfo.value,
              }

              const apiData: Record<string, unknown> = {
                project_id: Number(formData.project_id),
                description: formData.scene || `为页面"${nodeLabel}"生成详细测试用例`,
                case_type: formData.case_type,
                exec_mode: formData.exec_mode,
                priority: formData.priority,
                enhanced_mode: formData.enhanced_mode,
                extra_requirements: formData.extra_requirements,
                mode: 'graph' as const,
                flow_sort_data: nodeFlowData,
                context: {
                  ...context,
                  current_test_point: {
                    module: nodeLabel,
                    point: `${nodeLabel}页面测试`,
                    priority: formData.priority,
                  },
                },
              }

              progress.value = 50
              progressText.value = `AI正在为"${nodeLabel}"生成测试用例...`

              const casesArray = await caseApi.aiGenerateCaseEnhanced(
                apiData as unknown as TestCaseAIEnhancedRequest
              )
              const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]

              for (let cIdx = 0; cIdx < casesData.length; cIdx++) {
                const caseData = casesData[cIdx]
                generatedCases.value.push({
                  id: nextCaseId(),
                  test_point_id: null,
                  test_point_label: `${nodeLabel} - ${caseData.case_category || '正向'}`,
                  title: caseData.title || caseData.name || `${nodeLabel} 测试用例`,
                  module: caseData.module || nodeLabel,
                  case_type: caseData.case_type || caseData.type || formData.case_type,
                  test_category: caseData.test_category || caseData.case_category || '',
                  precondition: caseData.precondition || '',
                  test_data: caseData.test_data,
                  steps: (caseData.steps || []) as GeneratedStep[],
                  expected_result: caseData.expected_result || '',
                  priority: caseData.priority || formData.priority,
                  scene: formData.scene,
                  ai_change_type: caseData.change_type || 'added',
                  parent_case_id: caseData.parent_case_id ?? null,
                })

                progressText.value = `正在保存 ${caseData.title || '用例'}...`
                const saved = await saveSingleCaseToDb(
                  generatedCases.value[generatedCases.value.length - 1]
                )
                if (!saved) {
                  const failedCase = generatedCases.value[generatedCases.value.length - 1]
                  failedCase._error = '保存失败'
                }
              }
            } catch (err: unknown) {
              const error = err as {
                response?: { data?: { detail?: string } }
                message?: string
              }
              generatedCases.value.push({
                id: nextCaseId(),
                test_point_id: null,
                test_point_label: nodeLabel,
                title: `${nodeLabel} 测试用例（生成失败）`,
                module: nodeLabel,
                case_type: formData.case_type,
                precondition: '',
                test_data: {},
                steps: [],
                expected_result: '',
                priority: formData.priority,
                _error: error.response?.data?.detail || error.message || '生成失败',
                scene: formData.scene,
                ai_change_type: 'added',
                parent_case_id: null,
              })
            }

            completed++
            progress.value = Math.round((completed / total) * 90)
            progressText.value = `生成中... ${completed}/${total}`
          }

          if (progressInterval) clearInterval(progressInterval)
        } else {
          // 只有1个或没有流程节点，一次性生成
          let completed = 0
          const totalSteps = 3

          progressInterval = setInterval(() => {
            const targetPct = Math.min(70, 25 + Math.round((completed / totalSteps) * 45))
            if (progress.value < targetPct) {
              progress.value = targetPct
              progressText.value = `AI生成中... ${completed}/${totalSteps}`
            }
          }, 500)

          progress.value = 25
          progressText.value = 'AI正在生成测试用例...'
          completed = 1

          const flowSortSubmitData = flowSortEditorRef?.getFlowSortSubmitData?.()
          const apiData: Record<string, unknown> = {
            project_id: Number(formData.project_id),
            description: formData.scene || '基于需求文档和UI原型生成测试用例',
            case_type: formData.case_type,
            exec_mode: formData.exec_mode,
            priority: formData.priority,
            enhanced_mode: formData.enhanced_mode,
            extra_requirements: formData.extra_requirements,
            context: context,
          }
          apiData.mode = flowSortStore.nodes.length > 0 ? 'graph' : 'linear'
          apiData.flow_sort_data = flowSortSubmitData?.flow_sort_data || {
            nodes: flowNodes,
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
            module_info: flowSortModuleInfo.value,
          }

          progress.value = 50
          progressText.value = 'AI正在生成测试用例...'
          completed = 2

          const casesArray = await caseApi.aiGenerateCaseEnhanced(
            apiData as unknown as TestCaseAIEnhancedRequest
          )
          const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]

          for (let cIdx = 0; cIdx < casesData.length; cIdx++) {
            const caseData = casesData[cIdx]
            generatedCases.value.push({
              id: nextCaseId(),
              test_point_id: null,
              test_point_label: caseData.case_category || 'AI生成',
              title: caseData.title || caseData.name || 'AI生成测试用例',
              module: caseData.module || '',
              case_type: caseData.case_type || caseData.type || formData.case_type,
              test_category: caseData.test_category || caseData.case_category || '',
              precondition: caseData.precondition || '',
              test_data: caseData.test_data,
              steps: (caseData.steps || []) as GeneratedStep[],
              expected_result: caseData.expected_result || '',
              priority: caseData.priority || formData.priority,
              scene: formData.scene,
              ai_change_type: caseData.change_type || 'added',
              parent_case_id: caseData.parent_case_id ?? null,
            })

            progressText.value = `正在保存 ${caseData.title || '用例'}...`
            const saved = await saveSingleCaseToDb(
              generatedCases.value[generatedCases.value.length - 1]
            )
            if (!saved) {
              const failedCase = generatedCases.value[generatedCases.value.length - 1]
              failedCase._error = '保存失败'
            }
          }

          progress.value = 90
          progressText.value = '生成中... 3/3'
          completed = 3

          if (progressInterval) clearInterval(progressInterval)
        }
      }

      if (!generating.value) {
        progressText.value = `已取消，已生成 ${generatedCases.value.length} 条`
      } else {
        currentCaseIndex.value = 0
        progress.value = 100
        progressText.value = `生成完成！共 ${generatedCases.value.length} 条`
        const failCount = generatedCases.value.filter((c) => c._error).length
        if (failCount === 0) {
          ElMessage.success(`成功生成 ${generatedCases.value.length} 条测试用例`)
        } else {
          ElMessage.warning(
            `生成完成：${generatedCases.value.length - failCount} 成功，${failCount} 失败`
          )
        }
      }
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string; message?: string } }
        message?: string
      }
      progress.value = 100
      progressText.value = '生成失败'
      errorMessage.value =
        err.response?.data?.detail ||
        err.response?.data?.message ||
        err.message ||
        'AI生成测试用例失败'
      generateErrorSuggestions()
      ElMessage.error(errorMessage.value)
    } finally {
      generating.value = false
    }
  }

  const handleRegenerateCase = async (
    index: number,
    skipConfirm: boolean = false,
    preserveGenerating: boolean = false
  ) => {
    const c = generatedCases.value[index]
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

    generating.value = true
    progress.value = 10
    progressText.value = '正在调用AI重新生成...'

    try {
      const flowSortStore = useFlowSortStore()
      const apiData: Record<string, unknown> = {
        project_id: Number(formData.project_id),
        description: formData.scene || `重新生成用例"${c.title}"`,
        case_type: formData.case_type || c.case_type,
        exec_mode: formData.exec_mode || 'all',
        priority: formData.priority || c.priority || 2,
        enhanced_mode: formData.enhanced_mode !== undefined ? formData.enhanced_mode : true,
        extra_requirements: formData.extra_requirements || '',
        mode: flowSortStore.nodes.length > 0 ? ('graph' as const) : ('linear' as const),
        flow_sort_data:
          flowSortStore.nodes.length > 0
            ? {
                nodes: [...flowSortStore.nodes]
                  .sort((a, b) => (a.main_order ?? 999) - (b.main_order ?? 999))
                  .map((n, idx) => ({
                    screen_id: n.screen_id,
                    screen_order: idx + 1,
                    flow_type: n.flow_type,
                    main_order: n.main_order,
                    screen_name: n.screen_name,
                    ui_spec_elements: n.ui_spec_elements || [],
                    summary: n.summary || '',
                    flow_meta: n.flow_meta || undefined,
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
                module_info: flowSortModuleInfo.value,
              }
            : undefined,
        context: {
          base_case: {
            title: c.title,
            module: c.module,
            precondition: c.precondition,
            steps: c.steps || [],
            expected_result: c.expected_result,
          },
          requirement_content: contextPreview.value?.requirement_content || '',
          ui_description: (lastContext.value as Record<string, string>).ui_description || '',
          ui_specs: (lastContext.value as Record<string, unknown[]>).ui_specs || [],
          test_points: contextPreview.value?.test_points || [],
          history_cases: (lastContext.value as Record<string, unknown[]>).history_cases || [],
        },
      }

      const casesArray = await caseApi.aiGenerateCaseEnhanced(
        apiData as unknown as TestCaseAIEnhancedRequest
      )
      const casesData = Array.isArray(casesArray) ? casesArray : [casesArray]
      const caseData = casesData[0]
      if (!caseData) {
        throw new Error('AI 未返回有效用例数据')
      }

      const oldDbId = c._dbId

      generatedCases.value[index] = {
        ...generatedCases.value[index],
        title: caseData.title || caseData.name || '',
        module: caseData.module || '',
        case_type: caseData.case_type || caseData.type || '',
        precondition: caseData.precondition || '',
        test_data: caseData.test_data,
        steps: (caseData.steps || []) as GeneratedStep[],
        expected_result: caseData.expected_result || '',
        priority: caseData.priority || formData.priority,
        ai_change_type: caseData.change_type || 'added',
        parent_case_id: caseData.parent_case_id ?? null,
        _error: undefined,
        _saved: false,
        _dbId: undefined,
      }

      progressText.value = '正在保存...'
      const saved = await saveSingleCaseToDb(generatedCases.value[index])
      if (!saved) {
        generatedCases.value[index]._error = '保存失败'
      }

      if (oldDbId && saved) {
        try {
          await caseApi.deleteCase(oldDbId)
        } catch {
          console.warn(`[handleRegenerateCase] 删除旧用例 #${oldDbId} 失败，可能产生冗余数据`)
        }
      }

      progress.value = 100
      progressText.value = '重新生成完成！'
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
        generating.value = false
      }
    }
  }

  const handleDeleteCase = async (index: number) => {
    const c = generatedCases.value[index]
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
        await caseApi.deleteCase(c._dbId)
      } catch (e) {
        console.error(`[handleDeleteCase] 删除数据库用例 #${c._dbId} 失败:`, e)
        ElMessage.error('数据库删除失败，请稍后重试')
        return
      }
    }

    generatedCases.value.splice(index, 1)
    selectedCaseIndices.value = new Set(
      [...selectedCaseIndices.value].filter((i) => i !== index).map((i) => (i > index ? i - 1 : i))
    )

    if (generatedCases.value.length === 0) {
      currentCaseIndex.value = -1
    } else if (currentCaseIndex.value >= generatedCases.value.length) {
      currentCaseIndex.value = generatedCases.value.length - 1
    }

    ElMessage.success('用例已删除')
  }

  const handleRegenerateSelected = async () => {
    const indices = [...selectedCaseIndices.value].sort((a, b) => a - b)
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

    generating.value = true
    try {
      for (const idx of indices) {
        await handleRegenerateCase(idx, true, true)
        if (!generating.value) break
      }
    } finally {
      generating.value = false
    }
  }

  const handleDeleteSelected = async () => {
    const indices = [...selectedCaseIndices.value].sort((a, b) => b - a)
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
      .map((i) => generatedCases.value[i]?._dbId)
      .filter((id): id is number => id !== undefined)

    if (dbIds.length > 0) {
      try {
        await caseApi.batchDeleteCases(dbIds)
      } catch (e) {
        console.error('[handleDeleteSelected] 批量删除数据库用例失败:', e)
        ElMessage.error('数据库批量删除失败，请稍后重试')
        return
      }
    }

    for (const idx of indices) {
      generatedCases.value.splice(idx, 1)
    }

    selectedCaseIndices.value = new Set()

    if (generatedCases.value.length === 0) {
      currentCaseIndex.value = -1
    } else if (currentCaseIndex.value >= generatedCases.value.length) {
      currentCaseIndex.value = generatedCases.value.length - 1
    }

    ElMessage.success(`已删除 ${indices.length} 条用例`)
  }

  const handleCancel = () => {
    if (!generating.value) return
    ElMessageBox.confirm('确定要取消生成吗？', '取消确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }).then(() => {
      generating.value = false
      progressText.value = '已取消'
      errorMessage.value = ''
      ElMessage.info('生成已取消')
    })
  }

  // ========== 保存逻辑 ==========
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
  }): {
    project_id: number
    case_no: string
    title: string
    module: string
    case_type: string
    precondition: string
    steps: TestCaseApiStep[]
    expected_result: string
    priority: number
    test_category: string
    test_data: Record<string, Record<string, string | number | boolean | null>>
    generate_status: number
    parent_case_id?: number | null
    ai_change_type?: 'added' | 'modified' | 'deprecated'
  } => {
    const stepsPayload = buildStepsPayload(c.steps)
    const priority = normalizePriority(c.priority ?? 2)
    return {
      project_id: Number(formData.project_id),
      case_no: generateCaseNo(formData.project_id, c.id),
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
  const handleSaveCase = async () => {
    const caseToSave = isEditingResult.value ? editingCase.value : viewingCase.value
    if (!caseToSave) {
      ElMessage.warning('没有可保存的用例')
      return
    }
    if ('_error' in caseToSave && caseToSave._error) {
      ElMessage.warning('该用例生成失败，无法保存，请重新生成')
      return
    }
    if (!formData.project_id) {
      ElMessage.warning('请先选择项目')
      return
    }

    saving.value = true
    try {
      const currentCase = viewingCase.value
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
        if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
          generatedCases.value[currentCaseIndex.value]._saved = true
          generatedCases.value[currentCaseIndex.value]._dbId = created.id
        }
      }

      const wasEditing = isEditingResult.value

      isEditingResult.value = false
      if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
        const target = generatedCases.value[currentCaseIndex.value]
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
      saving.value = false
    }
  }

  const saveSingleCaseToDb = async (c: {
    id: number
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
  }): Promise<boolean> => {
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

  // ========== 编辑操作 ==========
  const startEditResult = () => {
    const current = viewingCase.value
    if (!current) return
    editingCase.value = {
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
    isEditingResult.value = true
  }

  const cancelEditResult = () => {
    isEditingResult.value = false
  }

  const addEditStep = () => {
    editingCase.value.steps.push({
      step: editingCase.value.steps.length + 1,
      action: '',
      param: '',
      expected_result: '',
      test_data: {},
    })
  }

  const removeEditStep = (index: number) => {
    if (editingCase.value.steps.length > 1) {
      editingCase.value.steps.splice(index, 1)
      editingCase.value.steps.forEach((s, i) => {
        s.step = i + 1
      })
    }
  }

  const handleRetry = () => {
    errorMessage.value = ''
    errorSuggestions.value = []
  }

  const resetForm = () => {
    formData.scene = ''
    formData.case_type = ''
    formData.exec_mode = 'all'
    formData.priority = 2
    formData.extra_requirements = ''
    formData.enhanced_mode = true
    generatedCases.value = []
    currentCaseIndex.value = -1
    selectedCaseIndices.value = new Set()
    caseIdSeq = 0
    errorMessage.value = ''
    errorSuggestions.value = []
    isEditingResult.value = false
    lastContext.value = {}
    currentStep.value = 0
  }

  // ========== 辅助方法 ==========
  const getPriorityType = (priority: number): string => {
    const types: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'info', 4: 'success' }
    return types[priority] || 'info'
  }

  const getSelectedTagType = (id: number): string => {
    const point = testPointCache.get(id) || testPoints.value.find((p) => p.id === id)
    if (point) {
      return getPriorityType(point.priority)
    }
    return 'primary'
  }

  const getTypeTagType = (type: string): string => {
    const typeMap: Record<string, string> = {
      ui_automation: 'success',
      manual: 'info',
      api_automation: 'primary',
      performance: 'warning',
      security: 'danger',
      UI: 'success',
      API: '',
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

  const getPriorityTagType = (priority: unknown): string => {
    const priorityMap: Record<string, string> = {
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
    formData.ui_screen_ids = data.nodes.map((n) => n.screen_id)
    const flowSortStore = useFlowSortStore()
    flowSortStore.updateNodes(data.nodes)
    flowSortStore.updateEdges(data.edges)
    flowSortStore.triggerAutoSave()
  }

  /** 清理 blob URL */
  const cleanupScreenImages = () => {
    Object.values(screenImageUrls.value).forEach((url) => {
      if (url.startsWith('blob:')) {
        URL.revokeObjectURL(url)
      }
    })
    screenImageUrls.value = {}
  }

  const resetGenerateState = () => {
    generating.value = false
    progress.value = 0
    errorMessage.value = ''
    generatedCases.value = []
    currentCaseIndex.value = -1
    selectedCaseIndices.value = new Set()
    caseIdSeq = 0
  }

  return {
    // 状态
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
    selectedUiPrototypeProject,
    uiScreens,
    screenImageUrls,
    showParseWarning,
    projectCases,
    selectedHistoryCaseIds,
    _historyCaseUserCleared,
    isLoadingProjectCases,
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
    allSelected,
    hasSelected,
    selectedCount,
    toggleCaseSelection,
    toggleSelectAll,
    issueDialogVisible,
    issueDialogValidation,
    formData,
    // 计算属性
    flowSortModuleInfo,
    screenPreviewStatusType,
    screenPreviewStatusText,
    viewingCase,
    selectedTestPointsForDisplay,
    canGenerate,
    generateButtonLabel,
    progressStatus,
    // 方法
    getProjects,
    loadProjectFiles,
    loadTestPoints,
    handleSourceFileChange,
    selectAllTestPoints,
    deselectAllTestPoints,
    addTestPoint,
    removeTestPoint,
    getTestPointLabel,
    selectCurrentPageAll,
    goToTestPointPage,
    loadProjectCases,
    loadUIPrototypeProjects,
    loadUIScreens,
    loadScreenImages,
    handleUIPrototypeProjectChange,
    handleProjectChange,
    handleProjectFocus,
    extractFileContent,
    nextStep,
    prevStep,
    skipToStep2,
    handleCaseTypeChange,
    handleGenerate,
    handleRegenerateCase,
    handleDeleteCase,
    handleRegenerateSelected,
    handleDeleteSelected,
    handleCancel,
    handleSaveCase,
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
    onIssueDialogConfirm,
    onIssueDialogCancel,
    cleanupScreenImages,
    resetGenerateState,
  }
})
