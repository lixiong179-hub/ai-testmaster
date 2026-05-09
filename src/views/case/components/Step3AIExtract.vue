<template>
  <div class="step-content">
    <div class="step-title">
      <el-icon><MagicStick /></el-icon>
      <span>AI提取测试点</span>
    </div>
    <div class="step-body">
      <div v-if="selectedResource" class="selected-resource-card">
        <div class="resource-summary">
          <el-icon :size="32"
            ><component :is="getResourceIcon(selectedResource.resource_type)"
          /></el-icon>
          <div>
            <div class="resource-name">{{ selectedResource.display_name }}</div>
            <div class="resource-meta">
              {{ selectedResource.type_label }} · {{ selectedResource.size_text }}
            </div>
          </div>
        </div>
      </div>

      <div v-if="extracting" class="extract-progress">
        <div class="skeleton-wrapper">
          <el-skeleton :rows="5" animated />
        </div>
        <div class="progress-section">
          <el-progress
            :percentage="progress"
            :status="progressStatus"
            :stroke-width="16"
            :text-inside="true"
          />
          <div class="progress-text-animated">{{ progressText }}</div>
          <el-button type="danger" plain @click="handleCancel" size="small">
            <el-icon><Close /></el-icon>
            取消提取
          </el-button>
        </div>
      </div>

      <div v-else-if="errorMessage" class="extract-error">
        <el-result icon="error" title="提取失败" :sub-title="errorMessage">
          <template #extra>
            <el-button type="primary" @click="retryExtract">
              <el-icon><Refresh /></el-icon>
              重试
            </el-button>
          </template>
        </el-result>
      </div>

      <div v-else-if="testPoints.length > 0" class="extract-success">
        <div class="success-header">
          <div class="success-icon-wrapper">
            <el-icon :size="48" color="#67C23A"><CircleCheckFilled /></el-icon>
          </div>
          <div class="success-info">
            <h3 class="success-title">提取成功！</h3>
            <p class="success-desc">
              共提取 <strong>{{ testPoints.length }}</strong> 个测试点
            </p>
          </div>
        </div>
        <div class="success-stats-grid">
          <div class="stat-item stat-high">
            <span class="stat-number">{{ getPriorityCount(1) }}</span>
            <span class="stat-label">高优先级</span>
          </div>
          <div class="stat-item stat-medium">
            <span class="stat-number">{{ getPriorityCount(2) }}</span>
            <span class="stat-label">中优先级</span>
          </div>
          <div class="stat-item stat-low">
            <span class="stat-number">{{ getPriorityCount(3) }}</span>
            <span class="stat-label">低优先级</span>
          </div>
          <div class="stat-item stat-modules">
            <span class="stat-number">{{ moduleCount }}</span>
            <span class="stat-label">模块数</span>
          </div>
        </div>
        <div class="success-actions">
          <el-button type="primary" size="large" @click="goToNextStep">
            下一步：校验结果
            <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button size="large" @click="retryExtract" plain>
            <el-icon><Refresh /></el-icon>
            重新提取
          </el-button>
        </div>
      </div>

      <div v-else class="extract-ready">
        <el-empty description="点击下方按钮开始AI提取测试点" :image-size="120">
          <template #image>
            <div class="ready-icon">
              <el-icon :size="80" color="#409EFF"><MagicStick /></el-icon>
            </div>
          </template>
          <template #description>
            <p class="ready-text">AI将自动分析需求文档并提取测试点</p>
          </template>
          <template #default>
            <el-button
              type="primary"
              size="large"
              @click="startExtract"
              :disabled="!selectedResource"
            >
              <el-icon><MagicStick /></el-icon>
              开始提取
            </el-button>
          </template>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MagicStick, Close, Refresh, CircleCheckFilled, ArrowRight } from '@element-plus/icons-vue'
import { useTestPointExtract } from '@/composables/useTestPointExtract'

const {
  selectedResource,
  extracting,
  progress,
  progressStatus,
  progressText,
  errorMessage,
  testPoints,
  moduleCount,
  getResourceIcon,
  getPriorityCount,
  handleCancel,
  retryExtract,
  startExtract,
  goToNextStep,
} = useTestPointExtract()
</script>
