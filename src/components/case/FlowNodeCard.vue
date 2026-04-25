<template>
  <div
    class="flow-node-card"
    :class="[
      `flow-type-${data.flow_type}`,
      { 'is-selected': isSelected, 'is-dragging': isDragging },
    ]"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <div class="node-header">
      <el-dropdown trigger="click" @command="handleFlowTypeChange">
        <el-tag
          :type="flowTypeTagType"
          size="small"
          effect="dark"
          class="flow-type-tag"
          :class="{ 'tag-animated': isHovered }"
        >
          <el-icon v-if="flowTypeIcon" class="tag-icon"><component :is="flowTypeIcon" /></el-icon>
          {{ flowTypeLabel }}
        </el-tag>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="main">
              <el-icon><Guide /></el-icon>主干流程
            </el-dropdown-item>
            <el-dropdown-item command="branch">
              <el-icon><Connection /></el-icon>分支流程
            </el-dropdown-item>
            <el-dropdown-item command="exception">
              <el-icon><Warning /></el-icon>异常流程
            </el-dropdown-item>
            <el-dropdown-item command="bypass">
              <el-icon><More /></el-icon>旁路流程
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <div class="element-badges">
        <span v-if="data.element_count" class="badge badge-elements" title="元素数量">
          <el-icon><Grid /></el-icon>{{ data.element_count }}
        </span>
      </div>
    </div>

    <div class="node-image" @click="handlePreview">
      <div v-if="imageLoading && !imageLoadError && data.image_url" class="image-skeleton">
        <el-icon class="loading-icon"><Loading /></el-icon>
      </div>
      <img
        v-show="!imageLoading && !imageLoadError && data.image_url"
        :src="data.image_url"
        :alt="data.screen_name"
        class="node-image-img"
        :class="{ 'img-loaded': imageLoaded }"
        @load="handleImageLoad"
        @error="handleImageError"
      />
      <div v-if="!data.image_url || imageLoadError" class="image-placeholder">
        <el-icon :size="36"><Picture /></el-icon>
        <span class="placeholder-text">{{ imageLoadError ? '加载失败' : '暂无图片' }}</span>
      </div>
      <transition name="fade">
        <div v-if="!imageLoadError && data.image_url" class="image-overlay">
          <el-icon :size="28"><View /></el-icon>
          <span>点击预览</span>
        </div>
      </transition>
    </div>

    <div class="node-footer">
      <div class="screen-name" :title="data.screen_name">{{ data.screen_name }}</div>
      <el-tooltip v-if="data.summary" :content="data.summary" placement="top" :show-after="500">
        <div class="screen-summary">{{ data.summary }}</div>
      </el-tooltip>
    </div>

    <Handle type="source" :position="Position.Right" />
    <Handle type="target" :position="Position.Left" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { ElIcon } from 'element-plus'
import {
  Picture,
  View,
  Guide,
  Connection,
  Warning,
  More,
  Grid,
  Loading,
} from '@element-plus/icons-vue'

interface FlowNodeCardData {
  screen_id: number
  screen_name: string
  summary?: string
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  image_url?: string
  element_count?: number
}

const flowTypeConfig: Record<string, { label: string; icon: typeof Guide; color: string }> = {
  main: { label: '主干', icon: Guide, color: '#409eff' },
  branch: { label: '分支', icon: Connection, color: '#67c23a' },
  exception: { label: '异常', icon: Warning, color: '#f56c6c' },
  bypass: { label: '旁路', icon: More, color: '#e6a23c' },
}

const props = defineProps<{
  data: FlowNodeCardData
  isSelected?: boolean
  isDragging?: boolean
}>()

const emit = defineEmits<{
  'update:flow-type': [type: string]
  preview: []
}>()

const imageLoading = ref(true)
const imageLoaded = ref(false)
const imageLoadError = ref(false)
const isHovered = ref(false)

const handleImageLoad = () => {
  imageLoading.value = false
  imageLoaded.value = true
}

const handleImageError = () => {
  imageLoading.value = false
  imageLoadError.value = true
}

const flowTypeLabel = computed(() => flowTypeConfig[props.data.flow_type]?.label || '主干')

const flowTypeIcon = computed(() => flowTypeConfig[props.data.flow_type]?.icon || Guide)

const flowTypeTagType = computed(() => {
  const types: Record<string, string> = {
    main: 'primary',
    branch: 'success',
    exception: 'danger',
    bypass: 'warning',
  }
  return types[props.data.flow_type] || 'primary'
})

const handleFlowTypeChange = (type: string) => {
  emit('update:flow-type', type)
}

const handlePreview = () => {
  emit('preview')
}
</script>

<style scoped lang="scss">
@mixin glow($color) {
  box-shadow:
    0 0 0 1px $color,
    0 4px 16px rgba($color, 0.3),
    0 8px 32px rgba($color, 0.15);
}

.flow-node-card {
  width: 220px;
  background: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
  border-radius: 12px;
  overflow: hidden;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.08),
    0 1px 2px rgba(0, 0, 0, 0.04);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid transparent;

  &:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow:
      0 8px 24px rgba(0, 0, 0, 0.12),
      0 4px 8px rgba(0, 0, 0, 0.08);
  }

  &.is-selected {
    border-color: #409eff;
    @include glow(#409eff);
  }

  &.is-dragging {
    opacity: 0.8;
    transform: scale(1.05) rotate(2deg);
    @include glow(#409eff);
  }

  &.flow-type-main {
    border-color: rgba(64, 158, 255, 0.3);
    &:hover {
      @include glow(#409eff);
    }
  }

  &.flow-type-branch {
    border-color: rgba(103, 194, 58, 0.3);
    &:hover {
      @include glow(#67c23a);
    }
  }

  &.flow-type-exception {
    border-color: rgba(245, 108, 108, 0.3);
    &:hover {
      @include glow(#f56c6c);
    }
  }

  &.flow-type-bypass {
    border-color: rgba(230, 162, 60, 0.3);
    &:hover {
      @include glow(#e6a23c);
    }
  }

  .node-header {
    padding: 10px 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: linear-gradient(135deg, #fafbfc 0%, #f5f7fa 100%);
    border-bottom: 1px solid rgba(0, 0, 0, 0.04);

    .flow-type-tag {
      cursor: pointer;
      transition: all 0.2s ease;
      border-radius: 6px;
      font-weight: 500;
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      overflow: hidden;

      &.tag-animated {
        transform: scale(1.05);
      }

      .tag-icon {
        margin-right: 4px;
        flex-shrink: 0;
      }
    }

    .element-badges {
      display: flex;
      gap: 4px;

      .badge {
        display: flex;
        align-items: center;
        gap: 2px;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        background: rgba(0, 0, 0, 0.04);
        color: #606266;
      }
    }
  }

  .node-image {
    position: relative;
    height: 130px;
    background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    overflow: hidden;

    .node-image-img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      transition:
        transform 0.3s ease,
        opacity 0.3s ease;
      opacity: 0;

      &.img-loaded {
        opacity: 1;
      }
    }

    &:hover .node-image-img {
      transform: scale(1.05);
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

      .error-text {
        font-size: 12px;
        color: #f56c6c;
      }
    }

    .image-overlay {
      position: absolute;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 6px;
      color: #fff;
      font-size: 13px;
      opacity: 0;
      transition: opacity 0.3s ease;
      backdrop-filter: blur(2px);
    }

    &:hover .image-overlay {
      opacity: 1;
    }
  }

  .node-footer {
    padding: 10px 12px;
    background: #fff;

    .screen-name {
      font-size: 13px;
      font-weight: 600;
      color: #303133;
      margin-bottom: 4px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .screen-summary {
      font-size: 11px;
      color: #909399;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      cursor: help;
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
