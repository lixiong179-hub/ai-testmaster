import { defineStore } from 'pinia'
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { testPointApi, type TestPoint } from '@/api/testPoint'
import { fileApi, type ProjectFile } from '@/api/file'
import { type Project } from '@/api/project'
import caseApi from '@/api/case'
import request, { type ApiResponse } from '@/utils/request'
import { uiPrototypeApi, type UIPrototypeProject, type UIScreen } from '@/api/uiPrototype'
import type { FlowNodeData, FlowEdgeData } from '@/store/flowSort'

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
}

/** 生成用例的数据结构 */
export interface GeneratedCase {
    id: number
    test_point_id: number
    test_point_label: string
    title: string
    module: string
    case_type: string
    precondition: string
    test_data?: Record<string, Record<string, string | number | boolean | null>>
    steps: GeneratedStep[]
    expected_result: string
    priority: number
    scene?: string
    _error?: string
    _saved?: boolean
}

/** 编辑中的用例数据 */
export interface EditingCase {
    title: string
    module: string
    case_type: string
    precondition: string
    expected_result: string
    priority: number
    steps: GeneratedStep[]
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

let _caseNoCounter = 0

function generateCaseNo(projectId: number | '', extraSuffix?: number): string {
    _caseNoCounter++
    const ts = Date.now()
    const suffix = extraSuffix != null ? `-${extraSuffix}` : ''
    return `CASE${String(projectId)}-${ts}-${_caseNoCounter}${suffix}`
}

function normalizePriority(priority: unknown): number {
    if (typeof priority === 'number') {
        if (priority < 1) return 1
        if (priority > 3) return 3
        return priority
    }
    const pMap: Record<string, number> = { P0: 1, P2: 2, P3: 3, '1': 1, '2': 2, '3': 3 }
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
    const showParseWarning = ref(true)

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
        return uiPrototypeProjects.value.find(
            (p) => p.id === selectedUiPrototypeProjectId.value
        ) || null
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
            formData.ui_screen_ids.length > 0
        )
    })

    const generateButtonLabel = computed(() => {
        const count = formData.test_point_ids.length
        if (count > 0) return `${count} 个测试用例`
        if (formData.requirement_file_ids.length > 0) {
            return `${formData.requirement_file_ids.length} 份需求`
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
                projects.value = response.data.items.filter(
                    (p: Project) => p.name !== '默认项目'
                )
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
            requirementFiles.value = items.filter(
                (f) => f.resource_type === 'requirement'
            )
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
                    const allApiData = await testPointApi.getList(
                        formData.project_id as number,
                        { page: 1, page_size: Math.min(testPointTotal.value, 200) }
                    )
                    if (allApiData?.items) {
                        testPointAllIds.value = allApiData.items.map(
                            (item: TestPoint) => item.id
                        )
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

    // ========== UI 原型操作 ==========
    const loadUIPrototypeProjects = async () => {
        if (!formData.project_id) return
        try {
            const response = await uiPrototypeApi.getUIPrototypeProjectList(
                formData.project_id as number
            )
            if (response) {
                uiPrototypeProjects.value = Array.isArray(response)
                    ? response
                    : (response as Record<string, unknown>)?.data
                        ? ((response as Record<string, { items: UIPrototypeProject[] }>).data.items || [])
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
                    (a: UIScreen, b: UIScreen) =>
                        (a.screen_order || 0) - (b.screen_order || 0)
                )
                loadScreenImages()
            }
        } catch (error) {
            console.error('获取 UI 屏幕列表失败:', error)
        }
    }

    const loadScreenImages = async () => {
        for (const screen of uiScreens.value) {
            if (screen.id && screen.original_file_path && !screenImageUrls.value[screen.id]) {
                try {
                    const token = localStorage.getItem('token')
                    const baseUrl = import.meta.env?.VITE_API_BASE_URL || ''
                    const resp = await fetch(
                        `${baseUrl}/api/v1/file/preview-screen/${screen.id}`,
                        { headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) } }
                    )
                    if (!resp.ok) continue
                    const blob = await resp.blob()
                    if (blob.size > 0) {
                        screenImageUrls.value[screen.id] = URL.createObjectURL(blob)
                    }
                } catch (e) {
                    console.warn(`加载屏幕图片失败: ${screen.id}`, e)
                }
            }
        }
    }

    const handleUIPrototypeProjectChange = async (projectId: number | string) => {
        showParseWarning.value = true
        lastContext.value = {}
        selectedUiPrototypeProjectId.value = projectId as number | ''
        if (projectId) {
            await loadUIScreens(projectId as number)
            if (uiScreens.value.length > 0) {
                formData.ui_screen_ids = uiScreens.value.map((s) => s.id)
            } else {
                formData.ui_screen_ids = []
            }
        } else {
            uiScreens.value = []
            formData.ui_screen_ids = []
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
        selectedUiPrototypeProjectId.value = ''
        uiPrototypeProjects.value = []
        uiScreens.value = []
        handleSourceFileChange()
        loadProjectFiles()
        loadUIPrototypeProjects()
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
            error.includes('认证') || error.includes('authentication') ||
            (error.includes('api') && error.includes('key')) ||
            error.includes('503') || error.includes('无效')
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
            error.includes('429') || error.includes('rate limit') ||
            error.includes('频率') || error.includes('过多')
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

    const handleGenerate = async (
        flowSortEditorRef: { getFlowSortSubmitData?: () => { mode: 'graph'; flow_sort_data: Record<string, unknown> }; getFlowValidationIssues?: () => { errors: string[]; warnings: string[] } } | null
    ) => {
        if (!canGenerate.value) {
            ElMessage.warning('请先选择测试点或需求文档')
            return
        }

        // 流程图校验
        if (selectedUiPrototypeProjectId.value && uiScreens.value.length > 0) {
            const validation = flowSortEditorRef?.getFlowValidationIssues?.()
            if (validation?.errors.length) {
                ElMessage.warning(validation.errors[0])
                return
            }
            if (validation?.warnings.length) {
                try {
                    await ElMessageBox.confirm(
                        validation.warnings.join('\n'),
                        '流程图完整性提示',
                        { confirmButtonText: '继续生成', cancelButtonText: '返回调整', type: 'warning' }
                    )
                } catch {
                    return
                }
            }
        }

        const targetPoints =
            formData.test_point_ids.length > 0
                ? formData.test_point_ids
                : (contextPreview.value?.test_points || []).map((tp) => tp.id)

        if (targetPoints.length === 0) {
            ElMessage.warning('没有可用的测试点')
            return
        }

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

        generatedCases.value = []
        currentCaseIndex.value = -1
        errorMessage.value = ''
        errorSuggestions.value = []
        generating.value = true
        progress.value = 0
        progressText.value = `准备生成 ${targetPoints.length} 条测试用例...`
        currentStep.value = 2

        const total = targetPoints.length
        let completed = 0

        const progressInterval = setInterval(() => {
            const targetPct = Math.min(90, Math.round((completed / total) * 90))
            if (progress.value < targetPct) {
                progress.value = Math.min(progress.value + 5, targetPct)
                progressText.value = `生成中... ${completed}/${total} (${progress.value}%)`
            }
        }, 300)

        try {
            let context: Record<string, unknown> = {
                requirement_content: '',
                ui_description: '',
                test_points: [],
                project_config: null,
            }

            if (formData.project_id) {
                const contextResponse: ApiResponse<{
                    requirement_content?: string
                    ui_descriptions?: unknown[]
                    ui_specs?: unknown[]
                    test_points?: TestPoint[]
                    project_config?: unknown
                }> = await request.post('/api/v1/testCase/generate-context', {
                    project_id: Number(formData.project_id),
                    requirement_file_ids:
                        formData.requirement_file_ids.length > 0
                            ? formData.requirement_file_ids
                            : undefined,
                    ui_file_ids:
                        formData.ui_file_ids.length > 0 ? formData.ui_file_ids : undefined,
                    ui_screen_ids:
                        formData.ui_screen_ids.length > 0 ? formData.ui_screen_ids : undefined,
                    test_point_ids: targetPoints,
                })

                if (contextResponse?.data) {
                    const data = contextResponse.data
                    context = {
                        requirement_content: data.requirement_content || '',
                        ui_description: JSON.stringify(data.ui_descriptions || []),
                        ui_specs: data.ui_specs || [],
                        test_points: data.test_points || [],
                        project_config: data.project_config || null,
                    }
                    lastContext.value = { ...context }
                }
            }

            const allTestPoints = (context.test_points || []) as TestPoint[]

            for (let i = 0; i < targetPoints.length; i++) {
                const tpId = targetPoints[i]
                const tpInfo = allTestPoints.find((tp) => tp.id === tpId)
                const tpLabel = tpInfo
                    ? `${tpInfo.module} - ${tpInfo.point}`
                    : `测试点#${tpId}`

                try {
                    const flowSortSubmitData =
                        flowSortEditorRef?.getFlowSortSubmitData?.()
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
                    apiData.mode = 'graph'
                    apiData.flow_sort_data = flowSortSubmitData?.flow_sort_data || {
                        nodes: uiScreens.value.map((screen, index) => ({
                            screen_id: screen.id,
                            screen_order: index + 1,
                            flow_type: 'main',
                            screen_name: screen.screen_name,
                            ui_spec_elements: screen.ui_spec?.elements || [],
                            summary: screen.summary || '',
                        })),
                        edges: [],
                        module_info: flowSortModuleInfo.value,
                    }

                    const response = await caseApi.aiGenerateCaseEnhanced(
                        apiData as unknown as Parameters<typeof caseApi.aiGenerateCaseEnhanced>[0]
                    )
                    const caseData = response

                    generatedCases.value.push({
                        id: Date.now() + i,
                        test_point_id: tpId,
                        test_point_label: tpLabel,
                        title: caseData.title || caseData.name || `${tpLabel} 测试用例`,
                        module: caseData.module || tpInfo?.module || '',
                        case_type: caseData.case_type || caseData.type || formData.case_type,
                        precondition: caseData.precondition || '',
                        test_data: caseData.test_data,
                        steps: (caseData.steps || []) as GeneratedStep[],
                        expected_result: caseData.expected_result || '',
                        priority: caseData.priority || formData.priority,
                        scene: formData.scene,
                    })
                } catch (err: unknown) {
                    const error = err as {
                        response?: { data?: { detail?: string } }
                        message?: string
                    }
                    generatedCases.value.push({
                        id: Date.now() + i,
                        test_point_id: tpId,
                        test_point_label: tpLabel,
                        title: `${tpLabel} 测试用例（生成失败）`,
                        module: tpInfo?.module || '',
                        case_type: formData.case_type,
                        precondition: '',
                        steps: [],
                        expected_result: '',
                        priority: formData.priority,
                        _error: error.response?.data?.detail || error.message || '生成失败',
                        scene: formData.scene,
                    })
                }

                completed++
                progress.value = Math.round((completed / total) * 90)
                progressText.value = `生成中... ${completed}/${total}`
            }

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
        } catch (error: unknown) {
            const err = error as {
                response?: { data?: { detail?: string; message?: string } }
                message?: string
            }
            progress.value = 100
            progressText.value = '生成失败'
            errorMessage.value =
                err.response?.data?.detail || err.response?.data?.message || err.message || 'AI生成测试用例失败'
            generateErrorSuggestions()
            ElMessage.error(errorMessage.value)
        } finally {
            clearInterval(progressInterval)
            generating.value = false
        }
    }

    const handleContinueGenerate = async () => {
        const current = viewingCase.value
        if (!current) {
            ElMessage.warning('没有可基于的用例')
            return
        }

        generating.value = true
        progress.value = 0
        progressText.value = '准备重新生成...'

        const progressInterval = setInterval(() => {
            if (progress.value < 90) {
                progress.value += 10
                progressText.value = `生成中... ${progress.value}%`
            }
        }, 500)

        try {
            const apiData = {
                project_id: Number(formData.project_id),
                description: formData.scene || `基于已有用例"${current.title}"继续优化生成`,
                case_type: formData.case_type || current.case_type,
                exec_mode: formData.exec_mode || 'all',
                priority: formData.priority || current.priority || 2,
                enhanced_mode: formData.enhanced_mode !== undefined ? formData.enhanced_mode : true,
                extra_requirements: formData.extra_requirements || '',
                context: {
                    base_case: {
                        title: current.title,
                        module: current.module,
                        precondition: current.precondition,
                        steps: current.steps || [],
                        expected_result: current.expected_result,
                    },
                    requirement_content: contextPreview.value?.requirement_content || '',
                    ui_description: (lastContext.value as Record<string, string>).ui_description || '',
                    ui_specs: (lastContext.value as Record<string, unknown[]>).ui_specs || [],
                    test_points:
                        formData.test_point_ids.length > 0
                            ? []
                            : contextPreview.value?.test_points || [],
                },
            }

            const response = await caseApi.aiGenerateCaseEnhanced(
                apiData as unknown as Parameters<typeof caseApi.aiGenerateCaseEnhanced>[0]
            )
            const caseData = response

            if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
                generatedCases.value[currentCaseIndex.value] = {
                    ...generatedCases.value[currentCaseIndex.value],
                    title: caseData.title || caseData.name || '',
                    module: caseData.module || '',
                    case_type: caseData.case_type || caseData.type || '',
                    precondition: caseData.precondition || '',
                    test_data: caseData.test_data,
                    steps: (caseData.steps || []) as GeneratedStep[],
                    expected_result: caseData.expected_result || '',
                    priority: caseData.priority || formData.priority,
                    _error: undefined,
                }
            }

            progress.value = 100
            progressText.value = '生成完成！'
            ElMessage.success('AI继续生成测试用例成功')
        } catch (error: unknown) {
            const err = error as {
                response?: { data?: { detail?: string; message?: string } }
                message?: string
            }
            progress.value = 100
            progressText.value = '生成失败'
            errorMessage.value =
                err.response?.data?.detail || err.response?.data?.message || err.message || '继续生成失败'
            generateErrorSuggestions()
            ElMessage.error(errorMessage.value)
        } finally {
            clearInterval(progressInterval)
            generating.value = false
        }
    }

    const handleCancel = () => {
        ElMessageBox.confirm('确定要取消生成吗？', '取消确认', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
        }).then(() => {
            generating.value = false
            progress.value = 0
            progressText.value = '已取消'
            ElMessage.info('生成已取消')
        })
    }

    // ========== 保存逻辑 ==========
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
            const stepsPayload = (caseToSave.steps || []).map(
                (s: GeneratedStep, i: number) => ({
                    step: String(s.step || i + 1),
                    action: s.action || '',
                    param: s.input_value || s.param || '',
                    expected_result: s.expected_result || '',
                    action_type: s.action_type || '',
                    input_value: s.input_value || '',
                    target_element: s.target_element || '',
                })
            )
            const priority = normalizePriority(caseToSave.priority)

            await caseApi.createCase({
                project_id: Number(formData.project_id),
                case_no: generateCaseNo(formData.project_id),
                title: caseToSave.title || '未命名测试用例',
                module: caseToSave.module || '默认模块',
                case_type: caseToSave.case_type || '',
                precondition: caseToSave.precondition || '系统已通过配置自动登录至目标页面',
                steps:
                    stepsPayload.length > 0
                        ? (stepsPayload as unknown as import('@/api/case').TestCaseStep[])
                        : [{ step: 1, action: '执行测试', param: '预期结果正常' }],
                expected_result: caseToSave.expected_result || '操作成功',
                priority,
                generate_status: 1,
            })
            ElMessage.success(`"${caseToSave.title}" 保存成功`)
            isEditingResult.value = false

            if (currentCaseIndex.value >= 0 && currentCaseIndex.value < generatedCases.value.length) {
                generatedCases.value[currentCaseIndex.value]._saved = true
            }
        } catch (error: unknown) {
            const err = error as { response?: { data?: { detail?: string } } }
            const detail = err.response?.data?.detail
            ElMessage.error(
                detail && typeof detail === 'string' ? detail : '保存失败，请检查必填字段'
            )
        } finally {
            saving.value = false
        }
    }

    const saveAllCases = async () => {
        const toSave = generatedCases.value.filter((c) => !c._error && !c._saved)
        if (toSave.length === 0) {
            ElMessage.info('没有需要保存的用例')
            return
        }

        saving.value = true
        let successCount = 0
        let failCount = 0

        for (const c of toSave) {
            try {
                const stepsPayload = (c.steps || []).map(
                    (s: GeneratedStep, i: number) => ({
                        step: String(s.step || i + 1),
                        action: s.action || '',
                        param: s.input_value || s.param || '',
                        expected_result: s.expected_result || '',
                        action_type: s.action_type || '',
                        input_value: s.input_value || '',
                        target_element: s.target_element || '',
                    })
                )
                const priority = normalizePriority(c.priority)

                await caseApi.createCase({
                    project_id: Number(formData.project_id),
                    case_no: generateCaseNo(formData.project_id, c.id),
                    title: c.title || '未命名测试用例',
                    module: c.module || '默认模块',
                    case_type: c.case_type || '',
                    precondition: c.precondition || '系统已通过配置自动登录至目标页面',
                    steps:
                        stepsPayload.length > 0
                            ? (stepsPayload as unknown as import('@/api/case').TestCaseStep[])
                            : [{ step: 1, action: '执行测试', param: '预期结果正常' }],
                    expected_result: c.expected_result || '操作成功',
                    priority,
                    generate_status: 1,
                })
                c._saved = true
                successCount++
            } catch (e) {
                console.error(`保存失败(${c.title}):`, e)
                failCount++
            }
        }

        saving.value = false
        if (failCount === 0) {
            ElMessage.success(`全部保存成功，共 ${successCount} 条`)
        } else {
            ElMessage.warning(`保存完成：${successCount} 成功，${failCount} 失败`)
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
            precondition: current.precondition || '',
            expected_result: current.expected_result || '',
            priority: current.priority || 2,
            steps: current.steps ? JSON.parse(JSON.stringify(current.steps)) : [],
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
        errorMessage.value = ''
        errorSuggestions.value = []
        isEditingResult.value = false
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
            ui_automation: 'success', manual: 'info', api_automation: '',
            performance: 'warning', security: 'danger', UI: 'success', API: '',
            功能: 'info', 功能测试: 'info', functional: 'info',
        }
        return typeMap[type] || 'info'
    }

    const getTypeLabel = (type: string): string => {
        const typeMap: Record<string, string> = {
            ui_automation: 'UI自动化', manual: '手工测试', api_automation: 'API自动化',
            performance: '性能测试', security: '安全测试', UI: 'UI自动化', API: 'API自动化',
            功能: '手工测试', 功能测试: '手工测试', functional: '手工测试',
            接口: 'API自动化', 接口测试: 'API自动化',
        }
        return typeMap[type] || type
    }

    const getPriorityTagType = (priority: unknown): string => {
        const priorityMap: Record<string, string> = {
            '1': 'danger', P0: 'danger', '2': 'warning', P2: 'warning',
            '3': 'info', P3: 'info',
        }
        return priorityMap[String(priority)] || 'info'
    }

    const getPriorityLabel = (priority: unknown): string => {
        const priorityMap: Record<string, string> = {
            '1': '高(P0)', P0: 'P0-高', '2': '中(P2)', P2: 'P2-中',
            '3': '低(P3)', P3: 'P3-低',
        }
        return priorityMap[String(priority)] || String(priority)
    }

    const getDataTypeLabel = (key: string | number): string => {
        const keyStr = String(key)
        const labelMap: Record<string, string> = {
            normal: '正向数据', boundary: '边界值', abnormal: '异常数据',
        }
        return labelMap[keyStr] || keyStr
    }

    const cleanExpectedResult = (text: string): string => {
        if (!text) return text
        return text.replace(/^【\d+】\s*/, '')
    }

    const handleFlowSortUpdate = (data: { mode: string; nodes: FlowNodeData[]; edges: FlowEdgeData[] }) => {
        formData.ui_screen_ids = data.nodes.map((n) => n.screen_id)
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
        handleContinueGenerate,
        handleCancel,
        handleSaveCase,
        saveAllCases,
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
        cleanupScreenImages,
        resetGenerateState,
    }
})
