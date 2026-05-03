<template>
  <div class="pipeline-progress">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <el-button type="info" @click="goBack" :icon="ArrowLeft">返回</el-button>
            <h2>Pipeline 运行进度</h2>
            <el-tag v-if="runData" :type="runStatusType">{{ runStatusText }}</el-tag>
          </div>
          <div class="header-right">
            <el-button
              v-if="runData?.status === 'waiting_for_user'"
              type="primary"
              @click="handleResume"
            >
              确认并继续
            </el-button>
            <el-button
              v-if="isPolling"
              :icon="Loading"
              circle
              loading
            />
            <el-button @click="fetchRunData()" :icon="Refresh">刷新</el-button>
          </div>
        </div>
      </template>

      <div v-if="initialLoading && !runData" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="runData" class="pipeline-content">
        <el-descriptions :column="3" border class="run-info">
          <el-descriptions-item label="运行 ID">{{ runData.id }}</el-descriptions-item>
          <el-descriptions-item label="迭代 ID">{{ runData.iteration_id }}</el-descriptions-item>
          <el-descriptions-item label="Pipeline 版本">{{ runData.pipeline_version }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(runData.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(runData.finished_at) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ duration }}</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="runData.error"
          :title="runData.error"
          type="error"
          show-icon
          :closable="false"
          class="error-alert"
        />

        <h3 class="section-title">步骤列表</h3>
        <el-table :data="runData.steps" stripe class="steps-table">
          <el-table-column label="步骤名称" prop="step_name" min-width="160">
            <template #default="{ row }">
              <span class="step-name">{{ stepNameMap[row.step_name] || row.step_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" prop="status" width="140">
            <template #default="{ row }">
              <el-tag :type="stepStatusType(row.status)" size="small" effect="dark">
                {{ stepStatusText(row.status) }}
              </el-tag>
              <el-tag
                v-if="row.degraded"
                type="warning"
                size="small"
                effect="dark"
                class="degraded-badge"
              >
                降级
              </el-tag>
              <el-tag
                v-if="row.retried_count > 0"
                type="info"
                size="small"
                class="retry-badge"
              >
                重试{{ row.retried_count }}次
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="开始时间" width="180">
            <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="180">
            <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="100">
            <template #default="{ row }">{{ stepDuration(row) }}</template>
          </el-table-column>
          <el-table-column label="错误" prop="error" min-width="200">
            <template #default="{ row }">
              <el-text v-if="row.error" type="danger" truncated>{{ row.error }}</el-text>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
        </el-table>

        <h3 v-if="runData.artifacts.length > 0" class="section-title">产物列表</h3>
        <el-table
          v-if="runData.artifacts.length > 0"
          :data="runData.artifacts"
          stripe
          class="artifacts-table"
        >
          <el-table-column label="类型" prop="kind" min-width="180">
            <template #default="{ row }">
              {{ artifactKindMap[row.kind] || row.kind }}
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="120">
            <template #default="{ row }">
              <el-progress
                v-if="row.confidence !== null && row.confidence !== undefined"
                :percentage="Math.round(row.confidence * 100)"
                :color="confidenceColor(row.confidence)"
                :stroke-width="14"
                :text-inside="true"
              />
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="Schema 版本" prop="schema_version" width="120">
            <template #default="{ row }">{{ row.schema_version || '—' }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </div>

      <el-empty v-else description="未找到 Pipeline 运行记录" />
    </el-card>
    <ConfirmationDialog
      :visible="showConfirmDialog"
      :reason="confirmReason"
      :schema="confirmSchema"
      @confirm="handleConfirmResume"
      :close-on-click-modal="false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh, Loading } from '@element-plus/icons-vue'
import { pipelineApi, type PipelineRun } from '@/api/pipeline'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'

const route = useRoute()
const router = useRouter()

const runId = computed(() => Number(route.params.runId))
const runData = ref<PipelineRun | null>(null)
const loading = ref(false)
const initialLoading = ref(true)
const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
const showConfirmDialog = ref(false)

const isPolling = computed(() => {
  return runData.value?.status === 'running' || runData.value?.status === 'pending'
})

const confirmReason = computed(() => {
  if (runData.value?.pause_payload && typeof runData.value.pause_payload === 'object') {
    return (runData.value.pause_payload as Record<string, unknown>).reason as string || ''
  }
  return runData.value?.error || 'Pipeline 需要人工确认后继续'
})

const confirmSchema = computed(() => {
  if (runData.value?.pause_payload && typeof runData.value.pause_payload === 'object') {
    const schema = (runData.value.pause_payload as Record<string, unknown>).schema
    if (schema && typeof schema === 'object') {
      return schema as { fields: Array<{ key: string; label: string; type: string; options?: Array<{ label: string; value: string }>; placeholder?: string; required?: boolean }> }
    }
  }
  return null
})


const stepNameMap: Record<string, string> = {
  signal_gatherer: '信号采集',
  testpoint_alignment: '测试点对齐',
  case_generation: '用例生成',
  quality_gate: '质量门禁',
  persist: '用例持久化',
}

const artifactKindMap: Record<string, string> = {
  raw_signals: '原始信号',
  aligned_testpoints: '对齐测试点',
  generated_cases: '生成用例',
  quality_scores: '质量评分',
}

const runStatusType = computed(() => {
  const map: Record<string, string> = {
    pending: 'info',
    running: '',
    completed: 'success',
    failed: 'danger',
    waiting_for_user: 'warning',
    cancelled: 'info',
  }
  return map[runData.value?.status || ''] || 'info'
})

const runStatusText = computed(() => {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    waiting_for_user: '等待确认',
    cancelled: '已取消',
  }
  return map[runData.value?.status || ''] || runData.value?.status || ''
})

const duration = computed(() => {
  if (!runData.value?.started_at) return '—'
  const start = new Date(runData.value.started_at).getTime()
  const end = runData.value.finished_at
    ? new Date(runData.value.finished_at).getTime()
    : Date.now()
  return formatDuration(end - start)
})

function stepStatusType(status: string): string {
  const map: Record<string, string> = {
    pending: 'info',
    running: '',
    done: 'success',
    failed: 'danger',
    skipped: 'info',
    degraded: 'warning',
  }
  return map[status] || 'info'
}

function stepStatusText(status: string): string {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    done: '已完成',
    failed: '失败',
    skipped: '已跳过',
    degraded: '降级完成',
  }
  return map[status] || status
}

function stepDuration(step: { started_at: string | null; finished_at: string | null }): string {
  if (!step.started_at) return '—'
  const start = new Date(step.started_at).getTime()
  const end = step.finished_at ? new Date(step.finished_at).getTime() : Date.now()
  return formatDuration(end - start)
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.85) return '#67c23a'
  if (confidence >= 0.7) return '#e6a23c'
  return '#f56c6c'
}

function formatTime(time: string | null | undefined): string {
  if (!time) return '—'
  try {
    return new Date(time).toLocaleString('zh-CN')
  } catch {
    return time
  }
}

function formatDuration(ms: number): string {
  if (ms < 0 || isNaN(ms)) return '—'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}秒`
  const minutes = Math.floor(seconds / 60)
  const remainSeconds = seconds % 60
  if (minutes < 60) return `${minutes}分${remainSeconds}秒`
  const hours = Math.floor(minutes / 60)
  const remainMinutes = minutes % 60
  return `${hours}时${remainMinutes}分`
}

async function fetchRunData(isInitial = false) {
  if (!runId.value) return
  if (isInitial) {
    initialLoading.value = true
  }
  loading.value = true
  try {
    const res = await pipelineApi.getPipelineRun(runId.value)
    runData.value = res.data
    if (!isPolling.value) {
      stopPolling()
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '获取 Pipeline 状态失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

async function handleResume() {
  if (runData.value?.status === 'waiting_for_user') {
    showConfirmDialog.value = true
  } else {
    doResume({})
  }
}

function handleConfirmResume(payload: Record<string, unknown>) {
  showConfirmDialog.value = false
  doResume(payload)
}

async function doResume(payload: Record<string, unknown>) {
  if (!runData.value) return
  try {
    await pipelineApi.resumePipeline(
      runData.value.id,
      Object.keys(payload).length > 0 ? payload : undefined,
    )
    ElMessage.success('Pipeline 已恢复')
    await fetchRunData()
    startPolling()
  } catch (e: unknown) {
    if (e && typeof e === 'object' && 'status' in e && (e as { status: number }).status === 409) {
      ElMessage.warning('Pipeline 状态已变更，请刷新')
    } else {
      ElMessage.error('恢复失败')
    }
  }
}

function startPolling() {
  stopPolling()
  if (isPolling.value) {
    pollingTimer.value = setInterval(fetchRunData, 5000)
  }
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

function goBack() {
  router.back()
}

onMounted(async () => {
  await fetchRunData(true)
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.pipeline-progress {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-container {
  padding: 20px;
}

.pipeline-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.run-info {
  margin-bottom: 0;
}

.error-alert {
  margin-top: 0;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.step-name {
  font-weight: 500;
}

.degraded-badge {
  margin-left: 4px;
}

.retry-badge {
  margin-left: 4px;
}

.text-muted {
  color: #c0c4cc;
}

.steps-table,
.artifacts-table {
  width: 100%;
}
</style>
