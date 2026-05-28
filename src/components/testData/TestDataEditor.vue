<template>
  <div class="test-data-editor">
    <div class="editor-header">
      <h3>测试数据管理</h3>
      <div class="header-actions">
        <el-button
          type="primary"
          size="small"
          @click="handleAutoGenerate"
          :loading="autoGenerating"
        >
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

    <el-table
      class="test-data-table"
      :data="testDataList"
      style="width: 100%"
      border
      v-loading="loading"
    >
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column label="字段名称" min-width="150">
        <template #default="{ row }">
          <el-input
            v-if="row.isEditing"
            v-model="row.field_name"
            placeholder="字段名称"
            size="small"
          />
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
          <el-select
            v-if="row.isEditing"
            v-model="row.generation_rule"
            size="small"
            style="width: 100%"
          >
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
              <el-input-number
                v-model="row.min_value"
                placeholder="最小值"
                size="small"
                :controls="false"
                style="width: 80px"
              />
              <span style="margin: 0 5px">-</span>
              <el-input-number
                v-model="row.max_value"
                placeholder="最大值"
                size="small"
                :controls="false"
                style="width: 80px"
              />
            </div>
            <div v-else class="length-config">
              <el-input-number
                v-model="row.min_length"
                placeholder="最小长度"
                size="small"
                :controls="false"
                style="width: 80px"
              />
              <span style="margin: 0 5px">-</span>
              <el-input-number
                v-model="row.max_length"
                placeholder="最大长度"
                size="small"
                :controls="false"
                style="width: 80px"
              />
            </div>
          </template>
          <template v-else>
            <span v-if="row.data_value" class="data-value">{{ row.data_value }}</span>
            <span v-else-if="row.min_value !== null && row.max_value !== null" class="range-value">
              {{ row.min_value }} - {{ row.max_value }}
            </span>
            <span
              v-else-if="row.min_length !== null && row.max_length !== null"
              class="range-value"
            >
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
          <el-input
            v-if="row.isEditing"
            v-model="row.description"
            placeholder="描述"
            size="small"
          />
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
            <el-button type="primary" size="small" @click="handleSave(row)"> 保存 </el-button>
            <el-button size="small" @click="handleCancel(row, $index)"> 取消 </el-button>
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

    <el-empty v-if="testDataList.length === 0 && !loading" description="暂无测试数据" />

    <el-card
      v-if="Object.keys(generatedData).length > 0"
      class="preview-card"
      style="margin-top: 20px"
    >
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
import { Plus, Edit, Delete, Refresh, MagicStick, CopyDocument } from '@element-plus/icons-vue'
import { dataTypeOptions, generationRuleOptions, type TestData } from '@/api/testData'
import { useTestDataEditor } from './useTestDataEditor'

const props = defineProps<{
  stepId: number
  stepAction?: string
}>()

const emit = defineEmits<{
  (e: 'update', data: TestData[]): void
}>()

const {
  loading,
  generating,
  autoGenerating,
  testDataList,
  generatedData,
  handleAdd,
  handleEdit,
  handleSave,
  handleCancel,
  handleDelete,
  handleGenerateAll,
  handleAutoGenerate,
  handleCopy,
  getDataTypeLabel,
  getDataTypeTagType,
  getGenerationRuleLabel,
} = useTestDataEditor(props, emit)
</script>

<style scoped lang="scss">
@use './TestDataEditor.scss';
</style>
