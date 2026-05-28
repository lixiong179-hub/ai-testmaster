<template>
  <el-dialog
    v-model="visible"
    title="批量元素定位"
    width="700px"
    :close-on-click-modal="false"
    @close="close"
  >
    <div v-if="currentView === 'config'" class="config-section">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 16px">
        <template #title>已选择 {{ selectedCaseIds.length }} 个用例进行批量元素定位</template>
      </el-alert>
      <el-form label-width="100px">
        <el-form-item label="定位方式">
          <el-radio-group v-model="locatorType">
            <el-radio value="css">CSS Selector</el-radio>
            <el-radio value="xpath">XPath</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="AI辅助">
          <el-switch v-model="aiAssist" active-text="启用" inactive-text="禁用" />
          <div style="margin-top: 4px; font-size: 12px; color: #909399">
            启用后AI将根据页面截图和DOM结构智能推荐定位器
          </div>
        </el-form-item>
      </el-form>
      <el-divider v-if="batchTasks.length > 0" />
      <div v-if="batchTasks.length > 0" class="history-section">
        <h4 style="margin: 0 0 8px; color: #303133">历史任务</h4>
        <el-table :data="batchTasks" border stripe size="small" max-height="200">
          <el-table-column prop="case_title" label="用例" min-width="150" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag
                :type="
                  row.status === 'completed'
                    ? 'success'
                    : row.status === 'failed'
                      ? 'danger'
                      : 'info'
                "
                size="small"
                >{{ row.status }}</el-tag
              >
            </template>
          </el-table-column>
          <el-table-column prop="progress" label="进度" width="80" align="center">
            <template #default="{ row }"
              >{{ row.completed_steps ?? 0 }}/{{ row.total_steps ?? 0 }}</template
            >
          </el-table-column>
        </el-table>
      </div>
    </div>
    <div v-else-if="currentView === 'progress'" class="progress-section">
      <el-progress :percentage="progress" :stroke-width="20" :text-inside="true" status="" />
      <p class="progress-message">{{ progressMessage }}</p>
      <div class="progress-stats">
        <el-tag type="info">总计: {{ selectedCaseIds.length }}</el-tag>
        <el-tag type="success">成功: {{ successCount }}</el-tag>
        <el-tag type="danger">失败: {{ failCount }}</el-tag>
      </div>
    </div>
    <div v-else class="report-section">
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      />
      <div class="report-summary" v-if="hasResults">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="总计">{{ totalProcessed }}</el-descriptions-item>
          <el-descriptions-item label="成功"
            ><el-tag type="success">{{ successCount }}</el-tag></el-descriptions-item
          >
          <el-descriptions-item label="失败"
            ><el-tag type="danger">{{ failCount }}</el-tag></el-descriptions-item
          >
        </el-descriptions>
      </div>
      <el-table :data="results" border stripe max-height="400" style="margin-top: 16px">
        <el-table-column prop="case_id" label="用例ID" width="80" />
        <el-table-column prop="case_title" label="用例名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{
              row.status === 'success' ? '成功' : '失败'
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="locator" label="定位器" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <code v-if="row.locator">{{ row.locator }}</code>
            <span v-else style="color: #909399">{{ row.error_message || '未生成' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="close">{{ currentView === 'config' ? '取消' : '关闭' }}</el-button>
        <el-button v-if="currentView === 'progress'" type="danger" @click="cancelTask"
          >取消任务</el-button
        >
        <el-button
          v-if="currentView === 'config'"
          type="primary"
          :loading="loading"
          @click="startLocate"
          >开始定位</el-button
        >
        <el-button
          v-if="currentView === 'report' && failCount > 0"
          type="warning"
          @click="retryFailed"
          >重试失败项</el-button
        >
        <el-button
          v-if="currentView === 'report' && successCount > 0"
          type="primary"
          @click="applyResults"
          >应用结果</el-button
        >
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { useBatchLocator } from './useBatchLocator'

const props = defineProps<{ projectId: number }>()
const {
  visible,
  loading,
  currentView,
  selectedCaseIds,
  locatorType,
  aiAssist,
  progress,
  progressMessage,
  results,
  error,
  successCount,
  failCount,
  totalProcessed,
  hasResults,
  open,
  close,
  startLocate,
  retryFailed,
  applyResults,
  cancelTask,
  batchTasks,
  loadBatchTasks,
} = useBatchLocator(props.projectId)

function handleOpen(caseIds: number[]): void {
  open(caseIds)
  loadBatchTasks()
}

defineExpose({ open: handleOpen })
</script>

<style scoped>
.config-section {
  padding: 8px 0;
}
.progress-section {
  padding: 20px 0;
  text-align: center;
}
.progress-message {
  margin: 16px 0;
  color: #606266;
}
.progress-stats {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}
.report-section {
  padding: 8px 0;
}
.report-summary {
  margin-bottom: 8px;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
