<template>
  <transition name="guide-slide">
    <div v-if="visible" class="next-step-guide">
      <el-alert :type="type" :closable="closable" show-icon @close="handleClose">
        <template #title>
          <span class="guide-title">{{ title }}</span>
        </template>
        <template #default>
          <div class="guide-body">
            <p v-if="description" class="guide-description">{{ description }}</p>
            <div class="guide-actions">
              <el-button
                v-for="action in actions"
                :key="action.label"
                :type="action.type || 'primary'"
                :size="action.size || 'small'"
                @click="handleAction(action)"
              >
                <el-icon v-if="action.icon">
                  <component :is="action.icon" />
                </el-icon>
                {{ action.label }}
              </el-button>
            </div>
          </div>
        </template>
      </el-alert>
    </div>
  </transition>
</template>

<script lang="ts">
import type { Component } from 'vue'

/**
 * Task4: 将类型定义放至普通 <script> 块中以兼容 vitest 的 SFC 编译器
 * （原 <script setup> 中 export interface 经第二个 <script> re-export 在 vitest 下会报
 * "Export 'GuideAction' is not defined"）。
 */
export interface GuideAction {
  label: string
  type?: 'primary' | 'success' | 'warning' | 'info' | 'danger'
  size?: 'small' | 'default' | 'large'
  icon?: Component
  /** 路由跳转路径，优先于 onClick */
  to?: string
  /** 自定义点击回调 */
  onClick?: () => void
}

export interface NextStepGuideProps {
  visible: boolean
  title: string
  description?: string
  actions: GuideAction[]
  type?: 'success' | 'info' | 'warning' | 'error'
  closable?: boolean
}

// 导出类型供外部使用
export type { GuideAction as NextStepGuideAction }
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<NextStepGuideProps>(), {
  type: 'success',
  closable: true,
})

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'action', action: GuideAction): void
}>()

function handleAction(action: GuideAction): void {
  emit('action', action)
  if (action.onClick) {
    action.onClick()
  }
}

function handleClose(): void {
  emit('close')
}

// 防 props 未使用的 lint 警告
void props
</script>

<style scoped>
.next-step-guide {
  margin-bottom: 16px;
}

.guide-title {
  font-weight: 600;
}

.guide-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guide-description {
  margin: 0;
  line-height: 1.6;
  color: #606266;
}

.guide-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.guide-slide-enter-active,
.guide-slide-leave-active {
  transition: all 0.3s ease;
}

.guide-slide-enter-from,
.guide-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
