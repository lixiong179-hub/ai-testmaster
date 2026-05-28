<template>
  <div class="ai-parse-loading" v-if="visible">
    <div class="loading-overlay" @click.self="handleOverlayClick">
      <div class="loading-card">
        <div class="loading-header">
          <div class="ai-icon">
            <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="aiGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#409eff" />
                  <stop offset="50%" stop-color="#66b1ff" />
                  <stop offset="100%" stop-color="#8cc5ff" />
                </linearGradient>
                <linearGradient id="aiGradient2" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#67c23a" />
                  <stop offset="100%" stop-color="#95d475" />
                </linearGradient>
              </defs>
              <g class="ai-circuit">
                <circle
                  cx="32"
                  cy="32"
                  r="24"
                  stroke="url(#aiGradient)"
                  stroke-width="2"
                  fill="none"
                  class="pulse-circle"
                />
                <circle
                  cx="32"
                  cy="32"
                  r="16"
                  stroke="url(#aiGradient2)"
                  stroke-width="2"
                  fill="none"
                  class="rotate-circle"
                />
                <circle cx="32" cy="12" r="4" fill="url(#aiGradient)" class="dot-1" />
                <circle cx="52" cy="32" r="4" fill="url(#aiGradient)" class="dot-2" />
                <circle cx="32" cy="52" r="4" fill="url(#aiGradient)" class="dot-3" />
                <circle cx="12" cy="32" r="4" fill="url(#aiGradient)" class="dot-4" />
              </g>
              <g class="ai-core">
                <circle cx="32" cy="32" r="8" fill="url(#aiGradient)" class="core-pulse" />
                <path
                  d="M32 24 L32 40 M24 32 L40 32 M26.3 26.3 L37.7 37.7 M37.7 26.3 L26.3 37.7"
                  stroke="white"
                  stroke-width="2"
                  stroke-linecap="round"
                  class="core-brain"
                />
              </g>
            </svg>
          </div>
          <div class="loading-title">
            <h3>{{ currentStep.title }}</h3>
            <p class="loading-subtitle">{{ currentStep.description }}</p>
          </div>
        </div>
        <div class="loading-progress">
          <div class="progress-bar-container">
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: progress + '%' }">
                <div class="progress-shine"></div>
              </div>
            </div>
            <div class="progress-percentage">{{ Math.round(progress) }}%</div>
          </div>
          <div class="steps-indicator">
            <div v-for="(step, index) in steps" :key="index" class="step-item">
              <div
                class="step-icon"
                :class="{ active: index <= currentStepIndex, completed: index < currentStepIndex }"
              >
                <el-icon v-if="index < currentStepIndex"><Check /></el-icon>
                <span v-else-if="index === currentStepIndex"
                  ><el-icon class="loading-icon"><Loading /></el-icon
                ></span>
                <span v-else>{{ index + 1 }}</span>
              </div>
              <div class="step-info">
                <div class="step-name">{{ step.title }}</div>
              </div>
              <div
                v-if="index < steps.length - 1"
                class="step-line"
                :class="{ active: index < currentStepIndex }"
              ></div>
            </div>
          </div>
        </div>
        <div class="loading-details">
          <div class="detail-item">
            <span class="detail-label">解析模式</span
            ><span class="detail-value">{{ parseMode === 'text' ? '文本模型' : 'AI视觉' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">处理进度</span
            ><span class="detail-value">{{ processedCount }} / {{ totalCount }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">耗时</span
            ><span class="detail-value">{{ elapsedTime }}</span>
          </div>
        </div>
        <div class="loading-tips" v-if="tips.length > 0">
          <div class="tip-icon">💡</div>
          <div class="tip-text">{{ currentTip }}</div>
        </div>
        <div class="loading-actions" v-if="showCancelButton">
          <el-button type="default" size="default" @click="handleCancel">取消解析</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Check, Loading } from '@element-plus/icons-vue'

interface ParseStep {
  title: string
  description: string
  minProgress: number
  maxProgress: number
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    parseMode?: 'text' | 'vision'
    totalCount?: number
    processedCount?: number
    showCancelButton?: boolean
  }>(),
  { parseMode: 'text', totalCount: 0, processedCount: 0, showCancelButton: false }
)
const emit = defineEmits<{ cancel: []; close: [] }>()

const currentStepIndex = ref(0)
const customProgress = ref(0)
const startTime = ref<Date | null>(null)
const elapsedSeconds = ref(0)
let timer: number | null = null
let tipTimer: number | null = null
let currentTipIndex = ref(0)

const steps = computed((): ParseStep[] => [
  {
    title: '初始化解析引擎',
    description: props.parseMode === 'text' ? '加载 OCR 文本提取模块' : '加载 AI 视觉识别模型',
    minProgress: 0,
    maxProgress: 15,
  },
  {
    title: '读取并处理图片',
    description: '加载原型图，预处理图像数据',
    minProgress: 15,
    maxProgress: 35,
  },
  {
    title: props.parseMode === 'text' ? 'OCR 文本提取' : '视觉元素识别',
    description:
      props.parseMode === 'text' ? '识别图片中的文字和位置信息' : '识别页面元素、按钮、输入框等',
    minProgress: 35,
    maxProgress: 65,
  },
  {
    title: 'AI 智能解析',
    description: '调用 DeepSeek AI 分析页面结构和交互逻辑',
    minProgress: 65,
    maxProgress: 90,
  },
  {
    title: '保存解析结果',
    description: '结构化存储 UI Specification 数据',
    minProgress: 90,
    maxProgress: 100,
  },
])

const tips = [
  '提示：首次解析可能需要更长时间，后续解析会更快',
  '提示：文本模式解析速度较快，建议优先使用',
  '提示：视觉模式能识别更复杂的页面元素，但消耗更多 API',
  '提示：解析完成后可以自动生成测试用例',
  '提示：您可以随时查看解析进度和状态',
]
const currentTip = computed(() => tips[currentTipIndex.value])
const progress = computed(() => {
  if (props.processedCount !== undefined && props.totalCount && props.totalCount > 0) {
    const realProgress = Math.min(100, (props.processedCount / props.totalCount) * 100)
    return Math.max(customProgress.value, realProgress)
  }
  return customProgress.value
})
const currentStep = computed(
  () =>
    steps.value.find((s) => progress.value >= s.minProgress && progress.value < s.maxProgress) ||
    steps.value[steps.value.length - 1]
)
const elapsedTime = computed(() => {
  const m = Math.floor(elapsedSeconds.value / 60)
  const s = elapsedSeconds.value % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
})

const updateProgress = () => {
  const step = currentStep.value
  const sp = (progress.value - step.minProgress) / (step.maxProgress - step.minProgress)
  if (sp < 0.9 && customProgress.value < 95) {
    customProgress.value = Math.min(customProgress.value + Math.random() * 2 + 0.5, 95)
  }
}
const updateElapsedTime = () => {
  if (startTime.value) {
    elapsedSeconds.value = Math.floor((Date.now() - startTime.value.getTime()) / 1000)
  }
}
const rotateTip = () => {
  currentTipIndex.value = (currentTipIndex.value + 1) % tips.length
}
const handleCancel = () => {
  emit('cancel')
}
const handleOverlayClick = () => {}

onMounted(() => {
  if (props.visible) {
    startTime.value = new Date()
    timer = window.setInterval(() => {
      updateProgress()
      updateElapsedTime()
    }, 500)
    tipTimer = window.setInterval(rotateTip, 5000)
  }
})
onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (tipTimer) {
    clearInterval(tipTimer)
    tipTimer = null
  }
})
</script>

<style scoped lang="scss">
@use './AIParseLoading.scss';
</style>
