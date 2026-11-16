import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getUsers: vi.fn(),
  getRoles: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  getUser: vi.fn(),
  assignRole: vi.fn(),
}))

vi.mock('@/api/user', () => ({
  userApi: {
    getUsers: mocks.getUsers,
    getRoles: mocks.getRoles,
    createUser: mocks.createUser,
    updateUser: mocks.updateUser,
    getUser: mocks.getUser,
    assignRole: mocks.assignRole,
  },
}))

import { useUserManagement } from '../useUserManagement'

type Ctx = ReturnType<typeof useUserManagement>

const host = createComposableHost<Ctx>(() => useUserManagement())
let ctx: Ctx

function makeUser(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    username: 'zhangsan',
    email: 'zhangsan@example.com',
    phone: '13800138000',
    status: true,
    ...overrides,
  }
}

function makeFormRef(valid = true) {
  return {
    validate: vi.fn((cb: (v: boolean) => void) => {
      cb(valid)
      return Promise.resolve(valid)
    }),
    resetFields: vi.fn(),
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.getUsers.mockResolvedValue({
    data: [makeUser()],
    headers: { 'x-total-count': '42' },
  })
  mocks.getRoles.mockResolvedValue({ data: [{ id: 1, name: '管理员' }] })
  mocks.createUser.mockResolvedValue({ data: {} })
  mocks.updateUser.mockResolvedValue({ data: {} })
  mocks.getUser.mockResolvedValue({ data: { id: 1, roles: [{ id: 2 }, { id: 3 }] } })
  mocks.assignRole.mockResolvedValue({ data: {} })
})

describe('useUserManagement — 列表加载', () => {
  it('挂载后按分页拉取用户与角色', async () => {
    await mountHost()

    expect(mocks.getUsers).toHaveBeenCalledWith({ skip: 0, limit: 10 })
    expect(mocks.getRoles).toHaveBeenCalledTimes(1)
    expect(ctx.users.value).toHaveLength(1)
    expect(ctx.roles.value).toHaveLength(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('总数优先取响应头（字符串数字），缺失时使用列表长度', async () => {
    await mountHost()
    expect(Number(ctx.pagination.total)).toBe(42)

    mocks.getUsers.mockResolvedValue({ data: [makeUser(), makeUser({ id: 2 })], headers: {} })
    ctx.pagination.page = 1
    await ctx.loadUsers()
    expect(ctx.pagination.total).toBe(2)
  })

  it('响应为分页结构时取 data.data', async () => {
    mocks.getUsers.mockResolvedValue({ data: { data: [makeUser({ id: 5 })] } })

    await mountHost()

    expect(ctx.users.value[0].id).toBe(5)
  })

  it('用户列表失败时提示错误并复位 loading', async () => {
    mocks.getUsers.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取用户列表失败')
    expect(ctx.loading.value).toBe(false)
  })

  it('角色列表失败时提示错误', async () => {
    mocks.getRoles.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取角色列表失败')
  })
})

describe('useUserManagement — 筛选与翻页', () => {
  it('搜索时回到第一页', async () => {
    await mountHost()
    ctx.pagination.page = 3
    mocks.getUsers.mockClear()

    ctx.handleSearch()
    await flushPromises()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getUsers).toHaveBeenCalledWith({ skip: 0, limit: 10 })
  })

  it('重置筛选清空条件并回到第一页', async () => {
    await mountHost()
    ctx.searchQuery.value = 'zhang'
    ctx.statusFilter.value = 'disabled'
    ctx.pagination.page = 2
    mocks.getUsers.mockClear()

    ctx.resetFilter()
    await flushPromises()

    expect(ctx.searchQuery.value).toBe('')
    expect(ctx.statusFilter.value).toBe('')
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getUsers).toHaveBeenCalledWith({ skip: 0, limit: 10 })
  })

  it('调整每页条数后按新值计算偏移', async () => {
    await mountHost()
    ctx.pagination.page = 3
    mocks.getUsers.mockClear()

    ctx.handleSizeChange(20)
    await flushPromises()

    expect(ctx.pagination.size).toBe(20)
    expect(mocks.getUsers).toHaveBeenCalledWith({ skip: 40, limit: 20 })
  })

  it('切换页码后按偏移拉取', async () => {
    await mountHost()
    mocks.getUsers.mockClear()

    ctx.handleCurrentChange(4)
    await flushPromises()

    expect(ctx.pagination.page).toBe(4)
    expect(mocks.getUsers).toHaveBeenCalledWith({ skip: 30, limit: 10 })
  })
})

describe('useUserManagement — 用户表单', () => {
  it('打开新增弹窗重置表单', async () => {
    await mountHost()
    ctx.userForm.username = 'old'

    ctx.openAddDialog()

    expect(ctx.editMode.value).toBe(false)
    expect(ctx.dialogTitle.value).toBe('新增用户')
    expect(ctx.userForm.username).toBe('')
    expect(ctx.userForm.status).toBe(true)
    expect(ctx.dialogVisible.value).toBe(true)
  })

  it('打开编辑弹窗回填用户信息且不填密码', async () => {
    await mountHost()
    ctx.userForm.password = 'secret'

    ctx.openEditDialog(makeUser({ phone: '13900139000' }) as never)

    expect(ctx.editMode.value).toBe(true)
    expect(ctx.dialogTitle.value).toBe('编辑用户')
    expect(ctx.userForm.phone).toBe('13900139000')
    expect(ctx.userForm.password).toBe('secret')
  })

  it('表单实例未就绪时保存直接返回', async () => {
    await mountHost()

    await ctx.saveUser()

    expect(mocks.createUser).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.userFormRef.value = makeFormRef(false)

    await ctx.saveUser()

    expect(mocks.createUser).not.toHaveBeenCalled()
  })

  it('新增成功后关闭弹窗并刷新列表', async () => {
    await mountHost()
    ctx.userFormRef.value = makeFormRef()
    ctx.userForm.username = 'lisi'
    mocks.getUsers.mockClear()

    await ctx.saveUser()
    await flushPromises()

    expect(mocks.createUser).toHaveBeenCalledWith(ctx.userForm)
    expect(ElMessage.success).toHaveBeenCalledWith('用户创建成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getUsers).toHaveBeenCalledTimes(1)
  })

  it('编辑成功后按当前用户 ID 更新', async () => {
    await mountHost()
    ctx.userFormRef.value = makeFormRef()
    ctx.currentUser.value = makeUser({ id: 8 }) as never
    ctx.openEditDialog(makeUser({ id: 8 }) as never)
    ctx.currentUser.value = makeUser({ id: 8 }) as never

    await ctx.saveUser()
    await flushPromises()

    expect(mocks.updateUser).toHaveBeenCalledWith(8, ctx.userForm)
    expect(ElMessage.success).toHaveBeenCalledWith('用户更新成功')
  })

  it('保存失败时优先提示接口返回信息', async () => {
    mocks.createUser.mockRejectedValue({ response: { data: { message: '用户名已存在' } } })
    await mountHost()
    ctx.userFormRef.value = makeFormRef()

    await ctx.saveUser()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('用户名已存在')
  })

  it('保存失败且无接口信息时使用兜底文案', async () => {
    mocks.createUser.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.userFormRef.value = makeFormRef()

    await ctx.saveUser()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})

describe('useUserManagement — 启用停用与角色分配', () => {
  it('确认后切换用户状态并刷新', async () => {
    await mountHost()
    mocks.getUsers.mockClear()

    await ctx.toggleStatus(makeUser({ status: true }) as never)
    await flushPromises()

    expect(mocks.updateUser).toHaveBeenCalledWith(1, { status: false })
    expect(ElMessage.success).toHaveBeenCalledWith('禁用成功')
    expect(mocks.getUsers).toHaveBeenCalledTimes(1)
  })

  it('取消切换时不调用接口', async () => {
    await mountHost()
    mockCancel()

    await ctx.toggleStatus(makeUser() as never)
    await flushPromises()

    expect(mocks.updateUser).not.toHaveBeenCalled()
  })

  it('切换失败时提示操作失败', async () => {
    mocks.updateUser.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.toggleStatus(makeUser() as never)
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('操作失败')
  })

  it('打开角色分配时拉取用户已有角色与角色列表', async () => {
    await mountHost()
    mocks.getRoles.mockClear()

    await ctx.assignRole(makeUser({ id: 6 }) as never)

    expect(mocks.getUser).toHaveBeenCalledWith(6)
    expect(ctx.selectedRoles.value).toEqual([2, 3])
    expect(mocks.getRoles).toHaveBeenCalledTimes(1)
    expect(ctx.roleDialogVisible.value).toBe(true)
    expect(ctx.currentUser.value?.id).toBe(6)
  })

  it('用户没有角色时选中列表为空', async () => {
    mocks.getUser.mockResolvedValue({ data: { id: 6 } })
    await mountHost()
    ctx.selectedRoles.value = [9]

    await ctx.assignRole(makeUser({ id: 6 }) as never)

    expect(ctx.selectedRoles.value).toEqual([])
  })

  it('获取用户角色失败时提示错误但仍打开弹窗', async () => {
    mocks.getUser.mockRejectedValue(new Error('boom'))
    await mountHost()

    await ctx.assignRole(makeUser() as never)

    expect(ElMessage.error).toHaveBeenCalledWith('获取用户角色失败')
    expect(ctx.roleDialogVisible.value).toBe(true)
  })

  it('保存角色时逐个分配并关闭弹窗', async () => {
    await mountHost()
    ctx.currentUser.value = makeUser({ id: 6 }) as never
    ctx.selectedRoles.value = [2, 3]
    ctx.roleDialogVisible.value = true

    await ctx.saveRoles()

    expect(mocks.assignRole).toHaveBeenCalledTimes(2)
    expect(mocks.assignRole).toHaveBeenNthCalledWith(1, { user_id: 6, role_id: 2 })
    expect(mocks.assignRole).toHaveBeenNthCalledWith(2, { user_id: 6, role_id: 3 })
    expect(ElMessage.success).toHaveBeenCalledWith('角色分配成功')
    expect(ctx.roleDialogVisible.value).toBe(false)
  })

  it('未选择用户时保存角色直接返回', async () => {
    await mountHost()

    await ctx.saveRoles()

    expect(mocks.assignRole).not.toHaveBeenCalled()
  })

  it('分配角色失败时提示错误', async () => {
    mocks.assignRole.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.currentUser.value = makeUser({ id: 6 }) as never
    ctx.selectedRoles.value = [2]

    await ctx.saveRoles()

    expect(ElMessage.error).toHaveBeenCalledWith('角色分配失败')
  })
})
