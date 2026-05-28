<template>
  <div class="test-capability-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>测试能力管理</h2>
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
            <el-button type="primary" @click="openAddDialog">
              <el-icon><Plus /></el-icon>
              新增能力
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="capabilities" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="key" label="Key" width="180" show-overflow-tooltip />
        <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">
              {{ getStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteCapability(scope.row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <el-empty
        v-if="!loading && capabilities.length === 0 && selectedProjectId"
        description="暂无测试能力数据"
      />
      <el-empty v-if="!selectedProjectId && !loading" description="请先选择项目" />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
      <el-form :ref="setFormRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="Key" prop="key">
          <el-input v-model="formData.key" placeholder="请输入能力Key，如 login-test" />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入能力标题" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入能力描述（选填）"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option
              v-for="opt in STATUS_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveCapability">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { useTestCapability } from './useTestCapability'

const {
  loading,
  capabilities,
  projects,
  selectedProjectId,
  dialogVisible,
  dialogTitle,
  formRef,
  formData,
  formRules,
  STATUS_OPTIONS,
  handleProjectChange,
  getStatusTagType,
  getStatusLabel,
  openAddDialog,
  openEditDialog,
  saveCapability,
  deleteCapability,
} = useTestCapability()

const setFormRef = (el: unknown) => {
  formRef.value = el
}
</script>

<style scoped>
.test-capability-management {
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

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 768px) {
  .test-capability-management {
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
