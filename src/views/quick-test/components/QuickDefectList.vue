<template>
    <el-card class="quick-defect-card" shadow="never">
        <template #header>
            <div class="card-title">
                缺陷清单
                <el-tag v-if="sortedDefects.length > 0" size="small" type="danger" class="count-tag">
                    {{ sortedDefects.length }}
                </el-tag>
            </div>
        </template>

        <div v-if="sortedDefects.length > 0" class="defect-list">
            <div
                v-for="defect in sortedDefects"
                :key="defect.bug_no"
                class="defect-item"
                :class="`sev-${defect.severity}`"
            >
                <div class="defect-head">
                    <el-tag :type="severityTagType(defect.severity)" size="small" effect="dark">
                        {{ severityLabel(defect.severity) }}
                    </el-tag>
                    <span class="defect-title">{{ defect.title }}</span>
                    <span class="defect-bug-no">{{ defect.bug_no }}</span>
                </div>
                <div class="defect-meta">
                    <span v-if="defect.module">模块：{{ defect.module }}</span>
                    <span v-if="defect.ux_category">分类：{{ defect.ux_category }}</span>
                </div>
                <div v-if="defect.reproduction_steps" class="defect-steps">
                    <span class="steps-label">复现步骤：</span>
                    <span class="steps-text">{{ defect.reproduction_steps }}</span>
                </div>
                <div v-if="defect.screenshot" class="defect-screenshot">
                    <el-image
                        :src="defect.screenshot"
                        :preview-src-list="[defect.screenshot]"
                        :preview-teleported="true"
                        fit="cover"
                        class="defect-img"
                    />
                </div>
                <div v-if="defect.fix_suggestion" class="defect-fix">
                    <span class="fix-label">修复建议：</span>{{ defect.fix_suggestion }}
                </div>
                <div class="defect-actions">
                    <el-button
                        type="danger"
                        size="small"
                        plain
                        @click="onCreateBug(defect)"
                    >
                        创建 Bug
                    </el-button>
                </div>
            </div>
        </div>

        <el-empty v-else description="暂无缺陷" :image-size="60" />
    </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { DefectData, DefectSeverity } from '../quickTestTypes'
import { SEVERITY_LABELS, SEVERITY_TAG_TYPE } from '../quickTestTypes'

const props = defineProps<{
    defects: DefectData[]
}>()

const emit = defineEmits<{
    /** 创建 Bug：携带关联 case_id，由父组件决定跳转或降级提示 */
    (e: 'create-bug', defect: DefectData): void
}>()

/** 缺陷排序：severity 升序（P0=1 置顶） */
const sortedDefects = computed(() => {
    const list = [...props.defects]
    return list.sort((a, b) => a.severity - b.severity)
})

function severityLabel(sev: DefectSeverity): string {
    return SEVERITY_LABELS[sev] || `P${4 - sev + 1}`
}

function severityTagType(sev: DefectSeverity): typeof SEVERITY_TAG_TYPE[DefectSeverity] {
    return SEVERITY_TAG_TYPE[sev] || 'info'
}

/**
 * 创建 Bug：Bug 创建页路由若不存在则降级提示。
 * 仍 emit 给父组件，由父组件决定跳转；本地兜底提示。
 */
function onCreateBug(defect: DefectData): void {
    emit('create-bug', defect)
    // 兜底：路由 /home/bug/create 尚未落地时提示
    ElMessage.info('Bug 创建入口即将上线')
}
</script>

<style scoped lang="scss">
.quick-defect-card {
    border: none;
    border-radius: 8px;
    height: 100%;
}

.card-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
    display: flex;
    align-items: center;
    gap: 8px;
}

.count-tag {
    margin-left: 4px;
}

.defect-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.defect-item {
    border: 1px solid #e4e7ed;
    border-left: 4px solid #909399;
    border-radius: 6px;
    padding: 10px 12px;
    background: #fff;
}

.defect-item.sev-1 {
    border-left-color: #f56c6c;
    background: #fef0f0;
}

.defect-item.sev-2 {
    border-left-color: #e6a23c;
}

.defect-item.sev-3 {
    border-left-color: #909399;
}

.defect-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.defect-title {
    font-size: 14px;
    font-weight: 600;
    color: #1f2d3d;
    flex: 1;
    min-width: 0;
}

.defect-bug-no {
    font-size: 12px;
    color: #909399;
    font-family: monospace;
}

.defect-meta {
    font-size: 12px;
    color: #606266;
    margin-top: 4px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}

.defect-steps {
    font-size: 12px;
    color: #606266;
    margin-top: 6px;
    line-height: 1.5;
}

.steps-label {
    color: #909399;
}

.defect-screenshot {
    margin-top: 6px;
}

.defect-img {
    width: 140px;
    height: 90px;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
    cursor: zoom-in;
}

.defect-fix {
    font-size: 12px;
    color: #606266;
    margin-top: 6px;
    line-height: 1.5;
}

.fix-label {
    color: #67c23a;
    font-weight: 600;
}

.defect-actions {
    margin-top: 8px;
    display: flex;
    justify-content: flex-end;
}
</style>
