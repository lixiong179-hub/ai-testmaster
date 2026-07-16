import { defineStore } from 'pinia'
import quickTestApi, {
    type QuickTestLaunchRequest,
    type QuickTestStage,
} from '@/api/quickTest'

/** 快速测试三态状态机阶段 */
export type QuickTestPhase = 'idle' | 'running' | 'completed' | 'failed'

/** localStorage 持久化 key（手动持久化，不依赖 pinia-plugin-persistedstate） */
const SESSION_KEY = 'quickTestSession'

/** 持久化字段子集：仅保存断线刷新恢复所需的最小集合 */
interface PersistedSession {
    phase: QuickTestPhase
    taskId: number | null
    projectId: number | null
    websocketChannel: string | null
    estimatedDurationSec: number | null
    currentStage: QuickTestStage
    progress: number
    lastUrl: string | null
}

/** WebSocket 推送消息体（与后端 quick_test:{task_id} 通道契约对齐） */
export interface QuickTestPushMessage {
    stage: string
    status: string
    progress: number
    // 项目规范禁用未约束类型，detail 统一用 unknown，调用方按需窄化
    detail: unknown
}

/** 终态阶段集合：收到这些阶段时状态机切换到 failed */
const FAILED_STAGES: ReadonlySet<string> = new Set(['failed'])

/** 从 push detail 中安全提取错误信息 */
function extractDetailMessage(detail: unknown): string {
    if (typeof detail === 'string' && detail.length > 0) return detail
    if (detail && typeof detail === 'object' && 'message' in detail) {
        const msg = (detail as { message: unknown }).message
        if (typeof msg === 'string' && msg.length > 0) return msg
    }
    return '快速测试执行失败'
}

/** 安全读取 localStorage 字符串 */
function safeGetItem(key: string): string | null {
    try {
        return localStorage.getItem(key)
    } catch {
        return null
    }
}

/** 安全写入 localStorage */
function safeSetItem(key: string, value: string): void {
    try {
        localStorage.setItem(key, value)
    } catch {
        // localStorage 不可用（隐私模式/配额超限）时静默降级，不阻断业务
    }
}

/** 安全移除 localStorage */
function safeRemoveItem(key: string): void {
    try {
        localStorage.removeItem(key)
    } catch {
        // 静默降级
    }
}

export const useQuickTestStore = defineStore('quickTest', {
    state: () => ({
        phase: 'idle' as QuickTestPhase,
        taskId: null as number | null,
        projectId: null as number | null,
        websocketChannel: null as string | null,
        estimatedDurationSec: null as number | null,
        currentStage: 'pending' as QuickTestStage,
        progress: 0,
        caseCount: 0,
        startedAt: null as string | null,
        errorMessage: null as string | null,
        lastUrl: null as string | null,
    }),

    getters: {
        isIdle: (state) => state.phase === 'idle',
        isRunning: (state) => state.phase === 'running',
        isCompleted: (state) => state.phase === 'completed',
        isFailed: (state) => state.phase === 'failed',
    },

    actions: {
        /**
         * 启动快速测试。
         * 成功后置 running 态并持久化会话；失败时抛出异常由调用方 try/catch 处理 UI 错误。
         */
        async launch(payload: QuickTestLaunchRequest): Promise<void> {
            const res = await quickTestApi.launch(payload)
            const data = res.data
            this.phase = 'running'
            this.taskId = data.task_id
            this.projectId = data.project_id
            this.websocketChannel = data.websocket_channel
            this.estimatedDurationSec = data.estimated_duration_sec
            this.lastUrl = payload.url
            this.currentStage = 'pending'
            this.progress = 0
            this.caseCount = 0
            this.startedAt = null
            this.errorMessage = null
            this.persist()
        },

        /**
         * 拉取任务状态并同步状态机。
         * 后端 status 字段为中文标签：执行完成→completed，执行失败→failed，已停止→idle。
         * 异常向上抛出，调用方可在此后降级到 WebSocket 推送。
         */
        async refreshStatus(): Promise<void> {
            if (this.taskId == null) return
            const res = await quickTestApi.getStatus(this.taskId)
            const data = res.data
            this.currentStage = data.current_stage
            this.progress = data.progress
            this.caseCount = data.case_count
            this.startedAt = data.started_at
            this.websocketChannel = data.websocket_channel
            if (data.status === '执行完成') {
                this.phase = 'completed'
            } else if (data.status === '执行失败') {
                this.phase = 'failed'
            } else if (data.status === '已停止') {
                this.phase = 'idle'
            }
            this.persist()
        },

        /**
         * 应用 WebSocket 推送消息更新状态机。
         * stage='completed' 且 status='done' → completed；
         * stage 命中失败集合 → failed 并记录 errorMessage；
         * 其余阶段更新 currentStage/progress，若处于 idle 则自动切到 running。
         */
        applyPushMessage(msg: QuickTestPushMessage): void {
            if (!msg || typeof msg.stage !== 'string') return
            const stage = msg.stage
            if (typeof msg.progress === 'number' && msg.progress >= 0 && msg.progress <= 100) {
                this.progress = msg.progress
            }
            if (stage === 'completed' && msg.status === 'done') {
                this.currentStage = 'completed'
                this.phase = 'completed'
                this.persist()
                return
            }
            if (FAILED_STAGES.has(stage)) {
                this.currentStage = stage as QuickTestStage
                this.phase = 'failed'
                this.errorMessage = extractDetailMessage(msg.detail)
                this.persist()
                return
            }
            // 非终态推送：更新阶段，必要时从 idle 唤醒到 running
            this.currentStage = stage as QuickTestStage
            if (this.phase === 'idle') this.phase = 'running'
            this.persist()
        },

        /** 重置到 idle，清空所有字段（保留 lastUrl 方便用户重试） */
        reset(): void {
            this.phase = 'idle'
            this.taskId = null
            this.projectId = null
            this.websocketChannel = null
            this.estimatedDurationSec = null
            this.currentStage = 'pending'
            this.progress = 0
            this.caseCount = 0
            this.startedAt = null
            this.errorMessage = null
            // lastUrl 保留：用户刷新后可基于上次 URL 再次发起
            safeRemoveItem(SESSION_KEY)
        },

        /** 从 localStorage 恢复 state（断线刷新恢复场景） */
        restore(): void {
            const raw = safeGetItem(SESSION_KEY)
            if (!raw) return
            try {
                const parsed = JSON.parse(raw) as PersistedSession
                if (!parsed || typeof parsed !== 'object') return
                this.phase = parsed.phase ?? 'idle'
                this.taskId = parsed.taskId ?? null
                this.projectId = parsed.projectId ?? null
                this.websocketChannel = parsed.websocketChannel ?? null
                this.estimatedDurationSec = parsed.estimatedDurationSec ?? null
                this.currentStage = parsed.currentStage ?? 'pending'
                this.progress = parsed.progress ?? 0
                this.lastUrl = parsed.lastUrl ?? this.lastUrl
            } catch {
                // JSON 解析失败：清除脏数据，避免反复抛错
                safeRemoveItem(SESSION_KEY)
            }
        },

        /** 内部辅助：序列化会话到 localStorage，在各 mutation 后调用 */
        persist(): void {
            const session: PersistedSession = {
                phase: this.phase,
                taskId: this.taskId,
                projectId: this.projectId,
                websocketChannel: this.websocketChannel,
                estimatedDurationSec: this.estimatedDurationSec,
                currentStage: this.currentStage,
                progress: this.progress,
                lastUrl: this.lastUrl,
            }
            safeSetItem(SESSION_KEY, JSON.stringify(session))
        },
    },
})

/** 清除快速测试会话持久化数据（登出/主动重置场景调用） */
export function clearQuickTestSession(): void {
    safeRemoveItem(SESSION_KEY)
}
