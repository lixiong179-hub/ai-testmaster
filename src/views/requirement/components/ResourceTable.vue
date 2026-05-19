<template>
  <div class="resource-area">
    <el-card class="list-card">
      <template #header>
        <div class="resource-header">
          <span class="resource-title">{{ ctx.iterationManager.getCurrentIterationTitle() }}</span>
          <div class="resource-actions">
            <el-button type="success" @click="ctx.handleAddFileWrapper" :disabled="!ctx.resourceList.filterForm.project_id">
              <el-icon><Upload /></el-icon>上传文件
            </el-button>
          </div>
        </div>
      </template>
      <el-table :data="ctx.resourceList.resources" style="width: 100%" v-loading="ctx.resourceList.isLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="资源名称" min-width="200">
          <template #default="{ row }">
            <div class="resource-name-cell">
              <el-link v-if="row.resource_type === 'ui_mockup'" type="primary" underline="never" @click="ctx.handleEditWrapper(row)">{{ row.name }}</el-link>
              <el-link v-else-if="row.source_type === 'file' && row.id" type="primary" :href="`/api/v1/file/preview/${row.id}`" target="_blank" underline="never">{{ row.name }}</el-link>
              <span v-else>{{ row.name }}</span>
              <el-tag v-if="row.resource_type === 'ui_mockup' && row.screen_count" size="small" type="info" class="screen-count-tag">{{ row.screen_count }}张图片</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="ctx.resourceList.getResourceTypeTagType(row.resource_type)">{{ ctx.resourceList.getResourceTypeLabel(row.resource_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="upload_time" label="上传时间" width="180">
          <template #default="{ row }">{{ row.upload_time || row.created_at || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="ctx.resourceOperations.handleAnalyze(row)">AI分析</el-button>
            <el-button type="info" size="small" @click="ctx.handleEditWrapper(row)">{{ row.resource_type === 'ui_mockup' ? '查看' : '编辑' }}</el-button>
            <el-button type="danger" size="small" @click="ctx.resourceOperations.handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="empty-resources" v-if="!ctx.resourceList.isLoading && ctx.resourceList.resources.length === 0">
        <el-icon :size="60" color="#d0d5dd"><Files /></el-icon>
        <p class="empty-title">暂无资源</p>
        <p class="empty-desc">该迭代下还没有上传任何资源</p>
        <el-button type="primary" @click="ctx.handleAddFileWrapper"><el-icon><Upload /></el-icon>上传第一个文件</el-button>
      </div>
      <div class="pagination" v-if="ctx.resourceList.total > 0">
        <el-pagination
          v-model:current-page="ctx.resourceList.pagination.page"
          v-model:page-size="ctx.resourceList.pagination.pageSize"
          :page-sizes="RESOURCE_CONFIG.PAGE_SIZE_OPTIONS"
          layout="total, sizes, prev, pager, next, jumper"
          :total="ctx.resourceList.total"
          @size-change="ctx.resourceList.handleSizeChange"
          @current-change="ctx.resourceList.handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="ctx.resourceUpload.fileDialogVisible" :title="ctx.resourceUpload.fileDialogTitle" width="600px" :close-on-click-modal="false">
      <el-form ref="ctx.fileFormLocalRef.value" :model="ctx.resourceUpload.fileFormData" :rules="ctx.resourceUpload.fileFormRules" label-width="120px">
        <el-form-item label="项目" prop="project_id">
          <el-select v-model="ctx.resourceUpload.fileFormData.project_id" placeholder="请选择项目" style="width: 100%" :disabled="ctx.resourceUpload.fileDialogMode === 'edit'">
            <el-option v-for="project in ctx.projects.value" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属迭代" prop="iteration_id" v-if="ctx.resourceList.filterForm.project_id && (ctx.iterationManager.selectedIterationId === null || ctx.resourceUpload.fileDialogMode === 'edit')">
          <el-select v-model="ctx.resourceUpload.fileFormData.iteration_id" placeholder="请选择所属迭代" style="width: 100%" clearable>
            <el-option label="不归属任何迭代（未分类）" :value="0" />
            <template v-if="Array.isArray(ctx.validIterationsForSelectArray.value)">
              <el-option v-for="(it, idx) in ctx.validIterationsForSelectArray.value" :key="'iter-' + (it?.id ?? idx)" :label="`${it?.name ?? '未知'} (${it?.version ?? 'v1.0'})`" :value="it?.id" />
            </template>
          </el-select>
        </el-form-item>
        <el-form-item label="所属迭代" v-if="ctx.resourceList.filterForm.project_id && ctx.iterationManager.selectedIterationId !== null">
          <div class="iteration-hint">
            <el-tag v-if="ctx.iterationManager.selectedIterationId === 0" type="info">未分类</el-tag>
            <el-tag v-else type="success">{{ ctx.iterationManager.getCurrentIterationTitle() }}</el-tag>
          </div>
        </el-form-item>
        <el-form-item v-if="ctx.resourceUpload.fileDialogMode === 'edit'" label="资源名称" prop="name">
          <el-input v-model="ctx.resourceUpload.fileFormData.name" placeholder="如：需求文档v1.2、洪恩UI原型图v1.0" />
        </el-form-item>
        <el-form-item v-if="ctx.resourceUpload.fileDialogMode === 'edit'" label="资源类型" prop="resource_type">
          <el-select v-model="ctx.resourceUpload.fileFormData.resource_type" placeholder="请选择资源类型" style="width: 100%">
            <el-option v-for="option in RESOURCE_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="ctx.resourceUpload.fileDialogMode === 'add'" label="选择文件">
          <RequirementUploader ref="ctx.uploaderRef.value" :project-id="ctx.resourceUpload.fileFormData.project_id" :iteration-id="ctx.resourceUpload.fileFormData.iteration_id ?? null" :description="ctx.resourceUpload.fileFormData.description" :show-upload-button="false" @success="ctx.handleBatchUploadSuccess" @error="ctx.handleBatchUploadError" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="ctx.resourceUpload.fileFormData.description" type="textarea" :rows="2" placeholder="资源描述（可选）" />
        </el-form-item>
        <el-form-item v-if="ctx.resourceUpload.fileDialogMode === 'edit'" label="启用状态">
          <el-switch v-model="ctx.resourceUpload.fileFormData.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ctx.resourceUpload.fileDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="ctx.handleFileSubmitWrapper" :loading="ctx.isFileSubmitting.value">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Upload, Files } from '@element-plus/icons-vue'
import { useResourceManage, RESOURCE_TYPE_OPTIONS, RESOURCE_CONFIG } from '@/composables/requirement/useResourceManage'
import RequirementUploader from '@/components/RequirementUploader.vue'

const ctx = useResourceManage()
</script>

<style scoped>
.resource-area { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.list-card { flex: 1; display: flex; flex-direction: column; }
.list-card :deep(.el-card__body) { flex: 1; display: flex; flex-direction: column; }
.resource-header { display: flex; align-items: center; justify-content: space-between; padding: 4px 0; }
.resource-title { font-size: 16px; font-weight: 600; color: #303133; }
.resource-actions { display: flex; gap: 8px; }
.pagination { margin-top: 15px; display: flex; justify-content: flex-end; }
.resource-name-cell { display: flex; align-items: center; gap: 8px; }
.screen-count-tag { flex-shrink: 0; }
.iteration-hint { display: flex; align-items: center; }
.empty-resources { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; gap: 12px; }
.empty-title { font-size: 16px; font-weight: 600; color: #303133; margin: 8px 0 0; }
.empty-desc { font-size: 14px; color: #909399; margin: 0 0 16px; }
</style>
