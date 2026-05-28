<template>
  <div class="ui-prototype-container">
    <el-card class="header-card" shadow="never">
      <div class="page-header">
        <div class="header-top">
          <div class="header-left">
            <el-button @click="goBack" :icon="ArrowLeft" circle size="small" />
            <h2 class="prototype-title">{{ prototypeName }}</h2>
            <div class="header-tags">
              <el-tag v-if="currentIteration" type="info" size="small" effect="plain"
                >{{ currentIteration.name
                }}{{ currentIteration.version ? ` (${currentIteration.version})` : '' }}</el-tag
              >
              <el-tag v-else-if="iterationName" type="info" size="small" effect="plain">{{
                iterationName
              }}</el-tag>
              <el-tag type="warning" size="small" effect="plain">UI原型图</el-tag>
              <el-tag type="info" size="small" effect="plain">{{ screens.length }}张</el-tag>
            </div>
          </div>
          <div class="header-right">
            <el-button type="success" plain @click="handleAddScreens">
              <el-icon><Upload /></el-icon>追加上传
            </el-button>
            <el-button type="primary" @click="handlePrimaryAction" :loading="flowGenerating">
              {{ primaryActionText }}
            </el-button>
          </div>
        </div>
        <el-alert
          v-if="parseMode === 'vision'"
          title="视觉模型解析将消耗更多API调用费用，建议优先使用文本模式"
          type="warning"
          :closable="false"
          show-icon
          class="vision-alert"
        />
      </div>
    </el-card>
    <el-card class="workflow-card" shadow="never">
      <div class="workflow-head">
        <div>
          <div class="workflow-title">UI 原型处理流程</div>
          <div class="workflow-subtitle">
            先完成截图解析，再分析多页面流转，最后进入用例生成或回归变更分析。
          </div>
        </div>
        <div class="parse-mode-wrapper">
          <span class="parse-mode-label">解析模式</span>
          <el-radio-group v-model="parseMode" size="small">
            <el-radio-button value="text">文本模式</el-radio-button>
            <el-radio-button value="vision">视觉模型</el-radio-button>
          </el-radio-group>
        </div>
      </div>
      <el-steps class="workflow-steps" :active="workflowActiveStep" finish-status="success">
        <el-step
          v-for="step in workflowSteps"
          :key="step.title"
          :title="step.title"
          :description="step.description"
          :status="step.status"
        />
      </el-steps>
      <div class="workflow-actions">
        <el-button type="success" plain @click="handleAddScreens">
          <el-icon><Upload /></el-icon>追加上传
        </el-button>
        <el-button
          type="primary"
          plain
          @click="handleBatchParse"
          :disabled="screens.length === 0 || parsing"
        >
          {{ parseMode === 'text' ? '解析页面' : 'AI视觉解析' }}
        </el-button>
        <el-button
          type="warning"
          plain
          @click="handleGenerateFlow"
          :loading="flowGenerating"
          :disabled="completedScreenCount < 2"
        >
          分析页面流转
        </el-button>
        <el-button type="primary" @click="goToCaseGenerate" :disabled="completedScreenCount === 0">
          生成测试用例
        </el-button>
        <el-button
          type="danger"
          plain
          @click="goToScenario4"
          :disabled="completedScreenCount === 0"
        >
          回归变更分析
        </el-button>
      </div>
    </el-card>
    <div class="overview-strip">
      <div class="overview-card overview-card-primary">
        <div class="overview-label">屏幕总数</div>
        <div class="overview-value">{{ screens.length }}</div>
        <div class="overview-desc">当前原型版本下的全部页面截图</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">已解析</div>
        <div class="overview-value">{{ completedScreenCount }}</div>
        <div class="overview-desc">可查看元素和流程详情</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">待处理</div>
        <div class="overview-value">{{ pendingScreenCount }}</div>
        <div class="overview-desc">尚未完成解析的页面</div>
      </div>
      <div class="overview-card">
        <div class="overview-label">解析失败</div>
        <div class="overview-value">{{ failedScreenCount }}</div>
        <div class="overview-desc">建议重新发起解析</div>
      </div>
    </div>
    <el-card class="flow-overview-card" shadow="never">
      <div class="content-head">
        <div class="content-head-main">
          <div class="content-title">页面流转概览</div>
          <div class="content-subtitle">
            项目级页面流转会用于多页面自动化用例和回归变更分析；单页元素详情仍在截图弹层查看。
          </div>
        </div>
        <el-button type="primary" plain @click="goToFlowEditor" :disabled="!hasFlow">
          查看/编辑流程编排
        </el-button>
      </div>
      <div v-if="hasFlow && flowSummary" class="flow-summary-grid">
        <div class="flow-summary-item">
          <span>页面数</span><strong>{{ flowSummary.node_count }}</strong>
        </div>
        <div class="flow-summary-item">
          <span>连线数</span><strong>{{ flowSummary.edge_count }}</strong>
        </div>
        <div class="flow-summary-item">
          <span>入口页</span><strong>{{ flowSummary.entry_screen || '-' }}</strong>
        </div>
        <div class="flow-summary-item">
          <span>终止页</span><strong>{{ flowSummary.end_screens?.length || 0 }}</strong>
        </div>
        <div class="flow-summary-item">
          <span>分支</span><strong>{{ flowSummary.branch_count }}</strong>
        </div>
        <div class="flow-summary-item">
          <span>异常/提示</span><strong>{{ flowSummary.exception_count }}</strong>
        </div>
      </div>
      <el-empty v-else description="解析至少 2 张页面后，可分析页面流转并在这里查看概览" />
    </el-card>
    <el-card class="content-card" v-loading="loading" shadow="never">
      <div class="content-head">
        <div class="content-head-main">
          <div class="content-title">屏幕列表</div>
          <div class="content-subtitle">
            点击卡片查看详情，解析完成后可在弹层中查看元素、流程与布局信息。
          </div>
        </div>
        <div class="content-tags">
          <el-tag type="success" effect="plain">已解析 {{ completedScreenCount }}</el-tag
          ><el-tag type="warning" effect="plain">待处理 {{ pendingScreenCount }}</el-tag
          ><el-tag type="danger" effect="plain">失败 {{ failedScreenCount }}</el-tag>
        </div>
      </div>
      <ScreenCardGrid
        :screens="screens"
        :image-urls="screenImageUrls"
        :loading="loading"
        @preview="handlePreviewScreen"
        @parse="handleParseScreen"
        @delete="handleDeleteScreen"
        @add-screens="handleAddScreens"
      />
    </el-card>
    <ScreenPreviewDialog
      v-model:visible="previewVisible"
      :screen="previewScreen"
      :image-urls="screenImageUrls"
    />
    <ScreenUploadDialog
      v-model:visible="uploadDialogVisible"
      :uploading="uploading"
      @submit="handleUploadSubmit"
    />
    <AIParseLoading
      :visible="parsing"
      :parse-mode="parseMode"
      :total-count="pendingScreensCount"
      :processed-count="processedScreensCount"
      :show-cancel-button="true"
      @cancel="handleCancelParse"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import ScreenCardGrid from './components/ScreenCardGrid.vue'
import ScreenPreviewDialog from './components/ScreenPreviewDialog.vue'
import ScreenUploadDialog from './components/ScreenUploadDialog.vue'
import AIParseLoading from '@/components/loading/AIParseLoading.vue'
import { useUIPrototype } from './useUIPrototype'

const {
  prototypeName,
  iterationName,
  currentIteration,
  loading,
  parsing,
  uploading,
  flowGenerating,
  screens,
  screenImageUrls,
  previewVisible,
  previewScreen,
  uploadDialogVisible,
  parseMode,
  completedScreenCount,
  failedScreenCount,
  pendingScreenCount,
  pendingScreensCount,
  processedScreensCount,
  hasFlow,
  flowSummary,
  workflowSteps,
  primaryActionText,
  goBack,
  goToScenario4,
  goToCaseGenerate,
  goToFlowEditor,
  handlePrimaryAction,
  handlePreviewScreen,
  handleParseScreen,
  handleBatchParse,
  handleGenerateFlow,
  handleCancelParse,
  handleDeleteScreen,
  handleAddScreens,
  handleUploadSubmit,
} = useUIPrototype()

const workflowActiveStep = computed(() => {
  if (hasFlow.value) return 4
  if (completedScreenCount.value >= 2) return 3
  if (completedScreenCount.value > 0) return 2
  if (screens.value.length > 0) return 1
  return 0
})
</script>

<style scoped>
.ui-prototype-container {
  padding: 20px;
  background: linear-gradient(180deg, #f7f9fc 0%, #f3f6fb 100%);
  min-height: 100%;
}
.header-card {
  margin-bottom: 16px;
  border: none;
  background: linear-gradient(135deg, #fafbfc 0%, #f5f8fc 100%);
}
.workflow-card,
.flow-overview-card {
  margin-bottom: 16px;
  border: none;
  border-radius: 18px;
  background: #fff;
}
.workflow-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.workflow-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 6px;
}
.workflow-subtitle {
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
}
.workflow-steps {
  margin-bottom: 18px;
}
.workflow-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid #f0f2f5;
}
.flow-summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.flow-summary-item {
  min-height: 76px;
  padding: 14px;
  border: 1px solid #e8ecf0;
  border-radius: 12px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}
.flow-summary-item span {
  color: #6b7280;
  font-size: 13px;
}
.flow-summary-item strong {
  color: #1f2937;
  font-size: 18px;
  line-height: 1.3;
  word-break: break-all;
}
.page-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.prototype-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1a1d21;
}
.header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.parse-mode-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e8ecf0;
}
.parse-mode-label {
  font-size: 13px;
  color: #6b7280;
  font-weight: 500;
  white-space: nowrap;
}
.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.vision-alert {
  border-radius: 10px;
}
.overview-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.overview-card {
  padding: 16px 18px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #e8ecf0;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04);
}
.overview-card-primary {
  background: linear-gradient(135deg, #fff 0%, #eff6ff 100%);
  border-color: #dbeafe;
}
.overview-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}
.overview-value {
  font-size: 28px;
  line-height: 1;
  font-weight: 700;
  color: #2563eb;
  margin-bottom: 8px;
}
.overview-desc {
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
}
.content-card {
  min-height: 400px;
  border: none;
  background: #fff;
  border-radius: 18px;
}
.content-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f0f2f5;
}
.content-head-main {
  flex: 1;
  min-width: 0;
}
.content-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 6px;
}
.content-subtitle {
  font-size: 13px;
  line-height: 1.6;
  color: #6b7280;
}
.content-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 1100px) {
  .overview-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .flow-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
@media (max-width: 768px) {
  .ui-prototype-container {
    padding: 16px;
  }
  .workflow-head {
    flex-direction: column;
  }
  .content-head {
    flex-direction: column;
  }
  .overview-strip {
    grid-template-columns: 1fr;
  }
  .flow-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
