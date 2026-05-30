<template>
  <div class="case-refresh-page">
    <div class="page-hero">
      <div class="hero-copy">
        <h2 class="page-title">保鲜建议</h2>
        <p class="page-subtitle">AI 自动检测过期用例并生成保鲜建议，审核后即可更新用例</p>
      </div>
      <div class="hero-actions">
        <el-select
          v-model="selectedProjectId"
          placeholder="请选择项目"
          filterable
          style="width: 240px"
          @change="handleProjectChange"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="autoRefreshing"
          :disabled="!selectedProjectId"
          @click="handleAutoRefresh"
        >
          AI保鲜扫描
        </el-button>
        <el-button
          :loading="scanning"
          :disabled="!selectedProjectId"
          @click="handleScanStaleCases"
        >
          仅扫描过期
        </el-button>
      </div>
    </div>

    <div v-if="selectedProjectId" class="workspace-card">
      <div class="stats-row">
        <div class="stat-chip pending">
          <span class="stat-label">待审核</span>
          <span class="stat-value">{{ stats.pending }}</span>
        </div>
        <div class="stat-chip applied">
          <span class="stat-label">已应用</span>
          <span class="stat-value">{{ stats.applied }}</span>
        </div>
        <div class="stat-chip rejected">
          <span class="stat-label">已驳回</span>
          <span class="stat-value">{{ stats.rejected }}</span>
        </div>
      </div>

      <el-table :data="suggestions" border stripe v-loading="loading" row-key="id">
        <el-table-column prop="case_id" label="用例编号" width="100" />
        <el-table-column label="用例标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.suggested_title ?? `用例 #${row.case_id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="trigger_reason" label="触发原因" min-width="160" show-overflow-tooltip />
        <el-table-column label="建议状态" width="100">
          <template #default="{ row }">
            <el-tag :type="suggestionStatusTagType(row.suggestion_status)" size="small">
              {{ suggestionStatusLabel(row.suggestion_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审核状态" width="100">
          <template #default="{ row }">
            <el-tag :type="reviewStatusTagType(row.review_status)" size="small">
              {{ reviewStatusLabel(row.review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="触发时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.triggered_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <template v-if="row.review_status === 'pending'">
              <el-button link type="primary" @click="handleViewDiff(row)">查看详情</el-button>
              <el-button link type="primary" @click="handleReview(row, 'approve')">通过</el-button>
              <el-button link type="danger" @click="handleReview(row, 'reject')">驳回</el-button>
            </template>
            <template v-else-if="row.review_status === 'approved'">
              <el-button link type="primary" @click="handleViewDiff(row)">查看diff</el-button>
              <el-button
                v-if="row.snapshot_version_id"
                link
                type="warning"
                @click="handleRollback(row)"
              >
                回滚
              </el-button>
            </template>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchSuggestions"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <el-empty v-else description="请选择项目后查看保鲜建议" />

    <el-dialog
      v-model="reviewDialogVisible"
      :title="reviewAction === 'approve' ? '通过保鲜建议' : '驳回保鲜建议'"
      width="560px"
      destroy-on-close
    >
      <div v-if="currentSuggestion" class="review-detail">
        <div class="detail-item">
          <span class="detail-label">建议标题：</span>
          <span>{{ currentSuggestion.suggested_title ?? '--' }}</span>
        </div>
        <div v-if="currentSuggestion.suggested_expected_result" class="detail-item">
          <span class="detail-label">建议预期结果：</span>
          <pre class="diff-content">{{ currentSuggestion.suggested_expected_result }}</pre>
        </div>
        <div class="detail-item">
          <span class="detail-label">变更描述：</span>
          <pre class="diff-content">{{ currentSuggestion.diff_description ?? '暂无变更描述' }}</pre>
        </div>
        <div class="detail-item">
          <span class="detail-label">废弃原因：</span>
          <span>{{ currentSuggestion.deprecation_reason ?? '--' }}</span>
        </div>
        <div v-if="currentSuggestion.suggested_steps && currentSuggestion.suggested_steps.length" class="detail-item">
          <span class="detail-label">建议步骤：</span>
          <ol class="step-list">
            <li v-for="(step, idx) in currentSuggestion.suggested_steps" :key="idx">
              {{ step.action || step.description || JSON.stringify(step) }}
            </li>
          </ol>
        </div>
        <div v-if="reviewAction === 'reject'" class="detail-item">
          <span class="detail-label">驳回原因：</span>
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="3"
            placeholder="请填写驳回原因"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button
          v-if="reviewAction === 'reject'"
          type="danger"
          :loading="submitting"
          :disabled="!rejectReason.trim()"
          @click="submitReview"
        >
          确认驳回
        </el-button>
        <el-button
          v-else
          type="primary"
          :loading="submitting"
          @click="submitReview"
        >
          确认通过
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="diffDialogVisible"
      title="变更详情"
      width="640px"
      destroy-on-close
    >
      <div v-if="currentSuggestion" class="diff-detail">
        <div class="detail-item">
          <span class="detail-label">建议标题：</span>
          <span>{{ currentSuggestion.suggested_title ?? '--' }}</span>
        </div>
        <div v-if="currentSuggestion.suggested_expected_result" class="detail-item">
          <span class="detail-label">建议预期结果：</span>
          <pre class="diff-content">{{ currentSuggestion.suggested_expected_result }}</pre>
        </div>
        <div class="detail-item">
          <span class="detail-label">变更描述：</span>
          <pre class="diff-content">{{ currentSuggestion.diff_description ?? '暂无变更描述' }}</pre>
        </div>
        <div class="detail-item">
          <span class="detail-label">废弃原因：</span>
          <span>{{ currentSuggestion.deprecation_reason ?? '--' }}</span>
        </div>
        <div v-if="currentSuggestion.suggested_steps && currentSuggestion.suggested_steps.length" class="detail-item">
          <span class="detail-label">建议步骤：</span>
          <ol class="step-list">
            <li v-for="(step, idx) in currentSuggestion.suggested_steps" :key="idx">
              {{ step.action || step.description || JSON.stringify(step) }}
            </li>
          </ol>
        </div>
        <div class="detail-item">
          <span class="detail-label">模型版本：</span>
          <span>{{ currentSuggestion.model_version ?? '--' }}</span>
        </div>
        <div v-if="currentSuggestion.snapshot_version_id" class="detail-item">
          <span class="detail-label">快照版本ID：</span>
          <span>#{{ currentSuggestion.snapshot_version_id }}</span>
          <el-button link type="warning" style="margin-left: 8px" @click="handleRollback(currentSuggestion)">
            回滚到此版本
          </el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="diffDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import projectApi, { type Project } from '@/api/project'
import { caseApi } from '@/api/case'
import {
    listRefreshSuggestions,
    reviewRefreshSuggestion,
    scanStaleCases,
    autoRefreshCases,
    getRefreshSuggestionsStats,
} from '@/api/caseRefresh'

interface RefreshSuggestion {
    id: number
    case_id: number
    requirement_id: number | null
    trigger_reason: string
    triggered_at: string | null
    suggestion_status: string
    suggested_title: string | null
    suggested_steps: Array<Record<string, unknown>> | null
    suggested_expected_result: string | null
    diff_description: string | null
    deprecation_reason: string | null
    review_status: string
    reviewer_name: string | null
    reviewed_at: string | null
    reject_reason: string | null
    model_version: string | null
    snapshot_version_id: number | null
    created_at: string | null
}

const projects = ref<Project[]>([])
const selectedProjectId = ref<number | undefined>(undefined)

const suggestions = ref<RefreshSuggestion[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const stats = reactive({ pending: 0, applied: 0, rejected: 0 })

const scanning = ref(false)
const autoRefreshing = ref(false)

const reviewDialogVisible = ref(false)
const reviewAction = ref<'approve' | 'reject'>('approve')
const currentSuggestion = ref<RefreshSuggestion | null>(null)
const rejectReason = ref('')
const submitting = ref(false)

const diffDialogVisible = ref(false)

function suggestionStatusTagType(status: string): 'warning' | 'primary' | 'success' | 'danger' | 'info' {
    const map: Record<string, 'warning' | 'primary' | 'success' | 'danger' | 'info'> = {
        pending: 'warning',
        accepted: 'primary',
        applied: 'success',
        rejected: 'danger',
        expired: 'info',
    }
    return map[status] ?? 'info'
}

function suggestionStatusLabel(status: string): string {
    const map: Record<string, string> = {
        pending: '待处理',
        accepted: '已接受',
        applied: '已应用',
        rejected: '已拒绝',
        expired: '已过期',
    }
    return map[status] ?? status
}

function reviewStatusTagType(status: string): 'warning' | 'success' | 'danger' | 'info' {
    const map: Record<string, 'warning' | 'success' | 'danger' | 'info'> = {
        pending: 'warning',
        approved: 'success',
        rejected: 'danger',
    }
    return map[status] ?? 'info'
}

function reviewStatusLabel(status: string): string {
    const map: Record<string, string> = {
        pending: '待审核',
        approved: '已通过',
        rejected: '已驳回',
    }
    return map[status] ?? status
}

function formatTime(time: string | null): string {
    if (!time) return '--'
    return time.replace('T', ' ').substring(0, 19)
}

async function loadProjects(): Promise<void> {
    try {
        const response = await projectApi.getProjects({ page: 1, page_size: 100 })
        projects.value = response.data.items
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : '加载项目失败')
    }
}

function handleProjectChange(): void {
    page.value = 1
    fetchSuggestions()
}

async function fetchSuggestions(): Promise<void> {
    if (!selectedProjectId.value) return
    loading.value = true
    try {
        const response = await listRefreshSuggestions(
            selectedProjectId.value,
            page.value,
            pageSize.value
        )
        const data = response.data as { items: RefreshSuggestion[]; total: number }
        suggestions.value = data.items ?? []
        total.value = data.total ?? 0
        updateStats()
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : '获取保鲜建议失败')
    } finally {
        loading.value = false
    }
}

async function updateStats(): Promise<void> {
    if (!selectedProjectId.value) return
    try {
        const response = await getRefreshSuggestionsStats(selectedProjectId.value)
        const data = response.data as { pending: number; applied: number; rejected: number; total: number }
        stats.pending = data.pending ?? 0
        stats.applied = data.applied ?? 0
        stats.rejected = data.rejected ?? 0
    } catch {
        stats.pending = 0
        stats.applied = 0
        stats.rejected = 0
    }
}

function handlePageSizeChange(): void {
    page.value = 1
    fetchSuggestions()
}

async function handleScanStaleCases(): Promise<void> {
    if (!selectedProjectId.value) return
    scanning.value = true
    try {
        const response = await scanStaleCases(selectedProjectId.value)
        const data = response.data as { count: number }
        ElMessage.success(`扫描完成，发现 ${data.count} 条过期用例`)
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : '扫描过期用例失败')
    } finally {
        scanning.value = false
    }
}

async function handleAutoRefresh(): Promise<void> {
    if (!selectedProjectId.value) return
    autoRefreshing.value = true
    try {
        const response = await autoRefreshCases(selectedProjectId.value)
        const data = response.data as { total_scanned: number; status: string }
        if (data.status === 'processing') {
            ElMessage({
                type: 'success',
                message: `已提交后台处理，共 ${data.total_scanned} 条过期用例。建议稍后刷新查看结果。`,
                duration: 5000,
            })
            setTimeout(async () => {
                page.value = 1
                await fetchSuggestions()
            }, 3000)
        } else {
            ElMessage.info('无过期用例')
        }
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : 'AI保鲜扫描失败')
    } finally {
        autoRefreshing.value = false
    }
}

function handleReview(row: RefreshSuggestion, action: 'approve' | 'reject'): void {
    currentSuggestion.value = row
    reviewAction.value = action
    rejectReason.value = ''
    reviewDialogVisible.value = true
}

async function submitReview(): Promise<void> {
    if (!currentSuggestion.value) return
    if (reviewAction.value === 'reject' && !rejectReason.value.trim()) {
        ElMessage.warning('请填写驳回原因')
        return
    }
    submitting.value = true
    try {
        await reviewRefreshSuggestion(
            currentSuggestion.value.id,
            reviewAction.value,
            reviewAction.value === 'reject' ? rejectReason.value.trim() : undefined
        )
        ElMessage.success(reviewAction.value === 'approve' ? '已通过' : '已驳回')
        reviewDialogVisible.value = false
        await fetchSuggestions()
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : '审核操作失败')
    } finally {
        submitting.value = false
    }
}

function handleViewDiff(row: RefreshSuggestion): void {
    currentSuggestion.value = row
    diffDialogVisible.value = true
}

async function handleRollback(row: RefreshSuggestion): Promise<void> {
    if (!row.snapshot_version_id) {
        ElMessage.warning('无可用快照版本')
        return
    }
    try {
        await ElMessageBox.confirm(
            `确认将用例 #${row.case_id} 回滚到快照版本 #${row.snapshot_version_id}？回滚后保鲜建议的修改将被撤销。`,
            '确认回滚',
            { confirmButtonText: '确认回滚', cancelButtonText: '取消', type: 'warning' }
        )
    } catch {
        return
    }
    try {
        await caseApi.rollbackCaseVersion(row.case_id, row.snapshot_version_id)
        ElMessage.success('回滚成功')
        await fetchSuggestions()
    } catch (error) {
        ElMessage.error(error instanceof Error ? error.message : '回滚失败')
    }
}

onMounted(() => {
    loadProjects()
})
</script>

<style scoped>
.case-refresh-page {
    background: #f5f7fa;
    min-height: 100%;
}
.page-hero {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
    padding: 20px;
    background: #fff;
    border: 1px solid #ebeef5;
    border-radius: 8px;
}
.page-title {
    margin: 0;
    font-size: 24px;
    color: #1f2d3d;
}
.page-subtitle {
    margin: 6px 0 0;
    color: #7a8594;
}
.hero-actions {
    display: flex;
    gap: 12px;
    align-items: center;
}
.workspace-card {
    padding: 20px;
    background: #fff;
    border: 1px solid #ebeef5;
    border-radius: 8px;
}
.stats-row {
    display: grid;
    grid-template-columns: repeat(3, minmax(120px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}
.stat-chip {
    display: flex;
    flex-direction: column;
    padding: 12px 16px;
    background: #f8f9fb;
    border-radius: 8px;
    min-width: 0;
}
.stat-chip .stat-label {
    font-size: 12px;
    color: #909399;
}
.stat-chip .stat-value {
    font-size: 22px;
    font-weight: 700;
    color: #1f2d3d;
}
.stat-chip.pending {
    background: #fdf6ec;
}
.stat-chip.applied {
    background: #f0f9eb;
}
.stat-chip.rejected {
    background: #fef0f0;
}
.pagination {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
}
.text-muted {
    color: #c0c4cc;
}
.review-detail,
.diff-detail {
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.detail-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.detail-label {
    font-size: 13px;
    color: #909399;
    font-weight: 500;
}
.diff-content {
    margin: 0;
    padding: 12px;
    background: #f5f7fa;
    border: 1px solid #ebeef5;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 320px;
    overflow-y: auto;
}
.step-list {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    line-height: 1.8;
}
@media (max-width: 900px) {
    .page-hero {
        flex-direction: column;
        align-items: stretch;
    }
    .hero-actions {
        flex-wrap: wrap;
    }
    .stats-row {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .pagination {
        justify-content: flex-start;
        overflow-x: auto;
    }
}
@media (max-width: 520px) {
    .workspace-card,
    .page-hero {
        padding: 14px;
    }
    .stats-row {
        grid-template-columns: 1fr;
    }
}
</style>
