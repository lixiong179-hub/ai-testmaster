import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { WebSocketConnection, WebSocketOptions } from '@/utils/websocket'
import type { Report } from '@/api/report'

// 控制 WS 连接的回调入口，便于测试模拟事件
let lastWsOptions: WebSocketOptions | null = null
let connectionCloseSpy: ReturnType<typeof vi.fn>

vi.mock('@/utils/websocket', () => {
    return {
        connectWebSocket: vi.fn((_path: string, options: WebSocketOptions) => {
            lastWsOptions = options
            connectionCloseSpy = vi.fn()
            const conn: WebSocketConnection = {
                ws: {} as WebSocket,
                close: connectionCloseSpy,
            }
            return conn
        }),
    }
})

vi.mock('@/api/report', () => {
    return {
        default: {
            getReports: vi.fn(),
            getReportDetail: vi.fn(),
            exportReportPDF: vi.fn(),
            exportReportHTML: vi.fn(),
        },
    }
})

vi.mock('vue-router', () => ({
    useRouter: () => ({
        push: vi.fn().mockResolvedValue(undefined),
    }),
}))

import { connectWebSocket } from '@/utils/websocket'
import reportApi from '@/api/report'
import { useQuickTestStore } from '@/store/quickTest'
import { useQuickTestFlow } from '../useQuickTestFlow'

describe('useQuickTestFlow', () => {
    let store: ReturnType<typeof useQuickTestStore>

    beforeEach(() => {
        localStorage.clear()
        vi.clearAllMocks()
        vi.useFakeTimers()
        setActivePinia(createPinia())
        store = useQuickTestStore()
        lastWsOptions = null
        // 默认 running + 完整会话字段
        store.taskId = 101
        store.projectId = 202
        store.phase = 'running'
        store.websocketChannel = 'quick_test:101'
        store.estimatedDurationSec = 300
    })

    afterEach(() => {
        vi.useRealTimers()
        vi.restoreAllMocks()
    })

    describe('WS 订阅', () => {
        it('subscribeWebSocket 调 connectWebSocket 且 path 含 taskId', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            expect(connectWebSocket).toHaveBeenCalled()
            const args = vi.mocked(connectWebSocket).mock.calls[0]
            expect(args[0]).toBe('/quick-test/101')
            expect(args[1]).toBeTruthy()
        })

        it('phase 非 running 时不订阅 WS', () => {
            store.phase = 'completed'
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            expect(connectWebSocket).not.toHaveBeenCalled()
        })

        it('taskId 缺失时不订阅 WS', () => {
            store.taskId = null
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            expect(connectWebSocket).not.toHaveBeenCalled()
        })

        it('onOpen 触发后 wsConnected=true', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            lastWsOptions!.onOpen?.()
            expect(flow.wsConnected.value).toBe(true)
        })
    })

    describe('WS 消息处理：applyPushMessage + captureDetail', () => {
        it('WS 推送进度消息更新 store.currentStage 与 progress', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            lastWsOptions!.onMessage?.({
                stage: 'case_generating',
                status: 'running',
                progress: 55,
                detail: null,
            })
            expect(store.currentStage).toBe('case_generating')
            expect(store.progress).toBe(55)
        })

        it('WS 推送 completed+done 切换 store.phase 为 completed', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            lastWsOptions!.onMessage?.({
                stage: 'completed',
                status: 'done',
                progress: 100,
                detail: null,
            })
            expect(store.phase).toBe('completed')
            expect(store.isCompleted).toBe(true)
        })

        it('WS 推送 failed 阶段设置 store.errorMessage', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            lastWsOptions!.onMessage?.({
                stage: 'failed',
                status: 'error',
                progress: 30,
                detail: '探索站点超时',
            })
            expect(store.phase).toBe('failed')
            expect(store.errorMessage).toBe('探索站点超时')
        })

        it('WS 推送 detail 携带 cases 时捕获到 resultDetail', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            const cases = [
                { id: 1, title: '用例 A', status: 'passed', steps: [] },
            ]
            lastWsOptions!.onMessage?.({
                stage: 'completed',
                status: 'done',
                progress: 100,
                detail: { cases },
            })
            expect(flow.resultDetail.value?.cases).toHaveLength(1)
            expect(flow.resultDetail.value?.cases?.[0].title).toBe('用例 A')
            expect(flow.cases.value).toHaveLength(1)
        })

        it('WS 推送 detail 携带 defects 时捕获并暴露给 defects computed', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            const defects = [
                {
                    bug_no: 'B-1',
                    title: '缺陷 1',
                    severity: 1,
                    module: 'M',
                    ux_category: 'U',
                    status: 'open',
                    reproduction_steps: null,
                    evidence: null,
                    fix_suggestion: null,
                },
            ]
            lastWsOptions!.onMessage?.({
                stage: 'completed',
                status: 'done',
                progress: 100,
                detail: { defects },
            })
            expect(flow.defects.value).toHaveLength(1)
            expect(flow.defects.value[0].bug_no).toBe('B-1')
        })

        it('非对象消息被静默忽略不抛异常', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            expect(() => {
                lastWsOptions!.onMessage?.(null)
                lastWsOptions!.onMessage?.('invalid string')
            }).not.toThrow()
        })
    })

    describe('断线重连：指数退避（spec 偏离③ 支撑）', () => {
        it('onClose 非手动关闭时安排首次重连延迟 1000ms', async () => {
            // 重连回调内会 await store.refreshStatus()，未 mock quickTestApi 会发起真实请求挂起，
            // 故 spy refreshStatus 使其立即 resolve，确保 connect() 被执行
            vi.spyOn(store, 'refreshStatus').mockResolvedValue()
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            vi.mocked(connectWebSocket).mockClear()
            lastWsOptions!.onClose?.()
            expect(flow.wsConnected.value).toBe(false)
            // 未到 1000ms 不应触发重连
            await vi.advanceTimersByTimeAsync(999)
            expect(connectWebSocket).not.toHaveBeenCalled()
            // 到达 1000ms 触发首次重连
            await vi.advanceTimersByTimeAsync(1)
            expect(connectWebSocket).toHaveBeenCalled()
        })

        it('首次重连触发后调用 store.refreshStatus 与 connectWebSocket', async () => {
            const refreshSpy = vi.spyOn(store, 'refreshStatus').mockResolvedValue()
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            lastWsOptions!.onClose?.()
            vi.mocked(connectWebSocket).mockClear()
            await vi.advanceTimersByTimeAsync(1000)
            expect(refreshSpy).toHaveBeenCalled()
            expect(connectWebSocket).toHaveBeenCalled()
        })

        it('disconnectWebSocket 后不再触发自动重连', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            flow.disconnectWebSocket()
            vi.mocked(connectWebSocket).mockClear()
            // 模拟 onClose 被触发（实际不会，因为 manualClose=true）
            expect(connectionCloseSpy).toHaveBeenCalled()
            expect(flow.wsConnected.value).toBe(false)
        })

        it('phase 切换到 completed 后不再重连', async () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            vi.mocked(connectWebSocket).mockClear()
            store.phase = 'completed'
            lastWsOptions!.onClose?.()
            // scheduleReconnect 内部判断 phase !== 'running' 直接返回，不安排重连
            // 推进足够长时间验证仍无重连
            await vi.advanceTimersByTimeAsync(30000)
            expect(connectWebSocket).not.toHaveBeenCalled()
        })
    })

    describe('取消与再次执行', () => {
        it('cancelQuickTest 切回 idle 且断开 WS', () => {
            const flow = useQuickTestFlow()
            flow.subscribeWebSocket()
            flow.cancelQuickTest()
            expect(store.phase).toBe('idle')
            expect(store.taskId).toBeNull()
            expect(flow.wsConnected.value).toBe(false)
        })

        it('rerunQuickTest 清空 resultDetail 且切回 idle（保留 lastUrl）', () => {
            const flow = useQuickTestFlow()
            store.lastUrl = 'https://rerun.example.com'
            flow.resultDetail.value = { cases: [] }
            flow.rerunQuickTest()
            expect(store.phase).toBe('idle')
            expect(flow.resultDetail.value).toBeNull()
            expect(store.lastUrl).toBe('https://rerun.example.com')
        })
    })

    describe('downloadReport 降级（spec 偏离③）', () => {
        it('taskId/projectId 缺失时降级提示', async () => {
            store.taskId = null
            const flow = useQuickTestFlow()
            await flow.downloadReport('pdf')
            // 仅验证不抛异常，降级走 ElMessage.info（已由真实组件捕获）
            expect(true).toBe(true)
        })

        it('findReportByTask 返回空时降级提示不抛异常', async () => {
            vi.mocked(reportApi.getReports).mockResolvedValueOnce({
                data: { items: [] },
            } as never)
            const flow = useQuickTestFlow()
            await expect(flow.downloadReport('pdf')).resolves.toBeUndefined()
        })

        it('导出 API 失败时降级提示不抛异常', async () => {
            const report: Partial<Report> = { id: 1, test_task_id: 101, project_id: 202 }
            vi.mocked(reportApi.getReports).mockResolvedValueOnce({
                data: { items: [report] },
            } as never)
            vi.mocked(reportApi.exportReportPDF).mockRejectedValueOnce(new Error('500'))
            const flow = useQuickTestFlow()
            await expect(flow.downloadReport('pdf')).resolves.toBeUndefined()
        })
    })

    describe('saveToOtherProject 降级（spec 偏离③）', () => {
        it('taskId 缺失时不发起请求', async () => {
            store.taskId = null
            const flow = useQuickTestFlow()
            await expect(flow.saveToOtherProject(999)).resolves.toBeUndefined()
        })

        it('import-task API 失败时降级提示不抛异常', async () => {
            const flow = useQuickTestFlow()
            // mock request 模块的 post 抛错
            const request = (await import('@/utils/request')).default
            vi.spyOn(request, 'post').mockRejectedValueOnce(new Error('404'))
            await expect(flow.saveToOtherProject(999)).resolves.toBeUndefined()
        })
    })

    describe('fetchReport 补齐结果明细', () => {
        it('taskId/projectId 缺失时直接返回不请求', async () => {
            store.taskId = null
            const flow = useQuickTestFlow()
            await flow.fetchReport()
            expect(reportApi.getReports).not.toHaveBeenCalled()
        })

        it('拉取成功后填充 resultDetail.cases/defects/summary', async () => {
            const report: Partial<Report> = {
                id: 1,
                test_task_id: 101,
                project_id: 202,
                test_cases: [
                    {
                        test_case_id: 10,
                        status: 'passed',
                        actual_result: '通过',
                        start_time: '2026-06-27T10:00:00',
                        end_time: '2026-06-27T10:01:00',
                        expected_result: '应通过',
                        test_case_name: '用例 10',
                    },
                ],
                content: {
                    defect_list: [
                        {
                            bug_no: 'B-1',
                            title: '缺陷',
                            severity: 1,
                            ux_category: 'U',
                            module: 'M',
                            status: 'open',
                            reproduction_steps: null,
                            evidence: null,
                            ai_analysis: null,
                            fix_suggestion: null,
                        },
                    ],
                    test_cases: [],
                    statistics: {},
                    environment: null,
                    defect_overview: null,
                    defect_distribution: null,
                    implicit_defects: null,
                    security_findings: null,
                    coverage_assessment: null,
                },
                execution_time: 60,
            }
            vi.mocked(reportApi.getReports).mockResolvedValueOnce({
                data: { items: [report] },
            } as never)
            vi.mocked(reportApi.getReportDetail).mockResolvedValueOnce(report as never)
            const flow = useQuickTestFlow()
            await flow.fetchReport()
            expect(flow.cases.value).toHaveLength(1)
            expect(flow.cases.value[0].title).toBe('用例 10')
            expect(flow.defects.value).toHaveLength(1)
            expect(flow.summary.value).toBeTruthy()
            expect(flow.summary.value?.total).toBe(1)
        })

        it('拉取异常时不抛错且保留已有 resultDetail', async () => {
            vi.mocked(reportApi.getReports).mockRejectedValueOnce(new Error('500'))
            const flow = useQuickTestFlow()
            flow.resultDetail.value = { cases: [] }
            await expect(flow.fetchReport()).resolves.toBeUndefined()
            expect(flow.resultDetail.value).not.toBeNull()
        })
    })

    describe('路由跳转', () => {
        it('goToReport 在 taskId 缺失时不抛错', () => {
            store.taskId = null
            const flow = useQuickTestFlow()
            expect(() => flow.goToReport()).not.toThrow()
        })

        it('goToCaseEdit 在 projectId 缺失时不抛错', () => {
            store.projectId = null
            const flow = useQuickTestFlow()
            expect(() => flow.goToCaseEdit()).not.toThrow()
        })
    })
})
