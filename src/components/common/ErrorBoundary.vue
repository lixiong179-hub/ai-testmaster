<template>
  <slot v-if="!hasError" />
  <div v-else class="error-boundary">
    <el-result icon="error" title="页面渲染异常" sub-title="抱歉，该区域发生错误，请刷新或返回重试">
      <template #extra>
        <el-button type="primary" @click="handleRetry">重试</el-button>
        <el-button @click="handleBack">返回上一页</el-button>
      </template>
    </el-result>
  </div>
</template>

<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const hasError = ref(false)
const error = ref<Error | null>(null)

onErrorCaptured((err: unknown) => {
  error.value = err as Error
  hasError.value = true
  if (import.meta.env.DEV) {
    console.error('[ErrorBoundary]', err)
  }
  // 阻止错误继续向上传播（已被此边界捕获）
  return false
})

function handleRetry(): void {
  hasError.value = false
  error.value = null
}

function handleBack(): void {
  hasError.value = false
  error.value = null
  router.back()
}
</script>

<style scoped>
.error-boundary {
  padding: 40px 0;
}
</style>
