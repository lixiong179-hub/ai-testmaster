<template>
  <div class="test">
    <h1>测试页面</h1>
    <el-button @click="goToDashboard">跳转到仪表盘</el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()

const goToDashboard = () => {
  if (import.meta.env.MODE !== 'development') {
    ElMessage.error('此功能仅在开发环境可用')
    return
  }
  localStorage.setItem('token', 'test_token')
  router.push('/home/project')
}
</script>

<style scoped>
.test {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 20px;
}
</style>
