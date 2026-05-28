import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '@/api/user'
import type { User, UserForm, Pagination } from '@/types/user'

export function useUserManagement() {
  const loading = ref(false)
  const users = ref<User[]>([])
  const pagination = reactive<Pagination>({ page: 1, size: 10, total: 0 })

  const searchQuery = ref('')
  const statusFilter = ref('')

  const dialogVisible = ref(false)
  const roleDialogVisible = ref(false)
  const dialogTitle = ref('新增用户')
  const editMode = ref(false)

  const userFormRef = ref()
  const userForm = reactive<UserForm>({
    username: '',
    email: '',
    phone: '',
    password: '',
    status: true,
  })

  const userRules = {
    username: [
      { required: true, message: '请输入用户名', trigger: 'blur' },
      { min: 3, max: 50, message: '用户名长度3-50位', trigger: 'blur' },
    ],
    email: [
      { required: true, message: '请输入邮箱', trigger: 'blur' },
      { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
    ],
    phone: [
      { required: true, message: '请输入手机号', trigger: 'blur' },
      { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
    ],
    password: [
      { required: true, message: '请输入密码', trigger: 'blur' },
      { min: 6, message: '密码长度至少6位', trigger: 'blur' },
    ],
  }

  const roles = ref<any[]>([])
  const selectedRoles = ref<number[]>([])
  const currentUser = ref<User | null>(null)

  const loadUsers = async () => {
    loading.value = true
    try {
      const response = await userApi.getUsers({
        skip: (pagination.page - 1) * pagination.size,
        limit: pagination.size,
      })
      users.value = Array.isArray(response.data) ? response.data : response.data?.data || []
      pagination.total = response.headers['x-total-count'] || users.value.length
    } catch (error) {
      ElMessage.error('获取用户列表失败')
    } finally {
      loading.value = false
    }
  }

  const loadRoles = async () => {
    try {
      const response = await userApi.getRoles()
      roles.value = response.data
    } catch (error) {
      ElMessage.error('获取角色列表失败')
    }
  }

  const handleSearch = () => {
    pagination.page = 1
    loadUsers()
  }
  const resetFilter = () => {
    searchQuery.value = ''
    statusFilter.value = ''
    pagination.page = 1
    loadUsers()
  }
  const handleSizeChange = (size: number) => {
    pagination.size = size
    loadUsers()
  }
  const handleCurrentChange = (page: number) => {
    pagination.page = page
    loadUsers()
  }

  const openAddDialog = () => {
    editMode.value = false
    dialogTitle.value = '新增用户'
    Object.assign(userForm, { username: '', email: '', phone: '', password: '', status: true })
    dialogVisible.value = true
  }

  const openEditDialog = (user: User) => {
    editMode.value = true
    dialogTitle.value = '编辑用户'
    Object.assign(userForm, {
      username: user.username,
      email: user.email,
      phone: user.phone,
      status: user.status,
    })
    dialogVisible.value = true
  }

  const saveUser = async () => {
    if (!userFormRef.value) return
    await userFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        try {
          if (editMode.value) {
            await userApi.updateUser(currentUser.value?.id as number, userForm)
            ElMessage.success('用户更新成功')
          } else {
            await userApi.createUser(userForm)
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

  const toggleStatus = async (user: User) => {
    ElMessageBox.confirm(`确定要${user.status ? '禁用' : '启用'}该用户吗？`, '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(async () => {
        try {
          await userApi.updateUser(user.id, { status: !user.status })
          ElMessage.success(`${user.status ? '禁用' : '启用'}成功`)
          loadUsers()
        } catch (error) {
          ElMessage.error('操作失败')
        }
      })
      .catch(() => {})
  }

  const assignRole = async (user: User) => {
    currentUser.value = user
    selectedRoles.value = []
    try {
      const response = await userApi.getUser(user.id)
      if (response.data.roles) {
        selectedRoles.value = response.data.roles.map((role: any) => role.id)
      }
    } catch (error) {
      ElMessage.error('获取用户角色失败')
    }
    await loadRoles()
    roleDialogVisible.value = true
  }

  const saveRoles = async () => {
    if (!currentUser.value) return
    try {
      for (const roleId of selectedRoles.value) {
        await userApi.assignRole({ user_id: currentUser.value?.id as number, role_id: roleId })
      }
      ElMessage.success('角色分配成功')
      roleDialogVisible.value = false
    } catch (error) {
      ElMessage.error('角色分配失败')
    }
  }

  onMounted(() => {
    loadUsers()
    loadRoles()
  })

  return {
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
    loadUsers,
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
  }
}
