<template>
  <div class="quality-rule-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>质量规则配置</h2>
          <div class="header-actions">
            <el-select
              v-model="selectedProjectId"
              placeholder="请选择项目"
              clearable
              style="width: 240px"
              @change="handleProjectChange"
            >
              <el-option
                v-for="project in projects"
                :key="project.id"
                :label="project.name"
                :value="project.id"
              />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="rules" style="width: 100%" v-loading="loading">
        <el-table-column prop="rule_key" label="规则Key" width="240" show-overflow-tooltip />
        <el-table-column label="默认值" width="160">
          <template #default="scope">
            {{ formatRuleValue(scope.row.default_value) }}
          </template>
        </el-table-column>
        <el-table-column label="当前值" min-width="200">
          <template #default="scope">
            <span :class="{ 'value-modified': !isDefaultValue(scope.row) }">
              {{ formatRuleValue(scope.row.rule_value) }}
            </span>
            <el-tag
              v-if="!isDefaultValue(scope.row)"
              type="warning"
              size="small"
              style="margin-left: 8px"
            >
              已修改
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button
              size="small"
              type="warning"
              :disabled="isDefaultValue(scope.row)"
              @click="resetToDefault(scope.row)"
            >恢复默认</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && rules.length === 0 && selectedProjectId"
        description="暂无质量规则数据"
      />
      <el-empty v-if="!selectedProjectId && !loading" description="请先选择项目" />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" title="编辑规则" width="520px" destroy-on-close>
      <el-form :ref="setFormRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="规则Key">
          <el-input :model-value="formData.rule_key" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            :model-value="currentRule?.description ?? ''"
            disabled
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <!-- 根据规则类型动态生成表单字段 -->
        <el-form-item v-if="currentRule?.value_type === 'boolean'" label="规则值">
          <el-switch
            v-model="formData.rule_value_bool"
            active-text="是"
            inactive-text="否"
          />
        </el-form-item>
        <el-form-item v-else-if="currentRule?.value_type === 'number'" label="规则值">
          <el-input-number
            v-model="formData.rule_value_num"
            :min="0"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-else-if="currentRule?.value_type === 'enum'" label="规则值" prop="rule_value_str">
          <el-select v-model="formData.rule_value_str" placeholder="请选择" style="width: 100%">
            <el-option
              v-for="opt in (currentRule?.enum_options ?? [])"
              :key="opt"
              :label="opt"
              :value="opt"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="规则值" prop="rule_value_str">
          <el-input v-model="formData.rule_value_str" placeholder="请输入规则值" />
        </el-form-item>
        <el-form-item label="默认值">
          <el-tag type="info">{{ formatRuleValue(currentRule?.default_value ?? '') }}</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRule">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { useQualityRule } from './useQualityRule'

const {
  loading,
  rules,
  projects,
  selectedProjectId,
  dialogVisible,
  currentRule,
  formRef,
  formData,
  formRules,
  handleProjectChange,
  formatRuleValue,
  isDefaultValue,
  openEditDialog,
  saveRule,
  resetToDefault,
} = useQualityRule()

const setFormRef = (el: unknown) => {
  formRef.value = el
}
</script>

<style scoped>
.quality-rule-management {
  padding: 20px;
}

.page-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.value-modified {
  color: #e6a23c;
  font-weight: 500;
}

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 768px) {
  .quality-rule-management {
    padding: 10px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .header-actions {
    flex-direction: column;
    width: 100%;
  }

  .header-actions .el-select {
    width: 100% !important;
  }

  .el-table {
    font-size: 12px;
  }

  .el-table th,
  .el-table td {
    padding: 8px 4px;
  }

  :deep(.el-dialog) {
    width: 90% !important;
  }
}
</style>
