<template>
  <div v-if="currentStep === 0" class="upload-area">
    <div
      class="upload-drop-zone"
      :class="{ 'is-dragover': isDragover }"
      @click="triggerFileInput"
      @drop.prevent="handleDrop"
      @dragover.prevent="isDragover = true"
      @dragleave.prevent="isDragover = false"
    >
      <input
        ref="fileInputRef"
        type="file"
        accept=".xmind"
        style="display: none"
        @change="handleFileChange"
      />
      <el-icon :size="48" color="#409EFF"><Upload /></el-icon>
      <p class="upload-text">点击或拖拽上传 XMind 文件</p>
      <p class="upload-hint">
        支持 {{ XMIND_IMPORT_CONFIG.ACCEPT }} 格式，{{ XMIND_IMPORT_CONFIG.SIZE_HINT }}
      </p>
    </div>
    <div v-if="selectedFile" class="file-info">
      <el-icon color="#67C23A"><Document /></el-icon>
      <span class="file-name">{{ selectedFile.name }}</span>
      <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
      <el-icon class="file-remove" @click="clearFile"><Close /></el-icon>
    </div>
    <div v-if="loading && aiEnhance && importProgressText" class="import-progress-area">
      <el-progress
        v-if="importProgress && importProgress.total_batches > 1"
        :percentage="importProgress!.percentage"
        :stroke-width="18"
        :text-inside="true"
        status=""
        :format="() => `${importProgress!.completed_batches}/${importProgress!.total_batches} 批次`"
      />
      <div class="import-progress-text">{{ importProgressText }}</div>
    </div>
    <div class="ai-enhance-toggle">
      <div class="ai-enhance-row">
        <el-switch v-model="aiEnhance" active-text="AI增强" inline-prompt />
        <span class="ai-enhance-label">AI增强模式</span>
      </div>
      <div class="ai-enhance-desc">
        开启后将调用大模型，将思维导图路径智能转换为结构化测试用例，自动生成操作步骤与预期结果，适合需要详细用例的场景。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue'
import { Upload, Document, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { XMIND_IMPORT_CONFIG } from '@/constants/resource'
import { XmindImportKey } from '../useXmindImport'

const mgmt = inject(XmindImportKey)!
const {
  currentStep,
  selectedFile,
  loading,
  aiEnhance,
  importProgress,
  importProgressText,
  isDragover,
  formatFileSize,
} = mgmt

const fileInputRef = ref<HTMLInputElement>()

function triggerFileInput() {
  fileInputRef.value?.click()
}
function validateFile(file: File): boolean {
  if (!file.name.endsWith('.xmind')) {
    ElMessage.error('请选择 .xmind 格式的文件')
    return false
  }
  if (file.size > XMIND_IMPORT_CONFIG.MAX_FILE_SIZE) {
    ElMessage.error(XMIND_IMPORT_CONFIG.SIZE_HINT)
    return false
  }
  return true
}
function handleFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file && validateFile(file)) selectedFile.value = file
}
function handleDrop(event: DragEvent) {
  isDragover.value = false
  const file = event.dataTransfer?.files[0]
  if (file && validateFile(file)) selectedFile.value = file
}
function clearFile() {
  selectedFile.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}
</script>

<style scoped>
.upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.upload-drop-zone {
  width: 100%;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.3s;
}
.upload-drop-zone:hover,
.upload-drop-zone.is-dragover {
  border-color: #409eff;
  background: #ecf5ff;
}
.upload-text {
  font-size: 16px;
  color: #606266;
  margin: 12px 0 4px;
}
.upload-hint {
  font-size: 12px;
  color: #909399;
}
.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f0f9eb;
  border-radius: 4px;
  width: 100%;
}
.file-name {
  flex: 1;
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size {
  font-size: 12px;
  color: #909399;
}
.file-remove {
  cursor: pointer;
  color: #909399;
}
.file-remove:hover {
  color: #f56c6c;
}
.import-progress-area {
  width: 100%;
  padding: 12px 0 4px;
}
.import-progress-text {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
  text-align: center;
}
.ai-enhance-toggle {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  width: 100%;
  padding: 8px 0;
  gap: 6px;
}
.ai-enhance-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-enhance-label {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}
.ai-enhance-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  padding-left: 2px;
}
</style>
