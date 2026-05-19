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
          <el-button size="small" circle class="hover-action-btn" @click.stop="handlePreview"><el-icon :size="14"><ZoomIn /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="设为主干" placement="top" v-if="data.flow_type !== 'main'">
          <el-button size="small" circle class="hover-action-btn hover-action-main" @click.stop="handleFlowTypeChange('main')"><el-icon :size="14"><Guide /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="设为分支" placement="top" v-if="data.flow_type !== 'branch'">
          <el-button size="small" circle class="hover-action-btn hover-action-branch" @click.stop="handleFlowTypeChange('branch')"><el-icon :size="14"><Connection /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="设为异常" placement="top" v-if="data.flow_type !== 'exception'">
          <el-button size="small" circle class="hover-action-btn hover-action-exception" @click.stop="handleFlowTypeChange('exception')"><el-icon :size="14"><Warning /></el-icon></el-button>
        </el-tooltip>
        <el-tooltip content="设为旁路" placement="top" v-if="data.flow_type !== 'bypass'">
          <el-button size="small" circle class="hover-action-btn hover-action-bypass" @click.stop="handleFlowTypeChange('bypass')"><el-icon :size="14"><More /></el-icon></el-button>
        </el-tooltip>
      </div>
    </transition>
    <div class="node-header">
      <el-dropdown trigger="click" :disabled="displayMode === 'overview'" @command="handleFlowTypeChange">
        <el-tag :type="flowTypeTagType" size="small" effect="dark" class="flow-type-tag" :class="{ 'tag-animated': isHovered }">
          <el-icon v-if="flowTypeIcon" class="tag-icon"><component :is="flowTypeIcon" /></el-icon>
          {{ flowTypeLabel }}
        </el-tag>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="main"><el-icon><Guide /></el-icon>主干流程</el-dropdown-item>
            <el-dropdown-item command="branch"><el-icon><Connection /></el-icon>分支流程</el-dropdown-item>
            <el-dropdown-item command="exception"><el-icon><Warning /></el-icon>异常流程</el-dropdown-item>
            <el-dropdown-item command="bypass"><el-icon><More /></el-icon>旁路流程</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <div class="element-badges">
        <span v-if="data.element_count" class="badge badge-elements" title="元素数量"><el-icon><Grid /></el-icon>{{ data.element_count }}</span>
        <span v-if="data.flow_type === 'main' && (childBranchCount ?? 0) > 0" class="badge badge-branches" title="分支节点数"><el-icon><Connection /></el-icon>{{ childBranchCount }}</span>
      </div>
    </div>
    <div v-if="data.flow_type === 'main' && (childBranchCount ?? 0) > 0" class="collapse-toggle" @click.stop="handleToggleCollapse">
      <el-icon :size="14"><ArrowRight v-if="isCollapsed" /><ArrowDown v-else /></el-icon>
      <span>{{ isCollapsed ? '展开分支' : '收起分支' }}</span>
      <span class="collapse-count">({{ childBranchCount }})</span>
    </div>
    <template v-if="displayMode === 'overview'">
      <div class="node-image node-image--overview" @click="handlePreview">
        <div v-if="imageLoading && !imageLoadError && data.image_url" class="image-skeleton"><el-icon class="loading-icon"><Loading /></el-icon></div>
        <img v-show="!imageLoading && !imageLoadError && data.image_url" :src="data.image_url" :alt="data.screen_name" class="node-image-img" :class="{ 'img-loaded': imageLoaded }" @load="handleImageLoad" @error="handleImageError" />
        <div v-if="!data.image_url || imageLoadError" class="image-placeholder image-placeholder--overview"><el-icon :size="28"><Picture /></el-icon><span class="placeholder-text">{{ imageLoadError ? '加载失败' : '暂无图片' }}</span></div>
      </div>
      <div class="node-footer node-footer--overview"><div class="screen-name screen-name--overview" :title="data.screen_name">{{ data.screen_name }}</div></div>
    </template>
    <template v-else>
      <div class="node-image" @click="handlePreview">
        <div v-if="imageLoading && !imageLoadError && data.image_url" class="image-skeleton"><el-icon class="loading-icon"><Loading /></el-icon></div>
        <img v-show="!imageLoading && !imageLoadError && data.image_url" :src="data.image_url" :alt="data.screen_name" class="node-image-img" :class="{ 'img-loaded': imageLoaded }" @load="handleImageLoad" @error="handleImageError" />
        <div v-if="!data.image_url || imageLoadError" class="image-placeholder"><el-icon :size="36"><Picture /></el-icon><span class="placeholder-text">{{ imageLoadError ? '加载失败' : '暂无图片' }}</span></div>
        <transition name="fade">
          <div v-if="!imageLoadError && data.image_url" class="image-overlay"><el-icon :size="28"><View /></el-icon><span>点击预览</span></div>
        </transition>
      </div>
      <div class="node-footer">
        <div class="screen-name" :title="data.screen_name">{{ data.screen_name }}</div>
        <el-tooltip v-if="data.summary" :content="data.summary" placement="top" :show-after="500"><div class="screen-summary">{{ data.summary }}</div></el-tooltip>
      </div>
    </template>
    <Handle type="source" :position="Position.Top" id="source-top" />
    <Handle type="source" :position="Position.Right" id="source-right" />
    <Handle type="source" :position="Position.Bottom" id="source-bottom" />
    <Handle type="target" :position="Position.Left" id="target-left" />
    <Handle type="target" :position="Position.Top" id="target-top" />
    <Handle type="target" :position="Position.Bottom" id="target-bottom" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { ElIcon } from 'element-plus'
import { Picture, ZoomIn, View, Guide, Connection, Warning, More, Grid, Loading, ArrowRight, ArrowDown } from '@element-plus/icons-vue'

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

watch(() => props.data.image_url, (newUrl) => {
  if (newUrl) { imageLoading.value = true; imageLoaded.value = false; imageLoadError.value = false }
})

const handleImageLoad = () => { imageLoading.value = false; imageLoaded.value = true }
const handleImageError = () => { imageLoading.value = false; imageLoadError.value = true }
const flowTypeLabel = computed(() => flowTypeConfig[props.data.flow_type]?.label || '主干')
const flowTypeIcon = computed(() => flowTypeConfig[props.data.flow_type]?.icon || Guide)
const flowTypeTagType = computed(() => {
  const types: Record<string, string> = { main: 'primary', branch: 'success', exception: 'danger', bypass: 'warning' }
  return types[props.data.flow_type] || 'primary'
})
const handleFlowTypeChange = (type: string) => { emit('update:flow-type', type) }
const handlePreview = () => { emit('preview') }
const handleToggleCollapse = () => { if (props.nodeId) { emit('toggle-collapse', props.nodeId) } }
</script>

<style scoped lang="scss">
@import './FlowNodeCard.scss';
</style>
