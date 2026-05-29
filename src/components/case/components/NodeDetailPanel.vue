<template>
  <transition name="panel-slide">
    <div v-if="visible && nodeData" class="node-detail-panel">
      <div class="panel-header">
        <span class="panel-title">节点详情</span>
        <el-button size="small" text @click="handleClose"
          ><el-icon :size="16"><Close /></el-icon
        ></el-button>
      </div>
      <div class="panel-body">
        <div class="detail-image" @click="handlePreview">
          <div v-if="imageLoading && !imageLoadError && nodeData.image_url" class="image-skeleton">
            <el-icon class="loading-icon"><Loading /></el-icon>
          </div>
          <img
            v-show="!imageLoading && !imageLoadError && nodeData.image_url"
            :src="nodeData.image_url"
            :alt="nodeData.screen_name"
            class="detail-image-img"
            :class="{ 'img-loaded': imageLoaded }"
            @load="handleImageLoad"
            @error="handleImageError"
          />
          <div v-if="!nodeData.image_url || imageLoadError" class="image-placeholder">
            <el-icon :size="40"><Picture /></el-icon>
            <span class="placeholder-text">{{ imageLoadError ? '加载失败' : '暂无图片' }}</span>
          </div>
          <div v-if="nodeData.image_url && !imageLoadError" class="image-preview-hint">
            <el-icon :size="14"><View /></el-icon>
            <span>点击预览大图</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-name" :title="nodeData.screen_name">{{ nodeData.screen_name }}</div>
          <div class="detail-type-row">
            <span class="detail-flow-type" :class="`detail-flow-type--${nodeData.flow_type}`">
              {{ flowTypeLabel }}
            </span>
            <span
              v-if="nodeData.flow_type === 'main' && nodeData.main_order"
              class="detail-main-order"
            >
              主干第 {{ nodeData.main_order }} 步
            </span>
          </div>
        </div>

        <div v-if="nodeData.summary" class="detail-section">
          <div class="section-label">页面摘要</div>
          <div class="detail-summary">{{ nodeData.summary }}</div>
        </div>

        <div class="detail-section">
          <div class="section-label">元素统计</div>
          <div class="detail-stats">
            <span class="stat-item">
              <el-icon><Grid /></el-icon>
              {{ nodeData.element_count ?? 0 }} 个元素
            </span>
          </div>
        </div>

        <div v-if="upstreamPages.length > 0" class="detail-section">
          <div class="section-label">上游页面</div>
          <div class="detail-page-list">
            <div
              v-for="page in upstreamPages"
              :key="page.id"
              class="page-list-item"
              @click="handleLocateNode(page.id)"
            >
              <el-tag :type="tagMap[page.flow_type] || 'primary'" size="small" effect="plain">
                {{ labelMap[page.flow_type] || '主干' }}
              </el-tag>
              <span class="page-name" :title="page.screen_name">{{ page.screen_name }}</span>
            </div>
          </div>
        </div>

        <div v-if="downstreamPages.length > 0" class="detail-section">
          <div class="section-label">下游页面</div>
          <div class="detail-page-list">
            <div
              v-for="page in downstreamPages"
              :key="page.id"
              class="page-list-item"
              @click="handleLocateNode(page.id)"
            >
              <el-tag :type="tagMap[page.flow_type] || 'primary'" size="small" effect="plain">
                {{ labelMap[page.flow_type] || '主干' }}
              </el-tag>
              <span class="page-name" :title="page.screen_name">{{ page.screen_name }}</span>
            </div>
          </div>
        </div>

        <div v-if="displayMode === 'edit'" class="detail-section detail-actions">
          <div class="section-label">流程类型</div>
          <el-button-group class="type-action-group">
            <el-button
              size="small"
              :type="nodeData.flow_type === 'main' ? 'primary' : ''"
              @click="handleFlowTypeChange('main')"
              >主干</el-button
            >
            <el-button
              size="small"
              :type="nodeData.flow_type === 'branch' ? 'success' : ''"
              @click="handleFlowTypeChange('branch')"
              >分支</el-button
            >
            <el-button
              size="small"
              :type="nodeData.flow_type === 'exception' ? 'danger' : ''"
              @click="handleFlowTypeChange('exception')"
              >异常</el-button
            >
            <el-button
              size="small"
              :type="nodeData.flow_type === 'bypass' ? 'warning' : ''"
              @click="handleFlowTypeChange('bypass')"
              title="自动出现，关闭后继续主流程"
              >弹窗</el-button
            >
          </el-button-group>
          <div v-if="nodeData.flow_type === 'bypass'" class="type-help-text">
            自动出现，关闭后继续主流程
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElIcon } from 'element-plus'
import {
  Close,
  Picture,
  View,
  Grid,
  Loading,
} from '@element-plus/icons-vue'
import type { TagType } from '@/types/element-plus'
import { useFlowSortEditor } from '@/composables/flowSort/useFlowSortEditor'
import type { FlowEditorNode, FlowGraphEdge } from '@/composables/useFlowEditor'

interface DetailNodeData {
  id: string
  screen_id: number
  screen_name: string
  summary?: string
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  main_order?: number
  image_url?: string
  element_count?: number
}

const props = defineProps<{
  visible: boolean
  nodeData: DetailNodeData | null
  displayMode: 'overview' | 'edit'
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  'flow-type-change': [type: string]
  'locate-node': [nodeId: string]
  preview: []
}>()

const ctx = useFlowSortEditor()

const flowTypeConfig: Record<string, { label: string }> = {
  main: { label: '主干' },
  branch: { label: '分支' },
  exception: { label: '异常' },
  bypass: { label: '弹窗' },
}

const imageLoading = ref(true)
const imageLoaded = ref(false)
const imageLoadError = ref(false)

watch(
  () => props.nodeData?.image_url,
  (newUrl) => {
    if (newUrl) {
      imageLoading.value = true
      imageLoaded.value = false
      imageLoadError.value = false
    }
  }
)

const handleImageLoad = () => {
  imageLoading.value = false
  imageLoaded.value = true
}
const handleImageError = () => {
  imageLoading.value = false
  imageLoadError.value = true
}

const flowTypeLabel = computed(
  () => flowTypeConfig[props.nodeData?.flow_type || 'main']?.label || '主干'
)
const tagMap = computed(() => ctx.FLOW_TYPE_TAG_MAP as Record<string, TagType>)
const labelMap = computed(() => ctx.FLOW_TYPE_LABEL_MAP as Record<string, string>)

const upstreamPages = computed(() => {
  if (!props.nodeData) return []
  const nodeId = props.nodeData.id
  return (ctx.vueFlowEdges.value as FlowGraphEdge[])
    .filter((e) => e.target === nodeId && !e.hidden)
    .map((e) => {
      const sourceNode = (ctx.vueFlowNodes.value as FlowEditorNode[]).find((n) => n.id === e.source)
      if (!sourceNode) return null
      return {
        id: sourceNode.id,
        screen_name: sourceNode.data.screen_name,
        flow_type: sourceNode.data.flow_type,
      }
    })
    .filter(Boolean) as Array<{ id: string; screen_name: string; flow_type: string }>
})

const downstreamPages = computed(() => {
  if (!props.nodeData) return []
  const nodeId = props.nodeData.id
  return (ctx.vueFlowEdges.value as FlowGraphEdge[])
    .filter((e) => e.source === nodeId && !e.hidden)
    .map((e) => {
      const targetNode = (ctx.vueFlowNodes.value as FlowEditorNode[]).find((n) => n.id === e.target)
      if (!targetNode) return null
      return {
        id: targetNode.id,
        screen_name: targetNode.data.screen_name,
        flow_type: targetNode.data.flow_type,
      }
    })
    .filter(Boolean) as Array<{ id: string; screen_name: string; flow_type: string }>
})

const handleClose = () => {
  emit('update:visible', false)
}
const handleFlowTypeChange = (type: string) => {
  emit('flow-type-change', type)
}
const handleLocateNode = (nodeId: string) => {
  emit('locate-node', nodeId)
}
const handlePreview = () => {
  emit('preview')
}
</script>

<style scoped lang="scss">
.node-detail-panel {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border-left: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: -2px 0 12px rgba(0, 0, 0, 0.04);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);

  .panel-title {
    font-size: 13px;
    font-weight: 600;
    color: #303133;
  }
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
}

.detail-image {
  position: relative;
  height: 160px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;

  .detail-image-img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    transition: opacity 0.3s ease;
    opacity: 0;
    &.img-loaded {
      opacity: 1;
    }
  }

  .image-skeleton {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(90deg, #f5f7fa 25%, #e4e7ed 50%, #f5f7fa 75%);
    background-size: 200% 100%;
    animation: skeleton-loading 1.5s infinite;
    .loading-icon {
      font-size: 24px;
      color: #c0c4cc;
      animation: spin 1s linear infinite;
    }
  }

  .image-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    color: #c0c4cc;
    .placeholder-text {
      font-size: 12px;
    }
  }

  .image-preview-hint {
    position: absolute;
    bottom: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    border-radius: 6px;
    background: rgba(0, 0, 0, 0.5);
    color: #fff;
    font-size: 11px;
    opacity: 0;
    transition: opacity 0.2s ease;
  }

  &:hover .image-preview-hint {
    opacity: 1;
  }
}

.detail-section {
  margin-bottom: 12px;
}

.detail-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-type-row {
  display: flex;
  align-items: center;
  gap: 8px;

  .detail-flow-type {
    min-width: 44px;
    height: 24px;
    padding: 0 12px;
    border-radius: 12px;
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    line-height: 24px;
    text-align: center;
    white-space: nowrap;
  }

  .detail-flow-type--main {
    background: #409eff;
  }

  .detail-flow-type--branch {
    background: #67c23a;
  }

  .detail-flow-type--exception {
    background: #f56c6c;
  }

  .detail-flow-type--bypass {
    background: #e6a23c;
  }

  .detail-main-order {
    font-size: 12px;
    color: #409eff;
    font-weight: 500;
  }
}

.section-label {
  font-size: 11px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-summary {
  font-size: 12px;
  color: #606266;
  line-height: 1.6;
  background: #f5f7fa;
  padding: 8px 10px;
  border-radius: 6px;
}

.detail-stats {
  display: flex;
  gap: 12px;

  .stat-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #606266;
  }
}

.type-help-text {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #909399;
}

.detail-page-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-list-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;

  &:hover {
    background: #f5f7fa;
  }

  .page-name {
    font-size: 12px;
    color: #303133;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }
}

.detail-actions {
  .type-action-group {
    width: 100%;
    display: flex;

    :deep(.el-button) {
      flex: 1;
      font-size: 12px;
    }
  }
}

@keyframes skeleton-loading {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.panel-slide-enter-active {
  transition: all 0.25s ease;
}
.panel-slide-leave-active {
  transition: all 0.2s ease;
}
.panel-slide-enter-from {
  transform: translateX(100%);
  opacity: 0;
}
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
