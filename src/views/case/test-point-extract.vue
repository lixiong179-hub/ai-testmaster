<template>
  <div class="test-point-extract-container">
    <div class="page-header">
      <div class="header-left">
        <div>
          <h2>测试点提取向导</h2>
          <p class="page-subtitle">用于复杂提取与兼容场景，日常维护请优先使用测试点管理</p>
        </div>
        <div class="step-nav-buttons" v-if="currentStep > 0 || currentStep < 3">
          <el-button :disabled="currentStep === 0" @click="goToPrevStep" round plain size="small">
            <el-icon><ArrowLeft /></el-icon>
            上一步
          </el-button>
          <el-button
            :disabled="currentStep === 3"
            @click="goToNextStep"
            type="primary"
            round
            size="small"
          >
            下一步
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" plain @click="goToManagement">
          <el-icon><List /></el-icon>
          前往测试点管理
        </el-button>
        <el-button @click="goToManagement">
          <el-icon><ArrowLeft /></el-icon>
          返回列表
        </el-button>
      </div>
    </div>

    <el-alert
      title="该页面已调整为高级提取向导。XMind 导入、日常增删改查和常规批量生成已统一到「测试点管理」页。"
      type="warning"
      :closable="false"
      show-icon
      class="mode-alert"
    />

    <div class="steps-wrapper steps-enhanced">
      <el-steps :active="currentStep" finish-status="success" align-center class="custom-steps">
        <el-step title="选择项目" description="选择目标项目">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><FolderOpened /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="选择需求" description="选择需求资源">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><Document /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="AI提取" description="提取测试点">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><MagicStick /></el-icon>
            </div>
          </template>
        </el-step>
        <el-step title="校验结果" description="审核并保存">
          <template #icon>
            <div class="step-icon-custom">
              <el-icon><List /></el-icon>
            </div>
          </template>
        </el-step>
      </el-steps>
    </div>

    <div class="main-content">
      <div class="left-panel">
        <transition name="slide-fade" mode="out-in">
          <Step1ProjectSelect v-if="currentStep === 0" key="step1" />
          <Step2ResourceSelect v-else-if="currentStep === 1" key="step2" />
          <Step3AIExtract v-else-if="currentStep === 2" key="step3" />
          <Step4Validate v-else-if="currentStep === 3" key="step4" />
        </transition>
      </div>

      <RightPreviewPanel />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import {
  ArrowLeft,
  ArrowRight,
  MagicStick,
  FolderOpened,
  Document,
  List,
} from '@element-plus/icons-vue'
import { provideTestPointExtract } from '@/composables/useTestPointExtract'
import Step1ProjectSelect from './components/Step1ProjectSelect.vue'
import Step2ResourceSelect from './components/Step2ResourceSelect.vue'
import Step3AIExtract from './components/Step3AIExtract.vue'
import Step4Validate from './components/Step4Validate.vue'
import RightPreviewPanel from './components/RightPreviewPanel.vue'

const { currentStep, goToPrevStep, goToNextStep, goToManagement, init } = provideTestPointExtract()

onMounted(() => {
  init()
})
</script>

<style>
.test-point-extract-container {
  --primary-color: #409eff;
  --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --border-radius: 12px;
  --border-radius-sm: 8px;
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.08);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.12);
  --shadow-xl: 0 12px 48px rgba(0, 0, 0, 0.15);
  --spacing-xs: 8px;
  --spacing-sm: 12px;
  --spacing-md: 16px;
  --spacing-lg: 20px;
  --spacing-xl: 24px;
  --spacing-xxl: 32px;
}
</style>

<style>
.test-point-extract-container {
  padding: var(--spacing-xl);
  max-width: 1400px;
  margin: 0 auto;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  min-height: calc(100vh - 120px);
  border-radius: var(--border-radius);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-sm);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.header-left h2 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.page-subtitle {
  margin: 6px 0 0;
  color: #606266;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.mode-alert {
  margin-bottom: var(--spacing-xl);
}

.page-header .el-button {
  border-radius: 8px;
  font-weight: 500;
  transition: all 0.3s ease;
}

.page-header .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.step-nav-buttons {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.step-nav-buttons .el-button {
  font-weight: 600;
}

.steps-wrapper {
  margin-bottom: var(--spacing-xl);
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: var(--spacing-xl) var(--spacing-xxl);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  position: relative;
  overflow: hidden;
}

.steps-wrapper::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
}

.steps-enhanced :deep(.el-steps) {
  margin-top: 8px;
}

.step-icon-custom {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 18px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.main-content {
  display: flex;
  gap: var(--spacing-xl);
  min-height: 600px;
}

.left-panel {
  flex: 1;
  min-width: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  position: relative;
}

.left-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #409eff 0%, #67c23a 100%);
}

.right-panel {
  width: 400px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
  position: relative;
}

.right-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #f56c6c 0%, #e6a23c 50%, #409eff 100%);
}

.right-panel-enhanced {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 250, 252, 0.98) 100%);
}

.step-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.step-content.step-full {
  min-height: 650px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid #ebeef5;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  background: #fafafa;
  position: relative;
}

.step-title-gradient {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-bottom: 2px solid #e4e7ed;
}

.step-title .el-icon {
  color: var(--primary-color);
  font-size: 22px;
}

.step-badge {
  margin-left: auto;
  padding: 4px 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}

.step-body {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

.step-body-enhanced {
  padding: var(--spacing-xxl);
}

.project-selection-guide {
  text-align: center;
}

.guide-illustration {
  position: relative;
  margin-bottom: var(--spacing-xl);
  display: inline-block;
}

.illustration-circle {
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  animation: float 3s ease-in-out infinite;
  position: relative;
  z-index: 2;
  will-change: transform;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0px) translateZ(0);
  }
  50% {
    transform: translateY(-10px) translateZ(0);
  }
}

.floating-icons {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.float-icon {
  position: absolute;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
  animation: floatIcon 4s ease-in-out infinite;
  z-index: 3;
  will-change: transform;
}

.float-icon.float-1 {
  top: 10px;
  right: -10px;
  color: #409eff;
  animation-delay: 0s;
}

.float-icon.float-2 {
  bottom: 15px;
  left: -15px;
  color: #67c23a;
  animation-delay: 1s;
}

.float-icon.float-3 {
  bottom: -5px;
  right: 20px;
  color: #e6a23c;
  animation-delay: 2s;
}

@keyframes floatIcon {
  0%,
  100% {
    transform: translateY(0) translateZ(0) rotate(0deg);
  }
  33% {
    transform: translateY(-8px) translateZ(0) rotate(5deg);
  }
  66% {
    transform: translateY(4px) translateZ(0) rotate(-3deg);
  }
}

.guide-content {
  margin-bottom: var(--spacing-xl);
}

.guide-title {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 var(--spacing-sm) 0;
}

.guide-description {
  font-size: 16px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
}

.project-select-enhanced {
  margin-bottom: var(--spacing-xl);
}

.project-select-enhanced :deep(.el-select) {
  border-radius: var(--border-radius);
}

.project-select-enhanced :deep(.el-input__wrapper) {
  border-radius: var(--border-radius);
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  transition: all 0.3s ease;
}

.project-select-enhanced :deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.25);
}

.project-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px 0;
}

.workflow-hint {
  margin-top: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #e4e7ed;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
}

.wf-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.wf-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.wf-step span {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
}

.wf-arrow {
  color: #c0c4cc;
  font-size: 16px;
}

.project-selected-view {
  width: 100%;
}

.selected-project-card {
  background: white;
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.project-card-header {
  padding: var(--spacing-xl);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  color: white;
}

.project-icon-large {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.project-info-main {
  flex: 1;
}

.project-name-large {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 24px;
  font-weight: 700;
  color: white;
}

.project-meta-tags {
  display: flex;
  gap: var(--spacing-sm);
}

.project-meta-tags .el-tag {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
}

.project-card-body {
  padding: var(--spacing-xl);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.grid-item {
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  text-align: center;
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
}

.grid-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: #409eff;
}

.grid-icon {
  margin-bottom: var(--spacing-sm);
}

.grid-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 4px;
}

.grid-label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.project-card-footer {
  padding: var(--spacing-lg) var(--spacing-xl);
  background: #fafafa;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.project-card-footer .el-button {
  flex: 1;
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.project-card-footer .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.filter-bar {
  margin-bottom: var(--spacing-md);
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  border: 2px solid #ebeef5;
  border-radius: var(--border-radius);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: white;
  position: relative;
  overflow: hidden;
}

.resource-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: transparent;
  transition: all 0.3s ease;
}

.resource-item:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-lg);
  transform: translateX(4px);
}

.resource-item:hover::before {
  background: var(--primary-color);
}

.resource-item.active {
  border-color: var(--primary-color);
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.2);
}

.resource-item.active::before {
  background: var(--primary-color);
}

.resource-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: var(--border-radius-sm);
  color: #606266;
  transition: all 0.3s ease;
}

.resource-item:hover .resource-icon,
.resource-item.active .resource-icon {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
  transform: scale(1.05);
}

.resource-info {
  flex: 1;
  min-width: 0;
}

.resource-name {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.resource-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  font-size: 13px;
  color: #909399;
}

.resource-size,
.resource-time {
  font-size: 12px;
}

.resource-action {
  flex-shrink: 0;
}

.resource-action .el-button {
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.resource-action .el-button:hover {
  transform: scale(1.05);
  box-shadow: var(--shadow-md);
}

.selected-resource-card {
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  border: 2px solid #b3d8ff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.resource-summary {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.resource-summary .el-icon {
  color: var(--primary-color);
}

.resource-summary .resource-name {
  font-weight: 700;
  font-size: 17px;
  color: #303133;
}

.resource-summary .resource-meta {
  font-size: 14px;
  color: #606266;
  margin-top: 6px;
}

.extract-progress {
  text-align: center;
}

.skeleton-wrapper {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #ebeef5;
}

.progress-section {
  padding: var(--spacing-lg) 0;
}

.progress-section :deep(.el-progress-bar__outer) {
  border-radius: 20px;
}

.progress-section :deep(.el-progress-bar__inner) {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
}

.progress-text-animated {
  margin: var(--spacing-lg) 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--primary-color);
  animation: pulse 2s ease-in-out infinite;
  will-change: opacity;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.extract-error {
  padding: var(--spacing-lg) 0;
}

.extract-ready {
  padding: var(--spacing-xxl) 0;
}

.ready-icon {
  margin-bottom: var(--spacing-lg);
}

.ready-text {
  color: #606266;
  font-size: 15px;
  margin-bottom: var(--spacing-xl);
  line-height: 1.6;
}

.extract-success {
  padding: var(--spacing-lg) 0;
  text-align: center;
}

.success-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f0f9eb 0%, #ecf5ff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #e1f3d8;
}

.success-icon-wrapper {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  border-radius: 50%;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.3);
}

.success-info {
  text-align: left;
}

.success-title {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.success-desc {
  margin: 0;
  font-size: 15px;
  color: #606266;
}

.success-desc strong {
  color: #67c23a;
  font-size: 18px;
}

.success-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
}

.stat-item {
  padding: var(--spacing-md);
  border-radius: var(--border-radius-sm);
  text-align: center;
  transition: transform 0.2s ease;
}

.stat-item:hover {
  transform: translateY(-2px);
}

.stat-number {
  display: block;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-top: var(--spacing-xs);
}

.stat-high {
  background: #fef0f0;
  border: 1px solid #fde2e2;
}
.stat-high .stat-number {
  color: #f56c6c;
}

.stat-medium {
  background: #fdf6ec;
  border: 1px solid #faecd8;
}
.stat-medium .stat-number {
  color: #e6a23c;
}

.stat-low {
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
}
.stat-low .stat-number {
  color: #67c23a;
}

.stat-modules {
  background: #ecf5ff;
  border: 1px solid #d9ecff;
}
.stat-modules .stat-number {
  color: #409eff;
}

.success-actions {
  display: flex;
  justify-content: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.success-actions .el-button {
  font-weight: 600;
  border-radius: 10px;
  padding: 12px 28px;
  font-size: 15px;
  transition: all 0.3s ease;
}

.success-actions .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.batch-toolbar {
  margin-bottom: var(--spacing-lg);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius);
  border: 1px solid #e4e7ed;
  box-shadow: var(--shadow-sm);
}

.batch-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.action-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

.action-buttons .el-button {
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s ease;
}

.action-buttons .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.table-wrapper {
  overflow-x: auto;
  border-radius: var(--border-radius-sm);
  border: 1px solid #ebeef5;
  box-shadow: var(--shadow-sm);
}

.table-wrapper :deep(.el-table) {
  border-radius: var(--border-radius-sm);
}

.table-wrapper :deep(.el-table th.el-table__cell) {
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%) !important;
  font-weight: 700;
  color: #303133;
}

.table-wrapper :deep(.el-table tr:hover > td.el-table__cell) {
  background-color: #ecf5ff !important;
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  padding: var(--spacing-lg) 0 var(--spacing-md);
}

.preview-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.preview-card-enhanced {
  background: transparent !important;
  box-shadow: none !important;
}

.preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-welcome {
  padding: var(--spacing-xl);
  text-align: center;
}

.welcome-illustration {
  margin-bottom: var(--spacing-xl);
  display: flex;
  justify-content: center;
}

.welcome-icon-bg {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.4);
  animation: float 3s ease-in-out infinite;
}

.welcome-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 var(--spacing-sm) 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  line-height: 1.6;
  margin: 0 0 var(--spacing-xl) 0;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
  text-align: left;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
}

.feature-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
  border-color: #409eff;
}

.feature-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.feature-text {
  flex: 1;
}

.feature-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 2px;
}

.feature-desc {
  font-size: 12px;
  color: #909399;
}

.tip-card {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  background: linear-gradient(135deg, #fff8e6 0%, #fff4d9 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #ffe4b3;
  color: #909399;
  font-size: 13px;
}

.preview-body-enhanced {
  padding: var(--spacing-xl);
}

.project-summary-card {
  background: white;
  border-radius: var(--border-radius);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
  border: 1px solid #e4e7ed;
  margin-bottom: var(--spacing-lg);
}

.summary-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-lg);
  border-bottom: 2px solid #f2f6fc;
}

.summary-info {
  flex: 1;
}

.summary-title {
  margin: 0 0 4px 0;
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.summary-id {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.summary-stats {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
}

.summary-stat-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex: 1;
}

.stat-icon-wrapper {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.stat-icon-wrapper.stat-blue {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
}

.stat-icon-wrapper.stat-green {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
}

.stat-detail {
  flex: 1;
}

.stat-detail .stat-number {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.stat-detail .stat-text {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.summary-stat-divider {
  width: 1px;
  height: 40px;
  background: #e4e7ed;
}

.resource-preview-list {
  margin-bottom: var(--spacing-lg);
}

.preview-list-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: var(--spacing-md);
}

.preview-type-items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.type-item {
  display: grid;
  grid-template-columns: 100px 1fr auto;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) 0;
}

.type-bar {
  height: 8px;
  border-radius: 4px;
  transition: width 0.6s ease;
}

.type-requirement {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 100%);
}

.type-ui {
  background: linear-gradient(90deg, #e6a23c 0%, #f0c78a 100%);
}

.type-api {
  background: linear-gradient(90deg, #67c23a 0%, #85ce61 100%);
}

.type-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

.type-count {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.next-action-card {
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  border-radius: var(--border-radius);
  border: 2px solid #b3d8ff;
  text-align: center;
}

.action-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  color: #409eff;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: var(--spacing-md);
}

.next-btn-large {
  width: 100%;
  border-radius: 10px !important;
  font-size: 15px !important;
  font-weight: 700 !important;
  padding: 14px 20px !important;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%) !important;
  border: none !important;
  transition: all 0.3s ease !important;
}

.next-btn-large:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4) !important;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid #ebeef5;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
}

.preview-header .el-icon {
  color: var(--primary-color);
  font-size: 20px;
}

.preview-body {
  flex: 1;
  padding: var(--spacing-lg);
  overflow-y: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) 0;
  border-bottom: 1px solid #f2f6fc;
  transition: all 0.3s ease;
}

.info-item:hover {
  background: #fafafa;
  padding-left: var(--spacing-sm);
  padding-right: var(--spacing-sm);
  margin-left: calc(-1 * var(--spacing-sm));
  margin-right: calc(-1 * var(--spacing-sm));
  border-radius: 6px;
}

.info-item:last-child {
  border-bottom: none;
}

.info-item .label {
  color: #909399;
  font-size: 14px;
  font-weight: 500;
}

.info-item .value {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.info-item .value.highlight {
  color: var(--primary-color);
  font-weight: 700;
}

.next-step-hint {
  margin-top: var(--spacing-xl);
  padding-top: var(--spacing-lg);
  border-top: 2px solid #e4e7ed;
  text-align: center;
}

.next-step-hint .el-button {
  width: 100%;
  border-radius: 10px;
  font-weight: 700;
  font-size: 15px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  border: none;
  transition: all 0.3s ease;
}

.next-step-hint .el-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.4);
}

.resource-detail-card {
  text-align: center;
  padding: var(--spacing-lg) 0;
}

.detail-icon {
  margin-bottom: var(--spacing-lg);
}

.detail-name {
  font-size: 17px;
  font-weight: 700;
  color: #303133;
  margin-bottom: var(--spacing-md);
}

.detail-meta {
  margin-bottom: var(--spacing-lg);
}

.detail-stats {
  display: flex;
  justify-content: center;
  gap: var(--spacing-xl);
  margin-top: var(--spacing-lg);
}

.stat-value {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.stats-skeleton {
  padding: var(--spacing-lg);
}

.extract-stats {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.stat-card {
  text-align: center;
  padding: var(--spacing-xl);
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: var(--border-radius);
  color: #fff;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.35);
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  animation: shimmer 3s infinite;
  will-change: transform;
}

@keyframes shimmer {
  0% {
    transform: rotate(0deg) translateZ(0);
  }
  100% {
    transform: rotate(360deg) translateZ(0);
  }
}

.stat-card .stat-number {
  font-size: 52px;
  font-weight: 800;
  line-height: 1.2;
  position: relative;
  z-index: 1;
}

.stat-card .stat-label {
  font-size: 15px;
  opacity: 0.95;
  margin-top: var(--spacing-sm);
  font-weight: 600;
  position: relative;
  z-index: 1;
}

.distribution-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
  margin-bottom: var(--spacing-md);
  padding-left: var(--spacing-sm);
  border-left: 3px solid #409eff;
}

.distribution-items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.dist-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.dist-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
}

.dist-item.high {
  border-left: 3px solid #f56c6c;
}
.dist-item.high::before {
  background: #f56c6c;
}

.dist-item.medium {
  border-left: 3px solid #e6a23c;
}
.dist-item.medium::before {
  background: #e6a23c;
}

.dist-item.low {
  border-left: 3px solid #909399;
}
.dist-item.low::before {
  background: #909399;
}

.dist-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
}

.dist-count {
  font-size: 24px;
  font-weight: 800;
  color: #303133;
}

.dist-label {
  font-size: 13px;
  color: #909399;
  font-weight: 600;
}

.module-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.module-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px var(--spacing-md);
  font-size: 13px;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: 6px;
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
}

.module-item:hover {
  background: #ecf5ff;
  border-color: #b3d8ff;
  transform: translateX(4px);
}

.module-name {
  color: #606266;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.module-count {
  font-weight: 700;
  color: var(--primary-color);
  font-size: 15px;
}

.guide-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-xl);
}

.guide-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  font-size: 14px;
  color: #606266;
  background: linear-gradient(135deg, #f5f7fa 0%, #ffffff 100%);
  border-radius: var(--border-radius-sm);
  border: 1px solid #ebeef5;
  transition: all 0.3s ease;
}

.guide-item:hover {
  transform: translateX(4px);
  box-shadow: var(--shadow-sm);
  border-color: #409eff;
}

.quick-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  padding-top: var(--spacing-lg);
  border-top: 2px solid #e4e7ed;
}

.quick-stat-item {
  text-align: center;
  padding: var(--spacing-lg);
  background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
  border-radius: var(--border-radius-sm);
  border: 2px solid #b3d8ff;
  transition: all 0.3s ease;
}

.quick-stat-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.qs-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 600;
}

.qs-value {
  display: block;
  font-size: 28px;
  font-weight: 800;
  color: #303133;
}

.qs-value.highlight {
  color: var(--primary-color);
}

.empty-hint {
  padding: var(--spacing-xxl) 0;
  text-align: center;
}

.empty-icon,
.ready-icon {
  margin-bottom: var(--spacing-lg);
}

.waiting-state {
  padding: var(--spacing-xxl) 0;
  text-align: center;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
}

.dialog-footer .el-button {
  border-radius: 8px;
  font-weight: 600;
  padding: 10px 20px;
  transition: all 0.3s ease;
}

.dialog-footer .el-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(1, 0.5, 0.8, 1);
}

.slide-fade-enter-from {
  transform: translateX(30px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateX(-30px);
  opacity: 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.4s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}

@media (max-width: 1200px) {
  .right-panel {
    width: 360px;
  }

  .info-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .main-content {
    flex-direction: column;
  }

  .right-panel {
    width: 100%;
    order: -1;
  }

  .steps-wrapper {
    padding: var(--spacing-lg);
  }

  .steps-wrapper :deep(.el-steps--simple) {
    padding: 0;
  }

  .left-panel,
  .right-panel {
    width: 100%;
  }

  .resource-item {
    flex-wrap: wrap;
  }

  .resource-action {
    width: 100%;
    text-align: right;
    margin-top: var(--spacing-md);
  }

  .batch-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-info,
  .action-buttons {
    width: 100%;
    justify-content: center;
  }

  .page-header h2 {
    font-size: 20px;
  }

  .info-grid {
    grid-template-columns: 1fr 1fr;
  }

  .project-card-footer {
    flex-direction: column;
  }

  .workflow-steps {
    flex-wrap: wrap;
  }

  .guide-title {
    font-size: 22px;
  }

  .illustration-circle {
    width: 110px;
    height: 110px;
  }

  .welcome-icon-bg {
    width: 100px;
    height: 100px;
  }

  .success-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .success-header {
    flex-direction: column;
    text-align: center;
  }

  .success-info {
    text-align: center;
  }
}
</style>
