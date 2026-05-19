<template>
  <el-dialog v-model="visible" title="导入 XMind 测试点" width="800px" :close-on-click-modal="false" @close="handleClose">
    <el-steps :active="currentStep" finish-status="success" simple class="xmind-steps">
      <el-step title="上传文件" />
      <el-step title="预览确认" />
      <el-step title="导入结果" />
    </el-steps>
    <div class="step-content">
      <XmindUploadStep />
      <XmindPreviewStep />
      <div v-if="currentStep === 2" class="result-area">
        <div v-if="importResult.success" class="result-success">
          <el-icon :size="64" color="#67C23A"><CircleCheck /></el-icon>
          <h3>导入成功</h3>
          <el-alert v-if="importResult.aiTimeout" type="warning" show-icon :closable="false" class="result-ai-timeout-alert">
            <template #title>AI增强解析超时，已自动降级为普通解析模式导入。如需使用AI增强，请稍后重试或检查网络连接。</template>
          </el-alert>
          <div class="result-stats">
            <el-statistic title="成功导入" :value="importResult.savedCount" />
            <el-statistic v-if="importResult.savedCaseCount > 0" title="生成用例" :value="importResult.savedCaseCount" />
            <el-statistic title="解析总数" :value="importResult.totalParsed" />
            <el-statistic v-if="importResult.skippedCount > 0" title="跳过" :value="importResult.skippedCount" />
          </div>
          <div v-if="importResult.skippedReasons.length > 0" class="skipped-reasons">
            <el-collapse>
              <el-collapse-item title="查看跳过原因">
                <el-tag v-for="(reason, index) in importResult.skippedReasons" :key="index" type="warning" style="margin: 2px">{{ reason }}</el-tag>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
        <div v-else class="result-error">
          <el-icon :size="64" color="#F56C6C"><CircleClose /></el-icon>
          <h3>导入失败</h3>
          <el-alert :title="importResult.errorMessage" type="error" show-icon />
        </div>
      </div>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button v-if="currentStep === 1" @click="currentStep = 0">重新选择</el-button>
        <el-button v-if="currentStep === 0" @click="handleClose">取消</el-button>
        <el-button v-if="currentStep === 0" type="primary" :disabled="!selectedFile" :loading="loading" @click="handlePreview">预览</el-button>
        <el-button v-if="currentStep === 1" type="primary" :loading="loading" @click="doImport">确认导入</el-button>
        <el-button v-if="currentStep === 2" type="primary" @click="resetState">继续导入</el-button>
        <el-button v-if="currentStep === 2 && importResult.success" @click="handleGoToList">查看测试点</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { provide } from 'vue'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { useXmindImport, XmindImportKey } from './useXmindImport'
import XmindUploadStep from './components/XmindUploadStep.vue'
import XmindPreviewStep from './components/XmindPreviewStep.vue'

const props = defineProps<{ projectId: number }>()
const emit = defineEmits<{ (e: 'imported'): void }>()
const visible = defineModel<boolean>('visible', { default: false })

const mgmt = useXmindImport(props.projectId)
provide(XmindImportKey, mgmt)

const { currentStep, selectedFile, loading, importResult, handlePreview, resetState } = mgmt

function doImport() { mgmt.handleImport(() => emit('imported')) }
function handleGoToList() { visible.value = false; emit('imported') }
function handleClose() { visible.value = false; resetState() }
</script>

<style scoped>
.xmind-steps { margin-bottom: 20px; }
.step-content { min-height: 300px; }
.result-area { text-align: center; padding: 20px; }
.result-stats { display: flex; justify-content: center; gap: 40px; margin: 20px 0; }
.skipped-reasons { text-align: left; margin-top: 16px; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
