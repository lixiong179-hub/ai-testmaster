<template>
  <div class="progress-container">
    <div class="progress-header">
      <span class="progress-title">{{ title }}</span>
      <span class="progress-percentage">{{ progress }}%</span>
    </div>
    <el-progress :percentage="progress" :status="status" :stroke-width="15" :format="() => ''" />
    <div class="progress-message" v-if="message">
      {{ message }}
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  title: {
    type: String,
    default: '分析进度',
  },
  progress: {
    type: Number,
    default: 0,
  },
  message: {
    type: String,
    default: '',
  },
  status: {
    type: String as () => 'success' | 'exception' | 'warning' | '',
    default: '',
  },
})
</script>

<style scoped>
.progress-container {
  width: 100%;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.progress-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.progress-percentage {
  font-size: 16px;
  font-weight: 600;
  color: #409eff;
}

.progress-message {
  margin-top: 10px;
  font-size: 14px;
  color: #606266;
  line-height: 1.5;
}
</style>
