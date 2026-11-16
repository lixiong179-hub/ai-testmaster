import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getRoles: vi.fn(),
  getPermissions: vi.fn(),
  createRole: vi.fn(),
  updateRole: vi.fn(),
  deleteRole: vi.fn(),
}))

vi.mock('@/api/user', () => ({
  userApi: {
    getRoles: mocks.getRoles,
    getPermissions: mocks.getPermissions,
    createRole: mocks.createRole,
    updateRole: mocks.updateRole,
    deleteRole: mocks.deleteRole,
  },
}))

import { useRoleManagement } from '../useRoleManagement'

type Ctx = ReturnType<typeof useRoleManagement>

const host = createComposableHost<Ctx>(() => useRoleManagement())
let ctx: Ctx

function makeRole(overrides: Record<string, unknown> = {}) {
  return { id: 1, name: '管理员', desc: '系统管理员', permissions: [], ...overrides }
}

function makePerm(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    code: 'case.read',
    name: '查看用例',
    type: 'menu',
    parent_id: null,
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
  mocks.getRoles.mockResolvedValue({
    data: [makeRole()],
    headers: { 'x-total-count': '15' },
  })
  mocks.getPermissions.mockResolvedValue({
    data: [
      makePerm({ id: 1, code: 'case', name: '用例', parent_id: null }),
      makePerm({ id: 2, code: 'case.read', name: '查看', parent_id: 1 }),
      makePerm({ id: 3, code: 'orphan', name: '孤儿节点', parent_id: 99 }),
    ],
  })
  mocks.createRole.mockResolvedValue({ data: {} })
  mocks.updateRole.mockResolvedValue({ data: {} })
  mocks.deleteRole.mockResolvedValue({ data: {} })
})

describe('useRoleManagement — 加载与权限树', () => {
  it('挂载后按分页拉取角色与权限并构建树', async () => {
    await mountHost()

    expect(mocks.getRoles).toHaveBeenCalledWith({ skip: 0, limit: 10, search: '' })
    expect(mocks.getPermissions).toHaveBeenCalledTimes(1)
    expect(ctx.roles.value).toHaveLength(1)
    expect(Number(ctx.pagination.total)).toBe(15)
    expect(ctx.loading.value).toBe(false)
  })

  it('权限树按 parent_id 组装，孤儿节点被忽略', async () => {
    await mountHost()

    expect(ctx.permissionTree.value).toHaveLength(1)
    expect(ctx.permissionTree.value[0].code).toBe('case')
    expect(ctx.permissionTree.value[0].children.map((c) => c.code)).toEqual(['case.read'])
  })

  it('角色总数缺失时回退为列表长度', async () => {
    mocks.getRoles.mockResolvedValue({ data: [makeRole(), makeRole({ id: 2 })], headers: {} })

    await mountHost()

    expect(ctx.pagination.total).toBe(2)
  })

  it('角色列表失败时提示错误并复位 loading', async () => {
    mocks.getRoles.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取角色列表失败')
    expect(ctx.loading.value).toBe(false)
  })

  it('权限列表失败时提示错误且树为空', async () => {
    mocks.getPermissions.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取权限列表失败')
    expect(ctx.permissionTree.value).toEqual([])
  })
})

describe('useRoleManagement — 筛选与翻页', () => {
  it('搜索时回到第一页并带上关键字', async () => {
    await mountHost()
    ctx.pagination.page = 3
    ctx.searchQuery.value = '管理员'
    mocks.getRoles.mockClear()

    ctx.handleSearch()
    await flushPromises()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getRoles).toHaveBeenCalledWith({ skip: 0, limit: 10, search: '管理员' })
  })

  it('调整每页条数后按新值计算偏移', async () => {
    await mountHost()
    ctx.pagination.page = 2
    mocks.getRoles.mockClear()

    ctx.handleSizeChange(50)
    await flushPromises()

    expect(ctx.pagination.size).toBe(50)
    expect(mocks.getRoles).toHaveBeenCalledWith({ skip: 50, limit: 50, search: '' })
  })

  it('切换页码后按偏移拉取', async () => {
    await mountHost()
    mocks.getRoles.mockClear()

    ctx.handleCurrentChange(2)
    await flushPromises()

    expect(ctx.pagination.page).toBe(2)
    expect(mocks.getRoles).toHaveBeenCalledWith({ skip: 10, limit: 10, search: '' })
  })
})

describe('useRoleManagement — 角色表单', () => {
  it('打开新增弹窗重置表单', async () => {
    await mountHost()
    ctx.roleForm.name = '旧角色'

    ctx.openAddDialog()

    expect(ctx.editMode.value).toBe(false)
    expect(ctx.dialogTitle.value).toBe('新增角色')
    expect(ctx.roleForm.name).toBe('')
    expect(ctx.roleForm.permissions).toEqual([])
    expect(ctx.dialogVisible.value).toBe(true)
  })

  it('打开编辑弹窗回填角色并记录当前角色', async () => {
    await mountHost()
    const role = makeRole({ id: 5, permissions: ['case.read'] })

    ctx.openEditDialog(role as never)

    expect(ctx.editMode.value).toBe(true)
    expect(ctx.dialogTitle.value).toBe('编辑角色')
    expect(ctx.roleForm.permissions).toEqual(['case.read'])
    expect(ctx.currentRole.value).toEqual(role)
  })

  it('角色缺少权限时回填空数组', async () => {
    await mountHost()

    ctx.openEditDialog(makeRole({ permissions: undefined }) as never)

    expect(ctx.roleForm.permissions).toEqual([])
  })

  it('表单实例未就绪时保存直接返回', async () => {
    await mountHost()

    await ctx.saveRole()

    expect(mocks.createRole).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.roleFormRef.value = makeFormRef(false)

    await ctx.saveRole()

    expect(mocks.createRole).not.toHaveBeenCalled()
  })

  it('新增成功后关闭弹窗并刷新', async () => {
    await mountHost()
    ctx.roleFormRef.value = makeFormRef()
    ctx.roleForm.name = '测试角色'
    mocks.getRoles.mockClear()

    await ctx.saveRole()
    await flushPromises()

    expect(mocks.createRole).toHaveBeenCalledWith(ctx.roleForm)
    expect(ElMessage.success).toHaveBeenCalledWith('角色创建成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getRoles).toHaveBeenCalledTimes(1)
  })

  it('编辑成功后按角色 ID 更新', async () => {
    await mountHost()
    ctx.roleFormRef.value = makeFormRef()
    ctx.openEditDialog(makeRole({ id: 5 }) as never)

    await ctx.saveRole()
    await flushPromises()

    expect(mocks.updateRole).toHaveBeenCalledWith(5, ctx.roleForm)
    expect(ElMessage.success).toHaveBeenCalledWith('角色更新成功')
  })

  it('保存失败时优先提示接口返回信息', async () => {
    mocks.createRole.mockRejectedValue({ response: { data: { message: '角色名重复' } } })
    await mountHost()
    ctx.roleFormRef.value = makeFormRef()

    await ctx.saveRole()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('角色名重复')
  })

  it('保存失败且无接口信息时使用兜底文案', async () => {
    mocks.createRole.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.roleFormRef.value = makeFormRef()

    await ctx.saveRole()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})

describe('useRoleManagement — 删除与权限分配', () => {
  it('确认后删除角色并刷新', async () => {
    await mountHost()
    mocks.getRoles.mockClear()

    ctx.deleteRole(makeRole({ id: 7 }) as never)
    await flushPromises()

    expect(mocks.deleteRole).toHaveBeenCalledWith(7)
    expect(ElMessage.success).toHaveBeenCalledWith('角色删除成功')
    expect(mocks.getRoles).toHaveBeenCalledTimes(1)
  })

  it('取消删除时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.deleteRole(makeRole() as never)
    await flushPromises()

    expect(mocks.deleteRole).not.toHaveBeenCalled()
  })

  it('删除失败时提示错误', async () => {
    mocks.deleteRole.mockRejectedValue(new Error('boom'))
    await mountHost()

    ctx.deleteRole(makeRole() as never)
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })

  it('打开权限分配时回填已选权限并加载权限树', async () => {
    await mountHost()
    mocks.getPermissions.mockClear()

    await ctx.assignPermission(makeRole({ id: 9, permissions: ['case.read'] }) as never)

    expect(ctx.currentRole.value?.id).toBe(9)
    expect(ctx.selectedPermissions.value).toEqual(['case.read'])
    expect(mocks.getPermissions).toHaveBeenCalledTimes(1)
    expect(ctx.permissionDialogVisible.value).toBe(true)
  })

  it('角色无权限时默认选中为空', async () => {
    await mountHost()

    await ctx.assignPermission(makeRole({ id: 9, permissions: undefined }) as never)

    expect(ctx.selectedPermissions.value).toEqual([])
  })

  it('保存权限成功后关闭弹窗并刷新', async () => {
    await mountHost()
    ctx.currentRole.value = makeRole({ id: 9 }) as never
    ctx.selectedPermissions.value = ['case.read', 'case.write']
    mocks.getRoles.mockClear()

    await ctx.savePermissions()
    await flushPromises()

    expect(mocks.updateRole).toHaveBeenCalledWith(9, {
      permissions: ['case.read', 'case.write'],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('权限分配成功')
    expect(ctx.permissionDialogVisible.value).toBe(false)
    expect(mocks.getRoles).toHaveBeenCalledTimes(1)
  })

  it('未选择角色时保存权限直接返回', async () => {
    await mountHost()

    await ctx.savePermissions()

    expect(mocks.updateRole).not.toHaveBeenCalled()
  })

  it('保存权限失败时提示错误', async () => {
    mocks.updateRole.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.currentRole.value = makeRole({ id: 9 }) as never

    await ctx.savePermissions()

    expect(ElMessage.error).toHaveBeenCalledWith('权限分配失败')
  })
})
