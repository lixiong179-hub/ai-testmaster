<template>
  <transition name="panel-slide">
    <div v-if="visible" class="flow-completeness-panel">
      <div class="panel-header">
        <span class="panel-title">流程完整度</span>
        <el-button
          size="small"
          text
          class="panel-close-btn"
          @click="$emit('update:visible', false)"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>

      <!-- 完整度评分 -->
      <div class="score-section">
        <div class="score-ring" :class="scoreLevel">
          <span class="score-value">{{ stats.completenessScore }}</span>
        </div>
        <span class="score-label">{{ scoreLabel }}</span>
      </div>

      <!-- 节点统计 -->
      <div class="stats-section">
        <div class="section-title">节点统计</div>
        <div class="stat-grid">
          <div class="stat-item stat-main">
            <span class="stat-dot"></span>
            <span class="stat-name">主干</span>
            <span class="stat-count">{{ stats.mainNodes }}</span>
          </div>
          <div class="stat-item stat-branch">
            <span class="stat-dot"></span>
            <span class="stat-name">分支</span>
            <span class="stat-count">{{ stats.branchNodes }}</span>
          </div>
          <div class="stat-item stat-exception">
            <span class="stat-dot"></span>
            <span class="stat-name">异常</span>
            <span class="stat-count">{{ stats.exceptionNodes }}</span>
          </div>
          <div class="stat-item stat-bypass">
            <span class="stat-dot"></span>
            <span class="stat-name">弹窗</span>
            <span class="stat-count">{{ stats.bypassNodes }}</span>
          </div>
        </div>
      </div>

      <!-- 连线统计 -->
      <div class="stats-section">
        <div class="section-title">连线统计</div>
        <div class="stat-grid">
          <div class="stat-item stat-main">
            <span class="stat-dot"></span>
            <span class="stat-name">正常</span>
            <span class="stat-count">{{ stats.normalEdges }}</span>
          </div>
          <div class="stat-item stat-branch">
            <span class="stat-dot"></span>
            <span class="stat-name">分支</span>
            <span class="stat-count">{{ stats.branchEdges }}</span>
          </div>
          <div class="stat-item stat-exception">
            <span class="stat-dot"></span>
            <span class="stat-name">异常</span>
            <span class="stat-count">{{ stats.exceptionEdges }}</span>
          </div>
          <div class="stat-item stat-bypass">
            <span class="stat-dot"></span>
            <span class="stat-name">弹窗</span>
            <span class="stat-count">{{ stats.bypassEdges }}</span>
          </div>
        </div>
      </div>

      <!-- 问题提示 -->
      <div v-if="issues.length > 0" class="issues-section">
        <div class="section-title">待处理</div>
        <div class="issue-list">
          <div
            v-for="issue in issues"
            :key="issue.type + '-' + issue.message"
            class="issue-item"
            :class="'issue-' + issue.type"
          >
            <el-icon v-if="issue.type === 'error'"><CircleClose /></el-icon>
            <el-icon v-else><WarningFilled /></el-icon>
            <span>{{ issue.message }}</span>
          </div>
        </div>
      </div>

      <!-- 无问题提示 -->
      <div v-else-if="stats.totalNodes > 0" class="all-clear">
        <el-icon><CircleCheck /></el-icon>
        <span>流程完整，可继续生成</span>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Close, CircleClose, WarningFilled, CircleCheck } from '@element-plus/icons-vue'
import type { FlowStats, FlowStatsIssue } from '@/composables/useFlowStats'

const props = defineProps<{
  visible: boolean
  stats: FlowStats
  issues: FlowStatsIssue[]
}>()

defineEmits<{
  'update:visible': [value: boolean]
}>()

const scoreLevel = computed(() => {
  const s = props.stats.completenessScore
  if (s >= 80) return 'score-good'
  if (s >= 50) return 'score-warn'
  return 'score-bad'
})

const scoreLabel = computed(() => {
  const s = props.stats.completenessScore
  if (s >= 80) return '完整度良好'
  if (s >= 50) return '需要调整'
  return '存在严重缺失'
})
</script>

<style scoped>
.flow-completeness-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 20;
  width: 220px;
  max-height: calc(100% - 24px);
  overflow-y: auto;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.panel-close-btn {
  padding: 4px;
}

/* 评分环 */
.score-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
}

.score-ring {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 3px solid;
}

.score-ring.score-good {
  border-color: #67c23a;
  background: rgba(103, 194, 58, 0.08);
}

.score-ring.score-warn {
  border-color: #e6a23c;
  background: rgba(230, 162, 60, 0.08);
}

.score-ring.score-bad {
  border-color: #f56c6c;
  background: rgba(245, 108, 108, 0.08);
}

.score-value {
  font-size: 22px;
  font-weight: 700;
}

.score-good .score-value {
  color: #67c23a;
}

.score-warn .score-value {
  color: #e6a23c;
}

.score-bad .score-value {
  color: #f56c6c;
}

.score-label {
  font-size: 12px;
  color: #909399;
}

/* 统计区段 */
.stats-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  padding-bottom: 4px;
  border-bottom: 1px solid #f0f2f5;
}

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
}

.stat-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-name {
  color: #606266;
  flex: 1;
}

.stat-count {
  font-weight: 600;
  color: #303133;
}

.stat-main {
  background: #eff6ff;
}

.stat-main .stat-dot {
  background: #409eff;
}

.stat-branch {
  background: #f0f9eb;
}

.stat-branch .stat-dot {
  background: #67c23a;
}

.stat-exception {
  background: #fef0f0;
}

.stat-exception .stat-dot {
  background: #f56c6c;
}

.stat-bypass {
  background: #fdf6ec;
}

.stat-bypass .stat-dot {
  background: #e6a23c;
}

/* 问题区段 */
.issues-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.issue-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
}

.issue-item .el-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.issue-error {
  background: #fef0f0;
  color: #c45656;
}

.issue-warning {
  background: #fdf6ec;
  color: #b88230;
}

/* 全部通过 */
.all-clear {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  border-radius: 8px;
  background: #f0f9eb;
  color: #67c23a;
  font-size: 13px;
  font-weight: 500;
}

/* 面板滑入/滑出动画 */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition:
    transform 0.25s ease,
    opacity 0.25s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
