<template>
  <div class="audit-log-page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>审计日志</h2>
        </div>
      </template>

      <!-- 筛选区域 -->
      <div class="search-filter">
        <el-row :gutter="16">
          <el-col :span="4">
            <el-select
              v-model="filters.action"
              placeholder="操作类型"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in actionOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-input
              v-model="filters.actorId"
              placeholder="操作人ID"
              clearable
              @keyup.enter="handleSearch"
            />
          </el-col>
          <el-col :span="4">
            <el-select
              v-model="filters.targetKind"
              placeholder="目标类型"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in targetKindOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :span="8">
            <el-date-picker
              v-model="filters.dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              value-format="YYYY-MM-DDTHH:mm:ss"
              style="width: 100%"
            />
          </el-col>
          <el-col :span="4" class="text-right">
            <el-button type="primary" @click="handleSearch">
              <el-icon><Search /></el-icon>
              搜索
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-col>
        </el-row>
      </div>

      <!-- 数据表格 -->
      <el-table :data="logs" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="action" label="操作类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionTagType(row.action)" size="small">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="actor_id" label="操作人ID" width="100" />
        <el-table-column prop="target_kind" label="目标类型" width="110">
          <template #default="{ row }">
            {{ getTargetKindLabel(row.target_kind) }}
          </template>
        </el-table-column>
        <el-table-column prop="target_id" label="目标ID" width="90" />
        <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
        <el-table-column prop="run_id" label="运行ID" width="90">
          <template #default="{ row }">
            {{ row.run_id ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="iteration_id" label="迭代ID" width="90">
          <template #default="{ row }">
            {{ row.iteration_id ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { useAuditLog, targetKindOptions, actionOptions } from './useAuditLog'
import type { TagType } from '@/types/element-plus'

const {
  loading,
  logs,
  pagination,
  filters,
  handleSearch,
  handleReset,
  handleSizeChange,
  handleCurrentChange,
} = useAuditLog()

/** 操作类型对应 Tag 颜色 */
const actionTagTypeMap: Record<string, TagType> = {
  create: 'success',
  update: 'warning',
  delete: 'danger',
  execute: 'primary',
  approve: 'success',
  reject: 'danger',
}

function getActionTagType(action: string): TagType {
  return actionTagTypeMap[action] ?? 'info'
}

/** 目标类型中文映射 */
const targetKindLabelMap: Record<string, string> = Object.fromEntries(
  targetKindOptions.map((opt) => [opt.value, opt.label])
)

function getTargetKindLabel(kind: string): string {
  return targetKindLabelMap[kind] ?? kind
}
</script>

<style scoped lang="scss">
.audit-log-page {
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
}

.search-filter {
  margin-bottom: 20px;
}

.text-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
