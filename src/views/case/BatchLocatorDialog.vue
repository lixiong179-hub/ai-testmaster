<template>
  <el-dialog
    v-model="visible"
    title="批量补充元素定位"
    width="600px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="!isRunning"
  >
    <div class="batch-locator-dialog">
      <!-- 任务配置 -->
      <div v-if="!isRunning && !report" class="task-config">
        <el-alert
          type="info"
          title="批量补充元素定位"
          description="系统将自动遍历测试用例的所有步骤，AI识别每个步骤的目标元素并记录定位信息。"
          show-icon
          :closable="false"
          style="margin-bottom: 20px"
        />

        <el-form :model="config" label-width="150px">
          <el-form-item label="跳过已有定位">
            <el-switch v-model="config.skip_existing" />
            <span class="form-tip">开启后，已记录定位的步骤将自动跳过</span>
          </el-form-item>

          <el-form-item label="执行前置操作">
            <el-switch v-model="config.execute_precondition" />
            <span class="form-tip">开启后，系统将自动启动浏览器并登录</span>
          </el-form-item>
          <el-form-item label="MCP定位引擎">
            <el-switch v-model="config.use_mcp" active-text="MCP" inactive-text="VLM" />
            <div class="form-tip" style="margin-top: 4px; font-size: 12px; color: #909399">
              启用Playwright MCP定位引擎，支持role/text/css等多种定位策略
            </div>
          </el-form-item>
        </el-form>

        <div class="config-actions">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" @click="startBatchRecord" :loading="starting">
            开始批量补充
          </el-button>
        </div>
      </div>

      <!-- 执行进度 -->
      <div v-else-if="isRunning" class="task-progress">
        <div class="progress-header">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <span class="status-text">正在批量补充元素定位...</span>
        </div>

        <el-progress
          :percentage="progress"
          :stroke-width="20"
          :status="progressStatus"
          class="main-progress"
        />

        <div class="progress-stats">
          <div class="stat-item">
            <span class="stat-label">总步骤：</span>
            <span class="stat-value">{{ totalSteps }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已完成：</span>
            <span class="stat-value">{{ completedSteps }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">成功：</span>
            <span class="stat-value success">{{ successCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">失败：</span>
            <span class="stat-value error">{{ failedCount }}</span>
          </div>
        </div>

        <div class="current-step" v-if="currentStepInfo">
          <span class="step-label">当前步骤：</span>
          <span class="step-action">{{ currentStepInfo }}</span>
        </div>

        <div class="progress-actions">
          <el-button type="danger" @click="cancelBatchRecord" :loading="cancelling">
            取消任务
          </el-button>
        </div>
      </div>

      <!-- 完成报告 -->
      <div v-else-if="report" class="task-report">
        <div class="report-header" :class="report.status">
          <el-icon v-if="report.status === 'completed'" class="status-icon success"
            ><CircleCheck
          /></el-icon>
          <el-icon v-else-if="report.status === 'failed'" class="status-icon error"
            ><CircleClose
          /></el-icon>
          <el-icon v-else class="status-icon warning"><Warning /></el-icon>
          <span class="status-text">{{ reportStatusText }}</span>
        </div>

        <div class="report-stats">
          <div class="stat-row">
            <span class="stat-label">总步骤数：</span>
            <span class="stat-value">{{ report.total_steps }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">成功：</span>
            <span class="stat-value success">{{ report.success_count }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">失败：</span>
            <span class="stat-value error">{{ report.failed_count }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">跳过：</span>
            <span class="stat-value info">{{ report.skipped_count }}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">总耗时：</span>
            <span class="stat-value">{{ formatDuration(report.duration) }}</span>
          </div>
        </div>

        <!-- 步骤详情 -->
        <div class="step-details" v-if="report.step_results && report.step_results.length > 0">
          <h4>步骤详情</h4>
          <el-collapse>
            <el-collapse-item
              v-for="step in report.step_results"
              :key="step.step_id"
              :title="`步骤 ${step.step_number}: ${step.display_action || step.description || step.action}`"
            >
              <div class="step-detail-content">
                <div class="detail-row">
                  <span class="detail-label">状态：</span>
                  <el-tag :type="step.success ? 'success' : 'danger'" size="small">
                    {{ step.success ? '成功' : '失败' }}
                  </el-tag>
                </div>
                <div class="detail-row">
                  <span class="detail-label">消息：</span>
                  <span class="detail-value">{{ step.message }}</span>
                </div>
                <div class="detail-row" v-if="step.css_selector">
                  <span class="detail-label">CSS选择器：</span>
                  <code class="detail-value">{{ step.css_selector }}</code>
                </div>
                <div class="detail-row" v-if="step.confidence">
                  <span class="detail-label">置信度：</span>
                  <span class="detail-value">{{ (step.confidence * 100).toFixed(1) }}%</span>
                </div>
                <div class="detail-row" v-if="step.locator_type">
                  <span class="detail-label">定位类型：</span>
                  <el-tag size="small" :type="getLocatorTypeTagType(step.locator_type)">
                    {{ getLocatorTypeLabel(step.locator_type) }}
                  </el-tag>
                </div>
                <div class="detail-row">
                  <span class="detail-label">耗时：</span>
                  <span class="detail-value">{{ step.duration.toFixed(2) }}s</span>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <div class="report-actions">
          <el-button @click="visible = false">关闭</el-button>
          <el-button type="primary" @click="resetAndRestart">重新执行</el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, CircleCheck, CircleClose, Warning } from '@element-plus/icons-vue'
import { batchLocatorApi, type BatchRecordReport } from '@/api/batchLocator'
import { useWebSocket } from '@/composables/useWebSocket'
import { getLocatorTypeLabel, getLocatorTypeTagType } from '@/utils/locatorType'

const props = defineProps<{
  modelValue: boolean
  caseId: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

// 任务配置
const config = ref({
  skip_existing: true,
  execute_precondition: true,
  use_mcp: true,
})

// 任务状态
const isRunning = ref(false)
const starting = ref(false)
const cancelling = ref(false)
const progress = ref(0)
const totalSteps = ref(0)
const completedSteps = ref(0)
const successCount = ref(0)
const failedCount = ref(0)
const currentStepInfo = ref('')
const report = ref<BatchRecordReport | null>(null)

// WebSocket
const { connect, disconnect, onMessage } = useWebSocket()

// 计算属性
const progressStatus = computed(() => {
  if (report.value?.status === 'failed') return 'exception'
  if (report.value?.status === 'completed') return 'success'
  return ''
})

const reportStatusText = computed(() => {
  if (!report.value) return ''
  const statusMap: Record<string, string> = {
    completed: '批量补充完成',
    failed: '批量补充失败',
    cancelled: '任务已取消',
  }
  return statusMap[report.value.status] || '未知状态'
})

// 监听对话框显示
watch(visible, (newVal) => {
  if (newVal) {
    resetState()
  }
})

// 重置状态
const resetState = () => {
  isRunning.value = false
  starting.value = false
  cancelling.value = false
  progress.value = 0
  totalSteps.value = 0
  completedSteps.value = 0
  successCount.value = 0
  failedCount.value = 0
  currentStepInfo.value = ''
  report.value = null
}

// 开始批量记录
const batchRecordCleanup = ref<(() => void) | null>(null)

const startBatchRecord = async () => {
  starting.value = true

  if (batchRecordCleanup.value) {
    batchRecordCleanup.value()
    batchRecordCleanup.value = null
  }

  try {
    // 启动任务
    const response = await batchLocatorApi.startBatchRecord(props.caseId, config.value)

    if (response.success) {
      isRunning.value = true
      ElMessage.success('批量补充任务已启动')

      // 连接WebSocket
      disconnect()
      connect(`batch_${props.caseId}`)

      // 监听WebSocket消息
      const cleanup = onMessage((message: any) => {
        if (message.type === 'batch_locator_progress') {
          handleProgressUpdate(message)
        }
      })
      batchRecordCleanup.value = cleanup

      // 轮询状态（备用）
      startStatusPolling()
    } else {
      ElMessage.error(response.message || '启动失败')
    }
  } catch (error: any) {
    console.error('启动批量记录失败:', error)
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    starting.value = false
  }
}

// 处理进度更新
const handleProgressUpdate = (data: any) => {
  if (data.type === 'start') {
    totalSteps.value = data.total_steps || 0
  } else if (data.type === 'step_complete') {
    completedSteps.value++
    progress.value = Math.round(data.progress || 0)
    currentStepInfo.value = `步骤 ${data.step_number}: ${data.message}`

    if (data.success) {
      successCount.value++
    } else {
      failedCount.value++
    }
  } else if (data.type === 'step_skip') {
    completedSteps.value++
    progress.value = Math.round(data.progress || 0)
  } else if (data.type === 'complete') {
    report.value = data.report
    isRunning.value = false
    disconnect()
    emit('success')
    ElMessage.success('批量补充完成')
  } else if (data.type === 'error') {
    ElMessage.error(data.error || '执行失败')
    isRunning.value = false
    disconnect()
    loadReport()
  }
}

// 轮询状态（备用方案）
let pollingTimer: NodeJS.Timeout | null = null

const startStatusPolling = () => {
  pollingTimer = setInterval(async () => {
    if (!isRunning.value) {
      stopStatusPolling()
      return
    }

    try {
      const status = await batchLocatorApi.getBatchRecordStatus(props.caseId)

      if (
        status.status === 'completed' ||
        status.status === 'failed' ||
        status.status === 'cancelled'
      ) {
        stopStatusPolling()
        loadReport()
      }
    } catch (error) {
      console.error('获取状态失败:', error)
    }
  }, 2000)
}

const stopStatusPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

// 加载报告
const loadReport = async () => {
  try {
    const reportData = await batchLocatorApi.getBatchRecordReport(props.caseId)
    report.value = reportData
    isRunning.value = false
    progress.value = 100

    if (reportData.status === 'completed') {
      emit('success')
    }
  } catch (error) {
    console.error('获取报告失败:', error)
  }
}

// 取消任务
const cancelBatchRecord = async () => {
  try {
    await ElMessageBox.confirm('确定要取消批量补充任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    cancelling.value = true

    const response = await batchLocatorApi.cancelBatchRecord(props.caseId)

    if (response.success) {
      ElMessage.success('任务已取消')
      stopStatusPolling()
      disconnect()
      loadReport()
    } else {
      ElMessage.error('取消失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('取消任务失败:', error)
      ElMessage.error('取消失败')
    }
  } finally {
    cancelling.value = false
  }
}

// 重置并重新执行
const resetAndRestart = () => {
  report.value = null
  resetState()
}

// 格式化时长
const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}秒`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${minutes}分${secs}秒`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}小时${minutes}分`
  }
}

// 组件卸载时清理
onUnmounted(() => {
  if (batchRecordCleanup.value) {
    batchRecordCleanup.value()
    batchRecordCleanup.value = null
  }
  stopStatusPolling()
  disconnect()
})
</script>

<style scoped lang="scss">
.batch-locator-dialog {
  padding: 20px 0;
}

.task-config {
  .form-tip {
    margin-left: 10px;
    color: #909399;
    font-size: 12px;
  }

  .config-actions {
    margin-top: 30px;
    text-align: right;
  }
}

.task-progress {
  .progress-header {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 30px;

    .loading-icon {
      font-size: 24px;
      color: #409eff;
      margin-right: 10px;
      animation: rotating 2s linear infinite;
    }

    .status-text {
      font-size: 16px;
      color: #303133;
    }
  }

  .main-progress {
    margin-bottom: 30px;
  }

  .progress-stats {
    display: flex;
    justify-content: space-around;
    margin-bottom: 20px;

    .stat-item {
      text-align: center;

      .stat-label {
        color: #909399;
        font-size: 14px;
      }

      .stat-value {
        display: block;
        font-size: 24px;
        font-weight: bold;
        color: #303133;
        margin-top: 5px;

        &.success {
          color: #67c23a;
        }

        &.error {
          color: #f56c6c;
        }
      }
    }
  }

  .current-step {
    text-align: center;
    margin-bottom: 20px;
    padding: 15px;
    background: #f5f7fa;
    border-radius: 4px;

    .step-label {
      color: #909399;
    }

    .step-action {
      color: #409eff;
      font-weight: 500;
    }
  }

  .progress-actions {
    text-align: center;
  }
}

.task-report {
  .report-header {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 30px;
    padding: 20px;
    border-radius: 8px;

    &.completed {
      background: #f0f9eb;
    }

    &.failed {
      background: #fef0f0;
    }

    &.cancelled {
      background: #fdf6ec;
    }

    .status-icon {
      font-size: 32px;
      margin-right: 10px;

      &.success {
        color: #67c23a;
      }

      &.error {
        color: #f56c6c;
      }

      &.warning {
        color: #e6a23c;
      }
    }

    .status-text {
      font-size: 18px;
      font-weight: 500;
    }
  }

  .report-stats {
    background: #f5f7fa;
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 20px;

    .stat-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;

      &:last-child {
        margin-bottom: 0;
      }

      .stat-label {
        color: #606266;
      }

      .stat-value {
        font-weight: 500;
        color: #303133;

        &.success {
          color: #67c23a;
        }

        &.error {
          color: #f56c6c;
        }

        &.info {
          color: #909399;
        }
      }
    }
  }

  .step-details {
    margin-bottom: 20px;

    h4 {
      margin-bottom: 15px;
      color: #303133;
    }

    .step-detail-content {
      padding: 10px;

      .detail-row {
        margin-bottom: 8px;

        .detail-label {
          color: #909399;
          display: inline-block;
          width: 100px;
        }

        .detail-value {
          color: #606266;
        }
      }
    }
  }

  .report-actions {
    text-align: right;
  }
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
