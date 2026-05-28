<template>
  <div class="review-inbox">
    <el-card>
      <template #header>
        <div class="page-header">
          <div class="header-left">
            <el-button type="info" @click="goBack" :icon="ArrowLeft">返回</el-button>
            <h2>评审 Inbox</h2>
            <el-tag v-if="reviewStatus" :type="statusTagType">{{ statusText }}</el-tag>
          </div>
          <div class="header-right">
            <el-button
              v-if="hasHighConfidenceUndecided"
              type="warning"
              @click="handleBatchAcceptHighConfidence"
            >
              批量采纳高置信度 (≥85%)
            </el-button>
            <el-button @click="fetchDecisions()" :icon="Refresh" :loading="loading">刷新</el-button>
            <el-button
              v-if="reviewStatus === 'in_progress'"
              type="success"
              @click="handleFinalize"
              :loading="finalizing"
            >
              最终化评审
            </el-button>
            <el-button v-if="undoWindowOpen" type="danger" plain @click="handleUndoFinalize">
              撤销最终化
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="loading && decisions.length === 0" class="loading-container">
        <el-skeleton :rows="5" animated />
      </div>

      <div v-else-if="errorMsg" class="error-container">
        <el-alert :title="errorMsg" type="error" show-icon :closable="false" />
      </div>

      <div v-else class="inbox-content">
        <el-tabs v-model="activeTab" @tab-change="onTabChange">
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.key"
            :label="`${tab.label} (${tab.count})`"
            :name="tab.key"
          />
        </el-tabs>

        <el-table
          :data="filteredDecisions"
          stripe
          class="decisions-table"
          row-class-name="decision-row"
          @selection-change="onSelectionChange"
          :selectable="isSelectable"
        >
          <el-table-column type="selection" width="50" />
          <el-table-column label="目标ID" prop="target_id" width="100">
            <template #default="{ row }">
              <span class="target-id">{{ row.target_kind }}-{{ row.target_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 判定" width="120">
            <template #default="{ row }">
              <el-tag :type="verdictTagType(row.ai_verdict)" size="small" effect="dark">
                {{ verdictLabel(row.ai_verdict) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="AI 置信度" width="160">
            <template #default="{ row }">
              <el-progress
                v-if="row.ai_confidence !== null && row.ai_confidence !== undefined"
                :percentage="Math.round(row.ai_confidence ?? 0)"
                :color="confidenceColor(row.ai_confidence)"
                :stroke-width="14"
                :text-inside="true"
              />
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="AI 理由" min-width="200">
            <template #default="{ row }">
              <el-text v-if="row.ai_reason" truncated>{{ row.ai_reason }}</el-text>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="修改提示" min-width="180">
            <template #default="{ row }">
              <div v-if="row.modification_hint" class="hint-cell">
                <el-button type="warning" link size="small" @click="toggleHint(row)">
                  {{ expandedHints.has(row.id) ? '收起' : '展开' }}提示
                </el-button>
                <el-text v-if="expandedHints.has(row.id)" class="hint-text" truncated>
                  {{ row.modification_hint }}
                </el-text>
              </div>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="废弃理由" min-width="160">
            <template #default="{ row }">
              <el-text v-if="row.deprecate_reason" truncated>{{ row.deprecate_reason }}</el-text>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="人工判定" width="200" fixed="right">
            <template #default="{ row }">
              <div v-if="row.human_verdict" class="human-decision">
                <el-tag :type="verdictTagType(row.human_verdict)" size="small">
                  {{ verdictLabel(row.human_verdict) }}
                </el-tag>
                <el-button
                  v-if="reviewStatus !== 'finalized'"
                  type="danger"
                  link
                  size="small"
                  @click="handleResetDecision(row)"
                >
                  重置
                </el-button>
                <el-button
                  v-if="undoWindowOpen"
                  type="warning"
                  link
                  size="small"
                  @click="handleUndoDecision(row)"
                >
                  撤销
                </el-button>
              </div>
              <div v-else-if="reviewStatus !== 'finalized'" class="decision-buttons">
                <el-button type="success" size="small" @click="handleDecide(row, 'keep')">
                  采纳
                </el-button>
                <el-button type="primary" size="small" @click="handleDecide(row, 'modify')">
                  修改
                </el-button>
                <el-button type="danger" size="small" @click="handleDecide(row, 'deprecate')">
                  否决
                </el-button>
              </div>
              <div v-else-if="undoWindowOpen" class="decision-buttons">
                <el-button type="warning" size="small" @click="handleUndoDecision(row)">
                  撤销
                </el-button>
              </div>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="冲突" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.conflict_marker" type="danger" size="small" effect="dark">
                冲突
              </el-tag>
              <span v-else class="text-muted">—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { useReviewInbox } from './useReviewInbox'

const {
  decisions,
  loading,
  finalizing,
  errorMsg,
  reviewStatus,
  activeTab,
  expandedHints,
  tabs,
  filteredDecisions,
  statusTagType,
  statusText,
  hasHighConfidenceUndecided,
  undoWindowOpen,
  verdictLabel,
  verdictTagType,
  confidenceColor,
  isSelectable,
  toggleHint,
  onSelectionChange,
  onTabChange,
  goBack,
  fetchDecisions,
  handleDecide,
  handleResetDecision,
  handleUndoDecision,
  handleUndoFinalize,
  handleBatchAcceptHighConfidence,
  handleFinalize,
} = useReviewInbox()
</script>

<style scoped lang="scss">
@use './ReviewInbox.scss';
</style>
