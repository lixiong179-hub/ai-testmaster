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
                <span v-else-if="index === currentStepIndex">
                  <el-icon class="loading-icon"><Loading /></el-icon>
                </span>
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
            <span class="detail-label">解析模式</span>
            <span class="detail-value">{{ parseMode === 'text' ? '文本模型' : 'AI视觉' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">处理进度</span>
            <span class="detail-value">{{ processedCount }} / {{ totalCount }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">耗时</span>
            <span class="detail-value">{{ elapsedTime }}</span>
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

const props = defineProps<{
  visible: boolean
  parseMode?: 'text' | 'vision'
  totalCount?: number
  processedCount?: number
  showCancelButton?: boolean
}>()

const emit = defineEmits<{
  cancel: []
  close: []
}>()

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
    return Math.min(100, (props.processedCount / props.totalCount) * 100)
  }
  return customProgress.value
})

const currentStep = computed(() => {
  const step = steps.value.find(
    (s) => progress.value >= s.minProgress && progress.value < s.maxProgress
  )
  return step || steps.value[steps.value.length - 1]
})

const elapsedTime = computed(() => {
  const minutes = Math.floor(elapsedSeconds.value / 60)
  const seconds = elapsedSeconds.value % 60
  return minutes > 0 ? `${minutes}分${seconds}秒` : `${seconds}秒`
})

const updateProgress = () => {
  const step = currentStep.value
  const stepProgress = (progress.value - step.minProgress) / (step.maxProgress - step.minProgress)

  if (stepProgress < 0.9 && customProgress.value < 95) {
    const increment = Math.random() * 2 + 0.5
    customProgress.value = Math.min(customProgress.value + increment, 95)
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

<style scoped>
.ai-parse-loading {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.loading-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  max-width: 520px;
  width: 100%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: cardIn 0.3s ease-out;
}

@keyframes cardIn {
  from {
    opacity: 0;
    transform: scale(0.9) translateY(20px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.loading-header {
  text-align: center;
  margin-bottom: 32px;
}

.ai-icon {
  width: 100px;
  height: 100px;
  margin: 0 auto 20px;
}

.ai-icon svg {
  width: 100%;
  height: 100%;
}

.pulse-circle {
  animation: pulse 2s ease-in-out infinite;
  transform-origin: center;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
}

.rotate-circle {
  animation: rotate 8s linear infinite;
  transform-origin: center;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.dot-1 {
  animation: dotPulse1 1.5s ease-in-out infinite;
}

.dot-2 {
  animation: dotPulse2 1.5s ease-in-out infinite;
}

.dot-3 {
  animation: dotPulse3 1.5s ease-in-out infinite;
}

.dot-4 {
  animation: dotPulse4 1.5s ease-in-out infinite;
}

@keyframes dotPulse1 {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(0.8);
  }
  25% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@keyframes dotPulse2 {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@keyframes dotPulse3 {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(0.8);
  }
  75% {
    opacity: 1;
    transform: scale(1.2);
  }
}

@keyframes dotPulse4 {
  0%,
  100% {
    opacity: 0.4;
    transform: scale(0.8);
  }
  100% {
    opacity: 1;
    transform: scale(1.2);
  }
}

.core-pulse {
  animation: corePulse 2s ease-in-out infinite;
  transform-origin: center;
}

@keyframes corePulse {
  0%,
  100% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.1);
  }
}

.core-brain {
  animation: brainPulse 2s ease-in-out infinite;
}

@keyframes brainPulse {
  0%,
  100% {
    opacity: 0.7;
  }
  50% {
    opacity: 1;
  }
}

.loading-title h3 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1a1d21;
  margin-bottom: 6px;
}

.loading-subtitle {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
}

.loading-progress {
  margin-bottom: 24px;
}

.progress-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.progress-track {
  flex: 1;
  height: 8px;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #66b1ff, #409eff);
  background-size: 200% 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
  animation: gradientMove 2s linear infinite;
  position: relative;
}

@keyframes gradientMove {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 200% 50%;
  }
}

.progress-shine {
  position: absolute;
  top: 0;
  left: -50%;
  width: 50%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.5), transparent);
  animation: shine 1.5s ease-in-out infinite;
}

@keyframes shine {
  0% {
    left: -50%;
  }
  100% {
    left: 100%;
  }
}

.progress-percentage {
  font-size: 16px;
  font-weight: 600;
  color: #409eff;
  min-width: 50px;
  text-align: right;
}

.steps-indicator {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.step-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f2f5;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  color: #909399;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.step-icon.active {
  background: linear-gradient(135deg, #409eff, #66b1ff);
  color: white;
}

.step-icon.completed {
  background: linear-gradient(135deg, #67c23a, #95d475);
  color: white;
}

.step-icon .loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.step-info {
  flex: 1;
}

.step-name {
  font-size: 14px;
  font-weight: 500;
  color: #1a1d21;
}

.step-line {
  width: 2px;
  height: 20px;
  background: #f0f2f5;
  margin-left: 15px;
  flex-shrink: 0;
}

.step-line.active {
  background: linear-gradient(180deg, #67c23a, #409eff);
}

.loading-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 20px;
  padding: 16px;
  background: #f8fafc;
  border-radius: 8px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: center;
}

.detail-label {
  font-size: 12px;
  color: #909399;
}

.detail-value {
  font-size: 14px;
  font-weight: 600;
  color: #1a1d21;
}

.loading-tips {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px;
  background: #f0f9ff;
  border-left: 4px solid #409eff;
  border-radius: 4px;
  margin-bottom: 20px;
}

.tip-icon {
  font-size: 18px;
  line-height: 1.4;
}

.tip-text {
  font-size: 13px;
  color: #409eff;
  line-height: 1.6;
}

.loading-actions {
  display: flex;
  justify-content: center;
}

@media (max-width: 640px) {
  .loading-card {
    padding: 24px;
  }

  .loading-title h3 {
    font-size: 18px;
  }

  .ai-icon {
    width: 80px;
    height: 80px;
  }

  .loading-details {
    grid-template-columns: 1fr;
    gap: 12px;
  }
}
</style>
