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
            <el-button v-if="isPolling" :icon="Loading" circle loading />
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
          <el-descriptions-item label="Pipeline 版本">{{
            runData.pipeline_version
          }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{
            formatTime(runData.started_at)
          }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{
            formatTime(runData.finished_at)
          }}</el-descriptions-item>
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
                >降级</el-tag
              >
              <el-tag v-if="row.retried_count > 0" type="info" size="small" class="retry-badge"
                >重试{{ row.retried_count }}次</el-tag
              >
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
          @row-click="(row: { id: number }) => toggleArtifactDetail(row.id)"
        >
          <el-table-column label="类型" prop="kind" min-width="180">
            <template #default="{ row }">
              <span class="artifact-kind-link">{{ artifactKindMap[row.kind] || row.kind }}</span>
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
          <el-table-column label="操作" width="80">
            <template #default="{ row }">
              <el-icon v-if="expandedArtifactId === row.id"><ArrowUp /></el-icon>
              <el-icon v-else><ArrowDown /></el-icon>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="expandedArtifactId !== null" class="artifact-detail-panel">
          <div v-if="artifactDetailLoading" class="artifact-detail-loading">
            <el-skeleton :rows="3" animated />
          </div>
          <template v-else-if="artifactDetail">
            <div class="artifact-detail-header">
              <span class="artifact-detail-title"
                >产物详情 - {{ artifactKindMap[artifactDetail.kind] || artifactDetail.kind }}</span
              >
              <el-tag v-if="artifactDetail.truncated" type="warning" size="small"
                >数据已截断</el-tag
              >
            </div>
            <el-alert
              v-if="artifactDetail.truncated && artifactDetail.truncated_reason"
              :title="artifactDetail.truncated_reason"
              type="warning"
              show-icon
              :closable="false"
              class="truncate-alert"
            />
            <div class="artifact-detail-meta">
              <span>Artifact ID: {{ artifactDetail.artifact_id }}</span>
              <span>Schema: {{ artifactDetail.schema_version }}</span>
              <span v-if="artifactDetail.confidence !== null"
                >置信度: {{ (artifactDetail.confidence * 100).toFixed(1) }}%</span
              >
            </div>
            <pre class="artifact-payload">{{
              JSON.stringify(artifactDetail.payload, null, 2)
            }}</pre>
          </template>
        </div>

        <div v-if="summaryLoading" class="summary-loading">
          <el-skeleton :rows="3" animated />
        </div>

        <div v-if="pipelineSummary && !summaryLoading" class="summary-section">
          <h3 class="section-title">运行摘要</h3>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="保留">{{
              pipelineSummary.actions?.keep ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="需修改">{{
              pipelineSummary.actions?.needs_modify ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="定位损坏">{{
              pipelineSummary.actions?.locator_broken ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="定位+修改">{{
              pipelineSummary.actions?.locator_and_modify ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="废弃">{{
              pipelineSummary.actions?.deprecate ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="新增">{{
              pipelineSummary.actions?.add_new ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="冲突">{{
              pipelineSummary.actions?.conflict ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="待审核">{{
              pipelineSummary.actions?.pending_review ?? '-'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div v-if="inferredSummary && !summaryLoading" class="inferred-section">
          <h3 class="section-title">AI推断摘要</h3>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="分析摘要">{{
              inferredSummary.analysis_summary ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="是否旧项目">{{
              inferredSummary.is_old_project ? '是' : '否'
            }}</el-descriptions-item>
            <el-descriptions-item label="模式">{{
              inferredSummary.mode ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="置信度">{{
              inferredSummary.confidence ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="需要确认">{{
              inferredSummary.needs_confirmation ? '是' : '否'
            }}</el-descriptions-item>
            <el-descriptions-item v-if="inferredSummary.change_summary" label="新增能力数">{{
              inferredSummary.change_summary?.new_capabilities?.length ?? 0
            }}</el-descriptions-item>
            <el-descriptions-item v-if="inferredSummary.change_summary" label="修改能力数">{{
              inferredSummary.change_summary?.modified_capabilities?.length ?? 0
            }}</el-descriptions-item>
            <el-descriptions-item v-if="inferredSummary.change_summary" label="移除能力数">{{
              inferredSummary.change_summary?.removed_capabilities?.length ?? 0
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
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
import { ArrowLeft, ArrowDown, ArrowUp, Refresh, Loading } from '@element-plus/icons-vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import { usePipelineProgress } from './usePipelineProgress'

const {
  runData,
  initialLoading,
  isPolling,
  showConfirmDialog,
  confirmReason,
  confirmSchema,
  stepNameMap,
  artifactKindMap,
  runStatusType,
  runStatusText,
  duration,
  stepStatusType,
  stepStatusText,
  stepDuration,
  confidenceColor,
  formatTime,
  fetchRunData,
  handleResume,
  handleConfirmResume,
  goBack,
  pipelineSummary,
  inferredSummary,
  summaryLoading,
  expandedArtifactId,
  artifactDetail,
  artifactDetailLoading,
  toggleArtifactDetail,
} = usePipelineProgress()
</script>

<style scoped lang="scss">
@use './PipelineProgress.scss';
</style>
