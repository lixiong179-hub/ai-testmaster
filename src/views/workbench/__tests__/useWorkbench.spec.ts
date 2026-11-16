import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createComposableHost, silenceConsole } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  store: {} as Record<string, unknown>,
  getProjectDetail: vi.fn(),
  getIterations: vi.fn(),
  getReviewsByIteration: vi.fn(),
  getProjectCases: vi.fn(),
  getTaskList: vi.fn(),
  getStats: vi.fn(),
  initChart: vi.fn(),
  chart: {
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/store/project', () => ({ useProjectStore: () => mocks.store }))

vi.mock('@/api/project', () => ({
  default: { getProjectDetail: mocks.getProjectDetail },
}))

vi.mock('@/api/iteration', () => ({
  iterationApi: { getIterations: mocks.getIterations },
}))

vi.mock('@/api/review', () => ({
  reviewApi: { getReviewsByIteration: mocks.getReviewsByIteration },
}))

vi.mock('@/api/testTask', () => ({
  default: {
    getProjectCases: mocks.getProjectCases,
    getTaskList: mocks.getTaskList,
  },
}))

vi.mock('@/api/aiInvocation', () => ({
  aiInvocationApi: { getStats: mocks.getStats },
  usdToCny: (usd: number) => Math.round(usd * 7 * 100) / 100,
}))

vi.mock('@/utils/echarts', () => ({
  echarts: { init: mocks.initChart },
}))

import { useWorkbench } from '../useWorkbench'

type Ctx = ReturnType<typeof useWorkbench>

const host = createComposableHost(() => useWorkbench())
let ctx: Ctx

async function mountHost(storePatch: Record<string, unknown> = {}) {
  mocks.store = reactive({
    currentProjectId: 7,
    projects: [{ id: 1, name: '项目A' }],
    fetchProjects: vi.fn().mockResolvedValue(undefined),
    setCurrentProject: vi.fn(),
    ...storePatch,
  })
  const wrapper = await host.mount()
  ctx = host.ctx
  await flushPromises()
  return wrapper
}

function taskItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    task_name: '任务A',
    status: 2,
    success_count: 8,
    fail_count: 2,
    total_count: 10,
    create_time: '2026-11-13T10:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceConsole('warn')
  mocks.initChart.mockReturnValue(mocks.chart)
  mocks.getProjectDetail.mockResolvedValue({ data: { name: '项目A' } })
  mocks.getIterations.mockResolvedValue({
    data: { total: 3, items: [{ id: 11 }, { id: 12 }] },
  })
  mocks.getReviewsByIteration.mockResolvedValue({
    data: {
      reviews: [
        { id: 101, iteration_id: 11, kind: 'case', status: 'in_progress', created_at: 't1' },
        { id: 102, iteration_id: 11, kind: 'case', status: 'completed', created_at: 't2' },
      ],
    },
  })
  mocks.getProjectCases.mockResolvedValue({ data: { total: 12 } })
  mocks.getTaskList.mockResolvedValue({ data: { items: [taskItem()], total: 5 } })
  mocks.getStats.mockResolvedValue({
    data: {
      items: [
        { group_key: '2026-11-12', total_cost_usd: 2, total_calls: 3 },
        { group_key: '2026-11-11', total_cost_usd: 1, total_calls: 4 },
      ],
    },
  })
})

describe('useWorkbench — 项目上下文', () => {
  it('有项目时 hasProject 为 true', async () => {
    await mountHost()

    expect(ctx.hasProject.value).toBe(true)
  })

  it('无项目时不发起加载请求', async () => {
    await mountHost({ currentProjectId: 0, projects: [] })

    expect(mocks.getProjectDetail).not.toHaveBeenCalled()
    expect(ctx.hasProject.value).toBe(false)
  })

  it('无当前项目但有项目时自动继承首个项目', async () => {
    await mountHost({ currentProjectId: null })

    expect((mocks.store as { setCurrentProject: unknown }).setCurrentProject).toHaveBeenCalledWith(
      1
    )
  })

  it('项目列表为空时才拉取项目', async () => {
    await mountHost({ projects: [] })

    expect((mocks.store as { fetchProjects: unknown }).fetchProjects).toHaveBeenCalled()
  })

  it('项目切换后重新加载区块', async () => {
    await mountHost()
    mocks.getProjectDetail.mockClear()

    mocks.store.currentProjectId = 8
    await flushPromises()

    expect(mocks.getProjectDetail).toHaveBeenCalledWith(8)
  })
})

describe('useWorkbench — 项目概览', () => {
  it('组合项目详情、迭代数、用例数与通过率', async () => {
    await mountHost()

    expect(ctx.overview.value).toEqual({
      projectId: 7,
      name: '项目A',
      requirementCount: 3,
      caseCount: 12,
      qualityScore: null,
      passRate: 80,
    })
    expect(ctx.overviewLoading.value).toBe(false)
  })

  it('子接口失败时按空值兜底', async () => {
    mocks.getIterations.mockRejectedValue(new Error('迭代失败'))
    mocks.getProjectCases.mockRejectedValue(new Error('用例失败'))
    mocks.getTaskList.mockRejectedValue(new Error('任务失败'))
    await mountHost()

    expect(ctx.overview.value).toEqual({
      projectId: 7,
      name: '项目A',
      requirementCount: 0,
      caseCount: 0,
      qualityScore: null,
      passRate: 0,
    })
  })

  it('项目详情失败时告警并保持空概览', async () => {
    mocks.getProjectDetail.mockRejectedValue(new Error('详情失败'))
    await mountHost()

    expect(ctx.overview.value).toBeNull()
    expect(console.warn).toHaveBeenCalled()
    expect(ctx.overviewLoading.value).toBe(false)
  })
})

describe('useWorkbench — 待我评审', () => {
  it('仅保留进行中的评审并限制在 5 条', async () => {
    mocks.getReviewsByIteration.mockResolvedValue({
      data: {
        reviews: Array.from({ length: 8 }, (_, i) => ({
          id: i + 1,
          iteration_id: 11,
          kind: 'case',
          status: 'in_progress',
          created_at: 't',
        })),
      },
    })
    await mountHost()

    expect(ctx.pendingReviews.value).toHaveLength(5)
    expect(ctx.pendingReviews.value[0]).toMatchObject({ reviewId: 1, iterationId: 11 })
    expect(ctx.reviewsLoading.value).toBe(false)
  })

  it('单次评审查询失败时忽略该迭代', async () => {
    mocks.getReviewsByIteration.mockRejectedValueOnce(new Error('失败')).mockResolvedValueOnce({
      data: { reviews: [{ id: 2, iteration_id: 12, kind: 'case', status: 'in_progress' }] },
    })
    await mountHost()

    expect(ctx.pendingReviews.value.map((r) => r.reviewId)).toEqual([2])
  })

  it('迭代接口失败时清空列表', async () => {
    mocks.getIterations.mockRejectedValue(new Error('迭代失败'))
    await mountHost()

    expect(ctx.pendingReviews.value).toEqual([])
    expect(console.warn).toHaveBeenCalled()
  })
})

describe('useWorkbench — 最近任务与成本趋势', () => {
  it('最近任务映射字段', async () => {
    await mountHost()

    expect(mocks.getTaskList).toHaveBeenCalledWith({ project_id: 7, page: 1, page_size: 5 })
    expect(ctx.recentTasks.value[0]).toEqual({
      id: 1,
      taskName: '任务A',
      status: 2,
      successCount: 8,
      failCount: 2,
      totalCount: 10,
      createTime: '2026-11-13T10:00:00',
    })
    expect(ctx.tasksLoading.value).toBe(false)
  })

  it('最近任务失败时清空', async () => {
    mocks.getTaskList.mockRejectedValue(new Error('失败'))
    await mountHost()

    expect(ctx.recentTasks.value).toEqual([])
  })

  it('成本趋势按日期升序并换算人民币', async () => {
    await mountHost()

    expect(ctx.aiCostTrend.value).toEqual([
      { date: '2026-11-11', costCny: 7, calls: 4 },
      { date: '2026-11-12', costCny: 14, calls: 3 },
    ])
    expect(ctx.totalCostCny.value).toBe('21.00')
    expect(ctx.totalCalls.value).toBe(7)
    expect(ctx.costLoading.value).toBe(false)
  })

  it('成本趋势失败时清空', async () => {
    mocks.getStats.mockRejectedValue(new Error('失败'))
    await mountHost()

    expect(ctx.aiCostTrend.value).toEqual([])
  })

  it('空趋势时合计为零', async () => {
    mocks.getStats.mockResolvedValue({ data: { items: [] } })
    await mountHost()

    expect(ctx.totalCostCny.value).toBe('0.00')
    expect(ctx.totalCalls.value).toBe(0)
  })
})

describe('useWorkbench — 图表', () => {
  it('未设置图表容器时不初始化', async () => {
    await mountHost()

    expect(mocks.initChart).not.toHaveBeenCalled()
  })

  it('设置容器后渲染折线图并支持 resize', async () => {
    const wrapper = await mountHost()
    const el = document.createElement('div')

    ctx.setCostChartRef(el)
    mocks.store.currentProjectId = 9
    await flushPromises()
    await flushPromises()

    expect(mocks.initChart).toHaveBeenCalledWith(el)
    expect(mocks.chart.setOption).toHaveBeenCalledWith(
      expect.objectContaining({
        xAxis: expect.objectContaining({ data: ['2026-11-11', '2026-11-12'] }),
      })
    )

    window.dispatchEvent(new Event('resize'))
    expect(mocks.chart.resize).toHaveBeenCalled()

    wrapper.unmount()
    expect(mocks.chart.dispose).toHaveBeenCalled()
  })

  it('非 HTMLElement 的引用被忽略', async () => {
    await mountHost()

    ctx.setCostChartRef(null)
    ctx.setCostChartRef({})

    expect(mocks.initChart).not.toHaveBeenCalled()
  })
})

describe('useWorkbench — 导航', () => {
  it('创建项目与项目列表指向同一路由', async () => {
    await mountHost()

    ctx.goToCreateProject()
    ctx.goToProjectList()

    expect(mocks.push).toHaveBeenNthCalledWith(1, { name: 'ProjectList' })
    expect(mocks.push).toHaveBeenNthCalledWith(2, { name: 'ProjectList' })
  })

  it('有项目时任务列表带项目 ID，无项目时回概览', async () => {
    await mountHost()

    ctx.goToTaskList()
    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/7')

    mocks.store.currentProjectId = 0
    ctx.goToTaskList()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'TaskOverview' })
  })

  it('任务详情、评审收件箱与成本看板', async () => {
    await mountHost()

    ctx.goToTaskDetail(5)
    expect(mocks.push).toHaveBeenCalledWith('/home/task/detail/5?project_id=7')

    ctx.goToReviewInbox(3)
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'IterationReviewInbox',
      params: { reviewId: 3 },
    })

    ctx.goToAICostDashboard()
    expect(mocks.push).toHaveBeenCalledWith({ name: 'AICostDashboard' })
  })
})
