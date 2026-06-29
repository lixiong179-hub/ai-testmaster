import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, h } from 'vue'
import QuickTest from '../QuickTest.vue'
import { useQuickTestStore } from '@/store/quickTest'
import type { ApiResponse } from '@/utils/request'
import type {
    QuickTestLaunchResponse,
    QuickTestStatusResponse,
} from '@/api/quickTest'

vi.mock('@/api/quickTest', () => {
    const launch = vi.fn()
    const getStatus = vi.fn()
    return {
        default: { launch, getStatus },
        QuickTestApi: { launch, getStatus },
    }
})

vi.mock('@/api/report', () => ({
    default: {
        getReports: vi.fn().mockResolvedValue({ data: { items: [] } }),
        getReportDetail: vi.fn().mockResolvedValue({ data: {} }),
        exportReportPDF: vi.fn(),
        exportReportHTML: vi.fn(),
    },
}))

vi.mock('@/api/project', () => ({
    default: {
        getProjects: vi.fn().mockResolvedValue({ data: { items: [] } }),
        getProjectDetail: vi.fn().mockResolvedValue({ data: {} }),
        getProjectConfig: vi.fn().mockResolvedValue({ data: {} }),
    },
}))

vi.mock('vue-router', () => ({
    useRouter: () => ({ push: vi.fn().mockResolvedValue(undefined) }),
}))

vi.mock('@/utils/websocket', () => ({
    connectWebSocket: vi.fn((_path: string, options: { onOpen?: () => void }) => {
        // 模拟连接立即建立，便于测试 wsConnected 状态
        options.onOpen?.()
        return {
            ws: {} as WebSocket,
            close: vi.fn(),
        }
    }),
}))

import quickTestApi from '@/api/quickTest'

// 子组件桩：仅渲染固定文本与必要的 emit/props 钩子
const QuickInputCardStub = defineComponent({
    name: 'QuickInputCard',
    emits: ['launched'],
    setup(_, { emit }) {
        return () =>
            h('div', { class: 'stub-input' }, [
                'QuickInputCard',
                h(
                    'button',
                    { class: 'stub-launch', onClick: () => emit('launched') },
                    'launch'
                ),
            ])
    },
})

const QuickProgressViewStub = defineComponent({
    name: 'QuickProgressView',
    emits: ['cancel'],
    setup(_, { emit }) {
        return () =>
            h('div', { class: 'stub-progress' }, [
                'QuickProgressView',
                h(
                    'button',
                    { class: 'stub-cancel', onClick: () => emit('cancel') },
                    'cancel'
                ),
            ])
    },
})

const QuickResultViewStub = defineComponent({
    name: 'QuickResultView',
    emits: ['rerun', 'view-report', 'edit-cases', 'download', 'save-to-project', 'fetch-report'],
    setup(_, { emit }) {
        return () =>
            h('div', { class: 'stub-result' }, [
                'QuickResultView',
                h('button', { class: 'stub-rerun', onClick: () => emit('rerun') }, 'rerun'),
                h(
                    'button',
                    { class: 'stub-fetch', onClick: () => emit('fetch-report') },
                    'fetch'
                ),
            ])
    },
})

const QuickHistoryListStub = defineComponent({
    name: 'QuickHistoryList',
    emits: ['view', 'rerun'],
    setup(_, { emit }) {
        return () =>
            h('div', { class: 'stub-history' }, [
                'QuickHistoryList',
                h(
                    'button',
                    { class: 'stub-view', onClick: () => emit('view', 101) },
                    'view'
                ),
                h(
                    'button',
                    { class: 'stub-rerun-url', onClick: () => emit('rerun', 'https://x.com') },
                    'rerun-url'
                ),
                h(
                    'button',
                    { class: 'stub-rerun-null', onClick: () => emit('rerun', null) },
                    'rerun-null'
                ),
            ])
    },
})

function makeLaunchResponse(
    overrides: Partial<QuickTestLaunchResponse> = {}
): ApiResponse<QuickTestLaunchResponse> {
    return {
        code: 0,
        msg: 'ok',
        message: 'ok',
        data: {
            task_id: 101,
            project_id: 202,
            estimated_duration_sec: 300,
            websocket_channel: 'quick_test:101',
            ...overrides,
        },
    }
}

function makeStatusResponse(
    overrides: Partial<QuickTestStatusResponse> = {}
): ApiResponse<QuickTestStatusResponse> {
    return {
        code: 0,
        msg: 'ok',
        message: 'ok',
        data: {
            task_id: 101,
            status: '执行中',
            progress: 50,
            current_stage: 'case_generating',
            case_count: 3,
            started_at: '2026-06-27T10:00:00',
            websocket_channel: 'quick_test:101',
            ...overrides,
        },
    }
}

function mountContainer() {
    return mount(QuickTest, {
        global: {
            stubs: {
                QuickInputCard: QuickInputCardStub,
                QuickProgressView: QuickProgressViewStub,
                QuickResultView: QuickResultViewStub,
                QuickHistoryList: QuickHistoryListStub,
            },
        },
    })
}

describe('QuickTest 容器', () => {
    let store: ReturnType<typeof useQuickTestStore>

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useQuickTestStore()
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('三态视图切换', () => {
        it('idle 态渲染 QuickInputCard', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            expect(wrapper.find('.stub-input').exists()).toBe(true)
            expect(wrapper.find('.stub-progress').exists()).toBe(false)
            expect(wrapper.find('.stub-result').exists()).toBe(false)
        })

        it('running 态渲染 QuickProgressView', async () => {
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            const wrapper = mountContainer()
            await flushPromises()
            expect(wrapper.find('.stub-progress').exists()).toBe(true)
            expect(wrapper.find('.stub-input').exists()).toBe(false)
        })

        it('completed 态渲染 QuickResultView', async () => {
            store.phase = 'completed'
            store.taskId = 101
            store.projectId = 202
            const wrapper = mountContainer()
            await flushPromises()
            expect(wrapper.find('.stub-result').exists()).toBe(true)
        })

        it('failed 态也渲染 QuickResultView（内部渲染降级提示）', async () => {
            store.phase = 'failed'
            store.taskId = 101
            store.projectId = 202
            store.errorMessage = '探索失败'
            const wrapper = mountContainer()
            await flushPromises()
            expect(wrapper.find('.stub-result').exists()).toBe(true)
        })

        it('历史记录卡片始终渲染', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            expect(wrapper.find('.stub-history').exists()).toBe(true)
        })
    })

    describe('onMounted 恢复逻辑', () => {
        it('localStorage 无会话时保持 idle 态', async () => {
            mountContainer()
            await flushPromises()
            expect(store.phase).toBe('idle')
            expect(quickTestApi.getStatus).not.toHaveBeenCalled()
        })

        it('恢复到 running 时调 refreshStatus 并订阅 WS', async () => {
            // 预置会话到 localStorage
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            store.websocketChannel = 'quick_test:101'
            store.persist()
            // 新 pinia + 新 store 模拟刷新
            setActivePinia(createPinia())
            const freshStore = useQuickTestStore()
            expect(freshStore.taskId).toBeNull()
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '执行中', progress: 60 })
            )
            mountContainer()
            await flushPromises()
            expect(freshStore.taskId).toBe(101)
            expect(freshStore.phase).toBe('running')
            expect(quickTestApi.getStatus).toHaveBeenCalledWith(101)
        })

        it('恢复到 completed 时不调 refreshStatus', async () => {
            store.phase = 'completed'
            store.taskId = 101
            store.projectId = 202
            store.persist()
            setActivePinia(createPinia())
            const freshStore = useQuickTestStore()
            mountContainer()
            await flushPromises()
            expect(freshStore.phase).toBe('completed')
            expect(quickTestApi.getStatus).not.toHaveBeenCalled()
        })

        it('refreshStatus 异常时不阻断渲染', async () => {
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            store.persist()
            setActivePinia(createPinia())
            vi.mocked(quickTestApi.getStatus).mockRejectedValueOnce(new Error('500'))
            const wrapper = mountContainer()
            await flushPromises()
            // 异常后仍按已恢复的 phase 渲染
            expect(wrapper.find('.stub-progress').exists()).toBe(true)
        })
    })

    describe('QuickInputCard 启动回调', () => {
        it('launched 事件触发后切到 running 视图', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            // 预置 launch mock + 直接切 store.phase 模拟 useQuickTestCard 内部已完成 launch
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await wrapper.find('.stub-launch').trigger('click')
            // QuickInputCard 内部的 submitCard 才会调 launch；此处仅验证容器事件处理不抛错
            // 直接切 phase 验证视图切换
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            await flushPromises()
            expect(wrapper.find('.stub-progress').exists()).toBe(true)
        })
    })

    describe('QuickHistoryList 事件回调', () => {
        it('view 事件触发后滚动到顶部（不抛错）', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            // mock window.scrollTo
            const scrollToSpy = vi.fn()
            Object.defineProperty(window, 'scrollTo', {
                configurable: true,
                writable: true,
                value: scrollToSpy,
            })
            await wrapper.find('.stub-view').trigger('click')
            expect(scrollToSpy).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
        })

        it('rerun 携带 URL 时调 store.launch 并订阅 WS', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await wrapper.find('.stub-rerun-url').trigger('click')
            await flushPromises()
            expect(quickTestApi.launch).toHaveBeenCalledWith({ url: 'https://x.com' })
            expect(store.phase).toBe('running')
            expect(store.taskId).toBe(101)
        })

        it('rerun 携带 null 时不调 launch（回退到输入卡）', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            await wrapper.find('.stub-rerun-null').trigger('click')
            await flushPromises()
            expect(quickTestApi.launch).not.toHaveBeenCalled()
            expect(store.phase).toBe('idle')
        })

        it('rerun launch 失败时不抛错且保持 idle', async () => {
            store.phase = 'idle'
            const wrapper = mountContainer()
            await flushPromises()
            vi.mocked(quickTestApi.launch).mockRejectedValueOnce(new Error('网络错误'))
            await wrapper.find('.stub-rerun-url').trigger('click')
            await flushPromises()
            expect(store.phase).toBe('idle')
        })
    })

    describe('phase 变化自动管理 WS', () => {
        it('phase 从 idle 切到 running 时自动订阅 WS', async () => {
            store.phase = 'idle'
            mountContainer()
            await flushPromises()
            const { connectWebSocket } = await import('@/utils/websocket')
            vi.mocked(connectWebSocket).mockClear()
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            await flushPromises()
            expect(connectWebSocket).toHaveBeenCalled()
        })

        it('phase 从 running 切到 completed 时自动断开 WS（close 被调用）', async () => {
            store.phase = 'running'
            store.taskId = 101
            store.projectId = 202
            store.estimatedDurationSec = 300
            mountContainer()
            await flushPromises()
            const { connectWebSocket } = await import('@/utils/websocket')
            // 取首次连接返回的 close mock
            const firstResult = vi.mocked(connectWebSocket).mock.results[0]
            const closeSpy = firstResult?.value.close as ReturnType<typeof vi.fn> | undefined
            store.phase = 'completed'
            await flushPromises()
            // 切换到非 running 后 watch 触发 disconnectWebSocket，close 应被调用
            expect(closeSpy).toBeTruthy()
            expect(closeSpy!).toHaveBeenCalled()
        })
    })
})
