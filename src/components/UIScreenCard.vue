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

    <div class="screen-image-wrapper" @click="handleImageClick">
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

<style scoped src="./UIScreenCard.scss"></style>
