<template>
  <div class="test-data-editor">
    <div class="editor-header">
      <h3>测试数据管理</h3>
      <div class="header-actions">
        <el-button type="primary" size="small" @click="handleAutoGenerate" :loading="autoGenerating">
          <el-icon><MagicStick /></el-icon>
          智能生成
        </el-button>
        <el-button type="success" size="small" @click="handleGenerateAll" :loading="generating">
          <el-icon><Refresh /></el-icon>
          生成数据
        </el-button>
        <el-button type="primary" size="small" @click="handleAdd">
          <el-icon><Plus /></el-icon>
          添加字段
        </el-button>
      </div>
    </div>

    <!-- 测试数据列表 -->
    <el-table
      :data="testDataList"
      style="width: 100%"
      border
      v-loading="loading"
    >
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="字段名称" min-width="150">
        <template #default="{ row }">
          <el-input v-if="row.isEditing" v-model="row.field_name" placeholder="字段名称" size="small" />
          <span v-else>{{ row.field_name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="数据类型" width="120">
        <template #default="{ row }">
          <el-select v-if="row.isEditing" v-model="row.field_type" size="small" style="width: 100%">
            <el-option
              v-for="option in dataTypeOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-tag v-else :type="getDataTypeTagType(row.field_type)">
            {{ getDataTypeLabel(row.field_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="生成规则" width="120">
        <template #default="{ row }">
          <el-select v-if="row.isEditing" v-model="row.generation_rule" size="small" style="width: 100%">
            <el-option
              v-for="option in generationRuleOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <span v-else>{{ getGenerationRuleLabel(row.generation_rule) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="数据值/配置" min-width="200">
        <template #default="{ row }">
          <template v-if="row.isEditing">
            <el-input
              v-if="row.generation_rule === 'fixed'"
              v-model="row.data_value"
              placeholder="固定值"
              size="small"
            />
            <el-input
              v-else-if="row.generation_rule === 'custom'"
              v-model="row.data_value"
              placeholder="自定义规则，如: ${random.product_name}"
              size="small"
            />
            <div v-else-if="row.generation_rule === 'boundary'" class="boundary-config">
              <el-input-number v-model="row.min_value" placeholder="最小值" size="small" :controls="false" style="width: 80px" />
              <span style="margin: 0 5px">-</span>
              <el-input-number v-model="row.max_value" placeholder="最大值" size="small" :controls="false" style="width: 80px" />
            </div>
            <div v-else class="length-config">
              <el-input-number v-model="row.min_length" placeholder="最小长度" size="small" :controls="false" style="width: 80px" />
              <span style="margin: 0 5px">-</span>
              <el-input-number v-model="row.max_length" placeholder="最大长度" size="small" :controls="false" style="width: 80px" />
            </div>
          </template>
          <template v-else>
            <span v-if="row.data_value" class="data-value">{{ row.data_value }}</span>
            <span v-else-if="row.min_value !== null && row.max_value !== null" class="range-value">
              {{ row.min_value }} - {{ row.max_value }}
            </span>
            <span v-else-if="row.min_length !== null && row.max_length !== null" class="range-value">
              长度: {{ row.min_length }} - {{ row.max_length }}
            </span>
            <span v-else class="empty-value">-</span>
          </template>
        </template>
      </el-table-column>
      <el-table-column label="必填" width="80" align="center">
        <template #default="{ row }">
          <el-switch v-if="row.isEditing" v-model="row.is_required" size="small" />
          <el-tag v-else :type="row.is_required ? 'danger' : 'info'" size="small">
            {{ row.is_required ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="150">
        <template #default="{ row }">
          <el-input v-if="row.isEditing" v-model="row.description" placeholder="描述" size="small" />
          <span v-else class="description">{{ row.description || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="预览" width="150">
        <template #default="{ row }">
          <span v-if="generatedData[row.field_name]" class="preview-value">
            {{ generatedData[row.field_name] }}
          </span>
          <span v-else class="empty-value">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row, $index }">
          <template v-if="row.isEditing">
            <el-button type="primary" size="small" @click="handleSave(row)">
              保存
            </el-button>
            <el-button size="small" @click="handleCancel(row, $index)">
              取消
            </el-button>
          </template>
          <template v-else>
            <el-button type="primary" size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态 -->
    <el-empty v-if="testDataList.length === 0 && !loading" description="暂无测试数据" />

    <!-- 生成结果预览 -->
    <el-card v-if="Object.keys(generatedData).length > 0" class="preview-card" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>生成结果预览</span>
          <el-button type="primary" size="small" @click="handleCopy">
            <el-icon><CopyDocument /></el-icon>
            复制JSON
          </el-button>
        </div>
      </template>
      <pre class="json-preview">{{ JSON.stringify(generatedData, null, 2) }}</pre>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Edit, Delete, Refresh, MagicStick, CopyDocument } from '@element-plus/icons-vue';
import {
  testDataApi,
  dataTypeOptions,
  generationRuleOptions,
  DataType,
  GenerationRule,
  type TestData
} from '@/api/testData';

// Props
const props = defineProps<{
  stepId: number;
  stepAction?: string;
}>();

// Emits
const emit = defineEmits<{
  (e: 'update', data: TestData[]): void;
}>();

// 状态
const loading = ref(false);
const generating = ref(false);
const autoGenerating = ref(false);
const testDataList = ref<(TestData & { isEditing?: boolean; isNew?: boolean })[]>([]);
const generatedData = ref<Record<string, any>>({});

// 获取测试数据列表
const fetchTestData = async () => {
  if (!props.stepId) return;
  
  loading.value = true;
  try {
    const response = await testDataApi.getByStepId(props.stepId);
    testDataList.value = response.data_list.map(item => ({
      ...item,
      isEditing: false
    }));
    emit('update', testDataList.value);
  } catch (error) {
    ElMessage.error('获取测试数据失败');
  } finally {
    loading.value = false;
  }
};

// 添加新字段
const handleAdd = () => {
  const newItem = {
    id: 0,
    step_id: props.stepId,
    field_name: '',
    field_type: DataType.TEXT,
    generation_rule: GenerationRule.RANDOM,
    data_value: null,
    rule_config: null,
    min_length: null,
    max_length: null,
    min_value: null,
    max_value: null,
    enum_values: null,
    description: '',
    is_required: true,
    sort_order: testDataList.value.length,
    isEditing: true,
    isNew: true
  };
  testDataList.value.push(newItem);
};

// 编辑
const handleEdit = (row: TestData & { isEditing?: boolean }) => {
  row.isEditing = true;
};

// 保存
const handleSave = async (row: TestData & { isEditing?: boolean; isNew?: boolean }) => {
  if (!row.field_name) {
    ElMessage.warning('请输入字段名称');
    return;
  }

  try {
    const saveData = {
      step_id: row.step_id,
      field_name: row.field_name,
      field_type: row.field_type as DataType,
      generation_rule: row.generation_rule as GenerationRule,
      data_value: row.data_value || undefined,
      rule_config: row.rule_config || undefined,
      min_length: row.min_length || undefined,
      max_length: row.max_length || undefined,
      min_value: row.min_value || undefined,
      max_value: row.max_value || undefined,
      enum_values: row.enum_values || undefined,
      description: row.description || undefined,
      is_required: row.is_required,
      sort_order: row.sort_order
    };

    if (row.isNew) {
      const response = await testDataApi.create(saveData);
      Object.assign(row, response);
      row.isNew = false;
      ElMessage.success('创建成功');
    } else {
      const response = await testDataApi.update(row.id, saveData);
      Object.assign(row, response);
      ElMessage.success('更新成功');
    }
    row.isEditing = false;
    emit('update', testDataList.value);
  } catch (error) {
    ElMessage.error('保存失败');
  }
};

// 取消
const handleCancel = (row: TestData & { isEditing?: boolean; isNew?: boolean }, index: number) => {
  if (row.isNew) {
    testDataList.value.splice(index, 1);
  } else {
    row.isEditing = false;
    fetchTestData();
  }
};

// 删除
const handleDelete = async (row: TestData) => {
  try {
    await ElMessageBox.confirm('确定删除该测试数据吗？', '提示', {
      type: 'warning'
    });
    await testDataApi.delete(row.id);
    ElMessage.success('删除成功');
    fetchTestData();
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
};

// 生成数据
const handleGenerateAll = async () => {
  if (testDataList.value.length === 0) {
    ElMessage.warning('没有测试数据可生成');
    return;
  }

  generating.value = true;
  try {
    const response = await testDataApi.generate(props.stepId);
    generatedData.value = response.generated_data;
    ElMessage.success('数据生成成功');
  } catch (error) {
    ElMessage.error('数据生成失败');
  } finally {
    generating.value = false;
  }
};

// 智能生成
const handleAutoGenerate = async () => {
  if (!props.stepAction) {
    ElMessage.warning('步骤操作描述为空，无法智能生成');
    return;
  }

  autoGenerating.value = true;
  try {
    const response = await testDataApi.autoGenerate(props.stepId, props.stepAction);
    if (response.count > 0) {
      ElMessage.success(`成功生成 ${response.count} 个测试数据字段`);
      fetchTestData();
    } else {
      ElMessage.info('未识别到需要生成的测试数据');
    }
  } catch (error) {
    ElMessage.error('智能生成失败');
  } finally {
    autoGenerating.value = false;
  }
};

// 复制JSON
const handleCopy = () => {
  const jsonStr = JSON.stringify(generatedData.value, null, 2);
  navigator.clipboard.writeText(jsonStr).then(() => {
    ElMessage.success('已复制到剪贴板');
  }).catch(() => {
    ElMessage.error('复制失败');
  });
};

// 获取数据类型标签
const getDataTypeLabel = (type: string) => {
  const option = dataTypeOptions.find(opt => opt.value === type);
  return option?.label || type;
};

// 获取数据类型标签样式
const getDataTypeTagType = (type: string) => {
  const typeMap: Record<string, string> = {
    text: '',
    email: 'success',
    phone: 'success',
    number: 'warning',
    date: 'info',
    datetime: 'info',
    boolean: 'primary',
    url: 'success',
    username: '',
    password: 'danger',
    id_card: 'warning'
  };
  return typeMap[type] || '';
};

// 获取生成规则标签
const getGenerationRuleLabel = (rule: string) => {
  const option = generationRuleOptions.find(opt => opt.value === rule);
  return option?.label || rule;
};

// 监听stepId变化
watch(() => props.stepId, () => {
  fetchTestData();
  generatedData.value = {};
}, { immediate: true });
</script>

<style scoped>
.test-data-editor {
  padding: 0;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.editor-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.boundary-config,
.length-config {
  display: flex;
  align-items: center;
}

.data-value {
  color: #409eff;
  font-weight: 500;
}

.range-value {
  color: #67c23a;
  font-size: 12px;
}

.empty-value {
  color: #909399;
}

.description {
  color: #606266;
  font-size: 12px;
}

.preview-value {
  color: #409eff;
  font-weight: 500;
  font-size: 12px;
}

.preview-card {
  margin-top: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.json-preview {
  background-color: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 300px;
  overflow-y: auto;
}
</style>
