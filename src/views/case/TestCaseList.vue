<template>
  <div class="test-case-list-page">
    <div class="page-hero">
      <div class="hero-copy">
        <h2 class="page-title">测试用例列表</h2>
        <p class="page-subtitle">管理和查看项目下的所有测试用例，支持筛选、排序和批量操作</p>
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
      </div>
    </div>
    <div v-if="selectedProjectId" class="workspace-card">
      <div class="stats-row">
        <div class="stat-chip">
          <span class="stat-label">总计</span><span class="stat-value">{{ stats.total }}</span>
        </div>
        <div class="stat-chip automated">
          <span class="stat-label">自动化</span
          ><span class="stat-value">{{ stats.automated }}</span>
        </div>
        <div class="stat-chip manual">
          <span class="stat-label">手工</span><span class="stat-value">{{ stats.manual }}</span>
        </div>
        <div class="stat-chip high">
          <span class="stat-label">高优先级</span
          ><span class="stat-value">{{ stats.highPriority }}</span>
        </div>
      </div>
      <div class="filter-row">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索用例名称"
          clearable
          style="width: 200px"
          @keyup.enter="fetchTestCases"
        />
        <el-select
          v-model="filters.priority"
          placeholder="优先级"
          clearable
          style="width: 120px"
          @change="fetchTestCases"
        >
          <el-option label="高" :value="1" /><el-option label="中" :value="2" /><el-option
            label="低"
            :value="3"
          />
        </el-select>
        <el-select
          v-model="filters.case_type"
          placeholder="用例类型"
          clearable
          style="width: 140px"
          @change="fetchTestCases"
        >
          <el-option label="UI自动化" value="ui_automation" /><el-option
            label="手工测试"
            value="manual"
          /><el-option label="API自动化" value="api_automation" />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          style="width: 120px"
          @change="fetchTestCases"
        >
          <el-option label="草稿" value="draft" /><el-option
            label="已评审"
            value="reviewed"
          /><el-option label="已废弃" value="deprecated" />
        </el-select>
        <el-select
          v-model="filters.target_device"
          placeholder="设备类型"
          clearable
          style="width: 130px"
          @change="fetchTestCases"
        >
          <el-option label="平板" value="tablet" /><el-option
            label="手机"
            value="phone"
          /><el-option label="桌面" value="desktop" /><el-option
            label="Web"
            value="web"
          /><el-option label="通用" value="general" />
        </el-select>
        <el-button :icon="Search" @click="fetchTestCases">查询</el-button>
        <el-button :icon="RefreshRight" @click="resetFilters">重置</el-button>
        <el-dropdown style="margin-left: auto">
          <el-button :icon="Download" :loading="exporting"
            >导出<el-icon class="el-icon--right"><ArrowDown /></el-icon
          ></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleExportAll">导出全部</el-dropdown-item>
              <el-dropdown-item @click="handleExportSelected" :disabled="selectedRows.length === 0"
                >导出选中 ({{ selectedRows.length }})</el-dropdown-item
              >
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div v-if="selectedRows.length > 0" class="batch-bar">
        <el-tag type="warning">已选 {{ selectedRows.length }} 条</el-tag>
        <el-button
          type="primary"
          size="small"
          @click="handleBatchCreateTask"
          :disabled="!selectedProjectId"
          >创建任务</el-button
        >
        <el-button
          type="warning"
          size="small"
          @click="handleBatchLocate"
          :disabled="!selectedProjectId"
          >批量元素定位</el-button
        >
        <el-button type="danger" size="small" @click="handleBatchDelete">批量删除</el-button>
      </div>
      <el-table
        :data="testCases"
        border
        stripe
        v-loading="loading"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
        row-key="id"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column
          prop="module"
          label="模块"
          min-width="120"
          sortable="custom"
          show-overflow-tooltip
        />
        <el-table-column prop="title" label="用例名称" min-width="250" show-overflow-tooltip />
        <el-table-column prop="priority" label="优先级" width="90" sortable="custom">
          <template #default="{ row }"
            ><el-tag :type="getPriorityType(row.priority)" size="small">{{
              getPriorityLabel(row.priority)
            }}</el-tag></template
          >
        </el-table-column>
        <el-table-column prop="case_type" label="类型" width="110">
          <template #default="{ row }"
            ><el-tag :type="getTypeTagType(row.case_type)" size="small">{{
              getTypeLabel(row.case_type)
            }}</el-tag></template
          >
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="created_by" label="创建人" width="100" />
        <el-table-column prop="create_time" label="创建时间" width="170" sortable="custom" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/home/case/detail/${row.id}`)"
              >查看</el-button
            >
            <el-button link type="success" @click="handleQualityAnalysis(row)">质量分析</el-button>
            <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
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
          @current-change="fetchTestCases"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>
    <el-empty v-else description="请选择项目后查看用例列表" />
    <BatchLocatorDialog ref="batchLocatorDialogRef" :project-id="selectedProjectId ?? 0" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Search, RefreshRight, Download, ArrowDown } from '@element-plus/icons-vue'
import { useTestCaseList } from './useTestCaseList'
import BatchLocatorDialog from './BatchLocatorDialog.vue'

const batchLocatorDialogRef = ref<InstanceType<typeof BatchLocatorDialog>>()

const {
  loading,
  projects,
  selectedProjectId,
  testCases,
  total,
  page,
  pageSize,
  selectedRows,
  filters,
  stats,
  handleProjectChange,
  handleSelectionChange,
  handleSortChange,
  handlePageSizeChange,
  resetFilters,
  handleDelete,
  handleBatchDelete,
  handleBatchCreateTask,
  handleBatchLocate,
  handleQualityAnalysis,
  fetchTestCases,
  getPriorityType,
  getPriorityLabel,
  getTypeLabel,
  getTypeTagType,
  setBatchLocatorRef,
  exporting,
  handleExportAll,
  handleExportSelected,
} = useTestCaseList()

watch(
  batchLocatorDialogRef,
  (ref) => {
    if (ref) setBatchLocatorRef(ref)
  },
  { immediate: true }
)
</script>

<style scoped>
.test-case-list-page {
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
.workspace-card {
  padding: 20px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
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
.stat-chip.automated {
  background: #ecf5ff;
}
.stat-chip.manual {
  background: #f0f9eb;
}
.stat-chip.high {
  background: #fef0f0;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  align-items: center;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding: 10px 16px;
  background: #fdf6ec;
  border-radius: 8px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
@media (max-width: 900px) {
  .page-hero {
    flex-direction: column;
    align-items: stretch;
  }
  .stats-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .filter-row :deep(.el-input),
  .filter-row :deep(.el-select) {
    width: 100% !important;
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
