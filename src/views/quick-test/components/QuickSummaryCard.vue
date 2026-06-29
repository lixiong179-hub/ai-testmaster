<template>
    <el-card class="quick-summary-card" shadow="never">
        <template #header>
            <div class="card-title">报告摘要</div>
        </template>

        <div v-if="summary" class="summary-body">
            <!-- 通过率环形图 -->
            <div class="summary-ring">
                <el-progress
                    type="circle"
                    :percentage="summary.pass_rate"
                    :width="120"
                    :color="ringColor"
                />
                <div class="ring-label">通过率</div>
            </div>

            <!-- 统计指标 -->
            <div class="summary-stats">
                <div class="stat-item">
                    <div class="stat-value">{{ summary.total }}</div>
                    <div class="stat-label">用例总数</div>
                </div>
                <div class="stat-item is-pass">
                    <div class="stat-value">{{ summary.passed }}</div>
                    <div class="stat-label">通过</div>
                </div>
                <div class="stat-item is-fail">
                    <div class="stat-value">{{ summary.failed }}</div>
                    <div class="stat-label">失败</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{{ formatDuration(summary.duration_sec) }}</div>
                    <div class="stat-label">耗时</div>
                </div>
            </div>

            <!-- 缺陷严重度分布 -->
            <div class="severity-dist">
                <div class="dist-title">缺陷严重度分布</div>
                <div class="dist-list">
                    <div
                        v-for="item in severityItems"
                        :key="item.key"
                        class="dist-item"
                        :class="`sev-${item.key}`"
                    >
                        <el-tag :type="item.tagType" size="small" effect="dark">{{ item.label }}</el-tag>
                        <span class="dist-count">{{ item.count }}</span>
                    </div>
                </div>
            </div>
        </div>

        <el-empty v-else description="暂无摘要数据" :image-size="60" />
    </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SummaryStats, DefectSeverity } from '../quickTestTypes'
import { SEVERITY_LABELS, SEVERITY_TAG_TYPE } from '../quickTestTypes'

const props = defineProps<{
    summary: SummaryStats | null
}>()

const ringColor = computed(() => {
    const rate = props.summary?.pass_rate ?? 0
    if (rate >= 80) return '#67c23a'
    if (rate >= 50) return '#e6a23c'
    return '#f56c6c'
})

const severityItems = computed(() => {
    const dist = props.summary?.severity_dist ?? { p0: 0, p1: 0, p2: 0, p3: 0 }
    const list: Array<{ key: string; severity: DefectSeverity; label: string; count: number; tagType: typeof SEVERITY_TAG_TYPE[DefectSeverity] }> = [
        { key: 'p0', severity: 1, label: SEVERITY_LABELS[1], count: dist.p0, tagType: SEVERITY_TAG_TYPE[1] },
        { key: 'p1', severity: 2, label: SEVERITY_LABELS[2], count: dist.p1, tagType: SEVERITY_TAG_TYPE[2] },
        { key: 'p2', severity: 3, label: SEVERITY_LABELS[3], count: dist.p2, tagType: SEVERITY_TAG_TYPE[3] },
        { key: 'p3', severity: 4, label: SEVERITY_LABELS[4], count: dist.p3, tagType: SEVERITY_TAG_TYPE[4] },
    ]
    // P0 置顶：severity 升序
    return list.sort((a, b) => a.severity - b.severity)
})

function formatDuration(sec: number): string {
    if (!sec || sec <= 0) return '-'
    if (sec < 60) return `${sec}s`
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}分${s}秒`
}
</script>

<style scoped lang="scss">
.quick-summary-card {
    border: none;
    border-radius: 8px;
    height: 100%;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
}

.summary-body {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.summary-ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}

.ring-label {
    font-size: 12px;
    color: #7a8594;
}

.summary-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}

.stat-item {
    text-align: center;
    padding: 8px 4px;
    background: #f7f8fa;
    border-radius: 6px;
}

.stat-item.is-pass {
    background: #f0f9eb;
}

.stat-item.is-fail {
    background: #fef0f0;
}

.stat-value {
    font-size: 18px;
    font-weight: 700;
    color: #1f2d3d;
}

.stat-item.is-pass .stat-value {
    color: #67c23a;
}

.stat-item.is-fail .stat-value {
    color: #f56c6c;
}

.stat-label {
    font-size: 12px;
    color: #7a8594;
    margin-top: 2px;
}

.severity-dist {
    border-top: 1px dashed #e4e7ed;
    padding-top: 12px;
}

.dist-title {
    font-size: 13px;
    font-weight: 600;
    color: #606266;
    margin-bottom: 8px;
}

.dist-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.dist-item {
    display: flex;
    align-items: center;
    gap: 4px;
}

.dist-count {
    font-size: 14px;
    font-weight: 600;
    color: #1f2d3d;
}

.dist-item.sev-p0 .dist-count {
    color: #f56c6c;
}

@media (max-width: 768px) {
    .summary-stats {
        grid-template-columns: repeat(2, 1fr);
    }
}
</style>
