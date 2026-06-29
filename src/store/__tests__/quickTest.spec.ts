import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
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

import quickTestApi from '@/api/quickTest'
import { useQuickTestStore, clearQuickTestSession } from '../quickTest'

const SESSION_KEY = 'quickTestSession'

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

describe('quickTestStore', () => {
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

    describe('初始状态', () => {
        it('phase 为 idle 且相关字段为默认值', () => {
            expect(store.phase).toBe('idle')
            expect(store.taskId).toBeNull()
            expect(store.projectId).toBeNull()
            expect(store.currentStage).toBe('pending')
            expect(store.progress).toBe(0)
            expect(store.caseCount).toBe(0)
            expect(store.errorMessage).toBeNull()
        })

        it('三态 getters 与 phase 同步', () => {
            expect(store.isIdle).toBe(true)
            expect(store.isRunning).toBe(false)
            expect(store.isCompleted).toBe(false)
            expect(store.isFailed).toBe(false)
        })
    })

    describe('launch', () => {
        it('成功后切到 running 并写入会话字段与 lastUrl', async () => {
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await store.launch({ url: 'https://example.com' })

            expect(store.phase).toBe('running')
            expect(store.taskId).toBe(101)
            expect(store.projectId).toBe(202)
            expect(store.websocketChannel).toBe('quick_test:101')
            expect(store.estimatedDurationSec).toBe(300)
            expect(store.lastUrl).toBe('https://example.com')
            expect(store.isRunning).toBe(true)
        })

        it('成功后持久化会话到 localStorage', async () => {
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await store.launch({ url: 'https://example.com', description: '登录页' })

            const raw = localStorage.getItem(SESSION_KEY)
            expect(raw).toBeTruthy()
            const parsed = JSON.parse(raw!)
            expect(parsed.phase).toBe('running')
            expect(parsed.taskId).toBe(101)
            expect(parsed.lastUrl).toBe('https://example.com')
        })

        it('失败时抛出异常且不修改 idle 态', async () => {
            vi.mocked(quickTestApi.launch).mockRejectedValueOnce(new Error('网络错误'))
            await expect(store.launch({ url: 'https://example.com' })).rejects.toThrow('网络错误')

            expect(store.phase).toBe('idle')
            expect(store.taskId).toBeNull()
            expect(localStorage.getItem(SESSION_KEY)).toBeNull()
        })
    })

    describe('refreshStatus', () => {
        // 直接 seed 运行态，隔离测试 refreshStatus 自身逻辑（不依赖 launch mock）
        function seedRunningSession(): void {
            store.taskId = 101
            store.projectId = 202
            store.phase = 'running'
            store.websocketChannel = 'quick_test:101'
        }

        it('执行完成 → phase=completed', async () => {
            seedRunningSession()
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '执行完成', progress: 100, current_stage: 'completed' })
            )
            await store.refreshStatus()

            expect(store.phase).toBe('completed')
            expect(store.progress).toBe(100)
            expect(store.currentStage).toBe('completed')
            expect(store.isCompleted).toBe(true)
        })

        it('执行失败 → phase=failed', async () => {
            seedRunningSession()
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '执行失败', progress: 30, current_stage: 'failed' })
            )
            await store.refreshStatus()

            expect(store.phase).toBe('failed')
            expect(store.isFailed).toBe(true)
        })

        it('已停止 → phase=idle', async () => {
            seedRunningSession()
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({ status: '已停止', progress: 0, current_stage: 'stopped' })
            )
            await store.refreshStatus()

            expect(store.phase).toBe('idle')
            expect(store.isIdle).toBe(true)
        })

        it('执行中 → 保持 running 且更新进度字段', async () => {
            seedRunningSession()
            vi.mocked(quickTestApi.getStatus).mockResolvedValueOnce(
                makeStatusResponse({
                    status: '执行中',
                    progress: 60,
                    current_stage: 'executing',
                    case_count: 7,
                })
            )
            await store.refreshStatus()

            expect(store.phase).toBe('running')
            expect(store.progress).toBe(60)
            expect(store.currentStage).toBe('executing')
            expect(store.caseCount).toBe(7)
        })

        it('taskId 为 null 时直接返回不请求', async () => {
            await store.refreshStatus()
            expect(quickTestApi.getStatus).not.toHaveBeenCalled()
        })
    })

    describe('applyPushMessage', () => {
        it('completed + done → completed 且更新进度', () => {
            store.applyPushMessage({ stage: 'completed', status: 'done', progress: 100, detail: null })
            expect(store.phase).toBe('completed')
            expect(store.progress).toBe(100)
            expect(store.currentStage).toBe('completed')
        })

        it('failed 阶段 → failed 且记录 errorMessage（detail 为字符串）', () => {
            store.applyPushMessage({
                stage: 'failed',
                status: 'error',
                progress: 40,
                detail: '用例生成超时',
            })
            expect(store.phase).toBe('failed')
            expect(store.errorMessage).toBe('用例生成超时')
        })

        it('failed 阶段 detail 为对象时提取 message', () => {
            store.applyPushMessage({
                stage: 'failed',
                status: 'error',
                progress: 10,
                detail: { message: '探索站点失败' },
            })
            expect(store.phase).toBe('failed')
            expect(store.errorMessage).toBe('探索站点失败')
        })

        it('普通阶段 → 更新 currentStage/progress，idle 唤醒到 running', () => {
            store.applyPushMessage({ stage: 'site_exploring', status: 'running', progress: 15, detail: null })
            expect(store.phase).toBe('running')
            expect(store.currentStage).toBe('site_exploring')
            expect(store.progress).toBe(15)
        })

        it('非法消息（stage 非 string）被忽略', () => {
            store.applyPushMessage({ stage: 123, status: 'x', progress: 50, detail: null } as unknown as never)
            expect(store.phase).toBe('idle')
            expect(store.progress).toBe(0)
        })
    })

    describe('reset / restore / persist', () => {
        it('reset 清空状态并保留 lastUrl，同时清除 localStorage', async () => {
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await store.launch({ url: 'https://example.com' })
            expect(localStorage.getItem(SESSION_KEY)).toBeTruthy()

            store.reset()

            expect(store.phase).toBe('idle')
            expect(store.taskId).toBeNull()
            expect(store.websocketChannel).toBeNull()
            expect(store.lastUrl).toBe('https://example.com')
            expect(localStorage.getItem(SESSION_KEY)).toBeNull()
        })

        it('restore 从 localStorage 恢复会话', async () => {
            vi.mocked(quickTestApi.launch).mockResolvedValueOnce(makeLaunchResponse())
            await store.launch({ url: 'https://restore.example.com' })

            // 模拟页面刷新：重建 store 实例并恢复
            setActivePinia(createPinia())
            const freshStore = useQuickTestStore()
            expect(freshStore.taskId).toBeNull()

            freshStore.restore()
            expect(freshStore.taskId).toBe(101)
            expect(freshStore.projectId).toBe(202)
            expect(freshStore.websocketChannel).toBe('quick_test:101')
            expect(freshStore.lastUrl).toBe('https://restore.example.com')
            expect(freshStore.phase).toBe('running')
        })

        it('restore 遇到脏 JSON 时清除 key 且不抛异常', () => {
            localStorage.setItem(SESSION_KEY, '{not valid json')
            expect(() => store.restore()).not.toThrow()
            expect(localStorage.getItem(SESSION_KEY)).toBeNull()
            expect(store.phase).toBe('idle')
        })

        it('persist 与 restore 往返一致', () => {
            store.taskId = 555
            store.projectId = 666
            store.websocketChannel = 'quick_test:555'
            store.currentStage = 'task_assembling'
            store.progress = 77
            store.lastUrl = 'https://roundtrip.example.com'
            store.persist()

            setActivePinia(createPinia())
            const fresh = useQuickTestStore()
            fresh.restore()

            expect(fresh.taskId).toBe(555)
            expect(fresh.projectId).toBe(666)
            expect(fresh.websocketChannel).toBe('quick_test:555')
            expect(fresh.currentStage).toBe('task_assembling')
            expect(fresh.progress).toBe(77)
            expect(fresh.lastUrl).toBe('https://roundtrip.example.com')
        })

        it('clearQuickTestSession 移除会话 key', () => {
            localStorage.setItem(SESSION_KEY, '{"phase":"running"}')
            clearQuickTestSession()
            expect(localStorage.getItem(SESSION_KEY)).toBeNull()
        })
    })
})
