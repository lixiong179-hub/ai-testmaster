<template>
  <div class="iteration-list-page">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <h2>迭代管理</h2>
            <el-tag v-if="selectedProjectId" type="info" size="small">
              {{ currentProjectName }}
            </el-tag>
          </div>
          <div class="header-right">
            <el-select
              v-model="selectedProjectId"
              placeholder="请选择项目"
              filterable
              clearable
              size="default"
              class="project-select"
            >
              <el-option
                v-for="p in projectStore.projects"
                :key="p.id"
                :label="p.name"
                :value="p.id"
              />
            </el-select>
            <el-select
              v-model="statusFilter"
              placeholder="全部状态"
              clearable
              size="default"
              class="status-select"
            >
              <el-option
                v-for="opt in statusOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-button
              type="primary"
              :icon="Plus"
              :disabled="!selectedProjectId"
              @click="handleAdd"
            >
              新建迭代
            </el-button>
            <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <div v-if="!selectedProjectId" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><FolderOpened /></el-icon>
        <p class="empty-title">请先选择项目</p>
        <p class="empty-hint">选择项目后将展示该项目下的所有迭代</p>
      </div>

      <div v-else-if="loading && iterations.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="iterations.length === 0" class="empty-state">
        <el-icon :size="48" color="#c0c4cc"><Plus /></el-icon>
        <p class="empty-title">{{ statusFilter ? '该状态下暂无迭代' : '该项目暂无迭代' }}</p>
        <p class="empty-hint">
          {{ statusFilter ? '更换筛选条件或刷新列表' : '创建迭代以组织需求文档、UI 原型与回归 Pipeline' }}
        </p>
        <el-button v-if="!statusFilter" type="primary" :icon="Plus" @click="handleAdd">
          创建第一个迭代
        </el-button>
      </div>

      <el-table
        v-else
        :data="iterations"
        stripe
        border
        class="iteration-table"
        row-key="id"
      >
        <el-table-column label="迭代名称" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="iter-name">{{ row.name }}</span>
            <span v-if="row.description" class="iter-desc">{{ row.description }}</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.version }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文件数" width="90" align="center">
          <template #default="{ row }">
            <el-badge
              :value="getStats(row.id).files"
              :type="getStats(row.id).files > 0 ? 'primary' : 'info'"
              class="count-badge"
            />
          </template>
        </el-table-column>
        <el-table-column label="Pipeline 状态" width="130">
          <template #default="{ row }">
            <el-tag
              :type="getPipelineStatusType(row.status)"
              size="small"
              :effect="row.status === 'in_pipeline' ? 'dark' : 'light'"
            >
              {{ getPipelineStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.create_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-dropdown
              trigger="click"
              @command="(cmd: IterationAction) => handleCommand(cmd, row)"
            >
              <el-button size="small" link type="primary">
                操作<el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="action in getAvailableActions(row.status)"
                    :key="action.command"
                    :command="action.command"
                    :divided="action.divided"
                  >
                    {{ action.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="selectedProjectId && pagination.total > 0" class="pagination-wrapper">
        <el-pagination
          :current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>

    <!-- 新建/编辑迭代对话框 -->
    <el-dialog
      v-model="iterationManager.iterationDialogVisible"
      :title="iterationManager.iterationDialogMode === 'add' ? '新建迭代' : '编辑迭代'"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="iterationFormRef"
        :model="iterationManager.iterationFormData"
        :rules="iterationManager.iterationFormRules"
        label-width="100px"
      >
        <el-form-item label="迭代名称" prop="name">
          <el-input
            v-model="iterationManager.iterationFormData.name"
            placeholder="请输入迭代名称"
          />
        </el-form-item>
        <el-form-item label="版本号" prop="version">
          <el-input v-model="iterationManager.iterationFormData.version" placeholder="如 v1.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="iterationManager.iterationFormData.description"
            type="textarea"
            :rows="2"
            placeholder="迭代描述（可选）"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select
            v-model="iterationManager.iterationFormData.status"
            placeholder="请选择状态"
            style="width: 100%"
          >
            <el-option
              v-for="opt in statusOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期">
          <el-date-picker
            v-model="iterationManager.iterationFormData.start_date"
            type="date"
            placeholder="选择开始日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker
            v-model="iterationManager.iterationFormData.end_date"
            type="date"
            placeholder="选择结束日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="iterationManager.iterationDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="iterationManager.isSubmitting"
          @click="handleSubmit"
        >确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Plus, Refresh, FolderOpened, ArrowDown } from '@element-plus/icons-vue'
import type { FormInstance } from 'element-plus'
import { formatTime } from '@/utils/dateFormat'
import { useIterationList, type IterationAction } from './useIterationList'

const {
    loading,
    selectedProjectId,
    currentProjectName,
    iterations,
    statusFilter,
    pagination,
    projectStore,
    iterationManager,
    statusOptions,
    getStatusType,
    getStatusText,
    getStats,
    getPipelineStatusType,
    getPipelineStatusText,
    getAvailableActions,
    loadData,
    handleCommand,
} = useIterationList()

const iterationFormRef = ref<FormInstance>()

function formatDate(dateStr: string): string {
    return formatTime(dateStr)
}

function handleAdd(): void {
    if (!selectedProjectId.value) return
    iterationManager.handleAddIteration(selectedProjectId.value)
}

async function handleSubmit(): Promise<void> {
    const success = await iterationManager.handleIterationSubmit(iterationFormRef.value)
    if (success) await loadData()
}

function handlePageChange(page: number): void {
    pagination.page = page
}

function handleSizeChange(size: number): void {
    pagination.pageSize = size
    pagination.page = 1
}
</script>

<style scoped lang="scss">
@use './IterationList.scss';
</style>
