import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import Workbench from '../workbench/Workbench.vue'
import { useProjectStore } from '@/store/project'

// ==================== Mock 准备（hoisted 保证 vi.mock 工厂可用） ====================
const {
    mockPush,
    getProjectListMock,
    getProjectDetailMock,
    getIterationsMock,
    getReviewsMock,
    getTaskListMock,
    getProjectCasesMock,
    getStatsMock,
} = vi.hoisted(() => ({
    mockPush: vi.fn().mockResolvedValue(undefined),
    getProjectListMock: vi.fn(),
    getProjectDetailMock: vi.fn(),
    getIterationsMock: vi.fn(),
    getReviewsMock: vi.fn(),
    getTaskListMock: vi.fn(),
    getProjectCasesMock: vi.fn(),
    getStatsMock: vi.fn(),
}))

// Mock echarts，避免按需引入的重量级模块与 DOM 操作
vi.mock('@/utils/echarts', () => {
    const instance = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    const echartsMock = {
        init: vi.fn(() => instance),
        graphic: { LinearGradient: vi.fn() },
    }
    return { echarts: echartsMock, default: echartsMock }
})

vi.mock('vue-router', () => ({
    useRouter: () => ({ push: mockPush }),
    useRoute: () => ({ query: {} }),
    createRouter: vi.fn(() => ({ push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn() })),
    createWebHistory: vi.fn(),
}))

// Mock @/router：避免 request.ts 加载真实 router 实例（含 beforeEach/onError 等副作用）
vi.mock('@/router', () => ({
    default: { push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn(), onError: vi.fn() },
}))

vi.mock('element-plus', () => ({
    ElMessage: { error: vi.fn(), success: vi.fn(), warning: vi.fn(), info: vi.fn() },
}))

vi.mock('@/api/project', () => {
    const api = {
        getProjectList: getProjectListMock,
        getProjects: getProjectListMock,
        getProjectDetail: getProjectDetailMock,
        createProject: vi.fn(),
        deleteProject: vi.fn(),
        getProjectConfig: vi.fn(),
        updateProjectConfig: vi.fn(),
    }
    return { default: api, ProjectAPI: api }
})

vi.mock('@/api/file', () => ({
    FileAPI: { uploadFile: vi.fn(), submitUrl: vi.fn(), deleteFile: vi.fn() },
    default: { uploadFile: vi.fn(), submitUrl: vi.fn(), deleteFile: vi.fn() },
}))

vi.mock('@/api/iteration', () => {
    const api = { getIterations: getIterationsMock }
    return { iterationApi: api, IterationAPI: api, default: api }
})

vi.mock('@/api/review', () => {
    const api = { getReviewsByIteration: getReviewsMock }
    return { reviewApi: api, default: api }
})

vi.mock('@/api/testTask', () => ({
    default: { getTaskList: getTaskListMock, getProjectCases: getProjectCasesMock },
    TaskStatus: { WAITING: 0, RUNNING: 1, COMPLETED: 2, FAILED: 3, STOPPED: 4 },
    ExecutionStatus: { PENDING: 0, PASSED: 1, FAILED: 2, BLOCKED: 3 },
}))

vi.mock('@/api/aiInvocation', () => ({
    aiInvocationApi: { getStats: getStatsMock },
    usdToCny: (usd: number) => Number((usd * 7.25).toFixed(4)),
    default: { getStats: getStatsMock },
}))

// ==================== 测试数据工厂 ====================
function makeProject(overrides: Record<string, unknown> = {}) {
    return {
        id: 1,
        name: '项目A',
        project_type: 'web',
        status: 1,
        create_time: '',
        update_time: '',
        files: [],
        ...overrides,
    }
}

function makeTask(overrides: Record<string, unknown> = {}) {
    return {
        id: 101,
        task_name: '任务A',
        project_id: 1,
        case_ids: [],
        executor_id: 1,
        status: 2,
        success_count: 8,
        fail_count: 2,
        total_count: 10,
        progress: 100,
        create_time: '2026-07-30 10:00:00',
        ...overrides,
    }
}

function defaultApiResponses() {
    getProjectListMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: { items: [makeProject()], total: 1, page: 1, page_size: 10 },
    })
    getProjectDetailMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: makeProject(),
    })
    getIterationsMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: {
            items: [
                {
                    id: 10,
                    project_id: 1,
                    name: '迭代1',
                    version: 'v1',
                    status: 'in_review',
                    create_time: '',
                    update_time: '',
                },
            ],
            total: 3,
            page: 1,
            page_size: 50,
        },
    })
    getReviewsMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: {
            reviews: [
                {
                    id: 55,
                    iteration_id: 10,
                    kind: 'case',
                    status: 'in_progress',
                    created_at: '2026-07-30T09:00:00',
                    finalized_at: null,
                },
            ],
            total: 1,
        },
    })
    getTaskListMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: { items: [makeTask()], total: 1, page: 1, page_size: 5 },
    })
    getProjectCasesMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: { items: [], total: 5, page: 1, page_size: 1 },
    })
    getStatsMock.mockResolvedValue({
        code: 200,
        message: 'ok',
        data: {
            items: [
                {
                    group_key: '2026-07-30',
                    total_calls: 12,
                    total_prompt_tokens: 1000,
                    total_completion_tokens: 500,
                    total_cost_usd: 0.5,
                },
            ],
        },
    })
}

function findButtonByText(wrapper: ReturnType<typeof mount>, text: string) {
    return wrapper.findAll('button').find((b) => b.text().includes(text))
}

function mountWorkbench() {
    return mount(Workbench)
}

describe('Workbench 工作台首页', () => {
    let store: ReturnType<typeof useProjectStore>

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useProjectStore()
        defaultApiResponses()
        // 默认预置当前项目上下文，跳过自动继承首个项目的分支
        store.setCurrentProject(1)
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('四区块渲染', () => {
        it('渲染当前项目、待我评审、最近任务、AI 成本趋势四个区块标题', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const text = wrapper.text()
            expect(text).toContain('当前项目')
            expect(text).toContain('待我评审')
            expect(text).toContain('最近任务')
            expect(text).toContain('AI 成本趋势')
        })

        it('项目概览展示项目名与四项指标（需求数/用例数/质量分/通过率）', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const text = wrapper.text()
            expect(text).toContain('项目A')
            expect(text).toContain('需求数')
            expect(text).toContain('用例数')
            expect(text).toContain('质量分')
            expect(text).toContain('通过率')
            // 需求数取迭代总数=3；用例数=5；通过率=8/10=80%；质量分暂未采集显示 —
            expect(text).toContain('3')
            expect(text).toContain('5')
            expect(text).toContain('80%')
            expect(text).toContain('—')
        })

        it('待我评审列表渲染待评审项并展示评审类型', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const text = wrapper.text()
            expect(text).toContain('用例评审 #55')
            expect(text).toContain('迭代 10')
            expect(text).toContain('待评审')
        })

        it('最近任务列表渲染任务名与状态', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const text = wrapper.text()
            expect(text).toContain('任务A')
            expect(text).toContain('执行完成')
        })

        it('AI 成本趋势渲染图表容器与合计汇总', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            expect(wrapper.find('.wb-chart').exists()).toBe(true)
            const text = wrapper.text()
            // 0.5 USD → 3.625 CNY → toFixed(2) = 3.63
            expect(text).toContain('7天合计：3.63 元')
            expect(text).toContain('调用 12 次')
        })
    })

    describe('点击跳转', () => {
        it('点击待评审项跳转评审 Inbox（携带 reviewId）', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const item = wrapper.find('.wb-reviews .wb-list-item')
            expect(item.exists()).toBe(true)
            await item.trigger('click')

            expect(mockPush).toHaveBeenCalledWith({
                name: 'IterationReviewInbox',
                params: { reviewId: 55 },
            })
        })

        it('点击"查看全部"跳转评审 Inbox（reviewId=0）', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const btn = findButtonByText(wrapper, '查看全部')
            expect(btn).toBeTruthy()
            await btn!.trigger('click')

            expect(mockPush).toHaveBeenCalledWith({
                name: 'IterationReviewInbox',
                params: { reviewId: 0 },
            })
        })

        it('点击最近任务项跳转任务详情', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const item = wrapper.find('.wb-tasks .wb-list-item')
            expect(item.exists()).toBe(true)
            await item.trigger('click')

            expect(mockPush).toHaveBeenCalledWith(
                '/home/task/detail/101?project_id=1'
            )
        })

        it('点击"任务列表"跳转该项目任务列表', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const btn = findButtonByText(wrapper, '任务列表')
            expect(btn).toBeTruthy()
            await btn!.trigger('click')

            expect(mockPush).toHaveBeenCalledWith('/home/task/list/1')
        })

        it('点击"成本看板"跳转 AI 成本仪表盘', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const btn = findButtonByText(wrapper, '成本看板')
            expect(btn).toBeTruthy()
            await btn!.trigger('click')

            expect(mockPush).toHaveBeenCalledWith({ name: 'AICostDashboard' })
        })

        it('点击"项目中心"跳转项目列表', async () => {
            const wrapper = mountWorkbench()
            await flushPromises()

            const btn = findButtonByText(wrapper, '项目中心')
            expect(btn).toBeTruthy()
            await btn!.trigger('click')

            expect(mockPush).toHaveBeenCalledWith({ name: 'ProjectList' })
        })
    })

    describe('无项目引导', () => {
        it('currentProjectId 为空且无项目时显示"创建项目"引导', async () => {
            // 清空项目上下文与项目列表
            store.setCurrentProject(null)
            getProjectListMock.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: { items: [], total: 0, page: 1, page_size: 10 },
            })

            const wrapper = mountWorkbench()
            await flushPromises()

            const text = wrapper.text()
            expect(text).toContain('还没有项目')
            expect(text).toContain('创建项目')
            // 其他区块显示"请先选择项目"空状态
            expect(text).toContain('请先选择项目')
        })

        it('点击"创建项目"跳转项目中心', async () => {
            store.setCurrentProject(null)
            getProjectListMock.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: { items: [], total: 0, page: 1, page_size: 10 },
            })

            const wrapper = mountWorkbench()
            await flushPromises()

            const btn = wrapper.findAll('button').find((b) => b.text().trim() === '创建项目')
            expect(btn).toBeTruthy()
            await btn!.trigger('click')

            expect(mockPush).toHaveBeenCalledWith({ name: 'ProjectList' })
        })

        it('无项目时不发起区块数据请求', async () => {
            store.setCurrentProject(null)
            getProjectListMock.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: { items: [], total: 0, page: 1, page_size: 10 },
            })

            mountWorkbench()
            await flushPromises()

            // 无项目时 fetchAll 直接返回，不应触发区块数据请求
            expect(getProjectDetailMock).not.toHaveBeenCalled()
            expect(getTaskListMock).not.toHaveBeenCalled()
            expect(getReviewsMock).not.toHaveBeenCalled()
            expect(getStatsMock).not.toHaveBeenCalled()
        })
    })

    describe('骨架屏加载', () => {
        it('项目概览加载中显示骨架屏', async () => {
            // 项目详情接口挂起，overviewLoading 保持 true
            getProjectDetailMock.mockReturnValue(new Promise(() => {}))

            const wrapper = mountWorkbench()
            await flushPromises()

            // 骨架屏渲染（el-skeleton 产物）
            expect(wrapper.find('.wb-guide').exists()).toBe(false)
            expect(wrapper.findAll('.el-skeleton').length).toBeGreaterThan(0)
        })
    })

    describe('自动继承首个项目', () => {
        it('currentProjectId 为空但存在项目时自动继承首个项目并加载数据', async () => {
            store.setCurrentProject(null)
            getProjectListMock.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: {
                    items: [makeProject({ id: 7, name: '继承项目' })],
                    total: 1,
                    page: 1,
                    page_size: 10,
                },
            })
            getProjectDetailMock.mockResolvedValue({
                code: 200,
                message: 'ok',
                data: makeProject({ id: 7, name: '继承项目' }),
            })

            const wrapper = mountWorkbench()
            await flushPromises()

            // 自动继承后 currentProjectId=7，并按 7 发起详情请求
            expect(store.currentProjectId).toBe(7)
            expect(getProjectDetailMock).toHaveBeenCalledWith(7)
            const text = wrapper.text()
            expect(text).toContain('继承项目')
        })
    })
})
