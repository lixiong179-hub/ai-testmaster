<template>
  <el-card class="section-card table-card" shadow="never">
    <div class="section-header">
      <div>
        <div class="section-title">测试点列表</div>
        <div class="section-subtitle">
          支持批量处理、关联用例查看和单点生成，适合作为日常工作台。
        </div>
      </div>
      <div class="table-summary">
        <el-tag effect="plain" type="info">共 {{ total }} 条</el-tag>
        <el-tag v-if="selectedRows.length > 0" effect="plain" type="warning"
          >已选 {{ selectedRows.length }} 条</el-tag
        >
      </div>
    </div>
    <div v-if="selectedRows.length > 0" class="batch-actions">
      <el-tag type="warning">已选择 {{ selectedRows.length }} 条</el-tag>
      <div class="batch-action-buttons">
        <el-button type="danger" @click="handleBatchDelete">批量删除</el-button>
        <el-button type="success" @click="handleBatchGenerate">批量生成用例</el-button>
      </div>
    </div>
    <el-table
      class="management-table"
      :data="testPoints"
      border
      stripe
      row-key="id"
      v-loading="loading"
      @selection-change="handleSelectionChange"
      @sort-change="handleSortChange"
    >
      <el-table-column type="selection" width="48" />
      <el-table-column prop="module" label="模块" min-width="120" sortable="custom" />
      <el-table-column prop="point" label="测试点" min-width="320" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="point-cell">
            <div class="point-text">{{ row.point }}</div>
            <div class="point-meta">
              <span>{{ row.module }}</span>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="100" sortable="custom">
        <template #default="{ row }">
          <el-tag :type="priorityTagType(row.priority)">{{ priorityText(row.priority) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="已生成用例数" width="130">
        <template #default="{ row }">
          <el-link type="primary" @click="openCasesDialog(row)">{{
            row.test_case_count ?? 0
          }}</el-link>
        </template>
      </el-table-column>
      <el-table-column prop="created_by" label="创建人" width="120" />
      <el-table-column prop="create_time" label="创建时间" width="180" sortable="custom" />
      <el-table-column label="操作" width="340" fixed="right">
        <template #default="{ row }">
          <div class="action-group">
            <el-button class="table-action action-primary" text bg @click="openCasesDialog(row)"
              >查看用例</el-button
            >
            <el-button class="table-action action-success" text bg @click="handleGenerate(row)"
              >生成用例</el-button
            >
            <el-button class="table-action action-warning" text bg @click="openEditDialog(row)"
              >编辑</el-button
            >
            <el-button class="table-action action-danger" text bg @click="handleDelete(row)"
              >删除</el-button
            >
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="table-empty-state">
          <div class="table-empty-icon">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="table-empty-title">当前筛选下暂无测试点</div>
          <div class="table-empty-text">
            可以直接从需求提取、导入 XMind，或手动新增第一条测试点。
          </div>
          <div class="table-empty-actions">
            <el-button :icon="MagicStick" @click="openExtractDialog">从需求提取</el-button>
            <el-button :icon="Upload" @click="openXmindImportDialog">导入 XMind</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreateDialog">新增测试点</el-button>
          </div>
        </div>
      </template>
    </el-table>
    <div class="pagination">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchTestPoints"
        @size-change="handlePageSizeChange"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { DataAnalysis, MagicStick, Plus, Upload } from '@element-plus/icons-vue'
import { TestPointMgmtKey } from '../useTestPointManagement'

const mgmt = inject(TestPointMgmtKey)!
const {
  testPoints,
  loading,
  total,
  page,
  pageSize,
  selectedRows,
  handleSelectionChange,
  handleSortChange,
  handlePageSizeChange,
  openCasesDialog,
  handleGenerate,
  openEditDialog,
  handleDelete,
  openExtractDialog,
  openXmindImportDialog,
  openCreateDialog,
  handleBatchDelete,
  handleBatchGenerate,
  fetchTestPoints,
  priorityText,
  priorityTagType,
} = mgmt
</script>

<style scoped>
.section-card {
  border: none;
  border-radius: 20px;
  box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05);
}
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}
.section-subtitle {
  margin-top: 6px;
  color: #7a8594;
  line-height: 1.5;
}
.table-summary,
.batch-actions,
.batch-action-buttons,
.pagination {
  display: flex;
  align-items: center;
}
.table-summary,
.batch-action-buttons {
  gap: 10px;
}
.batch-actions {
  justify-content: space-between;
  padding: 14px 16px;
  margin-bottom: 16px;
  background: linear-gradient(90deg, rgba(250, 236, 216, 0.42), rgba(255, 250, 244, 0.8));
  border: 1px solid rgba(230, 162, 60, 0.18);
  border-radius: 16px;
}
.management-table :deep(.el-table__cell) {
  padding-top: 14px;
  padding-bottom: 14px;
}
.management-table :deep(.el-table__header th) {
  background: #f7faff;
  color: #4a5565;
  font-weight: 700;
}
.point-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.point-text {
  color: #1f2d3d;
  font-weight: 600;
  line-height: 1.5;
}
.point-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #7a8594;
}
.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.table-action {
  margin-left: 0;
  border-radius: 999px;
  font-weight: 600;
}
.action-primary {
  color: #409eff;
}
.action-success {
  color: #67c23a;
}
.action-warning {
  color: #e6a23c;
}
.action-danger {
  color: #f56c6c;
}
.table-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  text-align: center;
}
.table-empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 84px;
  height: 84px;
  margin-bottom: 16px;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(103, 194, 58, 0.14));
  color: #409eff;
  font-size: 36px;
}
.table-empty-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}
.table-empty-text {
  max-width: 460px;
  margin-top: 8px;
  color: #7a8594;
  line-height: 1.6;
}
.table-empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
}
.pagination {
  justify-content: flex-end;
  margin-top: 18px;
}
@media (max-width: 960px) {
  .batch-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .batch-action-buttons,
  .table-empty-actions {
    flex-wrap: wrap;
  }
}
</style>
