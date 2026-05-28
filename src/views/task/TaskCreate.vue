<template>
  <div class="task-create">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="title">创建测试任务</span>
          <el-button @click="$router.back()">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
        </div>
      </template>

      <el-form :model="form" :rules="rules" :ref="setFormRef" label-width="120px">
        <el-form-item label="任务名称" prop="task_name">
          <el-input
            v-model="form.task_name"
            placeholder="请输入任务名称"
            clearable
            maxlength="100"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="任务描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入任务描述（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="选择用例" prop="case_ids">
          <div class="case-filter">
            <el-select
              v-model="filter.module"
              placeholder="按模块筛选"
              clearable
              style="width: 200px; margin-right: 10px"
            >
              <el-option v-for="module in modules" :key="module" :label="module" :value="module" />
            </el-select>
            <el-select
              v-model="filter.priority"
              placeholder="按优先级筛选"
              clearable
              style="width: 150px"
            >
              <el-option label="高" :value="1" />
              <el-option label="中" :value="2" />
              <el-option label="低" :value="3" />
            </el-select>
            <el-input
              v-model="filter.keyword"
              placeholder="搜索用例名称"
              clearable
              style="width: 200px; margin-left: 10px"
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch"
                  ><el-icon><Search /></el-icon
                ></el-button>
              </template>
            </el-input>
          </div>

          <div class="selection-toolbar">
            <el-checkbox
              v-model="selectAll"
              @change="(val: string | number | boolean) => handleSelectAll(val as boolean)"
            >
              全选
            </el-checkbox>
            <span class="selection-info">
              已选择 <span class="count">{{ form.case_ids.length }}</span> 条用例
            </span>
            <el-button size="small" link type="primary" @click="clearSelection">清空选择</el-button>
          </div>

          <el-table
            v-loading="loading"
            :data="filteredCases"
            style="width: 100%; margin-top: 10px"
            border
            stripe
            @selection-change="handleSelectionChange"
            :ref="setTableRef"
            height="400"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="case_no" label="用例编号" width="130" />
            <el-table-column prop="module" label="模块" width="150" show-overflow-tooltip />
            <el-table-column prop="title" label="用例标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="priority" label="优先级" width="90" align="center">
              <template #default="scope">
                <el-tag :type="priorityType(scope.row.priority)" size="small">{{
                  priorityText(scope.row.priority)
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="case_type" label="类型" width="100" align="center">
              <template #default="scope">{{ scope.row.case_type || '-' }}</template>
            </el-table-column>
          </el-table>

          <div class="pagination-wrapper" v-if="total > filteredCases.length">
            <el-pagination
              v-model:current-page="page"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="total"
              layout="prev, pager, next"
              small
              @current-change="handlePageChange"
            />
          </div>
        </el-form-item>

        <el-form-item>
          <el-space>
            <el-button type="primary" @click="submitForm" :loading="submitting"
              ><el-icon><Check /></el-icon>创建任务</el-button
            >
            <el-button @click="resetForm"
              ><el-icon><RefreshLeft /></el-icon>重置</el-button
            >
            <el-button @click="$router.back()"> 取消 </el-button>
          </el-space>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Search, Check, RefreshLeft } from '@element-plus/icons-vue'
import { useTaskCreate } from './useTaskCreate'

const {
  formRef,
  tableRef,
  loading,
  submitting,
  form,
  filter,
  page,
  pageSize,
  total,
  modules,
  filteredCases,
  selectAll,
  rules,
  priorityText,
  priorityType,
  handleSelectionChange,
  handleSelectAll,
  clearSelection,
  handleSearch,
  handlePageChange,
  submitForm,
  resetForm,
} = useTaskCreate()

const setFormRef = (el: unknown) => {
  formRef.value = el
}
const setTableRef = (el: unknown) => {
  tableRef.value = el
}
</script>

<style scoped>
.task-create {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header .title {
  font-size: 18px;
  font-weight: 600;
}

.case-filter {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
}

.selection-toolbar {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.selection-info {
  color: #606266;
  font-size: 14px;
}

.selection-info .count {
  color: #409eff;
  font-weight: 700;
  font-size: 16px;
}

.pagination-wrapper {
  margin-top: 10px;
  display: flex;
  justify-content: center;
}
</style>
