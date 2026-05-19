<template>
  <div class="role-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>角色管理</h2>
          <el-button type="primary" @click="openAddDialog" v-permission="'role:create'">
            <el-icon><Plus /></el-icon>
            新增角色
          </el-button>
        </div>
      </template>

      <div class="search-box">
        <el-input v-model="searchQuery" placeholder="搜索角色名称" clearable @keyup.enter="handleSearch">
          <template #prefix><el-icon><Search /></el-icon></template>
          <template #append><el-button @click="handleSearch"><el-icon><Search /></el-icon></el-button></template>
        </el-input>
      </div>

      <el-table :data="roles" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="角色名称" />
        <el-table-column prop="desc" label="角色描述" />
        <el-table-column label="权限数量" width="120">
          <template #default="scope">{{ scope.row.permissions?.length || 0 }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)" v-permission="'role:update'">编辑</el-button>
            <el-button size="small" @click="assignPermission(scope.row)" v-permission="'role:update'">分配权限</el-button>
            <el-button size="small" type="danger" @click="deleteRole(scope.row)" v-permission="'role:delete'">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next, jumper" :total="pagination.total" @size-change="handleSizeChange" @current-change="handleCurrentChange" />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="100px">
        <el-form-item label="角色名称" prop="name"><el-input v-model="roleForm.name" placeholder="请输入角色名称" /></el-form-item>
        <el-form-item label="角色描述" prop="desc"><el-input v-model="roleForm.desc" placeholder="请输入角色描述" type="textarea" /></el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRole">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="permissionDialogVisible" title="分配权限" width="600px">
      <el-form>
        <el-form-item label="角色"><el-tag>{{ currentRole?.name }}</el-tag></el-form-item>
        <el-form-item label="权限">
          <el-tree v-model="selectedPermissions" :data="permissionTree" show-checkbox node-key="code" default-expand-all :props="{ label: 'name', children: 'children' }" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="permissionDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="savePermissions">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import { useRoleManagement } from './useRoleManagement'

const {
  loading, roles, pagination, searchQuery, dialogVisible, permissionDialogVisible,
  dialogTitle, roleFormRef, roleForm, roleRules, permissionTree,
  selectedPermissions, currentRole,
  handleSearch, handleSizeChange, handleCurrentChange, openAddDialog,
  openEditDialog, saveRole, deleteRole, assignPermission, savePermissions,
} = useRoleManagement()
void roleFormRef
</script>

<style scoped>
.role-management {
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

.search-box {
  margin-bottom: 20px;
  max-width: 400px;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 768px) {
  .role-management {
    padding: 10px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .search-box {
    max-width: 100%;
  }

  .el-table {
    font-size: 12px;
  }

  .el-table th,
  .el-table td {
    padding: 8px 4px;
  }

  .pagination {
    margin-top: 10px;
  }

  :deep(.el-pagination) {
    font-size: 12px;
  }

  :deep(.el-pagination__sizes .el-input__inner) {
    width: 80px;
  }

  .el-dialog {
    width: 90% !important;
  }

  :deep(.el-tree) {
    font-size: 12px;
  }
}
</style>
