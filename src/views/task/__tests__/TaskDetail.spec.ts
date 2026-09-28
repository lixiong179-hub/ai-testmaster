import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import TaskDetail from '../TaskDetail.vue'
import { useTaskStore } from '@/store/task'
import { TaskStatus } from '@/api/testTask'
import type { TestTask } from '@/store/taskTypes'

// vi.mock 工厂会被提升到文件顶部，需用 vi.hoisted 确保 pushMock 先于 mock 初始化
const { pushMock } = vi.hoisted(() => ({
    pushMock: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('vue-router', () => ({
    useRoute: () => ({
        params: { taskId: '101' },
        query: { project_id: '202' },
    }),
    useRouter: () => ({ push: pushMock }),
    // 依赖链 store -> request -> router 需要 createRouter/createWebHistory
    createRouter: vi.fn(() => ({
        beforeEach: vi.fn(),
        afterEach: vi.fn(),
        onError: vi.fn(),
        currentRoute: { value: { path: '/', fullPath: '/' } },
        push: pushMock,
    })),
    createWebHistory: vi.fn(),
}))

vi.mock('@/router', () => ({
    default: {
        push: pushMock,
        currentRoute: { value: { path: '/', fullPath: '/' } },
    },
}))

vi.mock('@/utils/websocket', () => ({
    wsClient: {
        connect: vi.fn(),
        disconnect: vi.fn(),
        onMessage: vi.fn(),
        offMessage: vi.fn(),
    },
}))

vi.mock('@/api/testExecution', () => ({
    getConnectedDevices: vi.fn().mockResolvedValue({
        data: { code: 200, data: [] },
    }),
}))

// mock ElMessageBox/ElMessage 服务，避免测试中弹出真实弹窗
vi.mock('element-plus', () => ({
    ElMessage: {
        success: vi.fn(),
        warning: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
    },
    ElMessageBox: {
        confirm: vi.fn().mockResolvedValue('confirm'),
    },
}))

// 桩：TaskResultsPanel 子组件，避免渲染其内部依赖
const TaskResultsPanelStub = defineComponent({
    name: 'TaskResultsPanel',
    setup() {
        return () => h('div', { class: 'stub-results' }, 'TaskResultsPanel')
    },
})

function makeTaskDetail(overrides: Partial<TestTask> = {}): TestTask {
    return {
        id: 101,
        task_name: '测试任务',
        project_id: 202,
        case_ids: [],
        executor_id: 1,
        status: TaskStatus.COMPLETED,
        success_count: 8,
        fail_count: 2,
        total_count: 10,
        progress: 100,
        create_time: '2026-07-30T10:00:00',
        ...overrides,
    }
}

function mountTaskDetail() {
    return mount(TaskDetail, {
        global: {
            stubs: {
                TaskResultsPanel: TaskResultsPanelStub,
            },
        },
    })
}

describe('TaskDetail 报告跳转（Task 5）', () => {
    let store: ReturnType<typeof useTaskStore>
    let wrapper: VueWrapper | null

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useTaskStore()
        // onMounted 会调 fetchTaskDetail/fetchTaskResults，mock 避免覆盖预设 taskDetail
        // fetchTaskDetail 返回 TestTask|null，fetchTaskResults 返回 TestResult[]
        vi.spyOn(store, 'fetchTaskDetail').mockResolvedValue(null as never)
        vi.spyOn(store, 'fetchTaskResults').mockResolvedValue([] as never)
        vi.spyOn(store, 'clearExecutionLogs').mockImplementation(() => {})
        wrapper = null
    })

    afterEach(() => {
        // unmount 触发 onUnmounted -> cleanup -> stopPolling，避免轮询残留
        wrapper?.unmount()
        wrapper = null
        vi.restoreAllMocks()
    })

    describe('COMPLETED 完成', () => {
        it('显示"查看测试报告"主按钮（primary + large）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.COMPLETED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.report-entry .el-button--primary')
            expect(btn.exists()).toBe(true)
            expect(btn.text()).toContain('查看测试报告')
            expect(btn.classes()).toContain('el-button--large')
        })

        it('点击跳转携带 task_id', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.COMPLETED })
            wrapper = mountTaskDetail()
            await flushPromises()
            await wrapper.find('.report-entry .el-button--primary').trigger('click')
            expect(pushMock).toHaveBeenCalledWith({
                name: 'ExecutionReportDetail',
                query: { task_id: '101' },
            })
        })
    })

    describe('FAILED 失败', () => {
        it('显示"查看失败报告"按钮（danger）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.FAILED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.report-entry .el-button--danger')
            expect(btn.exists()).toBe(true)
            expect(btn.text()).toContain('查看失败报告')
        })

        it('点击跳转携带 task_id 与 status=failed', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.FAILED })
            wrapper = mountTaskDetail()
            await flushPromises()
            await wrapper.find('.report-entry .el-button--danger').trigger('click')
            expect(pushMock).toHaveBeenCalledWith({
                name: 'ExecutionReportDetail',
                query: { task_id: '101', status: 'failed' },
            })
        })
    })

    describe('STOPPED 已停止', () => {
        it('显示"已停止"提示文案', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.STOPPED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const entry = wrapper.find('.report-entry')
            expect(entry.exists()).toBe(true)
            expect(entry.text()).toContain('已停止')
            // STOPPED 不渲染跳转按钮
            expect(entry.find('button').exists()).toBe(false)
        })
    })

    describe('非终态不显示报告入口', () => {
        it('WAITING 状态不显示 report-entry', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.WAITING })
            wrapper = mountTaskDetail()
            await flushPromises()
            expect(wrapper.find('.report-entry').exists()).toBe(false)
        })

        it('RUNNING 状态不显示 report-entry', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.RUNNING })
            wrapper = mountTaskDetail()
            await flushPromises()
            expect(wrapper.find('.report-entry').exists()).toBe(false)
        })
    })
})

describe('TaskDetail 重试入口（P1 E-01）', () => {
    let store: ReturnType<typeof useTaskStore>
    let wrapper: VueWrapper | null

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useTaskStore()
        vi.spyOn(store, 'fetchTaskDetail').mockResolvedValue(null as never)
        vi.spyOn(store, 'fetchTaskResults').mockResolvedValue([] as never)
        vi.spyOn(store, 'clearExecutionLogs').mockImplementation(() => {})
        vi.spyOn(store, 'startTask').mockResolvedValue({} as never)
        wrapper = null
    })

    afterEach(() => {
        wrapper?.unmount()
        wrapper = null
        vi.restoreAllMocks()
    })

    describe('FAILED 失败', () => {
        it('显示"重试任务"按钮（primary）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.FAILED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.action-buttons .el-button--primary')
            expect(btn.exists()).toBe(true)
            expect(btn.text()).toContain('重试任务')
        })

        it('点击重试调用 startTask 并清空日志', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.FAILED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.action-buttons .el-button--primary')
            await btn.trigger('click')
            await flushPromises()
            expect(store.clearExecutionLogs).toHaveBeenCalled()
            expect(store.startTask).toHaveBeenCalledWith(
                101,
                202,
                'smart',
                undefined
            )
        })
    })

    describe('STOPPED 已停止', () => {
        it('显示"重试任务"按钮（primary）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.STOPPED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.action-buttons .el-button--primary')
            expect(btn.exists()).toBe(true)
            expect(btn.text()).toContain('重试任务')
        })
    })

    describe('不可重试状态', () => {
        it('WAITING 状态不显示重试按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.WAITING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons .el-button--primary')
            const retryBtn = btns.find((b) => b.text().includes('重试任务'))
            expect(retryBtn).toBeUndefined()
        })

        it('RUNNING 状态不显示重试按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.RUNNING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons .el-button--primary')
            const retryBtn = btns.find((b) => b.text().includes('重试任务'))
            expect(retryBtn).toBeUndefined()
        })

        it('COMPLETED 状态不显示重试按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.COMPLETED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons .el-button--primary')
            const retryBtn = btns.find((b) => b.text().includes('重试任务'))
            expect(retryBtn).toBeUndefined()
        })
    })

    describe('重试取消', () => {
        it('用户取消确认时不调用 startTask', async () => {
            const { ElMessageBox } = await import('element-plus')
            vi.mocked(ElMessageBox.confirm).mockRejectedValueOnce('cancel')
            store.taskDetail = makeTaskDetail({ status: TaskStatus.FAILED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btn = wrapper.find('.action-buttons .el-button--primary')
            await btn.trigger('click')
            await flushPromises()
            expect(store.startTask).not.toHaveBeenCalled()
        })
    })
})

describe('TaskDetail 暂停/恢复入口（P1 E-04）', () => {
    let store: ReturnType<typeof useTaskStore>
    let wrapper: VueWrapper | null

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useTaskStore()
        vi.spyOn(store, 'fetchTaskDetail').mockResolvedValue(null as never)
        vi.spyOn(store, 'fetchTaskResults').mockResolvedValue([] as never)
        vi.spyOn(store, 'pauseTask').mockResolvedValue({} as never)
        vi.spyOn(store, 'resumeTask').mockResolvedValue({} as never)
        wrapper = null
    })

    afterEach(() => {
        wrapper?.unmount()
        wrapper = null
        vi.restoreAllMocks()
    })

    describe('RUNNING 状态显示暂停按钮', () => {
        it('显示"暂停任务"按钮（info）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.RUNNING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const pauseBtn = btns.find((b) => b.text().includes('暂停任务'))
            expect(pauseBtn).toBeDefined()
            expect(pauseBtn?.classes()).toContain('el-button--info')
        })

        it('点击暂停调用 pauseTask', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.RUNNING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const pauseBtn = btns.find((b) => b.text().includes('暂停任务'))
            await pauseBtn?.trigger('click')
            await flushPromises()
            expect(store.pauseTask).toHaveBeenCalledWith(101, 202)
        })
    })

    describe('PAUSED 状态显示恢复按钮', () => {
        it('显示"恢复任务"按钮（success）', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.PAUSED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const resumeBtn = btns.find((b) => b.text().includes('恢复任务'))
            expect(resumeBtn).toBeDefined()
            expect(resumeBtn?.classes()).toContain('el-button--success')
        })

        it('点击恢复调用 resumeTask', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.PAUSED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const resumeBtn = btns.find((b) => b.text().includes('恢复任务'))
            await resumeBtn?.trigger('click')
            await flushPromises()
            expect(store.resumeTask).toHaveBeenCalledWith(101, 202)
        })
    })

    describe('非 RUNNING 状态不显示暂停按钮', () => {
        it('WAITING 状态不显示暂停按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.WAITING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const pauseBtn = btns.find((b) => b.text().includes('暂停任务'))
            expect(pauseBtn).toBeUndefined()
        })

        it('COMPLETED 状态不显示暂停按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.COMPLETED })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const pauseBtn = btns.find((b) => b.text().includes('暂停任务'))
            expect(pauseBtn).toBeUndefined()
        })
    })

    describe('非 PAUSED 状态不显示恢复按钮', () => {
        it('RUNNING 状态不显示恢复按钮', async () => {
            store.taskDetail = makeTaskDetail({ status: TaskStatus.RUNNING })
            wrapper = mountTaskDetail()
            await flushPromises()
            const btns = wrapper.findAll('.action-buttons button')
            const resumeBtn = btns.find((b) => b.text().includes('恢复任务'))
            expect(resumeBtn).toBeUndefined()
        })
    })
})
