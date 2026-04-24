<template>
  <div
    class="ui-screen-card-shared"
    :class="{
      'is-dragging': isDragging,
      'is-draggable': draggable,
      'is-clickable': previewOn === 'card',
    }"
    :draggable="draggable"
    @click="handleCardClick"
    @dragstart="emit('dragstart', $event)"
    @dragover="emit('dragover', $event)"
    @drop="emit('drop', $event)"
    @dragend="emit('dragend')"
  >
    <div class="screen-card-topbar">
      <div class="screen-card-order">#{{ resolvedOrderText }}</div>
      <div class="screen-card-topbar-right">
        <el-tag size="small" class="parse-status-tag" effect="plain" :type="resolvedStatusType">
          {{ resolvedStatusText }}
        </el-tag>
        <slot name="topbar-extra" />
      </div>
    </div>

    <div class="screen-image-wrapper" @click.stop="handleImageClick">
      <img
        v-if="imageUrl"
        :src="imageUrl"
        :alt="screen.screen_name"
        class="screen-image"
        loading="lazy"
      />
      <div v-else class="screen-image-placeholder">
        <el-icon :size="40"><Picture /></el-icon>
      </div>
      <div class="screen-overlay">
        <span class="screen-overlay-text">{{ overlayText }}</span>
      </div>
    </div>

    <div class="screen-info">
      <div class="screen-name-row">
        <div class="screen-name" :title="screen.screen_name">{{ screen.screen_name }}</div>
      </div>
      <div v-if="screen.summary" class="screen-summary">{{ screen.summary }}</div>
      <div class="screen-meta" v-if="metaItems.length > 0">
        <span v-for="item in metaItems" :key="item" class="meta-pill">{{ item }}</span>
      </div>
    </div>

    <div v-if="$slots.footer" class="screen-card-footer">
      <slot name="footer" />
    </div>

    <div v-if="$slots.actions" class="screen-card-actions" @click.stop>
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import type { UIScreen } from '@/api/uiPrototype'
import { getUIScreenStatusMeta } from '@/composables/uiScreenStatus'

/**
 * `UIScreenCard` 负责渲染统一的 UI 屏幕卡片骨架。
 * 差异化区域通过 slots 注入，页面侧只关注行为，不再重复维护结构和样式。
 *
 * Slots:
 * - `topbar-extra`: 顶部状态区右侧的扩展内容
 * - `footer`: 底部说明信息
 * - `actions`: 底部操作按钮
 */
interface UIScreenCardProps {
  /** 当前屏幕对象，卡片主体信息均从这里读取。 */
  screen: UIScreen
  /** 已解析好的缩略图地址，可为空。 */
  imageUrl?: string
  /** 左上角序号文本，默认回退到 `screen_order` 或 `id`。 */
  orderText?: string | number
  /** 自定义状态文案，不传则走统一状态映射。 */
  statusText?: string
  /** 自定义状态标签类型，不传则走统一状态映射。 */
  statusType?: string
  /** 图片 hover 时显示的提示文案。 */
  overlayText?: string
  /** 决定点击预览是触发整张卡片还是仅缩略图区。 */
  previewOn?: 'card' | 'image'
  /** 是否启用原生拖拽。 */
  draggable?: boolean
  /** 当前卡片是否处于拖拽态。 */
  isDragging?: boolean
}

interface UIScreenCardEmits {
  /** 点击卡片或图片后抛出当前 screen。 */
  click: [screen: UIScreen]
  /** 原生拖拽开始。 */
  dragstart: [event: DragEvent]
  /** 原生拖拽悬停。 */
  dragover: [event: DragEvent]
  /** 原生拖拽放下。 */
  drop: [event: DragEvent]
  /** 原生拖拽结束。 */
  dragend: []
}

interface UIScreenCardSlots {
  /** 顶部状态标签右侧扩展区，常用于拖拽手柄或附加标识。 */
  'topbar-extra'?: () => unknown
  /** 卡片底部的说明/辅助信息区域。 */
  footer?: () => unknown
  /** 卡片底部操作按钮区域。 */
  actions?: () => unknown
}

const props = withDefaults(defineProps<UIScreenCardProps>(), {
  imageUrl: '',
  overlayText: '点击查看详情',
  previewOn: 'card',
  draggable: false,
  isDragging: false,
})

const emit = defineEmits<UIScreenCardEmits>()
defineSlots<UIScreenCardSlots>()

const resolvedOrderText = computed(() => {
  return props.orderText ?? props.screen.screen_order ?? props.screen.id
})

const resolvedStatusMeta = computed(() => getUIScreenStatusMeta(props.screen))

const resolvedStatusType = computed(() => {
  return props.statusType || resolvedStatusMeta.value.type
})

const resolvedStatusText = computed(() => {
  return props.statusText || resolvedStatusMeta.value.text
})

const metaItems = computed(() => {
  const items: string[] = []
  if (props.screen.element_count) items.push(`元素 ${props.screen.element_count}`)
  if (props.screen.button_count) items.push(`按钮 ${props.screen.button_count}`)
  if (props.screen.input_count) items.push(`输入框 ${props.screen.input_count}`)
  return items
})

const handleCardClick = () => {
  if (props.previewOn === 'card') {
    emit('click', props.screen)
  }
}

const handleImageClick = () => {
  if (props.previewOn === 'image') {
    emit('click', props.screen)
  }
}
</script>

<style scoped>
.ui-screen-card-shared {
  position: relative;
  border: 1px solid #e8ecf0;
  border-radius: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}

.ui-screen-card-shared.is-clickable {
  cursor: pointer;
}

.ui-screen-card-shared.is-draggable {
  cursor: grab;
}

.ui-screen-card-shared:hover {
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.1);
  transform: translateY(-4px);
  border-color: #cfe0ff;
}

.ui-screen-card-shared.is-dragging {
  opacity: 0.6;
  border-style: dashed;
  border-color: #409eff;
  background: linear-gradient(145deg, #ecf5ff 0%, #f8fbff 100%);
  transform: scale(0.98) rotate(1deg);
}

.screen-card-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px 0;
}

.screen-card-topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.screen-card-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
}

.parse-status-tag {
  border-radius: 999px;
}

.screen-image-wrapper {
  position: relative;
  width: calc(100% - 32px);
  height: 190px;
  margin: 14px 16px 0;
  background: linear-gradient(145deg, #f8f9fb 0%, #e8ecf0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid #eef2f6;
  cursor: pointer;
}

.screen-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  transition: transform 0.3s ease;
}

.ui-screen-card-shared:hover .screen-image {
  transform: scale(1.05);
}

.screen-image-placeholder {
  color: #a0a8b4;
}

.screen-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.04) 0%, rgba(15, 23, 42, 0.55) 100%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.ui-screen-card-shared:hover .screen-overlay {
  opacity: 1;
}

.screen-overlay-text {
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
}

.screen-info {
  padding: 14px 16px 12px;
}

.screen-name-row {
  margin-bottom: 8px;
}

.screen-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a1d21;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.5;
  min-height: 44px;
}

.screen-summary {
  font-size: 12px;
  line-height: 1.6;
  color: #6b7280;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
  margin-bottom: 10px;
}

.screen-meta {
  font-size: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f3f6fb;
  color: #667085;
}

.screen-card-footer,
.screen-card-actions {
  padding: 0 16px 16px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  border-top: 1px solid #f1f4f8;
  background: rgba(248, 250, 252, 0.8);
}

.screen-card-footer {
  align-items: center;
  justify-content: space-between;
}

.screen-card-actions {
  align-items: center;
}

.screen-card-actions :deep(.el-button) {
  margin: 0;
}

@media (max-width: 768px) {
  .screen-card-footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
