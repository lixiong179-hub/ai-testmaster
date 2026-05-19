<template>
  <div class="task-list">
    <el-card class="task-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">测试任务列表</div>
            <div class="card-subtitle">
              查看任务进度、执行结果和关键状态，适合作为项目任务总览入口。
            </div>
          </div>
          <div class="header-actions">
            <el-button plain @click="goToTestPointManagement">测试点管理</el-button>
            <el-button type="primary" @click="createTask">
              <el-icon><Plus /></el-icon>
              创建任务
            </el-button>
          </div>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="filter.status" placeholder="按状态筛选" clearable class="status-filter">
          <el-option label="全部" value="" />
          <el-option label="等待执行" :value="0" />
          <el-option label="执行中" :value="1" />
          <el-option label="执行完成" :value="2" />
          <el-option label="执行失败" :value="3" />
          <el-option label="已停止" :value="4" />
        </el-select>
        <el-button @click="fetchTaskList" type="primary" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-tag effect="plain" type="info">共 {{ total }} 条任务</el-tag>
      </div>

      <el-table
        class="task-table"
        v-loading="loading"
        :data="taskList"
        style="width: 100%; margin-top: 10px"
        border
        stripe
        @row-click="handleRowClick"
      >
        <el-table-column prop="id" label="任务ID" width="80" />
        <el-table-column prop="task_name" label="任务名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="total_count" label="总用例数" width="100" align="center" />
        <el-table-column label="执行结果" width="200" align="center">
          <template #default="scope">
            <div class="result-summary">
              <span class="success-count">
                <el-icon color="#67C23A"><SuccessFilled /></el-icon>
                {{ scope.row.success_count }}
              </span>
              <span class="fail-count">
                <el-icon color="#F56C6C"><CircleCloseFilled /></el-icon>
                {{ scope.row.fail_count }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.progress || 0"
              :stroke-width="8"
              :color="getProgressColor(scope.row.progress)"
              :status="getProgressStatus(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="taskStatusColor(scope.row.status)" effect="dark">
              {{ taskStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="160" />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="scope">
            <el-space class="task-actions" wrap>
              <el-button v-if="scope.row.status === 0" type="success" size="small" @click.stop="startTask(scope.row)">启动</el-button>
              <el-button v-if="scope.row.status === 1" type="warning" size="small" @click.stop="stopTask(scope.row)">停止</el-button>
              <el-button type="primary" size="small" @click.stop="viewTask(scope.row)">详情</el-button>
              <el-button type="danger" size="small" @click.stop="deleteTaskConfirm(scope.row)" :disabled="scope.row.status === 1">删除</el-button>
            </el-space>
          </template>
        </el-table-column>
        <template #empty>
          <div class="task-empty-state">
            <div class="task-empty-title">当前项目还没有测试任务</div>
            <div class="task-empty-text">可以先创建任务，随后在这里统一查看执行进度、结果和日志。</div>
            <div class="task-empty-actions">
              <el-button plain @click="goToTestPointManagement">先去测试点管理</el-button>
              <el-button type="primary" @click="createTask"><el-icon><Plus /></el-icon>创建首个任务</el-button>
            </div>
          </div>
        </template>
      </el-table>

      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { SuccessFilled, CircleCloseFilled, Plus, Refresh } from '@element-plus/icons-vue'
import { useTaskList } from './useTaskList'

const {
  loading, filter, page, pageSize, total, taskList,
  taskStatusText, taskStatusColor, getProgressColor, getProgressStatus,
  handleSizeChange, handleCurrentChange, fetchTaskList, createTask,
  goToTestPointManagement, viewTask, handleRowClick, startTask, stopTask, deleteTaskConfirm,
} = useTaskList()
</script>

<style scoped>
.task-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.card-subtitle {
  margin-top: 6px;
  color: #7a8594;
  line-height: 1.6;
}

.filter-bar {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.status-filter {
  width: 170px;
}

.result-summary {
  display: flex;
  justify-content: center;
  gap: 15px;
}

.success-count,
.fail-count {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.task-actions {
  justify-content: center;
}

.task-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 16px;
  text-align: center;
}

.task-empty-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}

.task-empty-text {
  max-width: 420px;
  color: #7a8594;
  line-height: 1.6;
}

.task-empty-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
