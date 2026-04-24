# Phase 3: 前端列表页面开发（8个任务）

---

## T3.1: 创建测试点列表页面基础结构

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T2.1-T2.3 |
| **时间节点** | Phase3 第1个任务 |

---

### 目标描述

创建测试点列表页面的基础结构，参考TestCaseList.vue的风格，确保UI一致性。

---

### 具体实施步骤

1. **创建页面文件
   - 在 `src/views/test-point/` 目录下创建 `TestPointList.vue`
   - 复制 `src/views/case/TestCaseList.vue` 作为起点

2. **修改页面基础结构

```vue
<template>
  <div class="test-point-list">
    <el-card class="main-card">
      <!-- 页面标题 -->
      <div class="page-header">
        <div class="header-left">
          <h2 class="page-title">测试点管理</h2>
          <span class="test-point-count" v-if="store.testPoints.length > 0">
            共 {{ store.total }} 条
          </span>
        </div>
        <div class="header-right">
          <!-- 按钮区域占位 -->
          <el-button v-if="selectedProjectId" type="primary">
            新增测试点
          </el-button>
        </div>
      </div>

      <!-- 未选择项目提示 -->
      <div v-if="!selectedProjectId" class="empty-state">
        <el-empty description="请先选择项目" />
      </div>

      <!-- 内容区域 -->
      <div v-else class="content-section" v-loading="store.loading">
        <!-- 统计卡片占位 -->
        <!-- 筛选区域占位 -->
        <!-- 列表/网格区域占位 -->
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useTestPointStore } from '@/store/testPoint';

const store = useTestPointStore();
const selectedProjectId = ref<number | null>(null); // 需要从项目Store获取
</script>

<style scoped>
/* 参考TestCaseList的样式 */
.test-point-list {
  padding: 20px;
}

.main-card {
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #ebeef5;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.test-point-count {
  margin-left: 10px;
  color: #909399;
  font-size: 14px;
}

.header-right {
  display: flex;
  gap: 10px;
}

.empty-state {
  padding: 60px 0;
}

.content-section {
  min-height: 400px;
}
</style>
```

3. **验证页面结构
   - 确保页面可以正常访问
   - 确保风格与项目一致

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考页面 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae\rules\project_rules.md` |
| Element Plus | 项目已安装 |

---

### 预期成果标准（可量化）

- [ ] 页面文件完整创建
- [ ] 页面结构完整（Header、内容区、Footer）
- [ ] 风格与项目一致
- [ ] 页面可以正常访问（无编译错误）

---

---

## T3.2: 实现统计卡片

| 属性 | 内容 |
|------|------|
| **优先级** | 🟡 中 |
| **负责人** | 前端开发 |
| **预计工时** | 0.75 小时 |
| **依赖关系** | T3.1 |
| **时间节点** | Phase3 第2个任务 |

---

### 目标描述

在测试点列表页面添加统计卡片，展示测试点总数、高/中/低优先级数量、已生成用例数等。

---

### 具体实施步骤

1. **在内容区域添加统计卡片

```vue
<div class="stats-cards">
  <div class="stat-card stat-total" @click="filterByPriority(null)">
    <div class="stat-icon">
      <el-icon><Document /></el-icon>
    </div>
    <div class="stat-info">
      <span class="stat-value">{{ store.testPoints.length }}</span>
      <span class="stat-label">全部测试点</span>
    </div>
  </div>
  <div class="stat-card stat-high" @click="filterByPriority(1)">
    <div class="stat-icon">
      <el-icon><Warning /></el-icon>
    </div>
    <div class="stat-info">
      <span class="stat-value">{{ store.highPriorityCount }}</span>
      <span class="stat-label">高优先级</span>
    </div>
  </div>
  <div class="stat-card stat-medium" @click="filterByPriority(2)">
    <div class="stat-icon">
      <el-icon><Info /></el-icon>
    </div>
    <div class="stat-info">
      <span class="stat-value">{{ store.mediumPriorityCount }}</span>
      <span class="stat-label">中优先级</span>
    </div>
  </div>
  <div class="stat-card stat-low" @click="filterByPriority(3)">
    <div class="stat-icon">
      <el-icon><CircleCheck /></el-icon>
    </div>
    <div class="stat-info">
      <span class="stat-value">{{ store.lowPriorityCount }}</span>
      <span class="stat-label">低优先级</span>
    </div>
  </div>
  <div class="stat-card stat-cases">
    <div class="stat-icon">
      <el-icon><List /></el-icon>
    </div>
    <div class="stat-info">
      <span class="stat-value">{{ store.totalTestCaseCount }}</span>
      <span class="stat-label">已生成用例</span>
    </div>
  </div>
</div>
```

2. **实现点击筛选函数

```typescript
const filterByPriority = (priority: number | null) => {
  store.setFilter({ priority });
  store.fetchTestPoints();
};
```

3. **添加相应的样式（参考TestCaseList）

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考页面 | `src/views/case/TestCaseList.vue` |
| Element Plus图标 | 项目已安装 |

---

### 预期成果标准（可量化）

- [ ] 统计卡片完整显示（5个卡片）
- [ ] 统计数据正确计算
- [ ] 点击筛选功能正常工作
- [ ] 样式美观，与项目风格一致

---

---

## T3.3: 实现筛选栏

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T3.1, T3.2 |
| **时间节点** | Phase3 第3个任务 |

---

### 目标描述

在测试点列表页面实现筛选栏，支持按模块、优先级、创建人、创建时间、关键词筛选。

---

### 具体实施步骤

1. **在统计卡片下方添加筛选栏

```vue
<div class="filter-section">
  <el-form inline :model="filterForm">
    <!-- 模块筛选 -->
    <el-form-item label="模块">
      <el-input v-model="filterForm.module" placeholder="请输入模块名称" clearable />
    </el-form-item>

    <!-- 优先级筛选 -->
    <el-form-item label="优先级">
      <el-select v-model="filterForm.priority" placeholder="请选择优先级" clearable>
        <el-option label="高" :value="1" />
        <el-option label="中" :value="2" />
        <el-option label="低" :value="3" />
      </el-select>
    </el-form-item>

    <!-- 创建人筛选 -->
    <el-form-item label="创建人">
      <el-input v-model="filterForm.created_by" placeholder="请输入创建人" clearable />
    </el-form-item>

    <!-- 创建时间筛选 -->
    <el-form-item label="创建时间">
      <el-date-picker
        v-model="filterForm.date_range"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        value-format="YYYY-MM-DD"
        clearable
      />
    </el-form-item>

    <!-- 关键词搜索 -->
    <el-form-item label="关键词">
      <el-input v-model="filterForm.keyword" placeholder="请输入关键词" clearable />
    </el-form-item>

    <!-- 按钮 -->
    <el-form-item>
      <el-button type="primary" @click="handleSearch">
        <el-icon><Search /></el-icon>
        查询
      </el-button>
      <el-button @click="handleReset">
        <el-icon><Refresh /></el-icon>
        重置
      </el-button>
    </el-form-item>
  </el-form>
</div>
```

2. **实现筛选逻辑

```typescript
import { reactive } from 'vue';

const filterForm = reactive({
  module: '',
  priority: null as number | null,
  created_by: '',
  date_range: [] as string[],
  keyword: ''
});

const handleSearch = () => {
  store.setFilter({
    module: filterForm.module || undefined,
    priority: filterForm.priority,
    created_by: filterForm.created_by || undefined,
    keyword: filterForm.keyword || undefined
  });
  store.fetchTestPoints();
};

const handleReset = () => {
  Object.assign(filterForm, {
    module: '',
    priority: null,
    created_by: '',
    date_range: [],
    keyword: ''
  });
  store.setFilter({});
  store.fetchTestPoints();
};
```

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考页面 | `src/views/case/TestCaseList.vue` |
| Element Plus组件 | 项目已安装 |

---

### 预期成果标准（可量化）

- [ ] 筛选栏完整显示
- [ ] 所有筛选条件组件正常工作
- [ ] 查询按钮正常触发筛选
- [ ] 重置按钮正常工作
- [ ] 样式美观，与项目风格一致

---

---

## T3.4: 实现表格视图

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1.5 小时 |
| **依赖关系** | T3.1-T3.3 |
| **时间节点** | Phase3 第4个任务 |

---

### 目标描述

实现测试点列表的表格视图，包含多选、所有必要列、操作列。

---

### 具体实施步骤

1. **在筛选栏下方添加表格视图

```vue
<div class="table-section">
  <!-- 批量操作按钮 -->
  <div v-if="store.selectedTestPointIds.length > 0" class="batch-actions">
    <el-tag type="warning" class="batch-tag">
      已选择 {{ store.selectedTestPointIds.length }} 条
    </el-tag>
    <el-button type="danger" @click="handleBatchDelete">
      <el-icon><Delete /></el-icon>
      批量删除
    </el-button>
    <el-button type="primary" @click="handleBatchGenerate">
      <el-icon><MagicStick /></el-icon>
      批量生成用例
    </el-button>
    <el-button @click="store.clearSelection">
      取消选择
    </el-button>
  </div>

  <!-- 表格 -->
  <el-table
    :data="store.testPoints"
    @selection-change="handleSelectionChange"
    stripe
    border
  >
    <!-- 多选列 -->
    <el-table-column type="selection" width="55" />

    <!-- 模块列 -->
    <el-table-column prop="module" label="模块" min-width="120" />

    <!-- 功能列 -->
    <el-table-column prop="function" label="功能" min-width="150" />

    <!-- 测试点列 -->
    <el-table-column prop="point" label="测试点" min-width="200" show-overflow-tooltip />

    <!-- 优先级列 -->
    <el-table-column prop="priority" label="优先级" width="100">
      <template #default="{ row }">
        <el-tag v-if="row.priority === 1" type="danger">高</el-tag>
        <el-tag v-else-if="row.priority === 2" type="warning">中</el-tag>
        <el-tag v-else type="info">低</el-tag>
      </template>
    </el-table-column>

    <!-- 已生成用例数列 -->
    <el-table-column label="已生成用例数" width="120">
      <template #default="{ row }">
        <el-link type="primary" @click="showTestCases(row)">
          {{ row.test_case_count || 0 }}
        </el-link>
      </template>
    </el-table-column>

    <!-- 创建人列 -->
    <el-table-column prop="created_by" label="创建人" width="120">
      <template #default="{ row }">
        {{ row.created_by || '-' }}
      </template>
    </el-table-column>

    <!-- 创建时间列 -->
    <el-table-column prop="create_time" label="创建时间" width="180" />

    <!-- 操作列 -->
    <el-table-column label="操作" width="220" fixed="right">
      <template #default="{ row }">
        <el-button type="primary" size="small" @click="showTestCases(row)">
          <el-icon><List /></el-icon>
          查看用例
        </el-button>
        <el-button type="success" size="small" @click="handleGenerateSingle(row)">
          <el-icon><MagicStick /></el-icon>
          生成用例
        </el-button>
        <el-button type="warning" size="small" @click="handleEdit(row)">
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
        <el-popconfirm title="确定删除吗？" @confirm="handleDelete(row)">
          <template #reference>
            <el-button type="danger" size="small">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>

  <!-- 分页 -->
  <div class="pagination">
    <el-pagination
      v-model:current-page="currentPage"
      v-model:page-size="pageSize"
      :total="store.total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handlePageChange"
    />
  </div>
</div>
```

2. **实现表格逻辑

```typescript
import { ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import * as testPointApi from '@/api/testPoint';

const currentPage = ref(1);
const pageSize = ref(20);

const handleSelectionChange = (selection: any[]) => {
  store.selectedTestPointIds = selection.map(item => item.id);
};

const handleSizeChange = (size: number) => {
  pageSize.value = size;
  currentPage.value = 1;
  store.setFilter({ skip: 0, limit: size });
  store.fetchTestPoints();
};

const handlePageChange = (page: number) => {
  currentPage.value = page;
  store.setFilter({ skip: (page - 1) * pageSize.value, limit: pageSize.value });
  store.fetchTestPoints();
};

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm('确定删除选中的测试点吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    await testPointApi.batchDeleteTestPoints(store.selectedTestPointIds);
    ElMessage.success('删除成功');
    store.fetchTestPoints();
    store.clearSelection();
  } catch {
    // 用户取消
  }
};

const handleBatchGenerate = () => {
  // 见T3.7
};

const showTestCases = (row: any) => {
  // 见T3.6
};

const handleGenerateSingle = (row: any) => {
  // 见T3.7
};

const handleEdit = (row: any) => {
  // 见T3.5
};

const handleDelete = async (row: any) => {
  try {
    await testPointApi.deleteTestPoint(row.id);
    ElMessage.success('删除成功');
    store.fetchTestPoints();
  } catch {
    ElMessage.error('删除失败');
  }
};
```

---

### 预期成果标准（可量化）

- [ ] 表格完整显示
- [ ] 所有列正确展示
- [ ] 多选功能正常工作
- [ ] 批量操作按钮正确显示
- [ ] 分页功能正常
- [ ] 样式美观，与项目风格一致

---

---

## T3.5: 实现新增/编辑测试点弹窗

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T3.4 |
| **时间节点** | Phase3 第5个任务 |

---

### 目标描述

实现新增和编辑测试点的弹窗组件，包含表单验证、提交逻辑。

---

### 具体实施步骤

1. **修改页面右上角的新增按钮，添加点击事件

```vue
<el-button v-if="selectedProjectId" type="primary" @click="openCreateDialog">
  <el-icon><Plus /></el-icon>
  新增测试点
</el-button>
```

2. **实现弹窗组件

```vue
<!-- 新增/编辑弹窗 -->
<el-dialog
  v-model="showCreateDialog"
  :title="editingTestPoint ? '编辑测试点' : '新增测试点'"
  width="600px"
  @closed="handleDialogClose"
>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="formRules"
    label-width="100px"
  >
    <el-form-item label="模块" prop="module">
      <el-input v-model="formData.module" placeholder="请输入模块名称" />
    </el-form-item>
    <el-form-item label="功能" prop="function">
      <el-input v-model="formData.function" placeholder="请输入功能名称" />
    </el-form-item>
    <el-form-item label="测试点" prop="point">
      <el-input
        v-model="formData.point"
        type="textarea"
        :rows="3"
        placeholder="请输入测试点描述"
      />
    </el-form-item>
    <el-form-item label="优先级" prop="priority">
      <el-select v-model="formData.priority" placeholder="请选择优先级">
        <el-option label="高" :value="1" />
        <el-option label="中" :value="2" />
        <el-option label="低" :value="3" />
      </el-select>
    </el-form-item>
    <el-form-item label="AI提示词" prop="ai_prompt">
      <el-input
        v-model="formData.ai_prompt"
        type="textarea"
        :rows="2"
        placeholder="可选：AI生成时的额外提示词"
      />
    </el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="showCreateDialog = false">取消</el-button>
    <el-button type="primary" @click="handleSubmit" :loading="submitting">
      确定
    </el-button>
  </template>
</el-dialog>
```

3. **实现弹窗逻辑

```typescript
import { reactive, ref } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import * as testPointApi from '@/api/testPoint';

const showCreateDialog = ref(false);
const editingTestPoint = ref<any>(null);
const submitting = ref(false);
const formRef = ref<FormInstance>();

const formData = reactive({
  module: '',
  function: '',
  point: '',
  priority: 2,
  ai_prompt: ''
});

const formRules: FormRules = {
  module: [{ required: true, message: '请输入模块名称', trigger: 'blur' }],
  function: [{ required: true, message: '请输入功能名称', trigger: 'blur' }],
  point: [{ required: true, message: '请输入测试点描述', trigger: 'blur' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }]
};

const openCreateDialog = () => {
  editingTestPoint.value = null;
  Object.assign(formData, {
    module: '',
    function: '',
    point: '',
    priority: 2,
    ai_prompt: ''
  });
  showCreateDialog.value = true;
};

const handleEdit = (row: any) => {
  editingTestPoint.value = row;
  Object.assign(formData, {
    module: row.module,
    function: row.function,
    point: row.point,
    priority: row.priority,
    ai_prompt: row.ai_prompt || ''
  });
  showCreateDialog.value = true;
};

const handleSubmit = async () => {
  if (!formRef.value) return;

  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitting.value = true;
      try {
        if (editingTestPoint.value) {
          await testPointApi.updateTestPoint(editingTestPoint.value.id, formData);
          ElMessage.success('更新成功');
        } else {
          await testPointApi.createTestPoint(formData);
          ElMessage.success('创建成功');
        }
        showCreateDialog.value = false;
        store.fetchTestPoints();
      } catch {
        ElMessage.error(editingTestPoint.value ? '更新失败' : '创建失败');
      } finally {
        submitting.value = false;
      }
    }
  });
};

const handleDialogClose = () => {
  formRef.value?.resetFields();
};
```

---

### 预期成果标准（可量化）

- [ ] 新增功能正常工作
- [ ] 编辑功能正常工作
- [ ] 表单验证正常
- [ ] 弹窗关闭时正确重置
- [ ] 样式美观，与项目风格一致

---

---

## T3.6: 实现查看关联用例弹窗

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T3.5 |
| **时间节点** | Phase3 第6个任务 |

---

### 目标描述

实现查看测试点关联用例的弹窗组件。

---

### 具体实施步骤

1. **在页面中添加查看关联用例弹窗

```vue
<!-- 查看关联用例弹窗 -->
<el-dialog
  v-model="showTestCasesDialog"
  :title="'测试点：' + (currentTestPoint?.point || '')"
  width="800px"
>
  <el-table
    :data="testCases"
    v-loading="loadingTestCases"
    stripe
    border
  >
    <el-table-column prop="title" label="用例标题" min-width="200" show-overflow-tooltip />
    <el-table-column prop="priority" label="优先级" width="100">
      <template #default="{ row }">
        <el-tag v-if="row.priority === 1" type="danger">高</el-tag>
        <el-tag v-else-if="row.priority === 2" type="warning">中</el-tag>
        <el-tag v-else type="info">低</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="create_time" label="创建时间" width="180" />
  </el-table>
</el-dialog>
```

2. **实现查看逻辑

```typescript
const showTestCasesDialog = ref(false);
const currentTestPoint = ref<any>(null);
const testCases = ref<any[]>([]);
const loadingTestCases = ref(false);

const showTestCases = async (row: any) => {
  currentTestPoint.value = row;
  showTestCasesDialog.value = true;
  loadingTestCases.value = true;
  try {
    testCases.value = await testPointApi.getTestPointTestCases(row.id);
  } catch {
    ElMessage.error('获取关联用例失败');
    testCases.value = [];
  } finally {
    loadingTestCases.value = false;
  }
};
```

---

### 预期成果标准（可量化）

- [ ] 查看关联用例功能正常工作
- [ ] 用例列表正常显示
- [ ] 加载状态正常显示
- [ ] 样式美观，与项目风格一致

---

---

## T3.7: 实现批量生成用例功能

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T3.6 |
| **时间节点** | Phase3 第7个任务 |

---

### 目标描述

实现从测试点生成用例功能，支持单条和批量生成。

---

### 具体实施步骤

1. **实现批量生成函数

```typescript
const generating = ref(false);

const handleBatchGenerate = async () => {
  try {
    await ElMessageBox.confirm('确定为选中的测试点生成用例吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    generating.value = true;
    await testPointApi.batchGenerateTestCases(store.selectedTestPointIds);
    ElMessage.success('生成成功');
    store.fetchTestPoints();
    store.clearSelection();
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('生成失败');
    }
  } finally {
    generating.value = false;
  }
};

const handleGenerateSingle = async (row: any) => {
  try {
    await ElMessageBox.confirm('确定为该测试点生成用例吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    });
    generating.value = true;
    await testPointApi.batchGenerateTestCases([row.id]);
    ElMessage.success('生成成功');
    store.fetchTestPoints();
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('生成失败');
    }
  } finally {
    generating.value = false;
  }
};
```

2. **更新表格中的按钮，添加加载状态

---

### 预期成果标准（可量化）

- [ ] 单条生成功能正常工作
- [ ] 批量生成功能正常工作
- [ ] 加载状态正常显示
- [ ] 二次确认正常显示

---

---

## T3.8: 实现卡片视图（可选，切换）

| 属性 | 内容 |
|------|------|
| **优先级** | 🟢 低 |
| **负责人** | 前端开发 |
| **预计工时** | 0.75 小时 |
| **依赖关系** | T3.4 |
| **时间节点** | Phase3 第8个任务 |

---

### 目标描述

实现卡片视图，并支持在列表视图和卡片视图之间切换。

---

### 具体实施步骤

1. **在页面右上角添加视图切换按钮

```vue
<el-button-group>
  <el-button
    :type="store.viewMode === 'list' ? 'primary' : ''"
    @click="store.viewMode = 'list'"
  >
    <el-icon><List /></el-icon>
    列表视图
  </el-button>
  <el-button
    :type="store.viewMode === 'grid' ? 'primary' : ''"
    @click="store.viewMode = 'grid'"
  >
    <el-icon><Grid /></el-icon>
    卡片视图
  </el-button>
</el-button-group>
```

2. **实现卡片视图（参考TestCaseList）

```vue
<!-- 卡片视图 -->
<div v-if="store.viewMode === 'grid'" class="grid-view">
  <!-- 卡片内容 -->
</div>
```

---

### 预期成果标准（可量化）

- [ ] 视图切换功能正常工作
- [ ] 卡片视图正常显示
- [ ] 样式美观，与项目风格一致

---

### 相关参考资料链接

| 参考 | 文件路径 |
|------|---------|
| TestCaseList.vue | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae\rules\project_rules.md` |
