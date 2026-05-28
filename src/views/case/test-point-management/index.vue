<template>
  <div class="test-point-page">
    <div class="page-hero">
      <div class="hero-copy">
        <div class="hero-kicker">Test Point Workspace</div>
        <h2 class="page-title">测试点管理</h2>
        <p class="page-subtitle">统一管理测试点，支持需求提取、XMind 导入并直接生成关联测试用例</p>
        <div class="hero-meta">
          <el-tag effect="dark" type="primary">主入口工作台</el-tag>
          <el-tag v-if="selectedProjectName" effect="plain" type="info"
            >当前项目：{{ selectedProjectName }}</el-tag
          >
          <el-tag v-if="selectedProjectId" effect="plain" type="success"
            >筛选结果：{{ total }}</el-tag
          >
        </div>
      </div>
      <div class="header-actions">
        <el-select
          v-model="selectedProjectId"
          class="project-select"
          placeholder="请选择项目"
          filterable
          @change="handleProjectChange"
        >
          <template #prefix
            ><el-icon><FolderOpened /></el-icon
          ></template>
          <el-option
            v-for="project in projects"
            :key="project.id"
            :label="project.name"
            :value="project.id"
          />
        </el-select>
        <div class="hero-action-group">
          <el-button :disabled="!selectedProjectId" @click="openTaskList">查看任务</el-button>
          <el-button :icon="MagicStick" :disabled="!selectedProjectId" @click="openExtractDialog"
            >从需求提取</el-button
          >
          <el-button :icon="Upload" :disabled="!selectedProjectId" @click="openXmindImportDialog"
            >导入 XMind</el-button
          >
          <el-button
            type="primary"
            :icon="Plus"
            :disabled="!selectedProjectId"
            @click="openCreateDialog"
            >新增测试点</el-button
          >
        </div>
        <el-button
          link
          type="primary"
          :disabled="!selectedProjectId"
          @click="openLegacyExtractGuide"
          >高级提取向导</el-button
        >
      </div>
    </div>

    <div class="workspace-card">
      <el-empty v-if="!selectedProjectId" description="请选择项目后查看测试点列表">
        <template #image>
          <div class="empty-illustration">
            <el-icon><DataAnalysis /></el-icon>
          </div>
        </template>
        <template #description>
          <div class="empty-description">
            <p>从这里开始统一管理测试点、提取需求结果和生成关联用例。</p>
            <p>先选择一个项目，再进行后续操作。</p>
          </div>
        </template>
      </el-empty>
      <template v-else>
        <StatsCards />
        <FilterSection />
        <TestPointTable />
      </template>
    </div>

    <TestPointFormDialog
      v-model="formDialogVisible"
      :project-id="selectedProjectId || 0"
      :editing-point="editingPoint"
      @success="fetchTestPoints"
    />
    <TestPointCasesDialog v-model="casesDialogVisible" :test-point="currentTestPoint" />
    <TestPointExtractDialog
      v-model:visible="extractDialogVisible"
      :project-id="selectedProjectId || 0"
      :initial-file-id="initialExtractFileId || undefined"
      @saved="handleIngestSaved"
    />
    <XmindImportDialog
      v-model:visible="xmindImportDialogVisible"
      :project-id="selectedProjectId || 0"
      @imported="handleIngestSaved"
    />

    <el-dialog
      v-model="generateDialogVisible"
      class="generate-status-dialog"
      title="生成测试用例进度"
      width="520px"
      :close-on-click-modal="false"
      :show-close="!generating"
    >
      <div class="generate-status-panel">
        <div class="generate-status-head">
          <div class="generate-status-icon">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div>
            <div class="generate-status-title">
              {{ generating ? '正在处理测试点' : '生成流程已结束' }}
            </div>
            <div class="generate-status-subtitle">系统会自动刷新列表并同步最新的关联用例数量。</div>
          </div>
        </div>
        <el-progress :percentage="generateProgress" :status="progressStatus" />
        <p class="generate-message">{{ generateMessage }}</p>
      </div>
      <template #footer>
        <el-button :disabled="generating" type="primary" @click="generateDialogVisible = false"
          >关闭</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { provide } from 'vue'
import { DataAnalysis, FolderOpened, MagicStick, Plus, Upload } from '@element-plus/icons-vue'
import XmindImportDialog from '@/components/xmind/XmindImportDialog.vue'
import TestPointExtractDialog from './TestPointExtractDialog.vue'
import TestPointCasesDialog from './TestPointCasesDialog.vue'
import TestPointFormDialog from './TestPointFormDialog.vue'
import StatsCards from './components/StatsCards.vue'
import FilterSection from './components/FilterSection.vue'
import TestPointTable from './components/TestPointTable.vue'
import { useTestPointManagement, TestPointMgmtKey } from './useTestPointManagement'

const mgmt = useTestPointManagement()
provide(TestPointMgmtKey, mgmt)

const {
  generateDialogVisible,
  generateProgress,
  generateMessage,
  generating,
  xmindImportDialogVisible,
  extractDialogVisible,
  initialExtractFileId,
  projects,
  selectedProjectId,
  total,
  formDialogVisible,
  casesDialogVisible,
  editingPoint,
  currentTestPoint,
  selectedProjectName,
  progressStatus,
  handleProjectChange,
  openCreateDialog,
  openExtractDialog,
  openXmindImportDialog,
  openLegacyExtractGuide,
  openTaskList,
  handleIngestSaved,
  fetchTestPoints,
} = mgmt
</script>

<style scoped>
.test-point-page {
  padding: 20px;
  background:
    radial-gradient(circle at top right, rgba(64, 158, 255, 0.12), transparent 24%),
    linear-gradient(180deg, #f7faff 0%, #f3f6fb 100%);
}
.page-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  margin-bottom: 20px;
  background: linear-gradient(135deg, #ffffff 0%, #f7fbff 55%, #eef5ff 100%);
  border: 1px solid rgba(64, 158, 255, 0.12);
  border-radius: 24px;
  box-shadow: 0 14px 40px rgba(31, 45, 61, 0.08);
}
.hero-copy {
  min-width: 0;
}
.hero-kicker {
  margin-bottom: 10px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #409eff;
  font-weight: 700;
}
.page-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
  color: #1f2d3d;
}
.page-subtitle {
  margin: 10px 0 0;
  max-width: 760px;
  color: #5f6b7a;
  line-height: 1.6;
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}
.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  min-width: 420px;
}
.hero-action-group {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}
.project-select {
  width: 280px;
}
.workspace-card {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(220, 230, 241, 0.9);
  border-radius: 24px;
  box-shadow: 0 18px 48px rgba(31, 45, 61, 0.06);
}
.empty-illustration {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 110px;
  height: 110px;
  margin: 0 auto;
  border-radius: 50%;
  font-size: 52px;
  color: #409eff;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(103, 194, 58, 0.12));
}
.empty-description {
  color: #606266;
  line-height: 1.8;
}
.empty-description p {
  margin: 0;
}
.generate-status-panel {
  padding: 4px 2px 8px;
}
.generate-status-head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 20px;
}
.generate-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(118, 75, 162, 0.14));
  color: #409eff;
  font-size: 22px;
}
.generate-status-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}
.generate-status-subtitle {
  margin-top: 4px;
  color: #7a8594;
  line-height: 1.5;
}
.generate-message {
  margin: 16px 0 0;
  color: #606266;
  line-height: 1.6;
}
@media (max-width: 960px) {
  .page-hero {
    flex-direction: column;
    align-items: stretch;
  }
  .header-actions {
    min-width: 0;
    align-items: stretch;
  }
  .hero-action-group {
    justify-content: flex-start;
  }
  .project-select {
    width: 100%;
  }
}
@media (max-width: 640px) {
  .test-point-page {
    padding: 12px;
  }
  .workspace-card,
  .page-hero {
    padding: 16px;
    border-radius: 18px;
  }
}
</style>
