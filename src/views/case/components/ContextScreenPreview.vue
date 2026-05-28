<template>
  <el-form-item
    label="屏幕预览"
    v-if="store.selectedUiPrototypeProjectId"
    class="screen-preview-form-item"
  >
    <el-alert
      v-if="
        store.selectedUiPrototypeProject &&
        store.selectedUiPrototypeProject.parse_status !== 'completed' &&
        store.showParseWarning
      "
      :title="
        store.selectedUiPrototypeProject.parse_status === 'partial'
          ? `该UI原型图部分解析（${store.selectedUiPrototypeProject.parsed_count}/${store.selectedUiPrototypeProject.screen_count}），未解析的屏幕将无法获取详细元素信息`
          : '该UI原型图尚未解析，将无法获取详细的按钮、输入框等元素信息，建议先在资源管理中进行解析'
      "
      type="warning"
      show-icon
      closable
      style="margin-bottom: 16px"
      @close="store.showParseWarning = false"
    />
    <div v-if="store.uiScreens.length > 0" class="screen-preview-wrapper">
      <div class="screen-preview-overview">
        <div class="preview-overview-main">
          <div class="preview-overview-title">
            <span class="preview-overview-name">{{
              store.selectedUiPrototypeProject?.name || '当前UI版本'
            }}</span>
            <el-tag size="small" type="info" effect="plain"
              >共 {{ store.uiScreens.length }} 个屏幕</el-tag
            >
            <el-tag size="small" :type="store.screenPreviewStatusType" effect="plain">{{
              store.screenPreviewStatusText
            }}</el-tag>
          </div>
          <div class="preview-overview-desc">
            点击缩略图可查看大图；拖拽节点可调整页面顺序，连线可补充页面流转关系。
          </div>
        </div>
        <div class="preview-overview-tips">
          <div class="preview-tip-item">
            <el-icon><View /></el-icon><span>点击预览</span>
          </div>
          <div class="preview-tip-item">
            <el-icon><Rank /></el-icon><span>拖拽调整顺序</span>
          </div>
        </div>
      </div>
      <FlowSortEditor
        ref="flowSortEditorRef"
        class="screen-sort-editor"
        :screens="store.uiScreens"
        :screen-image-urls="store.screenImageUrls"
        :module-info="store.flowSortModuleInfo"
        @update:sort-data="store.handleFlowSortUpdate"
        @preview-screen="handleFlowNodePreview"
        @test-point-link="handleTestPointLink"
      />
    </div>
    <div v-else class="ui-screens-empty"><el-empty description="该版本暂无屏幕" /></div>
  </el-form-item>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Rank, View } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import FlowSortEditor from '@/components/case/FlowSortEditor.vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import { useTestPointLink } from '@/composables/useTestPointLink'

type FlowSortValidationResult = { errors: string[]; warnings: string[] }
type FlowSortEditorExpose = InstanceType<typeof FlowSortEditor> & {
  getFlowSortSubmitData?: () => { flow_sort_data: Record<string, unknown> }
  getFlowValidationIssues?: () => FlowSortValidationResult
}

const emit = defineEmits<{ 'preview-screen': [url: string]; 'test-point-link': [ids: number[]] }>()
const store = useGenerateStore()
const { matchScreenName } = useTestPointLink()
const flowSortEditorRef = ref<InstanceType<typeof FlowSortEditor> | null>(null)

function getFlowSortEditorRef(): FlowSortEditorExpose | null {
  return flowSortEditorRef.value as FlowSortEditorExpose | null
}

const handleFlowNodePreview = async (screenData: {
  screen_id: number
  screen_name: string
  image_url?: string
}) => {
  const screen = store.uiScreens.find((s) => s.id === screenData.screen_id)
  const imageUrl = screen ? store.screenImageUrls[screen.id] : screenData.image_url
  if (imageUrl) {
    emit('preview-screen', imageUrl)
    return
  }
  if (screen?.original_file_path) {
    await store.loadScreenImages()
    const reloadedUrl = store.screenImageUrls[screen.id]
    if (reloadedUrl) {
      emit('preview-screen', reloadedUrl)
      return
    }
  }
  ElMessage.warning('该屏幕暂无可预览图片')
}

const handleTestPointLink = (screenIds: number[]) => {
  if (!screenIds.length || !store.testPoints.length) {
    emit('test-point-link', [])
    return
  }
  const screenNames = store.uiScreens
    .filter((s) => screenIds.includes(s.id))
    .map((s) => s.screen_name || '')
    .filter(Boolean)
  if (!screenNames.length) {
    emit('test-point-link', [])
    return
  }
  const results: number[] = []
  for (const tp of store.testPoints) {
    for (const name of screenNames) {
      if (matchScreenName(tp, name) && !results.includes(tp.id)) {
        results.push(tp.id)
        break
      }
    }
  }
  emit('test-point-link', results)
}

defineExpose({ getFlowSortEditorRef })
</script>

<style scoped>
.screen-preview-form-item :deep(.el-form-item__content) {
  width: 100%;
  min-height: 0;
  display: block;
}
.screen-preview-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
  border: 1px solid #ebeef5;
  box-sizing: border-box;
}
.screen-preview-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 4px;
}
.preview-overview-main {
  flex: 1;
  min-width: 0;
}
.preview-overview-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.preview-overview-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.preview-overview-desc {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}
.preview-overview-tips {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.preview-tip-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e4e7ed;
  color: #606266;
  font-size: 12px;
  white-space: nowrap;
}
.screen-sort-editor {
  min-height: clamp(460px, 62vh, 760px);
}
.ui-screens-empty {
  width: 100%;
  padding: 40px 0;
  border: 1px dashed #dcdfe6;
  border-radius: 12px;
  background: #fafbfc;
}
@media (max-width: 1200px) {
  .screen-preview-overview {
    flex-direction: column;
  }
  .preview-overview-tips {
    justify-content: flex-start;
  }
}
@media (max-width: 768px) {
  .screen-preview-wrapper {
    padding: 12px;
    border-radius: 12px;
  }
  .screen-sort-editor {
    min-height: 420px;
  }
}
</style>
