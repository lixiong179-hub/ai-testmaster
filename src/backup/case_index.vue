<template>
  <div class="case-list-container">
    <!-- 页面标题和操作栏 -->
    <div class="page-header">
      <h2>测试用例管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新建用例
        </el-button>
        <el-button @click="handleAIGenerate">
          <el-icon><MagicStick /></el-icon>
          AI生成
        </el-button>
        <el-dropdown>
          <el-button>
            <el-icon><Download /></el-icon>
            导出
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="handleExportAll">导出全部</el-dropdown-item>
              <el-dropdown-item @click="handleExportSelected" :disabled="selectedCases.length === 0">
                导出选中 ({{ selectedCases.length }})
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button @click="handleImport">
          <el-icon><Upload /></el-icon>
          导入
        </el-button>
        <el-button type="danger" @click="handleBatchDelete" :disabled="selectedCases.length === 0">
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedCases.length }})
        </el-button>
      </div>
    </div>

    <!-- 筛选条件 -->
    <div class="filter-container">
      <el-row :gutter="20">
        <el-col :span="5">
          <el-select v-model="queryParams.project_id" placeholder="选择项目" clearable filterable @change="handleProjectChange">
            <el-option
              v-for="project in projectList"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-input
            v-model="queryParams.keyword"
            placeholder="用例名称/模块"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-select v-model="queryParams.type" placeholder="用例类型" clearable>
            <el-option label="UI自动化" value="ui_automation" />
            <el-option label="手工测试" value="manual" />
            <el-option label="API自动化" value="api_automation" />
            <el-option label="性能测试" value="performance" />
            <el-option label="安全测试" value="security" />
          </el-select>
        </el-col>
        <el-col :span="3">
          <el-select v-model="queryParams.priority" placeholder="优先级" clearable>
            <el-option label="高(P0)" :value="1" />
            <el-option label="中(P2)" :value="2" />
            <el-option label="低(P3)" :value="3" />
          </el-select>
        </el-col>
        <el-col :span="7">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetFilter">重置</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 测试用例列表 -->
    <div class="case-table-container">
      <el-table
        v-loading="loading"
        :data="caseList"
        style="width: 100%"
        @selection-change="handleSelectionChange"
        height="calc(100vh - 320px)"
        border
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="case_no" label="用例编号" width="150" show-overflow-tooltip />
        <el-table-column prop="title" label="用例名称" min-width="200">
          <template #default="scope">
          <el-link type="primary" @click="handleView(scope.row)">
              {{ scope.row.title || scope.row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column prop="module" label="模块" width="150" show-overflow-tooltip />
        <el-table-column prop="case_type" label="类型" width="120">
          <template #default="scope">
            <el-tag :type="getTypeTagType(scope.row.case_type || scope.row.type)">
              {{ getTypeLabel(scope.row.case_type || scope.row.type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="test_category" label="分类" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.test_category" :type="getCategoryTagType(scope.row.test_category)">
              {{ getCategoryLabel(scope.row.test_category) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="scope">
            <el-tag :type="getPriorityTagType(scope.row.priority)">
              {{ getPriorityLabel(scope.row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generate_status" label="生成状态" width="100">
          <template #default="scope">
            <el-tag v-if="scope.row.generate_status === 1" type="success">成功</el-tag>
            <el-tag v-else-if="scope.row.generate_status === 2" type="danger">失败</el-tag>
            <el-tag v-else type="info">生成中</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="handleView(scope.row)">
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button size="small" type="primary" @click="handleEdit(scope.row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row.id)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-container">
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.page_size"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 导入文件对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入测试用例"
      width="500px"
    >
      <el-upload
        class="upload-demo"
        action=""
        :auto-upload="false"
        :on-change="handleFileChange"
        :show-file-list="true"
        accept=".xlsx,.xls,.json"
      >
        <el-button type="primary">
          <el-icon><Upload /></el-icon>
          选择文件
        </el-button>
        <template #tip>
          <div class="el-upload__tip">
            支持 .xlsx, .xls, .json 格式文件
          </div>
        </template>
      </el-upload>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleImportConfirm" :loading="importLoading">
            导入
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import caseApi from '@/api/case';
// 类型从全局 case.d.ts 声明文件获取，无需显式导入
import request from '@/utils/request';
import { Plus, MagicStick, Download, Upload, Delete, Search, View, Edit, ArrowDown } from '@element-plus/icons-vue';

const router = useRouter();

// 状态管理
const caseList = ref<TestCase[]>([]);
const total = ref(0);
const loading = ref(false);
const selectedCases = ref<TestCase[]>([]);
const importDialogVisible = ref(false);
const importLoading = ref(false);
const selectedFile = ref<File | null>(null);
const projectList = ref<any[]>([]);

// 查询参数
const queryParams = ref<CaseQueryParams>({
  page: 1,
  page_size: 20,
  project_id: undefined
});

// 获取项目列表
const fetchProjectList = async () => {
  try {
    const response = await request.get('/api/v1/project/list') as { data: { items: Array<{ id: number; name: string }> } };
    if (response && response.data && response.data.items) {
      projectList.value = response.data.items.filter((p: any) => p.name !== '默认项目');
    }
  } catch (error) {
    console.error('获取项目列表失败:', error);
  }
};

// 项目变更处理
const handleProjectChange = () => {
  queryParams.value.page = 1;
  fetchCaseList();
};

// 初始化
onMounted(async () => {
  await fetchProjectList();
  fetchCaseList();
});

// 获取测试用例列表
const fetchCaseList = async () => {
  loading.value = true;
  try {
    const response: any = await caseApi.getCaseList(queryParams.value);
    caseList.value = response.data?.items || response.items || [];
    total.value = response.data?.total || response.total || 0;
  } catch (error) {
    ElMessage.error('获取测试用例列表失败');
  } finally {
    loading.value = false;
  }
};

// 搜索
const handleSearch = () => {
  queryParams.value.page = 1;
  fetchCaseList();
};

// 重置筛选
const resetFilter = () => {
  queryParams.value = {
    page: 1,
    page_size: queryParams.value.page_size,
    project_id: undefined,
    keyword: undefined,
    type: undefined,
    priority: undefined
  };
  fetchCaseList();
};

// 分页处理
const handleSizeChange = (size: number) => {
  queryParams.value.page_size = size;
  fetchCaseList();
};

const handleCurrentChange = (current: number) => {
  queryParams.value.page = current;
  fetchCaseList();
};

// 选择变更
const handleSelectionChange = (val: TestCase[]) => {
  selectedCases.value = val;
};

// 新建用例
const handleCreate = () => {
  router.push('/case/detail');
};

// 查看用例
const handleView = (caseItem: TestCase) => {
  router.push(`/case/detail?id=${caseItem.id}`);
};

// 编辑用例
const handleEdit = (caseItem: TestCase) => {
  router.push(`/case/detail?id=${caseItem.id}&mode=edit`);
};

// AI生成用例
const handleAIGenerate = () => {
  router.push('/case/ai-generate');
};

// 删除用例
const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm('确定要删除这个测试用例吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    
    await caseApi.deleteCase(id);
    ElMessage.success('删除成功');
    fetchCaseList();
  } catch (error) {
    // 取消删除
  }
};

// 批量删除
const handleBatchDelete = async () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning('请选择要删除的测试用例');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedCases.value.length} 个测试用例吗？`,
      '批量删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    const ids = selectedCases.value.map((item: TestCase) => item.id);
    await caseApi.batchDeleteCases(ids);
    ElMessage.success('批量删除成功');
    selectedCases.value = [];
    fetchCaseList();
  } catch (error) {
    // 取消删除
  }
};

// 导出全部
const handleExportAll = async () => {
  try {
    const blob = await caseApi.exportCases();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error('导出失败');
  }
};

// 导出选中
const handleExportSelected = async () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning('请选择要导出的测试用例');
    return;
  }

  try {
    const ids = selectedCases.value.map((item: TestCase) => item.id);
    const blob = await caseApi.exportCases(ids);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `测试用例_${new Date().toISOString().slice(0, 10)}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error('导出失败');
  }
};

// 导入用例
const handleImport = () => {
  importDialogVisible.value = true;
};

// 文件选择
const handleFileChange = (file: any) => {
  selectedFile.value = file.raw;
};

// 确认导入
const handleImportConfirm = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择要导入的文件');
    return;
  }

  importLoading.value = true;
  try {
    const result = await caseApi.importCases(selectedFile.value);
    ElMessage.success(`导入成功！成功: ${result.success}, 失败: ${result.failed}`);
    importDialogVisible.value = false;
    selectedFile.value = null;
    fetchCaseList();
  } catch (error) {
    ElMessage.error('导入失败');
  } finally {
    importLoading.value = false;
  }
};

// 辅助方法
const getTypeTagType = (type: string) => {
  const typeMap: Record<string, string> = {
    'ui_automation': 'success',
    'manual': 'info',
    'api_automation': '',
    'performance': 'warning',
    'security': 'danger',
    'UI': 'success',
    'API': '',
    '功能': 'info',
    '功能测试': 'info',
    'functional': 'info',
  };
  return typeMap[type] || 'info';
};

const getTypeLabel = (type: string) => {
  const typeMap: Record<string, string> = {
    'ui_automation': 'UI自动化',
    'manual': '手工测试',
    'api_automation': 'API自动化',
    'performance': '性能测试',
    'security': '安全测试',
    'UI': 'UI自动化',
    'API': 'API自动化',
    '功能': '手工测试',
    '功能测试': '手工测试',
    'functional': '手工测试',
  };
  return typeMap[type] || type;
};

const getCategoryLabel = (category: string) => {
  return getTypeLabel(category);
};

const getCategoryTagType = (category: string) => {
  return getTypeTagType(category);
};

const getPriorityTagType = (priority: number | string) => {
  const priorityMap: Record<string, string> = {
    1: 'danger',
    2: 'warning',
    3: 'info',
    'low': 'info',
    'medium': 'warning',
    'high': 'danger'
  };
  return priorityMap[String(priority)] || 'info';
};

const getPriorityLabel = (priority: number | string) => {
  const priorityMap: Record<string, string> = {
    1: '高(P0)',
    2: '中(P2)',
    3: '低(P3)',
    'low': '低',
    'medium': '中',
    'high': '高'
  };
  return priorityMap[String(priority)] || String(priority);
};
</script>

<style scoped>
.case-list-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-container {
  margin-bottom: 20px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.case-table-container {
  margin-bottom: 20px;
}

.pagination-container {
  display: flex;
  justify-content: flex-end;
}

.dialog-footer {
  text-align: right;
}
</style>
