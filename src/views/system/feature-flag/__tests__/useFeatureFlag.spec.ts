import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  getFeatureFlags: vi.fn(),
  createFeatureFlag: vi.fn(),
  updateFeatureFlag: vi.fn(),
  deleteFeatureFlag: vi.fn(),
  toggleFeatureFlag: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  ProjectAPI: { getProjects: mocks.getProjects },
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/featureFlag', () => ({
  featureFlagApi: {
    getFeatureFlags: mocks.getFeatureFlags,
    createFeatureFlag: mocks.createFeatureFlag,
    updateFeatureFlag: mocks.updateFeatureFlag,
    deleteFeatureFlag: mocks.deleteFeatureFlag,
    toggleFeatureFlag: mocks.toggleFeatureFlag,
  },
}))

import { useFeatureFlag } from '../useFeatureFlag'

type Ctx = ReturnType<typeof useFeatureFlag>
type Flag = Ctx['flags']['value'][number]

const host = createComposableHost<Ctx>(() => useFeatureFlag())
let ctx: Ctx

function makeFlag(overrides: Partial<Flag> = {}): Flag {
  return {
    key: 'new-ui',
    name: '新版界面',
    description: '描述',
    enabled: false,
    rollout_percentage: 30,
    target_type: 'all',
    target_project_ids: [],
    ...overrides,
  } as Flag
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
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 9, name: '项目A' },
        { id: 10, name: '项目B' },
      ],
    },
  })
  mocks.getFeatureFlags.mockResolvedValue({ data: [makeFlag()] })
  mocks.createFeatureFlag.mockResolvedValue({ data: {} })
  mocks.updateFeatureFlag.mockResolvedValue({ data: {} })
  mocks.deleteFeatureFlag.mockResolvedValue({ data: {} })
  mocks.toggleFeatureFlag.mockResolvedValue({ data: {} })
})

describe('useFeatureFlag — 初始化加载', () => {
  it('挂载后同时加载项目与 FeatureFlag 列表', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(mocks.getFeatureFlags).toHaveBeenCalledTimes(1)
    expect(ctx.projects.value).toHaveLength(2)
    expect(ctx.flags.value).toHaveLength(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('项目加载失败时提示 Error 信息', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('项目服务异常')
  })

  it('项目加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getProjects.mockRejectedValue(undefined)

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('列表接口返回非数组时置为空数组', async () => {
    mocks.getFeatureFlags.mockResolvedValue({ data: null })

    await mountHost()

    expect(ctx.flags.value).toEqual([])
  })

  it('列表加载失败时提示错误并复位 loading', async () => {
    mocks.getFeatureFlags.mockRejectedValue(new Error('列表异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('列表异常')
    expect(ctx.loading.value).toBe(false)
  })

  it('列表加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getFeatureFlags.mockRejectedValue('boom')

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取FeatureFlag列表失败')
  })
})

describe('useFeatureFlag — 启停开关', () => {
  it('启用与禁用分别给出对应提示', async () => {
    await mountHost()

    await ctx.handleToggle(makeFlag({ enabled: true }))
    expect(mocks.toggleFeatureFlag).toHaveBeenCalledWith('new-ui', true)
    expect(ElMessage.success).toHaveBeenCalledWith('已启用')

    await ctx.handleToggle(makeFlag({ enabled: false }))
    expect(ElMessage.success).toHaveBeenCalledWith('已禁用')
  })

  it('切换失败时回滚开关状态并提示错误', async () => {
    mocks.toggleFeatureFlag.mockRejectedValue(new Error('权限不足'))
    await mountHost()
    const row = makeFlag({ enabled: true })

    await ctx.handleToggle(row)

    expect(row.enabled).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('权限不足')
  })

  it('切换失败且非 Error 时使用兜底文案', async () => {
    mocks.toggleFeatureFlag.mockRejectedValue(undefined)
    await mountHost()
    const row = makeFlag({ enabled: true })

    await ctx.handleToggle(row)

    expect(ElMessage.error).toHaveBeenCalledWith('切换状态失败')
  })
})

describe('useFeatureFlag — 对话框与表单', () => {
  it('打开新增弹窗时重置表单与标题', async () => {
    await mountHost()
    ctx.formData.key = 'old'
    ctx.formData.target_project_ids = [1]

    ctx.openAddDialog()

    expect(ctx.editMode.value).toBe(false)
    expect(ctx.dialogTitle.value).toBe('新增 FeatureFlag')
    expect(ctx.formData.key).toBe('')
    expect(ctx.formData.target_project_ids).toEqual([])
    expect(ctx.formData.target_type).toBe('all')
    expect(ctx.dialogVisible.value).toBe(true)
  })

  it('打开编辑弹窗回填字段并复制项目 ID 数组', async () => {
    await mountHost()
    const row = makeFlag({
      description: null as never,
      target_type: 'specific',
      target_project_ids: [9, 10],
    })

    ctx.openEditDialog(row)

    expect(ctx.editMode.value).toBe(true)
    expect(ctx.dialogTitle.value).toBe('编辑 FeatureFlag')
    expect(ctx.formData.description).toBe('')
    expect(ctx.formData.target_project_ids).toEqual([9, 10])
    expect(ctx.formData.target_project_ids).not.toBe(row.target_project_ids)
  })

  it('目标类型选项常量齐全', async () => {
    await mountHost()

    expect(ctx.TARGET_TYPE_OPTIONS.map((o) => o.value)).toEqual(['all', 'specific'])
  })
})

describe('useFeatureFlag — 保存', () => {
  it('表单实例未就绪时直接返回', async () => {
    await mountHost()

    await ctx.saveFlag()

    expect(mocks.createFeatureFlag).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef(false)

    await ctx.saveFlag()

    expect(mocks.createFeatureFlag).not.toHaveBeenCalled()
  })

  it('新增时 target_type=all 会清空目标项目', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()
    ctx.formData.key = 'flag-x'
    ctx.formData.name = '开关 X'
    ctx.formData.target_type = 'all'
    ctx.formData.target_project_ids = [9]
    mocks.getFeatureFlags.mockClear()

    await ctx.saveFlag()
    await flushPromises()

    expect(mocks.createFeatureFlag).toHaveBeenCalledWith({
      key: 'flag-x',
      name: '开关 X',
      description: undefined,
      enabled: false,
      rollout_percentage: 0,
      target_type: 'all',
      target_project_ids: [],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('FeatureFlag 创建成功')
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.getFeatureFlags).toHaveBeenCalledTimes(1)
  })

  it('编辑时按 key 提交并保留指定项目', async () => {
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openEditDialog(makeFlag({ target_type: 'specific', target_project_ids: [9, 10] }))
    ctx.formData.description = '已更新'

    await ctx.saveFlag()
    await flushPromises()

    expect(mocks.updateFeatureFlag).toHaveBeenCalledWith('new-ui', {
      name: '新版界面',
      description: '已更新',
      enabled: false,
      rollout_percentage: 30,
      target_type: 'specific',
      target_project_ids: [9, 10],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('FeatureFlag 更新成功')
  })

  it('保存失败时提示 Error 信息', async () => {
    mocks.createFeatureFlag.mockRejectedValue(new Error('Key 已存在'))
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()

    await ctx.saveFlag()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('Key 已存在')
  })

  it('保存失败且非 Error 时使用兜底文案', async () => {
    mocks.createFeatureFlag.mockRejectedValue(undefined)
    await mountHost()
    ctx.formRef.value = makeFormRef()
    ctx.openAddDialog()

    await ctx.saveFlag()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('保存失败')
  })
})

describe('useFeatureFlag — 删除与展示辅助', () => {
  it('确认后删除并刷新', async () => {
    await mountHost()
    mocks.getFeatureFlags.mockClear()

    ctx.deleteFlag(makeFlag())
    await flushPromises()

    expect(mocks.deleteFeatureFlag).toHaveBeenCalledWith('new-ui')
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getFeatureFlags).toHaveBeenCalledTimes(1)
  })

  it('取消删除时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.deleteFlag(makeFlag())
    await flushPromises()

    expect(mocks.deleteFeatureFlag).not.toHaveBeenCalled()
  })

  it('删除失败时提示错误', async () => {
    mocks.deleteFeatureFlag.mockRejectedValue(new Error('删除被拒绝'))
    await mountHost()

    ctx.deleteFlag(makeFlag())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('删除被拒绝')
  })

  it('getProjectNames 空数组与无匹配时展示占位符', async () => {
    await mountHost()

    expect(ctx.getProjectNames([])).toBe('-')
    expect(ctx.getProjectNames([404])).toBe('-')
  })

  it('getProjectNames 按顿号拼接匹配到的项目名', async () => {
    await mountHost()

    expect(ctx.getProjectNames([9, 10])).toBe('项目A、项目B')
    expect(ctx.getProjectNames([9, 404])).toBe('项目A')
  })
})
