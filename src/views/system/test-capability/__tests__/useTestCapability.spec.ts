import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  getList: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  ProjectAPI: { getProjects: mocks.getProjects },
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/testCapability', () => ({
  testCapabilityApi: {
    getList: mocks.getList,
    create: mocks.create,
    update: mocks.update,
    delete: mocks.remove,
  },
}))

import { useTestCapability } from '../useTestCapability'

type Ctx = ReturnType<typeof useTestCapability>

const host = createComposableHost<Ctx>(() => useTestCapability())
let ctx: Ctx

function makeCapability(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    project_id: 9,
    key: 'ui.auto',
    title: 'UI 自动化',
    description: '描述',
    status: 'active',
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
  mocks.getProjects.mockResolvedValue({ data: { items: [{ id: 9, name: '项目A' }] } })
  mocks.getList.mockResolvedValue({ data: [makeCapability()] })
  mocks.create.mockResolvedValue({ data: {} })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.remove.mockResolvedValue({ data: {} })
})

describe('useTestCapability — 初始化加载', () => {
  it('挂载后拉取项目、自动选中首个项目并加载能力', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.selectedProjectId.value).toBe(9)
    expect(mocks.getList).toHaveBeenCalledWith({ project_id: 9 })
    expect(ctx.capabilities.value).toHaveLength(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('没有项目时不选中也不加载能力', async () => {
    mocks.getProjects.mockResolvedValue({ data: { items: [] } })

    await mountHost()

    expect(ctx.selectedProjectId.value).toBeNull()
    expect(mocks.getList).not.toHaveBeenCalled()
  })

  it('项目列表失败时提示错误', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目接口异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('能力接口返回非数组时置为空数组', async () => {
    mocks.getList.mockResolvedValue({ data: null })

    await mountHost()

    expect(ctx.capabilities.value).toEqual([])
  })

  it('能力列表失败时提示错误并复位 loading', async () => {
    mocks.getList.mockRejectedValue(new Error('能力接口异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取测试能力列表失败')
    expect(ctx.loading.value).toBe(false)
  })

  it('切换项目后重新加载能力', async () => {
    await mountHost()
    mocks.getList.mockClear()
    ctx.selectedProjectId.value = 10

    ctx.handleProjectChange()
    await flushPromises()

    expect(mocks.getList).toHaveBeenCalledWith({ project_id: 10 })
  })

  it('未选项目时加载能力会清空列表且不请求', async () => {
    await mountHost()
    ctx.selectedProjectId.value = null
    mocks.getList.mockClear()

    ctx.handleProjectChange()
    await flushPromises()

    expect(ctx.capabilities.value).toEqual([])
    expect(mocks.getList).not.toHaveBeenCalled()
  })
})

describe('useTestCapability — 状态展示', () => {
  it.each([
    ['active', 'success', '活跃'],
    ['inactive', 'info', '停用'],
    ['deprecated', 'warning', '废弃'],
  ])('状态 %s 映射为 %s / %s', async (status, tagType, label) => {
    await mountHost()

    expect(ctx.getStatusTagType(status)).toBe(tagType)
    expect(ctx.getStatusLabel(status)).toBe(label)
  })

  it('未知状态回退 info 并原样展示', async () => {
    await mountHost()

    expect(ctx.getStatusTagType('unknown')).toBe('info')
    expect(ctx.getStatusLabel('unknown')).toBe('unknown')
  })

  it('状态选项常量齐全', async () => {
    await mountHost()

    expect(ctx.STATUS_OPTIONS.map((o) => o.value)).toEqual(['active', 'inactive', 'deprecated'])
  })
})

describe('useTestCapability — 对话框', () => {
  it('未选项目时打开新增弹窗会被拦截', async () => {
    mocks.getProjects.mockResolvedValue({ data: { items: [] } })
    await mountHost()

    ctx.openAddDialog()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(ctx.dialogVisible.value).toBe(false)
  })

  it('打开新增弹窗会重置表单', async () => {
    await mountHost()
    ctx.formData.key = 'old'
    ctx.formData.title = '旧标题'

    ctx.openAddDialog()

    expect(ctx.editMode.value).toBe(false)
    expect(ctx.dialogTitle.value).toBe('新增测试能力')
    expect(ctx.formData.key).toBe('')
    expect(ctx.formData.status).toBe('active')
    expect(ctx.dialogVisible.value).toBe(true)
  })

  it('打开编辑弹窗回填字段，description 为空时给空串', async () => {
    await mountHost()

    ctx.openEditDialog(makeCapability({ description: null }) as never)

    expect(ctx.editMode.value).toBe(true)
    expect(ctx.dialogTitle.value).toBe('编辑测试能力')
    expect(ctx.formData.description).toBe('')
    expect(ctx.formData.title).toBe('UI 自动化')
    expect(ctx.dialogVisible.value).toBe(true)
  })
})

describe('useTestCapability — 保存', () => {
  it('表单实例未就绪时直接返回', async () => {
    await mountHost()

    await ctx.saveCapability()

    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef(false)

    await ctx.saveCapability()

    expect(mocks.create).not.toHaveBeenCalled()
  })

  it('新增时提交项目ID并在成功后刷新', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()
    ctx.formData.key = 'api.auto'
    ctx.formData.title = '接口自动化'
    mocks.getList.mockClear()

    await ctx.saveCapability()
    await flushPromises()

    expect(mocks.create).toHaveBeenCalledWith({
      project_id: 9,
      key: 'api.auto',
      title: '接口自动化',
      description: undefined,
      status: 'active',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('测试能力创建成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('编辑时按 ID 提交更新', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openEditDialog(makeCapability({ id: 7 }) as never)
    ctx.formData.description = '已更新'

    await ctx.saveCapability()
    await flushPromises()

    expect(mocks.update).toHaveBeenCalledWith(7, {
      key: 'ui.auto',
      title: 'UI 自动化',
      description: '已更新',
      status: 'active',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('测试能力更新成功')
  })

  it('保存失败时提示 Error 信息', async () => {
    mocks.create.mockRejectedValue(new Error('Key 重复'))
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()

    await ctx.saveCapability()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('Key 重复')
  })

  it('保存失败且非 Error 时使用兜底文案', async () => {
    mocks.create.mockRejectedValue(undefined)
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()

    await ctx.saveCapability()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})

describe('useTestCapability — 删除', () => {
  it('确认后删除并刷新', async () => {
    await mountHost()
    mocks.getList.mockClear()

    ctx.deleteCapability(makeCapability({ id: 3 }) as never)
    await flushPromises()

    expect(mocks.remove).toHaveBeenCalledWith(3)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('取消删除时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.deleteCapability(makeCapability() as never)
    await flushPromises()

    expect(mocks.remove).not.toHaveBeenCalled()
  })

  it('删除失败时提示错误', async () => {
    mocks.remove.mockRejectedValue(new Error('删除失败'))
    await mountHost()

    ctx.deleteCapability(makeCapability() as never)
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})
