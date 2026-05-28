<template>
  <div class="ai-generate-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>新增用例生成</h2>
      <div class="header-actions">
        <el-button type="primary" plain @click="goToResourceManage">
          <el-icon><Upload /></el-icon>
          上传资源文件
        </el-button>
        <el-button @click="handleBack">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
      </div>
    </div>

    <!-- 步骤指示器 -->
    <el-steps :active="store.currentStep" finish-status="success" class="steps-indicator">
      <el-step title="选择项目与目标" description="确定生成范围和上下文来源" />
      <el-step title="配置生成上下文" description="检查需求、测试点、UI和页面流转质量" />
      <el-step title="生成并保存" description="生成可评审的专项测试用例" />
    </el-steps>

    <!-- 步骤1: 选择需求来源 -->
    <ContextSelectPanel
      v-if="store.currentStep === 0"
      ref="contextSelectPanelRef"
      @next="store.nextStep"
      @skip-to-step2="store.skipToStep2"
      @go-resource-manage="goToResourceManage"
      @preview-screen="handlePreviewScreen"
    />

    <!-- 步骤2+3: 配置参数 + 生成结果 -->
    <GeneratePreviewPanel @prev="store.prevStep" @generate="handleGenerate" />

    <!-- 图片预览 -->
    <el-image-viewer
      v-if="isPreviewImageVisible"
      :url-list="[previewImageUrl]"
      :initial-index="0"
      @close="isPreviewImageVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import { useFlowSortStore } from '@/store/flowSort'
import ContextSelectPanel from './ContextSelectPanel.vue'
import GeneratePreviewPanel from './GeneratePreviewPanel.vue'

const router = useRouter()
const route = useRoute()
const store = useGenerateStore()

// 图片预览
const previewImageUrl = ref('')
const isPreviewImageVisible = ref(false)

// ContextSelectPanel 引用
const contextSelectPanelRef = ref<InstanceType<typeof ContextSelectPanel> | null>(null)

/** 处理图片预览 */
const handlePreviewScreen = (url: string) => {
  previewImageUrl.value = url
  isPreviewImageVisible.value = true
}

/** 跳转到资源管理页面上传文件 */
const goToResourceManage = () => {
  router.push('/home/requirement')
}

/** 返回列表 */
const handleBack = () => {
  router.push('/home/case')
}

/** 触发生成 */
const handleGenerate = () => {
  const flowSortEditorRef = contextSelectPanelRef.value?.getFlowSortEditorRef?.() || null
  store.handleGenerate(flowSortEditorRef)
}

// 初始化
onMounted(async () => {
  const projectId = route.query.project_id
  if (projectId) {
    store.formData.project_id = Number(projectId)
    const flowSortStore = useFlowSortStore()
    flowSortStore.setProjectId(Number(projectId))
    void flowSortStore.loadFromBackend()
  }

  const fids = route.query.requirement_file_ids
  if (fids) {
    try {
      const parsed = JSON.parse(String(fids))
      if (Array.isArray(parsed)) {
        store.formData.requirement_file_ids = parsed
          .map(Number)
          .filter((n: number) => !Number.isNaN(n))
      }
    } catch {
      /* ignore */
    }
  }

  const singleFid = route.query.file_id
  if (!store.formData.requirement_file_ids.length && singleFid) {
    const id = Number(singleFid)
    if (!Number.isNaN(id) && id > 0) {
      store.formData.requirement_file_ids = [id]
    }
  }

  // 从测试点提取页面跳转时，预选测试点
  const tpIds = route.query.test_point_ids
  if (tpIds) {
    try {
      const parsed = JSON.parse(String(tpIds))
      if (Array.isArray(parsed)) {
        store.formData.test_point_ids = parsed
          .map(Number)
          .filter((n: number) => !Number.isNaN(n) && n > 0)
      }
    } catch {
      /* ignore */
    }
  }

  await store.getProjects()
  if (store.formData.project_id) {
    await store.loadProjectFiles()
    await store.loadUIPrototypeProjects()
    const uiProjectId = Number(route.query.ui_project_id || 0)
    if (uiProjectId > 0) {
      const exists = store.uiPrototypeProjects.some((project) => project.id === uiProjectId)
      if (exists) {
        await store.handleUIPrototypeProjectChange(uiProjectId)
      }
    }
    await store.loadProjectCases()
    await store.loadTestPoints(1)
    if (store.formData.test_point_ids.length > 0) {
      store.formData.test_points_data = store.testPoints.filter((tp) =>
        store.formData.test_point_ids.includes(tp.id)
      )
    }
  }
})

// 监听需求文档/UI原型图选择变化，自动加载测试点
watch(
  [() => store.formData.requirement_file_ids, () => store.formData.ui_file_ids],
  async ([newReqIds, newUiIds], [oldReqIds, oldUiIds]) => {
    const reqChanged = JSON.stringify(newReqIds || []) !== JSON.stringify(oldReqIds || [])
    const uiChanged = JSON.stringify(newUiIds || []) !== JSON.stringify(oldUiIds || [])

    if ((reqChanged || uiChanged) && store.formData.project_id) {
      store.handleSourceFileChange()
      await store.loadTestPoints(1)
    }
  },
  { deep: true }
)

onUnmounted(() => {
  store.resetGenerateState()
  store.cleanupScreenImages()
})
</script>

<style scoped>
.ai-generate-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.steps-indicator {
  margin-bottom: 30px;
}
</style>

<style src="./ai-generate.scss"></style>
