<template>
    <!-- 快速测试三态视图容器：依据 store.phase 渲染输入/进度/结果，下方挂历史记录 -->
    <div class="quick-test-page">
        <div class="quick-test-container">
            <!-- idle：URL 输入卡 -->
            <QuickInputCard
                v-if="store.isIdle"
                :default-url="store.lastUrl"
                @launched="onLaunched"
            />

            <!-- running：4 阶段进度视图 -->
            <QuickProgressView
                v-else-if="store.isRunning"
                :ws-connected="flow.wsConnected.value"
                @cancel="flow.cancelQuickTest"
            />

            <!-- completed / failed：结果视图（失败时内部渲染降级提示） -->
            <QuickResultView
                v-else
                :result-detail="flow.resultDetail.value"
                :cases="flow.cases.value"
                :defects="flow.defects.value"
                :summary="flow.summary.value"
                :explored-pages="flow.exploredPages.value"
                @view-report="flow.goToReport"
                @edit-cases="flow.goToCaseEdit"
                @download="flow.downloadReport"
                @save-to-project="flow.saveToOtherProject"
                @rerun="flow.rerunQuickTest"
                @fetch-report="flow.fetchReport"
            />

            <!-- 历史记录：始终展示，idle 态作为参考，运行/结果态折叠在底部 -->
            <QuickHistoryList
                class="quick-test-history"
                @view="onViewFromHistory"
                @rerun="onRerunFromHistory"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useQuickTestFlow } from './useQuickTestFlow'
import QuickInputCard from './components/QuickInputCard.vue'
import QuickProgressView from './components/QuickProgressView.vue'
import QuickResultView from './components/QuickResultView.vue'
import QuickHistoryList from './components/QuickHistoryList.vue'

const flow = useQuickTestFlow()
const store = flow.store

/**
 * 启动成功回调：store.launch 已在 QuickInputCard/useQuickTestEntry 内完成，
 * 此处仅触发 WS 订阅（phase 已切到 running）。
 */
function onLaunched(): void {
    flow.subscribeWebSocket()
}

/** 历史记录「重看结果」：滚动到顶部查看上方结果视图 */
function onViewFromHistory(_taskId: number): void {
    window.scrollTo({ top: 0, behavior: 'smooth' })
}

/** 历史记录「再次执行」：reset 后用原 URL 重新 launch */
async function onRerunFromHistory(url: string | null): Promise<void> {
    flow.rerunQuickTest()
    if (!url) {
        // 无原 URL：回退到输入卡，由用户回填 lastUrl 后手动提交
        return
    }
    try {
        await store.launch({ url })
        flow.subscribeWebSocket()
    } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : '再次执行失败'
        ElMessage.error(msg)
    }
}

onMounted(async () => {
    // 11.10 页面刷新恢复：从 localStorage 恢复 taskId 等会话字段
    store.restore()
    // 恢复到 running：拉一次后端状态补齐 + 订阅 WS
    // 恢复到 completed/failed：渲染结果视图（结果明细由 QuickResultView 拉报告补齐）
    if (store.isRunning) {
        try {
            await store.refreshStatus()
        } catch {
            // refreshStatus 失败不阻断：仍按已恢复的 phase 渲染
        }
        if (store.isRunning) {
            flow.subscribeWebSocket()
        }
    }
})

// phase 变化时管理 WS：进入 running 自动订阅，离开 running 自动断开
watch(
    () => store.phase,
    (next, prev) => {
        if (next === 'running' && prev !== 'running') {
            flow.subscribeWebSocket()
        } else if (next !== 'running' && prev === 'running') {
            flow.disconnectWebSocket()
        }
    }
)
</script>

<style scoped lang="scss">
.quick-test-page {
    width: 100%;
}

.quick-test-container {
    width: 100%;
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.quick-test-history {
    margin-top: 8px;
}

/* 平板：满宽 */
@media (min-width: 768px) {
    .quick-test-container {
        padding: 0 8px;
    }
}

/* 桌面：1400px 居中 */
@media (min-width: 1280px) {
    .quick-test-container {
        padding: 0 16px;
    }
}
</style>
