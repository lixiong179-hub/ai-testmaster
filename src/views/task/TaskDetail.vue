<template>
  <div class="task-detail">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">任务详情</span>
          <div class="header-actions">
            <el-button @click="refreshAll" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button @click="$router.back()">返回列表</el-button>
          </div>
        </div>
      </template>

      <!-- 任务基本信息 -->
      <div class="task-info" v-if="taskDetail">
        <el-row :gutter="20">
          <el-col :span="8">
            <div class="info-item">
              <label>任务名称：</label>
              <span>{{ taskDetail.task_name }}</span>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="info-item">
              <label>任务状态：</label>
              <el-tag :type="taskStatusColor(taskDetail.status)" effect="dark" size="large">
                {{ taskStatusText(taskDetail.status) }}
              </el-tag>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="info-item">
              <label>创建时间：</label>
              <span>{{ formatTime(taskDetail.create_time) }}</span>
            </div>
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-top: 15px">
          <el-col :span="8">
            <div class="info-item">
              <label>开始时间：</label>
              <span>{{ taskDetail.start_time ? formatTime(taskDetail.start_time) : '-' }}</span>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="info-item">
              <label>结束时间：</label>
              <span>{{ taskDetail.end_time ? formatTime(taskDetail.end_time) : '-' }}</span>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="info-item">
              <label>执行用户：</label>
              <span>{{ taskDetail.executor_id || '-' }}</span>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 加载状态 -->
      <div v-if="!taskDetail && !loading" class="empty-state">
        <el-empty description="未找到任务信息" />
      </div>

      <!-- 执行进度 -->
      <div class="execution-progress" style="margin-top: 20px" v-if="taskDetail">
        <div class="progress-header">
          <span class="progress-label">执行进度</span>
          <span class="progress-time" v-if="taskDetail.status === 1">
            <el-icon class="is-loading"><Loading /></el-icon>
            执行中...
          </span>
        </div>
        <el-progress
          :percentage="taskDetail.progress || 0"
          :stroke-width="20"
          :color="getProgressColor(taskDetail.progress)"
          :status="getProgressStatus()"
          :striped="taskDetail.status === 1"
          :striped-flow="taskDetail.status === 1"
        />
        <div class="progress-stats">
          <div class="stat-item">
            <span class="stat-value">{{ taskDetail.total_count || 0 }}</span>
            <span class="stat-label">总用例</span>
          </div>
          <div class="stat-item success">
            <span class="stat-value">{{ taskDetail.success_count || 0 }}</span>
            <span class="stat-label">成功</span>
          </div>
          <div class="stat-item danger">
            <span class="stat-value">{{ taskDetail.fail_count || 0 }}</span>
            <span class="stat-label">失败</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ taskPassRate }}%</span>
            <span class="stat-label">通过率</span>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="action-buttons" style="margin-top: 20px" v-if="taskDetail">
        <el-space>
          <el-button
            v-if="taskDetail.status === 0"
            type="success"
            @click="startTask"
            :loading="actionLoading"
          >
            <el-icon><VideoPlay /></el-icon>
            启动任务
          </el-button>
          <el-button
            v-if="taskDetail.status === 1"
            type="warning"
            @click="stopTask"
            :loading="actionLoading"
          >
            <el-icon><VideoPause /></el-icon>
            停止任务
          </el-button>
          <el-button @click="fetchTaskResults" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新结果
          </el-button>
          <el-button @click="exportResults" :disabled="taskResults.length === 0">
            <el-icon><Download /></el-icon>
            导出结果
          </el-button>
        </el-space>
        <div class="execution-mode-selector" v-if="taskDetail.status === 0">
          <span class="mode-label">执行模式：</span>
          <el-radio-group v-model="executionMode" size="small">
            <el-radio value="smart">智能模式（推荐）</el-radio>
            <el-radio value="realtime">实时识别模式</el-radio>
            <el-radio value="preprocess">预处理模式</el-radio>
            <el-radio value="mobile_smart">移动端智能模式</el-radio>
            <el-radio value="mobile_realtime">移动端实时模式</el-radio>
          </el-radio-group>
          <div class="mode-desc">
            <template v-if="executionMode === 'smart'">优先使用缓存定位，失败后AI实时识别</template>
            <template v-else-if="executionMode === 'realtime'"
              >直接执行，无需预先补充元素定位</template
            >
            <template v-else-if="executionMode === 'preprocess'"
              >需要先批量补充元素定位信息才能执行</template
            >
            <template v-else-if="executionMode === 'mobile_smart'"
              >移动端：优先缓存定位+AI兜底（ADB）</template
            >
            <template v-else-if="executionMode === 'mobile_realtime'"
              >移动端：AI实时识别（ADB）</template
            >
          </div>
          <div
            v-if="executionMode.startsWith('mobile_')"
            class="mobile-device-selector"
            style="margin-top: 8px"
          >
            <span class="mode-label">目标设备：</span>
            <el-select
              v-model="mobileDeviceId"
              placeholder="选择已连接的设备"
              :loading="loadingDevices"
              @focus="loadConnectedDevices"
              size="small"
              style="width: 260px"
            >
              <el-option
                v-for="device in connectedDevices.filter((d) => d.state === 'device')"
                :key="device.udid"
                :label="`${device.model || device.udid} (${device.udid})`"
                :value="device.udid"
              />
            </el-select>
            <el-alert type="warning" :closable="false" style="margin-top: 8px; font-size: 12px">
              请确保设备已通过ADB连接，且已开启USB调试模式
            </el-alert>
          </div>
        </div>
      </div>

      <!-- 执行结果 -->
      <div class="execution-results" style="margin-top: 20px">
        <el-collapse v-model="activeNames">
          <el-collapse-item title="执行结果" name="results">
            <template #title>
              <span class="collapse-title">
                <el-icon><List /></el-icon>
                执行结果
                <el-tag size="small" type="info" style="margin-left: 8px">
                  {{ taskResults.length }} 条
                </el-tag>
              </span>
            </template>

            <el-table
              v-loading="loading"
              :data="taskResults"
              style="width: 100%"
              border
              stripe
              max-height="400"
            >
              <el-table-column prop="case_no" label="用例编号" width="130" />
              <el-table-column prop="case_id" label="用例ID" width="80" align="center" />
              <el-table-column prop="exec_status" label="执行状态" width="120" align="center">
                <template #default="scope">
                  <el-tag :type="execStatusColor(scope.row.exec_status)" effect="dark">
                    {{ execStatusText(scope.row.exec_status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="exec_time" label="执行时长" width="120">
                <template #default="scope">
                  {{ scope.row.exec_time || '-' }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="280" align="center">
                <template #default="scope">
                  <el-space>
                    <el-button type="info" size="small" link @click="viewCaseLog(scope.row)">
                      查看日志
                    </el-button>
                    <el-button
                      v-if="scope.row.screenshot_url"
                      type="primary"
                      size="small"
                      link
                      @click="viewScreenshot(scope.row)"
                    >
                      查看截图
                    </el-button>
                    <el-button
                      v-if="scope.row.error_msg"
                      type="danger"
                      size="small"
                      link
                      @click="viewError(scope.row)"
                    >
                      查看错误
                    </el-button>
                  </el-space>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 实时日志 -->
      <div class="execution-logs" style="margin-top: 20px">
        <el-collapse v-model="logActiveNames">
          <el-collapse-item title="执行日志" name="logs">
            <template #title>
              <span class="collapse-title">
                <el-icon><Document /></el-icon>
                执行日志
                <el-badge
                  v-if="executionLogs.length > 0"
                  :value="executionLogs.length"
                  type="primary"
                  style="margin-left: 8px"
                />
              </span>
            </template>

            <div class="log-toolbar">
              <el-button size="small" @click="clearLogs">
                <el-icon><Delete /></el-icon>
                清空日志
              </el-button>
              <el-button size="small" @click="exportLogs" :disabled="executionLogs.length === 0">
                <el-icon><Download /></el-icon>
                导出日志
              </el-button>
              <el-checkbox v-model="autoScroll" size="small" style="margin-left: 10px">
                自动滚动
              </el-checkbox>
            </div>

            <el-scrollbar style="height: 400px" ref="scrollbarRef">
              <div class="log-container" ref="logContainerRef">
                <div
                  v-for="(item, index) in executionLogs"
                  :key="index"
                  :class="['log-item', getLogItemClass(item.status)]"
                >
                  <div class="log-header">
                    <span class="log-time">{{ formatTime(item.timestamp) }}</span>
                    <span class="log-case" v-if="item.case_no">[{{ item.case_no }}]</span>
                    <el-tag :type="logStatusColor(item.status)" size="small">
                      {{ logStatusText(item.status) }}
                    </el-tag>
                  </div>
                  <div class="log-content">{{ item.log }}</div>
                </div>
                <div v-if="executionLogs.length === 0" class="empty-log">
                  <el-empty description="暂无执行日志" :image-size="80" />
                </div>
              </div>
            </el-scrollbar>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>

    <!-- 日志详情弹窗 -->
    <el-dialog v-model="logDialogVisible" title="用例执行日志" width="80%" top="5vh">
      <div class="case-log">
        <pre>{{ currentCaseLog }}</pre>
      </div>
      <template #footer>
        <el-button @click="copyLog">复制日志</el-button>
        <el-button type="primary" @click="logDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 截图预览弹窗 -->
    <el-dialog v-model="screenshotDialogVisible" title="失败截图" width="80%" top="5vh">
      <div class="screenshot-preview">
        <el-image
          v-if="currentScreenshot"
          :src="currentScreenshot"
          :preview-src-list="[currentScreenshot]"
          fit="contain"
          style="max-height: 70vh"
        />
        <div v-else class="no-screenshot">
          <el-empty description="暂无截图" />
        </div>
      </div>
    </el-dialog>

    <!-- 错误详情弹窗 -->
    <el-dialog v-model="errorDialogVisible" title="错误详情" width="60%" top="10vh">
      <div class="error-detail">
        <pre>{{ currentError }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  VideoPlay,
  VideoPause,
  Download,
  List,
  Document,
  Delete,
  Loading,
} from '@element-plus/icons-vue'
import { useTaskStore } from '../../store/task'
import { wsClient } from '../../utils/websocket'
import { getConnectedDevices } from '@/api/testExecution'

const route = useRoute()
const taskStore = useTaskStore()

// 任务ID
const taskId = computed(() => {
  return Number(route.params.taskId) || 0
})

// 项目ID
const projectId = computed(() => {
  return Number(route.query.project_id) || 0
})

// 加载状态
const loading = computed(() => taskStore.loading)
const actionLoading = ref(false)
const executionMode = ref<'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart'>(
  'smart'
)
const mobileDeviceId = ref<string>('')
const connectedDevices = ref<Array<{ udid: string; model?: string; state: string }>>([])
const loadingDevices = ref(false)

// 折叠面板
const activeNames = ref(['results'])
const logActiveNames = ref(['logs'])

// 自动滚动
const autoScroll = ref(true)

// 日志容器
const scrollbarRef = ref<any>(null)
const logContainerRef = ref<HTMLElement | null>(null)

// 弹窗状态
const logDialogVisible = ref(false)
const currentCaseLog = ref('')
const screenshotDialogVisible = ref(false)
const currentScreenshot = ref('')
const errorDialogVisible = ref(false)
const currentError = ref('')

// 轮询定时器
let pollTimer: number | null = null

// 任务详情
const taskDetail = computed(() => taskStore.taskDetail)

// 执行结果
const taskResults = computed(() => taskStore.taskResults)

// 执行日志
const executionLogs = computed(() => taskStore.executionLogs)

// 任务通过率
const taskPassRate = computed(() => {
  if (!taskDetail.value) return 0
  const { total_count, success_count } = taskDetail.value
  return total_count > 0 ? Math.round((success_count / total_count) * 100) : 0
})

// 任务状态文本
const taskStatusText = (status: number): string => {
  return taskStore.taskStatusText(status)
}

// 任务状态颜色
const taskStatusColor = (status: number): string => {
  return taskStore.taskStatusColor(status)
}

// 执行状态文本
const execStatusText = (status: number): string => {
  return taskStore.execStatusText(status)
}

// 执行状态颜色
const execStatusColor = (status: number): string => {
  return taskStore.execStatusColor(status)
}

// 日志状态文本
const logStatusText = (status: number): string => {
  return taskStore.logStatusText(status)
}

// 日志状态颜色
const logStatusColor = (status: number): string => {
  return taskStore.logStatusColor(status)
}

// 获取日志样式
const getLogItemClass = (status: number): string => {
  if (status === 3) return 'log-warning'
  if (status === 2) return 'log-error'
  if (status === 1) return 'log-success'
  return ''
}

// 进度颜色
const getProgressColor = (progress: number): string => {
  if (progress < 30) return '#409EFF'
  if (progress < 70) return '#E6A23C'
  return '#67C23A'
}

// 进度状态
const getProgressStatus = (): string | undefined => {
  if (!taskDetail.value) return undefined
  if (taskDetail.value.status === 3) return 'exception'
  if (taskDetail.value.status === 2 && taskDetail.value.fail_count === 0) return 'success'
  return undefined
}

// 格式化时间
const formatTime = (timestamp: string): string => {
  if (!timestamp) return '-'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// 获取任务详情
const fetchTaskDetail = async () => {
  try {
    await taskStore.fetchTaskDetail(taskId.value, projectId.value)
  } catch (error: any) {
    ElMessage.error(error.message || '获取任务详情失败')
  }
}

// 获取执行结果
const fetchTaskResults = async () => {
  try {
    await taskStore.fetchTaskResults(taskId.value, projectId.value)
  } catch (error: any) {
    console.error('获取执行结果失败:', error)
  }
}

// 刷新所有数据
const refreshAll = async () => {
  await Promise.all([fetchTaskDetail(), fetchTaskResults()])
}

// 启动任务
const loadConnectedDevices = async () => {
  loadingDevices.value = true
  try {
    const res = await getConnectedDevices()
    if (res.data?.code === 200) {
      connectedDevices.value = res.data.data || []
    }
  } catch (error) {
    console.error('获取设备列表失败:', error)
  } finally {
    loadingDevices.value = false
  }
}

const startTask = async () => {
  if (executionMode.value.startsWith('mobile_') && !mobileDeviceId.value) {
    ElMessage.warning('移动端模式请先选择目标设备')
    return
  }
  try {
    actionLoading.value = true
    await taskStore.startTask(
      taskId.value,
      projectId.value,
      executionMode.value,
      executionMode.value.startsWith('mobile_') ? mobileDeviceId.value : undefined
    )
    ElMessage.success('任务已启动')
    await fetchTaskDetail()
    // 开始轮询
    startPolling()
  } catch (error: any) {
    ElMessage.error(error.message || '启动任务失败')
  } finally {
    actionLoading.value = false
  }
}

// 停止任务
const stopTask = async () => {
  try {
    await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    actionLoading.value = true
    await taskStore.stopTask(taskId.value, projectId.value)
    ElMessage.success('任务已停止')
    await fetchTaskDetail()
    stopPolling()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '停止任务失败')
    }
  } finally {
    actionLoading.value = false
  }
}

// 导出结果
const exportResults = () => {
  if (taskResults.value.length === 0) {
    ElMessage.warning('暂无结果可导出')
    return
  }

  const results = taskResults.value.map((result) => ({
    case_no: result.case_no,
    case_id: result.case_id,
    exec_status: execStatusText(result.exec_status),
    exec_time: result.exec_time || '-',
    error_msg: result.error_msg || '',
  }))

  const csv = [
    ['用例编号', '用例ID', '执行状态', '执行时长', '错误信息'].join(','),
    ...results.map((r) =>
      [r.case_no, r.case_id, r.exec_status, r.exec_time, `"${r.error_msg}"`].join(',')
    ),
  ].join('\n')

  downloadFile(csv, `task_${taskId.value}_results.csv`, 'text/csv')
}

// 查看用例日志
const viewCaseLog = (result: any) => {
  currentCaseLog.value = result.exec_log || '暂无日志'
  logDialogVisible.value = true
}

// 复制日志
const copyLog = async () => {
  try {
    await navigator.clipboard.writeText(currentCaseLog.value)
    ElMessage.success('日志已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 查看截图
const viewScreenshot = (result: any) => {
  if (result.screenshot_url) {
    currentScreenshot.value = result.screenshot_url
    screenshotDialogVisible.value = true
  } else {
    ElMessage.warning('暂无截图')
  }
}

// 查看错误
const viewError = (result: any) => {
  currentError.value = result.error_msg || '暂无错误信息'
  errorDialogVisible.value = true
}

// 清空日志
const clearLogs = () => {
  taskStore.clearExecutionLogs()
}

// 导出日志
const exportLogs = () => {
  if (executionLogs.value.length === 0) {
    ElMessage.warning('暂无日志可导出')
    return
  }

  const logs = executionLogs.value
    .map((log) => {
      return `[${formatTime(log.timestamp)}] [${logStatusText(log.status)}] ${log.case_no ? `[${log.case_no}] ` : ''}${log.log}`
    })
    .join('\n')

  downloadFile(logs, `task_${taskId.value}_logs.txt`, 'text/plain')
}

// 下载文件
const downloadFile = (content: string, filename: string, type: string) => {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// 滚动到底部
const scrollToBottom = () => {
  if (autoScroll.value && logContainerRef.value) {
    nextTick(() => {
      if (scrollbarRef.value) {
        scrollbarRef.value.setScrollTop(logContainerRef.value!.scrollHeight)
      }
    })
  }
}

// 开始轮询
const startPolling = () => {
  if (pollTimer) return
  pollTimer = window.setInterval(async () => {
    await fetchTaskDetail()
    await fetchTaskResults()
    // 如果任务结束，停止轮询
    if (taskDetail.value && taskDetail.value.status !== 1) {
      stopPolling()
    }
  }, 3000)
}

// 停止轮询
const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// WebSocket 消息处理
const handleWsMessage = (data: any) => {
  // 处理不同类型的消息
  if (data.type === 'log') {
    taskStore.addExecutionLog({
      task_id: taskId.value,
      case_id: data.case_id,
      case_no: data.case_no,
      status: data.status,
      log: data.log,
      timestamp: data.timestamp || new Date().toISOString(),
    })
  } else if (data.type === 'progress') {
    taskStore.updateExecutionProgress({
      task_id: taskId.value,
      progress: data.progress,
      success_count: data.success_count,
      fail_count: data.fail_count,
      current_case: data.current_case,
      total_cases: data.total_cases,
      timestamp: new Date().toISOString(),
    })
  } else if (data.type === 'status') {
    taskStore.updateTaskStatus(taskId.value, data.status)
    if (data.status !== 1) {
      stopPolling()
    }
  }
}

// 监听日志变化
watch(
  () => taskStore.executionLogs.length,
  () => {
    scrollToBottom()
  }
)

// 监听任务状态
watch(
  () => taskDetail.value?.status,
  (newStatus) => {
    if (newStatus === 1) {
      startPolling()
    } else {
      stopPolling()
    }
  }
)

// 生命周期
onMounted(async () => {
  // 清除之前的状态
  taskStore.clearExecutionLogs()

  // 获取任务详情和执行结果
  await fetchTaskDetail()
  await fetchTaskResults()

  // 如果任务正在执行，开始轮询
  if (taskDetail.value?.status === 1) {
    startPolling()
  }

  // 连接WebSocket
  const token = localStorage.getItem('token')
  if (token) {
    wsClient.connect(taskId.value, projectId.value, token)
    wsClient.onMessage(handleWsMessage)
  }
})

// 组件卸载时
onUnmounted(() => {
  stopPolling()
  wsClient.offMessage(handleWsMessage)
  wsClient.disconnect()
  taskStore.clearExecutionLogs()
})
</script>

<style scoped>
.task-detail {
  padding: 20px;
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.task-info {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ef 100%);
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e4e8ef;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-item label {
  font-weight: 600;
  color: #606266;
  min-width: 80px;
}

.info-item span {
  color: #303133;
}

.empty-state {
  padding: 60px 0;
}

.execution-progress {
  background: #fff;
  padding: 15px;
  border-radius: 8px;
  border: 1px solid #e4e8ef;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.progress-label {
  font-weight: 600;
  color: #303133;
}

.progress-time {
  color: #409eff;
  display: flex;
  align-items: center;
  gap: 5px;
}

.progress-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.stat-item {
  text-align: center;
  padding: 10px 20px;
  border-radius: 8px;
  background: #f5f7fa;
}

.stat-item.success {
  background: #f0f9eb;
}

.stat-item.danger {
  background: #fef0f0;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.stat-item.success .stat-value {
  color: #67c23a;
}

.stat-item.danger .stat-value {
  color: #f56c6c;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.action-buttons {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 12px;
}

.execution-mode-selector {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.mode-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  line-height: 24px;
  white-space: nowrap;
}

.mode-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  padding-left: 72px;
}

.collapse-title {
  display: flex;
  align-items: center;
  font-weight: 600;
}

.log-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 10px;
}

.log-container {
  padding: 10px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  min-height: 350px;
}

.log-item {
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  background: #f5f7fa;
  border-left: 3px solid #909399;
}

.log-item.log-success {
  background: #f0f9eb;
  border-left-color: #67c23a;
}

.log-item.log-error {
  background: #fef0f0;
  border-left-color: #f56c6c;
}

.log-item.log-warning {
  background: #fdf6ec;
  border-left-color: #e6a23c;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  font-size: 12px;
  color: #909399;
}

.log-time {
  font-weight: 500;
}

.log-case {
  font-weight: 700;
  color: #409eff;
}

.log-content {
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
  color: #303133;
}

.empty-log {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.case-log {
  max-height: 60vh;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
}

.case-log pre {
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.screenshot-preview {
  text-align: center;
  background: #f5f7fa;
  padding: 20px;
  border-radius: 4px;
}

.no-screenshot {
  padding: 40px 0;
}

.error-detail {
  background: #fef0f0;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #fde2e2;
}

.error-detail pre {
  margin: 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #f56c6c;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
