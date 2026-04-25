<template>
  <div class="requirement-uploader">
    <el-upload
      ref="uploadRef"
      drag
      multiple
      :auto-upload="false"
      :show-file-list="false"
      :on-change="handleFileChange"
      :accept="computedAccept"
      :limit="limit"
      :on-exceed="handleExceed"
      :disabled="disabled || uploading"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">拖拽文件到此处，或<em>点击上传</em></div>
      <template #tip>
        <div class="el-upload__tip">
          支持 doc/docx/pdf/xlsx/png/jpg 等格式，最多{{ limit }}个文件，类型自动识别
        </div>
      </template>
    </el-upload>

    <!-- 全局资源类型覆盖 + 清空 -->
    <div v-if="previewList.length > 0" class="global-override">
      <span class="override-label">统一资源类型：</span>
      <el-select
        v-model="globalResourceType"
        placeholder="自动识别"
        clearable
        size="small"
        style="width: 150px"
      >
        <el-option
          v-for="opt in RESOURCE_TYPE_OPTIONS"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-button type="danger" size="small" text style="margin-left: auto" @click="clearFiles">
        清空文件
      </el-button>
    </div>

    <!-- 文件预览列表 -->
    <div v-if="previewList.length > 0" class="file-preview">
      <div v-for="item in previewList" :key="item.uid" class="preview-item">
        <span class="file-name" :title="item.name">{{ item.name }}</span>
        <span class="file-size">{{ formatFileSize(item.size) }}</span>
        <el-tag size="small" :type="RESOURCE_TYPE_TAG_MAP[item.effectiveType] ?? 'info'">
          {{ getResourceTypeLabel(item.effectiveType) }}
        </el-tag>
      </div>
    </div>

    <!-- 上传按钮 -->
    <div v-if="showUploadButton && previewList.length > 0" class="upload-actions">
      <el-button
        type="primary"
        :loading="uploading"
        :disabled="!projectId"
        @click="handleUpload"
      >
        开始上传（{{ previewList.length }}个文件）
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { fileApi, type FileBatchUploadResponse } from '@/api/file'
import {
  RESOURCE_TYPE_OPTIONS,
  RESOURCE_TYPE_TAG_MAP,
  detectResourceType,
  getResourceTypeLabel,
} from '@/constants/resource'

/** 预览项 */
interface PreviewItem {
  uid: string
  name: string
  size: number
  raw: File
  detectedType: string
  effectiveType: string
}

const props = withDefaults(
  defineProps<{
    projectId: number | ''
    iterationId?: number | null
    description?: string
    accept?: string
    limit?: number
    showUploadButton?: boolean
    disabled?: boolean
  }>(),
  {
    iterationId: null,
    description: '',
    accept: '',
    limit: 20,
    showUploadButton: true,
    disabled: false,
  }
)

const emit = defineEmits<{
  (e: 'success', data: FileBatchUploadResponse): void
  (e: 'error', error: unknown): void
}>()

const uploadRef = ref()
const previewList = ref<PreviewItem[]>([])
const uploading = ref(false)
const globalResourceType = ref('')

const computedAccept = computed(
  () =>
    props.accept ||
    '.txt,.doc,.docx,.pdf,.md,.xlsx,.xls,.csv,.json,.yaml,.yml,.png,.jpg,.jpeg,.gif,.zip,.rar'
)

/** 格式化文件大小 */
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** 文件选择变化 */
const handleFileChange = (
  _file: unknown,
  fileList: { raw: File; uid: number | string }[]
): void => {
  previewList.value = fileList.map((f) => {
    const detected = detectResourceType(f.raw.name)
    return {
      uid: String(f.uid),
      name: f.raw.name,
      size: f.raw.size,
      raw: f.raw,
      detectedType: detected,
      effectiveType: globalResourceType.value || detected,
    }
  })
}

/** 文件数量超限 */
const handleExceed = (): void => {
  ElMessage.warning(`最多上传 ${props.limit} 个文件`)
}

/** 全局类型覆盖变化时同步 effectiveType */
watch(globalResourceType, (val) => {
  previewList.value.forEach((item) => {
    item.effectiveType = val || item.detectedType
  })
})

/** 清空文件 */
const clearFiles = (): void => {
  previewList.value = []
  globalResourceType.value = ''
  uploadRef.value?.clearFiles()
}

/** 执行上传 */
const handleUpload = async (): Promise<FileBatchUploadResponse | null> => {
  if (!props.projectId) {
    ElMessage.warning('请先选择项目')
    return null
  }
  if (previewList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return null
  }

  uploading.value = true
  try {
    const files = previewList.value.map((item) => item.raw)
    const resourceType = globalResourceType.value || 'other'
    // iteration_id: null/undefined/0 均不传，后端默认为 NULL（未关联迭代）
    const iterationIdParam =
      props.iterationId != null && props.iterationId > 0
        ? props.iterationId
        : undefined

    const response = await fileApi.batchUploadFiles(
      props.projectId as number,
      files,
      resourceType,
      props.description,
      '',
      iterationIdParam
    )

    const data = response?.data ?? response
    const successCount = data?.success_count ?? 0
    const failCount = data?.fail_count ?? 0

    if (failCount > 0) {
      ElMessage.warning(`上传完成：成功 ${successCount} 个，失败 ${failCount} 个`)
    } else {
      ElMessage.success(`成功上传 ${successCount} 个文件`)
    }

    emit('success', response)
    clearFiles()
    return response
  } catch (error: unknown) {
    ElMessage.error('批量上传失败')
    emit('error', error)
    return null
  } finally {
    uploading.value = false
  }
}

/** 文件数量 */
const fileCount = computed(() => previewList.value.length)

defineExpose({ upload: handleUpload, clearFiles, fileCount, uploading })
</script>

<style scoped>
.requirement-uploader {
  width: 100%;
}

.global-override {
  display: flex;
  align-items: center;
  margin-top: 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.override-label {
  font-size: 13px;
  color: #606266;
  margin-right: 8px;
  white-space: nowrap;
}

.file-preview {
  margin-top: 12px;
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.preview-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #f0f2f5;
  gap: 8px;
}

.preview-item:last-child {
  border-bottom: none;
}

.file-name {
  flex: 1;
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.file-size {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.upload-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
