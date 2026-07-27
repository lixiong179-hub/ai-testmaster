<template>
  <!-- 编辑对话框 -->
  <el-dialog v-model="editVisibleLocal" title="编辑用例" width="700px" destroy-on-close>
    <el-form v-if="editingCaseLocal" label-width="90px" size="default">
      <el-form-item label="标题" required>
        <el-input v-model="editingCaseLocal.title" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="模块">
        <el-input v-model="editingCaseLocal.module" maxlength="100" />
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="editingCaseLocal.priority">
          <el-option label="高" :value="1" />
          <el-option label="中" :value="2" />
          <el-option label="低" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item label="前置条件">
        <el-input v-model="editingCaseLocal.precondition" type="textarea" :rows="2" />
      </el-form-item>
      <el-form-item label="步骤" required>
        <div class="edit-steps">
          <div
            v-for="(step, i) in editingCaseLocal.steps"
            :key="i"
            class="edit-step-row"
          >
            <el-input-number :model-value="i + 1" disabled :controls="false" style="width: 48px" />
            <el-input
              :model-value="(step as Record<string, unknown>).action as string"
              @update:model-value="updateStepField(i, 'action', $event)"
              placeholder="操作"
              style="flex: 2"
            />
            <el-input
              :model-value="((step as Record<string, unknown>).expected_result as string) || ''"
              @update:model-value="updateStepField(i, 'expected_result', $event)"
              placeholder="预期结果"
              style="flex: 2"
            />
            <el-button text type="danger" @click="removeEditStep(i)">删除</el-button>
          </div>
          <el-button size="small" @click="addEditStep">+ 添加步骤</el-button>
        </div>
      </el-form-item>
      <el-form-item label="预期结果" required>
        <el-input v-model="editingCaseLocal.expected_result" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisibleLocal = false">取消</el-button>
      <el-button type="primary" @click="saveEdit">保存修改</el-button>
    </template>
  </el-dialog>

  <!-- 保存结果对话框 -->
  <el-dialog
    v-model="saveResultVisibleLocal"
    title="保存结果"
    width="560px"
    :close-on-click-modal="false"
    destroy-on-close
  >
    <template v-if="store.saveResult">
      <el-result
        :icon="
          store.saveResult.status === 'saved'
            ? 'success'
            : store.saveResult.status === 'partial_saved'
              ? 'warning'
              : 'error'
        "
        :title="
          store.saveResult.status === 'saved'
            ? '保存成功'
            : store.saveResult.status === 'partial_saved'
              ? '部分保存成功'
              : '保存失败'
        "
      >
        <template #extra>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="成功数量">{{
              store.saveResult.saved_count
            }}</el-descriptions-item>
            <el-descriptions-item label="失败数量">{{
              store.saveResult.failed_count
            }}</el-descriptions-item>
            <el-descriptions-item label="Token 消耗">
              <template v-if="store.batchCost">
                <span>{{ store.batchCost.totalTokens.toLocaleString() }}</span>
                <span class="cost-detail">
                  （输入 {{ store.batchCost.totalPromptTokens.toLocaleString() }} / 输出
                  {{ store.batchCost.totalCompletionTokens.toLocaleString() }}）
                </span>
              </template>
              <el-icon v-else class="spin-icon" :size="14" color="var(--color-info)">
                <Loading />
              </el-icon>
            </el-descriptions-item>
            <el-descriptions-item label="估算成本">
              <template v-if="store.batchCost">
                <span>&yen;{{ (store.batchCost.totalCostUsd * 7.25).toFixed(2) }}</span>
                <span class="cost-detail">
                  （${{ store.batchCost.totalCostUsd.toFixed(4) }}）
                </span>
              </template>
              <el-icon v-else class="spin-icon" :size="14" color="var(--color-info)">
                <Loading />
              </el-icon>
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="store.saveResult.failures.length > 0" class="failure-list">
            <h4>失败明细</h4>
            <div v-for="(f, i) in store.saveResult.failures" :key="i" class="failure-item">
              <el-tag type="danger" size="small">{{ f.title || f.client_id }}</el-tag>
              <span>{{ f.reason }}</span>
            </div>
          </div>
        </template>
      </el-result>
    </template>
    <template v-else-if="store.saveError">
      <ErrorState title="保存失败" :reason="store.saveError" retryable @retry="emit('save')" />
    </template>
    <template #footer>
      <el-button @click="saveResultVisibleLocal = false">关闭</el-button>
      <el-button type="primary" @click="emit('go-to-case-list')">查看已保存用例</el-button>
      <el-button @click="emit('reset')">重新生成</el-button>
    </template>
  </el-dialog>

  <!-- UI 上传对话框 -->
  <el-dialog
    v-model="store.uiUploadDialogVisible"
    title="上传 UI 页面"
    width="500px"
    destroy-on-close
  >
    <el-upload
      ref="uiUploadRef"
      action=""
      :auto-upload="false"
      :limit="20"
      :multiple="true"
      accept=".png,.jpg,.jpeg,.gif,.webp,.bmp"
      drag
      :on-change="handleUIFileChange"
    >
      <el-icon :size="48" color="var(--color-text-disabled)"><Upload /></el-icon>
      <div>拖拽或点击上传 UI 页面截图</div>
      <template #tip>
        <div class="upload-tip">支持 PNG/JPG/GIF/WebP/BMP，单次最多 20 张</div>
      </template>
    </el-upload>
    <template #footer>
      <el-button @click="store.uiUploadDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="store.uiUploading" @click="handleUIUploadSubmit">
        上传并解析
      </el-button>
    </template>
  </el-dialog>

  <!-- 系统用例选择对话框 -->
  <el-dialog
    v-model="systemCaseVisibleLocal"
    title="从系统用例导入"
    width="700px"
    destroy-on-close
  >
    <el-table
      :data="systemCases"
      size="small"
      stripe
      @selection-change="handleSystemCaseSelectionChange"
    >
      <el-table-column type="selection" width="50" />
      <el-table-column prop="title" label="用例标题" show-overflow-tooltip />
      <el-table-column prop="module" label="模块" width="120" show-overflow-tooltip />
      <el-table-column prop="case_type" label="类型" width="80" />
    </el-table>
    <template #footer>
      <el-button @click="systemCaseVisibleLocal = false">取消</el-button>
      <el-button
        type="primary"
        :disabled="selectedSystemCaseIds.length === 0"
        @click="handleImportSystemCases"
      >
        导入选中 ({{ selectedSystemCaseIds.length }})
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Loading, Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSmartGenerationStore } from '@/store/smartGeneration'
import type { SmartPreviewCase } from '@/store/smartGeneration'
import { extractErrorDetail } from '@/store/smartGenerationHelpers'
import request from '@/utils/request'
import ErrorState from './ErrorState.vue'

interface Props {
  editVisible: boolean
  saveResultVisible: boolean
  systemCaseVisible: boolean
  editingCase: SmartPreviewCase | null
  editingClientId: string
  saveMode: 'draft' | 'formal' | 'passed_only'
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:editVisible', value: boolean): void
  (e: 'update:saveResultVisible', value: boolean): void
  (e: 'update:systemCaseVisible', value: boolean): void
  (e: 'save'): void
  (e: 'reset'): void
  (e: 'go-to-case-list'): void
}>()

const store = useSmartGenerationStore()

// 双向绑定可见性状态
const editVisibleLocal = computed({
  get: () => props.editVisible,
  set: (v) => emit('update:editVisible', v),
})
const saveResultVisibleLocal = computed({
  get: () => props.saveResultVisible,
  set: (v) => emit('update:saveResultVisible', v),
})
const systemCaseVisibleLocal = computed({
  get: () => props.systemCaseVisible,
  set: (v) => emit('update:systemCaseVisible', v),
})

// 编辑用例本地副本（避免直接修改原对象）
const editingCaseLocal = ref<SmartPreviewCase | null>(null)

watch(
  () => props.editingCase,
  (val) => {
    editingCaseLocal.value = val ? JSON.parse(JSON.stringify(val)) : null
  },
  { immediate: true }
)

// 系统用例选择
const systemCases = ref<{ id: number; title: string; module: string; case_type: string }[]>([])
const selectedSystemCaseIds = ref<number[]>([])

function extractListData(resp: unknown) {
  const data = (resp as { data?: unknown })?.data || resp
  return Array.isArray(data) ? data : (data as { items?: unknown[] })?.items || []
}

async function loadSystemCases() {
  if (!store.selectedProjectId) {
    systemCases.value = []
    return
  }
  try {
    systemCases.value = extractListData(
      await request.get(
        `/api/v1/test-case/?project_id=${store.selectedProjectId}&page=1&page_size=200`
      )
    ) as { id: number; title: string; module: string; case_type: string }[]
  } catch {
    systemCases.value = []
  }
}

watch(systemCaseVisibleLocal, (val) => {
  if (val) loadSystemCases()
})

function handleSystemCaseSelectionChange(rows: unknown[]) {
  selectedSystemCaseIds.value = rows.map((r) => (r as { id: number }).id)
}

async function handleImportSystemCases() {
  if (selectedSystemCaseIds.value.length === 0) return
  try {
    await store.importSystemCasesAsHistory(selectedSystemCaseIds.value)
    ElMessage.success('系统用例导入成功')
    systemCaseVisibleLocal.value = false
    selectedSystemCaseIds.value = []
  } catch (e: unknown) {
    ElMessage.error(extractErrorDetail(e, '导入失败'))
  }
}

// UI 上传
const uiUploadFiles = ref<File[]>([])
const uiUploadRef = ref()

function handleUIFileChange(_file: unknown, fileList: unknown[]) {
  uiUploadFiles.value = fileList.map((f) => (f as { raw: File }).raw).filter(Boolean)
}

async function handleUIUploadSubmit() {
  if (uiUploadFiles.value.length === 0) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  await store.uploadUIScreens(uiUploadFiles.value)
  uiUploadFiles.value = []
  store.uiUploadDialogVisible = false
  ElMessage.success('上传成功，正在后台解析')
}

// 编辑步骤操作
function updateStepField(idx: number, field: string, value: string) {
  if (!editingCaseLocal.value) return
  const steps = [...editingCaseLocal.value.steps]
  const step = { ...(steps[idx] as Record<string, unknown>) }
  step[field] = value
  steps[idx] = step
  editingCaseLocal.value.steps = steps
}

function removeEditStep(index: number) {
  editingCaseLocal.value?.steps.splice(index, 1)
}

function addEditStep() {
  if (!editingCaseLocal.value) return
  editingCaseLocal.value.steps.push({
    step: editingCaseLocal.value.steps.length + 1,
    action: '',
    expected_result: '',
  })
}

function saveEdit() {
  if (!editingCaseLocal.value) return
  const target = store.previewCases.find((c) => c.client_id === props.editingClientId)
  if (target) {
    target.title = editingCaseLocal.value.title
    target.module = editingCaseLocal.value.module
    target.priority = editingCaseLocal.value.priority
    target.precondition = editingCaseLocal.value.precondition
    target.steps = editingCaseLocal.value.steps
    target.expected_result = editingCaseLocal.value.expected_result
    target.dirty = true
    store.recalcQualitySummary()
  }
  editVisibleLocal.value = false
  ElMessage.success('修改已保存到预览')
}
</script>

<style scoped>
.upload-tip {
  font-size: 12px;
  color: var(--color-info);
}
.spin-icon {
  animation: spin 1.5s linear infinite;
  margin-bottom: 16px;
}
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
.failure-list {
  margin-top: 16px;
  text-align: left;
}
.failure-list h4 {
  margin: 0 0 8px;
}
.failure-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.cost-detail {
  color: var(--color-info);
  font-size: 12px;
  margin-left: 8px;
}
.edit-steps {
  width: 100%;
}
.edit-step-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
</style>
