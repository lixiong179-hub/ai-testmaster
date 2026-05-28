<template>
  <div class="steps-panel">
    <div class="panel-header">
      <h3>执行步骤</h3>
      <el-radio-group v-model="ctx.viewMode.value" size="small">
        <el-radio-button value="list">列表</el-radio-button>
        <el-radio-button value="timeline">时间轴</el-radio-button>
      </el-radio-group>
    </div>

    <div class="steps-list" v-if="ctx.viewMode.value === 'list'">
      <div
        v-for="(step, index) in ctx.executionSteps.value"
        :key="index"
        class="step-item"
        :class="{
          active: ctx.currentStepIndex.value === index,
          success: step.status === 'passed',
          failed: step.status === 'failed',
          running: step.status === 'running',
        }"
        @click="ctx.selectStep(index)"
      >
        <div class="step-number">{{ index + 1 }}</div>
        <div class="step-content">
          <div class="step-action">
            {{ step.display_action || step.description || step.action }}
          </div>
          <div class="step-target" v-if="step.target">{{ step.target }}</div>
          <div class="step-status">
            <el-tag :type="ctx.getStepStatusType(step.status)" size="small">
              {{ ctx.getStepStatusText(step.status) }}
            </el-tag>
            <span v-if="step.execution_time" class="execution-time"
              >{{ step.execution_time }}s</span
            >
          </div>
        </div>
        <div class="step-icon">
          <el-icon v-if="step.status === 'passed'"><CircleCheck /></el-icon>
          <el-icon v-else-if="step.status === 'failed'"><CircleClose /></el-icon>
          <el-icon v-else-if="step.status === 'running'" class="is-loading"><Loading /></el-icon>
          <el-icon v-else><ArrowRight /></el-icon>
        </div>
        <div class="step-actions" v-if="step.status === 'failed'">
          <el-tag
            v-if="ctx.issueTypeMap.value[index]"
            :type="ISSUE_TYPE_COLORS[ctx.issueTypeMap.value[index]]"
            size="small"
            class="issue-tag"
          >
            {{ ISSUE_TYPE_LABELS[ctx.issueTypeMap.value[index]] }}
          </el-tag>
          <el-button
            v-if="ctx.issueTypeMap.value[index] !== 'product_bug'"
            type="warning"
            size="small"
            @click.stop="ctx.handleCorrectCase(step, index)"
            >纠正用例</el-button
          >
          <el-button
            size="small"
            @click.stop="ctx.handleAnalyzeFailure(step, index)"
            :loading="ctx.analysisLoading.value"
            >分析失败</el-button
          >
        </div>
      </div>
    </div>

    <el-timeline v-else class="steps-timeline">
      <el-timeline-item
        v-for="(step, index) in ctx.executionSteps.value"
        :key="index"
        :type="ctx.getTimelineItemType(step.status)"
        :icon="ctx.getTimelineIcon(step.status)"
        :timestamp="step.timestamp"
      >
        <div
          class="timeline-step"
          :class="{ active: ctx.currentStepIndex.value === index }"
          @click="ctx.selectStep(index)"
        >
          <div class="step-action">
            {{ step.display_action || step.description || step.action }}
          </div>
          <div class="step-target" v-if="step.target">{{ step.target }}</div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script setup lang="ts">
import { CircleCheck, CircleClose, Loading, ArrowRight } from '@element-plus/icons-vue'
import {
  useTestExecution,
  ISSUE_TYPE_LABELS,
  ISSUE_TYPE_COLORS,
} from '@/composables/execution/useTestExecution'

const ctx = useTestExecution()
</script>

<style scoped>
.steps-panel {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #fafbfc;
}
.panel-header h3 {
  margin: 0;
  font-size: 14px;
  color: #303133;
}
.steps-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.step-item {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  margin-bottom: 4px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
  gap: 10px;
}
.step-item:hover {
  background: #f5f7fa;
}
.step-item.active {
  background: #ecf5ff;
  border-color: #409eff;
}
.step-item.success {
  border-left: 3px solid #67c23a;
}
.step-item.failed {
  border-left: 3px solid #f56c6c;
}
.step-item.running {
  border-left: 3px solid #409eff;
}
.step-number {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  flex-shrink: 0;
}
.step-item.active .step-number {
  background: #409eff;
  color: #fff;
}
.step-content {
  flex: 1;
  min-width: 0;
}
.step-action {
  font-size: 13px;
  color: #303133;
  line-height: 1.4;
  word-break: break-all;
}
.step-target {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
.step-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}
.execution-time {
  font-size: 11px;
  color: #909399;
}
.step-icon {
  flex-shrink: 0;
  font-size: 16px;
}
.step-icon .el-icon {
  font-size: 16px;
}
.step-item.success .step-icon {
  color: #67c23a;
}
.step-item.failed .step-icon {
  color: #f56c6c;
}
.step-item.running .step-icon {
  color: #409eff;
}
.step-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #e4e7ed;
}
.issue-tag {
  flex-shrink: 0;
}
.steps-timeline {
  padding: 16px;
}
.timeline-step {
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
}
.timeline-step:hover {
  background: #f5f7fa;
}
.timeline-step.active {
  background: #ecf5ff;
}
</style>
