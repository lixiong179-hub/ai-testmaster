import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { uiPrototypeApi, type UIPrototypeProject, type UIScreen } from '@/api/uiPrototype'
import { uiPrototypeFlowApi, type UIPrototypeFlowSummary } from '@/api/uiPrototypeFlow'
import { iterationApi, type Iteration } from '@/api/iteration'
import { getRouteQueryParam, isUIScreenListResponse } from '@/composables/uiPrototypeHelpers'
import { useScreenImageUrl } from '@/composables/useScreenImageUrl'

export function useUIPrototype() {
  const route = useRoute()
  const router = useRouter()
  const { getImageUrl, cleanupImageCache } = useScreenImageUrl()

  const projectId = computed(() => Number(route.query.project_id || 0))
  const prototypeProjectId = computed(() => Number(route.query.prototype_project_id || 0))
  const prototypeName = computed(() => String(route.query.name || 'UI原型图'))
  const iterationId = computed(() => {
    const id = route.query.iteration_id
    return id ? Number(id) : undefined
  })
  const iterationName = computed(() => String(route.query.iteration_name || ''))

  const currentIteration = ref<Iteration | null>(null)
  const loading = ref(false)
  const parsing = ref(false)
  const uploading = ref(false)
  const flowGenerating = ref(false)
  const screens = ref<UIScreen[]>([])
  type UIPrototypeProjectWithFlow = UIPrototypeProject & {
    has_flow?: boolean
    flow_summary?: UIPrototypeFlowSummary
  }

  const prototypeProject = ref<UIPrototypeProjectWithFlow | null>(null)
  const screenImageUrls = ref<Record<number, string>>({})
  const pendingScreensIds = ref<number[]>([])
  const previewVisible = ref(false)
  const previewScreen = ref<UIScreen | null>(null)
  const uploadDialogVisible = ref(false)
  const parseMode = ref<'text' | 'vision'>('text')

  const pendingScreensCount = computed(() => pendingScreensIds.value.length)
  const completedScreenCount = computed(
    () => screens.value.filter((s) => s.parse_status === 'completed').length
  )
  const failedScreenCount = computed(
    () => screens.value.filter((s) => s.parse_status === 'failed').length
  )
  const pendingScreenCount = computed(
    () =>
      screens.value.filter(
        (s) => !s.parse_status || s.parse_status === 'pending' || s.parse_status === 'running'
      ).length
  )
  const processedScreensCount = computed(() => {
    if (!pendingScreensIds.value.length) return 0
    return screens.value.filter(
      (s) =>
        pendingScreensIds.value.includes(s.id!) &&
        (s.parse_status === 'completed' || s.parse_status === 'failed')
    ).length
  })
  const hasFlow = computed(() => Boolean(prototypeProject.value?.has_flow))
  const flowSummary = computed<UIPrototypeFlowSummary | null>(
    () => prototypeProject.value?.flow_summary || null
  )
  type WorkflowStepStatus = 'success' | 'process' | 'wait'
  const workflowSteps = computed(() => [
    {
      title: '上传截图',
      status: (screens.value.length > 0 ? 'success' : 'process') as WorkflowStepStatus,
      description:
        screens.value.length > 0 ? `已上传 ${screens.value.length} 张` : '先上传页面截图',
    },
    {
      title: '解析页面',
      status: (parsing.value
        ? 'process'
        : completedScreenCount.value > 0
          ? 'success'
          : 'wait') as WorkflowStepStatus,
      description:
        completedScreenCount.value > 0
          ? `已解析 ${completedScreenCount.value}/${screens.value.length}`
          : '识别元素和单页跳转',
    },
    {
      title: '分析页面流转',
      status: (flowGenerating.value
        ? 'process'
        : hasFlow.value
          ? 'success'
          : 'wait') as WorkflowStepStatus,
      description: hasFlow.value ? '已生成项目级流转' : '至少需要 2 张已解析页面',
    },
    {
      title: '生成用例/回归分析',
      status: (hasFlow.value ? 'process' : 'wait') as WorkflowStepStatus,
      description: hasFlow.value ? '可进入后续分析' : '流转完成后推荐执行',
    },
  ])

  const primaryActionText = computed(() => {
    if (screens.value.length === 0) return '上传截图'
    if (pendingScreenCount.value > 0 || failedScreenCount.value > 0) {
      return parseMode.value === 'text' ? '解析页面' : 'AI视觉解析'
    }
    if (!hasFlow.value && completedScreenCount.value >= 2) return '分析页面流转'
    return '生成测试用例'
  })

  function goBack() {
    router.push('/home/requirement')
  }
  function goToScenario4() {
    router.push({
      name: 'IterationRegressionGenerate',
      query: {
        project_id: projectId.value,
        ui_project_id: prototypeProjectId.value,
        name: prototypeName.value,
        change_source: 'ui_flow',
      },
    })
  }
  function goToCaseGenerate() {
    router.push({
      path: '/home/case/smart-generate',
      query: {
        project_id: projectId.value,
        ui_project_id: prototypeProjectId.value,
      },
    })
  }

  function goToFlowEditor() {
    goToCaseGenerate()
  }

  async function handlePrimaryAction() {
    if (screens.value.length === 0) {
      handleAddScreens()
      return
    }
    if (pendingScreenCount.value > 0 || failedScreenCount.value > 0) {
      await handleBatchParse()
      return
    }
    if (!hasFlow.value && completedScreenCount.value >= 2) {
      await handleGenerateFlow()
      return
    }
    goToCaseGenerate()
  }

  async function loadIterationDetail() {
    if (iterationId.value && iterationName.value) {
      currentIteration.value = {
        id: iterationId.value,
        project_id: projectId.value,
        name: iterationName.value,
        version: getRouteQueryParam(route.query.iteration_version),
        description: '',
        status: '',
        start_date: '',
        end_date: '',
        create_time: '',
        update_time: '',
      }
      return
    }
    if (iterationId.value && !iterationName.value) {
      try {
        const response = await iterationApi.getIteration(iterationId.value)
        currentIteration.value = response.data
      } catch (error: unknown) {
        const err = error as { response?: { status?: number } }
        if (err?.response?.status !== 404) ElMessage.warning('迭代信息加载失败')
      }
    }
  }

  function extractProjectItems(response: unknown): UIPrototypeProjectWithFlow[] {
    if (Array.isArray(response)) return response as UIPrototypeProjectWithFlow[]
    if (!response || typeof response !== 'object') return []
    const root = response as Record<string, unknown>
    const data = root.data
    if (data && typeof data === 'object') {
      const items = (data as Record<string, unknown>).items
      return Array.isArray(items) ? (items as UIPrototypeProjectWithFlow[]) : []
    }
    const items = root.items
    return Array.isArray(items) ? (items as UIPrototypeProjectWithFlow[]) : []
  }

  async function loadPrototypeProject() {
    if (!projectId.value || !prototypeProjectId.value) return
    try {
      const response = await uiPrototypeApi.getUIPrototypeProjectList(
        projectId.value,
        1,
        100,
        iterationId.value
      )
      prototypeProject.value =
        extractProjectItems(response).find((item) => item.id === prototypeProjectId.value) || null
    } catch (error) {
      console.warn('加载 UI 原型流程状态失败:', error)
      prototypeProject.value = null
    }
  }

  async function loadScreens() {
    if (!projectId.value || !prototypeProjectId.value) return
    loading.value = true
    try {
      const res = await uiPrototypeApi.getUIScreenList(projectId.value, prototypeProjectId.value)
      let screenList: UIScreen[] = []
      if (isUIScreenListResponse(res)) {
        const responseData = (res as unknown as { data: { items: UIScreen[] } }).data
        screenList = responseData?.items || []
      } else if (Array.isArray(res)) {
        screenList = res as UIScreen[]
      }
      screens.value = screenList
      const imagePromises = screens.value
        .filter((s) => s.id && s.original_file_path)
        .map((screen) => getImageUrl(screen).then((url) => ({ id: screen.id, url })))
      const results = await Promise.all(imagePromises)
      results.forEach(({ id, url }) => {
        if (id && url) screenImageUrls.value[id] = url
      })
      await loadPrototypeProject()
    } catch (error) {
      ElMessage.error('加载截图列表失败，请刷新重试')
      screens.value = []
    } finally {
      loading.value = false
    }
  }

  async function handlePreviewScreen(screen: UIScreen) {
    previewScreen.value = screen
    if (screen.id && !screenImageUrls.value[screen.id]) {
      const url = await getImageUrl(screen)
      if (url && screen.id) screenImageUrls.value[screen.id] = url
    }
    previewVisible.value = true
  }

  async function handleParseScreen(screen: UIScreen) {
    if (parsing.value) return
    try {
      pendingScreensIds.value = [screen.id!]
      parsing.value = true
      await uiPrototypeApi.parseUIScreens([screen.id], prototypeProjectId.value, parseMode.value)
      ElMessage.success('解析任务已启动')
      await pollParseStatus()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '解析失败')
    } finally {
      parsing.value = false
      pendingScreensIds.value = []
    }
  }

  async function handleBatchParse() {
    if (parsing.value) return
    const pending = screens.value.filter(
      (s) => s.parse_status === 'pending' || s.parse_status === 'failed'
    )
    if (pending.length === 0) {
      ElMessage.info('所有图片已解析完成')
      return
    }
    try {
      pendingScreensIds.value = pending.map((s) => s.id!)
      parsing.value = true
      await uiPrototypeApi.parseUIScreens(
        pending.map((s) => s.id),
        prototypeProjectId.value,
        parseMode.value
      )
      ElMessage.success(
        parseMode.value === 'text'
          ? `已启动 ${pending.length} 张图片的文本模型一键解析`
          : `已启动 ${pending.length} 张图片的AI视觉解析`
      )
      await pollParseStatus()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '批量解析失败')
    } finally {
      parsing.value = false
      pendingScreensIds.value = []
    }
  }

  async function handleGenerateFlow() {
    if (flowGenerating.value) return
    if (completedScreenCount.value < 2) {
      ElMessage.warning('至少需要 2 张已解析页面才能分析页面流转')
      return
    }
    try {
      flowGenerating.value = true
      const response = await uiPrototypeFlowApi.generatePageFlow(prototypeProjectId.value)
      const result = response?.data || response
      if (result?.success === false) {
        ElMessage.warning(response?.msg || response?.message || '页面流转分析未完成')
        return
      }
      ElMessage.success(response?.msg || response?.message || '页面流转分析完成')
      await loadPrototypeProject()
      await loadScreens()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } }; message?: string }
      ElMessage.error(err?.response?.data?.detail || err?.message || '页面流转分析失败')
    } finally {
      flowGenerating.value = false
    }
  }

  function handleCancelParse() {
    ElMessage.info('解析任务已取消')
    parsing.value = false
    pendingScreensIds.value = []
  }

  async function pollParseStatus(maxAttempts: number = 40) {
    const currentScreenId = previewScreen.value?.id
    for (let i = 0; i < maxAttempts && parsing.value; i++) {
      const delay = i < 5 ? 2000 : i < 15 ? 5000 : 10000
      await new Promise((resolve) => setTimeout(resolve, delay))
      await loadScreens()
      if (currentScreenId) {
        const updated = screens.value.find((s) => s.id === currentScreenId)
        if (updated) previewScreen.value = updated
      }
      if (
        screens.value
          .filter((s) => pendingScreensIds.value.includes(s.id!))
          .every((s) => s.parse_status === 'completed' || s.parse_status === 'failed')
      ) {
        ElMessage.success('所有图片解析完成！')
        break
      }
    }
  }

  async function handleDeleteScreen(screen: UIScreen) {
    try {
      await ElMessageBox.confirm(`确定要删除图片 "${screen.screen_name}" 吗？`, '删除确认', {
        type: 'warning',
      })
      await uiPrototypeApi.deleteUIScreen(screen.id)
      ElMessage.success('删除成功')
      loadScreens()
    } catch (error: unknown) {
      if (error !== 'cancel') {
        const err = error as { response?: { data?: { detail?: string } } }
        ElMessage.error(err?.response?.data?.detail || '删除失败')
      }
    }
  }

  function handleAddScreens() {
    uploadDialogVisible.value = true
  }

  async function handleUploadSubmit(files: File[]) {
    uploading.value = true
    try {
      const response = await uiPrototypeApi.uploadUIScreens(
        projectId.value,
        files,
        prototypeName.value,
        prototypeProjectId.value,
        iterationId.value
      )
      const result = response?.data || response
      if (result?.total > 0) ElMessage.success(`追加上传成功，共 ${result.total} 张图片`)
      uploadDialogVisible.value = false
      await loadScreens()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '上传失败')
    } finally {
      uploading.value = false
    }
  }

  onMounted(async () => {
    if (!projectId.value || !prototypeProjectId.value) {
      ElMessage.error('缺少项目ID或原型项目ID参数')
      goBack()
      return
    }
    await loadIterationDetail()
    await loadScreens()
  })
  onUnmounted(() => cleanupImageCache())

  return {
    projectId,
    prototypeProjectId,
    prototypeName,
    iterationName,
    currentIteration,
    loading,
    parsing,
    uploading,
    flowGenerating,
    screens,
    prototypeProject,
    screenImageUrls,
    previewVisible,
    previewScreen,
    uploadDialogVisible,
    parseMode,
    completedScreenCount,
    failedScreenCount,
    pendingScreenCount,
    pendingScreensCount,
    processedScreensCount,
    hasFlow,
    flowSummary,
    workflowSteps,
    primaryActionText,
    goBack,
    goToScenario4,
    goToCaseGenerate,
    goToFlowEditor,
    handlePrimaryAction,
    handlePreviewScreen,
    handleParseScreen,
    handleBatchParse,
    handleGenerateFlow,
    handleCancelParse,
    handleDeleteScreen,
    handleAddScreens,
    handleUploadSubmit,
  }
}
