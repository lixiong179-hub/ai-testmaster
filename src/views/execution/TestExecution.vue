<template>
  <div class="test-execution-page">
    <div class="page-header">
      <div class="header-left">
        <el-button @click="ctx.goBack" icon="ArrowLeft">返回</el-button>
        <h2 class="page-title">测试执行 - {{ ctx.taskInfo.value?.task_name || '加载中...' }}</h2>
      </div>
      <div class="header-right">
        <div class="execution-options">
          <el-select
            v-model="ctx.targetEnv.value"
            placeholder="选择环境"
            size="default"
            class="env-selector"
            :disabled="!ctx.envOptions.value.length"
          >
            <el-option
              v-for="env in ctx.envOptions.value"
              :key="env.name"
              :label="`${env.name} (${env.url})`"
              :value="env.name"
            >
              <div class="env-option">
                <span class="env-name">{{ env.name }}</span
                ><span class="env-url">{{ env.url }}</span
                ><span class="env-account" v-if="env.username"
                  >账号: {{ env.username }} / 密码: ••••••</span
                >
              </div>
            </el-option>
          </el-select>
          <el-tooltip content="执行前自动初始化（启动浏览器+导航+登录）" placement="bottom">
            <el-switch
              v-model="ctx.autoInitEnabled.value"
              active-text="自动初始化"
              inactive-text="跳过初始化"
              inline-prompt
              class="init-switch"
            />
          </el-tooltip>
        </div>
        <div class="journey-actions">
          <el-button plain @click="ctx.goToTaskList">任务列表</el-button>
          <el-button plain @click="ctx.goToTestPointManagement">测试点管理</el-button>
        </div>
        <el-button-group v-if="ctx.executionStatus.value">
          <el-button
            v-if="ctx.executionStatus.value.status === 'running'"
            type="warning"
            @click="ctx.pauseExecution"
            :loading="ctx.controlLoading.value"
            ><el-icon><VideoPause /></el-icon>暂停</el-button
          >
          <el-button
            v-if="ctx.executionStatus.value.status === 'paused'"
            type="success"
            @click="ctx.resumeExecution"
            :loading="ctx.controlLoading.value"
            ><el-icon><VideoPlay /></el-icon>恢复</el-button
          >
          <el-button
            v-if="['running', 'paused'].includes(ctx.executionStatus.value.status)"
            type="danger"
            @click="ctx.stopExecution"
            :loading="ctx.controlLoading.value"
            ><el-icon><CircleClose /></el-icon>停止</el-button
          >
          <el-button
            v-if="
              ['pending', 'stopped', 'completed', 'failed'].includes(
                ctx.executionStatus.value.status
              )
            "
            type="primary"
            @click="ctx.startExecution"
            :loading="ctx.controlLoading.value"
            ><el-icon><VideoPlay /></el-icon>开始执行</el-button
          >
        </el-button-group>
        <el-button @click="ctx.showConfigDialog.value = true" icon="Setting">
          可见模式配置
        </el-button>
      </div>
    </div>

    <div class="execution-progress" v-if="ctx.executionStatus.value">
      <el-progress
        :percentage="ctx.progressPercentage.value"
        :status="ctx.progressStatus.value"
        :stroke-width="20"
        :text-inside="true"
      >
        <template #default="{ percentage }">
          <span class="progress-text"
            >{{ ctx.executionStatus.value.current_step || 0 }} /
            {{ ctx.executionStatus.value.total_steps || 0 }} 步骤 ({{ percentage }}%)</span
          >
        </template>
      </el-progress>
      <div class="progress-info">
        <el-tag :type="ctx.statusTagType.value">{{ ctx.statusText.value }}</el-tag>
        <span v-if="ctx.executionStatus.value.estimated_time_remaining" class="time-remaining"
          >预计剩余: {{ ctx.formatTime(ctx.executionStatus.value.estimated_time_remaining) }}</span
        >
      </div>
    </div>

    <div class="main-content">
      <ExecutionStepsPanel />

      <div class="screenshot-panel">
        <div class="panel-header">
          <h3>执行截图</h3>
          <el-radio-group v-model="ctx.screenshotType.value" size="small">
            <el-radio-button value="before">执行前</el-radio-button>
            <el-radio-button value="after">执行后</el-radio-button>
          </el-radio-group>
        </div>
        <div class="screenshot-container">
          <div v-if="ctx.currentScreenshot.value" class="screenshot-wrapper">
            <img
              :src="ctx.currentScreenshot.value"
              alt="执行截图"
              class="screenshot-image"
              @click="ctx.showScreenshotFullscreen.value = true"
            />
            <div
              v-if="ctx.currentStep.value?.element_highlight"
              class="element-highlight"
              :style="{
                left: ctx.currentStep.value.element_highlight.x + 'px',
                top: ctx.currentStep.value.element_highlight.y + 'px',
                width: ctx.currentStep.value.element_highlight.width + 'px',
                height: ctx.currentStep.value.element_highlight.height + 'px',
              }"
            ></div>
          </div>
          <el-empty v-else description="暂无截图" />
        </div>
        <div class="ai-analysis" v-if="ctx.currentStep.value?.ai_analysis">
          <div class="analysis-header">
            <el-icon><MagicStick /></el-icon><span>AI分析结果</span>
          </div>
          <div class="analysis-content">{{ ctx.currentStep.value.ai_analysis }}</div>
        </div>
        <el-alert
          v-if="
            ctx.currentStepIndex.value >= 0 &&
            ctx.issueTypeMap.value[ctx.currentStepIndex.value] === 'product_bug'
          "
          title="这是Bug问题，不要修改用例！"
          description="执行步骤完全正确，但实际结果与预期不符。这可能是产品功能缺陷，请勿修改测试用例来掩盖Bug。"
          type="error"
          show-icon
          :closable="false"
          class="bug-warning-alert"
        />
        <div
          class="failure-analysis-detail"
          v-if="
            ctx.currentStepIndex.value >= 0 &&
            ctx.failureAnalysisMap.value[ctx.currentStepIndex.value]
          "
        >
          <div class="analysis-header">
            <el-icon><Warning /></el-icon><span>失败原因分析</span>
          </div>
          <div class="analysis-body">
            <p>
              <strong>建议类型：</strong
              ><el-tag
                :type="
                  ISSUE_TYPE_COLORS[
                    ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].suggested_type
                  ]
                "
                size="small"
                >{{
                  ISSUE_TYPE_LABELS[
                    ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].suggested_type
                  ]
                }}</el-tag
              ><span class="confidence"
                >置信度:
                {{
                  (
                    ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].confidence * 100
                  ).toFixed(0)
                }}%</span
              >
            </p>
            <p>{{ ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].reason }}</p>
            <div
              v-if="
                ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].case_issue_indicators
                  .length > 0
              "
              class="indicators"
            >
              <p><strong>用例问题指标：</strong></p>
              <ul>
                <li
                  v-for="(ind, i) in ctx.failureAnalysisMap.value[ctx.currentStepIndex.value]
                    .case_issue_indicators"
                  :key="i"
                >
                  {{ ind }}
                </li>
              </ul>
            </div>
            <div
              v-if="
                ctx.failureAnalysisMap.value[ctx.currentStepIndex.value].bug_issue_indicators
                  .length > 0
              "
              class="indicators"
            >
              <p><strong>Bug问题指标：</strong></p>
              <ul>
                <li
                  v-for="(ind, i) in ctx.failureAnalysisMap.value[ctx.currentStepIndex.value]
                    .bug_issue_indicators"
                  :key="i"
                >
                  {{ ind }}
                </li>
              </ul>
            </div>
            <div class="issue-type-switch">
              <span>手动切换问题类型：</span
              ><el-radio-group
                v-model="ctx.issueTypeMap.value[ctx.currentStepIndex.value]"
                size="small"
                ><el-radio-button value="case_issue">用例问题</el-radio-button
                ><el-radio-button value="product_bug">Bug问题</el-radio-button
                ><el-radio-button value="needs_review">待判断</el-radio-button></el-radio-group
              >
            </div>
          </div>
        </div>
      </div>

      <ExecutionSidePanel />
    </div>

    <el-dialog
      v-model="ctx.showScreenshotFullscreen.value"
      title="截图预览"
      width="90%"
      class="screenshot-fullscreen-dialog"
    >
      <img :src="ctx.currentScreenshot.value" alt="截图预览" class="fullscreen-image" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { VideoPlay, VideoPause, CircleClose, MagicStick, Warning } from '@element-plus/icons-vue'
import {
  provideTestExecution,
  ISSUE_TYPE_LABELS,
  ISSUE_TYPE_COLORS,
} from '@/composables/execution/useTestExecution'
import ExecutionStepsPanel from './components/ExecutionStepsPanel.vue'
import ExecutionSidePanel from './components/ExecutionSidePanel.vue'

const ctx = provideTestExecution()

onMounted(() => {
  void ctx.init()
})
</script>

<style scoped lang="scss">
@use './TestExecution.scss';
</style>
