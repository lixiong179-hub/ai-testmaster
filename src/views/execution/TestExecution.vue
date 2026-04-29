<template>
  <div class="test-execution-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button @click="goBack" icon="ArrowLeft">返回</el-button>
        <h2 class="page-title">测试执行 - {{ taskInfo?.task_name || '加载中...' }}</h2>
      </div>
      <div class="header-right">
        <!-- 环境选择 + 初始化开关 -->
        <div class="execution-options">
          <el-select
            v-model="targetEnv"
            placeholder="选择环境"
            size="default"
            class="env-selector"
            :disabled="!envOptions.length"
          >
            <el-option
              v-for="env in envOptions"
              :key="env.name"
              :label="`${env.name} (${env.url})`"
              :value="env.name"
            >
              <div class="env-option">
                <span class="env-name">{{ env.name }}</span>
                <span class="env-url">{{ env.url }}</span>
                <span class="env-account" v-if="env.username">账号: {{ env.username }} / 密码: ••••••</span>
              </div>
            </el-option>
          </el-select>
          <el-tooltip content="执行前自动初始化（启动浏览器+导航+登录）" placement="bottom">
            <el-switch
              v-model="autoInitEnabled"
              active-text="自动初始化"
              inactive-text="跳过初始化"
              inline-prompt
              class="init-switch"
            />
          </el-tooltip>
        </div>

        <!-- 执行控制按钮 -->
        <el-button-group v-if="executionStatus">
          <el-button
            v-if="executionStatus.status === 'running'"
            type="warning"
            @click="pauseExecution"
            :loading="controlLoading"
          >
            <el-icon><VideoPause /></el-icon>暂停
          </el-button>
          <el-button
            v-if="executionStatus.status === 'paused'"
            type="success"
            @click="resumeExecution"
            :loading="controlLoading"
          >
            <el-icon><VideoPlay /></el-icon>恢复
          </el-button>
          <el-button
            v-if="['running', 'paused'].includes(executionStatus.status)"
            type="danger"
            @click="stopExecution"
            :loading="controlLoading"
          >
            <el-icon><CircleClose /></el-icon>停止
          </el-button>
          <el-button
            v-if="['pending', 'stopped', 'completed', 'failed'].includes(executionStatus.status)"
            type="primary"
            @click="startExecution"
            :loading="controlLoading"
          >
            <el-icon><VideoPlay /></el-icon>开始执行
          </el-button>
        </el-button-group>

        <!-- 可见模式配置 -->
        <el-button @click="showConfigDialog = true" icon="Setting">
          可见模式配置
        </el-button>
      </div>
    </div>

    <!-- 执行进度 -->
    <div class="execution-progress" v-if="executionStatus">
      <el-progress
        :percentage="progressPercentage"
        :status="progressStatus"
        :stroke-width="20"
        :text-inside="true"
      >
        <template #default="{ percentage }">
          <span class="progress-text">
            {{ executionStatus.current_step || 0 }} / {{ executionStatus.total_steps || 0 }} 步骤
            ({{ percentage }}%)
          </span>
        </template>
      </el-progress>
      <div class="progress-info">
        <el-tag :type="statusTagType">{{ statusText }}</el-tag>
        <span v-if="executionStatus.estimated_time_remaining" class="time-remaining">
          预计剩余: {{ formatTime(executionStatus.estimated_time_remaining) }}
        </span>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <!-- 左侧：步骤列表 -->
      <div class="steps-panel">
        <div class="panel-header">
          <h3>执行步骤</h3>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="list">列表</el-radio-button>
            <el-radio-button value="timeline">时间轴</el-radio-button>
          </el-radio-group>
        </div>

        <div class="steps-list" v-if="viewMode === 'list'">
          <div
            v-for="(step, index) in executionSteps"
            :key="index"
            class="step-item"
            :class="{
              'active': currentStepIndex === index,
              'success': step.status === 'passed',
              'failed': step.status === 'failed',
              'running': step.status === 'running'
            }"
            @click="selectStep(index)"
          >
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-content">
              <div class="step-action">{{ step.action }}</div>
              <div class="step-target" v-if="step.target">{{ step.target }}</div>
              <div class="step-status">
                <el-tag :type="getStepStatusType(step.status)" size="small">
                  {{ getStepStatusText(step.status) }}
                </el-tag>
                <span v-if="step.execution_time" class="execution-time">
                  {{ step.execution_time }}s
                </span>
              </div>
            </div>
            <div class="step-icon">
              <el-icon v-if="step.status === 'passed'"><CircleCheck /></el-icon>
              <el-icon v-else-if="step.status === 'failed'"><CircleClose /></el-icon>
              <el-icon v-else-if="step.status === 'running'" class="is-loading"><Loading /></el-icon>
              <el-icon v-else><ArrowRight /></el-icon>
            </div>
            <!-- 失败步骤操作按钮 -->
            <div class="step-actions" v-if="step.status === 'failed'">
              <el-tag
                v-if="issueTypeMap[index]"
                :type="ISSUE_TYPE_COLORS[issueTypeMap[index]]"
                size="small"
                class="issue-tag"
              >
                {{ ISSUE_TYPE_LABELS[issueTypeMap[index]] }}
              </el-tag>
              <el-button
                v-if="issueTypeMap[index] !== 'product_bug'"
                type="warning"
                size="small"
                @click.stop="handleCorrectCase(step, index)"
              >
                纠正用例
              </el-button>
              <el-button
                size="small"
                @click.stop="handleAnalyzeFailure(step, index)"
                :loading="analysisLoading"
              >
                分析失败
              </el-button>
            </div>
          </div>
        </div>

        <el-timeline v-else class="steps-timeline">
          <el-timeline-item
            v-for="(step, index) in executionSteps"
            :key="index"
            :type="getTimelineItemType(step.status)"
            :icon="getTimelineIcon(step.status)"
            :timestamp="step.timestamp"
          >
            <div
              class="timeline-step"
              :class="{ 'active': currentStepIndex === index }"
              @click="selectStep(index)"
            >
              <div class="step-action">{{ step.action }}</div>
              <div class="step-target" v-if="step.target">{{ step.target }}</div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 中间：截图展示 -->
      <div class="screenshot-panel">
        <div class="panel-header">
          <h3>执行截图</h3>
          <el-radio-group v-model="screenshotType" size="small">
            <el-radio-button value="before">执行前</el-radio-button>
            <el-radio-button value="after">执行后</el-radio-button>
          </el-radio-group>
        </div>

        <div class="screenshot-container">
          <div v-if="currentScreenshot" class="screenshot-wrapper">
            <img
              :src="currentScreenshot"
              alt="执行截图"
              class="screenshot-image"
              @click="showScreenshotFullscreen = true"
            />
            <!-- 元素高亮标注 -->
            <div
              v-if="currentStep?.element_highlight"
              class="element-highlight"
              :style="{
                left: currentStep.element_highlight.x + 'px',
                top: currentStep.element_highlight.y + 'px',
                width: currentStep.element_highlight.width + 'px',
                height: currentStep.element_highlight.height + 'px'
              }"
            ></div>
          </div>
          <el-empty v-else description="暂无截图" />
        </div>

        <!-- AI分析结果 -->
        <div class="ai-analysis" v-if="currentStep?.ai_analysis">
          <div class="analysis-header">
            <el-icon><MagicStick /></el-icon>
            <span>AI分析结果</span>
          </div>
          <div class="analysis-content">{{ currentStep.ai_analysis }}</div>
        </div>

        <!-- Bug问题警告 -->
        <el-alert
          v-if="currentStepIndex >= 0 && issueTypeMap[currentStepIndex] === 'product_bug'"
          title="这是Bug问题，不要修改用例！"
          description="执行步骤完全正确，但实际结果与预期不符。这可能是产品功能缺陷，请勿修改测试用例来掩盖Bug。"
          type="error"
          show-icon
          :closable="false"
          class="bug-warning-alert"
        />

        <!-- 失败分析详情 -->
        <div class="failure-analysis-detail" v-if="currentStepIndex >= 0 && failureAnalysisMap[currentStepIndex]">
          <div class="analysis-header">
            <el-icon><Warning /></el-icon>
            <span>失败原因分析</span>
          </div>
          <div class="analysis-body">
            <p><strong>建议类型：</strong>
              <el-tag :type="ISSUE_TYPE_COLORS[failureAnalysisMap[currentStepIndex].suggested_type]" size="small">
                {{ ISSUE_TYPE_LABELS[failureAnalysisMap[currentStepIndex].suggested_type] }}
              </el-tag>
              <span class="confidence">置信度: {{ (failureAnalysisMap[currentStepIndex].confidence * 100).toFixed(0) }}%</span>
            </p>
            <p>{{ failureAnalysisMap[currentStepIndex].reason }}</p>
            <div v-if="failureAnalysisMap[currentStepIndex].case_issue_indicators.length > 0" class="indicators">
              <p><strong>用例问题指标：</strong></p>
              <ul>
                <li v-for="(ind, i) in failureAnalysisMap[currentStepIndex].case_issue_indicators" :key="i">{{ ind }}</li>
              </ul>
            </div>
            <div v-if="failureAnalysisMap[currentStepIndex].bug_issue_indicators.length > 0" class="indicators">
              <p><strong>Bug问题指标：</strong></p>
              <ul>
                <li v-for="(ind, i) in failureAnalysisMap[currentStepIndex].bug_issue_indicators" :key="i">{{ ind }}</li>
              </ul>
            </div>
            <div class="issue-type-switch">
              <span>手动切换问题类型：</span>
              <el-radio-group v-model="issueTypeMap[currentStepIndex]" size="small">
                <el-radio-button value="case_issue">用例问题</el-radio-button>
                <el-radio-button value="product_bug">Bug问题</el-radio-button>
                <el-radio-button value="needs_review">待判断</el-radio-button>
              </el-radio-group>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：日志和视频 -->
      <div class="side-panel">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="执行日志" name="logs">
            <div class="logs-container" ref="logsContainer">
              <div
                v-for="(log, index) in executionLogs"
                :key="index"
                class="log-item"
                :class="log.level"
              >
                <span class="log-time">{{ formatLogTime(log.timestamp) }}</span>
                <span class="log-level">[{{ log.level.toUpperCase() }}]</span>
                <span class="log-message">{{ log.message }}</span>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="执行视频" name="video">
            <div class="video-container">
              <video
                v-if="videoUrl"
                :src="videoUrl"
                controls
                class="execution-video"
                ref="videoPlayer"
              ></video>
              <el-empty v-else description="暂无视频">
                <template #description>
                  <p>视频录制未启用或执行未完成</p>
                  <el-button type="primary" @click="showConfigDialog = true">
                    启用视频录制
                  </el-button>
                </template>
              </el-empty>
            </div>

            <!-- 视频控制 -->
            <div class="video-controls" v-if="videoUrl">
              <el-button-group>
                <el-button @click="seekVideo(-10)">
                  <el-icon><ArrowLeft /></el-icon> -10s
                </el-button>
                <el-button @click="toggleVideoPlay">
                  <el-icon><VideoPlay v-if="!isVideoPlaying" /><VideoPause v-else /></el-icon>
                  {{ isVideoPlaying ? '暂停' : '播放' }}
                </el-button>
                <el-button @click="seekVideo(10)">
                  +10s <el-icon><ArrowRight /></el-icon>
                </el-button>
              </el-button-group>

              <el-slider
                v-model="videoCurrentTime"
                :max="videoDuration"
                @change="onVideoTimeChange"
                class="video-progress"
              />
            </div>
          </el-tab-pane>

          <el-tab-pane label="回放控制" name="replay" v-if="executionStatus?.status === 'completed'">
            <div class="replay-controls">
              <el-button-group>
                <el-button @click="startReplay" type="primary">
                  <el-icon><VideoPlay /></el-icon>开始回放
                </el-button>
                <el-button @click="pauseReplay">
                  <el-icon><VideoPause /></el-icon>暂停
                </el-button>
                <el-button @click="stopReplay">
                  <el-icon><CircleClose /></el-icon>停止
                </el-button>
              </el-button-group>

              <div class="replay-speed">
                <span>回放速度:</span>
                <el-slider v-model="replaySpeed" :min="0.5" :max="2" :step="0.5" show-stops />
                <span>{{ replaySpeed }}x</span>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 可见模式配置对话框 -->
    <el-dialog
      v-model="showConfigDialog"
      title="可见模式配置"
      width="600px"
    >
      <el-form :model="visibilityConfig" label-width="150px">
        <el-form-item label="无头模式">
          <el-switch
            v-model="visibilityConfig.headless"
            active-text="启用"
            inactive-text="禁用"
          />
          <div class="form-tip">禁用后浏览器窗口可见</div>
        </el-form-item>

        <el-form-item label="视频录制">
          <el-switch
            v-model="visibilityConfig.recordVideo"
            active-text="启用"
            inactive-text="禁用"
          />
          <div class="form-tip">启用后自动录制执行过程</div>
        </el-form-item>

        <el-form-item label="视频分辨率" v-if="visibilityConfig.recordVideo">
          <el-select v-model="videoResolution" placeholder="选择分辨率">
            <el-option label="1920x1080 (1080p)" value="1920x1080" />
            <el-option label="1280x720 (720p)" value="1280x720" />
            <el-option label="854x480 (480p)" value="854x480" />
          </el-select>
        </el-form-item>

        <el-form-item label="视频帧率" v-if="visibilityConfig.recordVideo">
          <el-slider v-model="visibilityConfig.videoFps" :min="15" :max="60" :step="15" show-stops />
          <span>{{ visibilityConfig.videoFps }} fps</span>
        </el-form-item>

        <el-form-item label="MCP定位引擎">
          <el-switch v-model="useMcpMode" active-text="MCP" inactive-text="VLM" />
          <div style="margin-top: 4px; font-size: 12px; color: #909399;">
            启用Playwright MCP定位引擎，支持更精准的元素识别和自愈
          </div>
        </el-form-item>
        <el-form-item label="执行模式">
            <el-radio-group v-model="executionMode">
              <el-radio value="smart">智能模式（推荐）</el-radio>
              <el-radio value="realtime">实时识别模式</el-radio>
              <el-radio value="preprocess">预处理模式</el-radio>
              <el-radio value="mobile_smart">移动端智能模式</el-radio>
              <el-radio value="mobile_realtime">移动端实时模式</el-radio>
            </el-radio-group>
            <div style="margin-top: 4px; font-size: 12px; color: #909399;">
              <template v-if="executionMode === 'smart'">优先使用缓存定位，失败后AI实时识别</template>
              <template v-else-if="executionMode === 'realtime'">直接执行，无需预先补充元素定位</template>
              <template v-else-if="executionMode === 'preprocess'">需要先批量补充元素定位信息才能执行</template>
              <template v-else-if="executionMode === 'mobile_smart'">移动端：优先使用缓存定位，失败后AI实时识别（ADB）</template>
              <template v-else-if="executionMode === 'mobile_realtime'">移动端：直接执行，AI实时识别元素（ADB）</template>
            </div>
          </el-form-item>
        <el-form-item label="目标设备" v-if="executionMode.startsWith('mobile_')">
          <el-select
            v-model="mobileDeviceId"
            placeholder="选择已连接的设备"
            :loading="loadingDevices"
            @focus="loadConnectedDevices"
            style="width: 100%;"
          >
            <el-option
              v-for="device in connectedDevices.filter(d => d.state === 'device')"
              :key="device.udid"
              :label="`${device.model || device.udid} (${device.udid})`"
              :value="device.udid"
            />
          </el-select>
          <el-alert
            type="warning"
            :closable="false"
            style="margin-top: 8px;"
          >
            请确保设备已通过ADB连接，且已开启USB调试模式
          </el-alert>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showConfigDialog = false">取消</el-button>
        <el-button type="primary" @click="saveVisibilityConfig" :loading="saveConfigLoading">
          保存配置
        </el-button>
      </template>
    </el-dialog>

    <!-- 全屏截图预览 -->
    <el-dialog
      v-model="showScreenshotFullscreen"
      title="截图预览"
      width="90%"
      class="screenshot-fullscreen-dialog"
    >
      <img :src="currentScreenshot" alt="截图预览" class="fullscreen-image" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, VideoPlay, VideoPause, CircleClose,
  CircleCheck, Loading, ArrowRight, MagicStick,
  Warning
} from '@element-plus/icons-vue'
import {
  startTestExecution, pauseTestExecution, resumeTestExecution,
  stopTestExecution, getExecutionStatus, getExecutionLogs,
  getStepScreenshot, getVisibilityConfig,
  updateVisibilityConfig, startReplay as startReplayApi, pauseReplay as pauseReplayApi, stopReplay as stopReplayApi,
  analyzeFailure, type FailureAnalysisResult, getConnectedDevices
} from '@/api/testExecution'
import testTaskApi from '@/api/testTask'
import request from '@/utils/request'
import { connectWebSocket, disconnectWebSocket } from '@/utils/websocket'

// 路由
const route = useRoute()
const router = useRouter()
const taskId = computed(() => Number(route.params.taskId))

// 状态
const taskInfo = ref<any>(null)
const executionStatus = ref<any>(null)
const executionSteps = ref<any[]>([])
const executionLogs = ref<any[]>([])
const currentStepIndex = ref(0)
const currentScreenshot = ref('')
const videoUrl = ref('')
const videoDuration = ref(0)
const isVideoPlaying = ref(false)
const videoCurrentTime = ref(0)
const controlLoading = ref(false)
const saveConfigLoading = ref(false)
const showConfigDialog = ref(false)
const showScreenshotFullscreen = ref(false)
const viewMode = ref<'list' | 'timeline'>('list')
const screenshotType = ref<'before' | 'after'>('after')
const activeTab = ref('logs')
const replaySpeed = ref(1)
const logsContainer = ref<HTMLElement>()
const videoPlayer = ref<HTMLVideoElement>()

// 可见模式配置
const visibilityConfig = ref({
  headless: true,
  recordVideo: false,
  videoFps: 30
})
const videoResolution = ref('1280x720')

// 环境选择与初始化控制
const targetEnv = ref('test')
const autoInitEnabled = ref(true)
const executionMode = ref<'preprocess' | 'realtime' | 'smart' | 'mobile_realtime' | 'mobile_smart'>('smart')
const mobileDeviceId = ref<string>('')
const connectedDevices = ref<Array<{ udid: string; model?: string; state: string }>>([])
const loadingDevices = ref(false)
const useMcpMode = ref(true)
const envOptions = ref<Array<{ name: string; url: string; username?: string }>>([])

// 失败分析相关状态
const failureAnalysisMap = ref<Record<number, FailureAnalysisResult>>({})
const analysisLoading = ref(false)
const issueTypeMap = ref<Record<number, 'case_issue' | 'product_bug' | 'needs_review'>>({})

const ISSUE_TYPE_LABELS: Record<string, string> = {
  case_issue: '用例问题',
  product_bug: 'Bug问题',
  needs_review: '待人工判断'
}

const ISSUE_TYPE_COLORS: Record<string, string> = {
  case_issue: 'warning',
  product_bug: 'danger',
  needs_review: 'info'
}

// WebSocket连接
let wsConnection: any = null

// 计算属性
const progressPercentage = computed(() => {
  if (!executionStatus.value) return 0
  const { current_step = 0, total_steps = 1 } = executionStatus.value
  return Math.round((current_step / total_steps) * 100)
})

const progressStatus = computed(() => {
  const status = executionStatus.value?.status
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
})

const statusText = computed(() => {
  const statusMap: Record<string, string> = {
    'pending': '等待执行',
    'running': '执行中',
    'paused': '已暂停',
    'completed': '执行完成',
    'failed': '执行失败',
    'stopped': '已停止'
  }
  return statusMap[executionStatus.value?.status] || '未知状态'
})

const statusTagType = computed(() => {
  const typeMap: Record<string, any> = {
    'pending': 'info',
    'running': 'primary',
    'paused': 'warning',
    'completed': 'success',
    'failed': 'danger',
    'stopped': 'info'
  }
  return typeMap[executionStatus.value?.status] || 'info'
})

const currentStep = computed(() => {
  return executionSteps.value[currentStepIndex.value]
})

// 方法
const loadTaskInfo = async () => {
  try {
    const res = await testTaskApi.getTaskDetail(taskId.value)
    if (res.data.code === 200) {
      taskInfo.value = res.data.data
      const taskData = res.data.data.task || res.data.data
      const projectId = taskData?.project_id

      if (projectId) {
        const projectRes = await request.get(`/api/v1/project/${projectId}`)
        if (projectRes?.data?.code === 200 && projectRes.data.data) {
          const projectData = projectRes.data.data
          const webEnvConfigs = projectData?.web_env_configs
          if (webEnvConfigs && typeof webEnvConfigs === 'object') {
            const options = Object.entries(webEnvConfigs).map(([name, cfg]: [string, any]) => ({
              name,
              url: cfg?.url || '',
              username: cfg?.username || ''
            })).filter(opt => opt.url)
            envOptions.value = options
            if (options.some(o => o.name === 'test')) {
              targetEnv.value = 'test'
            } else if (options.length > 0) {
              targetEnv.value = options[0].name
            }
          }
        }
      }
    }
  } catch (error) {
    console.error('加载任务信息失败:', error)
    ElMessage.error('加载任务信息失败')
  }
}

const loadExecutionStatus = async () => {
  try {
    const res = await getExecutionStatus(taskId.value)
    if (res.data.code === 200) {
      executionStatus.value = res.data.data
    }
  } catch (error) {
    console.error('加载执行状态失败:', error)
  }
}

const loadExecutionLogs = async () => {
  try {
    const res = await getExecutionLogs(taskId.value)
    if (res.data.code === 200) {
      executionLogs.value = res.data.data.logs || []
      nextTick(() => {
        scrollToBottom()
      })
    }
  } catch (error) {
    console.error('加载执行日志失败:', error)
  }
}

const loadStepScreenshot = async () => {
  if (!currentStep.value) return
  try {
    const res = await getStepScreenshot(
      taskId.value,
      currentStepIndex.value + 1,
      screenshotType.value
    )
    if (currentScreenshot.value && currentScreenshot.value.startsWith('blob:')) {
      URL.revokeObjectURL(currentScreenshot.value)
    }
    currentScreenshot.value = URL.createObjectURL(res.data)
  } catch (error) {
    console.error('加载截图失败:', error)
    if (currentScreenshot.value && currentScreenshot.value.startsWith('blob:')) {
      URL.revokeObjectURL(currentScreenshot.value)
    }
    currentScreenshot.value = ''
  }
}

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

const startExecution = async () => {
  if (executionMode.value.startsWith('mobile_') && !mobileDeviceId.value) {
    ElMessage.warning('移动端模式请先选择目标设备')
    return
  }
  controlLoading.value = true
  try {
    const res = await startTestExecution(taskId.value, {
      headless: visibilityConfig.value.headless,
      recordVideo: visibilityConfig.value.recordVideo,
      targetEnv: targetEnv.value,
      skipInit: !autoInitEnabled.value,
      executionMode: executionMode.value,
      mobileDeviceId: executionMode.value.startsWith('mobile_') ? mobileDeviceId.value : undefined,
      use_mcp: useMcpMode.value
    })
    if (res.data.code === 200) {
      ElMessage.success('开始执行')
      await loadExecutionStatus()
      connectWebSocketForRealtimeUpdate()
    } else {
      ElMessage.error(res.data.message || '开始执行失败')
    }
  } catch (error) {
    console.error('开始执行失败:', error)
    ElMessage.error('开始执行失败')
  } finally {
    controlLoading.value = false
  }
}

const pauseExecution = async () => {
  controlLoading.value = true
  try {
    const res = await pauseTestExecution(taskId.value)
    if (res.data.code === 200) {
      ElMessage.success('已暂停')
      await loadExecutionStatus()
    }
  } catch (error) {
    console.error('暂停失败:', error)
    ElMessage.error('暂停失败')
  } finally {
    controlLoading.value = false
  }
}

const resumeExecution = async () => {
  controlLoading.value = true
  try {
    const res = await resumeTestExecution(taskId.value)
    if (res.data.code === 200) {
      ElMessage.success('已恢复')
      await loadExecutionStatus()
    }
  } catch (error) {
    console.error('恢复失败:', error)
    ElMessage.error('恢复失败')
  } finally {
    controlLoading.value = false
  }
}

const stopExecution = async () => {
  try {
    await ElMessageBox.confirm('确定要停止执行吗？', '确认', {
      type: 'warning'
    })
    controlLoading.value = true
    const res = await stopTestExecution(taskId.value)
    if (res.data.code === 200) {
      ElMessage.success('已停止')
      await loadExecutionStatus()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('停止失败:', error)
      ElMessage.error('停止失败')
    }
  } finally {
    controlLoading.value = false
  }
}

const selectStep = (index: number) => {
  currentStepIndex.value = index
}

const getStepStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    'passed': 'success',
    'failed': 'danger',
    'running': 'primary',
    'pending': 'info',
    'skipped': 'warning'
  }
  return typeMap[status] || 'info'
}

const getStepStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'passed': '通过',
    'failed': '失败',
    'running': '执行中',
    'pending': '等待',
    'skipped': '跳过'
  }
  return textMap[status] || status
}

const getTimelineItemType = (status: string) => {
  const typeMap: Record<string, any> = {
    'passed': 'success',
    'failed': 'danger',
    'running': 'primary'
  }
  return typeMap[status] || ''
}

const getTimelineIcon = (status: string) => {
  if (status === 'passed') return CircleCheck
  if (status === 'failed') return CircleClose
  if (status === 'running') return Loading
  return undefined
}

const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}分${secs}秒`
}

const formatLogTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN')
}

const scrollToBottom = () => {
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

const goBack = () => {
  router.back()
}

const handleAnalyzeFailure = async (step: any, index: number) => {
  if (failureAnalysisMap.value[index]) return
  analysisLoading.value = true
  try {
    const resultId = step.result_id || step.id
    if (!resultId) {
      ElMessage.warning('无法获取执行结果ID，请稍后重试')
      analysisLoading.value = false
      return
    }
    const res = await analyzeFailure(resultId)
    const data = (res as any).data?.data || (res as any).data
    if (data) {
      failureAnalysisMap.value[index] = data
      issueTypeMap.value[index] = data.suggested_type
    }
  } catch (error: any) {
    console.error('分析失败原因出错:', error)
    ElMessage.error(error.response?.data?.detail || '分析失败原因出错')
  } finally {
    analysisLoading.value = false
  }
}

const handleCorrectCase = (step: any, index: number) => {
  if (issueTypeMap.value[index] === 'product_bug') {
    ElMessage.warning('这是Bug问题，不允许修改用例！')
    return
  }
  const caseId = step.case_id || executionStatus.value?.case_id
  if (!caseId) {
    ElMessage.warning('无法获取用例ID')
    return
  }
  const analysis = failureAnalysisMap.value[index]
  const query: Record<string, string> = {
    correction: 'true',
    stepIndex: String(index),
    issueType: issueTypeMap.value[index] || 'case_issue'
  }
  if (analysis) {
    query.failureReason = encodeURIComponent(analysis.reason || '')
    query.aiAnalysis = encodeURIComponent(analysis.ai_analysis || '')
  }
  router.push({
    path: `/home/case/detail/${caseId}`,
    query
  })
}

const saveVisibilityConfig = async () => {
  saveConfigLoading.value = true
  try {
    const [width, height] = videoResolution.value.split('x').map(Number)
    const res = await updateVisibilityConfig('task', {
      headless: visibilityConfig.value.headless,
      recordVideo: visibilityConfig.value.recordVideo,
      videoResolution: [width, height],
      videoFps: visibilityConfig.value.videoFps
    }, taskId.value)

    if (res.data.code === 200) {
      ElMessage.success('配置已保存')
      showConfigDialog.value = false
    } else {
      ElMessage.error(res.data.message || '保存失败')
    }
  } catch (error) {
    console.error('保存配置失败:', error)
    ElMessage.error('保存配置失败')
  } finally {
    saveConfigLoading.value = false
  }
}

const loadVisibilityConfig = async () => {
  try {
    const res = await getVisibilityConfig('task', taskId.value)
    if (res.data.code === 200) {
      const config = res.data.data
      visibilityConfig.value.headless = config.headless
      visibilityConfig.value.recordVideo = config.record_video
      visibilityConfig.value.videoFps = config.video_fps
      if (config.video_resolution) {
        videoResolution.value = `${config.video_resolution[0]}x${config.video_resolution[1]}`
      }
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

// WebSocket连接
const connectWebSocketForRealtimeUpdate = () => {
  wsConnection = connectWebSocket(`/ws/execution/${taskId.value}`, {
    onMessage: (data: any) => {
      if (data.type === 'step_update') {
        executionSteps.value = data.steps
        if (data.current_step) {
          currentStepIndex.value = data.current_step - 1
          loadStepScreenshot()
        }
      } else if (data.type === 'log') {
        executionLogs.value.push(data.log)
        nextTick(() => scrollToBottom())
      } else if (data.type === 'status_update') {
        executionStatus.value = data.status
      }
    },
    onError: (error: any) => {
      console.error('WebSocket错误:', error)
    }
  })
}

// 视频控制
const toggleVideoPlay = () => {
  if (videoPlayer.value) {
    if (isVideoPlaying.value) {
      videoPlayer.value.pause()
    } else {
      videoPlayer.value.play()
    }
    isVideoPlaying.value = !isVideoPlaying.value
  }
}

const seekVideo = (seconds: number) => {
  if (videoPlayer.value) {
    videoPlayer.value.currentTime += seconds
  }
}

const onVideoTimeChange = (value: number) => {
  if (videoPlayer.value) {
    videoPlayer.value.currentTime = value
  }
}

// 回放控制
const startReplay = async () => {
  try {
    const executionId = `${taskId.value}_${taskInfo.value?.case_id}`
    await startReplayApi(executionId)
    ElMessage.success('开始回放')
  } catch (error) {
    console.error('开始回放失败:', error)
    ElMessage.error('开始回放失败')
  }
}

const pauseReplay = async () => {
  try {
    const executionId = `${taskId.value}_${taskInfo.value?.case_id}`
    await pauseReplayApi(executionId)
    ElMessage.success('已暂停回放')
  } catch (error) {
    console.error('暂停回放失败:', error)
  }
}

const stopReplay = async () => {
  try {
    const executionId = `${taskId.value}_${taskInfo.value?.case_id}`
    await stopReplayApi(executionId)
    ElMessage.success('已停止回放')
  } catch (error) {
    console.error('停止回放失败:', error)
  }
}

// 监听
watch(screenshotType, () => {
  loadStepScreenshot()
})

watch(currentStepIndex, () => {
  loadStepScreenshot()
})

// 生命周期
onMounted(() => {
  loadTaskInfo()
  loadExecutionStatus()
  loadExecutionLogs()
  loadVisibilityConfig()
  connectWebSocketForRealtimeUpdate()
})

onUnmounted(() => {
  if (wsConnection) {
    disconnectWebSocket(wsConnection)
  }
})
</script>

<style scoped lang="scss">
.test-execution-page {
  padding: 20px;
  height: 100vh;
  display: flex;
  flex-direction: column;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 15px;

      .page-title {
        margin: 0;
        font-size: 20px;
      }
    }

    .header-right {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;

      .execution-options {
        display: flex;
        align-items: center;
        gap: 12px;

        .env-selector {
          width: 280px;
        }

        .init-switch {
          --el-switch-on-color: #409eff;
        }
      }
    }
  }

  .execution-progress {
    margin-bottom: 20px;
    padding: 15px;
    background: #f5f7fa;
    border-radius: 8px;

    .progress-text {
      font-size: 14px;
      color: #606266;
    }

    .progress-info {
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 15px;

      .time-remaining {
        color: #909399;
        font-size: 14px;
      }
    }
  }

  .main-content {
    flex: 1;
    display: flex;
    gap: 20px;
    overflow: hidden;

    .steps-panel {
      width: 300px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;

      .panel-header {
        padding: 15px;
        border-bottom: 1px solid #ebeef5;
        display: flex;
        justify-content: space-between;
        align-items: center;

        h3 {
          margin: 0;
          font-size: 16px;
        }
      }

      .steps-list {
        flex: 1;
        overflow-y: auto;
        padding: 10px;

        .step-item {
          display: flex;
          align-items: flex-start;
          padding: 12px;
          margin-bottom: 8px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.3s;

          &:hover {
            background: #f5f7fa;
          }

          &.active {
            background: #ecf5ff;
            border-left: 3px solid #409eff;
          }

          &.success {
            border-left: 3px solid #67c23a;
          }

          &.failed {
            border-left: 3px solid #f56c6c;
          }

          &.running {
            border-left: 3px solid #409eff;
            animation: pulse 2s infinite;
          }

          .step-number {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #e4e7ed;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            margin-right: 10px;
            flex-shrink: 0;
          }

          .step-content {
            flex: 1;
            min-width: 0;

            .step-action {
              font-weight: 500;
              margin-bottom: 4px;
              word-break: break-all;
            }

            .step-target {
              font-size: 12px;
              color: #909399;
              margin-bottom: 4px;
            }

            .step-status {
              display: flex;
              align-items: center;
              gap: 8px;

              .execution-time {
                font-size: 12px;
                color: #909399;
              }
            }
          }

          .step-icon {
            margin-left: 8px;
            font-size: 16px;

            .is-loading {
              animation: rotating 2s linear infinite;
            }
          }
        }
      }

      .steps-timeline {
        flex: 1;
        overflow-y: auto;
        padding: 15px;

        .timeline-step {
          cursor: pointer;
          padding: 8px;
          border-radius: 4px;
          transition: background 0.3s;

          &:hover {
            background: #f5f7fa;
          }

          &.active {
            background: #ecf5ff;
          }

          .step-action {
            font-weight: 500;
            margin-bottom: 4px;
          }

          .step-target {
            font-size: 12px;
            color: #909399;
          }
        }
      }
    }

    .screenshot-panel {
      flex: 1;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;

      .panel-header {
        padding: 15px;
        border-bottom: 1px solid #ebeef5;
        display: flex;
        justify-content: space-between;
        align-items: center;

        h3 {
          margin: 0;
          font-size: 16px;
        }
      }

      .screenshot-container {
        flex: 1;
        padding: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #f5f7fa;
        overflow: auto;

        .screenshot-wrapper {
          position: relative;
          max-width: 100%;
          max-height: 100%;

          .screenshot-image {
            max-width: 100%;
            max-height: 100%;
            border-radius: 4px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            cursor: zoom-in;
          }

          .element-highlight {
            position: absolute;
            border: 3px solid #f56c6c;
            border-radius: 4px;
            pointer-events: none;
            animation: highlight-pulse 2s infinite;
          }
        }
      }

      .ai-analysis {
        padding: 15px;
        border-top: 1px solid #ebeef5;
        background: #f5f7fa;

        .analysis-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
          color: #409eff;
          font-weight: 500;
        }

        .analysis-content {
          color: #606266;
          line-height: 1.6;
        }
      }
    }

    .side-panel {
      width: 350px;
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
      display: flex;
      flex-direction: column;

      :deep(.el-tabs) {
        flex: 1;
        display: flex;
        flex-direction: column;

        .el-tabs__content {
          flex: 1;
          overflow: auto;
        }
      }

      .logs-container {
        height: 100%;
        overflow-y: auto;
        padding: 10px;
        font-family: 'Courier New', monospace;
        font-size: 12px;
        line-height: 1.6;

        .log-item {
          margin-bottom: 4px;
          padding: 4px;
          border-radius: 3px;

          &.info {
            color: #409eff;
          }

          &.success {
            color: #67c23a;
          }

          &.warning {
            color: #e6a23c;
          }

          &.error {
            color: #f56c6c;
            background: #fef0f0;
          }

          .log-time {
            color: #909399;
            margin-right: 8px;
          }

          .log-level {
            font-weight: bold;
            margin-right: 8px;
          }
        }
      }

      .video-container {
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 10px;

        .execution-video {
          max-width: 100%;
          max-height: 300px;
          border-radius: 4px;
        }
      }

      .video-controls {
        padding: 10px;
        border-top: 1px solid #ebeef5;

        .video-progress {
          margin-top: 10px;
        }
      }

      .replay-controls {
        padding: 20px;

        .replay-speed {
          margin-top: 20px;
          display: flex;
          align-items: center;
          gap: 10px;

          .el-slider {
            flex: 1;
          }
        }
      }
    }
  }

  .form-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
  }

  .env-option {
    display: flex;
    align-items: center;
    gap: 8px;

    .env-name {
      font-weight: 600;
      color: #303133;
      min-width: 50px;
    }

    .env-url {
      color: #606266;
      font-size: 12px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 160px;
    }

    .env-account {
      color: #909399;
      font-size: 11px;
      margin-left: auto;
    }
  }
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
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

@keyframes highlight-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(245, 108, 108, 0.4);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(245, 108, 108, 0);
  }
}

.screenshot-fullscreen-dialog {
  :deep(.el-dialog__body) {
    padding: 0;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  .fullscreen-image {
    max-width: 100%;
    max-height: 80vh;
  }
}

.step-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: 8px;
  flex-shrink: 0;
}

.issue-tag {
  flex-shrink: 0;
}

.bug-warning-alert {
  margin: 12px 0;
}

.failure-analysis-detail {
  margin: 12px 0;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;

  .analysis-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    background: #f5f7fa;
    font-weight: 600;
    font-size: 14px;
  }

  .analysis-body {
    padding: 12px 16px;
    font-size: 13px;
    line-height: 1.8;

    .confidence {
      margin-left: 8px;
      color: #909399;
      font-size: 12px;
    }

    .indicators {
      margin: 8px 0;
      padding-left: 16px;

      ul {
        margin: 4px 0;
        padding-left: 16px;

        li {
          color: #606266;
          font-size: 12px;
        }
      }
    }

    .issue-type-switch {
      margin-top: 12px;
      padding-top: 10px;
      border-top: 1px dashed #e4e7ed;
      display: flex;
      align-items: center;
      gap: 8px;
    }
  }
}
</style>
