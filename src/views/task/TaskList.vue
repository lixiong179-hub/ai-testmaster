<template>
  <div class="task-list">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>测试任务列表</span>
          <el-button type="primary" @click="createTask">
            <el-icon><Plus /></el-icon>
            创建任务
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="filter.status" placeholder="按状态筛选" clearable style="width: 150px;">
          <el-option label="全部" :value="null" />
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
      </div>

      <el-table
        v-loading="loading"
        :data="taskList"
        style="width: 100%; margin-top: 10px;"
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
            <el-space>
              <el-button
                v-if="scope.row.status === 0"
                type="success"
                size="small"
                @click.stop="startTask(scope.row)"
              >
                启动
              </el-button>
              <el-button
                v-if="scope.row.status === 1"
                type="warning"
                size="small"
                @click.stop="stopTask(scope.row)"
              >
                停止
              </el-button>
              <el-button
                type="primary"
                size="small"
                @click.stop="viewTask(scope.row)"
              >
                详情
              </el-button>
              <el-button
                type="danger"
                size="small"
                @click.stop="deleteTaskConfirm(scope.row)"
                :disabled="scope.row.status === 1"
              >
                删除
              </el-button>
            </el-space>
          </template>
        </el-table-column>
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
import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { SuccessFilled, CircleCloseFilled, Plus, Refresh } from '@element-plus/icons-vue';
import { useTaskStore } from '../../store/task';

const router = useRouter();
const route = useRoute();
const taskStore = useTaskStore();

// 项目ID
const projectId = computed(() => {
  return Number(route.params.projectId) || 0;
});

// 加载状态
const loading = computed(() => taskStore.loading);

// 筛选条件
const filter = ref({
  status: undefined as number | undefined
});

// 分页
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);

// 任务列表
const taskList = computed(() => taskStore.taskList);

// 任务状态文本
const taskStatusText = (status: number): string => {
  return taskStore.taskStatusText(status);
};

// 任务状态颜色
const taskStatusColor = (status: number): string => {
  return taskStore.taskStatusColor(status);
};

// 进度颜色
const getProgressColor = (progress: number): string => {
  if (progress < 30) return '#409EFF';
  if (progress < 70) return '#E6A23C';
  return '#67C23A';
};

// 进度状态
const getProgressStatus = (task: any): string | undefined => {
  if (task.status === 3) return 'exception';
  if (task.status === 2 && task.fail_count === 0) return 'success';
  return undefined;
};

// 行点击
const handleRowClick = (row: any) => {
  viewTask(row);
};

// 处理分页大小变化
const handleSizeChange = (size: number) => {
  pageSize.value = size;
  fetchTaskList();
};

// 处理页码变化
const handleCurrentChange = (current: number) => {
  page.value = current;
  fetchTaskList();
};

// 获取任务列表
const fetchTaskList = async () => {
  try {
    const params: any = {
      page: page.value,
      page_size: pageSize.value
    };

    if (projectId.value) {
      params.project_id = projectId.value;
    }

    if (filter.value.status !== undefined) {
      params.status = filter.value.status;
    }

    const result = await taskStore.fetchTaskList(params);
    const items = Array.isArray(result?.items) ? result.items : [];
    if (items.length !== taskStore.taskList.length) {
      taskStore.taskList = items;
    }
    total.value = result?.total || 0;
  } catch (error: any) {
    ElMessage.error(error.message || '获取任务列表失败');
  }
};

// 创建任务
const createTask = () => {
  router.push(`/home/task/create/${projectId.value}`);
};

// 查看任务详情
const viewTask = (task: any) => {
  router.push(`/home/task/detail/${task.id}?project_id=${projectId.value}`);
};

// 启动任务
const startTask = async (task: any) => {
  try {
    await ElMessageBox.confirm('确定要启动此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });

    await taskStore.startTask(task.id, projectId.value);
    ElMessage.success('任务已开始执行');
    fetchTaskList();
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '启动任务失败');
    }
  }
};

// 停止任务
const stopTask = async (task: any) => {
  try {
    await ElMessageBox.confirm('确定要停止此任务吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });

    await taskStore.stopTask(task.id, projectId.value);
    ElMessage.success('任务已停止');
    fetchTaskList();
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '停止任务失败');
    }
  }
};

// 删除任务确认
const deleteTaskConfirm = async (task: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务"${task.task_name}"吗？此操作不可恢复。`,
      '删除确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    await taskStore.deleteTask(task.id, projectId.value);
    ElMessage.success('任务删除成功');
    fetchTaskList();
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除任务失败');
    }
  }
};

// 生命周期
onMounted(() => {
  fetchTaskList();
});
</script>

<style scoped>
.task-list {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-bar {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
  align-items: center;
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

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>