<template>
  <el-dialog
    :model-value="visible"
    :title="screen?.screen_name || '图片预览'"
    width="1200px"
    destroy-on-close
    class="ui-preview-dialog"
    @close="emit('update:visible', false)"
  >
    <div class="preview-content" v-if="screen">
      <div class="preview-split-layout">
        <div class="preview-left">
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

        <div class="preview-right">
          <div class="info-section identity-section">
            <div class="section-header">
              <span class="section-title">{{ screen.screen_name }}</span>
              <el-tag :type="getParseStatusType(screen.parse_status)" size="small">
                {{ screen.parse_status_text || getParseStatusText(screen.parse_status) }}
              </el-tag>
            </div>
            <div class="prototype-path">
              <el-icon><FolderOpened /></el-icon>
              <span>{{ screen.prototype_name }}</span>
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

          <div class="unparsed-tip" v-else-if="screen.parse_status === 'failed'">
            <el-icon><WarningFilled /></el-icon>
            <span>解析失败：{{ screen.parse_error || '未知错误' }}</span>
          </div>
          <div class="unparsed-tip" v-else-if="screen.parse_status !== 'completed'">
            <el-icon><WarningFilled /></el-icon>
            <span>请先解析以查看详情</span>
          </div>
        </div>
      </div>

      <el-collapse v-model="activeNames" class="preview-collapse" v-if="screen.parse_status === 'completed' && hasDetailData">
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
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Picture, Memo, WarningFilled, DataAnalysis, FolderOpened
} from '@element-plus/icons-vue'
import type { UIScreen } from '@/api/uiPrototype'
import { getParseStatusType, getParseStatusText } from '@/composables/useParseStatus'
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

const hasDetailData = computed(() => {
  if (!props.screen?.ui_spec) return false
  const spec = props.screen.ui_spec
  return !!(spec.elements?.length || spec.flows?.length || spec.layout_constraints?.length || spec.visual_style || spec.warnings?.length)
})
</script>

<style scoped>
.preview-content { text-align: left; }
.preview-split-layout { display: flex; gap: 32px; margin-bottom: 24px; }
.preview-left {
  flex: 1.2; min-width: 0; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(145deg, #f8f9fb 0%, #e8ecf0 100%); border-radius: 16px;
  min-height: 420px; max-height: 560px; overflow: hidden; border: 1px solid #e8ecf0;
}
.preview-left .preview-image { max-width: 100%; max-height: 560px; object-fit: contain; }
.preview-left .preview-image-placeholder { display: flex; flex-direction: column; align-items: center; gap: 16px; color: #a0a8b4; }
.preview-right { flex: 0.8; min-width: 300px; max-width: 380px; display: flex; flex-direction: column; gap: 20px; }
.info-section { background: #ffffff; border-radius: 14px; padding: 20px 24px; border: 1px solid #f0f2f5; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02); }
.identity-section { background: linear-gradient(145deg, #ffffff 0%, #f8f9fb 100%); border-color: #e8ecf0; }
.identity-section .section-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.identity-section .section-title { font-size: 18px; font-weight: 600; color: #1a1d21; line-height: 1.4; }
.prototype-path { display: flex; align-items: center; gap: 8px; color: #6b7280; font-size: 14px; }
.prototype-path .el-icon { color: #9ca3af; }
.section-label { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 500; color: #6b7280; margin-bottom: 16px; }
.section-label .el-icon { color: #409eff; font-size: 15px; }
.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.stat-card { display: flex; flex-direction: column; align-items: center; padding: 18px 12px; background: #f9fafb; border-radius: 12px; border: 1px solid #f0f2f5; transition: all 0.25s ease; }
.stat-card:hover { transform: translateY(-3px); box-shadow: 0 6px 16px rgba(64, 158, 255, 0.12); }
.stat-card.stat-primary { background: linear-gradient(145deg, #eff6ff 0%, #e0f2fe 100%); border-color: #bfdbfe; }
.stat-card.stat-primary .stat-value { color: #2563eb; }
.stat-value { font-size: 28px; font-weight: 700; color: #409eff; line-height: 1; margin-bottom: 8px; }
.stat-label { font-size: 12px; color: #9ca3af; font-weight: 500; }
.type-tags { display: flex; gap: 10px; }
.type-tags .el-tag { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 8px; font-size: 14px; }
.ai-section { background: linear-gradient(145deg, #f8faff 0%, #f0f4ff 100%); border-color: #d9e8ff; }
.ai-section .section-label { color: #3b82f6; }
.ai-section .section-label .el-icon { color: #3b82f6; }
.ai-summary-content { font-size: 14px; color: #374151; line-height: 1.9; word-break: break-word; }
.unparsed-tip { display: flex; align-items: center; justify-content: center; gap: 10px; padding: 28px; color: #b45309; background: linear-gradient(145deg, #fffbeb 0%, #fef3c7 100%); border-radius: 12px; border: 1px solid #fcd34d; font-size: 14px; }
.preview-collapse { border-top: 1px solid #f0f2f5; padding-top: 20px; }
</style>
