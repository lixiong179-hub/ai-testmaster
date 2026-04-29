<template>
  <el-dialog
    :model-value="visible"
    title="追加上传UI原型图片"
    width="600px"
    :close-on-click-modal="false"
    @close="emit('update:visible', false)"
  >
    <el-upload
      class="upload-component"
      action=""
      :auto-upload="false"
      :limit="20"
      :multiple="true"
      :on-change="handleFileChange"
      :on-remove="handleFileRemove"
      :on-exceed="handleExceed"
      accept=".png,.jpg,.jpeg,.gif,.webp,.bmp,.zip"
      drag
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">
        拖拽文件到此处，或<em>点击上传</em>（最多20张，支持ZIP压缩包）
      </div>
      <template #tip>
        <div class="el-upload__tip">
          支持批量上传UI原型图：png, jpg, jpeg, gif, webp, bmp 格式，最多20张
        </div>
      </template>
    </el-upload>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="handleSubmit" :loading="uploading">确定上传</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  uploading: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'submit': [files: File[]]
}>()

const appendFiles = ref<File[]>([])

watch(() => props.visible, (val) => {
  if (val) {
    appendFiles.value = []
  }
})

const updateFileList = (_file: File, fileList: File[]) => {
  appendFiles.value = fileList.map((f: File & { raw?: File }) => f.raw || f)
}

const handleFileChange = updateFileList
const handleFileRemove = updateFileList

const handleExceed = () => {
  ElMessage.warning('最多上传20个文件')
}

const handleSubmit = () => {
  if (appendFiles.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  emit('submit', appendFiles.value)
}
</script>

<style scoped>
.upload-component {
  width: 100%;
}

.upload-component :deep(.el-upload) {
  width: 100%;
}

.upload-component :deep(.el-upload-dragger) {
  width: 100%;
}
</style>
