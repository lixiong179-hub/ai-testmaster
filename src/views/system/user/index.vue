<template>
  <div class="user-management">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>用户管理</h2>
          <el-button type="primary" @click="openAddDialog" v-permission="'user:create'">
            <el-icon><Plus /></el-icon>
            新增用户
          </el-button>
        </div>
      </template>

      <div class="search-filter">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-input
              v-model="searchQuery"
              placeholder="搜索用户名/手机号/邮箱"
              clearable
              @keyup.enter="handleSearch"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
              <template #append>
                <el-button @click="handleSearch"
                  ><el-icon><Search /></el-icon
                ></el-button>
              </template>
            </el-input>
          </el-col>
          <el-col :span="6">
            <el-select v-model="statusFilter" placeholder="状态" clearable>
              <el-option label="启用" value="true" />
              <el-option label="禁用" value="false" />
            </el-select>
          </el-col>
          <el-col :span="10" class="text-right">
            <el-button @click="resetFilter">重置筛选</el-button>
          </el-col>
        </el-row>
      </div>

      <el-table :data="users" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.status ? 'success' : 'danger'">
              {{ scope.row.status ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login_time" label="最后登录时间" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)" v-permission="'user:update'">
              编辑
            </el-button>
            <el-button
              size="small"
              :type="scope.row.status ? 'danger' : 'success'"
              @click="toggleStatus(scope.row)"
              v-permission="'user:update'"
            >
              {{ scope.row.status ? '禁用' : '启用' }}
            </el-button>
            <el-button
              size="small"
              @click="assignRole(scope.row)"
              v-permission="'user:assign_role'"
            >
              分配角色
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pagination.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :ref="setUserFormRef" :model="userForm" :rules="userRules" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="userForm.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="密码" prop="password" v-if="!editMode">
          <el-input
            v-model="userForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="userForm.status" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveUser">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" title="分配角色" width="400px">
      <el-form>
        <el-form-item label="用户">
          <el-tag>{{ currentUser?.username }}</el-tag>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="selectedRoles" multiple placeholder="请选择角色" style="width: 100%">
            <el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRoles">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus, Search } from '@element-plus/icons-vue'
import { useUserManagement } from './useUserManagement'

const {
  loading,
  users,
  pagination,
  searchQuery,
  statusFilter,
  dialogVisible,
  roleDialogVisible,
  dialogTitle,
  editMode,
  userFormRef,
  userForm,
  userRules,
  roles,
  selectedRoles,
  currentUser,
  handleSearch,
  resetFilter,
  handleSizeChange,
  handleCurrentChange,
  openAddDialog,
  openEditDialog,
  saveUser,
  toggleStatus,
  assignRole,
  saveRoles,
} = useUserManagement()

const setUserFormRef = (el: unknown) => {
  userFormRef.value = el
}
</script>

<style scoped lang="scss">
@use './UserManagement.scss';
</style>
