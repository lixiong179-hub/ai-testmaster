import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({
  getFileList: vi.fn(),
  getUIPrototypeProjectList: vi.fn(),
}))

vi.mock('@/api/file', () => ({ fileApi: { getFileList: mocks.getFileList } }))
vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: { getUIPrototypeProjectList: mocks.getUIPrototypeProjectList },
}))

import { useResourceList } from '../useResourceList'

type IterationManagerLike = {
  getIterationIdParam: ReturnType<typeof vi.fn>
  selectedIterationId: number | null
}

function setup(projectId: number | '' = 1, iterationParam: unknown = undefined) {
  const iterationManager: IterationManagerLike = {
    getIterationIdParam: vi.fn(() => iterationParam),
    selectedIterationId: null,
  }
  const ctx = useResourceList(iterationManager as never)
  ctx.filterForm.project_id = projectId
  return { ctx, iterationManager }
}

const fileItem = {
  id: 1,
  project_id: 1,
  file_name: '需求文档v1.docx',
  resource_type: 'requirement',
  file_url: '/f/1',
  file_type: 'docx',
  is_active: true,
  size: 1024,
  upload_time: '2026-11-01 10:00:00',
  iteration_id: 5,
}

const protoItem = {
  id: 9,
  project_id: 1,
  name: '登录原型',
  description: '登录页',
  screen_count: 3,
  create_time: '2026-11-02 10:00:00',
  iteration_id: 5,
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  mocks.getFileList.mockResolvedValue({ data: { items: [fileItem] } })
  mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { items: [protoItem] } })
})

describe('useResourceList — 未选择项目', () => {
  it('直接清空列表且不发起请求', async () => {
    const { ctx } = setup('')
    ctx.resources = [{ id: 1 } as never]
    ctx.total = 3

    await ctx.getResources()

    expect(mocks.getFileList).not.toHaveBeenCalled()
    expect(mocks.getUIPrototypeProjectList).not.toHaveBeenCalled()
    expect(ctx.resources).toEqual([])
    expect(ctx.total).toBe(0)
    expect(ctx.loading).toBe(false)
  })
})

describe('useResourceList — 双来源合并', () => {
  it('文件与原型各自带分页与迭代参数，并统一字段', async () => {
    const { ctx, iterationManager } = setup(1, 5)
    ctx.pagination.page = 2
    ctx.pagination.pageSize = 20

    await ctx.getResources()

    expect(iterationManager.getIterationIdParam).toHaveBeenCalled()
    expect(mocks.getFileList).toHaveBeenCalledWith(1, 5, 2, 20)
    expect(mocks.getUIPrototypeProjectList).toHaveBeenCalledWith(1, 2, 20, 5)

    const file = ctx.resources.find((r) => r.source_type === 'file')!
    expect(file).toMatchObject({
      id: 1,
      name: '需求文档v1.docx',
      resource_type: 'requirement',
      is_active: true,
      created_at: '2026-11-01 10:00:00',
      upload_time: '2026-11-01 10:00:00',
      iteration_id: 5,
    })

    const proto = ctx.resources.find((r) => r.source_type === 'ui_prototype')!
    expect(proto).toMatchObject({
      id: 9,
      name: '登录原型',
      resource_type: 'ui_mockup',
      is_active: true,
      screen_count: 3,
      prototype_project_id: 9,
      description: '登录页',
      created_at: '2026-11-02 10:00:00',
    })
    expect(ctx.resources).toHaveLength(2)
  })

  it('按 upload_time 倒序，缺失时间排最后', async () => {
    mocks.getFileList.mockResolvedValue([
      { id: 1, file_name: '旧', resource_type: 'requirement', upload_time: '2026-01-01T00:00:00' },
      { id: 2, file_name: '无时间', resource_type: 'other' },
    ])
    mocks.getUIPrototypeProjectList.mockResolvedValue([
      { id: 3, name: '新', create_time: '2026-12-01T00:00:00' },
    ])
    const { ctx } = setup()

    await ctx.getResources()

    expect(ctx.resources.map((r) => r.name)).toEqual(['新', '旧', '无时间'])
  })

  it('文件字段缺省时按默认值兜底', async () => {
    mocks.getFileList.mockResolvedValue([{ id: 4, file_name: '无类型文件', is_active: false }])
    mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { items: [] } })
    const { ctx } = setup()

    await ctx.getResources()

    expect(ctx.resources[0]).toMatchObject({
      resource_type: 'other',
      is_active: false,
      created_at: undefined,
    })
  })
})

describe('useResourceList — 类型筛选', () => {
  it('选择 ui_mockup 时只请求原型接口', async () => {
    const { ctx } = setup()
    ctx.filterForm.resource_type = 'ui_mockup'

    await ctx.getResources()

    expect(mocks.getFileList).not.toHaveBeenCalled()
    expect(mocks.getUIPrototypeProjectList).toHaveBeenCalledTimes(1)
    expect(ctx.resources.every((r) => r.resource_type === 'ui_mockup')).toBe(true)
  })

  it('选择具体文件类型时只请求文件接口并二次过滤', async () => {
    mocks.getFileList.mockResolvedValue({
      data: {
        items: [
          { id: 1, file_name: '需求', resource_type: 'requirement' },
          { id: 2, file_name: '接口', resource_type: 'api_doc' },
        ],
      },
    })
    const { ctx } = setup()
    ctx.filterForm.resource_type = 'requirement'

    await ctx.getResources()

    expect(mocks.getUIPrototypeProjectList).not.toHaveBeenCalled()
    expect(ctx.resources.map((r) => r.name)).toEqual(['需求'])
  })
})

describe('useResourceList — 容错', () => {
  it.each([
    ['纯数组', [{ id: 1, file_name: 'a' }]],
    ['items 包裹', { items: [{ id: 1, file_name: 'a' }] }],
    ['data.items 包裹', { data: { items: [{ id: 1, file_name: 'a' }] } }],
    ['data 数组', { data: [{ id: 1, file_name: 'a' }] }],
  ])('文件响应支持 %s', async (_label, response) => {
    mocks.getFileList.mockResolvedValue(response)
    mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { items: [] } })
    const { ctx } = setup()

    await ctx.getResources()

    expect(ctx.resources).toHaveLength(1)
  })

  it('无法识别的响应视为空列表', async () => {
    mocks.getFileList.mockResolvedValue({ data: { total: 1 } })
    mocks.getUIPrototypeProjectList.mockResolvedValue(null)
    const { ctx } = setup()

    await ctx.getResources()

    expect(ctx.resources).toEqual([])
    expect(ctx.total).toBe(0)
  })

  it('单个接口失败只告警，另一个来源仍可用', async () => {
    mocks.getFileList.mockRejectedValue(new Error('file down'))
    const { ctx } = setup()

    await ctx.getResources()

    expect(console.warn).toHaveBeenCalledWith('获取文件列表失败:', expect.any(Error))
    expect(ctx.resources.map((r) => r.source_type)).toEqual(['ui_prototype'])
    expect(ctx.loading).toBe(false)
  })

  it('迭代参数获取抛错时整体回退为空列表', async () => {
    const { ctx, iterationManager } = setup()
    iterationManager.getIterationIdParam.mockImplementation(() => {
      throw new Error('boom')
    })

    await ctx.getResources()

    expect(console.error).toHaveBeenCalledWith('获取资源列表失败:', expect.any(Error))
    expect(ctx.resources).toEqual([])
    expect(ctx.total).toBe(0)
    expect(ctx.loading).toBe(false)
  })
})

describe('useResourceList — 查询与分页操作', () => {
  it('handleSearch 重置页码后重新加载', async () => {
    const { ctx } = setup()
    ctx.pagination.page = 3

    ctx.handleSearch()
    await Promise.resolve()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getFileList).toHaveBeenCalledTimes(1)
  })

  it('handleSizeChange 更新页长并回到第一页', async () => {
    const { ctx } = setup()
    ctx.pagination.page = 4

    ctx.handleSizeChange(50)
    await Promise.resolve()

    expect(ctx.pagination.pageSize).toBe(50)
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getFileList).toHaveBeenCalledWith(1, undefined, 1, 50)
  })

  it('handleCurrentChange 切换页码', async () => {
    const { ctx } = setup()

    ctx.handleCurrentChange(3)
    await Promise.resolve()

    expect(ctx.pagination.page).toBe(3)
    expect(mocks.getFileList).toHaveBeenCalledWith(1, undefined, 3, 10)
  })

  it('refreshAndResetPage 回到第一页并等待加载完成', async () => {
    const { ctx } = setup()
    ctx.pagination.page = 5

    await ctx.refreshAndResetPage()

    expect(ctx.pagination.page).toBe(1)
    expect(ctx.resources).toHaveLength(2)
  })

  it('handleReset 清空筛选、迭代选择与列表', () => {
    const { ctx, iterationManager } = setup()
    ctx.filterForm.resource_type = 'ui_mockup'
    ctx.pagination.page = 4
    ctx.resources = [{ id: 1 } as never]
    ctx.total = 1

    ctx.handleReset()

    expect(ctx.filterForm.project_id).toBe('')
    expect(ctx.filterForm.resource_type).toBe('')
    expect(iterationManager.selectedIterationId).toBeNull()
    expect(ctx.pagination.page).toBe(1)
    expect(ctx.resources).toEqual([])
    expect(ctx.total).toBe(0)
  })

  it('isLoading 跟随 loading 状态', async () => {
    const { ctx } = setup()

    expect(ctx.isLoading).toBe(false)
    const promise = ctx.getResources()
    expect(ctx.isLoading).toBe(true)
    await promise
    expect(ctx.isLoading).toBe(false)
  })
})

describe('useResourceList — 类型映射', () => {
  it.each([
    ['requirement', 'primary', '需求文档'],
    ['ui_mockup', 'warning', 'UI原型图'],
    ['api_doc', 'success', 'API文档'],
    ['test_data', 'info', '测试数据'],
    ['other', 'info', '其他'],
  ])('类型 %s → 标签色 %s / 文案 %s', (type, tagType, label) => {
    const { ctx } = setup()

    expect(ctx.getResourceTypeTagType(type)).toBe(tagType)
    expect(ctx.getResourceTypeLabel(type)).toBe(label)
  })

  it('未知类型回退为 info 与原值', () => {
    const { ctx } = setup()

    expect(ctx.getResourceTypeTagType('unknown')).toBe('info')
    expect(ctx.getResourceTypeLabel('unknown')).toBe('unknown')
  })
})
