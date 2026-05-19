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
          <el-descriptions-item label="Pipeline 版本">{{ runData.pipeline_version }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatTime(runData.started_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束时间">{{ formatTime(runData.finished_at) }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ duration }}</el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="runData.error" :title="runData.error" type="error" show-icon :closable="false" class="error-alert" />

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
              <el-tag v-if="row.degraded" type="warning" size="small" effect="dark" class="degraded-badge">降级</el-tag>
              <el-tag v-if="row.retried_count > 0" type="info" size="small" class="retry-badge">重试{{ row.retried_count }}次</el-tag>
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
        <el-table v-if="runData.artifacts.length > 0" :data="runData.artifacts" stripe class="artifacts-table">
          <el-table-column label="类型" prop="kind" min-width="180">
            <template #default="{ row }">{{ artifactKindMap[row.kind] || row.kind }}</template>
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
import { ArrowLeft, Refresh, Loading } from '@element-plus/icons-vue'
import ConfirmationDialog from '@/components/ConfirmationDialog.vue'
import { usePipelineProgress } from './usePipelineProgress'

const {
  runData, initialLoading, isPolling, showConfirmDialog,
  confirmReason, confirmSchema, stepNameMap, artifactKindMap,
  runStatusType, runStatusText, duration,
  stepStatusType, stepStatusText, stepDuration, confidenceColor, formatTime,
  fetchRunData, handleResume, handleConfirmResume, goBack,
} = usePipelineProgress()
</script>

<style scoped lang="scss">
@import './PipelineProgress.scss';
</style>
