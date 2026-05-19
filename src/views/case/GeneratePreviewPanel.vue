<template>
  <div>
    <GenerateCaseConfigForm @prev="$emit('prev')" @generate="$emit('generate')" />
    <el-card v-if="store.generating" class="progress-card">
      <template #header><div class="card-header"><span>生成进度</span></div></template>
      <div class="progress-container">
        <el-progress :percentage="store.progress" :status="store.progressStatus" :stroke-width="20" />
        <div class="progress-text">{{ store.progressText }}</div>
        <el-button type="danger" @click="store.handleCancel" v-if="store.generating"><el-icon><Close /></el-icon>取消生成</el-button>
      </div>
    </el-card>
    <GenerateCaseResultCard @finish="handleFinish" />
    <el-card v-if="store.errorMessage" class="error-card">
      <template #header><div class="card-header"><span>生成失败</span></div></template>
      <div class="error-content">
        <el-alert :title="store.errorMessage" type="error" show-icon :closable="false" />
        <div v-if="store.errorSuggestions.length > 0" class="error-suggestions">
          <h4>优化建议：</h4>
          <ul><li v-for="(suggestion, index) in store.errorSuggestions" :key="index">{{ suggestion }}</li></ul>
        </div>
        <el-button type="primary" @click="handleRetry" style="margin-top: 15px"><el-icon><Refresh /></el-icon>重试</el-button>
      </div>
    </el-card>
    <FlowIssueDialog :visible="store.issueDialogVisible" :validation="store.issueDialogValidation" @confirm="store.onIssueDialogConfirm" @cancel="store.onIssueDialogCancel" />
  </div>
</template>

<script setup lang="ts">
import { Close, Refresh } from '@element-plus/icons-vue'
import { useGenerateStore } from '@/store/useGenerateStore'
import FlowIssueDialog from '@/components/case/FlowIssueDialog.vue'
import GenerateCaseConfigForm from './components/GenerateCaseConfigForm.vue'
import GenerateCaseResultCard from './components/GenerateCaseResultCard.vue'

const emit = defineEmits<{ prev: []; generate: [] }>()
const store = useGenerateStore()

const handleRetry = () => { store.handleRetry(); emit('generate') }
const handleFinish = () => { store.resetGenerateState(); store.currentStep = 0 }
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.progress-card, .error-card { margin-bottom: 20px; }
.progress-container { text-align: center; padding: 20px 0; }
.progress-text { margin: 15px 0; font-size: 16px; font-weight: 500; }
.error-content { padding: 10px 0; }
.error-suggestions { margin-top: 15px; padding: 15px; background: #fef0f0; border-radius: 4px; }
.error-suggestions h4 { margin-top: 0; color: #f56c6c; }
.error-suggestions ul { margin: 10px 0 0 0; padding-left: 20px; }
.error-suggestions li { margin-bottom: 5px; color: #606266; }
</style>
