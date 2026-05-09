<template>
  <div class="step-content">
    <div class="step-title step-title-gradient">
      <el-icon><FolderOpened /></el-icon>
      <span>选择项目</span>
      <span class="step-badge">1/4</span>
    </div>
    <div class="step-body step-body-enhanced">
      <div v-if="!formData.project_id" class="project-selection-guide">
        <div class="guide-illustration">
          <div class="illustration-circle">
            <el-icon :size="64" color="#409EFF"><FolderOpened /></el-icon>
          </div>
          <div class="floating-icons">
            <div class="float-icon float-1">
              <el-icon :size="24"><Document /></el-icon>
            </div>
            <div class="float-icon float-2">
              <el-icon :size="20"><MagicStick /></el-icon>
            </div>
            <div class="float-icon float-3">
              <el-icon :size="22"><DataAnalysis /></el-icon>
            </div>
          </div>
        </div>
        <div class="guide-content">
          <h3 class="guide-title">选择您的项目</h3>
          <p class="guide-description">选择一个项目后，AI将帮助您自动提取测试点，提升测试效率</p>
        </div>
        <div class="project-select-enhanced">
          <el-select
            v-model="formData.project_id"
            placeholder="请搜索或选择项目"
            size="large"
            filterable
            clearable
            style="width: 100%"
            @change="handleProjectChange"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            >
              <div class="project-option">
                <el-icon><FolderOpened /></el-icon>
                <span>{{ project.name }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="workflow-hint">
          <div class="workflow-steps">
            <div class="wf-step">
              <div class="wf-number">1</div>
              <span>选择项目</span>
            </div>
            <div class="wf-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="wf-step">
              <div class="wf-number">2</div>
              <span>上传需求</span>
            </div>
            <div class="wf-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="wf-step">
              <div class="wf-number">3</div>
              <span>AI提取</span>
            </div>
            <div class="wf-arrow">
              <el-icon><ArrowRight /></el-icon>
            </div>
            <div class="wf-step">
              <div class="wf-number">4</div>
              <span>校验结果</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="project-selected-view">
        <div class="selected-project-card">
          <div class="project-card-header">
            <div class="project-icon-large">
              <el-icon :size="48"><FolderOpened /></el-icon>
            </div>
            <div class="project-info-main">
              <h3 class="project-name-large">{{ selectedProjectInfo?.name }}</h3>
              <div class="project-meta-tags">
                <el-tag type="primary" effect="plain" size="small"
                  >ID: {{ selectedProjectInfo?.id }}</el-tag
                >
                <el-tag type="success" effect="plain" size="small"
                  >{{ files.length }} 个资源文件</el-tag
                >
              </div>
            </div>
          </div>
          <div class="project-card-body">
            <div class="info-grid">
              <div class="grid-item">
                <div class="grid-icon">
                  <el-icon :size="28" color="#409EFF"><Files /></el-icon>
                </div>
                <div class="grid-content">
                  <div class="grid-value">{{ files.length }}</div>
                  <div class="grid-label">资源文件</div>
                </div>
              </div>
              <div class="grid-item">
                <div class="grid-icon">
                  <el-icon :size="28" color="#67C23A"><Document /></el-icon>
                </div>
                <div class="grid-content">
                  <div class="grid-value">{{ getResourceTypeCount('requirement') }}</div>
                  <div class="grid-label">需求文档</div>
                </div>
              </div>
              <div class="grid-item">
                <div class="grid-icon">
                  <el-icon :size="28" color="#E6A23C"><Picture /></el-icon>
                </div>
                <div class="grid-content">
                  <div class="grid-value">{{ getResourceTypeCount('ui_mockup') }}</div>
                  <div class="grid-label">UI原型</div>
                </div>
              </div>
              <div class="grid-item">
                <div class="grid-icon">
                  <el-icon :size="28" color="#F56C6C"><DocumentCopy /></el-icon>
                </div>
                <div class="grid-content">
                  <div class="grid-value">{{ getResourceTypeCount('api_doc') }}</div>
                  <div class="grid-label">API文档</div>
                </div>
              </div>
            </div>
          </div>
          <div class="project-card-footer">
            <el-button size="large" @click="formData.project_id = '' as number | ''">
              <el-icon><RefreshLeft /></el-icon>
              重新选择
            </el-button>
            <el-button type="primary" size="large" @click="goToNextStep">
              下一步：选择需求
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  FolderOpened,
  Document,
  MagicStick,
  DataAnalysis,
  Search,
  ArrowRight,
  Files,
  Picture,
  DocumentCopy,
  RefreshLeft,
} from '@element-plus/icons-vue'
import { useTestPointExtract } from '@/composables/useTestPointExtract'

const {
  formData,
  projects,
  files,
  selectedProjectInfo,
  handleProjectChange,
  goToNextStep,
  getResourceTypeCount,
} = useTestPointExtract()
</script>
