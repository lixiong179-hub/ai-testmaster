import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { uiPrototypeApi, type UIScreen } from '@/api/uiPrototype'
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
  const iterationId = computed(() => { const id = route.query.iteration_id; return id ? Number(id) : undefined })
  const iterationName = computed(() => String(route.query.iteration_name || ''))

  const currentIteration = ref<Iteration | null>(null)
  const loading = ref(false)
  const parsing = ref(false)
  const uploading = ref(false)
  const screens = ref<UIScreen[]>([])
  const screenImageUrls = ref<Record<number, string>>({})
  const pendingScreensIds = ref<number[]>([])
  const previewVisible = ref(false)
  const previewScreen = ref<UIScreen | null>(null)
  const uploadDialogVisible = ref(false)
  const parseMode = ref<'text' | 'vision'>('text')

  const pendingScreensCount = computed(() => pendingScreensIds.value.length)
  const completedScreenCount = computed(() => screens.value.filter((s) => s.parse_status === 'completed').length)
  const failedScreenCount = computed(() => screens.value.filter((s) => s.parse_status === 'failed').length)
  const pendingScreenCount = computed(() => screens.value.filter((s) => !s.parse_status || s.parse_status === 'pending' || s.parse_status === 'running').length)
  const processedScreensCount = computed(() => {
    if (!pendingScreensIds.value.length) return 0
    return screens.value.filter((s) => pendingScreensIds.value.includes(s.id!) && (s.parse_status === 'completed' || s.parse_status === 'failed')).length
  })

  function goBack() { router.push('/home/requirement') }
  function goToScenario4() {
    router.push({ path: '/home/iteration/regression-generate', query: { project_id: projectId.value, ui_project_id: prototypeProjectId.value, name: prototypeName.value } })
  }

  async function loadIterationDetail() {
    if (iterationId.value && iterationName.value) {
      currentIteration.value = { id: iterationId.value, project_id: projectId.value, name: iterationName.value, version: getRouteQueryParam(route.query.iteration_version), description: '', status: '', start_date: '', end_date: '', create_time: '', update_time: '' }
      return
    }
    if (iterationId.value && !iterationName.value) {
      try { const response = await iterationApi.getIteration(iterationId.value); currentIteration.value = response.data }
      catch (error: unknown) { const err = error as { response?: { status?: number } }; if (err?.response?.status !== 404) ElMessage.warning('迭代信息加载失败') }
    }
  }

  async function loadScreens() {
    if (!projectId.value || !prototypeProjectId.value) return
    loading.value = true
    try {
      const res = await uiPrototypeApi.getUIScreenList(projectId.value, prototypeProjectId.value)
      let screenList: UIScreen[] = []
      if (isUIScreenListResponse(res)) { const responseData = (res as unknown as { data: { items: UIScreen[] } }).data; screenList = responseData?.items || [] }
      else if (Array.isArray(res)) { screenList = res as UIScreen[] }
      screens.value = screenList
      const imagePromises = screens.value.filter((s) => s.id && s.original_file_path).map((screen) => getImageUrl(screen).then((url) => ({ id: screen.id, url })))
      const results = await Promise.all(imagePromises)
      results.forEach(({ id, url }) => { if (id && url) screenImageUrls.value[id] = url })
    } catch (error) { ElMessage.error('加载截图列表失败，请刷新重试'); screens.value = [] }
    finally { loading.value = false }
  }

  async function handlePreviewScreen(screen: UIScreen) {
    previewScreen.value = screen
    if (screen.id && !screenImageUrls.value[screen.id]) { const url = await getImageUrl(screen); if (url && screen.id) screenImageUrls.value[screen.id] = url }
    previewVisible.value = true
  }

  async function handleParseScreen(screen: UIScreen) {
    if (parsing.value) return
    try { pendingScreensIds.value = [screen.id!]; parsing.value = true; await uiPrototypeApi.parseUIScreens([screen.id], prototypeProjectId.value, parseMode.value); ElMessage.success('解析任务已启动'); await pollParseStatus() }
    catch (error: unknown) { const err = error as { response?: { data?: { detail?: string } } }; ElMessage.error(err?.response?.data?.detail || '解析失败') }
    finally { parsing.value = false; pendingScreensIds.value = [] }
  }

  async function handleBatchParse() {
    if (parsing.value) return
    const pending = screens.value.filter((s) => s.parse_status === 'pending' || s.parse_status === 'failed')
    if (pending.length === 0) { ElMessage.info('所有图片已解析完成'); return }
    try {
      pendingScreensIds.value = pending.map((s) => s.id!); parsing.value = true
      await uiPrototypeApi.parseUIScreens(pending.map((s) => s.id), prototypeProjectId.value, parseMode.value)
      ElMessage.success(parseMode.value === 'text' ? `已启动 ${pending.length} 张图片的文本模型一键解析` : `已启动 ${pending.length} 张图片的AI视觉解析`)
      await pollParseStatus()
    } catch (error: unknown) { const err = error as { response?: { data?: { detail?: string } } }; ElMessage.error(err?.response?.data?.detail || '批量解析失败') }
    finally { parsing.value = false; pendingScreensIds.value = [] }
  }

  function handleCancelParse() { ElMessage.info('解析任务已取消'); parsing.value = false; pendingScreensIds.value = [] }

  async function pollParseStatus(maxAttempts: number = 40) {
    const currentScreenId = previewScreen.value?.id
    for (let i = 0; i < maxAttempts && parsing.value; i++) {
      const delay = i < 5 ? 2000 : i < 15 ? 5000 : 10000
      await new Promise((resolve) => setTimeout(resolve, delay))
      await loadScreens()
      if (currentScreenId) { const updated = screens.value.find((s) => s.id === currentScreenId); if (updated) previewScreen.value = updated }
      if (screens.value.filter((s) => pendingScreensIds.value.includes(s.id!)).every((s) => s.parse_status === 'completed' || s.parse_status === 'failed')) { ElMessage.success('所有图片解析完成！'); break }
    }
  }

  async function handleDeleteScreen(screen: UIScreen) {
    try { await ElMessageBox.confirm(`确定要删除图片 "${screen.screen_name}" 吗？`, '删除确认', { type: 'warning' }); await uiPrototypeApi.deleteUIScreen(screen.id); ElMessage.success('删除成功'); loadScreens() }
    catch (error: unknown) { if (error !== 'cancel') { const err = error as { response?: { data?: { detail?: string } } }; ElMessage.error(err?.response?.data?.detail || '删除失败') } }
  }

  function handleAddScreens() { uploadDialogVisible.value = true }

  async function handleUploadSubmit(files: File[]) {
    uploading.value = true
    try { const response = await uiPrototypeApi.uploadUIScreens(projectId.value, files, prototypeName.value, prototypeProjectId.value, iterationId.value); const result = response?.data || response; if (result?.total > 0) ElMessage.success(`追加上传成功，共 ${result.total} 张图片`); uploadDialogVisible.value = false; loadScreens() }
    catch (error: unknown) { const err = error as { response?: { data?: { detail?: string } } }; ElMessage.error(err?.response?.data?.detail || '上传失败') }
    finally { uploading.value = false }
  }

  onMounted(async () => { if (!projectId.value || !prototypeProjectId.value) { ElMessage.error('缺少项目ID或原型项目ID参数'); goBack(); return }; await loadIterationDetail(); loadScreens() })
  onUnmounted(() => cleanupImageCache())

  return {
    projectId, prototypeProjectId, prototypeName, currentIteration, loading, parsing,
    uploading, screens, screenImageUrls, previewVisible, previewScreen, uploadDialogVisible,
    parseMode, completedScreenCount, failedScreenCount, pendingScreenCount, pendingScreensCount,
    processedScreensCount, goBack, goToScenario4, handlePreviewScreen, handleParseScreen,
    handleBatchParse, handleCancelParse, handleDeleteScreen, handleAddScreens, handleUploadSubmit,
  }
}
