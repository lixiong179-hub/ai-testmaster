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

      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
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
              style="width: 200px; margin-right: 10px;"
            >
              <el-option
                v-for="module in modules"
                :key="module"
                :label="module"
                :value="module"
              />
            </el-select>
            <el-select
              v-model="filter.priority"
              placeholder="按优先级筛选"
              clearable
              style="width: 150px;"
            >
              <el-option label="高" :value="1" />
              <el-option label="中" :value="2" />
              <el-option label="低" :value="3" />
            </el-select>
            <el-input
              v-model="filter.keyword"
              placeholder="搜索用例名称"
              clearable
              style="width: 200px; margin-left: 10px;"
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch">
                  <el-icon><Search /></el-icon>
                </el-button>
              </template>
            </el-input>
          </div>

          <div class="selection-toolbar">
            <el-checkbox v-model="selectAll" @change="handleSelectAll">
              全选
            </el-checkbox>
            <span class="selection-info">
              已选择 <span class="count">{{ form.case_ids.length }}</span> 条用例
            </span>
            <el-button size="small" link type="primary" @click="clearSelection">
              清空选择
            </el-button>
          </div>

          <el-table
            v-loading="loading"
            :data="filteredCases"
            style="width: 100%; margin-top: 10px;"
            border
            stripe
            @selection-change="handleSelectionChange"
            ref="tableRef"
            height="400"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="case_no" label="用例编号" width="130" />
            <el-table-column prop="module" label="模块" width="150" show-overflow-tooltip />
            <el-table-column prop="title" label="用例标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="priority" label="优先级" width="90" align="center">
              <template #default="scope">
                <el-tag :type="priorityType(scope.row.priority)" size="small">
                  {{ priorityText(scope.row.priority) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="case_type" label="类型" width="100" align="center">
              <template #default="scope">
                {{ scope.row.case_type || '-' }}
              </template>
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
            <el-button type="primary" @click="submitForm" :loading="submitting">
              <el-icon><Check /></el-icon>
              创建任务
            </el-button>
            <el-button @click="resetForm">
              <el-icon><RefreshLeft /></el-icon>
              重置
            </el-button>
            <el-button @click="$router.back()">
              取消
            </el-button>
          </el-space>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { ArrowLeft, Search, Check, RefreshLeft } from '@element-plus/icons-vue';
import { useTaskStore } from '../../store/task';
import request from '@/utils/request';

const router = useRouter();
const route = useRoute();
const taskStore = useTaskStore();
const formRef = ref();
const tableRef = ref();
const loading = ref(false);
const submitting = ref(false);

// 项目ID
const projectId = computed(() => {
  return Number(route.params.projectId) || 0;
});

// 表单数据
const form = ref({
  task_name: '',
  description: '',
  project_id: '' as number | '',
  case_ids: [] as number[]
});

// 监听projectId变化，更新表单
watch(projectId, (newVal) => {
  form.value.project_id = newVal;
}, { immediate: true });

// 筛选条件
const filter = ref({
  module: '',
  priority: '' as number | '',
  keyword: ''
});

// 用例列表
const cases = ref<any[]>([]);

// 分页
const page = ref(1);
const pageSize = ref(50);
const total = ref(0);

// 模块列表
const modules = computed(() => {
  const moduleSet = new Set<string>();
  cases.value.forEach(item => {
    if (item.module) moduleSet.add(item.module);
  });
  return Array.from(moduleSet);
});

// 筛选后的用例
const filteredCases = computed(() => {
  return cases.value.filter(item => {
    let match = true;
    if (filter.value.module) {
      match = match && item.module === filter.value.module;
    }
    if (filter.value.priority !== '') {
      match = match && item.priority === filter.value.priority;
    }
    if (filter.value.keyword) {
      const keyword = filter.value.keyword.toLowerCase();
      match = match && (
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.case_no && item.case_no.toLowerCase().includes(keyword))
      );
    }
    return match;
  });
});

// 全选状态
const selectAll = computed({
  get: () => {
    if (filteredCases.value.length === 0) return false;
    return filteredCases.value.every(item =>
      form.value.case_ids.includes(item.id)
    );
  },
  set: (value) => {
    if (value) {
      const ids = filteredCases.value.map(item => item.id);
      const newIds = [...new Set([...form.value.case_ids, ...ids])];
      form.value.case_ids = newIds;
    } else {
      const idsToRemove = filteredCases.value.map(item => item.id);
      form.value.case_ids = form.value.case_ids.filter(id => !idsToRemove.includes(id));
    }
  }
});

// 表单验证规则
const rules = {
  task_name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ],
  case_ids: [
    {
      required: true,
      validator: (_rule: any, value: any, callback: any) => {
        if (value.length === 0) {
          callback(new Error('请至少选择一条用例'));
        } else {
          callback();
        }
      },
      trigger: 'change'
    }
  ]
};

// 优先级文本
const priorityText = (priority: number | undefined): string => {
  const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' };
  return priority ? (map[priority] || '未知') : '-';
};

// 优先级类型
const priorityType = (priority: number | undefined): string => {
  const map: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'success' };
  return priority ? (map[priority] || 'info') : 'info';
};

// 处理表格选择变化
const handleSelectionChange = (selection: any[]) => {
  form.value.case_ids = selection.map(item => item.id);
};

// 处理全选
const handleSelectAll = (value: boolean) => {
  if (value) {
    tableRef.value?.toggleAllSelection();
  } else {
    tableRef.value?.clearSelection();
  }
};

// 清空选择
const clearSelection = () => {
  tableRef.value?.clearSelection();
  form.value.case_ids = [];
};

// 搜索
const handleSearch = () => {
  page.value = 1;
};

// 分页变化
const handlePageChange = (newPage: number) => {
  page.value = newPage;
};

// 提交表单
const submitForm = async () => {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid: boolean) => {
    if (valid) {
      submitting.value = true;
      try {
        await taskStore.createTask({
          task_name: form.value.task_name,
          project_id: form.value.project_id as number,
          description: form.value.description,
          case_ids: form.value.case_ids
        });

        ElMessage.success('任务创建成功');
        router.push(`/home/task/list/${projectId.value}`);
      } catch (error: any) {
        ElMessage.error(error.message || '任务创建失败');
      } finally {
        submitting.value = false;
      }
    }
  });
};

// 重置表单
const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields();
    form.value.description = '';
    form.value.case_ids = [];
    tableRef.value?.clearSelection();
  }
};

// 获取项目下的测试用例
const fetchProjectCases = async () => {
  loading.value = true;
  try {
    // 尝试从 store 获取任务列表（可能包含用例信息）
    const response = await taskStore.fetchTaskList({
      project_id: projectId.value,
      page: 1,
      page_size: 1000
    });

    // 尝试获取用例列表 - 使用专门的用例 API
    try {
      const caseResponse = await request.get('/api/v1/testCase', {
        params: { project_id: projectId.value, page: 1, page_size: 1000 }
      }) as any;
      const data = caseResponse?.data || caseResponse || {};
      cases.value = data.items || data.data?.items || [];
      total.value = cases.value.length;
    } catch {
      // 如果用例 API 失败，使用任务列表数据
      const data = response?.items || [];
      cases.value = data;
      total.value = response?.total || data.length;
    }

    if (cases.value.length === 0) {
      ElMessage.warning('该项目下暂无测试用例，请先生成测试用例');
    }
  } catch (error: any) {
    console.error('获取用例列表失败:', error);
    ElMessage.error(error.message || '获取用例列表失败');
  } finally {
    loading.value = false;
  }
};

// 生命周期
onMounted(() => {
  fetchProjectCases();
});
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
  color: #409EFF;
  font-weight: 700;
  font-size: 16px;
}

.pagination-wrapper {
  margin-top: 10px;
  display: flex;
  justify-content: center;
}
</style>