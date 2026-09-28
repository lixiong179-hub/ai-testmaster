<template>
  <div class="audit-list-page">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>自愈审计</h2>
          <span class="header-hint">记录元素定位自愈变更，支持查看详情与回滚</span>
        </div>
      </template>

      <!-- 筛选区域 -->
      <div class="search-filter">
        <el-row :gutter="16">
          <el-col :span="5">
            <el-select
              v-model="filters.projectId"
              placeholder="选择项目"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="p in projects"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select
              v-model="filters.failureType"
              placeholder="失败类型"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="opt in failureTypeOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-col>
          <el-col :span="5">
            <div class="confidence-range">
              <el-input-number
                v-model="filters.confidenceMin"
                :min="0"
                :max="1"
                :step="0.1"
                :precision="2"
                placeholder="最低"
                controls-position="right"
                style="width: 48%"
              />
              <span class="range-sep">-</span>
              <el-input-number
                v-model="filters.confidenceMax"
                :min="0"
                :max="1"
                :step="0.1"
                :precision="2"
                placeholder="最高"
                controls-position="right"
                style="width: 48%"
              />
            </div>
          </el-col>
          <el-col :span="6">
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
              <el-icon><Search /></el-icon>搜索
            </el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-col>
        </el-row>
        <el-alert
          v-if="hasClientFilter"
          type="info"
          :closable="false"
          show-icon
          class="filter-tip"
        >
          失败类型/置信度/日期范围基于当前页数据前端过滤，如未匹配请调整分页或项目筛选。
        </el-alert>
      </div>

      <!-- 数据表格 -->
      <el-table :data="filteredAudits" style="width: 100%" v-loading="loading" stripe border>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="项目" width="140">
          <template #default>{{ currentProjectName }}</template>
        </el-table-column>
        <el-table-column prop="test_case_id" label="用例ID" width="90" />
        <el-table-column label="旧选择器" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.old_selector || '-' }}</template>
        </el-table-column>
        <el-table-column label="新选择器" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.new_selector || '-' }}</template>
        </el-table-column>
        <el-table-column label="失败类型" width="110">
          <template #default="{ row }">
            <el-tag :type="getFailureTagType(row.failure_type)" size="small">
              {{ getFailureLabel(row.failure_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="策略" width="100">
          <template #default="{ row }">
            <el-tag :type="row.strategy === 'rollback' ? 'success' : 'info'" size="small">
              {{ row.strategy }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="100">
          <template #default="{ row }">
            <span v-if="row.confidence == null" class="text-muted">-</span>
            <el-tag
              v-else
              :type="row.low_confidence ? 'warning' : 'success'"
              size="small"
            >
              {{ (row.confidence * 100).toFixed(1) }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="修复时间" width="170" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openDetail(row)">
              查看详情
            </el-button>
            <el-button
              size="small"
              link
              type="danger"
              :loading="rollingBack"
              :disabled="!canRollback(row)"
              @click="handleRollback(row)"
            >
              回滚
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无自愈审计记录" />
        </template>
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

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="自愈审计详情"
      width="640px"
      @close="closeDetail"
    >
      <el-descriptions v-if="currentAudit" :column="2" border>
        <el-descriptions-item label="审计ID">{{ currentAudit.id }}</el-descriptions-item>
        <el-descriptions-item label="用例ID">{{ currentAudit.test_case_id }}</el-descriptions-item>
        <el-descriptions-item label="步骤序号">{{ currentAudit.step_index }}</el-descriptions-item>
        <el-descriptions-item label="定位器ID">
          {{ currentAudit.locator_id ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="失败类型">
          <el-tag :type="getFailureTagType(currentAudit.failure_type)" size="small">
            {{ getFailureLabel(currentAudit.failure_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="策略">
          <el-tag
            :type="currentAudit.strategy === 'rollback' ? 'success' : 'info'"
            size="small"
          >
            {{ currentAudit.strategy }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="置信度">
          <span v-if="currentAudit.confidence == null">-</span>
          <span v-else>{{ (currentAudit.confidence * 100).toFixed(2) }}%</span>
        </el-descriptions-item>
        <el-descriptions-item label="低置信度">
          <el-tag :type="currentAudit.low_confidence ? 'warning' : 'info'" size="small">
            {{ currentAudit.low_confidence ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Token消耗">
          {{ currentAudit.token_cost }}
        </el-descriptions-item>
        <el-descriptions-item label="修复时间">{{ currentAudit.created_at }}</el-descriptions-item>
        <el-descriptions-item label="旧选择器" :span="2">
          <code class="selector-code">{{ currentAudit.old_selector || '-' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="新选择器" :span="2">
          <code class="selector-code">{{ currentAudit.new_selector || '-' }}</code>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="closeDetail">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { useAuditList, failureTypeOptions } from './useAuditList'
import type { SelfHealingAudit } from '@/api/selfHealing'
import type { TagType } from '@/types/element-plus'

const {
  loading,
  rollingBack,
  filteredAudits,
  projects,
  currentProjectName,
  detailVisible,
  currentAudit,
  pagination,
  filters,
  handleSearch,
  handleReset,
  handleSizeChange,
  handleCurrentChange,
  openDetail,
  closeDetail,
  handleRollback,
} = useAuditList()

/** 是否启用了客户端过滤条件（用于提示） */
const hasClientFilter = computed<boolean>(() => {
  return (
    !!filters.failureType ||
    filters.confidenceMin != null ||
    filters.confidenceMax != null ||
    (filters.dateRange != null && filters.dateRange.length === 2)
  )
})

/** 失败类型中文映射 */
const failureLabelMap: Record<string, string> = Object.fromEntries(
  failureTypeOptions.map((opt) => [opt.value, opt.label])
)

function getFailureLabel(type: string): string {
  return failureLabelMap[type] ?? type
}

/** 失败类型对应 Tag 颜色 */
const failureTagTypeMap: Record<string, TagType> = {
  element_gone: 'danger',
  dom_changed: 'warning',
  load_delay: 'info',
  env_noise: 'info',
}

function getFailureTagType(type: string): TagType {
  return failureTagTypeMap[type] ?? 'info'
}

/** 可回滚判断：回滚审计(strategy=rollback)无 old_selector/locator_id 不可再回滚 */
function canRollback(row: SelfHealingAudit): boolean {
  return row.strategy !== 'rollback' && row.old_selector != null && row.locator_id != null
}
</script>

<style scoped lang="scss">
.audit-list-page {
  padding: 20px;
}
.card-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
  .header-hint {
    font-size: 12px;
    color: #909399;
  }
}
.search-filter {
  margin-bottom: 16px;
}
.filter-tip {
  margin-top: 12px;
}
.confidence-range {
  display: flex;
  align-items: center;
  gap: 4px;
}
.range-sep {
  color: #909399;
}
.text-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.text-muted {
  color: #c0c4cc;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
.selector-code {
  display: block;
  padding: 6px 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  word-break: break-all;
}
</style>
