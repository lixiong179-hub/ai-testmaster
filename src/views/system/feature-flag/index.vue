<template>
  <div class="feature-flag-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>FeatureFlag 管理</h2>
          <el-button type="primary" @click="openAddDialog">
            <el-icon><Plus /></el-icon>
            新增 Flag
          </el-button>
        </div>
      </template>

      <el-table :data="flags" style="width: 100%" v-loading="loading">
        <el-table-column prop="key" label="Key" width="200" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-switch
              v-model="scope.row.enabled"
              @change="handleToggle(scope.row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="灰度比例" width="200">
          <template #default="scope">
            <el-slider
              :model-value="scope.row.rollout_percentage"
              :min="0"
              :max="100"
              :format-tooltip="(val: number) => val + '%'"
              disabled
              style="width: 140px"
            />
          </template>
        </el-table-column>
        <el-table-column label="目标类型" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.target_type === 'all' ? 'info' : 'warning'" size="small">
              {{ scope.row.target_type === 'all' ? '全部项目' : '指定项目' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="目标项目" min-width="180" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.target_type === 'all' ? '全部' : getProjectNames(scope.row.target_project_ids) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteFlag(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && flags.length === 0"
        description="暂无 FeatureFlag 数据"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px" destroy-on-close>
      <el-form :ref="setFormRef" :model="formData" :rules="formRules" label-width="110px">
        <el-form-item label="Key" prop="key">
          <el-input
            v-model="formData.key"
            placeholder="请输入Flag Key，如 new-ui"
            :disabled="editMode"
          />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入Flag名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="2"
            placeholder="请输入描述（选填）"
          />
        </el-form-item>
        <el-form-item label="启用开关">
          <el-switch v-model="formData.enabled" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="灰度比例">
          <el-slider
            v-model="formData.rollout_percentage"
            :min="0"
            :max="100"
            :format-tooltip="(val: number) => val + '%'"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="目标类型" prop="target_type">
          <el-radio-group v-model="formData.target_type">
            <el-radio
              v-for="opt in TARGET_TYPE_OPTIONS"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="formData.target_type === 'specific'" label="目标项目">
          <el-select
            v-model="formData.target_project_ids"
            multiple
            placeholder="请选择目标项目"
            style="width: 100%"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveFlag">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { useFeatureFlag } from './useFeatureFlag'

const {
  loading,
  flags,
  projects,
  dialogVisible,
  dialogTitle,
  editMode,
  formRef,
  formData,
  formRules,
  TARGET_TYPE_OPTIONS,
  handleToggle,
  openAddDialog,
  openEditDialog,
  saveFlag,
  deleteFlag,
  getProjectNames,
} = useFeatureFlag()

const setFormRef = (el: unknown) => {
  formRef.value = el
}
</script>

<style scoped>
.feature-flag-management {
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

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 768px) {
  .feature-flag-management {
    padding: 10px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
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
