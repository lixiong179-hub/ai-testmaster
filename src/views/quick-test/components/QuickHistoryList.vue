<template>
    <el-card class="quick-history-card" shadow="never">
        <template #header>
            <div class="card-header">
                <div>
                    <div class="card-title">历史记录</div>
                    <div class="card-subtitle">完整历史记录功能即将上线，当前仅展示本次会话的任务记录</div>
                </div>
            </div>
        </template>

        <el-table
            v-if="records.length > 0"
            :data="records"
            size="small"
            border
            stripe
            style="width: 100%"
        >
            <el-table-column label="网址" min-width="200" show-overflow-tooltip>
                <template #default="{ row }">
                    <span class="history-url">{{ row.url || '-' }}</span>
                </template>
            </el-table-column>
            <el-table-column label="时间" width="170">
                <template #default="{ row }">{{ formatTime(row.startedAt) }}</template>
            </el-table-column>
            <el-table-column label="用例数" width="80" align="center">
                <template #default="{ row }">{{ row.caseCount }}</template>
            </el-table-column>
            <el-table-column label="进度" width="80" align="center">
                <template #default="{ row }">{{ row.progress }}%</template>
            </el-table-column>
            <el-table-column label="状态" width="110">
                <template #default="{ row }">
                    <el-tag :type="statusTagType(row.status)" size="small">{{ row.status || '-' }}</el-tag>
                </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
                <template #default="{ row }">
                    <el-button size="small" @click="emit('view', row.taskId)">重看结果</el-button>
                    <el-button size="small" type="primary" plain @click="emit('rerun', row.url)">
                        再次执行
                    </el-button>
                </template>
            </el-table-column>
        </el-table>

        <el-empty v-else description="暂无历史记录" :image-size="60">
            <div class="empty-hint">发起一次快速测试后将在此展示记录</div>
        </el-empty>
    </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { TagType } from '@/types/element-plus'
import { useQuickTestStore } from '@/store/quickTest'
import quickTestApi from '@/api/quickTest'
import type { QuickTestStatusResponse } from '@/api/quickTest'

interface HistoryRecord {
    taskId: number
    url: string | null
    startedAt: string | null
    caseCount: number
    progress: number
    status: string
}

const emit = defineEmits<{
    /** 重看结果：携带 taskId，父组件决定切回结果视图 */
    (e: 'view', taskId: number): void
    /** 再次执行：携带原 URL，父组件 reset 后用该 URL 重新 launch */
    (e: 'rerun', url: string | null): void
}>()

const store = useQuickTestStore()
const records = ref<HistoryRecord[]>([])

function formatTime(iso: string | null): string {
    if (!iso) return '-'
    const t = Date.parse(iso)
    if (Number.isNaN(t)) return '-'
    return new Date(t).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    })
}

function statusTagType(status: string): TagType {
    if (status === '执行完成') return 'success'
    if (status === '执行失败') return 'danger'
    if (status === '已停止') return 'info'
    return 'warning'
}

onMounted(async () => {
    const taskId = store.taskId
    if (!taskId) return
    // spec 偏离②：后端无专门历史 API，仅展示当前会话最后一次任务记录
    try {
        const res = (await quickTestApi.getStatus(taskId)) as unknown as {
            data?: QuickTestStatusResponse
        }
        const data = res?.data
        if (!data) return
        records.value = [
            {
                taskId: data.task_id,
                url: store.lastUrl,
                startedAt: data.started_at,
                caseCount: data.case_count,
                progress: data.progress,
                status: data.status,
            },
        ]
    } catch {
        // 拉取失败：降级用 store 已有字段展示一条记录
        records.value = [
            {
                taskId,
                url: store.lastUrl,
                startedAt: store.startedAt,
                caseCount: store.caseCount,
                progress: store.progress,
                status: store.isFailed ? '执行失败' : store.isCompleted ? '执行完成' : '执行中',
            },
        ]
    }
})
</script>

<style scoped lang="scss">
.quick-history-card {
    border: none;
    border-radius: 8px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
}

.card-subtitle {
    margin-top: 4px;
    color: #909399;
    font-size: 12px;
    line-height: 1.5;
}

.history-url {
    font-family: monospace;
    font-size: 12px;
    color: #606266;
}

.empty-hint {
    color: #909399;
    font-size: 12px;
}

@media (max-width: 768px) {
    .card-header {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>
