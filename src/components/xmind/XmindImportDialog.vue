<template>
  <el-dialog
    v-model="visible"
    title="导入 XMind 测试点"
    width="800px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-steps :active="currentStep" finish-status="success" simple class="xmind-steps">
      <el-step title="上传文件" />
      <el-step title="预览确认" />
      <el-step title="导入结果" />
    </el-steps>

    <div class="step-content">
      <!-- Step 0: 上传 -->
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
        <div class="ai-enhance-toggle">
          <el-tooltip
            content="AI增强模式会使用大模型将思维导图路径转换为结构化测试用例，生成更详细的步骤和预期结果"
            placement="top"
          >
            <el-switch
              v-model="aiEnhance"
              active-text="AI增强模式"
              inline-prompt
            />
          </el-tooltip>
        </div>
      </div>

      <!-- Step 1: 预览 -->
      <div v-if="currentStep === 1" class="preview-area">
        <div class="preview-header">
          <el-tag type="info">测试点 {{ previewData.length }} 条</el-tag>
          <el-tag v-if="previewCaseData.length > 0" type="primary">
            测试用例 {{ previewCaseData.length }} 条
          </el-tag>
          <el-tag v-if="isCasePreviewMode" type="success">识别为场景树导入</el-tag>
          <el-tag type="danger">高优先级: {{ highPriorityCount }}</el-tag>
          <el-tag type="warning">中优先级: {{ mediumPriorityCount }}</el-tag>
          <el-tag type="success">低优先级: {{ lowPriorityCount }}</el-tag>
          <el-tag v-if="previewSkippedCount > 0" type="warning">
            已跳过 {{ previewSkippedCount }} 个节点
          </el-tag>
        </div>
        <el-alert
          v-if="previewSkippedCount > 0"
          type="warning"
          show-icon
          :closable="false"
          class="preview-skipped-alert"
        >
          <template #title>
            检测到 {{ previewSkippedCount }} 个节点未导入预览，常见原因是模块名或测试点名称为空。
          </template>
          <div v-if="previewSkippedReasons.length > 0" class="preview-skipped-reasons">
            <el-tag
              v-for="(reason, index) in previewSkippedReasons"
              :key="index"
              type="warning"
              effect="plain"
            >
              {{ reason }}
            </el-tag>
          </div>
        </el-alert>
        <el-alert
          v-if="isCasePreviewMode"
          type="info"
          show-icon
          :closable="false"
          class="preview-mode-alert"
        >
          <template #title>
            该 XMind 将按"测试点 + 测试用例"双通道导入，可切换查看两种预览视图。
          </template>
        </el-alert>
        <el-alert
          v-if="previewAiTimeout"
          type="warning"
          show-icon
          :closable="false"
          class="preview-ai-timeout-alert"
        >
          <template #title>
            AI增强解析超时，已自动降级为普通解析模式。如需使用AI增强，请稍后重试或检查网络连接。
          </template>
        </el-alert>
        <div v-if="hasCasePreview" class="preview-switcher">
          <el-radio-group v-model="activePreviewTab" size="small" @change="handlePreviewTabChange">
            <el-radio-button label="points">测试点预览</el-radio-button>
            <el-radio-button label="cases">测试用例预览</el-radio-button>
          </el-radio-group>
        </div>
        <el-table
          v-if="activePreviewTab === 'points'"
          :data="paginatedPreviewData"
          border
          stripe
          v-loading="loading"
          height="360"
          style="width: 100%"
        >
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
          <el-table-column prop="function" label="功能" width="150" show-overflow-tooltip />
          <el-table-column prop="point" label="测试点描述" min-width="250" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="scope">
              <el-tag :type="getPriorityType(scope.row.priority)">
                {{ getPriorityLabel(scope.row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <el-table
          v-else
          :data="paginatedPreviewCases"
          border
          stripe
          v-loading="loading"
          height="360"
          style="width: 100%"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="case-step-list">
                <div v-if="row.precondition" class="case-step-block">
                  <div class="case-step-title">前置条件</div>
                  <div class="case-step-text">{{ row.precondition }}</div>
                </div>
                <div class="case-step-block">
                  <div class="case-step-title">操作步骤</div>
                  <ol class="case-step-ordered">
                    <li v-for="step in row.steps" :key="`${row.title}-${step.step_number}`">
                      <div>{{ step.action }}</div>
                      <div v-if="step.expected_result" class="case-step-expected">
                        预期：{{ step.expected_result }}
                      </div>
                    </li>
                  </ol>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
          <el-table-column prop="function" label="功能" width="140" show-overflow-tooltip />
          <el-table-column prop="title" label="用例标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="步骤摘要" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="case-step-summary">
                <el-tag size="small" type="info">{{ row.step_count }} 步</el-tag>
                <span>{{ formatCaseStepSummary(row) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            prop="expected_result"
            label="预期结果"
            min-width="220"
            show-overflow-tooltip
          />
          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :type="getPriorityType(row.priority)">
                {{ getPriorityLabel(row.priority) }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
        <div class="preview-pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="currentPreviewTotal"
            layout="prev, pager, next"
            small
          />
        </div>
      </div>

      <!-- Step 2: 结果 -->
      <div v-if="currentStep === 2" class="result-area">
        <div v-if="importResult.success" class="result-success">
          <el-icon :size="64" color="#67C23A"><CircleCheck /></el-icon>
          <h3>导入成功</h3>
          <el-alert
            v-if="importResult.aiTimeout"
            type="warning"
            show-icon
            :closable="false"
            class="result-ai-timeout-alert"
          >
            <template #title>
              AI增强解析超时，已自动降级为普通解析模式导入。如需使用AI增强，请稍后重试或检查网络连接。
            </template>
          </el-alert>
          <div class="result-stats">
            <el-statistic title="成功导入" :value="importResult.savedCount" />
            <el-statistic
              v-if="importResult.savedCaseCount > 0"
              title="生成用例"
              :value="importResult.savedCaseCount"
            />
            <el-statistic title="解析总数" :value="importResult.totalParsed" />
            <el-statistic
              v-if="importResult.skippedCount > 0"
              title="跳过"
              :value="importResult.skippedCount"
            />
          </div>
          <div v-if="importResult.skippedReasons.length > 0" class="skipped-reasons">
            <el-collapse>
              <el-collapse-item title="查看跳过原因">
                <el-tag
                  v-for="(reason, index) in importResult.skippedReasons"
                  :key="index"
                  type="warning"
                  style="margin: 2px"
                >
                  {{ reason }}
                </el-tag>
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
        <el-button v-if="currentStep === 1" @click="handleBackToUpload">重新选择</el-button>
        <el-button v-if="currentStep === 0" @click="handleClose">取消</el-button>
        <el-button
          v-if="currentStep === 0"
          type="primary"
          :disabled="!selectedFile"
          :loading="loading"
          @click="handlePreview"
        >
          预览
        </el-button>
        <el-button v-if="currentStep === 1" type="primary" :loading="loading" @click="handleImport">
          确认导入
        </el-button>
        <el-button v-if="currentStep === 2" type="primary" @click="handleRetry">
          继续导入
        </el-button>
        <el-button v-if="currentStep === 2 && importResult.success" @click="handleGoToList">
          查看测试点
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Upload, Document, Close, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  testPointApi,
  type XmindPreviewItem,
  type XmindPreviewCaseItem,
  type XmindImportResponse,
  type XmindPreviewResponse,
} from '@/api/testPoint'
import { XMIND_IMPORT_CONFIG } from '@/constants/resource'

interface ImportResultData {
  success: boolean
  savedCount: number
  savedCaseCount: number
  totalParsed: number
  skippedCount: number
  skippedReasons: string[]
  errorMessage: string
  aiTimeout: boolean
}

const props = defineProps<{
  projectId: number
}>()

const emit = defineEmits<{
  (e: 'imported'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })

const currentStep = ref(0)
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const previewMode = ref<'test_points' | 'test_cases'>('test_points')
const previewData = ref<XmindPreviewItem[]>([])
const previewCaseData = ref<XmindPreviewCaseItem[]>([])
const previewSkippedCount = ref(0)
const previewSkippedReasons = ref<string[]>([])
const activePreviewTab = ref<'points' | 'cases'>('points')
const currentPage = ref(1)
const pageSize = 20
const isDragover = ref(false)
const fileInputRef = ref<HTMLInputElement>()
const aiEnhance = ref(false)
const previewAiTimeout = ref(false)

const importResult = ref<ImportResultData>({
  success: false,
  savedCount: 0,
  savedCaseCount: 0,
  totalParsed: 0,
  skippedCount: 0,
  skippedReasons: [],
  errorMessage: '',
  aiTimeout: false,
})

const paginatedPreviewData = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return previewData.value.slice(start, start + pageSize)
})

const paginatedPreviewCases = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return previewCaseData.value.slice(start, start + pageSize)
})

const hasCasePreview = computed(() => previewCaseData.value.length > 0)
const isCasePreviewMode = computed(() => previewMode.value === 'test_cases')
const currentPreviewTotal = computed(() =>
  activePreviewTab.value === 'cases' ? previewCaseData.value.length : previewData.value.length
)

const highPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 1).length)
const mediumPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 2).length)
const lowPriorityCount = computed(() => previewData.value.filter((i) => i.priority === 3).length)

const getPriorityType = (priority: number): string => {
  const map: Record<number, string> = { 1: 'danger', 2: 'warning', 3: 'success' }
  return map[priority] || 'info'
}

const getPriorityLabel = (priority: number): string => {
  const map: Record<number, string> = { 1: '高', 2: '中', 3: '低' }
  return map[priority] || '未知'
}

const formatCaseStepSummary = (item: XmindPreviewCaseItem): string => {
  if (!item.steps.length) return '无步骤'
  return item.steps.map((step) => step.action).join(' -> ')
}

const handlePreviewTabChange = () => {
  currentPage.value = 1
}

const formatFileSize = (size: number): string => {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const validateFile = (file: File): boolean => {
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

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file && validateFile(file)) {
    selectedFile.value = file
  }
}

const handleDrop = (event: DragEvent) => {
  isDragover.value = false
  const file = event.dataTransfer?.files[0]
  if (file && validateFile(file)) {
    selectedFile.value = file
  }
}

const clearFile = () => {
  selectedFile.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const getErrorMessage = (error: unknown, defaultMsg: string): string => {
  if (error && typeof error === 'object' && 'message' in error) {
    return String(error.message) || defaultMsg
  }
  return defaultMsg
}

const handlePreview = async () => {
  if (!selectedFile.value) return
  loading.value = true
  try {
    const data = (await testPointApi.importXmind(
      selectedFile.value,
      props.projectId,
      true,
      aiEnhance.value
    )) as XmindPreviewResponse
    previewMode.value = data.preview_mode || 'test_points'
    previewData.value = data.items || []
    previewCaseData.value = data.case_items || []
    previewSkippedCount.value = data.skipped_count || 0
    previewSkippedReasons.value = data.skipped_reasons || []
    previewAiTimeout.value = data.ai_timeout || false
    if (previewAiTimeout.value) {
      aiEnhance.value = false
    }
    activePreviewTab.value = data.preview_mode === 'test_cases' ? 'cases' : 'points'
    currentPage.value = 1
    currentStep.value = 1
  } catch (error: unknown) {
    const msg = getErrorMessage(error, '预览失败')
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const handleImport = async () => {
  if (!selectedFile.value) return
  loading.value = true
  try {
    const data = (await testPointApi.importXmind(
      selectedFile.value,
      props.projectId,
      false,
      aiEnhance.value
    )) as XmindImportResponse
    importResult.value = {
      success: true,
      savedCount: data.saved_count,
      savedCaseCount: data.saved_case_count || 0,
      totalParsed: data.total_parsed,
      skippedCount: data.skipped_count,
      skippedReasons: data.skipped_reasons || [],
      errorMessage: '',
      aiTimeout: data.ai_timeout || false,
    }
    currentStep.value = 2
    emit('imported')
  } catch (error: unknown) {
    const msg = getErrorMessage(error, '导入失败')
    importResult.value = {
      success: false,
      savedCount: 0,
      savedCaseCount: 0,
      totalParsed: 0,
      skippedCount: 0,
      skippedReasons: [],
      errorMessage: msg,
      aiTimeout: false,
    }
    currentStep.value = 2
  } finally {
    loading.value = false
  }
}

const handleBackToUpload = () => {
  currentStep.value = 0
}

const handleRetry = () => {
  currentStep.value = 0
  selectedFile.value = null
  aiEnhance.value = false
  previewAiTimeout.value = false
  previewMode.value = 'test_points'
  previewData.value = []
  previewCaseData.value = []
  previewSkippedCount.value = 0
  previewSkippedReasons.value = []
  activePreviewTab.value = 'points'
  importResult.value = {
    success: false,
    savedCount: 0,
    savedCaseCount: 0,
    totalParsed: 0,
    skippedCount: 0,
    skippedReasons: [],
    errorMessage: '',
    aiTimeout: false,
  }
}

const handleGoToList = () => {
  visible.value = false
  emit('imported')
}

const handleClose = () => {
  visible.value = false
  currentStep.value = 0
  selectedFile.value = null
  aiEnhance.value = false
  previewAiTimeout.value = false
  previewMode.value = 'test_points'
  previewData.value = []
  previewCaseData.value = []
  previewSkippedCount.value = 0
  previewSkippedReasons.value = []
  activePreviewTab.value = 'points'
  importResult.value = {
    success: false,
    savedCount: 0,
    savedCaseCount: 0,
    totalParsed: 0,
    skippedCount: 0,
    skippedReasons: [],
    errorMessage: '',
    aiTimeout: false,
  }
  loading.value = false
}
</script>

<style scoped>
.xmind-steps {
  margin-bottom: 20px;
}
.step-content {
  min-height: 300px;
}
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
.ai-enhance-toggle {
  display: flex;
  justify-content: flex-start;
  width: 100%;
  padding: 8px 0;
}
.preview-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.preview-header {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.preview-skipped-alert {
  margin-top: 4px;
}
.preview-mode-alert {
  margin-top: 4px;
}
.preview-switcher {
  display: flex;
  justify-content: flex-start;
}
.preview-skipped-reasons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.preview-pagination {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}
.case-step-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 4px;
}
.case-step-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.case-step-title {
  font-weight: 600;
  color: #303133;
}
.case-step-text {
  color: #606266;
  white-space: pre-wrap;
}
.case-step-ordered {
  margin: 0;
  padding-left: 20px;
  color: #606266;
}
.case-step-expected {
  color: #909399;
  font-size: 12px;
  margin-top: 2px;
}
.case-step-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}
.result-area {
  text-align: center;
  padding: 20px;
}
.result-stats {
  display: flex;
  justify-content: center;
  gap: 40px;
  margin: 20px 0;
}
.skipped-reasons {
  text-align: left;
  margin-top: 16px;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
