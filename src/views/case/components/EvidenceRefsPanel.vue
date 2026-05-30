<template>
  <div class="evidence-refs-panel">
    <!-- 需求依据 -->
    <div class="evidence-section" v-if="hasRequirements">
      <div class="section-label">
        需求依据
        <el-tag size="small" type="info" round>{{ requirementCount }}条</el-tag>
      </div>
      <div class="evidence-list">
        <div
          v-for="req in allRequirements"
          :key="'req-' + req.id"
          class="evidence-item"
        >
          <el-icon class="evidence-icon"><Document /></el-icon>
          <span class="evidence-title">{{ getEvidenceTitle(req) }}</span>
          <el-tag
            v-if="getEvidenceNo(req)"
            size="small"
            type="primary"
            effect="plain"
            round
          >
            {{ getEvidenceNo(req) }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- UI依据 -->
    <div class="evidence-section" v-if="hasUiScreens">
      <div class="section-label">
        UI依据
        <el-tag size="small" type="info" round>{{ evidenceRefs.ui_screens.length }}条</el-tag>
      </div>
      <div class="evidence-list">
        <div
          v-for="screen in evidenceRefs.ui_screens"
          :key="'ui-' + screen.id"
          class="evidence-item"
        >
          <el-icon class="evidence-icon"><Monitor /></el-icon>
          <span class="evidence-title">{{ getScreenName(screen) }}</span>
          <el-tag
            v-if="getScreenConfidence(screen) !== null"
            size="small"
            :type="confidenceTagType(getScreenConfidence(screen)!)"
            effect="plain"
            round
          >
            置信度 {{ getScreenConfidence(screen) }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 历史参考 -->
    <div class="evidence-section" v-if="hasHistoryCases">
      <div class="section-label">
        历史参考
        <el-tag size="small" type="info" round>{{ evidenceRefs.history_cases.length }}条</el-tag>
      </div>
      <div class="evidence-list">
        <div
          v-for="hc in evidenceRefs.history_cases"
          :key="'hc-' + hc.id"
          class="evidence-item history-case-item"
        >
          <el-icon class="evidence-icon"><Clock /></el-icon>
          <span class="evidence-title">{{ getHistoryCaseTitle(hc) }}</span>
          <el-tag
            v-if="hc.similarity != null"
            size="small"
            :type="similarityTagType(hc.similarity)"
            effect="plain"
            round
          >
            相似度 {{ (hc.similarity * 100).toFixed(0) }}%
          </el-tag>
          <el-tag
            size="small"
            :type="trustLevelTagType(hc.trust_level)"
            effect="plain"
            round
          >
            {{ trustLevelLabel(hc.trust_level) }}
          </el-tag>
          <el-tooltip
            v-if="hc.staleness_reason"
            :content="hc.staleness_reason"
            placement="top"
          >
            <el-icon class="staleness-icon"><Warning /></el-icon>
          </el-tooltip>
        </div>
      </div>
    </div>

    <!-- 无数据提示 -->
    <div
      class="evidence-empty"
      v-if="!hasRequirements && !hasUiScreens && !hasHistoryCases"
    >
      <el-empty description="暂无证据引用数据" :image-size="48" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Document, Monitor, Clock, Warning } from '@element-plus/icons-vue'
import type { ContextStats, ServerWarning, EvidenceRefs, EvidenceRef } from '@/store/generate/types'

const props = defineProps<{
  contextStats: ContextStats | null
  warnings: ServerWarning[]
  evidenceRefs: EvidenceRefs
}>()

/** 合并需求与需求文件列表 */
const allRequirements = computed(() => {
  const reqs: EvidenceRef[] = []
  if (props.evidenceRefs.requirements?.length) {
    reqs.push(...props.evidenceRefs.requirements)
  }
  if (props.evidenceRefs.requirement_files?.length) {
    reqs.push(...props.evidenceRefs.requirement_files)
  }
  return reqs
})

/** 需求总数 */
const requirementCount = computed(() => allRequirements.value.length)

/** 是否有需求数据 */
const hasRequirements = computed(() => requirementCount.value > 0)

/** 是否有UI数据 */
const hasUiScreens = computed(() => (props.evidenceRefs.ui_screens?.length ?? 0) > 0)

/** 是否有历史用例数据 */
const hasHistoryCases = computed(() => (props.evidenceRefs.history_cases?.length ?? 0) > 0)

/** 安全获取证据标题 */
function getEvidenceTitle(ref: EvidenceRef): string {
  if (typeof ref.title === 'string') return ref.title
  if (typeof ref.name === 'string') return ref.name
  if (typeof ref.screen_name === 'string') return ref.screen_name
  return `#${ref.id}`
}

function getEvidenceNo(ref: EvidenceRef): string | null {
  if (typeof ref.req_no === 'string') return ref.req_no
  if (typeof ref.no === 'string') return ref.no
  if (typeof ref.case_no === 'string') return ref.case_no
  if (typeof ref.code === 'string') return ref.code
  return null
}

function getScreenName(screen: EvidenceRef): string {
  if (typeof screen.screen_name === 'string') return screen.screen_name
  if (typeof screen.name === 'string') return screen.name
  if (typeof screen.title === 'string') return screen.title
  if (typeof screen.prototype_name === 'string') return screen.prototype_name
  return `页面 #${screen.id}`
}

function getScreenConfidence(screen: EvidenceRef): string | null {
  if (typeof screen.confidence === 'string') return screen.confidence
  if (typeof screen.confidence === 'number') return String(screen.confidence)
  if (typeof screen.match_score === 'number') return String(screen.match_score)
  return null
}

function confidenceTagType(confidence: string | null): 'success' | 'warning' | 'info' | 'danger' {
  if (!confidence) return 'info'
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    explicit: 'success',
    matched: 'warning',
    adjacent: 'info',
    ui_file: 'warning',
  }
  return map[confidence] ?? 'info'
}

/** 安全获取历史用例标题 */
function getHistoryCaseTitle(hc: {
  id: number
  case_no?: string
  design_tag?: string
  similarity?: number
  trust_level: string
  staleness_reason: string
}): string {
  if (hc.design_tag) return hc.design_tag
  if (hc.case_no) return hc.case_no
  return `用例 #${hc.id}`
}

function similarityTagType(similarity: number): 'success' | 'warning' | 'danger' {
  if (similarity >= 0.8) return 'success'
  if (similarity >= 0.5) return 'warning'
  return 'danger'
}

/** 可信度标签类型 */
function trustLevelTagType(trustLevel: string): 'success' | 'warning' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'danger'> = {
    high: 'success',
    medium: 'warning',
    low: 'danger',
  }
  return map[trustLevel] ?? 'warning'
}

/** 可信度标签文字 */
function trustLevelLabel(trustLevel: string): string {
  const map: Record<string, string> = {
    high: '高可信',
    medium: '中可信',
    low: '低可信',
  }
  return map[trustLevel] ?? trustLevel
}
</script>

<style scoped>
.evidence-refs-panel {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fff;
}

.evidence-section {
  margin-bottom: 12px;
}

.evidence-section:last-child {
  margin-bottom: 0;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.evidence-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.evidence-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 4px;
  background: #f8f9fb;
  font-size: 13px;
  transition: background 0.2s;
}

.evidence-item:hover {
  background: #ecf5ff;
}

.evidence-icon {
  color: #909399;
  flex-shrink: 0;
}

.evidence-title {
  flex: 1;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 320px;
}

.history-case-item {
  flex-wrap: nowrap;
}

.staleness-icon {
  color: #e6a23c;
  flex-shrink: 0;
  cursor: help;
}

.evidence-empty {
  padding: 8px 0;
}
</style>
