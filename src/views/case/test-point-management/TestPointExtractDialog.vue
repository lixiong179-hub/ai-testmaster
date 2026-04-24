<template>
  <el-dialog
    v-model="visible"
    title="从需求提取测试点"
    class="test-point-extract-dialog"
    width="960px"
    :close-on-click-modal="false"
    @closed="resetState"
  >
    <div class="extract-dialog">
      <div class="dialog-hero">
        <div>
          <div class="hero-title">在当前工作台内完成提取和入库</div>
          <div class="hero-subtitle">
            选择一个需求文档后即可直接提取并保存到当前项目，无需跳转旧向导页面。
          </div>
        </div>
        <el-tag effect="dark" type="primary">需求提取</el-tag>
      </div>

      <div class="extract-toolbar">
        <el-select
          v-model="selectedFileId"
          filterable
          placeholder="请选择需求文档"
          class="file-select"
          :loading="loadingFiles"
        >
          <el-option
            v-for="file in requirementFiles"
            :key="file.id"
            :label="file.file_name"
            :value="file.id"
          >
            <div class="file-option">
              <span>{{ file.file_name }}</span>
              <el-tag size="small" type="info">{{
                formatExtractStatus(file.extract_status)
              }}</el-tag>
            </div>
          </el-option>
        </el-select>
        <el-button
          type="primary"
          :loading="extracting"
          :disabled="!selectedFileId"
          @click="handleExtract"
        >
          提取测试点
        </el-button>
        <el-button
          type="success"
          :loading="saving"
          :disabled="extractedPoints.length === 0"
          @click="handleSave"
        >
          保存到管理列表
        </el-button>
      </div>

      <div v-if="extracting" class="progress-panel">
        <el-progress :percentage="progress" />
        <p class="progress-text">{{ progressText }}</p>
      </div>

      <el-empty
        v-else-if="requirementFiles.length === 0 && !loadingFiles"
        description="当前项目暂无需求文档，请先在资源管理中上传 requirement 类型文件"
      >
        <template #image>
          <div class="empty-illustration">TP</div>
        </template>
      </el-empty>

      <template v-else>
        <div v-if="extractedPoints.length > 0" class="extract-summary">
          <el-tag type="info">共 {{ extractedPoints.length }} 条</el-tag>
          <el-tag type="danger">高优先级 {{ highPriorityCount }}</el-tag>
          <el-tag type="warning">中优先级 {{ mediumPriorityCount }}</el-tag>
          <el-tag type="success">低优先级 {{ lowPriorityCount }}</el-tag>
        </div>

        <el-table
          class="extract-table"
          :data="extractedPoints"
          border
          stripe
          height="420"
          empty-text="请选择需求文档并提取测试点"
        >
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="module" label="模块" min-width="140" show-overflow-tooltip />
          <el-table-column prop="function" label="功能" min-width="180" show-overflow-tooltip />
          <el-table-column prop="point" label="测试点" min-width="320" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="{ row }">
              <el-tag :type="priorityTagType(row.priority)">{{
                priorityText(row.priority)
              }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </template>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fileApi, type ProjectFile } from '@/api/file'
import { testPointApi, type TestPointDraft } from '@/api/testPoint'

const props = defineProps<{
  projectId: number
  initialFileId?: number | null
}>()

const emit = defineEmits<{
  (e: 'saved'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })

const loadingFiles = ref(false)
const extracting = ref(false)
const saving = ref(false)
const progress = ref(0)
const progressText = ref('准备提取...')
const selectedFileId = ref<number | undefined>(undefined)
const files = ref<ProjectFile[]>([])
const extractedPoints = ref<TestPointDraft[]>([])
let progressTimer: ReturnType<typeof setInterval> | null = null

const requirementFiles = computed(() =>
  files.value.filter((file) => file.resource_type === 'requirement' && file.is_active !== false)
)
const highPriorityCount = computed(
  () => extractedPoints.value.filter((item) => item.priority === 1).length
)
const mediumPriorityCount = computed(
  () => extractedPoints.value.filter((item) => item.priority === 2).length
)
const lowPriorityCount = computed(
  () => extractedPoints.value.filter((item) => item.priority === 3).length
)

watch(
  () => visible.value,
  async (open) => {
    if (!open || !props.projectId) {
      return
    }
    await loadFiles()
  }
)

watch(
  () => props.initialFileId,
  (fileId) => {
    if (visible.value && fileId) {
      selectedFileId.value = fileId
    }
  }
)

function startFakeProgress(): void {
  stopFakeProgress()
  progress.value = 0
  progressText.value = '正在读取文件内容...'
  const phases = [
    { limit: 25, text: '正在读取文件内容...' },
    { limit: 55, text: '正在解析文档结构...' },
    { limit: 80, text: 'AI 正在提取测试点...' },
    { limit: 92, text: '正在整理提取结果...' },
  ]
  let phaseIndex = 0
  progressTimer = setInterval(() => {
    const phase = phases[phaseIndex]
    if (!phase) {
      return
    }
    if (progress.value < phase.limit) {
      progress.value = Math.min(progress.value + Math.round(Math.random() * 4 + 1), phase.limit)
      progressText.value = phase.text
      return
    }
    phaseIndex += 1
  }, 250)
}

function stopFakeProgress(): void {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

async function loadFiles(): Promise<void> {
  loadingFiles.value = true
  try {
    const response = await fileApi.getFileList(props.projectId, undefined, 1, 200)
    files.value = response.data.items || []
    if (props.initialFileId && files.value.some((file) => file.id === props.initialFileId)) {
      selectedFileId.value = props.initialFileId
    } else if (!selectedFileId.value && requirementFiles.value.length > 0) {
      selectedFileId.value = requirementFiles.value[0].id
    }
  } catch (error) {
    files.value = []
    ElMessage.error(error instanceof Error ? error.message : '加载需求文档失败')
  } finally {
    loadingFiles.value = false
  }
}

async function handleExtract(): Promise<void> {
  if (!selectedFileId.value) {
    ElMessage.warning('请先选择需求文档')
    return
  }
  extracting.value = true
  extractedPoints.value = []
  startFakeProgress()
  try {
    const response = await testPointApi.extract({ file_id: selectedFileId.value })
    extractedPoints.value = response.items.map((item, index) => ({
      id: item.id || index + 1,
      module: item.module || '',
      function: item.function || '',
      point: item.point || '',
      priority: item.priority || 2,
      ai_prompt: item.ai_prompt ?? undefined,
      create_time: item.create_time,
    }))
    progress.value = 100
    progressText.value = `提取完成，共 ${extractedPoints.value.length} 个测试点`
    ElMessage.success(progressText.value)
  } catch (error) {
    progress.value = 0
    progressText.value = '提取失败'
    ElMessage.error(error instanceof Error ? error.message : '提取测试点失败')
  } finally {
    stopFakeProgress()
    extracting.value = false
  }
}

async function handleSave(): Promise<void> {
  if (extractedPoints.value.length === 0) {
    ElMessage.warning('没有可保存的测试点')
    return
  }
  saving.value = true
  try {
    const payload = extractedPoints.value
      .map((item) => ({
        module: item.module,
        function: item.function,
        point: item.point,
        priority: item.priority,
        ai_prompt: item.ai_prompt ?? undefined,
      }))
      .filter((item) => item.module && item.point)
    const response = await testPointApi.batchSave(props.projectId, payload)
    ElMessage.success(response.message || `成功保存 ${response.data.saved_count} 个测试点`)
    emit('saved')
    visible.value = false
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '保存测试点失败')
  } finally {
    saving.value = false
  }
}

function resetState(): void {
  stopFakeProgress()
  extracting.value = false
  saving.value = false
  progress.value = 0
  progressText.value = '准备提取...'
  extractedPoints.value = []
  if (props.initialFileId) {
    selectedFileId.value = props.initialFileId
  } else if (requirementFiles.value.length > 0) {
    selectedFileId.value = requirementFiles.value[0].id
  } else {
    selectedFileId.value = undefined
  }
}

function priorityText(priority: number): string {
  return priority === 1 ? '高' : priority === 2 ? '中' : '低'
}

function priorityTagType(priority: number): 'danger' | 'warning' | 'info' {
  return priority === 1 ? 'danger' : priority === 2 ? 'warning' : 'info'
}

function formatExtractStatus(status?: string): string {
  if (status === 'completed') return '已提取'
  if (status === 'processing') return '提取中'
  if (status === 'failed') return '提取失败'
  return '待提取'
}
</script>

<style scoped>
.extract-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dialog-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.12), rgba(103, 194, 58, 0.08));
  border-radius: 18px;
}

.hero-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2d3d;
}

.hero-subtitle {
  margin-top: 6px;
  color: #6b7684;
  line-height: 1.6;
}

.extract-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 20px;
  border: 1px solid rgba(220, 230, 241, 0.9);
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #fafcff 100%);
}

.file-select {
  width: 420px;
}

.file-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.progress-panel {
  padding: 16px 18px;
  background: linear-gradient(180deg, #f7faff 0%, #f3f7fd 100%);
  border: 1px solid rgba(220, 230, 241, 0.9);
  border-radius: 16px;
}

.progress-text {
  margin: 10px 0 0;
  color: #606266;
}

.extract-summary {
  display: flex;
  gap: 8px;
  align-items: center;
}

.extract-table :deep(.el-table__header th) {
  background: #f7faff;
  color: #4a5565;
  font-weight: 700;
}

.empty-illustration {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 84px;
  height: 84px;
  margin: 0 auto;
  border-radius: 24px;
  background: linear-gradient(135deg, rgba(64, 158, 255, 0.16), rgba(103, 194, 58, 0.14));
  color: #409eff;
  font-size: 28px;
  font-weight: 700;
}

.test-point-extract-dialog :deep(.el-dialog) {
  border-radius: 24px;
  overflow: hidden;
}

@media (max-width: 900px) {
  .dialog-hero,
  .extract-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .file-select {
    width: 100%;
  }
}
</style>
