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
            <el-tag :type="screenStatusMeta.type" size="small" effect="plain">{{
              screenStatusMeta.text
            }}</el-tag>
          </div>
          <div class="overview-subtitle">
            <span class="prototype-path"
              ><el-icon><FolderOpened /></el-icon
              ><span>{{ screen.prototype_name || '未命名原型' }}</span></span
            ><span v-if="screen.summary" class="overview-note">已生成页面摘要与结构信息</span>
          </div>
        </div>
        <div class="overview-metrics">
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.element_count || 0 }}</span
            ><span class="metric-chip-label">总元素</span>
          </div>
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.button_count || 0 }}</span
            ><span class="metric-chip-label">按钮</span>
          </div>
          <div class="metric-chip">
            <span class="metric-chip-value">{{ screen.input_count || 0 }}</span
            ><span class="metric-chip-label">输入框</span>
          </div>
        </div>
      </div>
      <div class="preview-split-layout">
        <div class="preview-left">
          <div class="preview-stage">
            <div class="preview-stage-toolbar">
              <span class="preview-stage-title">屏幕截图</span
              ><span class="preview-stage-tip">可结合右侧信息与下方解析详情一起查看</span>
            </div>
            <div class="preview-image-shell">
              <img
                v-if="screen?.original_file_path && screen?.id && imageUrls[screen.id]"
                :src="imageUrls[screen.id]"
                :alt="screen.screen_name"
                class="preview-image"
              />
              <div v-else class="preview-image-placeholder">
                <el-icon :size="60"><Picture /></el-icon><span>暂无图片</span>
              </div>
            </div>
          </div>
        </div>
        <div class="preview-right">
          <div class="info-section identity-section">
            <div class="section-header">
              <span class="section-title">页面标识</span
              ><el-tag type="info" size="small" effect="plain">基础信息</el-tag>
            </div>
            <div class="identity-content">
              <div class="identity-name">{{ screen.screen_name }}</div>
              <div class="prototype-path">
                <el-icon><FolderOpened /></el-icon><span>{{ screen.prototype_name }}</span>
              </div>
            </div>
          </div>
          <div class="info-section stats-section">
            <div class="section-label">
              <el-icon><DataAnalysis /></el-icon><span>元素统计</span>
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
              <el-icon><Memo /></el-icon><span>AI摘要</span>
            </div>
            <div class="ai-summary-content">{{ screen.summary }}</div>
          </div>
          <div class="unparsed-tip" v-else-if="screenStatusMeta.isFailed">
            <el-icon><WarningFilled /></el-icon
            ><span>解析失败：{{ screen.parse_error || '未知错误' }}</span>
          </div>
          <div class="unparsed-tip" v-else-if="!screenStatusMeta.canShowDetails">
            <el-icon><WarningFilled /></el-icon><span>请先解析以查看详情</span>
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
const emit = defineEmits<{ 'update:visible': [value: boolean] }>()
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

<style scoped lang="scss">
@use './ScreenPreviewDialog.scss';
</style>
