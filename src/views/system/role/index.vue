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

      <!-- 搜索 -->
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索角色名称"
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
      </div>

      <!-- 角色列表 -->
      <el-table :data="roles" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="角色名称" />
        <el-table-column prop="desc" label="角色描述" />
        <el-table-column label="权限数量" width="120">
          <template #default="scope">
            {{ scope.row.permissions?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)" v-permission="'role:update'">
              编辑
            </el-button>
            <el-button
              size="small"
              @click="assignPermission(scope.row)"
              v-permission="'role:update'"
            >
              分配权限
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="deleteRole(scope.row)"
              v-permission="'role:delete'"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
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

    <!-- 新增/编辑角色对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="roleFormRef" :model="roleForm" :rules="roleRules" label-width="100px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="roleForm.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="角色描述" prop="desc">
          <el-input v-model="roleForm.desc" placeholder="请输入角色描述" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveRole">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 分配权限对话框 -->
    <el-dialog v-model="permissionDialogVisible" title="分配权限" width="600px">
      <el-form>
        <el-form-item label="角色">
          <el-tag>{{ currentRole?.name }}</el-tag>
        </el-form-item>
        <el-form-item label="权限">
          <el-tree
            v-model="selectedPermissions"
            :data="permissionTree"
            show-checkbox
            node-key="code"
            default-expand-all
            :props="{
              label: 'name',
              children: 'children',
            }"
          />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import axios from '@/utils/request'
import type { Role, RoleForm, Permission, Pagination } from '@/types/user'

// 状态管理
const loading = ref(false)
const roles = ref<Role[]>([])
const pagination = reactive<Pagination>({
  page: 1,
  size: 10,
  total: 0,
})

// 搜索
const searchQuery = ref('')

// 对话框
const dialogVisible = ref(false)
const permissionDialogVisible = ref(false)
const dialogTitle = ref('新增角色')
const editMode = ref(false)

// 表单
const roleFormRef = ref()
const roleForm = reactive<RoleForm>({
  name: '',
  desc: '',
  permissions: [],
})

const roleRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 1, max: 50, message: '角色名称长度1-50位', trigger: 'blur' },
  ],
  desc: [{ max: 200, message: '角色描述长度不超过200位', trigger: 'blur' }],
}

// 权限管理
const permissions = ref<Permission[]>([])
const permissionTree = ref<any[]>([])
const selectedPermissions = ref<string[]>([])
const currentRole = ref<Role | null>(null)

// 加载角色列表
const loadRoles = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/v1/user/role', {
      params: {
        skip: (pagination.page - 1) * pagination.size,
        limit: pagination.size,
        search: searchQuery.value,
      },
    })
    roles.value = response.data
    // 假设返回的数据包含total字段
    pagination.total = response.headers['x-total-count'] || roles.value.length
  } catch (error) {
    ElMessage.error('获取角色列表失败')
  } finally {
    loading.value = false
  }
}

// 加载权限列表
const loadPermissions = async () => {
  try {
    const response = await axios.get('/api/v1/user/permission')
    permissions.value = response.data
    permissionTree.value = buildPermissionTree(response.data)
  } catch (error) {
    ElMessage.error('获取权限列表失败')
  }
}

// 构建权限树
const buildPermissionTree = (permissions: Permission[]): any[] => {
  const tree: any[] = []
  const map: { [key: number]: any } = {}

  // 构建节点映射
  permissions.forEach((perm) => {
    map[perm.id] = {
      id: perm.id,
      code: perm.code,
      name: perm.name,
      type: perm.type,
      children: [],
    }
  })

  // 构建树结构
  permissions.forEach((perm) => {
    if (perm.parent_id === null) {
      tree.push(map[perm.id])
    } else if (map[perm.parent_id]) {
      map[perm.parent_id].children.push(map[perm.id])
    }
  })

  return tree
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadRoles()
}

// 分页
const handleSizeChange = (size: number) => {
  pagination.size = size
  loadRoles()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  loadRoles()
}

// 打开新增对话框
const openAddDialog = () => {
  editMode.value = false
  dialogTitle.value = '新增角色'
  Object.assign(roleForm, {
    name: '',
    desc: '',
    permissions: [],
  })
  dialogVisible.value = true
}

// 打开编辑对话框
const openEditDialog = (role: Role) => {
  editMode.value = true
  dialogTitle.value = '编辑角色'
  Object.assign(roleForm, {
    name: role.name,
    desc: role.desc,
    permissions: role.permissions || [],
  })
  currentRole.value = role
  dialogVisible.value = true
}

// 保存角色
const saveRole = async () => {
  if (!roleFormRef.value) return

  await roleFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        if (editMode.value && currentRole.value) {
          // 编辑角色
          await axios.put(`/api/v1/user/role/${currentRole.value.id}`, roleForm)
          ElMessage.success('角色更新成功')
        } else {
          // 新增角色
          await axios.post('/api/v1/user/role', roleForm)
          ElMessage.success('角色创建成功')
        }
        dialogVisible.value = false
        loadRoles()
      } catch (error: any) {
        ElMessage.error(error.response?.data?.message || '保存失败')
      }
    }
  })
}

// 删除角色
const deleteRole = (role: Role) => {
  ElMessageBox.confirm(`确定要删除角色 ${role.name} 吗？`, '确认操作', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        await axios.delete(`/api/v1/user/role/${role.id}`)
        ElMessage.success('角色删除成功')
        loadRoles()
      } catch (error) {
        ElMessage.error('删除失败')
      }
    })
    .catch(() => {
      // 取消操作
    })
}

// 分配权限
const assignPermission = async (role: Role) => {
  currentRole.value = role
  selectedPermissions.value = role.permissions || []

  // 加载权限列表
  await loadPermissions()
  permissionDialogVisible.value = true
}

// 保存权限分配
const savePermissions = async () => {
  if (!currentRole.value) return

  try {
    await axios.put(`/api/v1/user/role/${currentRole.value.id}`, {
      permissions: selectedPermissions.value,
    })
    ElMessage.success('权限分配成功')
    permissionDialogVisible.value = false
    loadRoles()
  } catch (error) {
    ElMessage.error('权限分配失败')
  }
}

// 初始化
onMounted(() => {
  loadRoles()
  loadPermissions()
})
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

/* 移动端适配 */
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
