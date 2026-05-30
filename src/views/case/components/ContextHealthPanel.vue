<template>
  <div class="context-health-panel">
    <!-- 完整性评分 -->
    <div class="health-score-section">
      <div class="score-ring">
        <el-progress
          type="circle"
          :percentage="completenessScore"
          :color="scoreColor"
          :width="80"
          :stroke-width="6"
        >
          <template #default>
            <span class="score-value" :style="{ color: scoreColor }">
              {{ completenessScore }}
            </span>
          </template>
        </el-progress>
      </div>
      <div class="score-info">
        <div class="score-title">上下文完整性评分</div>
        <div class="score-desc">
          <span v-if="completenessScore >= 80">上下文充分，可正常生成</span>
          <span v-else-if="completenessScore >= 50">上下文部分缺失，生成质量可能受影响</span>
          <span v-else>上下文严重不足，建议补齐后再生成</span>
        </div>
        <div class="score-meta" v-if="contextStats">
          <el-tag size="small" type="info">策略: {{ contextStats.strategy }}</el-tag>
          <el-tag size="small" type="info" v-if="contextStats.requirement_strategy">
            需求策略: {{ contextStats.requirement_strategy }}
          </el-tag>
          <el-tag size="small" type="info" v-if="contextStats.ui_strategy">
            UI策略: {{ contextStats.ui_strategy }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 缺失上下文 -->
    <div
      class="missing-context-section"
      v-if="hasMissingContext || hasLowConfidence"
    >
      <div class="section-label">缺失与低置信度</div>
      <div class="missing-tags" v-if="hasMissingContext">
        <span class="tag-group-label">缺失核心上下文:</span>
        <el-tag
          v-for="(item, idx) in contextStats?.missing_core_context ?? []"
          :key="'mc-' + idx"
          size="small"
          type="danger"
          effect="plain"
          class="context-tag"
        >
          {{ item }}
        </el-tag>
      </div>
      <div class="missing-tags" v-if="hasLowConfidence">
        <span class="tag-group-label">低置信度原因:</span>
        <el-tag
          v-for="(item, idx) in contextStats?.low_confidence_reasons ?? []"
          :key="'lc-' + idx"
          size="small"
          type="warning"
          effect="plain"
          class="context-tag"
        >
          {{ item }}
        </el-tag>
      </div>
    </div>

    <!-- 后端 warnings 分组展示 -->
    <div class="warnings-section" v-if="groupedWarnings.danger.length > 0 || groupedWarnings.warning.length > 0 || groupedWarnings.info.length > 0">
      <div class="section-label">后端警告</div>
      <!-- 阻断类 -->
      <div class="warning-group" v-if="groupedWarnings.danger.length > 0">
        <div class="warning-group-header danger-header">
          <el-icon><WarningFilled /></el-icon>
          <span>阻断类 ({{ groupedWarnings.danger.length }})</span>
        </div>
        <el-alert
          v-for="(w, idx) in groupedWarnings.danger"
          :key="'d-' + idx"
          type="error"
          :closable="false"
          show-icon
          class="warning-alert"
        >
          <template #title>{{ w.message }}</template>
          <template #default v-if="w.detail && Object.keys(w.detail).length > 0">
            <div class="warning-detail">
              <span v-for="(val, key) in w.detail" :key="String(key)">
                {{ key }}: {{ val }}
              </span>
            </div>
          </template>
        </el-alert>
      </div>
      <!-- 风险类 -->
      <div class="warning-group" v-if="groupedWarnings.warning.length > 0">
        <div class="warning-group-header warning-header">
          <el-icon><Warning /></el-icon>
          <span>风险类 ({{ groupedWarnings.warning.length }})</span>
        </div>
        <el-alert
          v-for="(w, idx) in groupedWarnings.warning"
          :key="'w-' + idx"
          type="warning"
          :closable="false"
          show-icon
          class="warning-alert"
        >
          <template #title>{{ w.message }}</template>
          <template #default v-if="w.detail && Object.keys(w.detail).length > 0">
            <div class="warning-detail">
              <span v-for="(val, key) in w.detail" :key="String(key)">
                {{ key }}: {{ val }}
              </span>
            </div>
          </template>
        </el-alert>
      </div>
      <!-- 提示类 -->
      <div class="warning-group" v-if="groupedWarnings.info.length > 0">
        <div class="warning-group-header info-header">
          <el-icon><InfoFilled /></el-icon>
          <span>提示类 ({{ groupedWarnings.info.length }})</span>
        </div>
        <el-alert
          v-for="(w, idx) in groupedWarnings.info"
          :key="'i-' + idx"
          type="info"
          :closable="false"
          show-icon
          class="warning-alert"
        >
          <template #title>{{ w.message }}</template>
          <template #default v-if="w.detail && Object.keys(w.detail).length > 0">
            <div class="warning-detail">
              <span v-for="(val, key) in w.detail" :key="String(key)">
                {{ key }}: {{ val }}
              </span>
            </div>
          </template>
        </el-alert>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { WarningFilled, Warning, InfoFilled } from '@element-plus/icons-vue'
import type { ContextStats, ServerWarning, EvidenceRefs } from '@/store/generate/types'

const props = defineProps<{
  contextStats: ContextStats | null
  warnings: ServerWarning[]
  evidenceRefs: EvidenceRefs | null
}>()

/** 完整性评分，空值兜底为0 */
const completenessScore = computed(() => {
  return props.contextStats?.completeness_score ?? 0
})

/** 评分颜色：>=80绿、50-79黄、<50红 */
const scoreColor = computed(() => {
  const score = completenessScore.value
  if (score >= 80) return '#67c23a'
  if (score >= 50) return '#e6a23c'
  return '#f56c6c'
})

/** 是否有缺失核心上下文 */
const hasMissingContext = computed(() => {
  return (props.contextStats?.missing_core_context?.length ?? 0) > 0
})

/** 是否有低置信度原因 */
const hasLowConfidence = computed(() => {
  return (props.contextStats?.low_confidence_reasons?.length ?? 0) > 0
})

/** 阻断类 warning code 集合 */
const DANGER_CODES = new Set([
  'REQUIREMENT_NOT_FOUND',
  'UI_AUTOMATION_DEGRADED',
  'CONTEXT_COMPLETENESS_LOW',
])

/** 风险类 warning code 集合 */
const WARNING_CODES = new Set([
  'HISTORY_POTENTIALLY_STALE',
  'HISTORY_LOW_TRUST_FILTERED',
  'UI_NO_MATCH',
  'UI_PARTIAL_MATCH',
  'REQUIREMENT_TRIMMED_BY_KEYWORDS',
  'UI_REQUIRED_ELEMENT_MISSING',
  'UI_SPEC_MISSING',
])

/** 按严重程度分组 warnings */
const groupedWarnings = computed(() => {
  const danger: ServerWarning[] = []
  const warning: ServerWarning[] = []
  const info: ServerWarning[] = []

  for (const w of props.warnings) {
    // CONTEXT_COMPLETENESS_LOW 仅在 score < 50 时归为阻断类
    if (w.code === 'CONTEXT_COMPLETENESS_LOW') {
      if (completenessScore.value < 50) {
        danger.push(w)
      } else {
        warning.push(w)
      }
    } else if (DANGER_CODES.has(w.code)) {
      danger.push(w)
    } else if (WARNING_CODES.has(w.code)) {
      warning.push(w)
    } else {
      info.push(w)
    }
  }

  return { danger, warning, info }
})
</script>

<style scoped>
.context-health-panel {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fff;
}

.health-score-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.score-ring {
  flex-shrink: 0;
}

.score-value {
  font-size: 20px;
  font-weight: 700;
}

.score-info {
  flex: 1;
  min-width: 0;
}

.score-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.score-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #606266;
}

.score-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.missing-context-section {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fdf6ec;
  border-radius: 6px;
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.missing-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.missing-tags:last-child {
  margin-bottom: 0;
}

.tag-group-label {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.context-tag {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.warnings-section {
  margin-top: 4px;
}

.warning-group {
  margin-bottom: 8px;
}

.warning-group:last-child {
  margin-bottom: 0;
}

.warning-group-header {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}

.danger-header {
  color: #f56c6c;
}

.warning-header {
  color: #e6a23c;
}

.info-header {
  color: #909399;
}

.warning-alert {
  margin-bottom: 4px;
}

.warning-alert:last-child {
  margin-bottom: 0;
}

.warning-detail {
  font-size: 12px;
  color: #606266;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
