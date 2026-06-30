<template>
  <!-- Task12: 统一错误状态组件，三个错误场景复用（生成失败/UI解析超时/保存失败） -->
  <div class="error-state" role="alert" aria-live="assertive">
    <el-icon :size="48" color="#f56c6c" class="error-icon"><CircleCloseFilled /></el-icon>
    <h4 class="error-title">{{ title }}</h4>
    <p v-if="reason" class="error-reason">{{ reason }}</p>
    <div class="error-actions">
      <el-button v-if="retryable" type="primary" @click="$emit('retry')">
        <el-icon><Refresh /></el-icon>重试
      </el-button>
      <slot name="extra-actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircleCloseFilled, Refresh } from '@element-plus/icons-vue'

/** 错误状态展示组件：图标 + 原因 + 重试按钮，生成失败/UI 解析超时/保存失败三场景复用 */
defineProps<{
  /** 错误标题 */
  title: string
  /** 透出的真实错误原因（来自后端 detail 或 error.message） */
  reason?: string
  /** 是否可重试，true 显示重试按钮 */
  retryable?: boolean
}>()

defineEmits<{
  (e: 'retry'): void
}>()
</script>

<style scoped>
.error-state {
  text-align: center;
  padding: 32px 16px;
}
.error-icon {
  margin-bottom: 12px;
}
.error-title {
  margin: 0 0 8px;
  font-size: 16px;
  color: #303133;
}
.error-reason {
  margin: 0 0 16px;
  font-size: 13px;
  color: #909399;
  word-break: break-all;
  line-height: 1.6;
}
.error-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
