import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createComposableHost } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  route: { query: {} as Record<string, string> },
  getProjects: vi.fn(),
  getList: vi.fn(),
  getRequirementOptions: vi.fn(),
  remove: vi.fn(),
  batchDelete: vi.fn(),
  batchGenerateStream: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: {
    getList: mocks.getList,
    getRequirementOptions: mocks.getRequirementOptions,
    delete: mocks.remove,
    batchDelete: mocks.batchDelete,
    batchGenerateStream: mocks.batchGenerateStream,
  },
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  const message = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    close: vi.fn(),
    closeAll: vi.fn(),
  })
  return {
    ...actual,
    ElMessage: message,
    ElMessageBox: { ...actual.ElMessageBox, confirm: vi.fn() },
  }
})

import { ElMessage, ElMessageBox } from 'element-plus'
import { useTestPointManagement } from '../useTestPointManagement'

const messageMock = ElMessage as unknown as ReturnType<typeof vi.fn> & {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
  warning: ReturnType<typeof vi.fn>
}
const confirmMock = ElMessageBox.confirm as unknown as ReturnType<typeof vi.fn>

type Ctx = ReturnType<typeof useTestPointManagement>

const host = createComposableHost<Ctx>(() => useTestPointManagement())
let ctx: Ctx

const EMPTY_STATS = {
  total: 0,
  high_priority_count: 0,
  medium_priority_count: 0,
  low_priority_count: 0,
  generated_case_count: 0,
}

const RICH_STATS = {
  total: 12,
  high_priority_count: 5,
  medium_priority_count: 4,
  low_priority_count: 3,
  generated_case_count: 7,
}

function makePoint(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    project_id: 9,
    point: '登录成功',
    priority: 1,
    module: '登录',
    ...overrides,
  }
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

async function* streamOf(...items: unknown[]) {
  for (const item of items) yield item
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.query = {}
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 9, name: '项目A' },
        { id: 10, name: '默认项目' },
      ],
    },
  })
  mocks.getList.mockResolvedValue({
    items: [makePoint()],
    total: 1,
    stats: RICH_STATS,
  })
  mocks.getRequirementOptions.mockResolvedValue([{ id: 1, title: '需求一' }])
  mocks.remove.mockResolvedValue({})
  mocks.batchDelete.mockResolvedValue({})
  mocks.batchGenerateStream.mockResolvedValue(
    streamOf({ progress: 40, message: '生成中...', status: 'running' })
  )
  confirmMock.mockResolvedValue('confirm')
})

describe('useTestPointManagement — 初始化', () => {
  it('未带路由参数时仅加载项目且过滤「默认项目」', async () => {
    await mountHost()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(ctx.projects.value.map((p) => p.name)).toEqual(['项目A'])
    expect(ctx.selectedProjectId.value).toBeUndefined()
    expect(mocks.getList).not.toHaveBeenCalled()
  })

  it('路由带 project_id 时自动选中并加载列表与需求选项', async () => {
    mocks.route.query = { project_id: '9' }

    await mountHost()

    expect(ctx.selectedProjectId.value).toBe(9)
    expect(mocks.getList).toHaveBeenCalledWith(
      9,
      expect.objectContaining({ page: 1, page_size: 10 })
    )
    expect(mocks.getRequirementOptions).toHaveBeenCalledWith(9)
    expect(ctx.testPoints.value).toHaveLength(1)
    expect(ctx.total.value).toBe(1)
  })

  it('路由带 file_id 时初始化待提取文件并自动打开提取弹窗', async () => {
    mocks.route.query = { project_id: '9', file_id: '88' }

    await mountHost()

    expect(ctx.initialExtractFileId.value).toBe(88)
    expect(ctx.extractDialogVisible.value).toBe(true)
  })

  it('路由带 openExtract=1 时自动打开提取弹窗', async () => {
    mocks.route.query = { project_id: '9', openExtract: '1' }

    await mountHost()

    expect(ctx.extractDialogVisible.value).toBe(true)
  })

  it('项目加载失败时提示错误', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目接口异常'))

    await mountHost()

    expect(messageMock.error).toHaveBeenCalledWith('项目接口异常')
  })

  it('未选项目时 refreshManagementData 不发起请求', async () => {
    await mountHost()
    mocks.getList.mockClear()
    mocks.getRequirementOptions.mockClear()

    await ctx.handleProjectChange()

    expect(mocks.getList).not.toHaveBeenCalled()
    expect(mocks.getRequirementOptions).not.toHaveBeenCalled()
  })
})

describe('useTestPointManagement — 列表加载', () => {
  it('未选项目时清空列表、总数与统计', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()

    ctx.selectedProjectId.value = undefined
    await ctx.fetchTestPoints()

    expect(ctx.testPoints.value).toEqual([])
    expect(ctx.total.value).toBe(0)
    expect(ctx.listStats.value).toEqual(EMPTY_STATS)
  })

  it('按筛选条件、日期范围与分页组装请求参数', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.filters.module = '登录'
    ctx.filters.keyword = '成功'
    ctx.dateRange.value = ['2026-06-01', '2026-06-30']
    ctx.page.value = 2
    mocks.getList.mockClear()

    await ctx.fetchTestPoints()

    expect(mocks.getList).toHaveBeenCalledWith(9, {
      module: '登录',
      created_by: '',
      keyword: '成功',
      sort_by: 'create_time',
      sort_order: 'desc',
      created_from: '2026-06-01',
      created_to: '2026-06-30',
      page: 2,
      page_size: 10,
    })
  })

  it('加载失败时提示错误并清空数据', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getList.mockRejectedValue(new Error('列表接口异常'))
    await mountHost()

    expect(messageMock.error).toHaveBeenCalledWith('列表接口异常')
    expect(ctx.testPoints.value).toEqual([])
    expect(ctx.total.value).toBe(0)
    expect(ctx.listStats.value).toEqual(EMPTY_STATS)
    expect(ctx.loading.value).toBe(false)
  })

  it('需求选项加载失败时清空并提示', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.getRequirementOptions.mockRejectedValue(new Error('需求接口异常'))
    await mountHost()

    expect(ctx.requirementOptions.value).toEqual([])
    expect(messageMock.error).toHaveBeenCalledWith('需求接口异常')
  })
})

describe('useTestPointManagement — 统计与计算属性', () => {
  it('统计数量来自列表接口返回的 stats', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()

    expect(ctx.highCount.value).toBe(5)
    expect(ctx.mediumCount.value).toBe(4)
    expect(ctx.lowCount.value).toBe(3)
    expect(ctx.statsTotal.value).toBe(12)
    expect(ctx.generatedCaseCount.value).toBe(7)
  })

  it('selectedProjectName 按当前项目取名称', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()

    expect(ctx.selectedProjectName.value).toBe('项目A')

    ctx.selectedProjectId.value = 404
    expect(ctx.selectedProjectName.value).toBe('')
  })

  it.each([
    ['running', undefined],
    ['success', 'success'],
    ['partial', 'warning'],
    ['warning', 'warning'],
    ['error', 'exception'],
  ])('生成状态 %s 映射为进度条状态 %s', async (status, expected) => {
    await mountHost()
    ctx.generateStatus.value = status as Ctx['generateStatus']['value']

    expect(ctx.progressStatus.value).toBe(expected)
  })

  it('优先级文案与标签色映射', async () => {
    await mountHost()

    expect(ctx.priorityText(1)).toBe('高')
    expect(ctx.priorityText(2)).toBe('中')
    expect(ctx.priorityText(3)).toBe('低')
    expect(ctx.priorityTagType(1)).toBe('danger')
    expect(ctx.priorityTagType(2)).toBe('warning')
    expect(ctx.priorityTagType(9)).toBe('info')
  })
})

describe('useTestPointManagement — 选择与弹窗', () => {
  it('handleSelectionChange 记录选中行', async () => {
    await mountHost()
    const rows = [makePoint(), makePoint({ id: 2 })] as never[]

    ctx.handleSelectionChange(rows)

    // ref 会把数组包装为响应式代理，因此用深比较而非引用比较
    expect(ctx.selectedRows.value).toStrictEqual(rows)
  })

  it('新建弹窗清空编辑对象，编辑弹窗回填当前行', async () => {
    await mountHost()
    const row = makePoint() as never

    ctx.openEditDialog(row)
    expect(ctx.editingPoint.value).toEqual(row)
    expect(ctx.formDialogVisible.value).toBe(true)

    ctx.formDialogVisible.value = false
    ctx.openCreateDialog()
    expect(ctx.editingPoint.value).toBeNull()
    expect(ctx.formDialogVisible.value).toBe(true)
  })

  it('查看关联用例弹窗记录当前测试点', async () => {
    await mountHost()
    const row = makePoint() as never

    ctx.openCasesDialog(row)

    expect(ctx.currentTestPoint.value).toEqual(row)
    expect(ctx.casesDialogVisible.value).toBe(true)
  })

  it('优先级筛选重置页码并重新拉取', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.page.value = 3
    mocks.getList.mockClear()

    ctx.applyPriorityFilter(2)
    await Promise.resolve()

    expect(ctx.filters.priority).toBe(2)
    expect(ctx.page.value).toBe(1)
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('打开 XMind 导入与提取弹窗', async () => {
    await mountHost()

    ctx.openXmindImportDialog()
    expect(ctx.xmindImportDialogVisible.value).toBe(true)

    ctx.openExtractDialog()
    expect(ctx.extractDialogVisible.value).toBe(true)
  })

  it('旧版提取入口复用新提取弹窗', async () => {
    await mountHost()

    ctx.openLegacyExtractGuide()

    expect(ctx.extractDialogVisible.value).toBe(true)
  })

  it('openTaskList 未选项目不跳转，选中后跳转任务列表', async () => {
    await mountHost()

    ctx.openTaskList()
    expect(mocks.push).not.toHaveBeenCalled()

    ctx.selectedProjectId.value = 9
    ctx.openTaskList()
    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/9')
  })
})

describe('useTestPointManagement — 删除', () => {
  it('单条删除确认后调用接口、提示并刷新', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    mocks.getList.mockClear()

    await ctx.handleDelete(makePoint() as never)

    expect(confirmMock).toHaveBeenCalled()
    expect(mocks.remove).toHaveBeenCalledWith(1, 9)
    expect(messageMock.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('单条删除取消时不调用接口也不提示错误', async () => {
    await mountHost()
    confirmMock.mockRejectedValue('cancel')

    await ctx.handleDelete(makePoint() as never)

    expect(mocks.remove).not.toHaveBeenCalled()
    expect(messageMock.error).not.toHaveBeenCalled()
  })

  it('单条删除失败时提示接口错误', async () => {
    await mountHost()
    mocks.remove.mockRejectedValue(new Error('删除失败'))

    await ctx.handleDelete(makePoint() as never)

    expect(messageMock.error).toHaveBeenCalledWith('删除失败')
  })

  it('批量删除未选项目时提示先选项目', async () => {
    await mountHost()

    await ctx.handleBatchDelete()

    expect(messageMock.warning).toHaveBeenCalledWith('请先选择项目')
    expect(mocks.batchDelete).not.toHaveBeenCalled()
  })

  it('批量删除确认后清空选中并刷新', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.selectedRows.value = [makePoint({ id: 3 }), makePoint({ id: 4 })] as never[]
    mocks.getList.mockClear()

    await ctx.handleBatchDelete()

    expect(mocks.batchDelete).toHaveBeenCalledWith(9, [3, 4])
    expect(ctx.selectedRows.value).toEqual([])
    expect(messageMock.success).toHaveBeenCalledWith('批量删除成功')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('批量删除取消时不调用接口', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.selectedRows.value = [makePoint({ id: 3 })] as never[]
    confirmMock.mockRejectedValue('cancel')

    await ctx.handleBatchDelete()

    expect(mocks.batchDelete).not.toHaveBeenCalled()
  })
})

describe('useTestPointManagement — 用例生成', () => {
  it('未选项目时 startGenerate 提示且不打开弹窗', async () => {
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(messageMock.warning).toHaveBeenCalledWith('请先选择项目')
    expect(ctx.generateDialogVisible.value).toBe(false)
    expect(mocks.batchGenerateStream).not.toHaveBeenCalled()
  })

  it('单条生成成功后提示完成并刷新列表', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.batchGenerateStream.mockResolvedValue(
      streamOf(
        { progress: 50, message: '生成中...', status: 'running' },
        { progress: 100, message: '生成完成', status: 'success' }
      )
    )
    await mountHost()
    mocks.getList.mockClear()

    await ctx.handleGenerate(makePoint() as never)

    expect(mocks.batchGenerateStream).toHaveBeenCalledWith({ project_id: 9, test_point_ids: [1] })
    expect(ctx.generateDialogVisible.value).toBe(true)
    expect(ctx.generateProgress.value).toBe(100)
    expect(ctx.generateMessage.value).toBe('生成完成')
    expect(ctx.generateStatus.value).toBe('success')
    expect(messageMock.success).toHaveBeenCalledWith('测试用例生成完成')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
    expect(ctx.generating.value).toBe(false)
  })

  it('流结束仍为 running 时按成功处理', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(ctx.generateStatus.value).toBe('success')
    expect(messageMock.success).toHaveBeenCalledWith('测试用例生成完成')
  })

  it('部分成功时给出警告文案', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.batchGenerateStream.mockResolvedValue(
      streamOf({ progress: 80, message: '3 条失败', status: 'partial' })
    )
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(ctx.generateStatus.value).toBe('partial')
    expect(messageMock.warning).toHaveBeenCalledWith('3 条失败')
  })

  it('warning 状态优先于 running 且不覆盖已有终态', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.batchGenerateStream.mockResolvedValue(
      streamOf(
        { progress: 60, message: '部分缺失', status: 'warning' },
        { progress: 100, message: '完成', status: 'success' }
      )
    )
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(ctx.generateStatus.value).toBe('warning')
  })

  it('生成过程异常时标记 error 并提示', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.batchGenerateStream.mockRejectedValue(new Error('流式接口中断'))
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(ctx.generateStatus.value).toBe('error')
    expect(ctx.generateMessage.value).toBe('流式接口中断')
    expect(messageMock.error).toHaveBeenCalledWith('流式接口中断')
    expect(ctx.generating.value).toBe(false)
  })

  it('生成异常且非 Error 时使用兜底文案', async () => {
    mocks.route.query = { project_id: '9' }
    mocks.batchGenerateStream.mockRejectedValue(undefined)
    await mountHost()

    await ctx.handleGenerate(makePoint() as never)

    expect(ctx.generateMessage.value).toBe('生成失败')
  })

  it('取消确认时不发起生成', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    confirmMock.mockRejectedValue('cancel')

    await ctx.handleGenerate(makePoint() as never)

    expect(mocks.batchGenerateStream).not.toHaveBeenCalled()
  })

  it('批量生成携带选中行 ID', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.selectedRows.value = [makePoint({ id: 5 }), makePoint({ id: 6 })] as never[]

    await ctx.handleBatchGenerate()

    expect(mocks.batchGenerateStream).toHaveBeenCalledWith({
      project_id: 9,
      test_point_ids: [5, 6],
    })
  })

  it('批量生成取消时不发起请求', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.selectedRows.value = [makePoint({ id: 5 })] as never[]
    confirmMock.mockRejectedValue('cancel')

    await ctx.handleBatchGenerate()

    expect(mocks.batchGenerateStream).not.toHaveBeenCalled()
  })
})

describe('useTestPointManagement — 排序、分页与重置', () => {
  it('升序排序写入 sort 参数并刷新', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    mocks.getList.mockClear()

    ctx.handleSortChange({ prop: 'priority', order: 'ascending' })
    await Promise.resolve()

    expect(ctx.filters.sort_by).toBe('priority')
    expect(ctx.filters.sort_order).toBe('asc')
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('取消排序时回退默认排序与降序', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()

    ctx.handleSortChange({ prop: '', order: null })
    await Promise.resolve()

    expect(ctx.filters.sort_by).toBe('create_time')
    expect(ctx.filters.sort_order).toBe('desc')
  })

  it('调整每页条数后回到第一页并刷新', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.page.value = 3
    mocks.getList.mockClear()

    ctx.handlePageSizeChange(50)
    await Promise.resolve()

    expect(ctx.pageSize.value).toBe(50)
    expect(ctx.page.value).toBe(1)
    expect(mocks.getList).toHaveBeenCalledWith(
      9,
      expect.objectContaining({ page: 1, page_size: 50 })
    )
  })

  it('resetFilters 清空筛选条件并刷新', async () => {
    mocks.route.query = { project_id: '9' }
    await mountHost()
    ctx.filters.module = '登录'
    ctx.filters.priority = 1
    ctx.filters.requirement_id = 2
    ctx.filters.created_by = '张三'
    ctx.filters.keyword = '成功'
    ctx.filters.sort_by = 'priority'
    ctx.filters.sort_order = 'asc'
    ctx.dateRange.value = ['2026-06-01', '2026-06-30']
    ctx.page.value = 4
    mocks.getList.mockClear()

    ctx.resetFilters()
    await Promise.resolve()

    expect(ctx.filters).toMatchObject({
      module: '',
      priority: undefined,
      requirement_id: undefined,
      created_by: '',
      keyword: '',
      sort_by: 'create_time',
      sort_order: 'desc',
    })
    expect(ctx.dateRange.value).toEqual([])
    expect(ctx.page.value).toBe(1)
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })

  it('切换项目时重置项目相关状态后再加载', async () => {
    await mountHost()
    ctx.filters.keyword = '旧关键词'
    ctx.dateRange.value = ['2026-06-01', '2026-06-30']
    ctx.selectedRows.value = [makePoint()] as never[]
    ctx.page.value = 2

    ctx.selectedProjectId.value = 9
    await ctx.handleProjectChange()

    expect(ctx.page.value).toBe(1)
    expect(ctx.filters.keyword).toBe('')
    expect(ctx.dateRange.value).toEqual([])
    expect(ctx.selectedRows.value).toEqual([])
    expect(mocks.getList).toHaveBeenCalledTimes(1)
  })
})
