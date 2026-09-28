<template>
  <div class="not-found">
    <div class="not-found-content">
      <div class="not-found-code">404</div>
      <div class="not-found-title">页面不存在</div>
      <div class="not-found-desc">您访问的页面可能已被移除或地址有误</div>
      <div class="not-found-actions">
        <el-button type="primary" @click="goHome">返回首页</el-button>
        <el-button @click="goBack">返回上一页</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goHome(): void {
  router.push('/home/project')
}

function goBack(): void {
  router.back()
}
</script>

<style scoped lang="scss">
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background-color: var(--color-bg-page);
}

.not-found-content {
  text-align: center;
}

.not-found-code {
  font-size: 96px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-primary);
}

.not-found-title {
  margin-top: 16px;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.not-found-desc {
  margin-top: 8px;
  font-size: 14px;
  color: var(--color-info);
}

.not-found-actions {
  margin-top: 24px;
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
