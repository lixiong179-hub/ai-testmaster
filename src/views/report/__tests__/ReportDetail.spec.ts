import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ReportDetail from '../ReportDetail.vue'
import { useReportStore } from '@/store/report'
import type { Report } from '@/api/report'
import type { BugItem } from '@/api/bug'

// ==================== Mock 准备（hoisted 保证 vi.mock 工厂可用） ====================

const { mockRoute, mockPush, getBugListMock, getReportDetailMock } = vi.hoisted(() => ({
    // 路由参数：报告列表跳转时携带 id / project_id / task_id。
    // query 用 Record<string, string> 以便用例动态增删键（如移除 task_id 验证降级）。
    mockRoute: {
        query: { id: '1', project_id: '1', task_id: '100' } as Record<string, string>,
    },
    mockPush: vi.fn().mockResolvedValue(undefined),
    // 缺陷列表 API mock：默认空列表，各用例可覆写返回值
    getBugListMock: vi.fn(),
    // 报告详情 API mock：由 store 写入 currentReport
    getReportDetailMock: vi.fn(),
}))

// Mock echarts，避免按需引入的重量级模块与 DOM 操作
vi.mock('@/utils/echarts', () => {
    const instance = {
        setOption: vi.fn(),
        resize: vi.fn(),
        dispose: vi.fn(),
    }
    const echartsMock = {
        init: vi.fn(() => instance),
        graphic: { LinearGradient: vi.fn() },
    }
    return { echarts: echartsMock, default: echartsMock }
})

vi.mock('vue-router', () => ({
    useRoute: () => mockRoute,
    useRouter: () => ({ push: mockPush }),
    // request.ts → @/router 会调用 createRouter/createWebHistory，需一并提供
    createRouter: vi.fn(() => ({ push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn() })),
    createWebHistory: vi.fn(),
}))

// Mock @/router：避免 request.ts 加载真实 router 实例（含 beforeEach/onError 等副作用）
vi.mock('@/router', () => ({
    default: { push: mockPush, beforeEach: vi.fn(), afterEach: vi.fn(), onError: vi.fn() },
}))

vi.mock('@/api/bug', () => ({
    default: { getBugList: getBugListMock },
}))

vi.mock('@/api/report', () => ({
    default: {
        getReports: vi.fn(),
        getReportDetail: getReportDetailMock,
        deleteReport: vi.fn(),
        exportReportPDF: vi.fn(),
        exportReportHTML: vi.fn(),
    },
}))

// 项目 API（BugList 嵌入式不调用，此处兜底避免真实请求）
vi.mock('@/api/project', () => ({
    default: {
        getProjects: vi.fn().mockResolvedValue({ data: { items: [] } }),
    },
}))

// ==================== 测试数据工厂 ====================

function makeReport(overrides: Partial<Report> = {}): Report {
    return {
        id: 1,
        project_id: 1,
        test_task_id: 100,
        name: '测试报告',
        status: 'completed',
        total_cases: 10,
        passed_cases: 8,
        failed_cases: 2,
        blocked_cases: 0,
        pass_rate: 80,
        create_time: '2026-07-30 10:00:00',
        ...overrides,
    } as Report
}

function makeBugItem(overrides: Partial<BugItem> = {}): BugItem {
    return {
        id: 1,
        bug_no: 'BUG-001',
        title: '示例缺陷',
        severity: 2,
        priority: 2,
        status: 'open',
        source: 'self_test',
        ux_category: null,
        reporter_id: 1,
        assignee_id: null,
        test_case_id: null,
        test_result_id: null,
        create_time: '2026-07-30 10:05:00',
        update_time: null,
        ...overrides,
    }
}

function mountReport(report: Report) {
    // 预置 store 状态：currentReport 已加载，跳过骨架屏
    const store = useReportStore()
    store.currentReport = report
    // 挂载时 fetchReportDetail 会调用接口并写入 currentReport，
    // 故让接口返回同一 report，避免覆盖测试预期状态（如 test_task_id=0）
    getReportDetailMock.mockResolvedValue({ data: report })
    return mount(ReportDetail, {
        global: {
            stubs: {
                // 桩掉用例表格，避免其内部复杂依赖干扰本测试焦点
                ReportTable: { template: '<div class="report-table-stub" />' },
            },
        },
    })
}

describe('ReportDetail 关联缺陷 Tab', () => {
    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        // 默认：报告详情接口返回空对象（store 已预置 currentReport，不会被覆盖为有意义数据，
        // 但 fetchReportDetail 仍会调用并写入 currentReport，故让接口返回同一报告）
        getReportDetailMock.mockResolvedValue({ data: makeReport() })
        getBugListMock.mockResolvedValue({ data: { items: [], total: 0 } })
        setActivePinia(createPinia())
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('渲染"报告详情"与"关联缺陷"两个 Tab', async () => {
        const wrapper = mountReport(makeReport())
        await flushPromises()

        const tabLabels = wrapper.findAll('.el-tabs__item').map((n) => n.text())
        expect(tabLabels).toContain('报告详情')
        expect(tabLabels).toContain('关联缺陷')
    })

    it('默认激活"报告详情"Tab', async () => {
        const wrapper = mountReport(makeReport())
        await flushPromises()

        const activeTab = wrapper.find('.el-tabs__item.is-active')
        expect(activeTab.exists()).toBe(true)
        expect(activeTab.text()).toContain('报告详情')
    })

    it('关联缺陷 Tab 按 task_id 筛选缺陷（传入 task_id=100）', async () => {
        mountReport(makeReport())
        await flushPromises()

        expect(getBugListMock).toHaveBeenCalled()
        const callArg = getBugListMock.mock.calls[0][0] as {
            project_id: number
            task_id?: number
        }
        expect(callArg.project_id).toBe(1)
        expect(callArg.task_id).toBe(100)
    })

    it('无关联缺陷时显示空状态"本次执行未发现缺陷"与"手动提缺陷"入口', async () => {
        const wrapper = mountReport(makeReport())
        await flushPromises()

        const text = wrapper.text()
        expect(text).toContain('本次执行未发现缺陷')
        // 空状态操作入口存在
        const btnTexts = wrapper.findAll('button').map((b) => b.text())
        expect(btnTexts).toContain('手动提缺陷')
    })

    it('点击"手动提缺陷"跳转到缺陷管理页并携带 project_id', async () => {
        const wrapper = mountReport(makeReport())
        await flushPromises()

        const btn = wrapper.findAll('button').find((b) => b.text() === '手动提缺陷')
        expect(btn).toBeTruthy()
        await btn!.trigger('click')

        expect(mockPush).toHaveBeenCalledWith({
            path: '/home/execution/bug',
            query: { project_id: 1 },
        })
    })

    it('有关联缺陷时渲染缺陷表格（展示 bug_no）', async () => {
        getBugListMock.mockResolvedValue({
            data: { items: [makeBugItem({ bug_no: 'BUG-REL-001' })], total: 1 },
        })
        const wrapper = mountReport(makeReport())
        await flushPromises()

        const text = wrapper.text()
        expect(text).toContain('BUG-REL-001')
    })

    it('报告未携带 task_id 时，关联缺陷 Tab 降级为空状态并保留手动入口', async () => {
        // 报告无 test_task_id，且路由无 task_id
        const report = makeReport({ test_task_id: 0 })
        mockRoute.query = { id: '1', project_id: '1' }
        const wrapper = mountReport(report)
        await flushPromises()

        // 缺陷列表接口不应被调用（BugList 因 taskId 为 0 不渲染）
        expect(getBugListMock).not.toHaveBeenCalled()
        const text = wrapper.text()
        expect(text).toContain('当前报告未关联任务，无法展示缺陷')
        const btnTexts = wrapper.findAll('button').map((b) => b.text())
        expect(btnTexts).toContain('手动提缺陷')

        // 恢复路由 mock，避免影响后续用例
        mockRoute.query = { id: '1', project_id: '1', task_id: '100' }
    })
})
