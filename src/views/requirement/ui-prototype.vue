<template>
  <div class="ui-prototype-container">
    <el-card class="header-card" shadow="never">
      <div class="page-header">
        <div class="header-top">
          <div class="header-left">
            <el-button @click="goBack" :icon="ArrowLeft" circle size="small" />
            <h2 class="prototype-title">{{ prototypeName }}</h2>
            <div class="header-tags">
              <el-tag v-if="currentIteration" type="info" size="small" effect="plain">
                {{ currentIteration.name
                }}{{ currentIteration.version ? ` (${currentIteration.version})` : '' }}
              </el-tag>
              <el-tag v-else-if="iterationName" type="info" size="small" effect="plain">
                {{ iterationName }}
              </el-tag>
              <el-tag type="warning" size="small" effect="plain">UI原型图</el-tag>
              <el-tag type="info" size="small" effect="plain">{{ screens.length }}张</el-tag>
            </div>
          </div>
          <div class="header-right">
            <div class="parse-mode-wrapper">
              <span class="parse-mode-label">解析模式</span>
              <el-radio-group v-model="parseMode" size="small">
                <el-radio-button value="text">文本模式</el-radio-button>
                <el-radio-button value="vision">视觉模型</el-radio-button>
              </el-radio-group>
            </div>
            <div class="action-buttons">
              <el-button type="primary" @click="handleBatchParse" :disabled="screens.length === 0">
                {{ parseMode === 'text' ? '文本模型一键解析' : 'AI视觉解析' }}
              </el-button>
              <el-button type="success" @click="handleAddScreens">
                <el-icon><Upload /></el-icon>
                追加上传
              </el-button>
            </div>
          </div>
        </div>
        <el-alert
          v-if="parseMode === 'vision'"
          title="视觉模型解析将消耗更多API调用费用，建议优先使用文本模式"
          type="warning"
          :closable="false"
          show-icon
          class="vision-alert"
        />
      </div>
    </el-card>

    <div class="overview-strip">
      <div class="overview-card overview-card-primary">
        <div class="overview-label">屏幕总数</div>
        <div class="overview-value">{{ screens.length }}</div>
        <div class="overview-desc">当前原型版本下的全部页面截图</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">已解析</div>
        <div class="overview-value">{{ completedScreenCount }}</div>
        <div class="overview-desc">可查看元素和流程详情</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">待处理</div>
        <div class="overview-value">{{ pendingScreenCount }}</div>
        <div class="overview-desc">尚未完成解析的页面</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">解析失败</div>
        <div class="overview-value">{{ failedScreenCount }}</div>
        <div class="overview-desc">建议重新发起解析</div>
      </div>
    </div>

    <el-card class="content-card" v-loading="loading" shadow="never">
      <div class="content-head">
        <div class="content-head-main">
          <div class="content-title">屏幕列表</div>
          <div class="content-subtitle">
            点击卡片查看详情，解析完成后可在弹层中查看元素、流程与布局信息。
          </div>
        </div>
        <div class="content-tags">
          <el-tag type="success" effect="plain">已解析 {{ completedScreenCount }}</el-tag>
          <el-tag type="warning" effect="plain">待处理 {{ pendingScreenCount }}</el-tag>
          <el-tag type="danger" effect="plain">失败 {{ failedScreenCount }}</el-tag>
        </div>
      </div>
      <ScreenCardGrid
        :screens="screens"
        :image-urls="screenImageUrls"
        :loading="loading"
        @preview="handlePreviewScreen"
        @parse="handleParseScreen"
        @delete="handleDeleteScreen"
        @add-screens="handleAddScreens"
      />
    </el-card>

    <ScreenPreviewDialog
      v-model:visible="previewVisible"
      :screen="previewScreen"
      :image-urls="screenImageUrls"
    />

    <ScreenUploadDialog
      v-model:visible="uploadDialogVisible"
      :uploading="uploading"
      @submit="handleUploadSubmit"
    />

    <AIParseLoading
      :visible="parsing"
      :parse-mode="parseMode"
      :total-count="pendingScreensCount"
      :processed-count="processedScreensCount"
      :show-cancel-button="true"
      @cancel="handleCancelParse"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import { uiPrototypeApi } from '@/api/uiPrototype'
import type { UIScreen } from '@/api/uiPrototype'
import { iterationApi } from '@/api/iteration'
import type { Iteration } from '@/api/iteration'
import { getRouteQueryParam, isUIScreenListResponse } from '@/composables/uiPrototypeHelpers'
import { useScreenImageUrl } from '@/composables/useScreenImageUrl'
import ScreenCardGrid from './components/ScreenCardGrid.vue'
import ScreenPreviewDialog from './components/ScreenPreviewDialog.vue'
import ScreenUploadDialog from './components/ScreenUploadDialog.vue'
import AIParseLoading from '@/components/loading/AIParseLoading.vue'

const router = useRouter()
const route = useRoute()
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
const screens = ref<UIScreen[]>([])
const screenImageUrls = ref<Record<number, string>>({})
const pendingScreensIds = ref<number[]>([])

const previewVisible = ref(false)
const previewScreen = ref<UIScreen | null>(null)

const uploadDialogVisible = ref(false)
const parseMode = ref<'text' | 'vision'>('text')

const pendingScreensCount = computed(() => pendingScreensIds.value.length)

const completedScreenCount = computed(() => {
  return screens.value.filter((screen) => screen.parse_status === 'completed').length
})

const failedScreenCount = computed(() => {
  return screens.value.filter((screen) => screen.parse_status === 'failed').length
})

const pendingScreenCount = computed(() => {
  return screens.value.filter(
    (screen) =>
      !screen.parse_status || screen.parse_status === 'pending' || screen.parse_status === 'running'
  ).length
})

const processedScreensCount = computed(() => {
  if (!pendingScreensIds.value.length) return 0
  return screens.value.filter(
    (s) =>
      pendingScreensIds.value.includes(s.id!) &&
      (s.parse_status === 'completed' || s.parse_status === 'failed')
  ).length
})

const goBack = () => {
  router.push('/home/requirement')
}

const loadIterationDetail = async () => {
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
      if (err?.response?.status === 404) {
        currentIteration.value = null
      } else {
        console.error('Failed to load iteration:', error)
        ElMessage.warning('迭代信息加载失败')
      }
    }
  }
}

const loadScreens = async () => {
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
  } catch (error) {
    console.error('Failed to load screens:', error)
    ElMessage.error('加载截图列表失败，请刷新重试')
    screens.value = []
  } finally {
    loading.value = false
  }
}

const handlePreviewScreen = async (screen: UIScreen) => {
  previewScreen.value = screen
  if (screen.id && !screenImageUrls.value[screen.id]) {
    const url = await getImageUrl(screen)
    if (url && screen.id) {
      screenImageUrls.value[screen.id] = url
    }
  }
  previewVisible.value = true
}

const handleParseScreen = async (screen: UIScreen) => {
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

const handleBatchParse = async () => {
  const pendingScreens = screens.value.filter(
    (s) => s.parse_status === 'pending' || s.parse_status === 'failed'
  )
  if (pendingScreens.length === 0) {
    ElMessage.info('所有图片已解析完成')
    return
  }

  try {
    pendingScreensIds.value = pendingScreens.map((s) => s.id!)
    parsing.value = true
    await uiPrototypeApi.parseUIScreens(
      pendingScreens.map((s) => s.id),
      prototypeProjectId.value,
      parseMode.value
    )
    const messageText =
      parseMode.value === 'text'
        ? `已启动 ${pendingScreens.length} 张图片的文本模型一键解析`
        : `已启动 ${pendingScreens.length} 张图片的AI视觉解析`
    ElMessage.success(messageText)
    await pollParseStatus()
  } catch (error: unknown) {
    const err = error as { response?: { data?: { detail?: string } } }
    ElMessage.error(err?.response?.data?.detail || '批量解析失败')
  } finally {
    parsing.value = false
    pendingScreensIds.value = []
  }
}

const handleCancelParse = () => {
  ElMessage.info('解析任务已取消')
  parsing.value = false
  pendingScreensIds.value = []
}

const pollParseStatus = async (maxAttempts: number = 40) => {
  const currentScreenId = previewScreen.value?.id
  for (let i = 0; i < maxAttempts && parsing.value; i++) {
    const delay = i < 5 ? 2000 : i < 15 ? 5000 : 10000
    await new Promise((resolve) => setTimeout(resolve, delay))
    await loadScreens()
    if (currentScreenId) {
      const updatedScreen = screens.value.find((s) => s.id === currentScreenId)
      if (updatedScreen) {
        previewScreen.value = updatedScreen
      }
    }
    const allDone = screens.value.every(
      (s) => s.parse_status === 'completed' || s.parse_status === 'failed'
    )
    if (allDone) {
      ElMessage.success('所有图片解析完成！')
      break
    }
  }
}

const handleDeleteScreen = async (screen: UIScreen) => {
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

const handleAddScreens = () => {
  uploadDialogVisible.value = true
}

const handleUploadSubmit = async (files: File[]) => {
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
    if (result?.total > 0) {
      ElMessage.success(`追加上传成功，共 ${result.total} 张图片`)
    }

    uploadDialogVisible.value = false
    loadScreens()
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
  loadScreens()
})

onUnmounted(() => {
  cleanupImageCache()
})
</script>

<style scoped>
.ui-prototype-container {
  padding: 20px;
  background: linear-gradient(180deg, #f7f9fc 0%, #f3f6fb 100%);
  min-height: 100%;
}

.header-card {
  margin-bottom: 16px;
  border: none;
  background: linear-gradient(135deg, #fafbfc 0%, #f5f8fc 100%);
}

.page-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.prototype-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1a1d21;
}
.header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.parse-mode-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #ffffff;
  border-radius: 10px;
  border: 1px solid #e8ecf0;
}

.parse-mode-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
  white-space: nowrap;
}
.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.vision-alert {
  border-radius: 10px;
}

.overview-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}

.overview-card {
  padding: 16px 18px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #e8ecf0;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.overview-card-primary {
  background: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
  border-color: #dbeafe;
}

.overview-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.overview-value {
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 8px;
}

.overview-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}

.content-card {
  min-height: 400px;
  border: none;
  background: #ffffff;
  border-radius: 18px;
}

.content-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f0f2f5;
}

.content-head-main {
  flex: 1;
  min-width: 0;
}

.content-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 6px;
}

.content-subtitle {
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
}

.content-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 1100px) {
  .overview-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .ui-prototype-container {
    padding: 16px;
  }

  .content-head {
    flex-direction: column;
  }

  .overview-strip {
    grid-template-columns: 1fr;
  }
}
</style>
