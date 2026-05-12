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
@import './test-point-extract.css';
</style>
