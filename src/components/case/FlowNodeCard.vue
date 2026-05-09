<template>
  <div
    class="flow-node-card"
    :class="[
      `flow-type-${data.flow_type}`,
      `display-${displayMode}`,
      {
        'is-selected': isSelected,
        'is-dragging': isDragging,
        'is-search-match': isSearchMatch,
        'is-focused': isFocused,
        'is-upstream': isUpstream,
        'is-downstream': isDownstream,
        'is-path-dimmed': isPathDimmed,
        'is-test-point-related': isTestPointRelated,
      },
    ]"
    @mouseenter="isHovered = true"
    @mouseleave="isHovered = false"
  >
    <transition name="hover-actions-fade">
      <div v-if="isHovered && displayMode === 'edit'" class="hover-actions">
        <el-tooltip content="预览截图" placement="top">
          <el-button size="small" circle class="hover-action-btn" @click.stop="handlePreview">
            <el-icon :size="14"><ZoomIn /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="设为主干" placement="top" v-if="data.flow_type !== 'main'">
          <el-button
            size="small"
            circle
            class="hover-action-btn hover-action-main"
            @click.stop="handleFlowTypeChange('main')"
          >
            <el-icon :size="14"><Guide /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="设为分支" placement="top" v-if="data.flow_type !== 'branch'">
          <el-button
            size="small"
            circle
            class="hover-action-btn hover-action-branch"
            @click.stop="handleFlowTypeChange('branch')"
          >
            <el-icon :size="14"><Connection /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="设为异常" placement="top" v-if="data.flow_type !== 'exception'">
          <el-button
            size="small"
            circle
            class="hover-action-btn hover-action-exception"
            @click.stop="handleFlowTypeChange('exception')"
          >
            <el-icon :size="14"><Warning /></el-icon>
          </el-button>
        </el-tooltip>
        <el-tooltip content="设为旁路" placement="top" v-if="data.flow_type !== 'bypass'">
          <el-button
            size="small"
            circle
            class="hover-action-btn hover-action-bypass"
            @click.stop="handleFlowTypeChange('bypass')"
          >
            <el-icon :size="14"><More /></el-icon>
          </el-button>
        </el-tooltip>
      </div>
    </transition>
    <div class="node-header">
      <el-dropdown
        trigger="click"
        :disabled="displayMode === 'overview'"
        @command="handleFlowTypeChange"
      >
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
        <span
          v-if="data.flow_type === 'main' && (childBranchCount ?? 0) > 0"
          class="badge badge-branches"
          title="分支节点数"
        >
          <el-icon><Connection /></el-icon>{{ childBranchCount }}
        </span>
      </div>
    </div>

    <div
      v-if="data.flow_type === 'main' && (childBranchCount ?? 0) > 0"
      class="collapse-toggle"
      @click.stop="handleToggleCollapse"
    >
      <el-icon :size="14">
        <ArrowRight v-if="isCollapsed" />
        <ArrowDown v-else />
      </el-icon>
      <span>{{ isCollapsed ? '展开分支' : '收起分支' }}</span>
      <span class="collapse-count">({{ childBranchCount }})</span>
    </div>

    <!-- Overview mode: screenshot-centric compact card -->
    <template v-if="displayMode === 'overview'">
      <div class="node-image node-image--overview" @click="handlePreview">
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
        <div
          v-if="!data.image_url || imageLoadError"
          class="image-placeholder image-placeholder--overview"
        >
          <el-icon :size="28"><Picture /></el-icon>
          <span class="placeholder-text">{{ imageLoadError ? '加载失败' : '暂无图片' }}</span>
        </div>
      </div>
      <div class="node-footer node-footer--overview">
        <div class="screen-name screen-name--overview" :title="data.screen_name">
          {{ data.screen_name }}
        </div>
      </div>
    </template>
    <!-- Edit mode: full card with image -->
    <template v-else>
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
    </template>

    <Handle type="source" :position="Position.Right" id="source-right" />
    <Handle type="source" :position="Position.Bottom" id="source-bottom" />
    <Handle type="target" :position="Position.Left" id="target-left" />
    <Handle type="target" :position="Position.Top" id="target-top" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { ElIcon } from 'element-plus'
import {
  Picture,
  ZoomIn,
  View,
  Guide,
  Connection,
  Warning,
  More,
  Grid,
  Loading,
  ArrowRight,
  ArrowDown,
} from '@element-plus/icons-vue'

interface FlowNodeCardData {
  screen_id: number
  screen_name: string
  summary?: string
  flow_type: 'main' | 'branch' | 'exception' | 'bypass'
  image_url?: string
  element_count?: number
}

type DisplayMode = 'overview' | 'edit'

const flowTypeConfig: Record<string, { label: string; icon: typeof Guide; color: string }> = {
  main: { label: '主干', icon: Guide, color: '#409eff' },
  branch: { label: '分支', icon: Connection, color: '#67c23a' },
  exception: { label: '异常', icon: Warning, color: '#f56c6c' },
  bypass: { label: '旁路', icon: More, color: '#e6a23c' },
}

const props = defineProps<{
  data: FlowNodeCardData
  nodeId?: string
  displayMode?: DisplayMode
  isSelected?: boolean
  isDragging?: boolean
  isSearchMatch?: boolean
  isFocused?: boolean
  isUpstream?: boolean
  isDownstream?: boolean
  isPathDimmed?: boolean
  childBranchCount?: number
  isCollapsed?: boolean
  isTestPointRelated?: boolean
}>()

const emit = defineEmits<{
  'update:flow-type': [type: string]
  preview: []
  'toggle-collapse': [nodeId: string]
}>()

const imageLoading = ref(true)
const imageLoaded = ref(false)
const imageLoadError = ref(false)
const isHovered = ref(false)

watch(
  () => props.data.image_url,
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

const handleToggleCollapse = () => {
  if (props.nodeId) {
    emit('toggle-collapse', props.nodeId)
  }
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

  &.is-focused {
    border-color: #409eff !important;
    box-shadow:
      0 0 0 2px rgba(64, 158, 255, 0.5),
      0 6px 24px rgba(64, 158, 255, 0.3);
  }

  &.is-upstream {
    border-color: #a855f7 !important;
    box-shadow:
      0 0 0 1px rgba(168, 85, 247, 0.4),
      0 3px 12px rgba(168, 85, 247, 0.15);
  }

  &.is-downstream {
    border-color: #22c55e !important;
    box-shadow:
      0 0 0 1px rgba(34, 197, 94, 0.4),
      0 3px 12px rgba(34, 197, 94, 0.15);
  }

  &.is-path-dimmed {
    opacity: 0.35;
  }

  &.is-test-point-related {
    position: relative;

    &::before {
      content: '';
      position: absolute;
      top: -2px;
      left: -2px;
      right: -2px;
      bottom: -2px;
      border-radius: inherit;
      background: linear-gradient(135deg, #f093fb, #f5576c, #4facfe);
      background-size: 300% 300%;
      animation: test-point-glow 2s ease-in-out infinite;
      z-index: -1;
      opacity: 0.6;
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

      .badge-branches {
        background: rgba(103, 194, 58, 0.12);
        color: #67c23a;
      }
    }
  }

  .collapse-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 5px 12px;
    background: rgba(103, 194, 58, 0.06);
    border-top: 1px solid rgba(103, 194, 58, 0.15);
    cursor: pointer;
    font-size: 12px;
    color: #67c23a;
    transition: background 0.2s ease;
    user-select: none;

    &:hover {
      background: rgba(103, 194, 58, 0.12);
    }

    .collapse-count {
      font-size: 11px;
      color: #909399;
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

  // Overview mode: screenshot-centric compact card
  &.display-overview {
    width: 180px;

    .node-header {
      height: 4px;
      padding: 0;
      border-bottom: none;

      .flow-type-tag {
        display: none;
      }

      .element-badges {
        display: none;
      }
    }

    .node-image--overview {
      height: 112px;
    }

    .image-placeholder--overview {
      height: 100%;
    }

    .node-footer--overview {
      padding: 6px 8px;

      .screen-name--overview {
        font-size: 12px;
        font-weight: 600;
        color: #303133;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    &:hover {
      transform: translateY(-1px);
    }

    &.flow-type-main .node-header {
      background: #409eff;
    }

    &.flow-type-branch .node-header {
      background: #67c23a;
    }

    &.flow-type-exception .node-header {
      background: #f56c6c;
    }

    &.flow-type-bypass .node-header {
      background: #e6a23c;
    }
  }

  // Search match highlight
  &.is-search-match {
    border-color: #e6a23c !important;
    box-shadow:
      0 0 0 2px rgba(230, 162, 60, 0.4),
      0 4px 16px rgba(230, 162, 60, 0.2);
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

.hover-actions-fade-enter-active {
  transition: all 0.2s ease;
}

.hover-actions-fade-leave-active {
  transition: all 0.15s ease;
}

.hover-actions-fade-enter-from,
.hover-actions-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

.hover-actions {
  position: absolute;
  top: -36px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 4px;
  background: #fff;
  padding: 4px 6px;
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  border: 1px solid rgba(0, 0, 0, 0.06);
  z-index: 20;

  .hover-action-btn {
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    background: #f2f3f5;

    &:hover {
      background: #e4e7ed;
    }

    &.hover-action-main:hover {
      background: #409eff;
      color: #fff;
    }

    &.hover-action-branch:hover {
      background: #67c23a;
      color: #fff;
    }

    &.hover-action-exception:hover {
      background: #f56c6c;
      color: #fff;
    }

    &.hover-action-bypass:hover {
      background: #e6a23c;
      color: #fff;
    }
  }
}

@keyframes test-point-glow {
  0%,
  100% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
}
</style>
