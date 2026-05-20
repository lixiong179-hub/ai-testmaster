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
        <el-select v-model="selectedFileId" filterable placeholder="请选择需求文档" class="file-select" :loading="loadingFiles">
          <el-option v-for="file in requirementFiles" :key="file.id" :label="file.file_name" :value="file.id">
            <div class="file-option">
              <span>{{ file.file_name }}</span>
              <el-tag size="small" type="info">{{ formatExtractStatus(file.extract_status) }}</el-tag>
            </div>
          </el-option>
        </el-select>
        <el-button type="primary" :loading="extracting" :disabled="!selectedFileId" @click="handleExtract">提取测试点</el-button>
        <el-button type="success" :loading="saving" :disabled="extractedPoints.length === 0" @click="onSave">保存到管理列表</el-button>
      </div>

      <div v-if="extracting" class="progress-panel">
        <el-progress :percentage="progress" />
        <p class="progress-text">{{ progressText }}</p>
      </div>

      <el-empty v-else-if="requirementFiles.length === 0 && !loadingFiles" description="当前项目暂无需求文档，请先在资源管理中上传 requirement 类型文件">
        <template #image><div class="empty-illustration">TP</div></template>
      </el-empty>

      <template v-else>
        <div v-if="extractedPoints.length > 0" class="extract-summary">
          <el-tag type="info">共 {{ extractedPoints.length }} 条</el-tag>
          <el-tag type="danger">高优先级 {{ highPriorityCount }}</el-tag>
          <el-tag type="warning">中优先级 {{ mediumPriorityCount }}</el-tag>
          <el-tag type="success">低优先级 {{ lowPriorityCount }}</el-tag>
        </div>

        <el-table class="extract-table" :data="extractedPoints" border stripe height="420" empty-text="请选择需求文档并提取测试点">
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="module" label="模块" min-width="140" show-overflow-tooltip />
          <el-table-column prop="point" label="测试点" min-width="320" show-overflow-tooltip />
          <el-table-column prop="priority" label="优先级" width="100">
            <template #default="{ row }"><el-tag :type="priorityTagType(row.priority)">{{ priorityText(row.priority) }}</el-tag></template>
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
import { useTestPointExtract } from './useTestPointExtract'

const props = defineProps<{
  projectId: number
  initialFileId?: number | null
}>()

const emit = defineEmits<{
  (e: 'saved'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })

const {
  loadingFiles, extracting, saving, progress, progressText, selectedFileId,
  requirementFiles, extractedPoints, highPriorityCount, mediumPriorityCount, lowPriorityCount,
  handleExtract, handleSave, resetState, priorityText, priorityTagType, formatExtractStatus,
} = useTestPointExtract(props, visible)

const onSave = async () => { await handleSave(); emit('saved'); visible.value = false }
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
