<template>
  <el-dialog
    :model-value="visible"
    :title="screen?.screen_name || '图片预览'"
    width="min(1280px, 92vw)"
    top="4vh"
    destroy-on-close
    class="ui-preview-dialog"
    @close="emit('update:visible', false)"
  >
    <div class="preview-content" v-if="screen">
      <div class="preview-overview">
        <div class="overview-main">
          <div class="overview-title-row">
            <h3 class="overview-title">{{ screen.screen_name }}</h3>
            <el-tag :type="screenStatusMeta.type" size="small" effect="plain">
              {{ screenStatusMeta.text }}
            </el-tag>
          </div>
          <div class="overview-subtitle">
            <span class="prototype-path">
              <el-icon><FolderOpened /></el-icon>
              <span>{{ screen.prototype_name || '未命名原型' }}</span>
            </span>
            <span v-if="screen.summary" class="overview-note">已生成页面摘要与结构信息</span>
          </div>
        </div>
        <div class="overview-metrics">
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.element_count || 0 }}</span>
            <span class="metric-chip-label">总元素</span>
          </div>
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.button_count || 0 }}</span>
            <span class="metric-chip-label">按钮</span>
          </div>
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.input_count || 0 }}</span>
            <span class="metric-chip-label">输入框</span>
          </div>
        </div>
      </div>

      <div class="preview-split-layout">
        <div class="preview-left">
          <div class="preview-stage">
            <div class="preview-stage-toolbar">
              <span class="preview-stage-title">屏幕截图</span>
              <span class="preview-stage-tip">可结合右侧信息与下方解析详情一起查看</span>
            </div>
            <div class="preview-image-shell">
              <img
                v-if="screen?.original_file_path && screen?.id && imageUrls[screen.id]"
                :src="imageUrls[screen.id]"
                :alt="screen.screen_name"
                class="preview-image"
              />
              <div v-else class="preview-image-placeholder">
                <el-icon :size="60"><Picture /></el-icon>
                <span>暂无图片</span>
              </div>
            </div>
          </div>
        </div>

        <div class="preview-right">
          <div class="info-section identity-section">
            <div class="section-header">
              <span class="section-title">页面标识</span>
              <el-tag type="info" size="small" effect="plain">基础信息</el-tag>
            </div>
            <div class="identity-content">
              <div class="identity-name">{{ screen.screen_name }}</div>
              <div class="prototype-path">
                <el-icon><FolderOpened /></el-icon>
                <span>{{ screen.prototype_name }}</span>
              </div>
            </div>
          </div>

          <div class="info-section stats-section">
            <div class="section-label">
              <el-icon><DataAnalysis /></el-icon>
              <span>元素统计</span>
            </div>
            <div class="stats-grid">
              <div class="stat-card stat-primary">
                <div class="stat-value">{{ screen.element_count || 0 }}</div>
                <div class="stat-label">总元素</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{{ screen.button_count || 0 }}</div>
                <div class="stat-label">按钮</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{{ screen.input_count || 0 }}</div>
                <div class="stat-label">输入框</div>
              </div>
            </div>
          </div>

          <div class="info-section ai-section" v-if="screen.summary">
            <div class="section-label">
              <el-icon><Memo /></el-icon>
              <span>AI摘要</span>
            </div>
            <div class="ai-summary-content">{{ screen.summary }}</div>
          </div>

          <div class="unparsed-tip" v-else-if="screenStatusMeta.isFailed">
            <el-icon><WarningFilled /></el-icon>
            <span>解析失败：{{ screen.parse_error || '未知错误' }}</span>
          </div>
          <div class="unparsed-tip" v-else-if="!screenStatusMeta.canShowDetails">
            <el-icon><WarningFilled /></el-icon>
            <span>请先解析以查看详情</span>
          </div>
        </div>
      </div>

      <div class="detail-panel" v-if="screenStatusMeta.canShowDetails && hasDetailData">
        <div class="detail-panel-header">
          <div class="detail-panel-title">解析详情</div>
          <div class="detail-panel-desc">包含元素、页面跳转、布局约束与视觉风格信息</div>
        </div>
        <el-collapse v-model="activeNames" class="preview-collapse">
          <ElementDetailPanel
            v-if="screen.ui_spec?.elements?.length"
            :elements="screen.ui_spec.elements"
          />
          <FlowLayoutPanel
            :flows="screen.ui_spec?.flows"
            :navigation="screen.navigation_flow?.navigation"
            :layout-constraints="screen.ui_spec?.layout_constraints"
            :visual-style="screen.ui_spec?.visual_style"
            :warnings="screen.ui_spec?.warnings"
          />
        </el-collapse>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Picture, Memo, WarningFilled, DataAnalysis, FolderOpened } from '@element-plus/icons-vue'
import type { UIScreen } from '@/api/uiPrototype'
import { getUIScreenStatusMeta } from '@/composables/uiScreenStatus'
import ElementDetailPanel from './ElementDetailPanel.vue'
import FlowLayoutPanel from './FlowLayoutPanel.vue'

const props = defineProps<{
  visible: boolean
  screen: UIScreen | null
  imageUrls: Record<number, string>
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const activeNames = ref<string[]>(['elements'])

const screenStatusMeta = computed(() => getUIScreenStatusMeta(props.screen))

const hasDetailData = computed(() => {
  if (!props.screen?.ui_spec) return false
  const spec = props.screen.ui_spec
  return !!(
    spec.elements?.length ||
    spec.flows?.length ||
    spec.layout_constraints?.length ||
    spec.visual_style ||
    spec.warnings?.length
  )
})
</script>

<style scoped>
.ui-preview-dialog :deep(.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
}

.ui-preview-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 20px 24px 12px;
  border-bottom: 1px solid #f0f2f5;
}

.ui-preview-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 24px;
  max-height: calc(100vh - 110px);
  overflow-y: auto;
  background: linear-gradient(180deg, #fcfdff 0%, #f7f9fc 100%);
}

.preview-content {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-overview {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fbff 100%);
  border: 1px solid #e6eef8;
}

.overview-main {
  flex: 1;
  min-width: 0;
}

.overview-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.overview-title {
  margin: 0;
  font-size: 20px;
  line-height: 1.4;
  font-weight: 600;
  color: #1f2937;
}

.overview-subtitle {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.overview-note {
  font-size: 12px;
  color: #409eff;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.08);
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(86px, 1fr));
  gap: 10px;
  min-width: 300px;
}

.metric-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 10px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #edf2f7;
}

.metric-chip-value {
  font-size: 20px;
  font-weight: 700;
  color: #2563eb;
  line-height: 1;
}

.metric-chip-label {
  font-size: 12px;
  color: #6b7280;
}

.preview-split-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 420px);
  gap: 24px;
}

.preview-left {
  min-width: 0;
}

.preview-stage {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  height: 100%;
  min-height: 460px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid #e8ecf0;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

.preview-stage-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.preview-stage-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.preview-stage-tip {
  font-size: 12px;
  color: #909399;
}

.preview-image-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: linear-gradient(145deg, #f8f9fb 0%, #e8ecf0 100%);
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid #eef2f6;
}

.preview-left .preview-image {
  max-width: 100%;
  max-height: min(68vh, 760px);
  object-fit: contain;
  border-radius: 10px;
}

.preview-left .preview-image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #a0a8b4;
}

.preview-right {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-section {
  background: #ffffff;
  border-radius: 16px;
  padding: 18px 20px;
  border: 1px solid #f0f2f5;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
}

.identity-section {
  background: linear-gradient(145deg, #ffffff 0%, #f8f9fb 100%);
  border-color: #e8ecf0;
}
.identity-section .section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.identity-section .section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a1d21;
  line-height: 1.4;
}
.identity-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.identity-name {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  line-height: 1.5;
  word-break: break-word;
}

.prototype-path {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6b7280;
  font-size: 14px;
  flex-wrap: wrap;
}
.prototype-path .el-icon {
  color: #9ca3af;
}
.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  margin-bottom: 16px;
}
.section-label .el-icon {
  color: #409eff;
  font-size: 15px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 12px;
  background: #f9fafb;
  border-radius: 12px;
  border: 1px solid #f0f2f5;
  transition: all 0.25s ease;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.12);
}
.stat-card.stat-primary {
  background: linear-gradient(145deg, #eff6ff 0%, #e0f2fe 100%);
  border-color: #bfdbfe;
}
.stat-card.stat-primary .stat-value {
  color: #2563eb;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #409eff;
  line-height: 1;
  margin-bottom: 8px;
}
.stat-label {
  font-size: 12px;
  color: #9ca3af;
  font-weight: 500;
}
.type-tags {
  display: flex;
  gap: 10px;
}
.type-tags .el-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
}
.ai-section {
  background: linear-gradient(145deg, #f8faff 0%, #f0f4ff 100%);
  border-color: #d9e8ff;
}
.ai-section .section-label {
  color: #3b82f6;
}
.ai-section .section-label .el-icon {
  color: #3b82f6;
}
.ai-summary-content {
  font-size: 14px;
  color: #374151;
  line-height: 1.9;
  word-break: break-word;
}
.unparsed-tip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px 18px;
  color: #b45309;
  background: linear-gradient(145deg, #fffbeb 0%, #fef3c7 100%);
  border-radius: 14px;
  border: 1px solid #fcd34d;
  font-size: 14px;
  line-height: 1.6;
}

.detail-panel {
  padding: 18px 20px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid #ebeef5;
}

.detail-panel-header {
  margin-bottom: 14px;
}

.detail-panel-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.detail-panel-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}

.preview-collapse {
  border-top: 1px solid #f0f2f5;
  padding-top: 16px;
}

.preview-collapse :deep(.el-collapse-item__header) {
  min-height: 52px;
  font-weight: 600;
}

.preview-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: 1px solid #f0f2f5;
}

@media (max-width: 1080px) {
  .preview-overview,
  .preview-split-layout {
    grid-template-columns: 1fr;
    display: flex;
    flex-direction: column;
  }

  .overview-metrics {
    min-width: 0;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .ui-preview-dialog :deep(.el-dialog__header) {
    padding: 16px 16px 10px;
  }

  .ui-preview-dialog :deep(.el-dialog__body) {
    padding: 16px;
    max-height: calc(100vh - 80px);
  }

  .preview-overview,
  .preview-stage,
  .detail-panel,
  .info-section {
    padding: 14px;
    border-radius: 14px;
  }

  .preview-stage {
    min-height: 360px;
  }

  .stats-grid,
  .overview-metrics {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 520px) {
  .stats-grid,
  .overview-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
