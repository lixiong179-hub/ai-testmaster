import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, createFormInstanceMock, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  route: { params: {} as Record<string, string> },
  taskStore: {} as Record<string, unknown>,
  getProjectCases: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => mocks.route,
}))

vi.mock('@/store/task', () => ({ useTaskStore: () => mocks.taskStore }))

vi.mock('@/api/testTask', () => ({
  default: { getProjectCases: mocks.getProjectCases },
}))

import { useTaskCreate } from '../useTaskCreate'

type Ctx = ReturnType<typeof useTaskCreate>

const host = createComposableHost(() => useTaskCreate())
let ctx: Ctx

function pageOf(items: unknown[], total: number) {
  return { data: { items, total } }
}

async function mountHost() {
  mocks.taskStore = {
    createTask: vi.fn().mockResolvedValue(undefined),
  }
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    case_no: 'TC-1',
    title: '登录用例',
    module: '登录',
    priority: 1,
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.params = { projectId: '7' }
  silenceElMessage()
  mocks.getProjectCases.mockResolvedValue(pageOf([], 0))
})

describe('useTaskCreate — 表单与派生', () => {
  it('路由项目 ID 同步到表单', async () => {
    await mountHost()

    expect(ctx.projectId.value).toBe(7)
    expect(ctx.form.value.project_id).toBe(7)
  })

  it('模块列表去重', async () => {
    await mountHost()
    ctx.cases.value = [
      makeCase({ id: 1, module: '登录' }),
      makeCase({ id: 2, module: '登录' }),
      makeCase({ id: 3, module: '下单' }),
      makeCase({ id: 4, module: undefined }),
    ] as never

    expect(ctx.modules.value).toEqual(['登录', '下单'])
  })

  it('按模块、优先级、关键词过滤', async () => {
    await mountHost()
    ctx.cases.value = [
      makeCase({ id: 1, module: '登录', priority: 1, title: '登录成功' }),
      makeCase({ id: 2, module: '下单', priority: 2, title: '提交订单', case_no: 'TC-9' }),
    ] as never

    expect(ctx.filteredCases.value).toHaveLength(2)

    ctx.filter.value.module = '登录'
    expect(ctx.filteredCases.value.map((c) => c.id)).toEqual([1])

    ctx.filter.value.module = ''
    ctx.filter.value.priority = 2
    expect(ctx.filteredCases.value.map((c) => c.id)).toEqual([2])

    ctx.filter.value.priority = ''
    ctx.filter.value.keyword = 'tc-9'
    expect(ctx.filteredCases.value.map((c) => c.id)).toEqual([2])
  })

  it('关键词也能匹配用例标题', async () => {
    await mountHost()
    ctx.cases.value = [makeCase({ id: 1, title: 'Login Flow', case_no: 'X' })] as never
    ctx.filter.value.keyword = 'flo'

    expect(ctx.filteredCases.value).toHaveLength(1)
  })

  it('全选与取消全选维护选中 ID', async () => {
    await mountHost()
    ctx.cases.value = [makeCase({ id: 1 }), makeCase({ id: 2 })] as never
    ctx.form.value.case_ids = [1]

    expect(ctx.selectAll.value).toBe(false)

    ctx.selectAll.value = true
    expect(ctx.form.value.case_ids.sort()).toEqual([1, 2])
    expect(ctx.selectAll.value).toBe(true)

    ctx.selectAll.value = false
    expect(ctx.form.value.case_ids).toEqual([])
  })

  it('空列表时全选为 false', async () => {
    await mountHost()

    expect(ctx.selectAll.value).toBe(false)
  })

  it('优先级文案与标签类型', async () => {
    await mountHost()

    expect(ctx.priorityText(1)).toBe('高')
    expect(ctx.priorityText(2)).toBe('中')
    expect(ctx.priorityText(3)).toBe('低')
    expect(ctx.priorityText(9)).toBe('未知')
    expect(ctx.priorityText(undefined)).toBe('-')

    expect(ctx.priorityType(1)).toBe('danger')
    expect(ctx.priorityType(2)).toBe('warning')
    expect(ctx.priorityType(3)).toBe('success')
    expect(ctx.priorityType(9)).toBe('info')
    expect(ctx.priorityType(undefined)).toBe('info')
  })
})

describe('useTaskCreate — 选择与分页', () => {
  it('表格选择同步到表单', async () => {
    await mountHost()

    ctx.handleSelectionChange([makeCase({ id: 3 }), makeCase({ id: 4 })] as never)

    expect(ctx.form.value.case_ids).toEqual([3, 4])
  })

  it('全选按钮联动表格实例', async () => {
    await mountHost()
    const toggleAllSelection = vi.fn()
    const clearSelection = vi.fn()
    ctx.tableRef.value = { toggleAllSelection, clearSelection } as never

    ctx.handleSelectAll(true)
    expect(toggleAllSelection).toHaveBeenCalled()

    ctx.handleSelectAll(false)
    expect(clearSelection).toHaveBeenCalled()
  })

  it('清空选择同时重置表单 ID', async () => {
    await mountHost()
    const clearSelection = vi.fn()
    ctx.tableRef.value = { clearSelection } as never
    ctx.form.value.case_ids = [1]

    ctx.clearSelection()

    expect(clearSelection).toHaveBeenCalled()
    expect(ctx.form.value.case_ids).toEqual([])
  })

  it('搜索回到第一页，翻页更新页码', async () => {
    await mountHost()
    ctx.page.value = 3

    ctx.handleSearch()
    expect(ctx.page.value).toBe(1)

    ctx.handlePageChange(5)
    expect(ctx.page.value).toBe(5)
  })
})

describe('useTaskCreate — 用例加载', () => {
  it('单页加载并写入总数', async () => {
    mocks.getProjectCases.mockResolvedValue(pageOf([makeCase()], 1))
    await mountHost()

    expect(mocks.getProjectCases).toHaveBeenCalledWith(7, { page: 1, page_size: 100 })
    expect(ctx.cases.value).toHaveLength(1)
    expect(ctx.total.value).toBe(1)
  })

  it('分页聚合全部用例并按 ID 去重', async () => {
    mocks.getProjectCases
      .mockResolvedValueOnce(
        pageOf(
          Array.from({ length: 100 }, (_, i) => makeCase({ id: i + 1 })),
          150
        )
      )
      .mockResolvedValueOnce(pageOf([makeCase({ id: 1 }), makeCase({ id: 101 })], 150))
    await mountHost()

    expect(mocks.getProjectCases).toHaveBeenCalledTimes(2)
    expect(ctx.cases.value).toHaveLength(101)
    expect(ctx.cases.value.map((c) => c.id)).toContain(101)
  })

  it('空页时提前结束分页', async () => {
    mocks.getProjectCases.mockResolvedValueOnce(pageOf([], 500))
    await mountHost()

    expect(mocks.getProjectCases).toHaveBeenCalledTimes(1)
    expect(ctx.cases.value).toEqual([])
  })

  it('用例为空时给出提示', async () => {
    await mountHost()

    expect(ElMessage.warning).toHaveBeenCalledWith('该项目下暂无测试用例，请先生成测试用例')
  })

  it('加载失败提示错误并结束 loading', async () => {
    mocks.getProjectCases.mockRejectedValue(new Error('接口异常'))
    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('接口异常')
    expect(ctx.loading.value).toBe(false)
  })
})

describe('useTaskCreate — 提交与重置', () => {
  it('表单未挂载时直接返回', async () => {
    await mountHost()

    await ctx.submitForm()

    expect((mocks.taskStore as { createTask: unknown }).createTask).not.toHaveBeenCalled()
  })

  it('校验通过后创建任务并跳转列表', async () => {
    await mountHost()
    ctx.formRef.value = createFormInstanceMock({ withCallback: true }) as never
    ctx.form.value.task_name = '回归任务'
    ctx.form.value.description = '说明'
    ctx.form.value.case_ids = [1, 2]

    await ctx.submitForm()

    expect((mocks.taskStore as { createTask: unknown }).createTask).toHaveBeenCalledWith({
      task_name: '回归任务',
      project_id: 7,
      description: '说明',
      case_ids: [1, 2],
    })
    expect(ElMessage.success).toHaveBeenCalledWith('任务创建成功')
    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/7')
    expect(ctx.submitting.value).toBe(false)
  })

  it('创建失败提示错误并复位提交状态', async () => {
    await mountHost()
    ;(mocks.taskStore as { createTask: unknown }).createTask = vi
      .fn()
      .mockRejectedValue(new Error('创建失败'))
    ctx.formRef.value = createFormInstanceMock({ withCallback: true }) as never

    await ctx.submitForm()

    expect(ElMessage.error).toHaveBeenCalledWith('创建失败')
    expect(ctx.submitting.value).toBe(false)
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('校验失败时不提交', async () => {
    await mountHost()
    ctx.formRef.value = createFormInstanceMock({ valid: false, withCallback: true }) as never

    await ctx.submitForm()

    expect((mocks.taskStore as { createTask: unknown }).createTask).not.toHaveBeenCalled()
  })

  it('重置表单清空描述、选择与表格选中', async () => {
    await mountHost()
    const resetFields = vi.fn()
    const clearSelection = vi.fn()
    ctx.formRef.value = { resetFields } as never
    ctx.tableRef.value = { clearSelection } as never
    ctx.form.value.description = 'x'
    ctx.form.value.case_ids = [1]

    ctx.resetForm()

    expect(resetFields).toHaveBeenCalled()
    expect(clearSelection).toHaveBeenCalled()
    expect(ctx.form.value.description).toBe('')
    expect(ctx.form.value.case_ids).toEqual([])
  })
})
