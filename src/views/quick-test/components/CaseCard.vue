<template>
    <div class="case-card" :class="`is-${caseData.status}`">
        <!-- 标题行：用例名 + 状态标签 + 耗时 -->
        <div class="case-header">
            <span class="case-title">{{ caseData.title }}</span>
            <el-tag :type="statusTagType" size="small" class="case-status-tag">
                {{ statusText }}
            </el-tag>
            <span v-if="caseData.duration_sec != null" class="case-duration">
                耗时 {{ formatSec(caseData.duration_sec) }}
            </span>
        </div>

        <!-- 步骤列表：每步标注元素验证状态 -->
        <div v-if="caseData.steps.length > 0" class="case-steps">
            <div v-for="step in caseData.steps" :key="step.step" class="case-step">
                <span class="step-no">{{ step.step }}</span>
                <div class="step-body">
                    <div class="step-desc">{{ step.description }}</div>
                    <div class="step-action">
                        动作：{{ step.action }}
                        <el-tag
                            v-if="step.target_element"
                            size="small"
                            type="info"
                            effect="plain"
                            class="step-target"
                        >
                            {{ step.target_element }}
                        </el-tag>
                        <el-icon v-if="step.element_verified === true" class="step-verified ok">
                            <CircleCheckFilled />
                        </el-icon>
                        <el-icon v-else-if="step.element_verified === false" class="step-verified warn">
                            <WarningFilled />
                        </el-icon>
                    </div>
                    <div v-if="step.expected_result" class="step-expected">
                        预期：{{ step.expected_result }}
                    </div>
                    <div v-if="step.actual_result" class="step-actual" :class="{ 'is-fail': isFail }">
                        实际：{{ step.actual_result }}
                    </div>
                </div>
            </div>
        </div>

        <!-- 预期 vs 实际（报告用例无步骤时展示） -->
        <div v-else class="case-result">
            <div v-if="caseData.expected_result" class="result-row">
                <span class="result-label">预期</span>
                <span class="result-value">{{ caseData.expected_result }}</span>
            </div>
            <div v-if="caseData.actual_result" class="result-row" :class="{ 'is-fail': isFail }">
                <span class="result-label">实际</span>
                <span class="result-value">{{ caseData.actual_result }}</span>
            </div>
        </div>

        <!-- 失败原因 -->
        <div v-if="caseData.failure_reason" class="case-failure-reason">
            <el-icon><WarningFilled /></el-icon>
            <span>{{ caseData.failure_reason }}</span>
        </div>

        <!-- 失败截图：可放大预览 -->
        <div v-if="failureScreenshot" class="case-screenshot">
            <el-image
                :src="failureScreenshot"
                :preview-src-list="[failureScreenshot]"
                :preview-teleported="true"
                fit="cover"
                class="screenshot-img"
            />
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheckFilled, WarningFilled } from '@element-plus/icons-vue'
import type { CaseData } from '../quickTestTypes'

const props = defineProps<{
    caseData: CaseData
}>()

const isFail = computed(() => props.caseData.status === 'failed')

const statusTagType = computed<'success' | 'danger' | 'warning' | 'info'>(() => {
    switch (props.caseData.status) {
        case 'passed':
            return 'success'
        case 'failed':
            return 'danger'
        case 'running':
            return 'warning'
        default:
            return 'info'
    }
})

const statusText = computed(() => {
    switch (props.caseData.status) {
        case 'passed':
            return '✓ 通过'
        case 'failed':
            return '✗ 失败'
        case 'running':
            return '⏳ 进行中'
        default:
            return '○ 待执行'
    }
})

/** 失败截图：优先取首个失败步骤截图，回退用例级无截图字段 */
const failureScreenshot = computed(() => {
    if (isFail.value) {
        const failStep = props.caseData.steps.find((s) => s.screenshot)
        if (failStep?.screenshot) return failStep.screenshot
    }
    return ''
})

function formatSec(sec: number): string {
    if (sec < 60) return `${sec}s`
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}分${s}秒`
}
</script>

<style scoped lang="scss">
.case-card {
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    padding: 12px 16px;
    background: #fff;
    transition: border-color 0.2s;
}

.case-card.is-failed {
    border-color: #f56c6c;
    background: #fef0f0;
}

.case-card.is-passed {
    border-color: #b3e19d;
}

.case-header {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.case-title {
    font-size: 14px;
    font-weight: 600;
    color: #1f2d3d;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.case-status-tag {
    flex-shrink: 0;
}

.case-duration {
    font-size: 12px;
    color: #909399;
    flex-shrink: 0;
}

.case-steps {
    margin-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.case-step {
    display: flex;
    gap: 8px;
}

.step-no {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #f0f2f5;
    color: #606266;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.step-body {
    flex: 1;
    min-width: 0;
}

.step-desc {
    font-size: 13px;
    color: #303133;
}

.step-action {
    font-size: 12px;
    color: #606266;
    margin-top: 2px;
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}

.step-target {
    font-family: monospace;
}

.step-verified {
    font-size: 14px;
}

.step-verified.ok {
    color: #67c23a;
}

.step-verified.warn {
    color: #e6a23c;
}

.step-expected,
.step-actual {
    font-size: 12px;
    color: #606266;
    margin-top: 2px;
}

.step-actual.is-fail,
.result-row.is-fail .result-value {
    color: #f56c6c;
}

.case-result {
    margin-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.result-row {
    display: flex;
    gap: 8px;
    font-size: 13px;
}

.result-label {
    color: #909399;
    min-width: 32px;
}

.result-value {
    color: #303133;
    flex: 1;
}

.case-failure-reason {
    margin-top: 8px;
    padding: 6px 10px;
    background: #fef0f0;
    border-radius: 4px;
    color: #f56c6c;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.case-screenshot {
    margin-top: 8px;
}

.screenshot-img {
    width: 160px;
    height: 100px;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
    cursor: zoom-in;
}
</style>
