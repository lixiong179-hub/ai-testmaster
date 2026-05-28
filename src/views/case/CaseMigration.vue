<template>
  <div class="case-migration-page">
    <div class="page-header">
      <div>
        <h2>用例迁移</h2>
        <p>将旧端 Excel 或历史用例迁移到新端 UI 原型，确认后入库为草稿用例。</p>
      </div>
      <el-button @click="router.push('/home/case')">返回用例列表</el-button>
    </div>

    <el-card shadow="never" class="step-card">
      <template #header>
        <div class="card-header">
          <span>迁移来源与目标</span>
          <el-tag type="primary">跨端/跨形态迁移</el-tag>
        </div>
      </template>
      <el-form label-width="120px">
        <el-form-item label="源项目">
          <el-select
            v-model="sourceProjectId"
            filterable
            placeholder="选择旧端项目"
            @change="loadSourceCases"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="设备类型">
          <el-select v-model="sourceDevice" class="device-select">
            <el-option label="平板" value="tablet" />
            <el-option label="手机" value="phone" />
            <el-option label="桌面" value="desktop" />
            <el-option label="Web" value="web" />
          </el-select>
          <span class="arrow-text">迁移到</span>
          <el-select v-model="targetDevice" class="device-select">
            <el-option label="手机" value="phone" />
            <el-option label="平板" value="tablet" />
            <el-option label="桌面" value="desktop" />
            <el-option label="Web" value="web" />
          </el-select>
        </el-form-item>
        <el-form-item label="Excel用例">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xls"
            :on-change="handleExcelChange"
            :on-remove="handleExcelRemove"
          >
            <el-button>选择旧端 Excel</el-button>
          </el-upload>
          <el-button
            type="primary"
            plain
            :disabled="!excelFile || !sourceProjectId"
            :loading="importing"
            @click="importExcel"
          >
            导入为迁移源
          </el-button>
        </el-form-item>
        <el-form-item label="源用例">
          <el-select
            v-model="selectedSourceCaseIds"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择要迁移的旧端用例"
            style="width: 720px"
          >
            <el-option
              v-for="testCase in sourceCases"
              :key="testCase.id"
              :label="caseOptionLabel(testCase)"
              :value="testCase.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标项目">
          <el-select
            v-model="targetProjectId"
            filterable
            placeholder="选择新端项目"
            @change="loadTargetUiProjects"
          >
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标UI原型">
          <el-select
            v-model="targetUiProjectId"
            filterable
            clearable
            placeholder="选择已解析的新端UI原型"
            style="width: 420px"
            @change="loadTargetScreens"
          >
            <el-option
              v-for="project in targetUiProjects"
              :key="project.id"
              :label="`${project.name} (${project.parsed_count}/${project.screen_count})`"
              :value="project.id"
            />
          </el-select>
          <el-tag v-if="targetScreens.length > 0" type="success" class="inline-tag">
            已解析 {{ targetScreens.length }} 个页面
          </el-tag>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :disabled="!canPreview"
            :loading="previewing"
            @click="previewMigration"
          >
            生成迁移预览
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="previewData" shadow="never" class="step-card">
      <template #header>
        <div class="card-header">
          <span>迁移预览</span>
          <el-tag>{{ previewData.batch_id }}</el-tag>
        </div>
      </template>
      <div class="summary-row">
        <el-statistic title="总数" :value="previewData.summary.total" />
        <el-statistic title="成功" :value="previewData.summary.success" />
        <el-statistic title="失败" :value="previewData.summary.failed" />
        <el-statistic title="改写" :value="previewData.summary.adapted" />
        <el-statistic title="拆分" :value="previewData.summary.split" />
        <el-statistic title="废弃" :value="previewData.summary.deprecated" />
      </div>
      <el-table :data="previewData.items" stripe>
        <el-table-column label="源用例" prop="source_case_id" width="100" />
        <el-table-column label="迁移类型" width="120">
          <template #default="{ row }">
            <el-tag :type="migrationTypeTag(row.migration_type)">{{
              migrationTypeText(row.migration_type)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="140">
          <template #default="{ row }">{{ Math.round((row.confidence || 0) * 100) }}%</template>
        </el-table-column>
        <el-table-column label="产出用例" min-width="260">
          <template #default="{ row }">
            <div v-for="item in row.preview_cases" :key="item.title" class="preview-case-title">
              {{ item.title }}
            </div>
            <el-text v-if="row.preview_cases.length === 0" type="info">无新增用例</el-text>
          </template>
        </el-table-column>
        <el-table-column label="问题" min-width="220">
          <template #default="{ row }">
            <el-text v-if="row.errors.length > 0" type="danger">{{
              row.errors.join('；')
            }}</el-text>
            <el-text v-else-if="row.warnings.length > 0" type="warning">{{
              row.warnings.join('；')
            }}</el-text>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
      <div class="commit-actions">
        <el-button type="primary" :loading="committing" @click="commitMigration"
          >确认入库为草稿用例</el-button
        >
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import projectApi, { type Project } from '@/api/project'
import { caseApi } from '@/api/case'
import type { TestCase } from '@/types/testCase'
import { uiPrototypeApi, type UIPrototypeProject, type UIScreen } from '@/api/uiPrototype'
import {
  caseMigrationApi,
  caseOptionLabel,
  summarizeUiSpecs,
  type DeviceType,
  type MigrationPreviewResponse,
  type MigrationType,
} from '@/api/caseMigration'

const router = useRouter()
const projects = ref<Project[]>([])
const sourceProjectId = ref<number>()
const targetProjectId = ref<number>()
const sourceDevice = ref<DeviceType>('tablet')
const targetDevice = ref<DeviceType>('phone')
const excelFile = ref<File | null>(null)
const sourceCases = ref<TestCase[]>([])
const selectedSourceCaseIds = ref<number[]>([])
const targetUiProjects = ref<UIPrototypeProject[]>([])
const targetUiProjectId = ref<number>()
const targetScreens = ref<UIScreen[]>([])
const importing = ref(false)
const previewing = ref(false)
const committing = ref(false)
const previewData = ref<MigrationPreviewResponse | null>(null)

const canPreview = computed(
  () =>
    selectedSourceCaseIds.value.length > 0 &&
    Boolean(targetProjectId.value) &&
    sourceDevice.value !== targetDevice.value &&
    targetScreens.value.length > 0
)

async function loadProjects(): Promise<void> {
  const response = await projectApi.getProjects({ page: 1, page_size: 200 })
  projects.value = response.data.items
}

async function loadSourceCases(): Promise<void> {
  if (!sourceProjectId.value) return
  const response = await caseApi.getList(sourceProjectId.value, { page: 1, page_size: 200 })
  sourceCases.value = response.items
}

async function loadTargetUiProjects(): Promise<void> {
  targetUiProjectId.value = undefined
  targetScreens.value = []
  if (!targetProjectId.value) return
  targetUiProjects.value = await uiPrototypeApi.getUIPrototypeProjectList(targetProjectId.value)
}

async function loadTargetScreens(): Promise<void> {
  targetScreens.value = []
  if (!targetProjectId.value || !targetUiProjectId.value) return
  const response = await uiPrototypeApi.getUIScreenList(
    targetProjectId.value,
    targetUiProjectId.value
  )
  targetScreens.value = response.data.items.filter((screen) => screen.parse_status === 'completed')
}

function handleExcelChange(uploadFile: UploadFile): void {
  excelFile.value = uploadFile.raw || null
}

function handleExcelRemove(): void {
  excelFile.value = null
}

async function importExcel(): Promise<void> {
  if (!excelFile.value || !sourceProjectId.value) return
  importing.value = true
  try {
    const result = await caseMigrationApi.importExcel({
      file: excelFile.value,
      projectId: sourceProjectId.value,
      targetDevice: sourceDevice.value,
    })
    selectedSourceCaseIds.value = [
      ...new Set([...selectedSourceCaseIds.value, ...result.imported_case_ids]),
    ]
    await loadSourceCases()
    ElMessage.success(`导入 ${result.imported_count} 条源用例`)
  } finally {
    importing.value = false
  }
}

async function previewMigration(): Promise<void> {
  if (!targetProjectId.value) return
  previewing.value = true
  try {
    previewData.value = await caseMigrationApi.previewBatch({
      sourceCaseIds: selectedSourceCaseIds.value,
      sourceDevice: sourceDevice.value,
      targetDevice: targetDevice.value,
      targetProjectId: targetProjectId.value,
      targetUiSpecs: summarizeUiSpecs(targetScreens.value),
    })
    ElMessage.success('迁移预览已生成')
  } finally {
    previewing.value = false
  }
}

async function commitMigration(): Promise<void> {
  if (!previewData.value || !targetProjectId.value) return
  committing.value = true
  try {
    const result = await caseMigrationApi.commitBatch({
      batchId: previewData.value.batch_id,
      targetProjectId: targetProjectId.value,
      targetDevice: targetDevice.value,
      items: previewData.value.items,
    })
    if (result.errors.length > 0) {
      ElMessage.warning(`已创建 ${result.created_case_ids.length} 条，部分失败`)
      return
    }
    ElMessage.success(`已创建 ${result.created_case_ids.length} 条草稿用例`)
  } finally {
    committing.value = false
  }
}

function migrationTypeText(type: MigrationType): string {
  const map: Record<MigrationType, string> = {
    cloned: '直接复用',
    adapted: '改写',
    split: '拆分',
    new: '新增',
    deprecated: '废弃',
  }
  return map[type]
}

function migrationTypeTag(
  type: MigrationType
): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (type === 'deprecated') return 'danger'
  if (type === 'split') return 'warning'
  if (type === 'cloned') return 'success'
  if (type === 'new') return 'primary'
  return 'info'
}

onMounted(loadProjects)
</script>

<style scoped>
.case-migration-page {
  padding: 20px;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 18px;
}
.page-header h2 {
  margin: 0 0 6px;
  font-size: 20px;
}
.page-header p {
  margin: 0;
  color: #606266;
}
.step-card {
  margin-bottom: 18px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.device-select {
  width: 160px;
}
.arrow-text {
  margin: 0 12px;
  color: #909399;
}
.inline-tag {
  margin-left: 12px;
}
.summary-row {
  display: flex;
  gap: 28px;
  padding: 12px 16px;
  margin-bottom: 14px;
  background: #f8f9fb;
  border-radius: 8px;
}
.preview-case-title {
  line-height: 1.8;
  color: #303133;
}
.commit-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
