<template>
  <div class="ai-generate-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>AI生成测试用例</h2>
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
      <el-step title="选择需求来源" description="关联需求文档和UI原型" />
      <el-step title="配置测试参数" description="选择用例类型和测试点" />
      <el-step title="生成并保存" description="AI生成详细测试用例" />
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

    if (store.formData.requirement_file_ids.length > 0) {
      await store.loadTestPoints(1)
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
      if ((newReqIds && newReqIds.length > 0) || (newUiIds && newUiIds.length > 0)) {
        await store.loadTestPoints(1)
      }
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

<!-- 下拉框全局样式（测试点选择器） -->
<style>
.tp-dropdown {
  border-radius: 8px !important;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.1) !important;
  border: 1px solid #dcdfe6 !important;
}

.tp-d-header {
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
}

.tp-d-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  margin-bottom: 10px;
  transition: all 0.2s;
}

.tp-d-search:focus-within {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.tp-d-search input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  width: 100%;
  color: #606266;
}

.tp-d-search input::placeholder {
  color: #c0c4cc;
}

.tp-d-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #909399;
}

/* 选项 */
.tp-dropdown .el-select-dropdown__item {
  padding: 0 !important;
  height: auto !important;
  line-height: normal !important;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.15s;
}

.tp-dropdown .el-select-dropdown__item:last-child {
  border-bottom: none;
}

.tp-dropdown .el-select-dropdown__item.is-hovering,
.tp-dropdown .el-select-dropdown__item:hover {
  background-color: #f5faff !important;
}

.tp-dropdown .el-select-dropdown__item.is-checked {
  background-color: #ecf5ff !important;
}

.tp-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
}

.tp-check input[type='checkbox'] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #409eff;
  flex-shrink: 0;
}

.tp-content {
  flex: 1;
  min-width: 0;
}

.tp-row1 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.tp-mod {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.tp-sep {
  color: #c0c4cc;
  font-size: 11px;
}

.tp-func {
  font-size: 13px;
  font-weight: 500;
  color: #409eff;
}

.tp-pri {
  margin-left: auto;
  flex-shrink: 0;
}

.tp-row2 {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 420px;
}

/* 底部分页 */
.tp-d-footer {
  padding: 10px 16px;
  text-align: center;
  border-top: 1px solid #ebeef5;
  background: #fafafa;
}

.tp-d-footer .el-pagination {
  justify-content: center;
}

.tp-d-footer .el-pagination .el-pager li {
  min-width: 28px;
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  border-radius: 4px;
  margin: 0 2px;
}

.tp-d-footer .el-pagination .el-pager li.is-active {
  background: #409eff;
  color: #fff;
}

.tp-d-footer .el-pagination .btn-prev,
.tp-d-footer .el-pagination .btn-next {
  min-width: 28px;
  height: 28px;
  border-radius: 4px;
}

/* 空状态 */
.tp-empty {
  padding: 32px 20px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
