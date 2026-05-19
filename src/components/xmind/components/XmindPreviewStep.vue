<template>
  <div v-if="currentStep === 1" class="preview-area">
    <div v-if="loading && aiEnhance && importProgressText" class="import-progress-area">
      <el-progress v-if="importProgress && importProgress.total_batches > 1" :percentage="importProgress!.percentage" :stroke-width="18" :text-inside="true" status="" :format="() => `${importProgress!.completed_batches}/${importProgress!.total_batches} 批次`" />
      <div class="import-progress-text">{{ importProgressText }}</div>
    </div>
    <div class="preview-header">
      <el-tag type="info">测试点 {{ previewData.length }} 条</el-tag>
      <el-tag v-if="previewCaseData.length > 0" type="primary">测试用例 {{ previewCaseData.length }} 条</el-tag>
      <el-tag v-if="isCasePreviewMode" type="success">识别为场景树导入</el-tag>
      <el-tag type="danger">高优先级: {{ highPriorityCount }}</el-tag>
      <el-tag type="warning">中优先级: {{ mediumPriorityCount }}</el-tag>
      <el-tag type="success">低优先级: {{ lowPriorityCount }}</el-tag>
      <el-tag v-if="previewSkippedCount > 0" type="warning">已跳过 {{ previewSkippedCount }} 个节点</el-tag>
    </div>
    <el-alert v-if="previewSkippedCount > 0" type="warning" show-icon :closable="false" class="preview-skipped-alert">
      <template #title>检测到 {{ previewSkippedCount }} 个节点未导入预览，常见原因是模块名或测试点名称为空。</template>
      <div v-if="previewSkippedReasons.length > 0" class="preview-skipped-reasons">
        <el-tag v-for="(reason, index) in previewSkippedReasons" :key="index" type="warning" effect="plain">{{ reason }}</el-tag>
      </div>
    </el-alert>
    <el-alert v-if="isCasePreviewMode" type="info" show-icon :closable="false" class="preview-mode-alert">
      <template #title>该 XMind 将按"测试点 + 测试用例"双通道导入，可切换查看两种预览视图。</template>
    </el-alert>
    <el-alert v-if="previewAiTimeout" type="warning" show-icon :closable="false" class="preview-ai-timeout-alert">
      <template #title>AI增强解析超时，已自动降级为普通解析模式。如需使用AI增强，请稍后重试或检查网络连接。</template>
    </el-alert>
    <el-alert v-if="isAiSamplePreview" type="info" show-icon :closable="false" class="preview-mode-alert">
      <template #title>AI 增强预览采样：已解析前 {{ previewCaseData.length }} 条路径（共 {{ previewTotalPaths }} 条）。确认导入时将对全部路径进行 AI 解析，预计耗时较长。</template>
    </el-alert>
    <div v-if="hasCasePreview" class="preview-switcher">
      <el-radio-group v-model="activePreviewTab" size="small" @change="currentPage = 1">
        <el-radio-button value="points">测试点预览</el-radio-button>
        <el-radio-button value="cases">测试用例预览</el-radio-button>
      </el-radio-group>
    </div>
    <el-table v-if="activePreviewTab === 'points'" :data="paginatedPreviewData" border stripe v-loading="loading" height="360" style="width: 100%">
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
      <el-table-column prop="function" label="功能" width="120" show-overflow-tooltip />
      <el-table-column prop="precondition" label="前置条件" width="150" show-overflow-tooltip />
      <el-table-column prop="point" label="测试点描述" min-width="250" show-overflow-tooltip />
      <el-table-column prop="priority" label="优先级" width="100">
        <template #default="scope"><el-tag :type="getPriorityType(scope.row.priority)">{{ getPriorityLabel(scope.row.priority) }}</el-tag></template>
      </el-table-column>
    </el-table>
    <el-table v-else :data="paginatedPreviewCases" border stripe v-loading="loading" height="360" style="width: 100%">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="case-step-list">
            <div v-if="row.precondition" class="case-step-block"><div class="case-step-title">前置条件</div><div class="case-step-text">{{ row.precondition }}</div></div>
            <div class="case-step-block"><div class="case-step-title">操作步骤</div>
              <div class="case-step-table">
                <div v-for="step in row.steps" :key="`${row.title}-${step.step_number}`" class="case-step-row">
                  <div class="case-step-num">{{ step.step_number }}</div>
                  <div class="case-step-content">
                    <div class="case-step-action">{{ step.display_action || step.description || step.action }}</div>
                    <div v-if="step.expected_result" class="case-step-expected">预期：{{ step.expected_result }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
      <el-table-column prop="function" label="功能" width="120" show-overflow-tooltip />
      <el-table-column prop="precondition" label="前置条件" min-width="180" show-overflow-tooltip />
      <el-table-column prop="title" label="用例标题" min-width="220" show-overflow-tooltip />
      <el-table-column label="步骤摘要" min-width="220" show-overflow-tooltip>
        <template #default="{ row }"><div class="case-step-summary"><el-tag size="small" type="info">{{ row.step_count }} 步</el-tag><span>{{ formatCaseStepSummary(row) }}</span></div></template>
      </el-table-column>
      <el-table-column prop="expected_result" label="预期结果" min-width="220" show-overflow-tooltip />
      <el-table-column prop="priority" label="优先级" width="100">
        <template #default="{ row }"><el-tag :type="getPriorityType(row.priority)">{{ getPriorityLabel(row.priority) }}</el-tag></template>
      </el-table-column>
    </el-table>
    <div class="preview-pagination">
      <el-pagination v-model:current-page="currentPage" :page-size="pageSize" :total="currentPreviewTotal" layout="prev, pager, next" size="small" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { XmindImportKey } from '../useXmindImport'

const mgmt = inject(XmindImportKey)!
const {
  currentStep, loading, aiEnhance, importProgress, importProgressText,
  previewData, previewCaseData, previewSkippedCount, previewSkippedReasons,
  activePreviewTab, currentPage, pageSize, isCasePreviewMode, hasCasePreview,
  currentPreviewTotal, highPriorityCount, mediumPriorityCount, lowPriorityCount,
  previewAiTimeout, previewTotalPaths, isAiSamplePreview, paginatedPreviewData,
  paginatedPreviewCases, getPriorityType, getPriorityLabel, formatCaseStepSummary,
} = mgmt
</script>

<style scoped>
.preview-area { display: flex; flex-direction: column; gap: 12px; }
.preview-header { display: flex; gap: 8px; flex-wrap: wrap; }
.preview-skipped-alert, .preview-mode-alert { margin-top: 4px; }
.preview-switcher { display: flex; justify-content: flex-start; }
.preview-skipped-reasons { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.preview-pagination { display: flex; justify-content: center; margin-top: 8px; }
.import-progress-area { width: 100%; padding: 12px 0 4px; }
.import-progress-text { font-size: 12px; color: #909399; margin-top: 6px; text-align: center; }
.case-step-list { display: flex; flex-direction: column; gap: 12px; padding: 8px 4px; }
.case-step-block { display: flex; flex-direction: column; gap: 6px; }
.case-step-title { font-weight: 600; color: #303133; }
.case-step-text { color: #606266; white-space: pre-wrap; }
.case-step-table { display: flex; flex-direction: column; gap: 0; }
.case-step-row { display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.case-step-row:last-child { border-bottom: none; }
.case-step-num { flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%; background: #409eff; color: #fff; font-size: 12px; font-weight: 600; display: flex; align-items: center; justify-content: center; line-height: 1; }
.case-step-content { flex: 1; min-width: 0; }
.case-step-action { color: #303133; font-size: 13px; line-height: 1.5; }
.case-step-expected { color: #67c23a; font-size: 12px; margin-top: 4px; line-height: 1.5; padding-left: 0; }
.case-step-summary { display: flex; align-items: center; gap: 8px; }
</style>
