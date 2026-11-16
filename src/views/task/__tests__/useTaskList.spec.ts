import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  route: { params: {} as Record<string, string> },
  taskStore: {} as Record<string, unknown>,
  projectStore: {} as Record<string, unknown>,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => mocks.route,
}))

vi.mock('@/store/task', () => ({ useTaskStore: () => mocks.taskStore }))
vi.mock('@/store/project', () => ({ useProjectStore: () => mocks.projectStore }))

import { useTaskList } from '../useTaskList'

type Ctx = ReturnType<typeof useTaskList>

function createTaskStore(overrides: Record<string, unknown> = {}) {
  return reactive({
    loading: false,
    taskList: [] as Record<string, unknown>[],
    taskStatusText: (status: number) => `状态${status}`,
    taskStatusColor: () => 'success',
    fetchTaskList: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    startTask: vi.fn().mockResolvedValue(undefined),
    stopTask: vi.fn().mockResolvedValue(undefined),
    deleteTask: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  })
}

const host = createComposableHost(() => useTaskList())
let ctx: Ctx

async function mountHost(
  taskPatch: Record<string, unknown> = {},
  projectPatch: Record<string, unknown> = {}
) {
  mocks.taskStore = createTaskStore(taskPatch)
  mocks.projectStore = reactive({
    projects: [{ id: 7, name: '项目A' }],
    fetchProjects: vi.fn().mockResolvedValue(undefined),
    ...projectPatch,
  })
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.route.params = {}
  silenceElMessage()
  mockConfirm()
})

describe('useTaskList — 派生状态', () => {
  it('路由参数解析项目 ID 与概览模式', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    expect(ctx.projectId.value).toBe(7)
    expect(ctx.isOverview.value).toBe(false)
  })

  it('无路由参数时为概览模式并使用筛选项目', async () => {
    await mountHost()

    expect(ctx.projectId.value).toBe(0)
    expect(ctx.isOverview.value).toBe(true)

    ctx.filter.value.projectId = 5
    ctx.createTask()
    expect(mocks.push).toHaveBeenCalledWith('/home/task/create/5')
  })

  it('进度颜色按区间切换', async () => {
    await mountHost()

    expect(ctx.getProgressColor(10)).toBe('#409EFF')
    expect(ctx.getProgressColor(50)).toBe('#E6A23C')
    expect(ctx.getProgressColor(90)).toBe('#67C23A')
  })

  it('进度状态按任务结果判定', async () => {
    await mountHost()

    expect(ctx.getProgressStatus({ status: 3, fail_count: 0 })).toBe('exception')
    expect(ctx.getProgressStatus({ status: 2, fail_count: 0 })).toBe('success')
    expect(ctx.getProgressStatus({ status: 2, fail_count: 1 })).toBeUndefined()
    expect(ctx.getProgressStatus({ status: 1, fail_count: 0 })).toBeUndefined()
  })

  it('状态文案与颜色透传 store', async () => {
    await mountHost()

    expect(ctx.taskStatusText(1)).toBe('状态1')
    expect(ctx.taskStatusColor(1)).toBe('success')
  })
})

describe('useTaskList — 列表加载', () => {
  it('挂载时加载任务与项目列表', async () => {
    await mountHost()

    expect((mocks.taskStore as { fetchTaskList: unknown }).fetchTaskList).toHaveBeenCalled()
    expect((mocks.projectStore as { fetchProjects: unknown }).fetchProjects).not.toHaveBeenCalled()
  })

  it('项目列表为空时才拉取项目', async () => {
    await mountHost({}, { projects: [] })

    expect((mocks.projectStore as { fetchProjects: unknown }).fetchProjects).toHaveBeenCalled()
  })

  it('拉取参数包含分页、项目与状态', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockClear()
    ctx.filter.value.status = 2
    ctx.page.value = 3
    ctx.pageSize.value = 20

    await ctx.fetchTaskList()

    expect(fetchTaskList).toHaveBeenCalledWith({
      page: 3,
      page_size: 20,
      project_id: 7,
      task_status: 2,
    })
  })

  it('状态为空串时不传 task_status', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockClear()
    ctx.filter.value.status = ''

    await ctx.fetchTaskList()

    expect(fetchTaskList).toHaveBeenCalledWith({ page: 1, page_size: 10, project_id: 7 })
  })

  it('返回结果写回列表与总数', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockClear()
    fetchTaskList.mockResolvedValue({ items: [{ id: 1 }, { id: 2 }], total: 42 })

    await ctx.fetchTaskList()

    expect((mocks.taskStore as { taskList: unknown[] }).taskList).toHaveLength(2)
    expect(ctx.total.value).toBe(42)
  })

  it('结果非数组时按空处理', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost({ taskList: [{ id: 9 }] })
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockClear()
    fetchTaskList.mockResolvedValue({ items: null, total: null })

    await ctx.fetchTaskList()

    expect((mocks.taskStore as { taskList: unknown[] }).taskList).toHaveLength(0)
    expect(ctx.total.value).toBe(0)
  })

  it('加载失败提示错误消息', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockRejectedValue(new Error('接口异常'))

    await ctx.fetchTaskList()

    expect(ElMessage.error).toHaveBeenCalledWith('接口异常')
  })

  it('加载失败且非 Error 时使用兜底文案', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockRejectedValue('boom')

    await ctx.fetchTaskList()

    expect(ElMessage.error).toHaveBeenCalledWith('获取任务列表失败')
  })

  it('分页切换更新页码并刷新', async () => {
    await mountHost()
    const fetchTaskList = (mocks.taskStore as { fetchTaskList: ReturnType<typeof vi.fn> })
      .fetchTaskList
    fetchTaskList.mockClear()

    ctx.handleSizeChange(50)
    expect(ctx.pageSize.value).toBe(50)

    ctx.handleCurrentChange(4)
    expect(ctx.page.value).toBe(4)
    expect(fetchTaskList).toHaveBeenCalledTimes(2)
  })
})

describe('useTaskList — 导航', () => {
  it('无项目时创建任务给出提示', async () => {
    await mountHost()

    ctx.createTask()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('有项目时跳转创建页', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    ctx.createTask()

    expect(mocks.push).toHaveBeenCalledWith('/home/task/create/7')
  })

  it('跳转测试点管理携带项目参数', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    ctx.goToTestPointManagement()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: { projectId: '7' },
    })
  })

  it('概览模式跳转测试点管理不带参数', async () => {
    await mountHost()

    ctx.goToTestPointManagement()

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: {},
    })
  })

  it('查看任务详情与行点击', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    ctx.viewTask({ id: 9 })
    expect(mocks.push).toHaveBeenCalledWith('/home/task/detail/9?project_id=7')

    ctx.handleRowClick({ id: 10 })
    expect(mocks.push).toHaveBeenCalledWith('/home/task/detail/10?project_id=7')
  })
})

describe('useTaskList — 任务操作', () => {
  it('启动任务成功后刷新', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    const store = mocks.taskStore as {
      startTask: ReturnType<typeof vi.fn>
      fetchTaskList: ReturnType<typeof vi.fn>
    }
    store.fetchTaskList.mockClear()

    await ctx.startTask({ id: 9 })

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(store.startTask).toHaveBeenCalledWith(9, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已开始执行')
    expect(store.fetchTaskList).toHaveBeenCalled()
  })

  it('启动任务失败提示错误', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    ;(mocks.taskStore as { startTask: unknown }).startTask = vi
      .fn()
      .mockRejectedValue(new Error('启动失败'))

    await ctx.startTask({ id: 9 })

    expect(ElMessage.error).toHaveBeenCalledWith('启动失败')
  })

  it('启动任务取消时静默', async () => {
    mockCancel()
    mocks.route.params = { projectId: '7' }
    await mountHost()

    await ctx.startTask({ id: 9 })

    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('停止任务成功后刷新', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    await ctx.stopTask({ id: 9 })

    expect((mocks.taskStore as { stopTask: unknown }).stopTask).toHaveBeenCalledWith(9, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务已停止')
  })

  it('停止任务失败提示错误', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    ;(mocks.taskStore as { stopTask: unknown }).stopTask = vi
      .fn()
      .mockRejectedValue(new Error('停止失败'))

    await ctx.stopTask({ id: 9 })

    expect(ElMessage.error).toHaveBeenCalledWith('停止失败')
  })

  it('删除任务使用名称提示并刷新', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()

    await ctx.deleteTaskConfirm({ id: 9, task_name: '回归任务' })

    expect(ElMessageBox.confirm).toHaveBeenCalledWith(
      '确定要删除任务"回归任务"吗？此操作不可恢复。',
      '删除确认',
      expect.any(Object)
    )
    expect((mocks.taskStore as { deleteTask: unknown }).deleteTask).toHaveBeenCalledWith(9, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('任务删除成功')
  })

  it('删除失败提示错误', async () => {
    mocks.route.params = { projectId: '7' }
    await mountHost()
    ;(mocks.taskStore as { deleteTask: unknown }).deleteTask = vi
      .fn()
      .mockRejectedValue(new Error('删除失败'))

    await ctx.deleteTaskConfirm({ id: 9, task_name: 'x' })

    expect(ElMessage.error).toHaveBeenCalledWith('删除失败')
  })
})
