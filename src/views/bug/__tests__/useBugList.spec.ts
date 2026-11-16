import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'
import type { BugItem } from '@/api/bug'

const mocks = vi.hoisted(() => ({
  route: { query: {} as Record<string, string> },
  getBugList: vi.fn(),
  getProjects: vi.fn(),
  projectStore: { currentProjectId: 0 as number | undefined },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
}))

vi.mock('@/api/bug', () => ({
  default: { getBugList: mocks.getBugList },
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/store/project', () => ({
  useProjectStore: () => mocks.projectStore,
}))

import {
  getPriorityLabel,
  getSeverityLabel,
  getSeverityTagType,
  getSourceLabel,
  getStatusLabel,
  getStatusTagType,
  getUxCategoryLabel,
  parseAttachments,
  severityOptions,
  sourceOptions,
  statusOptions,
  uxCategoryOptions,
  useBugList,
} from '../useBugList'

type Ctx = ReturnType<typeof useBugList>
type Options = Parameters<typeof useBugList>[0]

function makeBug(overrides: Partial<BugItem> = {}): BugItem {
  return {
    id: 1,
    title: '登录按钮无响应',
    severity: 2,
    status: 'open',
    source: 'manual',
    ...overrides,
  } as BugItem
}

function setup(options: Options = {}) {
  const host = createComposableHost<Ctx>(() => useBugList(options))
  return host
}

async function mountHost(host = setup()) {
  const wrapper = await host.mount()
  return { wrapper, ctx: host.ctx }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.route.query = {}
  mocks.projectStore.currentProjectId = 0
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 9, name: '项目A' },
        { id: 10, name: '项目B' },
      ],
    },
  })
  mocks.getBugList.mockResolvedValue({
    data: { items: [makeBug()], total: 1 },
  })
})

describe('useBugList — 标签与解析工具', () => {
  it('严重级别文案与颜色映射，未知值原样返回', () => {
    expect(getSeverityLabel(1)).toBe('致命')
    expect(getSeverityLabel(3)).toBe('一般')
    expect(getSeverityLabel(9)).toBe('9')
    expect(getSeverityTagType(1)).toBe('danger')
    expect(getSeverityTagType(2)).toBe('warning')
    expect(getSeverityTagType(3)).toBe('primary')
    expect(getSeverityTagType(4)).toBe('info')
    expect(getSeverityTagType(9)).toBe('info')
  })

  it('来源与状态文案映射，未知值原样返回', () => {
    expect(getSourceLabel('manual')).toBe('手动')
    expect(getSourceLabel('self_test')).toBe('自测')
    expect(getSourceLabel('other')).toBe('other')

    expect(getStatusLabel('in_progress')).toBe('处理中')
    expect(getStatusLabel('unknown')).toBe('unknown')
    expect(getStatusTagType('open')).toBe('info')
    expect(getStatusTagType('in_progress')).toBe('primary')
    expect(getStatusTagType('fixed')).toBe('success')
    expect(getStatusTagType('closed')).toBe('success')
    expect(getStatusTagType('rejected')).toBe('danger')
    expect(getStatusTagType('unknown')).toBe('info')
  })

  it('UX 分类为空时展示占位符', () => {
    expect(getUxCategoryLabel(null)).toBe('-')
    expect(getUxCategoryLabel('')).toBe('-')
    expect(getUxCategoryLabel('security')).toBe('安全')
    expect(getUxCategoryLabel('custom')).toBe('custom')
  })

  it('优先级文案映射，未知值原样返回', () => {
    expect(getPriorityLabel(1)).toBe('高')
    expect(getPriorityLabel(3)).toBe('低')
    expect(getPriorityLabel(4)).toBe('4')
  })

  it('parseAttachments 只保留字符串数组', () => {
    expect(parseAttachments('["a.png","b.png"]')).toEqual(['a.png', 'b.png'])
    expect(parseAttachments('["a.png",1,null]')).toEqual(['a.png'])
    expect(parseAttachments('{"a":1}')).toEqual([])
    expect(parseAttachments('not-json')).toEqual([])
  })

  it('筛选项常量与后端枚举对齐', () => {
    expect(severityOptions.map((o) => o.value)).toEqual([1, 2, 3, 4])
    expect(sourceOptions.map((o) => o.value)).toEqual(['manual', 'self_test'])
    expect(statusOptions).toHaveLength(5)
    expect(uxCategoryOptions.map((o) => o.value)).toContain('security')
  })
})

describe('useBugList — 项目初始化', () => {
  it('挂载后加载项目并按 URL query 预选、自动查询', async () => {
    mocks.route.query = { project_id: '9' }

    const { ctx } = await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.projects.value).toHaveLength(2)
    expect(ctx.filters.project_id).toBe(9)
    expect(mocks.getBugList).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 9, page: 1, page_size: 20 })
    )
  })

  it('URL 无参数时回退全局项目上下文', async () => {
    mocks.projectStore.currentProjectId = 10

    const { ctx } = await mountHost()

    expect(ctx.filters.project_id).toBe(10)
    expect(mocks.getBugList).toHaveBeenCalledWith(expect.objectContaining({ project_id: 10 }))
  })

  it.each(['abc', '0', '-3'])('非法 query 参数 %s 被忽略', async (value) => {
    mocks.route.query = { project_id: value }

    const { ctx } = await mountHost()

    expect(ctx.filters.project_id).toBe('')
    expect(mocks.getBugList).not.toHaveBeenCalled()
  })

  it('项目加载失败时提示 Error 信息', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('项目服务异常')
  })

  it('项目加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getProjects.mockRejectedValue('boom')

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('嵌入式传入 projectId 时跳过项目下拉直接查询', async () => {
    const host = setup({ projectId: 9, taskId: 77 })

    const { ctx } = await mountHost(host)

    expect(mocks.getProjects).not.toHaveBeenCalled()
    expect(ctx.filters.project_id).toBe(9)
    expect(ctx.taskId.value).toBe(77)
    expect(mocks.getBugList).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: 9, task_id: 77 })
    )
  })
})

describe('useBugList — 列表查询', () => {
  it('未选项目时给出提示且不请求', async () => {
    const { ctx } = await mountHost()

    await ctx.loadBugs()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(mocks.getBugList).not.toHaveBeenCalled()
  })

  it('按筛选条件组装请求参数', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()
    ctx.filters.severity = 1
    ctx.filters.source = 'self_test'
    ctx.filters.ux_category = 'security'
    ctx.filters.status = 'fixed'
    ctx.pagination.page = 2
    mocks.getBugList.mockClear()

    await ctx.loadBugs()

    expect(mocks.getBugList).toHaveBeenCalledWith({
      project_id: 9,
      page: 2,
      page_size: 20,
      severity: 1,
      source: 'self_test',
      ux_category: 'security',
      status: 'fixed',
    })
  })

  it('成功后写入列表与总数', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getBugList.mockResolvedValue({
      data: { items: [makeBug(), makeBug({ id: 2 })], total: 8 },
    })

    const { ctx } = await mountHost()

    expect(ctx.bugs.value).toHaveLength(2)
    expect(ctx.pagination.total).toBe(8)
    expect(ctx.loading.value).toBe(false)
    expect(ctx.errorMessage.value).toBe('')
  })

  it('接口缺少 items 时降级为空数组', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getBugList.mockResolvedValue({ data: {} })

    const { ctx } = await mountHost()

    expect(ctx.bugs.value).toEqual([])
    expect(ctx.pagination.total).toBe(0)
  })

  it('查询失败时写入错误信息并提示', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getBugList.mockRejectedValue(new Error('网关异常'))

    const { ctx } = await mountHost()

    expect(ctx.errorMessage.value).toBe('网关异常')
    expect(ElMessage.error).toHaveBeenCalledWith('网关异常')
    expect(ctx.loading.value).toBe(false)
  })

  it('查询失败且非 Error 时使用兜底文案', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getBugList.mockRejectedValue(undefined)

    const { ctx } = await mountHost()

    expect(ctx.errorMessage.value).toBe('获取缺陷列表失败')
  })

  it('查询时重置到第一页', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()
    ctx.pagination.page = 3
    mocks.getBugList.mockClear()

    ctx.handleSearch()
    await Promise.resolve()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getBugList).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }))
  })

  it('重置筛选保留已选项目', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()
    ctx.filters.severity = 1
    ctx.filters.source = 'manual'
    ctx.filters.ux_category = 'security'
    ctx.filters.status = 'open'
    ctx.pagination.page = 4
    mocks.getBugList.mockClear()

    ctx.handleReset()
    await Promise.resolve()

    expect(ctx.filters).toEqual({
      project_id: 9,
      severity: '',
      source: '',
      ux_category: '',
      status: '',
    })
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getBugList).toHaveBeenCalledTimes(1)
  })

  it('调整每页条数后回到第一页并查询', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()
    ctx.pagination.page = 2
    mocks.getBugList.mockClear()

    ctx.handleSizeChange(50)
    await Promise.resolve()

    expect(ctx.pagination.pageSize).toBe(50)
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getBugList).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 50 })
    )
  })

  it('切换页码后查询', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()
    mocks.getBugList.mockClear()

    ctx.handleCurrentChange(2)
    await Promise.resolve()

    expect(ctx.pagination.page).toBe(2)
    expect(mocks.getBugList).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))
  })
})

describe('useBugList — 详情与展示辅助', () => {
  it('打开与关闭详情弹窗', async () => {
    const { ctx } = await mountHost()
    const bug = makeBug()

    ctx.handleViewDetail(bug)
    expect(ctx.currentBug.value).toEqual(bug)
    expect(ctx.detailVisible.value).toBe(true)

    ctx.handleDetailClose()
    expect(ctx.currentBug.value).toBeNull()
    expect(ctx.detailVisible.value).toBe(false)
  })

  it('currentProjectName 按所选项目取名称', async () => {
    mocks.route.query = { project_id: '9' }
    const { ctx } = await mountHost()

    expect(ctx.currentProjectName()).toBe('项目A')

    ctx.filters.project_id = 404
    expect(ctx.currentProjectName()).toBe('-')

    ctx.filters.project_id = ''
    expect(ctx.currentProjectName()).toBe('-')
  })
})
