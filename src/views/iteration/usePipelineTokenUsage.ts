import { ref, computed, onUnmounted, type Ref } from 'vue'
import { aiInvocationApi, usdToCny } from '@/api/aiInvocation'

/** WebSocket 推送的 Pipeline 进度消息（前向兼容：可选携带累计 Token/成本） */
export interface PipelineProgressMessage {
    type: 'pipeline_progress'
    run_id: number
    step_name: string
    status: string
    progress: number
    pipeline_status: string
    /** 后端可选推送的累计 Token 消耗（prompt + completion） */
    token_usage?: number
    /** 后端可选推送的累计成本（美元） */
    cost_usd?: number
}

/** Token 累计消耗与成本快照 */
export interface TokenUsageSnapshot {
    totalTokens: number
    totalCostCny: number
    /** 是否已获取到真实数据（避免初始 0 与"无数据"混淆） */
    loaded: boolean
}

/** 空快照，表示尚未获取数据 */
const EMPTY_SNAPSHOT: TokenUsageSnapshot = {
    totalTokens: 0,
    totalCostCny: 0,
    loaded: false,
}

/** Token 轮询间隔（ms），与 Pipeline 轮询保持一致以减少接口抖动 */
const TOKEN_POLL_INTERVAL = 5000

/**
 * Pipeline Token 消耗与成本累计 composable。
 *
 * 数据来源优先级：
 *   1. WebSocket 推送的 token_usage/cost_usd（前向兼容，后端推送时直接更新）
 *   2. 轮询 aiInvocationApi.getRunCost(runId) 兜底（WS 不可用或未推送时）
 *
 * 设计为接收 runId 的 Ref，便于在运行切换时自动失效旧请求结果。
 */
export function usePipelineTokenUsage(runId: Ref<number>) {
    const tokenUsage = ref<TokenUsageSnapshot>({ ...EMPTY_SNAPSHOT })
    const pollingTimer = ref<ReturnType<typeof setInterval> | null>(null)
    /** 进行中的请求 seq，过期 runId 的响应将被丢弃 */
    let requestSeq = 0

    /** 格式化展示文本：Token: 12,345 | 成本: ¥1.23 */
    const tokenDisplay = computed(() => {
        if (!tokenUsage.value.loaded) return 'Token: — | 成本: —'
        const tokens = tokenUsage.value.totalTokens.toLocaleString('zh-CN')
        const cost = tokenUsage.value.totalCostCny.toFixed(2)
        return `Token: ${tokens} | 成本: ¥${cost}`
    })

    /** 拉取指定运行的累计 Token/成本；过期响应（runId 切换）会被丢弃 */
    async function fetchTokenUsage(): Promise<void> {
        const id = runId.value
        if (!id) return
        const seq = ++requestSeq
        try {
            const cost = await aiInvocationApi.getRunCost(id)
            // runId 已切换或组件已发起更新的请求，丢弃过期响应
            if (seq !== requestSeq || runId.value !== id) return
            tokenUsage.value = {
                totalTokens: cost.totalTokens,
                totalCostCny: usdToCny(cost.totalCostUsd),
                loaded: true,
            }
        } catch {
            // 静默失败：进度页 Token 显示为非关键路径，不弹错误提示
            if (seq === requestSeq) tokenUsage.value = { ...EMPTY_SNAPSHOT }
        }
    }

    /** 应用 WebSocket 推送的累计 Token/成本（后端前向兼容字段） */
    function applyWsMessage(msg: PipelineProgressMessage): void {
        if (msg.type !== 'pipeline_progress') return
        if (msg.run_id !== runId.value) return
        // 后端推送了累计字段时直接采用，避免再发一次轮询请求
        if (typeof msg.token_usage === 'number' && typeof msg.cost_usd === 'number') {
            tokenUsage.value = {
                totalTokens: msg.token_usage,
                totalCostCny: usdToCny(msg.cost_usd),
                loaded: true,
            }
            return
        }
        // 未携带累计字段：触发一次拉取兜底
        void fetchTokenUsage()
    }

    function startPolling(): void {
        stopPolling()
        pollingTimer.value = setInterval(fetchTokenUsage, TOKEN_POLL_INTERVAL)
    }

    function stopPolling(): void {
        if (pollingTimer.value) {
            clearInterval(pollingTimer.value)
            pollingTimer.value = null
        }
    }

    onUnmounted(() => {
        stopPolling()
        // 使进行中的请求响应失效
        requestSeq++
    })

    return {
        tokenUsage,
        tokenDisplay,
        fetchTokenUsage,
        applyWsMessage,
        startPolling,
        stopPolling,
    }
}
