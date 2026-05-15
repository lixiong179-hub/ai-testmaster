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
                <span class="env-account" v-if="env.username"
                  >账号: {{ env.username }} / 密码: ••••••</span
                >
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

        <div class="journey-actions">
          <el-button plain @click="goToTaskList">任务列表</el-button>
          <el-button plain @click="goToTestPointManagement">测试点管理</el-button>
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
        <el-button @click="showConfigDialog = true" icon="Setting"> 可见模式配置 </el-button>
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
              active: currentStepIndex === index,
              success: step.status === 'passed',
              failed: step.status === 'failed',
              running: step.status === 'running',
            }"
            @click="selectStep(index)"
          >
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-content">
              <div class="step-action">{{ step.display_action || step.description || step.action }}</div>
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
              <el-icon v-else-if="step.status === 'running'" class="is-loading"
                ><Loading
              /></el-icon>
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
              :class="{ active: currentStepIndex === index }"
              @click="selectStep(index)"
            >
              <div class="step-action">{{ step.display_action || step.description || step.action }}</div>
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
                height: currentStep.element_highlight.height + 'px',
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
        <div
          class="failure-analysis-detail"
          v-if="currentStepIndex >= 0 && failureAnalysisMap[currentStepIndex]"
        >
          <div class="analysis-header">
            <el-icon><Warning /></el-icon>
            <span>失败原因分析</span>
          </div>
          <div class="analysis-body">
            <p>
              <strong>建议类型：</strong>
              <el-tag
                :type="ISSUE_TYPE_COLORS[failureAnalysisMap[currentStepIndex].suggested_type]"
                size="small"
              >
                {{ ISSUE_TYPE_LABELS[failureAnalysisMap[currentStepIndex].suggested_type] }}
              </el-tag>
              <span class="confidence"
                >置信度:
                {{ (failureAnalysisMap[currentStepIndex].confidence * 100).toFixed(0) }}%</span
              >
            </p>
            <p>{{ failureAnalysisMap[currentStepIndex].reason }}</p>
            <div
              v-if="failureAnalysisMap[currentStepIndex].case_issue_indicators.length > 0"
              class="indicators"
            >
              <p><strong>用例问题指标：</strong></p>
              <ul>
                <li
                  v-for="(ind, i) in failureAnalysisMap[currentStepIndex].case_issue_indicators"
                  :key="i"
                >
                  {{ ind }}
                </li>
              </ul>
            </div>
            <div
              v-if="failureAnalysisMap[currentStepIndex].bug_issue_indicators.length > 0"
              class="indicators"
            >
              <p><strong>Bug问题指标：</strong></p>
              <ul>
                <li
                  v-for="(ind, i) in failureAnalysisMap[currentStepIndex].bug_issue_indicators"
                  :key="i"
                >
                  {{ ind }}
                </li>
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

          <el-tab-pane
            label="回放控制"
            name="replay"
            v-if="executionStatus?.status === 'completed'"
          >
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
    <el-dialog v-model="showConfigDialog" title="可见模式配置" width="600px">
      <el-form :model="visibilityConfig" label-width="150px">
        <el-form-item label="无头模式">
          <el-switch v-model="visibilityConfig.headless" active-text="启用" inactive-text="禁用" />
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
          <el-slider
            v-model="visibilityConfig.videoFps"
            :min="15"
            :max="60"
            :step="15"
            show-stops
          />
          <span>{{ visibilityConfig.videoFps }} fps</span>
        </el-form-item>

        <el-form-item label="MCP定位引擎">
          <el-switch v-model="useMcpMode" active-text="MCP" inactive-text="VLM" />
          <div style="margin-top: 4px; font-size: 12px; color: #909399">
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
          <div style="margin-top: 4px; font-size: 12px; color: #909399">
            <template v-if="executionMode === 'smart'">优先使用缓存定位，失败后AI实时识别</template>
            <template v-else-if="executionMode === 'realtime'"
              >直接执行，无需预先补充元素定位</template
            >
            <template v-else-if="executionMode === 'preprocess'"
              >需要先批量补充元素定位信息才能执行</template
            >
            <template v-else-if="executionMode === 'mobile_smart'"
              >移动端：优先使用缓存定位，失败后AI实时识别（ADB）</template
            >
            <template v-else-if="executionMode === 'mobile_realtime'"
              >移动端：直接执行，AI实时识别元素（ADB）</template
            >
          </div>
        </el-form-item>
        <el-form-item label="目标设备" v-if="executionMode.startsWith('mobile_')">
          <el-select
            v-model="mobileDeviceId"
            placeholder="选择已连接的设备"
            :loading="loadingDevices"
            @focus="loadConnectedDevices"
            style="width: 100%"
          >
            <el-option
              v-for="device in connectedDevices.filter((d) => d.state === 'device')"
              :key="device.udid"
              :label="`${device.model || device.udid} (${device.udid})`"
              :value="device.udid"
            />
          </el-select>
          <el-alert type="warning" :closable="false" style="margin-top: 8px">
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
import { ElMessage } from 'element-plus'
import {
  ArrowLeft,
  VideoPlay,
  VideoPause,
  CircleClose,
  CircleCheck,
  Loading,
  ArrowRight,
  MagicStick,
  Warning,
} from '@element-plus/icons-vue'
import {
  getExecutionStatus,
  getExecutionLogs,
  getStepScreenshot,
  getVisibilityConfig,
  updateVisibilityConfig,
  getConnectedDevices,
} from '@/api/testExecution'
import type { ExecutionMode } from '@/api/testExecution'
import testTaskApi from '@/api/testTask'
import request from '@/utils/request'
import { unwrapApiResponse } from '@/utils/api'
import { useExecutionControl } from '@/composables/useExecutionControl'
import { useExecutionWebSocket } from '@/composables/useExecutionWebSocket'
import { useVideoReplay } from '@/composables/useVideoReplay'
import {
  useFailureAnalysis,
  ISSUE_TYPE_LABELS,
  ISSUE_TYPE_COLORS,
} from '@/composables/useFailureAnalysis'

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
const saveConfigLoading = ref(false)
const showConfigDialog = ref(false)
const showScreenshotFullscreen = ref(false)
const viewMode = ref<'list' | 'timeline'>('list')
const screenshotType = ref<'before' | 'after'>('after')
const activeTab = ref('logs')
const logsContainer = ref<HTMLElement>()

// 可见模式配置
const visibilityConfig = ref({
  headless: true,
  recordVideo: false,
  videoFps: 30,
})
const videoResolution = ref('1280x720')

// 环境选择与初始化控制
const targetEnv = ref('test')
const autoInitEnabled = ref(true)
const executionMode = ref<ExecutionMode>('smart')
const mobileDeviceId = ref<string>('')
const connectedDevices = ref<Array<{ udid: string; model?: string; state: string }>>([])
const loadingDevices = ref(false)
const useMcpMode = ref(true)
const envOptions = ref<Array<{ name: string; url: string; username?: string }>>([])

function getTaskPayload() {
  return taskInfo.value?.task || taskInfo.value || null
}

function syncTaskInfoStatus(status: number) {
  if (!taskInfo.value) {
    return
  }

  if (taskInfo.value?.task) {
    taskInfo.value = {
      ...taskInfo.value,
      task: {
        ...taskInfo.value.task,
        status,
      },
    }
    return
  }

  taskInfo.value = {
    ...taskInfo.value,
    status,
  }
}

function buildExecutionStatusFallback() {
  const taskStatus = Number(getTaskPayload()?.status)
  const statusMap: Record<number, string> = {
    0: 'pending',
    1: 'running',
    2: 'completed',
    3: 'failed',
    4: 'stopped',
  }
  const fallbackStatus = statusMap[taskStatus]

  if (!fallbackStatus) {
    return null
  }

  return {
    status: fallbackStatus,
    current_step: Number(executionStatus.value?.current_step || 0),
    total_steps: Number(executionStatus.value?.total_steps || 0),
    estimated_time_remaining: executionStatus.value?.estimated_time_remaining,
  }
}

// ---- 数据加载方法 ----

const loadTaskInfo = async () => {
  try {
    const res = await testTaskApi.getTaskDetail(taskId.value)
    const body = unwrapApiResponse<any>(res)
    if (body.code === 200 && body.data) {
      taskInfo.value = body.data
      const taskData = body.data.task || body.data
      const projectId = taskData?.project_id

      if (projectId) {
        const projectRes = await request.get(`/api/v1/project/${projectId}`)
        const projectBody = unwrapApiResponse<any>(projectRes)
        if (projectBody.code === 200 && projectBody.data) {
          const projectData = projectBody.data
          const webEnvConfigs = projectData?.web_env_configs
          if (webEnvConfigs && typeof webEnvConfigs === 'object') {
            const options = Object.entries(webEnvConfigs)
              .map(([name, cfg]: [string, any]) => ({
                name,
                url: cfg?.url || '',
                username: cfg?.username || '',
              }))
              .filter((opt) => opt.url)
            envOptions.value = options
            if (options.some((o) => o.name === 'test')) {
              targetEnv.value = 'test'
            } else if (options.length > 0) {
              targetEnv.value = options[0].name
            }
          }
        }
      }
    }
    return taskInfo.value
  } catch (error) {
    console.error('加载任务信息失败:', error)
    ElMessage.error('加载任务信息失败')
    return null
  }
}

const loadExecutionStatus = async () => {
  try {
    const res = await getExecutionStatus(taskId.value)
    const body = unwrapApiResponse<any>(res)
    if (body.code === 200 && body.data) {
      executionStatus.value = body.data
    }
  } catch (error: any) {
    if (error?.response?.status === 404) {
      if (!getTaskPayload()) {
        await loadTaskInfo()
      }

      const fallbackStatus = buildExecutionStatusFallback()
      if (fallbackStatus) {
        executionStatus.value = fallbackStatus
      }
      return
    }
    console.error('加载执行状态失败:', error)
  }
}

const loadExecutionLogs = async () => {
  try {
    const res = await getExecutionLogs(taskId.value)
    const body = unwrapApiResponse<any>(res)
    if (body.code === 200) {
      executionLogs.value = body.data?.logs || []
      nextTick(() => {
        scrollToBottom()
      })
    }
  } catch (error) {
    console.error('加载执行日志失败:', error)
  }
}

const currentStep = computed(() => {
  return executionSteps.value[currentStepIndex.value]
})

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
    const body = unwrapApiResponse<any[]>(res)
    if (body.code === 200) {
      connectedDevices.value = body.data || []
    }
  } catch (error) {
    console.error('获取设备列表失败:', error)
  } finally {
    loadingDevices.value = false
  }
}

const scrollToBottom = () => {
  if (logsContainer.value) {
    logsContainer.value.scrollTop = logsContainer.value.scrollHeight
  }
}

// ---- Composables ----

// WebSocket实时更新（先初始化，因为执行控制依赖它）
const { connectWebSocketForRealtimeUpdate } = useExecutionWebSocket({
  taskId: () => taskId.value,
  executionSteps,
  currentStepIndex,
  executionLogs,
  executionStatus,
  loadStepScreenshot,
  scrollToBottom,
})

// 执行控制
const {
  controlLoading,
  startExecution,
  pauseExecution,
  resumeExecution,
  stopExecution,
} = useExecutionControl({
  taskId: () => taskId.value,
  executionStatus,
  visibilityConfig,
  targetEnv,
  autoInitEnabled,
  executionMode,
  mobileDeviceId,
  useMcpMode,
  syncTaskInfoStatus,
  loadTaskInfo,
  loadExecutionStatus,
  connectWebSocketForRealtimeUpdate: () => connectWebSocketForRealtimeUpdate(),
})

// 视频回放
const videoPlayer = ref<HTMLVideoElement>()
const {
  isVideoPlaying,
  videoCurrentTime,
  videoDuration,
  replaySpeed,
  toggleVideoPlay,
  seekVideo,
  onVideoTimeChange,
  startReplay,
  pauseReplay,
  stopReplay,
} = useVideoReplay({
  taskId: () => taskId.value,
  taskInfo,
  videoPlayer,
})

// 失败分析
const {
  failureAnalysisMap,
  analysisLoading,
  issueTypeMap,
  handleAnalyzeFailure,
  handleCorrectCase,
} = useFailureAnalysis({
  executionStatus,
})

// ---- 计算属性 ----

const progressPercentage = computed(() => {
  if (!executionStatus.value) return 0
  const currentStep = Number(executionStatus.value.current_step || 0)
  const totalSteps = Number(executionStatus.value.total_steps || 0)
  if (totalSteps <= 0) return 0
  return Math.round((currentStep / totalSteps) * 100)
})

const progressStatus = computed(() => {
  const status = executionStatus.value?.status
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  return ''
})

const statusText = computed(() => {
  const statusMap: Record<string, string> = {
    pending: '等待执行',
    running: '执行中',
    paused: '已暂停',
    completed: '执行完成',
    failed: '执行失败',
    stopped: '已停止',
  }
  return statusMap[executionStatus.value?.status] || '未知状态'
})

const statusTagType = computed(() => {
  const typeMap: Record<string, any> = {
    pending: 'info',
    running: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    stopped: 'info',
  }
  return typeMap[executionStatus.value?.status] || 'info'
})

// ---- 页面交互方法 ----

const selectStep = (index: number) => {
  currentStepIndex.value = index
}

const getStepStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    passed: 'success',
    failed: 'danger',
    running: 'primary',
    pending: 'info',
    skipped: 'warning',
  }
  return typeMap[status] || 'info'
}

const getStepStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    passed: '通过',
    failed: '失败',
    running: '执行中',
    pending: '等待',
    skipped: '跳过',
  }
  return textMap[status] || status
}

const getTimelineItemType = (status: string) => {
  const typeMap: Record<string, any> = {
    passed: 'success',
    failed: 'danger',
    running: 'primary',
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

const goBack = () => {
  goToTaskList()
}

const currentProjectId = computed(() => {
  const taskData = taskInfo.value?.task || taskInfo.value
  return Number(taskData?.project_id || route.query.project_id || 0)
})

const goToTaskList = () => {
  if (currentProjectId.value) {
    router.push(`/home/task/list/${currentProjectId.value}`)
    return
  }
  router.push('/home/project')
}

const goToTestPointManagement = () => {
  if (currentProjectId.value) {
    router.push({
      path: '/home/case/test-point-management',
      query: {
        projectId: String(currentProjectId.value),
      },
    })
    return
  }
  router.push('/home/case/test-point-management')
}

const saveVisibilityConfig = async () => {
  saveConfigLoading.value = true
  try {
    const [width, height] = videoResolution.value.split('x').map(Number)
    const res = await updateVisibilityConfig(
      'task',
      {
        headless: visibilityConfig.value.headless,
        recordVideo: visibilityConfig.value.recordVideo,
        videoResolution: [width, height],
        videoFps: visibilityConfig.value.videoFps,
      },
      taskId.value
    )

    const body = unwrapApiResponse<any>(res)
    if (body.code === 200) {
      ElMessage.success('配置已保存')
      showConfigDialog.value = false
    } else {
      ElMessage.error(body.message || '保存失败')
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
    const body = unwrapApiResponse<any>(res)
    if (body.code === 200 && body.data) {
      const config = body.data
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

// ---- 监听 ----

watch(screenshotType, () => {
  loadStepScreenshot()
})

watch(currentStepIndex, () => {
  loadStepScreenshot()
})

// ---- 生命周期 ----

const initializePage = async () => {
  await loadTaskInfo()
  await loadExecutionStatus()
  loadExecutionLogs()
  loadVisibilityConfig()
  connectWebSocketForRealtimeUpdate()
}

onMounted(() => {
  void initializePage()
})

onUnmounted(() => {
  // WebSocket断开由 useExecutionWebSocket 的 onUnmounted 自动处理
})
</script>

<style scoped lang="scss">
@import './TestExecution.scss';
</style>
