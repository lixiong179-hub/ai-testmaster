import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '@/api/user'
import type { Role, RoleForm, Permission, Pagination } from '@/types/user'

// 权限树节点
interface PermissionTreeNode {
  id: number
  code: string
  name: string
  type: Permission['type']
  children: PermissionTreeNode[]
}

export function useRoleManagement() {
  const loading = ref(false)
  const roles = ref<Role[]>([])
  const pagination = reactive<Pagination>({ page: 1, size: 10, total: 0 })
  const searchQuery = ref('')
  const dialogVisible = ref(false)
  const permissionDialogVisible = ref(false)
  const dialogTitle = ref('新增角色')
  const editMode = ref(false)
  const roleFormRef = ref()
  const roleForm = reactive<RoleForm>({ name: '', desc: '', permissions: [] })
  const roleRules = {
    name: [
      { required: true, message: '请输入角色名称', trigger: 'blur' },
      { min: 1, max: 50, message: '角色名称长度1-50位', trigger: 'blur' },
    ],
    desc: [{ max: 200, message: '角色描述长度不超过200位', trigger: 'blur' }],
  }
  const permissions = ref<Permission[]>([])
  const permissionTree = ref<PermissionTreeNode[]>([])
  const selectedPermissions = ref<string[]>([])
  const currentRole = ref<Role | null>(null)

  const loadRoles = async () => {
    loading.value = true
    try {
      const response = await userApi.getRoles({
        skip: (pagination.page - 1) * pagination.size,
        limit: pagination.size,
        search: searchQuery.value,
      })
      roles.value = response.data
      pagination.total = response.headers['x-total-count'] || roles.value.length
    } catch (error) {
      ElMessage.error('获取角色列表失败')
    } finally {
      loading.value = false
    }
  }

  const loadPermissions = async () => {
    try {
      const response = await userApi.getPermissions()
      permissions.value = response.data
      permissionTree.value = buildPermissionTree(response.data)
    } catch (error) {
      ElMessage.error('获取权限列表失败')
    }
  }

  const buildPermissionTree = (perms: Permission[]): PermissionTreeNode[] => {
    const tree: PermissionTreeNode[] = []
    const map: { [key: number]: PermissionTreeNode } = {}
    perms.forEach((perm) => {
      map[perm.id] = {
        id: perm.id,
        code: perm.code,
        name: perm.name,
        type: perm.type,
        children: [],
      }
    })
    perms.forEach((perm) => {
      if (perm.parent_id === null) tree.push(map[perm.id])
      else if (map[perm.parent_id]) map[perm.parent_id].children.push(map[perm.id])
    })
    return tree
  }

  const handleSearch = () => {
    pagination.page = 1
    loadRoles()
  }
  const handleSizeChange = (size: number) => {
    pagination.size = size
    loadRoles()
  }
  const handleCurrentChange = (page: number) => {
    pagination.page = page
    loadRoles()
  }

  const openAddDialog = () => {
    editMode.value = false
    dialogTitle.value = '新增角色'
    Object.assign(roleForm, { name: '', desc: '', permissions: [] })
    dialogVisible.value = true
  }

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

  const saveRole = async () => {
    if (!roleFormRef.value) return
    await roleFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        try {
          if (editMode.value && currentRole.value) {
            await userApi.updateRole(currentRole.value.id, roleForm)
            ElMessage.success('角色更新成功')
          } else {
            await userApi.createRole(roleForm)
            ElMessage.success('角色创建成功')
          }
          dialogVisible.value = false
          loadRoles()
        } catch (error: unknown) {
          const err = error as { response?: { data?: { message?: string } } }
          ElMessage.error(err.response?.data?.message || '保存失败')
        }
      }
    })
  }

  const deleteRole = (role: Role) => {
    ElMessageBox.confirm(`确定要删除角色 ${role.name} 吗？`, '确认操作', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(async () => {
        try {
          await userApi.deleteRole(role.id)
          ElMessage.success('角色删除成功')
          loadRoles()
        } catch (error) {
          ElMessage.error('删除失败')
        }
      })
      .catch(() => {})
  }

  const assignPermission = async (role: Role) => {
    currentRole.value = role
    selectedPermissions.value = role.permissions || []
    await loadPermissions()
    permissionDialogVisible.value = true
  }

  const savePermissions = async () => {
    if (!currentRole.value) return
    try {
      await userApi.updateRole(currentRole.value.id, { permissions: selectedPermissions.value })
      ElMessage.success('权限分配成功')
      permissionDialogVisible.value = false
      loadRoles()
    } catch (error) {
      ElMessage.error('权限分配失败')
    }
  }

  onMounted(() => {
    loadRoles()
    loadPermissions()
  })

  return {
    loading,
    roles,
    pagination,
    searchQuery,
    dialogVisible,
    permissionDialogVisible,
    dialogTitle,
    editMode,
    roleFormRef,
    roleForm,
    roleRules,
    permissionTree,
    selectedPermissions,
    currentRole,
    handleSearch,
    handleSizeChange,
    handleCurrentChange,
    openAddDialog,
    openEditDialog,
    saveRole,
    deleteRole,
    assignPermission,
    savePermissions,
  }
}
