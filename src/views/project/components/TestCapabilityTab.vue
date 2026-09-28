<template>
  <div class="test-capability-tab" v-loading="loading">
    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="config-tip"
    >
      项目级测试能力定义该项目支持的测试能力点（与测试点关联），用于能力维度的覆盖度统计与执行编排。
    </el-alert>

    <div class="header-actions">
      <el-button type="primary" size="small" @click="openAddDialog">
        <el-icon><Plus /></el-icon>
        新增能力
      </el-button>
    </div>

    <el-table :data="capabilities" style="width: 100%" border stripe size="small">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="key" label="Key" width="180" show-overflow-tooltip />
      <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
        <template #default="scope">
          {{ scope.row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="scope">
          <el-tag :type="getStatusTagType(scope.row.status)">
            {{ getStatusLabel(scope.row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
          <el-button size="small" type="danger" @click="deleteCapability(scope.row)"
            >删除</el-button
          >
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && capabilities.length === 0"
      description="暂无测试能力数据"
    />

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close>
      <el-form :ref="setFormRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="Key" prop="key">
          <el-input v-model="formData.key" placeholder="请输入能力Key，如 login-test" />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="formData.title" placeholder="请输入能力标题" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入能力描述（选填）"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option
              v-for="opt in STATUS_OPTIONS"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveCapability">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { testCapabilityApi } from '@/api/testCapability'
import type {
  TestCapabilityResponse,
  TestCapabilityCreateRequest,
  TestCapabilityUpdateRequest,
} from '@/api/testCapability'

const props = defineProps<{
  projectId: number
}>()

const loading = ref(false)
const saving = ref(false)
const capabilities = ref<TestCapabilityResponse[]>([])

const dialogVisible = ref(false)
const dialogTitle = ref('新增测试能力')
const editMode = ref(false)
const currentCapabilityId = ref<number | null>(null)
const formRef = ref<FormInstance>()

interface CapabilityFormData {
  key: string
  title: string
  description: string
  status: string
}

const formData = reactive<CapabilityFormData>({
  key: '',
  title: '',
  description: '',
  status: 'active',
})

const STATUS_OPTIONS = [
  { label: '活跃', value: 'active' },
  { label: '停用', value: 'inactive' },
  { label: '废弃', value: 'deprecated' },
] as const

const STATUS_TAG_TYPE: Record<string, 'success' | 'info' | 'warning'> = {
  active: 'success',
  inactive: 'info',
  deprecated: 'warning',
}

const formRules = {
  key: [
    { required: true, message: '请输入能力Key', trigger: 'blur' },
    { min: 1, max: 100, message: 'Key长度1-100位', trigger: 'blur' },
  ],
  title: [
    { required: true, message: '请输入能力标题', trigger: 'blur' },
    { min: 1, max: 200, message: '标题长度1-200位', trigger: 'blur' },
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const setFormRef = (el: unknown) => {
  formRef.value = el as FormInstance | undefined
}

const loadCapabilities = async (): Promise<void> => {
  if (!props.projectId) {
    capabilities.value = []
    return
  }
  loading.value = true
  try {
    const response = await testCapabilityApi.getList({
      project_id: props.projectId,
    })
    capabilities.value = Array.isArray(response.data) ? response.data : []
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '获取测试能力列表失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

const getStatusTagType = (status: string): 'success' | 'info' | 'warning' => {
  return STATUS_TAG_TYPE[status] ?? 'info'
}

const getStatusLabel = (status: string): string => {
  const option = STATUS_OPTIONS.find((o) => o.value === status)
  return option?.label ?? status
}

const resetForm = (): void => {
  Object.assign(formData, {
    key: '',
    title: '',
    description: '',
    status: 'active',
  })
  currentCapabilityId.value = null
}

const openAddDialog = (): void => {
  editMode.value = false
  dialogTitle.value = '新增测试能力'
  resetForm()
  dialogVisible.value = true
}

const openEditDialog = (row: TestCapabilityResponse): void => {
  editMode.value = true
  dialogTitle.value = '编辑测试能力'
  currentCapabilityId.value = row.id
  Object.assign(formData, {
    key: row.key,
    title: row.title,
    description: row.description ?? '',
    status: row.status,
  })
  dialogVisible.value = true
}

const saveCapability = async (): Promise<void> => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (editMode.value && currentCapabilityId.value !== null) {
      const updateData: TestCapabilityUpdateRequest = {
        key: formData.key,
        title: formData.title,
        description: formData.description || undefined,
        status: formData.status,
      }
      await testCapabilityApi.update(currentCapabilityId.value, updateData)
      ElMessage.success('测试能力更新成功')
    } else {
      const createData: TestCapabilityCreateRequest = {
        project_id: props.projectId,
        key: formData.key,
        title: formData.title,
        description: formData.description || undefined,
        status: formData.status,
      }
      await testCapabilityApi.create(createData)
      ElMessage.success('测试能力创建成功')
    }
    dialogVisible.value = false
    await loadCapabilities()
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : '保存失败'
    ElMessage.error(message)
  } finally {
    saving.value = false
  }
}

const deleteCapability = (row: TestCapabilityResponse): void => {
  ElMessageBox.confirm(`确定要删除测试能力「${row.title}」吗？`, '确认删除', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        await testCapabilityApi.delete(row.id)
        ElMessage.success('删除成功')
        await loadCapabilities()
      } catch (error: unknown) {
        const msg = error instanceof Error ? error.message : '删除失败'
        ElMessage.error(msg)
      }
    })
    .catch(() => {
      /* 用户取消 */
    })
}

watch(
  () => props.projectId,
  (newVal) => {
    if (newVal) loadCapabilities()
    else capabilities.value = []
  }
)

onMounted(() => {
  loadCapabilities()
})
</script>

<style scoped>
.test-capability-tab {
  padding: 4px 0;
}
.config-tip {
  margin-bottom: 16px;
}
.header-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}
.dialog-footer {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
