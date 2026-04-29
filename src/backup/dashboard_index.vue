<template>
  <div class="dashboard">
    <el-card class="dashboard-card">
      <template #header>
        <div class="card-header">
          <span>系统概览</span>
        </div>
      </template>
      <div class="dashboard-stats">
        <div
          v-for="stat in stats"
          :key="stat.key"
          class="stat-item"
        >
          <div class="stat-icon">
            <el-icon :size="32">
              <DocumentChecked v-if="stat.icon === 'DocumentChecked'" />
              <Clock v-else-if="stat.icon === 'Clock'" />
              <SuccessFilled v-else-if="stat.icon === 'SuccessFilled'" />
              <WarningFilled v-else-if="stat.icon === 'WarningFilled'" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-title">{{ stat.title }}</div>
            <div class="stat-value">{{ stat.value }}{{ stat.suffix }}</div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { 
  DocumentChecked, 
  Clock, 
  SuccessFilled, 
  WarningFilled 
} from '@element-plus/icons-vue'

// 统计数据
const stats = [
  {
    key: 'totalCases',
    title: '总测试用例',
    value: 1280,
    suffix: '个',
    icon: 'DocumentChecked'
  },
  {
    key: 'todayExecutions',
    title: '今日执行',
    value: 156,
    suffix: '次',
    icon: 'Clock'
  },
  {
    key: 'successRate',
    title: '成功率',
    value: 92.5,
    suffix: '%',
    icon: 'SuccessFilled'
  },
  {
    key: 'pendingTasks',
    title: '待执行任务',
    value: 12,
    suffix: '个',
    icon: 'WarningFilled'
  }
]

// 组件挂载
onMounted(() => {
  console.log('Dashboard component mounted')
})
</script>

<style scoped>
.dashboard {
  padding: 20px 0;
  min-height: 100%;
}

.dashboard-card {
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dashboard-stats {
  display: flex;
  justify-content: space-around;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-item {
  flex: 1;
  min-width: 200px;
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 15px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  height: 60px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
}

.stat-content {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
}
</style>
