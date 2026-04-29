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
      
      <!-- 搜索和筛选 -->
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
                <el-button @click="handleSearch"><el-icon><Search /></el-icon></el-button>
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
      
      <!-- 用户列表 -->
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
            <el-button size="small" @click="assignRole(scope.row)" v-permission="'user:assign_role'">
              分配角色
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
    
    <!-- 新增/编辑用户对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
    >
      <el-form
        ref="userFormRef"
        :model="userForm"
        :rules="userRules"
        label-width="100px"
      >
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
          <el-input v-model="userForm.password" type="password" placeholder="请输入密码" show-password />
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
    
    <!-- 分配角色对话框 -->
    <el-dialog
      v-model="roleDialogVisible"
      title="分配角色"
      width="400px"
    >
      <el-form>
        <el-form-item label="用户">
          <el-tag>{{ currentUser?.username }}</el-tag>
        </el-form-item>
        <el-form-item label="角色">
          <el-select
            v-model="selectedRoles"
            multiple
            placeholder="请选择角色"
            style="width: 100%"
          >
            <el-option
              v-for="role in roles"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import axios from '@/utils/request'
import type { User, UserForm, Pagination } from '@/types/user'

// 状态管理
const loading = ref(false)
const users = ref<User[]>([])
const pagination = reactive<Pagination>({
  page: 1,
  size: 10,
  total: 0
})

// 搜索和筛选
const searchQuery = ref('')
const statusFilter = ref('')

// 对话框
const dialogVisible = ref(false)
const roleDialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const editMode = ref(false)

// 表单
const userFormRef = ref()
const userForm = reactive<UserForm>({
  username: '',
  email: '',
  phone: '',
  password: '',
  status: true
})

const userRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度3-50位', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' }
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ]
}

// 角色管理
const roles = ref<any[]>([])
const selectedRoles = ref<number[]>([])
const currentUser = ref<User | null>(null)

// 加载用户列表
const loadUsers = async () => {
  loading.value = true
  try {
    const response = await axios.get('/api/v1/user', {
      params: {
        skip: (pagination.page - 1) * pagination.size,
        limit: pagination.size
      }
    })
    // 兼容不同格式的响应
    users.value = Array.isArray(response.data) ? response.data : (response.data?.data || [])
    // 假设返回的数据包含total字段
    pagination.total = response.headers['x-total-count'] || users.value.length
  } catch (error) {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

// 加载角色列表
const loadRoles = async () => {
  try {
    const response = await axios.get('/api/v1/user/role')
    roles.value = response.data
  } catch (error) {
    ElMessage.error('获取角色列表失败')
  }
}

// 搜索
const handleSearch = () => {
  pagination.page = 1
  loadUsers()
}

// 重置筛选
const resetFilter = () => {
  searchQuery.value = ''
  statusFilter.value = ''
  pagination.page = 1
  loadUsers()
}

// 分页
const handleSizeChange = (size: number) => {
  pagination.size = size
  loadUsers()
}

const handleCurrentChange = (page: number) => {
  pagination.page = page
  loadUsers()
}

// 打开新增对话框
const openAddDialog = () => {
  editMode.value = false
  dialogTitle.value = '新增用户'
  Object.assign(userForm, {
    username: '',
    email: '',
    phone: '',
    password: '',
    status: true
  })
  dialogVisible.value = true
}

// 打开编辑对话框
const openEditDialog = (user: User) => {
  editMode.value = true
  dialogTitle.value = '编辑用户'
  Object.assign(userForm, {
    username: user.username,
    email: user.email,
    phone: user.phone,
    status: user.status
  })
  dialogVisible.value = true
}

// 保存用户
const saveUser = async () => {
  if (!userFormRef.value) return
  
  await userFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      try {
        if (editMode.value) {
          // 编辑用户
          await axios.put(`/api/v1/user/${currentUser.value?.id}`, userForm)
          ElMessage.success('用户更新成功')
        } else {
          // 新增用户
          await axios.post('/api/v1/user', userForm)
          ElMessage.success('用户创建成功')
        }
        dialogVisible.value = false
        loadUsers()
      } catch (error: any) {
        ElMessage.error(error.response?.data?.message || '保存失败')
      }
    }
  })
}

// 切换用户状态
const toggleStatus = async (user: User) => {
  ElMessageBox.confirm(
    `确定要${user.status ? '禁用' : '启用'}该用户吗？`,
    '确认操作',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await axios.put(`/api/v1/user/${user.id}`, {
        status: !user.status
      })
      ElMessage.success(`${user.status ? '禁用' : '启用'}成功`)
      loadUsers()
    } catch (error) {
      ElMessage.error('操作失败')
    }
  }).catch(() => {
    // 取消操作
  })
}

// 分配角色
const assignRole = async (user: User) => {
  currentUser.value = user
  selectedRoles.value = []
  
  // 加载用户当前角色
  try {
    const response = await axios.get(`/api/v1/user/${user.id}`)
    if (response.data.roles) {
      selectedRoles.value = response.data.roles.map((role: any) => role.id)
    }
  } catch (error) {
    ElMessage.error('获取用户角色失败')
  }
  
  // 加载角色列表
  await loadRoles()
  roleDialogVisible.value = true
}

// 保存角色分配
const saveRoles = async () => {
  if (!currentUser.value) return
  
  try {
    // 先清除所有角色
    // 实际项目中应该提供批量操作接口
    for (const roleId of selectedRoles.value) {
      await axios.post('/api/v1/user/role/assign', {
        user_id: currentUser.value?.id,
        role_id: roleId
      })
    }
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
  } catch (error) {
    ElMessage.error('角色分配失败')
  }
}

// 初始化
onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.user-management {
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

.search-filter {
  margin-bottom: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
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
  .user-management {
    padding: 10px;
  }
  
  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .search-filter {
    padding: 10px;
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
}
</style>