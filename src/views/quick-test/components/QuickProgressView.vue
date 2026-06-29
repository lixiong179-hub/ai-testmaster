<template>
    <el-card class="quick-progress-card" shadow="never">
        <template #header>
            <div class="card-header">
                <div>
                    <div class="card-title">测试进行中</div>
                    <div class="card-subtitle">
                        当前阶段：{{ stageLabel }}
                        <el-tag v-if="wsConnected" type="success" size="small" class="ws-tag">实时</el-tag>
                        <el-tag v-else type="warning" size="small" class="ws-tag">重连中</el-tag>
                    </div>
                </div>
                <el-button type="danger" plain @click="emit('cancel')">取消</el-button>
            </div>
        </template>

        <div class="progress-meta">
            <div class="meta-item">
                <span class="meta-label">网址</span>
                <span class="meta-value" :title="store.lastUrl || ''">{{ store.lastUrl || '-' }}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">任务ID</span>
                <span class="meta-value">{{ store.taskId ?? '-' }}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">已用时长</span>
                <span class="meta-value">{{ elapsedText }}</span>
            </div>
            <div class="meta-item">
                <span class="meta-label">预计剩余</span>
                <span class="meta-value">{{ remainingText }}</span>
            </div>
        </div>

        <!-- 总进度条 -->
        <el-progress
            :percentage="store.progress"
            :status="progressStatus"
            :stroke-width="18"
            :text-inside="true"
            class="total-progress"
        />

        <!-- 4 阶段步骤 -->
        <div class="stage-list">
            <div
                v-for="(stage, index) in progressStages"
                :key="stage.key"
                class="stage-item"
                :class="stageItemClass(index)"
            >
                <div class="stage-icon">
                    <el-icon v-if="index < activeStageIndex"><CircleCheckFilled /></el-icon>
                    <el-icon v-else-if="index === activeStageIndex" class="is-active"><Loading /></el-icon>
                    <el-icon v-else><CircleCheck /></el-icon>
                </div>
                <div class="stage-info">
                    <div class="stage-label">{{ stage.label }}</div>
                    <div class="stage-status">{{ stageStatusText(index) }}</div>
                </div>
                <div class="stage-range">{{ rangeText(index) }}</div>
            </div>
        </div>
    </el-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { CircleCheck, CircleCheckFilled, Loading } from '@element-plus/icons-vue'
import { useQuickTestStore } from '@/store/quickTest'
import type { ProgressStatus } from '@/types/element-plus'
import {
    STAGE_LABELS,
    PROGRESS_STAGES,
    STAGE_PROGRESS_RANGE,
    getProgressStageIndex,
} from '../quickTestTypes'

defineProps<{
    /** WS 连接状态：用于展示「实时/重连中」标签 */
    wsConnected?: boolean
}>()

const emit = defineEmits<{
    (e: 'cancel'): void
}>()

const store = useQuickTestStore()
const progressStages = PROGRESS_STAGES

const stageLabel = computed(() => STAGE_LABELS[store.currentStage] || '处理中')
const activeStageIndex = computed(() => getProgressStageIndex(store.currentStage))

const progressStatus = computed<ProgressStatus>(() => {
    if (store.isFailed) return 'exception'
    if (store.isCompleted) return 'success'
    return ''
})

// 已用时长：基于 store.startedAt 用 setInterval 累加；startedAt 缺失时从挂载时刻起算
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null
const fallbackStart = ref(Date.now())

const startMs = computed(() => {
    if (store.startedAt) {
        // 后端 task.start_time.isoformat() 返回 naive UTC 字符串（无时区后缀），
        // Date.parse 按本地时区解析会导致 8 小时偏移；检测无时区后缀时追加 'Z' 按 UTC 解析
        let ts = store.startedAt
        if (!/[zZ]$|[+-]\d{2}:\d{2}$/.test(ts)) {
            ts = ts + 'Z'
        }
        const t = Date.parse(ts)
        if (!Number.isNaN(t)) return t
    }
    return fallbackStart.value
})

const elapsedSec = computed(() => Math.max(0, Math.floor((now.value - startMs.value) / 1000)))
const elapsedText = computed(() => formatDuration(elapsedSec.value))

const remainingText = computed(() => {
    const est = store.estimatedDurationSec
    if (!est || est <= 0) return '未知'
    const remain = Math.max(0, est - elapsedSec.value)
    return formatDuration(remain)
})

function formatDuration(sec: number): string {
    if (sec <= 0) return '0s'
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

function stageItemClass(index: number): Record<string, boolean> {
    return {
        'is-done': index < activeStageIndex.value,
        'is-active': index === activeStageIndex.value,
        'is-pending': index > activeStageIndex.value,
    }
}

function stageStatusText(index: number): string {
    if (index < activeStageIndex.value) return '已完成'
    if (index === activeStageIndex.value) return '进行中'
    return '等待中'
}

function rangeText(index: number): string {
    const stage = progressStages[index]
    const def = stage.stages[0]
    const range = STAGE_PROGRESS_RANGE[def]
    if (!range) return ''
    if (range[0] === range[1]) return `${range[0]}%`
    return `${range[0]}-${range[1]}%`
}

onMounted(() => {
    timer = setInterval(() => {
        now.value = Date.now()
    }, 1000)
})

onUnmounted(() => {
    if (timer) {
        clearInterval(timer)
        timer = null
    }
})
</script>

<style scoped lang="scss">
.quick-progress-card {
    border: none;
    border-radius: 8px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}

.card-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2d3d;
}

.card-subtitle {
    margin-top: 6px;
    color: #7a8594;
    line-height: 1.6;
    display: flex;
    align-items: center;
    gap: 8px;
}

.ws-tag {
    margin-left: 4px;
}

.progress-meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}

.meta-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.meta-label {
    font-size: 12px;
    color: #7a8594;
}

.meta-value {
    font-size: 14px;
    color: #1f2d3d;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.total-progress {
    margin-bottom: 24px;
}

.stage-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.stage-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    background: #f7f8fa;
    transition: background 0.2s;
}

.stage-item.is-done {
    background: #f0f9eb;
}

.stage-item.is-active {
    background: #ecf5ff;
    box-shadow: 0 0 0 1px #409eff inset;
}

.stage-item.is-pending {
    opacity: 0.6;
}

.stage-icon {
    font-size: 20px;
    color: #c0c4cc;
}

.stage-item.is-done .stage-icon {
    color: #67c23a;
}

.stage-item.is-active .stage-icon.is-active {
    color: #409eff;
    animation: spin 1.5s linear infinite;
}

.stage-info {
    flex: 1;
}

.stage-label {
    font-size: 14px;
    font-weight: 600;
    color: #1f2d3d;
}

.stage-status {
    font-size: 12px;
    color: #7a8594;
    margin-top: 2px;
}

.stage-range {
    font-size: 12px;
    color: #909399;
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
    .card-header {
        flex-direction: column;
        align-items: stretch;
    }
    .progress-meta {
        grid-template-columns: 1fr 1fr;
    }
}
</style>
