/**
 * 快速测试流程编排 composable。
 *
 * 职责：
 *  1. 订阅真实 WebSocket 通道 /ws/quick-test/{taskId}，断线指数退避重连，重连后拉取当前进度补齐；
 *  2. 捕获 WS 推送 detail 到 resultDetail，供结果视图渲染用例/缺陷明细；
 *  3. 提供「取消 / 再次执行 / 查看报告 / 编辑用例 / 下载报告 / 保存到其他项目」操作入口。
 *
 * 复用 Task 10 基础设施：useQuickTestStore（applyPushMessage/refreshStatus/reset/restore），
 * connectWebSocket 函数式 API（src/utils/websocket.ts），不重写 store 内部状态。
 */
import { ref, computed, onUnmounted } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useQuickTestStore } from '@/store/quickTest'
import { connectWebSocket, type WebSocketConnection } from '@/utils/websocket'
import reportApi from '@/api/report'
import type { Report } from '@/api/report'
import type { QuickTestPushMessage } from '@/store/quickTest'
import type {
    QuickTestResultDetail,
    CaseData,
    DefectData,
    SummaryStats,
} from './quickTestTypes'
import {
    testCaseResultToCaseData,
    defectItemToDefectData,
    buildSummaryFromReport,
} from './quickTestTypes'

/** 指数退避重连上限（与 wsClient 一致） */
const MAX_RECONNECT_DELAY = 30000
/** 重连尝试上限：超过后停止重连，避免无限轮询 */
const MAX_RECONNECT_ATTEMPTS = 8

export interface QuickTestFlowContext {
    store: ReturnType<typeof useQuickTestStore>
    resultDetail: Ref<QuickTestResultDetail | null>
    cases: ComputedRef<CaseData[]>
    defects: ComputedRef<DefectData[]>
    summary: ComputedRef<SummaryStats | null>
    exploredPages: ComputedRef<NonNullable<QuickTestResultDetail['explored_pages']>>
    wsConnected: Ref<boolean>
    /** 订阅 WS：phase=running 时调用，幂等 */
    subscribeWebSocket: () => void
    /** 手动断开 WS 并清重连定时器 */
    disconnectWebSocket: () => void
    /** 取消：当前仅前端置 idle（后端取消 API 未落地），如需扩展在此接入 */
    cancelQuickTest: () => void
    /** 再次执行：reset 后 phase→idle，lastUrl 保留作为默认值 */
    rerunQuickTest: () => void
    goToReport: () => void
    goToCaseEdit: () => void
    downloadReport: (format: 'pdf' | 'html') => Promise<void>
    saveToOtherProject: (targetProjectId: number) => Promise<void>
    /** 拉取报告补齐结果明细（restore 后无 WS 推送时调用） */
    fetchReport: () => Promise<void>
}

/**
 * 创建快速测试流程上下文。
 * 由 QuickTest.vue 容器调用一次，子组件通过 props/emits 接收数据与触发操作。
 */
export function useQuickTestFlow(): QuickTestFlowContext {
    const router = useRouter()
    const store = useQuickTestStore()

    const resultDetail = ref<QuickTestResultDetail | null>(null)
    const wsConnected = ref(false)
    let connection: WebSocketConnection | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let reconnectAttempts = 0
    let manualClose = false

    const cases = computed<CaseData[]>(() => resultDetail.value?.cases ?? [])
    const defects = computed<DefectData[]>(() => resultDetail.value?.defects ?? [])
    const summary = computed<SummaryStats | null>(() => {
        const s = resultDetail.value?.summary
        if (!s) return null
        return {
            total: s.total ?? 0,
            passed: s.passed ?? 0,
            failed: s.failed ?? 0,
            pass_rate: s.pass_rate ?? 0,
            duration_sec: s.duration_sec ?? 0,
            severity_dist: s.severity_dist ?? { p0: 0, p1: 0, p2: 0, p3: 0 },
        }
    })
    const exploredPages = computed(() => resultDetail.value?.explored_pages ?? [])

    /** 解析 WS 推送 detail 为结果负载，仅在 completed 或携带明细时写入 */
    function captureDetail(msg: QuickTestPushMessage): void {
        const detail = msg.detail
        if (!detail || typeof detail !== 'object') return
        const payload = detail as Partial<QuickTestResultDetail>
        // 仅在字段非空时合并，避免覆盖已有数据
        const next: QuickTestResultDetail = { ...(resultDetail.value || {}) }
        if (Array.isArray(payload.cases) && payload.cases.length > 0) next.cases = payload.cases
        if (Array.isArray(payload.defects) && payload.defects.length > 0) next.defects = payload.defects
        if (payload.summary) next.summary = { ...(next.summary || {}), ...payload.summary }
        if (Array.isArray(payload.explored_pages)) next.explored_pages = payload.explored_pages
        resultDetail.value = next
    }

    /** 处理 WS 消息：先调 store 唯一入口 applyPushMessage，再捕获明细 */
    function handleMessage(msg: QuickTestPushMessage): void {
        if (!msg || typeof msg !== 'object') return
        store.applyPushMessage(msg)
        captureDetail(msg)
    }

    /** 建立连接：基于 store.taskId 构造 path，token 走子协议 */
    function connect(): void {
        const taskId = store.taskId
        if (!taskId) return
        // phase 已终态（completed/failed/idle）时无需订阅
        if (store.phase !== 'running') return
        manualClose = false
        // 关闭旧连接，避免重复
        safeClose()
        const path = `/quick-test/${taskId}`
        connection = connectWebSocket(path, {
            onOpen: () => {
                reconnectAttempts = 0
                wsConnected.value = true
                // launch API 同步执行 4 阶段编排推送，前端在 launch 返回后才连
                // WebSocket，会错过编排期间的所有推送；连上后立即拉取当前进度补齐，
                // 确保 currentStage/progress 与后端一致（与 scheduleReconnect 机制对齐）
                store.refreshStatus().catch(() => {
                    // refreshStatus 失败不阻断 WebSocket 订阅
                })
            },
            onMessage: (data: unknown) => handleMessage(data as QuickTestPushMessage),
            onClose: () => {
                wsConnected.value = false
                if (!manualClose) scheduleReconnect()
            },
            onError: () => {
                wsConnected.value = false
            },
        })
    }

    /** 指数退避重连：min(1000*2^attempts, 30000)，超过上限停止 */
    function scheduleReconnect(): void {
        if (reconnectTimer || manualClose) return
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return
        if (store.phase !== 'running') return
        reconnectAttempts += 1
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), MAX_RECONNECT_DELAY)
        reconnectTimer = setTimeout(async () => {
            reconnectTimer = null
            if (store.phase !== 'running') return
            // 重连后拉取当前进度补齐，避免漏推
            try {
                await store.refreshStatus()
            } catch {
                // refreshStatus 失败不阻断重连
            }
            connect()
        }, delay)
    }

    function safeClose(): void {
        if (connection) {
            try {
                connection.close()
            } catch {
                // 关闭异常静默
            }
            connection = null
        }
    }

    function subscribeWebSocket(): void {
        if (connection && wsConnected.value) return
        connect()
    }

    function disconnectWebSocket(): void {
        manualClose = true
        if (reconnectTimer) {
            clearTimeout(reconnectTimer)
            reconnectTimer = null
        }
        safeClose()
        wsConnected.value = false
    }

    function cancelQuickTest(): void {
        // 后端取消 API 未落地：当前仅前端置 idle，断开 WS
        disconnectWebSocket()
        store.reset()
        ElMessage.info('已取消快速测试')
    }

    function rerunQuickTest(): void {
        // reset 保留 lastUrl，容器自动切回 idle 渲染输入卡，输入卡可回填 lastUrl
        disconnectWebSocket()
        resultDetail.value = null
        store.reset()
    }

    function goToReport(): void {
        const taskId = store.taskId
        if (!taskId) {
            ElMessage.warning('当前无任务可跳转')
            return
        }
        router.push({ path: '/home/report', query: { task_id: String(taskId) } })
    }

    function goToCaseEdit(): void {
        const projectId = store.projectId
        if (!projectId) {
            ElMessage.warning('当前无关联项目')
            return
        }
        router.push({ path: '/home/case', query: { project_id: String(projectId) } })
    }

    /**
     * 下载报告：先按 task_id 查询报告，再调真实导出 API。
     * 报告不存在或导出失败时降级提示「报告下载入口即将上线」。
     */
    async function downloadReport(format: 'pdf' | 'html'): Promise<void> {
        const taskId = store.taskId
        const projectId = store.projectId
        if (!taskId || !projectId) {
            ElMessage.info('报告下载入口即将上线')
            return
        }
        try {
            const report = await findReportByTask(taskId, projectId)
            if (!report) {
                ElMessage.info('报告下载入口即将上线')
                return
            }
            const res =
                format === 'pdf'
                    ? await reportApi.exportReportPDF(report.id, projectId)
                    : await reportApi.exportReportHTML(report.id, projectId)
            const blob = (res as { data?: Blob }).data
            if (!blob) {
                ElMessage.info('报告下载入口即将上线')
                return
            }
            triggerBlobDownload(blob, `quick-test-${taskId}.${format}`)
            ElMessage.success('报告下载已开始')
        } catch {
            // spec 偏离③：下载 API 不存在/失败时降级提示
            ElMessage.info('报告下载入口即将上线')
        }
    }

    /**
     * 保存到其他项目：调用真实 import-task API。
     * 接口不存在时降级提示。
     */
    async function saveToOtherProject(targetProjectId: number): Promise<void> {
        const taskId = store.taskId
        if (!taskId || !targetProjectId) return
        try {
            // 真实路径：POST /api/v1/projects/{targetId}/import-task/{taskId}
            const mod = await import('@/utils/request')
            const request = mod.default
            await request.post(`/api/v1/projects/${targetProjectId}/import-task/${taskId}`)
            ElMessage.success('已保存到目标项目')
        } catch {
            // spec 偏离③：保存 API 不存在/失败时降级提示
            ElMessage.info('保存到其他项目入口即将上线')
        }
    }

    /** 拉取报告补齐结果明细：restore 后无 WS 推送时由结果视图触发 */
    async function fetchReport(): Promise<void> {
        const taskId = store.taskId
        const projectId = store.projectId
        if (!taskId || !projectId) return
        try {
            const report = await findReportByTask(taskId, projectId)
            if (!report) return
            const full = await reportApi.getReportDetail(report.id, projectId)
            const detail = (full as unknown as Report) || report
            const mappedCases = (detail.test_cases || []).map(testCaseResultToCaseData)
            const mappedDefects = (detail.content?.defect_list || []).map(defectItemToDefectData)
            resultDetail.value = {
                ...(resultDetail.value || {}),
                cases: mappedCases.length ? mappedCases : resultDetail.value?.cases,
                defects: mappedDefects.length ? mappedDefects : resultDetail.value?.defects,
                summary: buildSummaryFromReport(detail),
            }
        } catch {
            // 报告拉取失败：保留已有 resultDetail，不阻断渲染（结果视图会展示空态）
        }
    }

    onUnmounted(() => {
        disconnectWebSocket()
    })

    return {
        store,
        resultDetail,
        cases,
        defects,
        summary,
        exploredPages,
        wsConnected,
        subscribeWebSocket,
        disconnectWebSocket,
        cancelQuickTest,
        rerunQuickTest,
        goToReport,
        goToCaseEdit,
        downloadReport,
        saveToOtherProject,
        fetchReport,
    }
}

/**
 * 按 test_task_id 查询报告。
 * 兼容 reportApi.getReports 两种响应结构（ApiResponse 包裹 / 直接返回）。
 */
async function findReportByTask(taskId: number, projectId: number): Promise<Report | null> {
    const res = (await reportApi.getReports({ project_id: projectId, page: 1, page_size: 100 })) as unknown as {
        data?: { items?: Report[] } | Report[]
        items?: Report[]
    }
    const items: Report[] = extractItems(res)
    return items.find((r) => r.test_task_id === taskId) || null
}

/** 从可能被包裹的响应中安全提取 items 数组 */
function extractItems(res: unknown): Report[] {
    if (!res || typeof res !== 'object') return []
    const r = res as { data?: { items?: Report[] }; items?: Report[] }
    if (Array.isArray(r.data?.items)) return r.data!.items!
    if (Array.isArray(r.items)) return r.items
    return []
}

/** 触发浏览器 Blob 下载 */
function triggerBlobDownload(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
}
