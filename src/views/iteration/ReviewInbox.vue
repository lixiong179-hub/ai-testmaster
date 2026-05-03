<template>
  <div class="review-inbox">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <el-button type="info" @click="goBack" :icon="ArrowLeft">返回</el-button>
            <h2>评审 Inbox</h2>
            <el-tag v-if="reviewStatus" :type="statusTagType">{{ statusText }}</el-tag>
          </div>
          <div class="header-right">
            <el-button
              v-if="hasHighConfidenceUndecided"
              type="warning"
              @click="handleBatchAcceptHighConfidence"
            >
              批量采纳高置信度 (≥85%)
            </el-button>
            <el-button @click="fetchDecisions()" :icon="Refresh" :loading="loading">刷新</el-button>
            <el-button
              v-if="reviewStatus === 'in_progress'"
              type="success"
              @click="handleFinalize"
              :loading="finalizing"
            >
              最终化评审
            </el-button>
            <el-button
              v-if="undoWindowOpen"
              type="danger"
              plain
              @click="handleUndoFinalize"
            >
              撤销最终化
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="loading && decisions.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="errorMsg" class="error-container">
        <el-alert :title="errorMsg" type="error" show-icon :closable="false" />
      </div>

      <div v-else class="inbox-content">
        <el-tabs v-model="activeTab" @tab-change="onTabChange">
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.key"
            :label="`${tab.label} (${tab.count})`"
            :name="tab.key"
          />
        </el-tabs>

        <el-table
          :data="filteredDecisions"
          stripe
          class="decisions-table"
          row-class-name="decision-row"
          @selection-change="onSelectionChange"
          :selectable="isSelectable"
        >
          <el-table-column type="selection" width="50" />
          <el-table-column label="目标ID" prop="target_id" width="100">
            <template #default="{ row }">
              <span class="target-id">{{ row.target_kind }}-{{ row.target_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 判定" width="120">
            <template #default="{ row }">
              <el-tag :type="verdictTagType(row.ai_verdict)" size="small" effect="dark">
                {{ verdictLabel(row.ai_verdict) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="AI 置信度" width="160">
            <template #default="{ row }">
              <el-progress
                v-if="row.ai_confidence !== null && row.ai_confidence !== undefined"
                :percentage="Math.round(row.ai_confidence ?? 0)"
                :color="confidenceColor(row.ai_confidence)"
                :stroke-width="14"
                :text-inside="true"
              />
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 理由" min-width="200">
            <template #default="{ row }">
              <el-text v-if="row.ai_reason" truncated>{{ row.ai_reason }}</el-text>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="修改提示" min-width="180">
            <template #default="{ row }">
              <div v-if="row.modification_hint" class="hint-cell">
                <el-button type="warning" link size="small" @click="toggleHint(row)">
                  {{ expandedHints.has(row.id) ? '收起' : '展开' }}提示
                </el-button>
                <el-text v-if="expandedHints.has(row.id)" class="hint-text" truncated>
                  {{ row.modification_hint }}
                </el-text>
              </div>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="废弃理由" min-width="160">
            <template #default="{ row }">
              <el-text v-if="row.deprecate_reason" truncated>{{ row.deprecate_reason }}</el-text>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="人工判定" width="200" fixed="right">
            <template #default="{ row }">
              <div v-if="row.human_verdict" class="human-decision">
                <el-tag :type="verdictTagType(row.human_verdict)" size="small">
                  {{ verdictLabel(row.human_verdict) }}
                </el-tag>
                <el-button
                  v-if="reviewStatus !== 'finalized'"
                  type="danger"
                  link
                  size="small"
                  @click="handleResetDecision(row)"
                >
                  重置
                </el-button>
                <el-button
                  v-if="undoWindowOpen"
                  type="warning"
                  link
                  size="small"
                  @click="handleUndoDecision(row)"
                >
                  撤销
                </el-button>
              </div>
              <div v-else-if="reviewStatus !== 'finalized'" class="decision-buttons">
                <el-button type="success" size="small" @click="handleDecide(row, 'keep')">
                  采纳
                </el-button>
                <el-button type="primary" size="small" @click="handleDecide(row, 'modify')">
                  修改
                </el-button>
                <el-button type="danger" size="small" @click="handleDecide(row, 'deprecate')">
                  否决
                </el-button>
              </div>
              <div v-else-if="undoWindowOpen" class="decision-buttons">
                <el-button
                  type="warning"
                  size="small"
                  @click="handleUndoDecision(row)"
                >
                  撤销
                </el-button>
              </div>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="冲突" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.conflict_marker" type="danger" size="small" effect="dark">
                冲突
              </el-tag>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { reviewApi, type ReviewDecision } from '@/api/review'

const route = useRoute()
const router = useRouter()

const reviewId = computed(() => Number(route.params.reviewId))
const decisions = ref<ReviewDecision[]>([])
const loading = ref(false)
const finalizing = ref(false)
const errorMsg = ref('')
const reviewStatus = ref('')
const reviewFinalizedAt = ref<string | null>(null)
const reviewUndoWindowExpiresAt = ref<string | null>(null)
const activeTab = ref('all')
const expandedHints = reactive(new Set<number>())
const selectedDecisions = ref<ReviewDecision[]>([])

interface TabDef {
  key: string
  label: string
  verdict: string | null
  count: number
}

const tabs = computed<TabDef[]>(() => {
  const counts: Record<string, number> = {}
  for (const d of decisions.value) {
    const v = d.ai_verdict || 'uncertain'
    counts[v] = (counts[v] || 0) + 1
  }
  return [
    { key: 'all', label: '全部', verdict: null },
    { key: 'keep', label: '采纳', verdict: 'keep' },
    { key: 'modify', label: '需修改', verdict: 'modify' },
    { key: 'deprecate', label: '废弃', verdict: 'deprecate' },
    { key: 'conflict', label: '冲突', verdict: 'conflict' },
  ].map((t) => {
    if (t.verdict === 'conflict') {
      return { ...t, count: decisions.value.filter((d) => d.conflict_marker).length }
    }
    if (t.verdict === null) {
      return { ...t, count: decisions.value.length }
    }
    return { ...t, count: counts[t.verdict] || 0 }
  })
})

const filteredDecisions = computed(() => {
  let result = decisions.value
  const active = activeTab.value
  if (active === 'keep' || active === 'modify' || active === 'deprecate') {
    result = result.filter((d) => d.ai_verdict === active)
  } else if (active === 'conflict') {
    result = result.filter((d) => d.conflict_marker)
  }

  const sorted = [...result]
  sorted.sort((a, b) => (b.conflict_marker ? 1 : 0) - (a.conflict_marker ? 1 : 0))
  return sorted
})

const statusTagType = computed(() => {
  const map: Record<string, string> = { draft: 'info', in_progress: '', finalized: 'success', cancelled: 'danger' }
  return map[reviewStatus.value] || 'info'
})

const statusText = computed(() => {
  const map: Record<string, string> = { draft: '草稿', in_progress: '进行中', finalized: '已最终化', cancelled: '已取消' }
  return map[reviewStatus.value] || reviewStatus.value
})

function verdictLabel(verdict?: string): string {
  const map: Record<string, string> = { keep: '采纳', modify: '需修改', deprecate: '废弃' }
  return map[verdict || ''] || verdict || '—'
}

function verdictTagType(verdict?: string): string {
  const map: Record<string, string> = { keep: 'success', modify: 'warning', deprecate: 'danger' }
  return map[verdict || ''] || 'info'
}

function confidenceColor(value: number): string {
  if (value >= 85) return '#67c23a'
  if (value >= 60) return '#e6a23c'
  return '#f56c6c'
}

const hasHighConfidenceUndecided = computed(() =>
  decisions.value.some(
    (d) => d.human_verdict === null && (d.ai_confidence ?? 0) >= 85
  )
)

const undoWindowOpen = computed(() => {
  if (reviewStatus.value !== 'finalized' || !reviewUndoWindowExpiresAt.value) return false
  return new Date(reviewUndoWindowExpiresAt.value).getTime() > Date.now()
})

function isSelectable(_row: ReviewDecision): boolean {
  return reviewStatus.value !== 'finalized'
}

function toggleHint(row: ReviewDecision) {
  if (expandedHints.has(row.id)) {
    expandedHints.delete(row.id)
  } else {
    expandedHints.add(row.id)
  }
}

function onSelectionChange(rows: ReviewDecision[]) {
  selectedDecisions.value = rows
}

function onTabChange() {
  selectedDecisions.value = []
}

function goBack() {
  router.back()
}

async function fetchDecisions() {
  loading.value = true
  errorMsg.value = ''
  expandedHints.clear()
  try {
    const res = await reviewApi.getDecisions(reviewId.value)
    decisions.value = res.data.decisions
    if (res.data.review) {
      reviewStatus.value = res.data.review.status || ''
      reviewFinalizedAt.value = res.data.review.finalized_at
      reviewUndoWindowExpiresAt.value = res.data.review.undo_window_expires_at
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { msg?: string } }; message?: string }
    errorMsg.value = err?.response?.data?.msg || err?.message || '获取决策列表失败'
  } finally {
    loading.value = false
  }
}

async function handleDecide(row: ReviewDecision, verdict: string) {
  try {
    await reviewApi.decideSingle(reviewId.value, row.id, {
      human_verdict: verdict,
    })
    ElMessage.success('判定已提交')
    await fetchDecisions()
  } catch (e: unknown) {
    const err = e as { response?: { status: number; data?: { msg?: string } }; message?: string }
    if (err?.response?.status === 409) {
      ElMessage.warning('该决策目标已被其他用户锁定，请稍后重试')
    } else if (err?.response?.status === 400) {
      ElMessage.warning(err?.response?.data?.msg || '操作失败：评审已最终化或状态异常')
    } else {
      ElMessage.error(err?.response?.data?.msg || err?.message || '提交判定失败')
    }
  }
}

async function handleResetDecision(row: ReviewDecision) {
  ElMessageBox.confirm(
    `确定重置决策 ${row.id} 吗？当前人工判定将恢复为 AI 原始判定。`,
    '重置决策',
    { type: 'warning', confirmButtonText: '确认重置' }
  ).then(async () => {
    try {
      await reviewApi.rollbackDecision(reviewId.value, row.id)
      ElMessage.success('决策已重置')
      await fetchDecisions()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { msg?: string } }; message?: string }
      ElMessage.error(err?.response?.data?.msg || '重置失败')
    }
  }).catch(() => {})
}

async function handleUndoDecision(row: ReviewDecision) {
  ElMessageBox.confirm(
    `确定撤销决策 ${row.id} 吗？此操作将逆操作生命周期变更并级联废弃子用例。`,
    '撤销决策',
    { type: 'warning', confirmButtonText: '确认撤销' }
  ).then(async () => {
    try {
      await reviewApi.undoDecision(reviewId.value, row.id)
      ElMessage.success('决策已撤销')
      await fetchDecisions()
    } catch (e: unknown) {
      const err = e as { response?: { status: number; data?: { msg?: string } }; message?: string }
      if (err?.response?.status === 403) {
        ElMessage.warning('撤销窗口已过期（超 1h），无法撤销')
      } else {
        ElMessage.error(err?.response?.data?.msg || '撤销失败')
      }
    }
  }).catch(() => {})
}

async function handleUndoFinalize() {
  ElMessageBox.confirm(
    `确定撤销评审最终化吗？所有决策将恢复为 in_progress 状态，已应用的生命周期变更将被逆操作。`,
    '撤销最终化',
    { type: 'warning', confirmButtonText: '确认撤销' }
  ).then(async () => {
    try {
      const res = await reviewApi.undoFinalize(reviewId.value)
      reviewStatus.value = res.data.status
      reviewFinalizedAt.value = null
      reviewUndoWindowExpiresAt.value = null
      ElMessage.success('评审最终化已撤销')
      await fetchDecisions()
    } catch (e: unknown) {
      const err = e as { response?: { status: number; data?: { msg?: string } }; message?: string }
      if (err?.response?.status === 403) {
        ElMessage.warning('撤销窗口已过期（超 1h），无法撤销')
      } else {
        ElMessage.error(err?.response?.data?.msg || '撤销失败')
      }
    }
  }).catch(() => {})
}

function handleBatchAcceptHighConfidence() {
  const highConfidenceDecisions = decisions.value.filter(
    (d) => d.human_verdict === null && (d.ai_confidence ?? 0) >= 85
  )

  if (highConfidenceDecisions.length === 0) {
    ElMessage.info('没有可批量采纳的高置信度决策（置信度 ≥ 85% 且未判定）')
    return
  }

  ElMessageBox.confirm(
    `将采纳 ${highConfidenceDecisions.length} 条高置信度决策，是否继续？`,
    '批量采纳',
    { type: 'warning' }
  ).then(async () => {
    try {
      await reviewApi.decideBatch(reviewId.value, {
        decisions: highConfidenceDecisions.map((d) => ({
          decision_id: d.id,
          human_verdict: 'keep' as string,
        })),
      })
      ElMessage.success(`已批量采纳 ${highConfidenceDecisions.length} 条决策`)
      await fetchDecisions()
    } catch (e: unknown) {
      const err = e as { response?: { status: number; data?: { msg?: string } }; message?: string }
      if (err?.response?.status === 409) {
        ElMessage.warning('部分决策目标已被锁定，批量采纳失败')
      } else {
        ElMessage.error(err?.response?.data?.msg || err?.message || '批量采纳失败')
      }
    }
  }).catch(() => {})
}

function handleFinalize() {
  ElMessageBox.confirm(
    '最终化后所有决策将不可修改，是否确认？',
    '最终化评审',
    { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
  ).then(async () => {
    finalizing.value = true
    try {
      const res = await reviewApi.finalizeReview(reviewId.value)
      reviewStatus.value = res.data.status
      ElMessage.success('评审已最终化')
      await fetchDecisions()
    } catch (e: unknown) {
      const err = e as { response?: { status: number; data?: { msg?: string } }; message?: string }
      if (err?.response?.status === 400) {
        ElMessage.warning(err?.response?.data?.msg || '最终化失败：评审状态异常')
      } else {
        ElMessage.error(err?.response?.data?.msg || '最终化失败')
      }
    } finally {
      finalizing.value = false
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchDecisions()
})
</script>

<style scoped>
.review-inbox {
  padding: 16px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-container,
.error-container {
  padding: 24px 0;
}

.inbox-content {
  padding: 8px 0;
}

.decisions-table {
  margin-top: 12px;
}

.target-id {
  font-family: monospace;
  font-size: 13px;
}

.text-muted {
  color: #909399;
  font-size: 13px;
}

.hint-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.hint-text {
  font-size: 12px;
  color: #909399;
}

.decision-buttons {
  display: flex;
  gap: 4px;
}

.human-decision {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
